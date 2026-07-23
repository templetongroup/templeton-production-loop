from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .evidence import redact_text


class BoundaryError(RuntimeError):
    def __init__(self, *, sink: str, rule_ids: tuple[str, ...], byte_count: int, sha256: str) -> None:
        self.sink = sink
        self.rule_ids = rule_ids
        self.byte_count = byte_count
        self.sha256 = sha256
        super().__init__(
            f"Blocked {sink} payload by {','.join(rule_ids)}; bytes={byte_count}; sha256={sha256}"
        )


@dataclass(frozen=True)
class PreparedPayload:
    sink: str
    text: str
    byte_count: int
    sha256: str
    prepared_at: str


@dataclass(frozen=True)
class BlockedPayload:
    sink: str
    rule_ids: tuple[str, ...]
    byte_count: int
    sha256: str
    blocked_at: str


def scan_text(text: str, *, max_bytes: int) -> tuple[str, ...]:
    raw = text.encode("utf-8")
    rules: list[str] = []
    if len(raw) > max_bytes:
        rules.append("size-limit")
    if redact_text(text) != text:
        rules.append("high-confidence-secret")
    return tuple(rules)


def prepare_sink(text: str, *, sink: str, max_bytes: int = 100_000) -> PreparedPayload:
    if not isinstance(text, str):
        raise TypeError("Sink payload must be text")
    raw = text.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    rules = scan_text(text, max_bytes=max_bytes)
    if rules:
        raise BoundaryError(
            sink=sink,
            rule_ids=rules,
            byte_count=len(raw),
            sha256=digest,
        )
    return PreparedPayload(
        sink=sink,
        text=text,
        byte_count=len(raw),
        sha256=digest,
        prepared_at=datetime.now(timezone.utc).isoformat(),
    )


def blocked_record(error: BoundaryError) -> BlockedPayload:
    return BlockedPayload(
        sink=error.sink,
        rule_ids=error.rule_ids,
        byte_count=error.byte_count,
        sha256=error.sha256,
        blocked_at=datetime.now(timezone.utc).isoformat(),
    )


def wrap_untrusted(kind: str, payload: Any, provenance: dict[str, Any]) -> str:
    if not kind or not kind.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Untrusted envelope kind must be a simple identifier")
    body = json.dumps(
        {"kind": kind, "provenance": provenance, "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    # Prevent an untrusted payload from injecting a literal closing envelope tag.
    body = body.replace("<", "\\u003c").replace(">", "\\u003e")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return (
        f"<templeton-untrusted kind=\"{kind}\" sha256=\"{digest}\">\n"
        f"{body}\n"
        "</templeton-untrusted>"
    )
