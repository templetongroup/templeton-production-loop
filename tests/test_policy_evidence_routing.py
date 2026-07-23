from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from templeton_loop.evidence import (
    EvidenceError,
    Finding,
    RunLedger,
    atomic_write_json,
    evidence_freshness,
    redact,
    validate_findings,
)
from templeton_loop.policy import (
    PolicyError,
    find_and_verify_openclaw_agent,
    hermes_policy_args,
    openclaw_agent_template,
    verify_openclaw_agent,
)
from templeton_loop.routing import Outcome, append_outcome, coverage_matrix, read_outcomes, recommend_route


def test_hermes_policy_preserves_verified_profile_config_and_limits_tools():
    assert hermes_policy_args("build") == [
        "--ignore-rules", "--toolsets", "terminal,todo"
    ]
    assert hermes_policy_args("review") == [
        "--safe-mode", "--ignore-rules", "--toolsets", "todo"
    ]
    assert "terminal" not in hermes_policy_args("qa")


def test_denial_canary_openclaw_template_and_verifier_fail_closed():
    image = "worker@sha256:" + "a" * 64
    build = openclaw_agent_template("templeton-builder", "build", "/workspace", image)
    result = verify_openclaw_agent(build, "build")
    assert result["ok"] is True
    assert result["network"] == "none"
    assert result["allowed_tools"] == ["apply_patch", "edit", "exec", "process", "read", "write"]
    assert build["sandbox"]["workspaceAccess"] == "rw"

    review = openclaw_agent_template("templeton-review", "review", "/workspace", image)
    assert review["sandbox"]["workspaceAccess"] == "ro"
    assert verify_openclaw_agent(review, "review")["allowed_tools"] == ["exec", "process", "read"]

    unsafe = json.loads(json.dumps(build))
    unsafe["tools"]["allow"].append("browser")
    with pytest.raises(PolicyError, match="tools.allow"):
        verify_openclaw_agent(unsafe, "build")
    unsafe = json.loads(json.dumps(build))
    unsafe["sandbox"]["mode"] = "off"
    with pytest.raises(PolicyError, match="mode=all"):
        verify_openclaw_agent(unsafe, "build")
    assert find_and_verify_openclaw_agent([build], "templeton-builder", "build")["ok"]


def test_redaction_applies_to_keys_values_and_atomic_sinks(tmp_path: Path):
    raw = {
        "api_key": "plain-secret",
        "nested": {"message": "Authorization: Bearer abcdefghijklmnop"},
        "tokenCount": 10,
        "github": "ghp_" + "abcdefghijklmnopqrstuvwxyz123456",
    }
    clean = redact(raw)
    assert clean["api_key"] == "[REDACTED]"
    assert "Bearer abc" not in clean["nested"]["message"]
    assert clean["tokenCount"] == 10
    assert clean["github"] == "[REDACTED]"
    path = tmp_path / "state.json"
    atomic_write_json(path, raw)
    text = path.read_text()
    assert "plain-secret" not in text
    assert "ghp_" not in text


def test_finding_schema_and_deduplication():
    value = {
        "finding_id": "F-AC1-001",
        "severity": "high",
        "confidence": "high",
        "summary": "Verifier can erase its artifact",
        "failure_scenario": "A verifier exits zero after emptying the file.",
        "evidence": "tests/test_proof.py:420",
        "fingerprint": "artifact-postcheck-empty",
        "disposition": "must-fix",
        "acceptance_criterion": "AC-1",
        "location": "templeton_loop/proof.py:900",
    }
    assert Finding.from_dict(value).acceptance_criterion == "AC-1"
    with pytest.raises(EvidenceError, match="Duplicate finding fingerprint"):
        validate_findings([value, {**value, "finding_id": "F-AC1-002"}])


def test_freshness_distinguishes_current_stale_and_unverifiable():
    now = datetime(2026, 7, 23, tzinfo=timezone.utc)
    current = evidence_freshness("abc", "abc", now.isoformat(), now=now)
    assert current.status == "current"
    assert evidence_freshness("abc", "def", now.isoformat(), now=now).status == "stale"
    old = (now - timedelta(days=2)).isoformat()
    assert evidence_freshness("abc", "abc", old, now=now).status == "stale"
    assert evidence_freshness("", "abc", old, now=now).status == "unverifiable"


def test_hash_chained_run_ledger_detects_tampering_and_redacts(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    ledger = RunLedger(path)
    first = ledger.append({"type": "run_started", "apiKey": "secret"})
    second = ledger.append({"type": "run_completed", "status": "passed"})
    assert first["previous_hash"] == "0" * 64
    assert second["previous_hash"] == first["entry_hash"]
    assert ledger.verify()["entries"] == 2
    assert "secret" not in path.read_text()
    lines = path.read_text().splitlines()
    lines[0] = lines[0].replace("run_started", "run_changed")
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(EvidenceError, match="hash mismatch"):
        ledger.verify()


def test_provider_neutral_routing_requires_measured_evidence(tmp_path: Path):
    path = tmp_path / "outcomes.jsonl"
    for duration in (100, 110, 120):
        append_outcome(path, Outcome("review", "provider-a", "model-a", True, duration, 1, cost_usd=0.2))
    append_outcome(path, Outcome("review", "provider-b", "model-b", True, 50, 1, cost_usd=0.1))
    outcomes = read_outcomes(path)
    recommendation = recommend_route(outcomes, "review")
    assert recommendation["status"] == "recommended"
    assert recommendation["route"] == {"provider": "provider-a", "model": "model-a"}
    assert recommend_route(outcomes, "build")["status"] == "insufficient-evidence"


def test_capability_coverage_matrix_is_fail_closed():
    matrix = coverage_matrix({"spec": ["repository-read", "report-output"]})
    assert matrix["ok"] is False
    assert any(row["task_class"] == "build" and row["missing"] for row in matrix["rows"])
