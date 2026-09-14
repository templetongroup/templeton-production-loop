# Project Setup Stage

This is an internal report-only planning stage of `templeton-build`, not a standalone skill.

Use it after a confirmed project seed when repository location, stack, commands, environments, ownership, or deployment boundaries still need an explicit setup decision. Inspect live prerequisites and produce a reviewed setup packet covering:

- repository path, ownership, canonical remote, branch and worktree strategy;
- chosen stack and why it fits the confirmed product constraints;
- local run, test, lint/typecheck, build, and smoke commands;
- environment-variable names with credentials reported only as `present` or `missing`;
- first vertical slice and acceptance proof;
- deployment target, approval gate, rollback, and live verification;
- risks, unresolved decisions, and exact next action.

Setup-only mode never scaffolds files, installs dependencies, mutates GitHub, applies `loop:agent-ready`, deploys, or silently enters implementation. When the operator's confirmed request explicitly includes building the product, the setup packet may be handed to a separate implementation stage; that stage performs and verifies the scaffold under the normal implementation contract.
