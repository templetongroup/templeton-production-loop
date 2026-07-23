from pathlib import Path
from unittest.mock import patch

import pytest

from templeton_loop.cli import (
    Candidate,
    Repo,
    agent_command,
    choose_build_issue,
    choose_repair_pr,
    health_report,
    latest_review_sha,
    main,
    parser,
    pr_needs_review,
)


def issue(number, *, labels, assignees=None, created="2026-01-01T00:00:00Z"):
    return {
        "number": number,
        "title": f"Issue {number}",
        "url": f"https://example.test/issues/{number}",
        "createdAt": created,
        "labels": [{"name": name} for name in labels],
        "assignees": assignees or [],
    }


def pr(*, sha="abc123", labels=None, draft=False):
    return {
        "number": 7,
        "title": "PR",
        "url": "https://example.test/pull/7",
        "headRefOid": sha,
        "isDraft": draft,
        "labels": [{"name": name} for name in (labels or [])],
    }


def test_build_queue_filters_blocked_building_and_assigned():
    chosen = choose_build_issue(
        [
            issue(1, labels=["loop:agent-ready", "loop:blocked"]),
            issue(2, labels=["loop:agent-ready"], assignees=[{"login": "someone"}]),
            issue(3, labels=["loop:agent-ready", "loop:building"]),
            issue(4, labels=["loop:spec-draft"]),
            issue(5, labels=["loop:agent-ready"]),
        ]
    )
    assert chosen and chosen.number == 5


def test_build_queue_sorts_priority_then_oldest():
    chosen = choose_build_issue(
        [
            issue(1, labels=["loop:agent-ready", "priority:p2"], created="2025-01-01T00:00:00Z"),
            issue(2, labels=["loop:agent-ready", "priority:p0"], created="2026-02-01T00:00:00Z"),
            issue(3, labels=["loop:agent-ready", "priority:p0"], created="2026-01-01T00:00:00Z"),
        ]
    )
    assert chosen and chosen.number == 3


def test_repair_queue_precludes_human_and_stuck_prs():
    chosen = choose_repair_pr(
        [
            {**pr(labels=["loop:changes-requested", "loop:needs-human-review"]), "number": 1, "updatedAt": "2026-01-01"},
            {**pr(labels=["loop:changes-requested", "loop:stuck"]), "number": 2, "updatedAt": "2026-01-01"},
            {**pr(labels=["loop:changes-requested"]), "number": 3, "updatedAt": "2026-01-02"},
        ]
    )
    assert chosen and chosen.number == 3 and chosen.kind == "pr-repair"


def test_review_sha_is_latest_sha_pinned_comment():
    comments = [
        {"body": "Templeton Loop review of oldsha\n\nEarlier", "created_at": "2026-01-01"},
        {"body": "unrelated", "created_at": "2026-01-03"},
        {"body": "Templeton Loop review of newsha\n\nLater", "created_at": "2026-01-02"},
    ]
    assert latest_review_sha(comments) == "newsha"


def test_pr_skips_only_when_current_sha_has_terminal_label():
    comments = [{"body": "Templeton Loop review of abc123", "created_at": "2026-01-01"}]
    assert not pr_needs_review(pr(labels=["loop:approved"]), comments)
    assert pr_needs_review(pr(labels=[]), comments)
    assert pr_needs_review(pr(sha="changed", labels=["loop:approved"]), comments)
    assert not pr_needs_review(pr(draft=True), [])


def test_agent_command_is_air_gapped_terminal_only_and_contains_hard_gates():
    repo = Repo(Path("/tmp/repo"), "org/repo", "https://github.com/org/repo", "trunk")
    command = agent_command(
        repo=repo,
        role="build",
        candidate=Candidate(42, "Thing", "https://github.com/org/repo/issues/42"),
        runtime="hermes",
        profile="nikki",
        agent="",
        max_turns=80,
        timeout=3600,
    )
    joined = " ".join(command)
    assert "--worktree" not in command
    assert "--safe-mode" not in command
    assert "--ignore-rules" in command
    assert "--toolsets" in command and "terminal,todo" in command
    assert "deterministic Templeton broker" in joined
    assert "Edit files directly inside the isolated current working directory" in joined
    assert "GitHub issue #42" in joined
    assert "Never merge" in joined
    assert "--profile nikki" in joined


def test_review_command_pins_candidate_head_sha():
    repo = Repo(Path("/tmp/repo"), "org/repo", "https://github.com/org/repo", "main")
    command = agent_command(
        repo=repo,
        role="review",
        candidate=Candidate(8, "Review", "https://github.com/org/repo/pull/8", head_sha="feedface"),
        runtime="hermes",
        profile="nikki",
        agent="",
        max_turns=90,
        timeout=3600,
    )
    assert "head feedface" in " ".join(command)


