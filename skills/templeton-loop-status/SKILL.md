---
name: templeton-loop-status
description: Read-only status of Templeton coding-loop queues across GitHub issues and pull requests, returning Tony's exact approve, answer, review, or merge actions.
---

# Templeton Loop — Status

Read the live repository state; never mutate it.

Report these ordered groups:

1. **Merge candidates** — open PRs carrying `loop:approved`, current required CI green, clean mergeability, and current SHA equal to the latest Templeton Loop review SHA.
2. **Human review** — PRs carrying `loop:needs-human-review`, with the exact reason and current SHA.
3. **Blocked questions** — open issues carrying `loop:blocked`, with the latest concrete question.
4. **Changes requested** — PRs carrying `loop:changes-requested`, including repair-round count.
5. **Ready queue** — unassigned issues carrying `loop:agent-ready` and not `loop:blocked` or `loop:building`.
6. **In flight** — claimed/building issues and PRs awaiting review.
7. **Spec drafts** — issues carrying `loop:spec-draft` but not `loop:agent-ready`.

Return exact URLs and one-line actions. Re-read GitHub; do not rely on chat or cached state. Never merge, label, assign, comment, or start a worker from this skill.
