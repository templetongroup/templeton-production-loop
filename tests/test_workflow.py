from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from templeton_loop.evidence import Finding
from templeton_loop.workflow import (
    LoopConfig,
    Verifier,
    WorkflowError,
    _linked_issue_number,
    _stage_and_validate_patch,
    _linked_contract_markers,
    _select_workspace,
    broker_build,
    broker_qa,
    broker_review,
    extract_json_object,
    format_review_comment,
    validate_builder_response,
    validate_changed_paths,
    verifier_container_command,
)


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_patch_budget_counts_untracked_files_after_staging(tmp_path: Path):
    git(tmp_path, "init")
    (tmp_path / "new.bin").write_bytes(b"x" * 1_000)
    config = LoopConfig((), (), 100, 10, None, None)

    with pytest.raises(WorkflowError, match="max_patch_bytes"):
        _stage_and_validate_patch(tmp_path, config)


def test_repair_contract_requires_one_linked_issue():
    assert _linked_issue_number("Supersedes #9.\n\nFixes #42") == 42
    with pytest.raises(WorkflowError, match="exactly one issue"):
        _linked_issue_number("Supersedes #9")
    with pytest.raises(WorkflowError, match="exactly one issue"):
        _linked_issue_number("Fixes #42 and resolves #43")


def write_config(root: Path) -> Path:
    path = root / ".templeton" / "loop.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "verifiers": [{"argv": ["python3", "-m", "pytest", "-q"], "timeout_seconds": 60}],
                "verifier_sandbox": {
                    "engine": "docker",
                    "image": "worker@sha256:" + "a" * 64,
                },
                "protected_paths": [".git", ".github/workflows", ".templeton/loop.json"],
                "max_patch_bytes": 10000,
                "max_changed_files": 2,
            }
        )
    )
    return path


def test_loop_config_requires_nonempty_structured_verifiers(tmp_path: Path):
    write_config(tmp_path)
    config = LoopConfig.load(tmp_path)
    assert config.verifiers[0].argv == ("python3", "-m", "pytest", "-q")
    data = json.loads((tmp_path / ".templeton/loop.json").read_text())
    data["verifiers"] = []
    (tmp_path / ".templeton/loop.json").write_text(json.dumps(data))
    with pytest.raises(WorkflowError, match="at least one verifier"):
        LoopConfig.load(tmp_path)


def test_outer_loop_verifier_command_is_air_gapped_and_hardened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("templeton_loop.workflow.shutil.which", lambda _name: "/usr/bin/docker")
    verifier = Verifier(("python", "-m", "pytest", "-q"), 60)
    config = LoopConfig(
        (verifier,),
        (".git",),
        100_000,
        10,
        "docker",
        "worker@sha256:" + "a" * 64,
    )
    command = verifier_container_command(tmp_path, verifier, config)

    assert command[:2] == ["docker", "run"]
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command[command.index("--security-opt") + 1] == "no-new-privileges"
    assert "--user" in command


def test_third_repair_attempt_is_stopped_before_agent_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    write_config(tmp_path)
    contract = {
        "headRefOid": "a" * 40,
        "comments": [
            {"body": "<!-- templeton-loop-repair-attempt-v1 -->"},
            {"body": "<!-- templeton-loop-repair-attempt-v1 -->"},
        ],
    }
    monkeypatch.setattr("templeton_loop.workflow._json_command", lambda *_args, **_kwargs: contract)
    commands: list[list[str]] = []

    def capture(args, **_kwargs):
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("templeton_loop.workflow._run", capture)
    result = broker_build(
        repo=SimpleNamespace(root=tmp_path, slug="owner/repo", default_branch="main"),
        candidate=SimpleNamespace(number=7, kind="pr-repair", title="repair", url="u"),
        agent_command=["never-run"],
        timeout=60,
        preflight=lambda _workspace: pytest.fail("preflight must not run"),
    )

    assert result["status"] == "stuck"
    assert result["repair_attempts"] == 2
    assert any("loop:stuck" in command and "loop:needs-human-review" in command for command in commands)