def test_openclaw_agent_command_is_fresh_and_names_agent_repo_and_broker():
    repo = Repo(Path("/tmp/repo"), "org/repo", "https://github.com/org/repo", "main")
    command = agent_command(
        repo=repo,
        role="build",
        candidate=Candidate(42, "Thing", "https://github.com/org/repo/issues/42"),
        runtime="openclaw",
        profile="",
        agent="builder",
        max_turns=90,
        timeout=1800,
    )
    joined = " ".join(command)
    assert command[:2] == ["openclaw", "agent"]
    assert "--agent builder" in joined
    assert "agent:builder:templeton-loop-build-42-" in joined
    assert "deterministic Templeton broker" in joined
    assert "/tmp/repo" not in joined
    assert "disposable, secret-filtered source snapshot" in joined
    assert "Never merge" in joined
    assert "--timeout 1800" in joined


def test_prove_parser_supports_lint_dry_run_and_run_root():
    lint = parser("source").parse_args(["prove", "plan.json", "--lint"])
    dry = parser("source").parse_args(["prove", "plan.json", "--dry-run"])
    run = parser("source").parse_args(["prove", "plan.json", "--run-root", "/tmp/proofs"])

    assert lint.command == "prove" and lint.manifest == "plan.json" and lint.lint
    assert dry.dry_run and not dry.lint
    assert run.run_root == "/tmp/proofs"
    assert not run.dry_run and not run.lint


def test_fixed_editions_hide_runtime_switch_and_unsupported_commands():
    hermes = parser("hermes")
    openclaw = parser("openclaw")

    assert "--runtime" not in hermes.format_help()
    assert "--runtime" not in openclaw.format_help()
    assert "prove" in hermes.format_help()
    assert "prove" in openclaw.format_help()

    hermes_run = hermes.parse_args(["run", "build"])
    openclaw_run = openclaw.parse_args(["run", "review", "--agent", "reviewer"])
    openclaw_prove = openclaw.parse_args(
        ["prove", "plan.json", "--agent", "prover", "--run-root", "/tmp/proofs"]
    )
    assert hermes_run.runtime == "hermes"
    assert openclaw_run.runtime == "openclaw"
    assert openclaw_prove.proof_runtime == "openclaw"
    assert openclaw_prove.runtime_executable == "openclaw"

    with pytest.raises(SystemExit):
        hermes.parse_args(["run", "build", "--agent", "builder"])
    with pytest.raises(SystemExit):
        openclaw.parse_args(["run", "review", "--agent", "reviewer", "--profile", "x"])
    with pytest.raises(SystemExit):
        hermes.parse_args(["policy-template", "--agent", "x", "--role", "build", "--workspace", "."])
    prove_policy = openclaw.parse_args(
        ["policy-template", "--agent", "x", "--role", "prove", "--workspace", "."]
    )
    assert prove_policy.role == "prove"


def test_health_discovers_only_bounded_run_ledgers(tmp_path: Path):
    from templeton_loop import proof as proof_module
    from templeton_loop.evidence import RunLedger

    config = tmp_path / ".templeton" / "loop.json"
    config.parent.mkdir()
    config.write_text('{"version":1}\n', encoding="utf-8")
    runs = tmp_path / ".git" / "templeton-loop" / "runs"
    workflow_path = runs / "outer" / "events.jsonl"
    RunLedger(workflow_path).append({"type": "run_completed", "status": "passed"})
    proof_path = runs / "proof" / "events.jsonl"
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    (proof_path.parent / "report.md").write_text("proof\n", encoding="utf-8")
    proof_events = proof_module._EventWriter(proof_path)
    proof_events.append(
        "evidence_sealed",
        files=proof_module._sealed_evidence_inventory(proof_path.parent),
    )
    proof_events.append("run_completed", status="passed")
    incomplete_path = runs / "incomplete" / "events.jsonl"
    RunLedger(incomplete_path).append({"type": "run_started", "status": "running"})
    ignored = runs / "nested" / "deeper" / "events.jsonl"
    RunLedger(ignored).append({"type": "run_completed", "status": "passed"})

    report = health_report(Repo(tmp_path, "org/repo", "https://example.test", "main"))

    assert report["ok"] is True
    assert {item["type"] for item in report["ledgers"]} == {"workflow", "proof"}
    assert {Path(item["path"]) for item in report["ledgers"]} == {
        workflow_path,
        proof_path,
        incomplete_path,
    }
    assert report["recovery"]["incomplete_runs"] == [str(incomplete_path)]
    completion = {Path(item["path"]): item["completed"] for item in report["ledgers"]}
    assert completion[workflow_path] is True
    assert completion[proof_path] is True
    assert completion[incomplete_path] is False


@patch("templeton_loop.cli.resolve_repo")
@patch("templeton_loop.cli.lint_manifest", return_value={"status": "valid", "task_count": 2})
def test_prove_lint_bypasses_github_repo_resolution(lint, resolve_repo, capsys):
    assert main(["--json", "prove", "plan.json", "--lint"], edition="source") == 0

    lint.assert_called_once_with("plan.json")
    resolve_repo.assert_not_called()
    assert '"status": "valid"' in capsys.readouterr().out


def test_shipped_openclaw_proof_example_supports_documented_dry_run(capsys):
    manifest = Path(__file__).resolve().parent.parent / "examples" / "proof-manifest.json"

    assert main(
        ["prove", str(manifest), "--agent", "templeton-prove", "--dry-run"],
        edition="openclaw",
    ) == 0

    result = capsys.readouterr().out
    assert "runtime_adapter: openclaw" in result
    assert "templeton-prove" in result
