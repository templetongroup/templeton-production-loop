from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from templeton_loop.boundaries import BoundaryError
from templeton_loop import proof as proof_module
from templeton_loop.proof import (
    MANIFEST_VERSION,
    ProofError,
    build_hermes_command,
    build_openclaw_command,
    dry_run,
    lint_manifest,
    load_manifest,
    run_proof,
    verify_event_chain,
)

ORIGINAL_VERIFIER_COMMAND = proof_module._verifier_command


@pytest.fixture(autouse=True)
def _fake_runtime_preflight(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(
        proof_module,
        "verify_hermes_runtime",
        lambda **_kwargs: {
            "ok": True,
            "runtime": "fake-test",
            "image": "test-worker@sha256:" + ("a" * 64),
            "home": str(tmp_path / "hermes-home"),
        },
    )
    monkeypatch.setattr(
        proof_module,
        "_verifier_command",
        lambda _workspace, argv, _image: list(argv),
    )


def write_manifest(tmp_path: Path, **changes: object) -> Path:
    source_root = tmp_path / "source"
    source_root.mkdir(exist_ok=True)
    (source_root / "README.md").write_text("source stays unchanged\n", encoding="utf-8")
    data: dict[str, object] = {
        "version": MANIFEST_VERSION,
        "name": "proof-demo",
        "source_root": "source",
        "source_paths": ["README.md"],
        "strategy": {
            "model": "strong-strategy-model",
            "provider": "strategy-provider",
            "profile": "strategy-profile",
            "prompt": "Plan the work.",
            "max_turns": 7,
            "timeout_seconds": 30,
        },
        "worker": {
            "model": "cheap-worker-model",
            "provider": "worker-provider",
            "profile": "worker-profile",
            "max_turns": 11,
            "timeout_seconds": 30,
        },
        "max_parallel": 2,
        "retries": 1,
        "env_allowlist": ["PATH"],
        "tasks": [
            {
                "id": "alpha",
                "brief": "Create the alpha artifact.",
                "expected_files": ["alpha.txt"],
                "verifiers": [
                    {
                        "argv": ["python3", "-c", "from pathlib import Path; assert Path('alpha.txt').stat().st_size"],
                        "timeout_seconds": 5,
                    }
                ],
            },
            {
                "id": "beta",
                "brief": "Create the beta artifact.",
                "model": "override-worker-model",
                "expected_files": ["nested/beta.txt"],
                "verifiers": [
                    {
                        "argv": ["python3", "-c", "from pathlib import Path; assert Path('nested/beta.txt').stat().st_size"],
                        "timeout_seconds": 5,
                    }
                ],
                "retries": 0,
            },
        ],
    }
    data.update(changes)
    path = tmp_path / "proof.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_manifest_resolves_sources_and_worker_overrides(tmp_path: Path):
    path = write_manifest(tmp_path)

    manifest = load_manifest(path)

    assert manifest.version == MANIFEST_VERSION
    assert manifest.source_root == (tmp_path / "source").resolve()
    assert manifest.source_paths == (Path("README.md"),)
    assert manifest.resolved_source_paths == ((tmp_path / "source" / "README.md").resolve(),)
    assert manifest.strategy.model == "strong-strategy-model"
    assert manifest.worker.model == "cheap-worker-model"
    assert manifest.tasks[0].worker_route(manifest.worker).model == "cheap-worker-model"
    assert manifest.tasks[1].worker_route(manifest.worker).model == "override-worker-model"
    assert manifest.tasks[1].retries == 0


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"version": 999}, "version"),
        ({"strategy": {"prompt": "missing model"}}, "model"),
        ({"worker": {"model": ""}}, "model"),
        ({"name": "a" * 65}, "at most 64"),
        ({"unexpected": True}, "unexpected"),
        ({"tasks": []}, "tasks"),
    ],
)
def test_load_manifest_rejects_invalid_or_unknown_schema(tmp_path: Path, change: dict[str, object], message: str):
    path = write_manifest(tmp_path, **change)

    with pytest.raises(ProofError, match=message):
        load_manifest(path)


