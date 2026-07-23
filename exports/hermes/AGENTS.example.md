# Templeton Coding Loop routing example for Hermes

Copy only the relevant block into the receiving profile or repository instructions. Replace placeholders with real repository paths and owners.

## Shared contract

When a request explicitly invokes the Templeton Coding Loop, use GitHub Issues as the only mutable work queue. Never treat chat as authorization to expand an approved issue. A human applies `loop:agent-ready` and makes every merge/deployment decision. Never merge, enable auto-merge, deploy, publish, purchase, or mutate production from a loop role.

## Intake/spec role

For new ideas, load `templeton-loop-spec`. Inspect the repository before asking questions. Show the complete issue contract before filing it. Create it with `loop:spec-draft` only. Never self-apply `loop:agent-ready` or start the builder.

## Builder role

Only build an issue already carrying `loop:agent-ready`. Load `templeton-loop-build`. Use a fresh Hermes `--worktree` session. Perform one bounded repair or one issue-to-PR pass, run real verification, open a PR, and stop.

## Reviewer role

Load `templeton-loop-review` in a fresh session that does not share builder context. Review one PR against the linked issue, exact head SHA, required CI, and mergeability. Post evidence labels/comments only; never change code or merge.

## Status role

Load `templeton-loop-status` for a read-only report of merge candidates, human decisions, blocked questions, repairs, ready work, and in-flight work.
