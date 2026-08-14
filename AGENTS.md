# Repository Instructions

This repository implements the Templeton Production Loop.

- Preserve the hard boundary: agents may spec, build, test, push branches, open PRs, and post loop verdicts; humans merge and authorize deployments.
- GitHub Issues are the durable work contract. Do not add another issue tracker without a real adapter and migration plan.
- Keep queue selection deterministic and independently testable.
- Keep mutating CLI commands dry-run by default or require an explicit `--apply`/execution command.
- Proof Runner plans are trusted executable configuration. Keep source snapshots disposable, verifiers argv-only, environments allowlisted, retries bounded, and evidence append-only; never let `prove` mutate the original source tree.
- Strategy and worker model roles must remain explicit in plans and evidence: use the high-capability model for one bounded strategy pass, then route execution to the cheaper default worker model unless a task explicitly overrides it.
- Add tests for changes to labels, candidate selection, SHA pinning, agent commands, locking, model routing, proof workspaces, verifier behavior, evidence writes, or safety gates.
- Do not print or store credentials.