def test_agent_json_and_builder_contract_are_strict():
    value = extract_json_object('prefix\n```json\n{"schema":"templeton.result.v1","status":"ready","summary":"Fix it","questions":[]}\n```')
    assert validate_builder_response(value, 1000)["status"] == "ready"
    with pytest.raises(WorkflowError, match="schema"):
        validate_builder_response({"status": "ready", "summary": "x"}, 100)
    with pytest.raises(WorkflowError, match="Unexpected"):
        validate_builder_response(
            {"schema": "templeton.result.v1", "status": "ready", "summary": "x", "patch": "nope"},
            100,
        )


def test_changed_paths_reject_protected_paths_symlinks_and_budgets(tmp_path: Path):
    git(tmp_path, "init", "-q")
    write_config(tmp_path)
    config = LoopConfig.load(tmp_path)
    (tmp_path / "src.py").write_text("ok\n")
    validate_changed_paths(tmp_path, ["src.py"], config)
    with pytest.raises(WorkflowError, match="protected"):
        validate_changed_paths(tmp_path, [".github/workflows/release.yml"], config)
    (tmp_path / "link").symlink_to("src.py")
    with pytest.raises(WorkflowError, match="symbolic link"):
        validate_changed_paths(tmp_path, ["link"], config)
    with pytest.raises(WorkflowError, match="count"):
        validate_changed_paths(tmp_path, ["a", "b", "c"], config)


def test_review_comment_is_sha_pinned_and_never_claims_safe_with_findings():
    finding = Finding(
        finding_id="F-1",
        severity="high",
        confidence="high",
        summary="Broken boundary",
        failure_scenario="A child can push.",
        evidence="policy.py:1",
        fingerprint="child-push",
        disposition="must-fix",
        acceptance_criterion="AC-1",
    ).validate()
    comment = format_review_comment("abc123", "One issue.", [finding], "required checks passed", "clean")
    assert comment.startswith("Templeton Loop review of abc123")
    assert "Broken boundary" in comment
    assert "## Safe to merge\n\nNo." in comment


def test_linked_issue_contract_is_required_and_loaded(monkeypatch: pytest.MonkeyPatch):
    repo = SimpleNamespace(root=Path("/tmp"), slug="owner/repo")
    monkeypatch.setattr(
        "templeton_loop.workflow._json_command",
        lambda *_args, **_kwargs: {"body": "## Acceptance\n- AC-1: complete\n- NG-1: deploy"},
    )
    assert _linked_contract_markers(repo, "Closes #12") == {"AC-1", "NG-1"}
    with pytest.raises(WorkflowError, match="exactly one issue"):
        _linked_contract_markers(repo, "No linked contract")


def _qa_finding(marker: str) -> dict[str, str]:
    mapping = (
        {"acceptance_criterion": marker}
        if marker.startswith("AC-")
        else {"non_goal": marker}
    )
    return {
        "finding_id": f"F-QA-{marker}",
        "severity": "medium",
        "confidence": "high",
        "summary": "Observed behavior",
        "failure_scenario": "The tested behavior differs from the contract.",
        "evidence": "scenario:1",
        "fingerprint": f"qa-{marker.lower()}",
        "disposition": "should-fix",
        **mapping,
    }


def test_qa_findings_must_reference_linked_issue_contract_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    head = "a" * 40
    responses = iter(
        [
            {"body": "Closes #12", "headRefOid": head},
            {"body": "AC-1: required\nNG-1: excluded"},
        ]
    )
    monkeypatch.setattr(
        "templeton_loop.workflow._json_command", lambda *_args, **_kwargs: next(responses)
    )
    monkeypatch.setattr(
        "templeton_loop.workflow._run_staged_readonly_agent",
        lambda **_kwargs: (
            subprocess.CompletedProcess(
                ["agent"],
                0,
                json.dumps({"summary": "checked", "findings": [_qa_finding("AC-2")]}),
                "",
            ),
            tmp_path / "events.jsonl",
        ),
    )

    with pytest.raises(WorkflowError, match="unknown contract marker AC-2"):
        broker_qa(
            repo=SimpleNamespace(root=tmp_path, slug="owner/repo"),
            candidate=SimpleNamespace(
                number=7, title="PR", url="u", head_sha=head, kind="pr-qa"
            ),
            agent_command=["agent"],
            timeout=60,
            preflight=lambda _workspace: {"ok": True},
        )


