from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from .evidence import EvidenceError, redact, utc_now


@dataclass(frozen=True)
class Outcome:
    task_class: str
    provider: str
    model: str
    passed: bool
    duration_ms: int
    attempts: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    failure_class: str | None = None
    recorded_at: str | None = None

    def validate(self) -> "Outcome":
        for name in ("task_class", "provider", "model"):
            if not getattr(self, name).strip():
                raise EvidenceError(f"Outcome {name} must not be empty")
        if isinstance(self.duration_ms, bool) or self.duration_ms < 0:
            raise EvidenceError("duration_ms must be a non-negative integer")
        if isinstance(self.attempts, bool) or self.attempts < 1:
            raise EvidenceError("attempts must be at least one")
        for name in ("input_tokens", "output_tokens"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise EvidenceError(f"{name} must be non-negative when present")
        if self.cost_usd is not None and self.cost_usd < 0:
            raise EvidenceError("cost_usd must be non-negative when present")
        return self

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Outcome":
        try:
            return cls(**value).validate()
        except TypeError as exc:
            raise EvidenceError(f"Invalid outcome fields: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        if value["recorded_at"] is None:
            value["recorded_at"] = utc_now()
        return redact(value)


def append_outcome(path: Path, outcome: Outcome) -> None:
    outcome.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(outcome.to_dict(), sort_keys=True) + "\n")


def read_outcomes(path: Path) -> list[Outcome]:
    if not path.exists():
        return []
    result: list[Outcome] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            value = json.loads(line)
            result.append(Outcome.from_dict(value))
        except (json.JSONDecodeError, EvidenceError) as exc:
            raise EvidenceError(f"Invalid outcome on line {number}: {exc}") from exc
    return result


def wilson_lower_bound(successes: int, total: int, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    margin = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total)
    return (centre - margin) / denominator


def summarize_outcomes(outcomes: Iterable[Outcome], *, task_class: str | None = None) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[Outcome]] = {}
    for outcome in outcomes:
        if task_class is not None and outcome.task_class != task_class:
            continue
        groups.setdefault((outcome.task_class, outcome.provider, outcome.model), []).append(outcome)
    rows: list[dict[str, Any]] = []
    for (kind, provider, model), values in groups.items():
        successes = sum(item.passed for item in values)
        durations = [item.duration_ms for item in values]
        costs = [item.cost_usd for item in values if item.cost_usd is not None]
        rows.append(
            {
                "task_class": kind,
                "provider": provider,
                "model": model,
                "samples": len(values),
                "passed": successes,
                "pass_rate": successes / len(values),
                "confidence_floor": wilson_lower_bound(successes, len(values)),
                "median_duration_ms": int(median(durations)),
                "median_cost_usd": median(costs) if costs else None,
                "median_attempts": median(item.attempts for item in values),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["task_class"],
            -row["confidence_floor"],
            row["median_cost_usd"] if row["median_cost_usd"] is not None else float("inf"),
            row["median_duration_ms"],
            row["provider"],
            row["model"],
        ),
    )


def recommend_route(
    outcomes: Iterable[Outcome],
    task_class: str,
    *,
    minimum_samples: int = 3,
    minimum_pass_rate: float = 0.8,
) -> dict[str, Any]:
    rows = summarize_outcomes(outcomes, task_class=task_class)
    eligible = [
        row
        for row in rows
        if row["samples"] >= minimum_samples and row["pass_rate"] >= minimum_pass_rate
    ]
    if not eligible:
        return {
            "task_class": task_class,
            "status": "insufficient-evidence",
            "route": None,
            "candidates": rows,
        }
    chosen = eligible[0]
    return {
        "task_class": task_class,
        "status": "recommended",
        "route": {"provider": chosen["provider"], "model": chosen["model"]},
        "evidence": chosen,
        "candidates": rows,
    }


REQUIRED_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "spec": ("report-output",),
    "plan-review": ("repository-read", "report-output"),
    "build": ("repository-read", "workspace-write", "report-output"),
    "review": ("repository-read", "report-output"),
    "qa": ("repository-read", "report-output"),
    "status": ("github-read", "report-output"),
    "prove-strategy": ("snapshot-read", "report-output"),
    "prove-worker": ("snapshot-read", "workspace-write", "report-output"),
}

FORBIDDEN_CAPABILITIES = {
    "merge",
    "auto-merge",
    "deploy",
    "publish",
    "purchase",
    "production-mutation",
    "credential-read",
    "github-write",
    "network",
    "gateway",
    "session-send",
    "cross-workspace-write",
}


def coverage_matrix(capabilities: dict[str, list[str]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    unknown_task_classes = sorted(set(capabilities) - set(REQUIRED_CAPABILITIES))
    ok = not unknown_task_classes
    for task_class, required in REQUIRED_CAPABILITIES.items():
        actual = set(capabilities.get(task_class, []))
        missing = sorted(set(required) - actual)
        forbidden = sorted(actual & FORBIDDEN_CAPABILITIES)
        unexpected = sorted(actual - set(required))
        row_ok = not missing and not unexpected
        rows.append(
            {
                "task_class": task_class,
                "required": list(required),
                "actual": sorted(actual),
                "missing": missing,
                "forbidden": forbidden,
                "unexpected": unexpected,
                "ok": row_ok,
            }
        )
        ok = ok and row_ok
    return {"ok": ok, "unknown_task_classes": unknown_task_classes, "rows": rows}
