import json
import os
from pathlib import Path
import sys

import pytest

from templeton_loop import proof as proof_module
from templeton_loop.cli import Candidate, Repo, agent_command, parser
from templeton_loop.connector import (
    ConnectorError,
    connector_command,
    load_connector_config,
    verify_connector_runtime,
)
from templeton_loop.edition import EDITION
from templeton_loop.proof import ModelRoute, build_connector_command, dry_run, run_proof


def make_connector(tmp_path: Path, *, bad_network: bool = False) -> Path:
    script = tmp_path / "connector.py"
    script.write_text(
        """#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("action", choices=("preflight", "invoke"))
parser.add_argument("--role", required=True)
parser.add_argument("--workspace", required=True)
parser.add_argument("--message")
parser.add_argument("--max-turns")
parser.add_argument("--timeout")
parser.add_argument("--phase")
parser.add_argument("--model")
parser.add_argument("--provider")
parser.add_argument("--profile")
parser.add_argument("--json", action="store_true")
args = parser.parse_args()
log_path = os.environ.get("TEST_CONNECTOR_LOG")
if log_path:
    with Path(log_path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"action": args.action, "role": args.role, "workspace": str(Path(args.workspace).resolve())}) + "\\n")
if args.action == "preflight":
    access = {"spec": "none", "build": "rw", "review": "ro", "qa": "ro", "prove": "rw"}[args.role]
    print(json.dumps({
        "schema": "templeton.connector-preflight.v1",
        "id": "test-harness",
        "role": args.role,
        "workspace": str(Path(args.workspace).resolve()),
        "workspace_access": access,
        "structured_output": True,
        "fresh_session": True,
        "isolation": "enforced",
        "network": "internet" if BAD_NETWORK else "none",
        "credentials": "none",
        "verifier_image": "worker@sha256:" + "a" * 64 if args.role == "prove" else None,
    }))
elif args.role == "prove" and args.phase == "worker":
    output = Path("output")
    output.mkdir(exist_ok=True)
    (output / "result.txt").write_text("verified connector artifact\\n", encoding="utf-8")
    print("worker complete")
elif args.role == "build":
    print(json.dumps({"schema":"templeton.result.v1","status":"ready","summary":"done","questions":[]}))
else:
    print("connector result")
""".replace("BAD_NETWORK", "True" if bad_network else "False"),
        encoding="utf-8",
    )
    script.chmod(0o700)
    config = tmp_path / "connector.json"
    config.write_text(
        json.dumps(
            {
                "schema": "templeton.connector.v1",
                "id": "test-harness",
                "command": [sys.executable, str(script)],
                "roles": ["spec", "build", "review", "qa", "prove"],
            }
        ),
        encoding="utf-8",
    )
    return config


def test_connector_config_and_preflight_form_a_small_fail_closed_interface(tmp_path: Path):
    config = load_connector_config(make_connector(tmp_path))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    evidence = verify_connector_runtime(config, role="build", workspace=workspace)
    assert evidence["id"] == "test-harness"
    assert evidence["workspace_access"] == "rw"
    assert evidence["network"] == "none"
    assert evidence["connector_config_sha256"] == config.sha256


def test_connector_preflight_rejects_unsafe_claims(tmp_path: Path):
    config = load_connector_config(make_connector(tmp_path, bad_network=True))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(ConnectorError, match="network must be 'none'"):
        verify_connector_runtime(config, role="build", workspace=workspace)


