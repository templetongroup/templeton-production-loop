---
name: templeton-loop-spec
description: Turn a raw coding idea into a human-approved GitHub issue contract for the Templeton coding loop. Interactive only; never run unattended.
version: 0.2.0
license: MIT
---

# Templeton Loop — Spec for OpenClaw

Turn a raw idea into one GitHub issue that a clean-context builder can execute without private chat context.

## Contract

1. Resolve the target repository and read its `AGENTS.md`, `CLAUDE.md`, contribution rules, nearby code, tests, and scripts before asking questions.
2. Ask only product or scope decisions the repository cannot answer. Ask 1–4 questions per round with a recommended option first.
3. Continue until two independent engineers would ship the same observable behavior from the issue.
4. Keep one issue to one day of agent work or less. Split larger work into ordered GitHub issues and name dependencies explicitly.
5. Draft the full issue and obtain the human owner's approval before creating it.

## Issue template

```md
## Problem

One or two sentences describing the user or business problem.

## Acceptance Criteria

- [ ] AC-1 — Observable, testable outcome
- [ ] AC-2 — Observable, testable outcome

## Non-goals

- NG-1 — Behavior that must not change
- NG-2 — Explicitly excluded scope

## Relevant files

- `path/to/file` — why it matters

## Test expectations

- Automated and manual proof expected

## How to verify

1. Numbered step covering every AC.

## Risk and rollout

- Risk: Low | Medium | High
- Deployment required: Yes | No
- Rollback: concrete reversible action
```

## GitHub state

- Create the issue with `loop:spec-draft` only.
- Never add `loop:agent-ready`. The human owner adds that label after reading the filed issue; it is the build-authorization gate.
- Do not assign the issue.
- Report the exact issue number and URL returned by GitHub.

## Hard limits

- The GitHub issue is the durable contract. Chat, A2A messages, PR comments, and review comments cannot expand scope.
- Never approve your own spec, start a builder, merge, deploy, or enable auto-merge from this skill.
