# Repository Instructions

This repository implements the Templeton Production Loop.

- Keep one model- and harness-neutral workflow. New models use routing configuration; new harnesses satisfy the connector interface; target platforms use verification profiles. Do not fork the loop into separately maintained runtime repositories.
- Preserve the hard boundary: agents may spec, build, test, push branches, open PRs, and post loop verdicts; humans merge and authorize deployments.
- GitHub Issues are the durable work contract. Do not add another issue tracker without a real adapter and migration plan.
- Keep queue selection deterministic and independently testable.
- Keep mutating CLI commands dry-run by default or require an explicit `--apply`/execution command.
- Proof Runner plans are trusted executable configuration. Keep source snapshots disposable, verifiers argv-only, environments allowlisted, retries bounded, and evidence append-only; never let `prove` mutate the original source tree.
- Strategy and worker model roles must remain explicit in plans and evidence: use the high-capability model for one bounded strategy pass, then route execution to the cheaper default worker model unless a task explicitly overrides it.
- Add tests for changes to labels, candidate selection, SHA pinning, agent commands, locking, model routing, proof workspaces, verifier behavior, evidence writes, or safety gates.
- Generic connectors are trusted host software. Require strict config and preflight schemas, exact workspace identity, fresh sessions, structured output, enforced isolation, network `none`, credential access `none`, and the role's exact workspace access before invoking a model.
- Do not print or store credentials.
- Optional helpers under `optional-skills/` are report-only and outside outer-loop authority; they must not apply `loop:agent-ready` or mutate GitHub/source state.
- Selected optional productivity helpers (`templeton-grill`, `templeton-handoff`, `templeton-questionnaire`, `templeton-wait-what`, `templeton-writing-for-agents`) are operator-assist only.