def test_connector_config_rejects_relative_executables(tmp_path: Path):
    path = tmp_path / "connector.json"
    path.write_text(
        json.dumps(
            {
                "schema": "templeton.connector.v1",
                "id": "bad",
                "command": ["python3"],
                "roles": ["build"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConnectorError, match="absolute path"):
        load_connector_config(path)


def test_connector_builds_outer_and_proof_invocations(tmp_path: Path):
    config_path = make_connector(tmp_path)
    config = load_connector_config(config_path)
    outer = connector_command(
        config,
        role="build",
        prompt="bounded prompt",
        max_turns=20,
        timeout=300,
    )
    assert outer[:2] == [str(Path(sys.executable).resolve()), str(tmp_path / "connector.py")]
    assert outer[outer.index("--role") + 1] == "build"
    assert outer[outer.index("--message") + 1] == "bounded prompt"

    proof = build_connector_command(
        ModelRoute("glm-5", provider="zai", profile="economy"),
        "make artifact",
        config=config,
        phase="worker",
    )
    assert proof[proof.index("--model") + 1] == "glm-5"
    assert proof[proof.index("--provider") + 1] == "zai"
    assert proof[proof.index("--phase") + 1] == "worker"


def test_source_cli_defaults_to_connector_without_changing_fixed_editions(tmp_path: Path):
    if EDITION is None:
        source = parser().parse_args(
            ["run", "build", "--connector-config", str(make_connector(tmp_path)), "--dry-run"]
        )
        assert source.runtime == "connector"
        assert source.connector_config.endswith("connector.json")
    assert parser("hermes").parse_args(["run", "build"]).runtime == "hermes"
    assert parser("openclaw").parse_args(
        ["run", "build", "--agent", "builder"]
    ).runtime == "openclaw"


def test_outer_agent_command_routes_through_connector(tmp_path: Path):
    config_path = make_connector(tmp_path)
    command = agent_command(
        repo=Repo(tmp_path, "owner/repo", "https://example.test/repo", "main"),
        role="build",
        candidate=Candidate(
            number=7,
            title="Change",
            url="https://example.test/7",
            head_sha=None,
            kind="issue",
        ),
        runtime="connector",
        profile="",
        agent="",
        max_turns=10,
        timeout=60,
        connector_config=str(config_path),
    )
    assert command[command.index("--role") + 1] == "build"
    assert "production-loop build pass" in command[command.index("--message") + 1]


def test_proof_dry_run_routes_models_through_connector(tmp_path: Path):
    config_path = make_connector(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("source\n", encoding="utf-8")
    manifest = tmp_path / "proof.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "name": "connector-smoke",
                "source_root": str(source),
                "source_paths": ["README.md"],
                "strategy": {"model": "gemini-pro", "provider": "google", "prompt": "plan"},
                "worker": {"model": "kimi-worker", "provider": "moonshot"},
                "tasks": [
                    {
                        "id": "artifact",
                        "brief": "create it",
                        "expected_files": ["result.txt"],
                        "verifiers": [{"argv": ["test", "-s", "result.txt"]}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = dry_run(manifest, runtime="connector", connector_config=config_path)
    assert result["runtime_adapter"] == "connector"
    assert result["strategy"]["command"][result["strategy"]["command"].index("--model") + 1] == "gemini-pro"
    worker = result["tasks"][0]["command"]
    assert worker[worker.index("--model") + 1] == "kimi-worker"


def test_live_connector_proof_preflights_each_exact_invocation_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_path = make_connector(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("source\n", encoding="utf-8")
    manifest = tmp_path / "proof-live.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "name": "connector-live",
                "source_root": str(source),
                "source_paths": ["README.md"],
                "strategy": {"model": "gemini-pro", "provider": "google", "prompt": "plan"},
                "worker": {"model": "kimi-worker", "provider": "moonshot"},
                "env_allowlist": ["PATH", "TEST_CONNECTOR_LOG"],
                "tasks": [
                    {
                        "id": "artifact",
                        "brief": "create it",
                        "expected_files": ["result.txt"],
                        "verifiers": [{"argv": ["test", "-s", "result.txt"]}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        proof_module,
        "_verifier_command",
        lambda _workspace, argv, _image: list(argv),
    )
    log = tmp_path / "connector.jsonl"
    run_root = tmp_path / "runs"
    state = run_proof(
        manifest,
        run_root=run_root,
        runtime="connector",
        connector_config=config_path,
        environ={
            "PATH": os.environ["PATH"],
            "TEST_CONNECTOR_LOG": str(log),
        },
    )

    assert state["status"] == "passed", state
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    preflight_workspaces = [row["workspace"] for row in records if row["action"] == "preflight"]
    invocation_workspaces = [row["workspace"] for row in records if row["action"] == "invoke"]
    assert len(preflight_workspaces) == 3
    assert set(invocation_workspaces).issubset(set(preflight_workspaces))
    assert state["tasks"][0]["attempts"][0]["runtime_policy"]["workspace"] in invocation_workspaces