def test_qa_accepts_ac_and_ng_markers_from_exact_linked_issue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    head = "a" * 40
    responses = iter(
        [
            {"body": "Closes #12", "headRefOid": head},
            {"body": "AC-1: required\nNG-1: excluded"},
            {"headRefOid": head},
        ]
    )
    monkeypatch.setattr(
        "templeton_loop.workflow._json_command", lambda *_args, **_kwargs: next(responses)
    )
    monkeypatch.setattr(
        "templeton_loop.workflow._run_staged_readonly_agent",
        lambda **_kwargs: (
            subprocess.CompletedProcess(
                ["agent"],
                0,
                json.dumps(
                    {
                        "summary": "checked",
                        "findings": [_qa_finding("AC-1"), _qa_finding("NG-1")],
                    }
                ),
                "",
            ),
            tmp_path / "events.jsonl",
        ),
    )

    result = broker_qa(
        repo=SimpleNamespace(root=tmp_path, slug="owner/repo"),
        candidate=SimpleNamespace(number=7, title="PR", url="u", head_sha=head, kind="pr-qa"),
        agent_command=["agent"],
        timeout=60,
        preflight=lambda _workspace: {"ok": True},
    )

    assert result["status"] == "passed"
    assert {
        finding.get("acceptance_criterion") or finding.get("non_goal")
        for finding in result["findings"]
    } == {"AC-1", "NG-1"}


def test_openclaw_workspace_deletion_scope_rejects_escape_and_symlink(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    run = repo / ".git" / "templeton-loop" / "runs" / "one"
    run.mkdir(parents=True)
    with pytest.raises(WorkflowError, match="direct child"):
        _select_workspace(repo, run, tmp_path / "outside")

    base = repo / ".git" / "templeton-loop" / "openclaw-workspaces"
    outside = tmp_path / "linked-root"
    outside.mkdir()
    base.parent.mkdir(parents=True, exist_ok=True)
    if base.exists():
        base.rmdir()
    base.symlink_to(outside, target_is_directory=True)
    with pytest.raises(WorkflowError, match="symbolic-link indirection"):
        _select_workspace(repo, run, base / "agent")


def test_review_stale_head_before_label_never_applies_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    head = "a" * 40
    newer = "b" * 40
    pr_reads = 0

    def json_command(args: list[str], **_kwargs: object) -> dict[str, object]:
        nonlocal pr_reads
        if args[1:3] == ["issue", "view"]:
            return {"number": 1, "body": "AC-1: reviewed", "title": "Contract", "url": "u"}
        pr_reads += 1
        if pr_reads == 1:
            return {
                "number": 7,
                "title": "PR",
                "body": "Closes #1",
                "url": "u",
                "headRefOid": head,
                "mergeable": "MERGEABLE",
                "mergeStateStatus": "CLEAN",
            }
        return {
            "headRefOid": newer if pr_reads == 4 else head,
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
        }

    commands: list[list[str]] = []

    def run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        stdout = '[{"bucket":"pass","name":"tests","state":"SUCCESS","link":"u"}]' if "checks" in args else ""
        return subprocess.CompletedProcess(args, 0, stdout, "")

    monkeypatch.setattr("templeton_loop.workflow._json_command", json_command)
    monkeypatch.setattr("templeton_loop.workflow._run", run)
    monkeypatch.setattr(
        "templeton_loop.workflow._run_staged_readonly_agent",
        lambda **_kwargs: (
            subprocess.CompletedProcess(["agent"], 0, '{"summary":"clean","findings":[]}', ""),
            tmp_path / "events.jsonl",
        ),
    )
    result = broker_review(
        repo=SimpleNamespace(root=tmp_path, slug="owner/repo"),
        candidate=SimpleNamespace(number=7, title="PR", url="u", head_sha=head, kind="pr-review"),
        agent_command=["agent"],
        timeout=60,
        preflight=lambda _workspace: {"ok": True},
    )
    assert result["status"] == "stale"
    assert result["current_sha"] == newer
    assert not any(command[:3] == ["gh", "pr", "edit"] for command in commands)
