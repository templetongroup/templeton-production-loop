# Repository Instructions

This repository implements the Templeton coding loop.

- Preserve the hard boundary: agents may spec, build, test, push branches, open PRs, and post loop verdicts; humans merge and authorize deployments.
- GitHub Issues are the durable work contract. Do not add another issue tracker without a real adapter and migration plan.
- Keep queue selection deterministic and independently testable.
- Keep mutating CLI commands dry-run by default or require an explicit `--apply`/execution command.
- Add tests for changes to labels, candidate selection, SHA pinning, agent commands, locking, or safety gates.
- Do not print or store credentials.
