from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class EvidenceError(ValueError):
    pass


_SECRET_KEYS = {
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "credentials",
    "passwd",
    "password",
    "secret",
    "token",
    "accesstoken",
    "refreshtoken",
}
_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
)


def redact_text(value: str) -> str:
    redacted = value
    for pattern in _SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _is_secret_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return normalized in _SECRET_KEYS


def redact(value: Any, key: str = "") -> Any:
    if _is_secret_key(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def canonical_json(value: Any) -> bytes:
    return json.dumps(redact(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(redact(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


_ALLOWED_SEVERITY = {"critical", "high", "medium", "low", "info"}
_ALLOWED_CONFIDENCE = {"high", "medium", "low"}
_ALLOWED_DISPOSITION = {
    "must-fix",
    "should-fix",
    "accepted-risk",
    "false-positive",
    "deferred",
    "needs-human",
}


@dataclass(frozen=True)
class Finding:
    finding_id: str
    severity: str
    confidence: str
    summary: str
    failure_scenario: str
    evidence: str
    fingerprint: str
    disposition: str
    acceptance_criterion: str | None = None
    non_goal: str | None = None
    location: str | None = None

    def validate(self) -> "Finding":
        if not re.fullmatch(r"F-[A-Za-z0-9._-]+", self.finding_id):
            raise EvidenceError(f"Invalid finding_id: {self.finding_id!r}")
        if self.severity not in _ALLOWED_SEVERITY:
            raise EvidenceError(f"Invalid severity: {self.severity!r}")
        if self.confidence not in _ALLOWED_CONFIDENCE:
            raise EvidenceError(f"Invalid confidence: {self.confidence!r}")
        if self.disposition not in _ALLOWED_DISPOSITION:
            raise EvidenceError(f"Invalid disposition: {self.disposition!r}")
        for name in ("summary", "failure_scenario", "evidence", "fingerprint"):
            if not getattr(self, name).strip():
                raise EvidenceError(f"Finding {name} must not be empty")
        if self.acceptance_criterion and not re.fullmatch(r"AC-\d+", self.acceptance_criterion):
            raise EvidenceError("acceptance_criterion must match AC-N")
        if self.non_goal and not re.fullmatch(r"NG-\d+", self.non_goal):
            raise EvidenceError("non_goal must match NG-N")
        if bool(self.acceptance_criterion) == bool(self.non_goal):
            raise EvidenceError("Each finding must map to exactly one AC-N or NG-N contract marker")
        return self

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Finding":
        try:
            finding = cls(**value)
        except TypeError as exc:
            raise EvidenceError(f"Invalid finding fields: {exc}") from exc
        return finding.validate()

    def to_dict(self) -> dict[str, Any]:
        return redact(asdict(self))


def validate_findings(values: Iterable[dict[str, Any]]) -> list[Finding]:
    findings = [Finding.from_dict(value) for value in values]
    ids = [finding.finding_id for finding in findings]
    if len(ids) != len(set(ids)):
        raise EvidenceError("Duplicate finding_id")
    fingerprints = [finding.fingerprint for finding in findings]
    if len(fingerprints) != len(set(fingerprints)):
        raise EvidenceError("Duplicate finding fingerprint")
    return findings


_ALLOWED_PR_FILE_STATUS = {
    "added",
    "changed",
    "copied",
    "modified",
    "removed",
    "renamed",
    "unchanged",
}
_ALLOWED_REVIEW_OUTCOME = {"reviewed", "skipped"}


def _validate_review_path(path: Any) -> str:
    if (
        not isinstance(path, str)
        or not path
        or path.startswith("/")
        or "\\" in path
        or any(ord(character) < 32 or ord(character) == 127 for character in path)
    ):
        raise EvidenceError(f"Invalid review coverage path: {path!r}")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise EvidenceError(f"Invalid review coverage path: {path!r}")
    return path


@dataclass(frozen=True)
class ReviewCoverageItem:
    path: str
    status: str
    outcome: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return redact(asdict(self))


@dataclass(frozen=True)
class ReviewCoverage:
    selected: tuple[ReviewCoverageItem, ...]
    reviewed: tuple[ReviewCoverageItem, ...]
    skipped: tuple[ReviewCoverageItem, ...]
    terminal_state: str

    @property
    def selected_count(self) -> int:
        return len(self.selected)

    @property
    def reviewed_count(self) -> int:
        return len(self.reviewed)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    def to_dict(self) -> dict[str, Any]:
        return {
            "terminal_state": self.terminal_state,
            "selected_count": self.selected_count,
            "reviewed_count": self.reviewed_count,
            "skipped_count": self.skipped_count,
            "selected": [item.to_dict() for item in self.selected],
            "reviewed": [item.to_dict() for item in self.reviewed],
            "skipped": [item.to_dict() for item in self.skipped],
        }


def validate_review_coverage(
    values: Iterable[dict[str, Any]],
    inventory: Iterable[dict[str, Any]],
) -> ReviewCoverage:
    """Reconcile one model-produced review ledger against a frozen PR inventory."""

    expected: dict[tuple[str, str], ReviewCoverageItem] = {}
    for raw in inventory:
        if not isinstance(raw, dict) or set(raw) != {"path", "status"}:
            raise EvidenceError("Frozen review inventory entries require exactly path and status")
        path = _validate_review_path(raw.get("path"))
        status = raw.get("status")
        if status not in _ALLOWED_PR_FILE_STATUS:
            raise EvidenceError(f"Invalid review coverage status: {status!r}")
        key = (path, status)
        if key in expected:
            raise EvidenceError(f"Duplicate frozen review inventory entry: {path} ({status})")
        expected[key] = ReviewCoverageItem(path, status, "selected")

    actual: dict[tuple[str, str], ReviewCoverageItem] = {}
    for raw in values:
        if not isinstance(raw, dict) or set(raw) - {"path", "status", "outcome", "reason"}:
            raise EvidenceError("Review coverage entries contain unexpected fields")
        path = _validate_review_path(raw.get("path"))
        status = raw.get("status")
        outcome = raw.get("outcome")
        if status not in _ALLOWED_PR_FILE_STATUS:
            raise EvidenceError(f"Invalid review coverage status: {status!r}")
        if outcome not in _ALLOWED_REVIEW_OUTCOME:
            raise EvidenceError(f"Invalid review coverage outcome: {outcome!r}")
        reason_value = raw.get("reason")
        if reason_value is not None and not isinstance(reason_value, str):
            raise EvidenceError("Review coverage reason must be text")
        reason = redact_text(reason_value or "").strip()
        if outcome == "skipped" and not reason:
            raise EvidenceError("Skipped review coverage entry requires a reason")
        if outcome == "reviewed" and reason:
            raise EvidenceError("Reviewed coverage entry must not include a reason")
        key = (path, status)
        if key in actual:
            raise EvidenceError(f"Duplicate review coverage entry: {path} ({status})")
        actual[key] = ReviewCoverageItem(path, status, outcome, reason or None)

    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise EvidenceError(
            f"Review coverage does not match frozen inventory: missing={missing}, extra={extra}"
        )

    selected = tuple(expected[key] for key in sorted(expected))
    reviewed = tuple(actual[key] for key in sorted(actual) if actual[key].outcome == "reviewed")
    skipped = tuple(actual[key] for key in sorted(actual) if actual[key].outcome == "skipped")
    if not selected:
        terminal_state = "skipped"
    elif skipped:
        terminal_state = "partial"
    else:
        terminal_state = "complete"
    return ReviewCoverage(
        selected=selected,
        reviewed=reviewed,
        skipped=skipped,
        terminal_state=terminal_state,
    )


@dataclass(frozen=True)
class Freshness:
    status: str
    reason: str
    reviewed_sha: str
    current_sha: str
    evidence_time: str | None


def evidence_freshness(
    reviewed_sha: str,
    current_sha: str,
    evidence_time: str | None,
    *,
    now: datetime | None = None,
    max_age_seconds: int = 86400,
) -> Freshness:
    if not reviewed_sha or not current_sha:
        return Freshness("unverifiable", "missing reviewed or current SHA", reviewed_sha, current_sha, evidence_time)
    if reviewed_sha != current_sha:
        return Freshness("stale", "reviewed SHA differs from current SHA", reviewed_sha, current_sha, evidence_time)
    if evidence_time is None:
        return Freshness("unverifiable", "missing evidence timestamp", reviewed_sha, current_sha, None)
    try:
        observed = datetime.fromisoformat(evidence_time.replace("Z", "+00:00"))
    except ValueError:
        return Freshness("unverifiable", "invalid evidence timestamp", reviewed_sha, current_sha, evidence_time)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    current_time = now or datetime.now(timezone.utc)
    age = (current_time - observed.astimezone(timezone.utc)).total_seconds()
    if age < 0:
        return Freshness("unverifiable", "evidence timestamp is in the future", reviewed_sha, current_sha, evidence_time)
    if age > max_age_seconds:
        return Freshness("stale", f"evidence is {int(age)} seconds old", reviewed_sha, current_sha, evidence_time)
    return Freshness("current", "SHA and timestamp are current", reviewed_sha, current_sha, evidence_time)


class RunLedger:
    """Append-only, redacted, hash-chained JSONL run ledger."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _last_hash(self) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return "0" * 64
        last = self.path.read_text(encoding="utf-8").splitlines()[-1]
        value = json.loads(last)
        digest = value.get("entry_hash")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise EvidenceError("Ledger tail has no valid entry_hash")
        return digest

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        body = {
            "schema_version": 1,
            "recorded_at": utc_now(),
            "previous_hash": self._last_hash(),
            "event": redact(event),
        }
        body["entry_hash"] = hashlib.sha256(canonical_json(body)).hexdigest()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(body, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return body

    def verify(self) -> dict[str, Any]:
        previous = "0" * 64
        count = 0
        if not self.path.exists():
            return {"ok": True, "entries": 0, "tail_hash": previous}
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvidenceError(f"Invalid ledger JSON on line {number}") from exc
            digest = entry.pop("entry_hash", None)
            if entry.get("previous_hash") != previous:
                raise EvidenceError(f"Broken ledger chain on line {number}")
            expected = hashlib.sha256(canonical_json(entry)).hexdigest()
            if digest != expected:
                raise EvidenceError(f"Ledger hash mismatch on line {number}")
            previous = digest
            count += 1
        return {"ok": True, "entries": count, "tail_hash": previous}
