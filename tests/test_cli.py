from pathlib import Path
from unittest.mock import patch

from templeton_loop.cli import (
    Candidate,
    Repo,
    agent_command,
    choose_build_issue,
    choose_repair_pr,
    latest_review_sha,
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


def test_agent_command_is_fresh_worktree_and_contains_hard_gates():
    repo = Repo(Path("/tmp/repo"), "org/repo", "https://github.com/org/repo", "trunk")
    command = agent_command(
        repo=repo,
        role="build",
        candidate=Candidate(42, "Thing", "https://github.com/org/repo/issues/42"),
        profile="nikki",
        max_turns=80,
    )
    joined = " ".join(command)
    assert "--worktree" in command
    assert "templeton-loop-build" in command
    assert "GitHub issue #42" in joined
    assert "Never merge" in joined
    assert "--profile nikki" in joined


def test_review_command_pins_candidate_head_sha():
    repo = Repo(Path("/tmp/repo"), "org/repo", "https://github.com/org/repo", "main")
    command = agent_command(
        repo=repo,
        role="review",
        candidate=Candidate(8, "Review", "https://github.com/org/repo/pull/8", head_sha="feedface"),
        profile="nikki",
        max_turns=90,
    )
    assert "head feedface" in " ".join(command)
