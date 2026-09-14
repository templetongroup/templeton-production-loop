# Independent Review and QA

## Review independence

A meaningful change gets a fresh reviewer who did not implement it. The reviewer is report-only and cannot edit code, merge, deploy, dismiss reviews, or widen the requested scope. Pin the base and head before judgment.

## Complete diff review

1. Identify the requested-behavior source and repository standards.
2. Freeze the exact base SHA, head SHA, status-bearing `(path, status)` inventory, commit range, and diff.
3. Assign each inventory entry exactly one outcome: `reviewed` or `skipped: <concrete reason>`. Deleted, binary, generated, oversized, unreadable, renamed, copied, and test files cannot disappear silently.
4. Reconcile totals programmatically. A skipped/missing file or truncated hunk means partial coverage and cannot support approval.
5. Review every file locally for correctness, security, data loss, validation, errors, concurrency, permissions, migrations, performance, compatibility, maintainability, and regression risk.
6. Inspect targeted callers, contracts, schemas, configs, and dependencies only to verify concrete risks.
7. For large diffs, partition the full inventory into bounded semantic groups, give each reviewer the global contract/inventory, then perform one cross-group integration pass.
8. Apply artifact-specific checks where relevant: CI permissions and untrusted events; dependency provenance and lockfiles; schema/IDL/migration reversibility; output encoding; and configuration/i18n parity.

## Validate findings

Recheck each candidate against the pinned diff and full subject-file context. Confirm changed behavior or a contract-required omission, verify anchors, deduplicate root causes, and discard unsupported preferences. Every blocker needs evidence, impact, fix direction, and a verification command. Separate spec compliance, engineering quality, and coverage.

## Production Loop review evidence

A brokered review begins with exactly:

`Templeton Loop review of HEAD_SHA against BASE_SHA`

The broker, not model prose, adds authenticated machine state:

`Review-State: verdict=<approved|changes-requested|needs-human-review|awaiting-review>; coverage=<complete|partial|skipped>`

Publish only for the still-current comparison. Complete coverage plus clean contract, required CI green, and mergeability may produce `loop:approved`. Complete must-fix findings produce `loop:changes-requested`. Missing CI, scope conflict, high-risk uncertainty, or policy ambiguity produces `loop:needs-human-review`. Partial coverage removes stale terminal approval/change labels and preserves `loop:awaiting-review`. Preserve an existing human-review gate until a human resolves it.

## QA

QA verifies acceptance behavior against the exact reviewed candidate; it does not edit code. Map each acceptance criterion to an observable check, include failure/empty/loading/permission/responsive paths where relevant, run the commands, and distinguish pass, fail, blocked, and not applicable. If the candidate SHA changes, discard stale QA and rerun. Final human merge authority is never delegated.
