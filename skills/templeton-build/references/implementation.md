# Implementation, Debugging, and Tests

## Standard implementation loop

1. Inspect repository rules, nearby patterns, dependency manifests, scripts, tests, and current behavior.
2. Define the shortest trustworthy feedback loop.
3. Make one focused change while preserving unrelated work.
4. Add or update behavioral tests at the real public seam.
5. Run focused proof, then the relevant broader suite.
6. Remove temporary diagnostics and inspect the final diff.

## Debugging

Build a red-capable check before theorizing. Prefer a focused failing test, HTTP/CLI probe, headless-browser assertion, captured-trace replay, throwaway harness, deterministic stress loop, bisection, or differential comparison. Run it once before the fix and preserve the exact invocation.

Minimize the reproduction, rank a small set of falsifiable hypotheses, probe one variable at a time, fix the root cause narrowly, watch the regression proof turn green, and rerun the original unminimized path. If no trustworthy loop can be built, report what was attempted and request the missing fixture, trace, log, recording, or environment.

## Test strategy

Map risk to the right test type: unit, integration, contract, end-to-end, smoke, regression, property, replay, or live probe. Prefer public behavior over internals. Avoid tautological assertions, fake mocks that cannot fail for the reported bug, and snapshots without an independent truth source.

## Long work and delegation

Use a named worktree/session and concise on-disk checkpoint for substantial work. Split only genuinely independent tasks. Every delegated implementer receives the complete bounded contract and proof command; every reviewer receives the fixed diff and original contract. Do not parallelize overlapping edits.

## Quality rules

- Follow the stack already present unless a change is justified.
- Keep changes focused and reviewable.
- Treat errors, validation, permissions, concurrency, migrations, compatibility, observability, and rollback as first-class where relevant.
- Never commit generated secrets, local credentials, unbounded logs, or machine-specific state.
- Do not stop at a stub when the user asked for a build, run, or fix.