def test_manifest_requires_verifier_and_caps_retries_at_one(tmp_path: Path):
    path = write_manifest(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["tasks"][0]["verifiers"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProofError, match="non-empty"):
        load_manifest(path)

    path = write_manifest(tmp_path, retries=2)
    with pytest.raises(ProofError, match="between 0 and 1"):
        load_manifest(path)


@pytest.mark.parametrize(
    ("field", "unsafe"),
    [
        ("source_paths", ["../outside.txt"]),
        ("source_paths", ["/absolute.txt"]),
        ("source_paths", ["./README.md"]),
        ("source_paths", ["README.md/"]),
        ("expected_files", ["../escape.txt"]),
        ("expected_files", ["/tmp/escape.txt"]),
        ("expected_files", ["reports//result.txt"]),
    ],
)
def test_manifest_rejects_unsafe_paths(tmp_path: Path, field: str, unsafe: list[str]):
    path = write_manifest(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if field == "source_paths":
        data[field] = unsafe
    else:
        data["tasks"][0][field] = unsafe
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ProofError, match="relative|traversal|safe"):
        load_manifest(path)


def test_manifest_rejects_missing_source_and_symlink(tmp_path: Path):
    path = write_manifest(tmp_path, source_paths=["missing.txt"])
    with pytest.raises(ProofError, match="does not exist"):
        load_manifest(path)

    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    link = tmp_path / "source" / "link.txt"
    link.symlink_to(outside)
    path = write_manifest(tmp_path, source_paths=["link.txt"])
    with pytest.raises(ProofError, match="symbolic link"):
        load_manifest(path)


def test_manifest_rejects_sensitive_declared_paths_and_content(tmp_path: Path):
    package = tmp_path / "source" / "pkg"
    package.mkdir(parents=True)
    (package / "safe.txt").write_text("safe\n", encoding="utf-8")
    (package / ".env").write_text("PASSWORD=not-for-proof\n", encoding="utf-8")
    path = write_manifest(tmp_path, source_paths=["pkg"])
    with pytest.raises(ProofError, match="sensitive path"):
        load_manifest(path)

    (package / ".env").unlink()
    (package / "token.txt").write_text("ghp_" + "A" * 32, encoding="utf-8")
    with pytest.raises(ProofError, match="credential-like"):
        load_manifest(path)


def test_run_revalidates_loaded_source_and_rejects_symlink_substitution(tmp_path: Path):
    path = write_manifest(tmp_path)
    manifest = load_manifest(path)
    declared = tmp_path / "source" / "README.md"
    outside = tmp_path / "credential.txt"
    outside.write_text("machine example.test password must-not-copy\n", encoding="utf-8")
    declared.unlink()
    declared.symlink_to(outside)
    run_root = tmp_path / "runs"

    with pytest.raises(ProofError, match="symbolic link"):
        run_proof(
            manifest,
            run_root=run_root,
            hermes_executable=make_fake_hermes(tmp_path),
            environ={"PATH": os.environ["PATH"]},
        )

    assert not run_root.exists()


def test_run_rejects_same_content_source_identity_replacement(tmp_path: Path):
    path = write_manifest(tmp_path)
    manifest = load_manifest(path)
    declared = tmp_path / "source" / "README.md"
    replacement = tmp_path / "replacement.md"
    replacement.write_bytes(declared.read_bytes())
    replacement.replace(declared)

    with pytest.raises(ProofError, match="changed after manifest validation"):
        run_proof(
            manifest,
            run_root=tmp_path / "runs",
            hermes_executable=make_fake_hermes(tmp_path),
            environ={"PATH": os.environ["PATH"]},
        )


def test_manifest_rejects_invalid_environment_variable_names(tmp_path: Path):
    path = write_manifest(tmp_path, env_allowlist=["PATH", "TOKEN=value"])

    with pytest.raises(ProofError, match="environment variable names"):
        load_manifest(path)


def test_manifest_rejects_overlapping_source_and_artifact_paths(tmp_path: Path):
    source = tmp_path / "source" / "docs"
    source.mkdir(parents=True)
    (source / "guide.md").write_text("guide\n", encoding="utf-8")
    path = write_manifest(tmp_path, source_paths=["docs", "docs/guide.md"])

    with pytest.raises(ProofError, match="must not overlap"):
        load_manifest(path)

    path = write_manifest(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["tasks"][0]["expected_files"] = ["reports", "reports/result.txt"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProofError, match="must not overlap"):
        load_manifest(path)


def test_artifact_check_rejects_symlink_in_parent_path(tmp_path: Path):
    output = tmp_path / "output"
    actual = output / "actual"
    actual.mkdir(parents=True)
    (actual / "result.txt").write_text("content\n", encoding="utf-8")
    (output / "alias").symlink_to(actual, target_is_directory=True)

    artifacts, failure = proof_module._check_expected_files(output, [Path("alias/result.txt")])

    assert artifacts == []
    assert failure and "symbolic link" in failure


def test_build_hermes_command_routes_explicit_model_provider_and_profile():
    path = Path("/tmp/unused")
    from templeton_loop.proof import ModelRoute

    route = ModelRoute(
        model="explicit-model",
        provider="explicit-provider",
        profile="isolated-profile",
        max_turns=9,
        timeout_seconds=20,
    )
    command = build_hermes_command(route, "bounded prompt", executable=path)

    assert command[:3] == [str(path), "--profile", "isolated-profile"]
    assert command[3] == "chat"
    assert command[command.index("--model") + 1] == "explicit-model"
    assert command[command.index("--provider") + 1] == "explicit-provider"
    assert command[command.index("--max-turns") + 1] == "9"
    assert command[command.index("--query") + 1] == "bounded prompt"
    assert "--quiet" in command
    assert "--ignore-rules" in command
    assert "--safe-mode" not in command
    assert command[command.index("--source") + 1] == "tool"
    assert "--yolo" not in command
    assert not any("hook" in part for part in command)


def test_verifier_command_is_air_gapped_non_root_and_capability_dropped(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    command = ORIGINAL_VERIFIER_COMMAND(
        workspace,
        ["python", "-m", "pytest", "-q"],
        "worker@sha256:" + "a" * 64,
    )

    assert command[:2] == ["docker", "run"]
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges" in command
    assert "--user" in command
    assert command[-4:] == ["python", "-m", "pytest", "-q"]


def test_lint_and_dry_run_expose_exact_routing_without_execution(tmp_path: Path):
    path = write_manifest(tmp_path)

    linted = lint_manifest(path)
    planned = dry_run(path, hermes_executable="fake-hermes")

    assert linted["status"] == "valid"
    assert linted["task_count"] == 2
    assert planned["status"] == "dry-run"
    assert planned["strategy"]["model"] == "strong-strategy-model"
    assert planned["strategy"]["command"][0] == "fake-hermes"
    assert [task["model"] for task in planned["tasks"]] == [
        "cheap-worker-model",
        "override-worker-model",
    ]
    for row in [planned["strategy"], *planned["tasks"]]:
        assert row["command"][row["command"].index("--model") + 1] == row["model"]


FAKE_HERMES = r'''#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path


def option(name):
    return sys.argv[sys.argv.index(name) + 1]

def prompt_option():
    return option("--message") if "--message" in sys.argv else option("--query")

phase = os.environ["TEMPLETON_PHASE"]
task = os.environ.get("TEMPLETON_TASK_ID")
attempt = int(os.environ.get("TEMPLETON_ATTEMPT", "0"))
record = {
    "phase": phase,
    "task": task,
    "attempt": attempt,
    "model": option("--model"),
    "prompt": prompt_option(),
    "cwd": os.getcwd(),
    "output_dir": os.environ.get("TEMPLETON_OUTPUT_DIR"),
    "secret_visible": "DO_NOT_INHERIT" in os.environ,
}
with open(os.environ["FAKE_HERMES_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")

if phase == "strategy":
    strategy = "<strategy>Use the copied source and write only declared artifacts.</strategy>"
    print(json.dumps({"text": strategy}) if "--message" in sys.argv else strategy)
    raise SystemExit(0)

sync = Path(os.environ["FAKE_SYNC_DIR"])
sync.mkdir(parents=True, exist_ok=True)
if attempt == 1 and os.environ.get("FAKE_PARALLEL"):
    (sync / task).write_text("started", encoding="utf-8")
    deadline = time.monotonic() + 3
    while len(list(sync.iterdir())) < 2 and time.monotonic() < deadline:
        time.sleep(0.02)
    if len(list(sync.iterdir())) < 2:
        print("workers did not overlap", file=sys.stderr)
        raise SystemExit(23)

output = Path(os.environ["TEMPLETON_OUTPUT_DIR"])
if task == "alpha" and attempt == 1:
    (output / "alpha.txt").write_text("", encoding="utf-8")
    print("intentionally produced an empty artifact", file=sys.stderr)
    raise SystemExit(0)
if task == "alpha":
    (output / "alpha.txt").write_text("alpha complete\n", encoding="utf-8")
else:
    target = output / "nested" / "beta.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("beta complete\n", encoding="utf-8")
print("worker complete")
'''


def make_fake_hermes(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-hermes"
    executable.write_text(FAKE_HERMES, encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable


def test_run_proof_routes_strategy_and_parallel_workers_with_retry(tmp_path: Path):
    log_path = tmp_path / "hermes.jsonl"
    sync_dir = tmp_path / "sync"
    manifest_path = write_manifest(
        tmp_path,
        env_allowlist=["PATH", "FAKE_HERMES_LOG", "FAKE_SYNC_DIR", "FAKE_PARALLEL"],
    )
    fake_hermes = make_fake_hermes(tmp_path)
    source_file = tmp_path / "source" / "README.md"
    original = source_file.read_bytes()
    environment = {
        "PATH": os.environ["PATH"],
        "FAKE_HERMES_LOG": str(log_path),
        "FAKE_SYNC_DIR": str(sync_dir),
        "FAKE_PARALLEL": "1",
        "DO_NOT_INHERIT": "top-secret",
    }

    state = run_proof(
        manifest_path,
        run_root=tmp_path / "runs",
        hermes_executable=fake_hermes,
        environ=environment,
    )

    assert state["status"] == "passed"
    assert state["strategy"]["model"] == "strong-strategy-model"
    assert state["strategy"]["attempts"] == 1
    assert [task["model"] for task in state["tasks"]] == [
        "cheap-worker-model",
        "override-worker-model",
    ]
    alpha, beta = state["tasks"]
    assert len(alpha["attempts"]) == 2
    assert alpha["attempts"][0]["status"] == "failed"
    assert "empty" in alpha["attempts"][0]["failure"].lower()
    assert alpha["attempts"][1]["status"] == "passed"
    assert len(beta["attempts"]) == 1
    assert beta["status"] == "passed"

    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    strategy_rows = [row for row in rows if row["phase"] == "strategy"]
    worker_rows = [row for row in rows if row["phase"] == "worker"]
    assert len(strategy_rows) == 1
    assert strategy_rows[0]["model"] == "strong-strategy-model"
    assert {row["task"]: row["model"] for row in worker_rows if row["attempt"] == 1} == {
        "alpha": "cheap-worker-model",
        "beta": "override-worker-model",
    }
    assert all(not row["secret_visible"] for row in rows)
    assert len({row["cwd"] for row in worker_rows if row["attempt"] == 1}) == 2
    retry = next(row for row in worker_rows if row["task"] == "alpha" and row["attempt"] == 2)
    assert "Use the copied source" in retry["prompt"]
    assert "empty" in retry["prompt"].lower()
    assert "Create the alpha artifact" in retry["prompt"]

    run_dir = Path(state["run_dir"])
    strategy_artifact = run_dir / state["strategy"]["artifact"]
    assert strategy_artifact.read_text(encoding="utf-8").startswith("<strategy>")
    assert source_file.read_bytes() == original
    snapshot_files = list(run_dir.glob("tasks/*/attempt-*/source/README.md"))
    assert len(snapshot_files) == 3
    assert all(not (path.stat().st_mode & stat.S_IWUSR) for path in snapshot_files)
    assert (run_dir / alpha["artifacts"][0]).read_text(encoding="utf-8") == "alpha complete\n"
    assert (run_dir / beta["artifacts"][0]).read_text(encoding="utf-8") == "beta complete\n"


def test_verifier_timeout_is_failure_evidence_and_respects_retry_bound(tmp_path: Path):
    manifest_path = write_manifest(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["tasks"] = [
        {
            "id": "beta",
            "brief": "Create the beta artifact.",
            "expected_files": ["nested/beta.txt"],
            "verifiers": [{"argv": ["python3", "-c", "import time; time.sleep(2)"], "timeout_seconds": 1}],
            "retries": 0,
        }
    ]
    data["env_allowlist"] = ["PATH", "FAKE_HERMES_LOG", "FAKE_SYNC_DIR"]
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    fake_hermes = make_fake_hermes(tmp_path)
    environment = {
        "PATH": os.environ["PATH"],
        "FAKE_HERMES_LOG": str(tmp_path / "timeout-log.jsonl"),
        "FAKE_SYNC_DIR": str(tmp_path / "timeout-sync"),
    }

    state = run_proof(
        manifest_path,
        run_root=tmp_path / "runs",
        hermes_executable=fake_hermes,
        environ=environment,
    )

    assert state["status"] == "failed"
    attempt = state["tasks"][0]["attempts"][0]
    assert attempt["status"] == "failed"
    assert "timed out" in attempt["failure"].lower()
    assert attempt["verifiers"][0]["timed_out"] is True


def test_proof_sinks_redact_verifier_output_and_manifest_values(tmp_path: Path):
    manifest_path = write_manifest(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["tasks"] = [data["tasks"][0]]
    data["tasks"][0]["verifiers"] = [
        {"argv": ["python3", "-c", "print('Bearer abcdefghijklmnop')"]}
    ]
    data["env_allowlist"] = ["PATH", "FAKE_HERMES_LOG", "FAKE_SYNC_DIR"]
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    state = run_proof(
        manifest_path,
        run_root=tmp_path / "runs",
        hermes_executable=make_fake_hermes(tmp_path),
        environ={
            "PATH": os.environ["PATH"],
            "FAKE_HERMES_LOG": str(tmp_path / "redaction-log.jsonl"),
            "FAKE_SYNC_DIR": str(tmp_path / "redaction-sync"),
        },
    )
    run_dir = Path(state["run_dir"])
    for relative in ("manifest.json", "state.json", "events.jsonl", "report.md"):
        text = (run_dir / relative).read_text(encoding="utf-8")
        assert "abcdefghijklmnop" not in text
    verifier = state["tasks"][0]["attempts"][-1]["verifiers"][0]
    verifier_stdout = (run_dir / verifier["stdout"]).read_text(encoding="utf-8")
    assert verifier_stdout.strip() == "[REDACTED]"


def test_proof_blocks_secret_positive_model_prompt(tmp_path: Path):
    manifest_path = write_manifest(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["strategy"]["prompt"] = "Plan without leaking Bearer abcdefghijklmnop"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(BoundaryError, match="proof-strategy-prompt"):
        run_proof(
            manifest_path,
            run_root=tmp_path / "runs",
            hermes_executable=make_fake_hermes(tmp_path),
            environ={"PATH": os.environ["PATH"]},
        )


def test_passing_verifier_cannot_delete_or_empty_artifact(tmp_path: Path):
    manifest_path = write_manifest(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["tasks"] = [data["tasks"][1]]
    data["tasks"][0]["verifiers"] = [
        {
            "argv": [
                "python3",
                "-c",
                "from pathlib import Path; Path('nested/beta.txt').write_text('')",
            ]
        }
    ]
    data["env_allowlist"] = ["PATH", "FAKE_HERMES_LOG", "FAKE_SYNC_DIR"]
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    state = run_proof(
        manifest_path,
        run_root=tmp_path / "runs",
        hermes_executable=make_fake_hermes(tmp_path),
        environ={
            "PATH": os.environ["PATH"],
            "FAKE_HERMES_LOG": str(tmp_path / "mutation-log.jsonl"),
            "FAKE_SYNC_DIR": str(tmp_path / "mutation-sync"),
        },
    )
    attempt = state["tasks"][0]["attempts"][0]
    assert state["status"] == "failed"
    assert attempt["verifiers"][0]["status"] == "failed"
    assert "invalidated artifacts" in attempt["failure"]


def test_passing_verifier_cannot_rewrite_artifact(tmp_path: Path):
    manifest_path = write_manifest(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["tasks"] = [data["tasks"][1]]
    data["tasks"][0]["verifiers"] = [
        {
            "argv": [
                "python3",
                "-c",
                "from pathlib import Path; Path('nested/beta.txt').write_text('rewritten')",
            ]
        }
    ]
    data["env_allowlist"] = ["PATH", "FAKE_HERMES_LOG", "FAKE_SYNC_DIR"]
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    state = run_proof(
        manifest_path,
        run_root=tmp_path / "runs",
        hermes_executable=make_fake_hermes(tmp_path),
        environ={
            "PATH": os.environ["PATH"],
            "FAKE_HERMES_LOG": str(tmp_path / "rewrite-log.jsonl"),
            "FAKE_SYNC_DIR": str(tmp_path / "rewrite-sync"),
        },
    )
    attempt = state["tasks"][0]["attempts"][0]
    assert state["status"] == "failed"
    assert attempt["verifiers"][0]["artifact_failure"] == "verifier mutated a declared artifact"
    events_path = Path(state["run_dir"]) / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    assert any(event["event"] == "verifier_mutation_detected" for event in events)


def test_run_root_must_be_outside_source_root(tmp_path: Path):
    manifest_path = write_manifest(tmp_path)
    with pytest.raises(ProofError, match="outside source_root"):
        run_proof(
            manifest_path,
            run_root=tmp_path / "source" / ".runs",
            hermes_executable=make_fake_hermes(tmp_path),
            environ={"PATH": os.environ["PATH"]},
        )


def test_evidence_state_events_and_reports_are_atomic_versioned_and_escaped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest_path = write_manifest(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["tasks"] = [data["tasks"][1]]
    data["env_allowlist"] = ["PATH", "FAKE_HERMES_LOG", "FAKE_SYNC_DIR"]
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    fake_hermes = make_fake_hermes(tmp_path)
    environment = {
        "PATH": os.environ["PATH"],
        "FAKE_HERMES_LOG": str(tmp_path / "report-log.jsonl"),
        "FAKE_SYNC_DIR": str(tmp_path / "report-sync"),
    }
    replacements: list[tuple[Path, Path]] = []
    real_replace = proof_module.os.replace

    def recording_replace(source: str | Path, destination: str | Path) -> None:
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(proof_module.os, "replace", recording_replace)

    state = run_proof(
        manifest_path,
        run_root=tmp_path / "runs",
        hermes_executable=fake_hermes,
        environ=environment,
    )

    run_dir = Path(state["run_dir"])
    assert json.loads((run_dir / state["manifest_artifact"]).read_text(encoding="utf-8")) == json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    disk_state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert disk_state == state
    assert disk_state["version"] == proof_module.STATE_VERSION
    state_replacements = [(source, destination) for source, destination in replacements if destination.name == "state.json"]
    assert len(state_replacements) >= 2
    assert len({source.name for source, _ in state_replacements}) == len(state_replacements)
    assert all(destination == run_dir / "state.json" for _, destination in state_replacements)
    assert all(not source.exists() for source, _ in state_replacements)

    events = [
        json.loads(line)
        for line in (run_dir / state["events"]).read_text(encoding="utf-8").splitlines()
    ]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert all(event["version"] == proof_module.STATE_VERSION for event in events)
    assert all(event["at"].endswith("+00:00") for event in events)
    assert events[-1]["event"] == "run_completed"
    assert {event["event"] for event in events} >= {
        "strategy_started",
        "strategy_completed",
        "worker_started",
        "artifact_check_completed",
        "verifier_started",
        "verifier_completed",
        "worker_completed",
        "run_completed",
    }

    markdown_path = run_dir / state["reports"]["markdown"]
    html_path = run_dir / state["reports"]["html"]
    markdown = markdown_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    assert "# Templeton Proof Report: proof-demo" in markdown
    assert "**Final status:** PASSED" in markdown
    assert "strong-strategy-model" in markdown
    assert "override-worker-model" in markdown
    assert "nested/beta.txt" in markdown
    assert "Attempt 1" in markdown
    assert "Verifier 1: PASSED" in markdown
    assert "<strategy>Use the copied source" in markdown
    assert "<strategy>" not in html
    assert "&lt;strategy&gt;Use the copied source" in html
    assert "override-worker-model" in html
    assert "evidence_sealed" in {event["event"] for event in events}
    events_path = run_dir / state["events"]
    assert verify_event_chain(events_path)["ok"] is True

    sealed_paths = [
        run_dir / state["tasks"][0]["artifacts"][0],
        run_dir / state["tasks"][0]["attempts"][-1]["verifiers"][0]["stdout"],
        markdown_path,
    ]
    for sealed_path in sealed_paths:
        original = sealed_path.read_bytes()
        sealed_path.write_bytes(original + b"tampered\n")
        with pytest.raises(ProofError, match="evidence digest mismatch"):
            verify_event_chain(events_path)
        sealed_path.write_bytes(original)
    assert verify_event_chain(events_path)["ok"] is True

    outside_dir = tmp_path / "outside-evidence"
    outside_dir.mkdir()
    evidence_link = run_dir / "linked-evidence"
    try:
        evidence_link.symlink_to(outside_dir, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ProofError, match="symbolic link"):
        verify_event_chain(events_path)


def test_internal_task_error_finishes_with_failed_state_and_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest_path = write_manifest(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["tasks"] = [data["tasks"][1]]
    data["env_allowlist"] = ["PATH", "FAKE_HERMES_LOG", "FAKE_SYNC_DIR"]
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    fake_hermes = make_fake_hermes(tmp_path)
    environment = {
        "PATH": os.environ["PATH"],
        "FAKE_HERMES_LOG": str(tmp_path / "internal-error-log.jsonl"),
        "FAKE_SYNC_DIR": str(tmp_path / "internal-error-sync"),
    }

    def fail_task(*args: object, **kwargs: object) -> dict[str, object]:
        raise RuntimeError("simulated workspace failure")

    monkeypatch.setattr(proof_module, "_run_task", fail_task)
    state = run_proof(
        manifest_path,
        run_root=tmp_path / "runs",
        hermes_executable=fake_hermes,
        environ=environment,
    )

    assert state["status"] == "failed"
    assert state["tasks"][0]["status"] == "failed"
    assert "simulated workspace failure" in state["tasks"][0]["failure"]
    run_dir = Path(state["run_dir"])
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    assert any(event["event"] == "task_internal_error" for event in events)
    assert events[-1]["event"] == "run_completed"


def test_declared_source_change_fails_run_and_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest_path = write_manifest(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["tasks"] = [data["tasks"][1]]
    data["env_allowlist"] = ["PATH", "FAKE_HERMES_LOG", "FAKE_SYNC_DIR"]
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    fake_hermes = make_fake_hermes(tmp_path)
    environment = {
        "PATH": os.environ["PATH"],
        "FAKE_HERMES_LOG": str(tmp_path / "source-change-log.jsonl"),
        "FAKE_SYNC_DIR": str(tmp_path / "source-change-sync"),
    }
    original_run_task = proof_module._run_task

    def run_then_mutate(*args: object, **kwargs: object) -> dict[str, object]:
        task_state = original_run_task(*args, **kwargs)
        (tmp_path / "source" / "README.md").write_text("mutated during run\n", encoding="utf-8")
        return task_state

    monkeypatch.setattr(proof_module, "_run_task", run_then_mutate)
    state = run_proof(
        manifest_path,
        run_root=tmp_path / "runs",
        hermes_executable=fake_hermes,
        environ=environment,
    )

    assert state["tasks"][0]["status"] == "passed"
    assert state["status"] == "failed"
    assert state["source_integrity"] == {"status": "failed", "changed": ["README.md"]}
    run_dir = Path(state["run_dir"])
    report = (run_dir / state["reports"]["markdown"]).read_text(encoding="utf-8")
    assert "Declared source integrity: **FAILED**" in report
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    assert any(event["event"] == "source_integrity_failed" for event in events)


def test_final_artifact_seal_detects_late_cross_task_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest_path = write_manifest(
        tmp_path,
        max_parallel=1,
        env_allowlist=["PATH", "FAKE_HERMES_LOG", "FAKE_SYNC_DIR"],
    )
    fake_hermes = make_fake_hermes(tmp_path)
    environment = {
        "PATH": os.environ["PATH"],
        "FAKE_HERMES_LOG": str(tmp_path / "seal-log.jsonl"),
        "FAKE_SYNC_DIR": str(tmp_path / "seal-sync"),
    }
    original_run_task = proof_module._run_task
    sealed_alpha: list[str] = []

    def run_then_tamper(*args: object, **kwargs: object) -> dict[str, object]:
        task_state = original_run_task(*args, **kwargs)
        if task_state["id"] == "alpha":
            sealed_alpha[:] = list(task_state["artifacts"])
        if task_state["id"] == "beta":
            run_dir = Path(kwargs["run_dir"])
            (run_dir / sealed_alpha[0]).write_text("tampered after verification\n", encoding="utf-8")
        return task_state

    monkeypatch.setattr(proof_module, "_run_task", run_then_tamper)
    state = run_proof(
        manifest_path,
        run_root=tmp_path / "runs",
        hermes_executable=fake_hermes,
        environ=environment,
    )
    assert state["status"] == "failed"
    assert state["artifact_integrity"]["status"] == "failed"
    assert state["tasks"][0]["status"] == "failed"


def test_openclaw_live_proof_execution_uses_empty_one_shot_workspace_and_exact_policy(
    tmp_path: Path,
):
    manifest_path = write_manifest(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["strategy"].pop("profile")
    data["worker"].pop("profile")
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    data["tasks"] = [data["tasks"][1]]
    data["env_allowlist"] = ["PATH", "FAKE_HERMES_LOG", "FAKE_SYNC_DIR"]
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    run_root = tmp_path / "openclaw-runs"
    run_root.mkdir()
    fake_openclaw = make_fake_hermes(tmp_path)
    environment = {
        "PATH": os.environ["PATH"],
        "FAKE_HERMES_LOG": str(tmp_path / "openclaw.jsonl"),
        "FAKE_SYNC_DIR": str(tmp_path / "openclaw-sync"),
    }
    preflights: list[dict[str, object]] = []

    def preflight(**kwargs: object) -> dict[str, object]:
        preflights.append(kwargs)
        return {
            "ok": True,
            "runtime": "openclaw",
            "image": "test-worker@sha256:" + ("a" * 64),
        }

    state = run_proof(
        manifest_path,
        run_root=run_root,
        hermes_executable=fake_openclaw,
        environ=environment,
        runtime_verifier=preflight,
        runtime="openclaw",
        agent_id="templeton-prove",
    )
    assert state["status"] == "passed"
    assert state["artifact_integrity"]["status"] == "passed"
    assert preflights[0]["workspace"] == run_root.resolve()
    assert preflights[0]["role"] == "prove"

    with pytest.raises(ProofError, match="must be empty"):
        run_proof(
            manifest_path,
            run_root=run_root,
            hermes_executable=fake_openclaw,
            environ=environment,
            runtime_verifier=preflight,
            runtime="openclaw",
            agent_id="templeton-prove",
        )

    with pytest.raises(ProofError, match="agent id"):
        build_openclaw_command(
            load_manifest(manifest_path).strategy,
            "prompt",
            agent_id="../escape",
            session_key="agent:x:test",
        )


def test_event_chain_requires_sealed_evidence_and_includes_nested_state_names(tmp_path: Path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "state.json").write_text("{}\n", encoding="utf-8")
    nested = evidence / "task"
    nested.mkdir()
    (nested / "state.json").write_text("nested\n", encoding="utf-8")
    (nested / "events.jsonl").write_text("nested events\n", encoding="utf-8")
    events = proof_module._EventWriter(evidence / "events.jsonl")
    events.append("run_started")

    inventory = proof_module._sealed_evidence_inventory(evidence)
    sealed_paths = {record["path"] for record in inventory}
    assert "task/state.json" in sealed_paths
    assert "task/events.jsonl" in sealed_paths
    assert "state.json" not in sealed_paths
    assert "events.jsonl" not in sealed_paths
    with pytest.raises(ProofError, match="missing the required evidence_sealed"):
        verify_event_chain(evidence / "events.jsonl")


def test_openclaw_proof_rejects_preflight_workspace_mutation(tmp_path: Path):
    manifest_path = write_manifest(tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["strategy"].pop("profile")
    data["worker"].pop("profile")
    data["tasks"] = [data["tasks"][1]]
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    run_root = tmp_path / "openclaw-runs"
    run_root.mkdir()

    def mutating_preflight(**kwargs: object) -> dict[str, object]:
        workspace = Path(kwargs["workspace"])
        (workspace / "unexpected.txt").write_text("mutated\n", encoding="utf-8")
        return {"ok": True, "image": "worker@sha256:" + "a" * 64}

    with pytest.raises(ProofError, match="mutated during policy preflight"):
        run_proof(
            manifest_path,
            run_root=run_root,
            hermes_executable=make_fake_hermes(tmp_path),
            environ={"PATH": os.environ["PATH"]},
            runtime_verifier=mutating_preflight,
            runtime="openclaw",
            agent_id="templeton-prove",
        )
