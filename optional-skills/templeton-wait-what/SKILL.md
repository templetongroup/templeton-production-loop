---
name: templeton-wait-what
description: Re-pitch the last Templeton status or recommendation more simply with missing context and project vocabulary. No side effects.
version: 1.0.0
license: MIT
metadata:
  templeton:
    role_class: optional-helper
    authority: report-only
    outer_loop: false
    upstream:
      repo: https://github.com/mattpocock/skills
      paths: [skills/productivity/wait-what]
      pinned_commit: 8b78b531ab965735c5dc74f6f7a219e1e37326df
---

# Templeton Wait-What (optional)

Use when the last message did not land.

Adapted from Matt Pocock's MIT-licensed `wait-what` skill at pin `8b78b531ab965735c5dc74f6f7a219e1e37326df`.
Vendored source: `third_party/mattpocock-skills/productivity/wait-what/`.


## Authority boundary

Optional operator helper only. **Not** one of the seven outer-loop authority roles.

Never:
- apply or recommend automatic `loop:agent-ready`
- merge, deploy, publish, purchase, or mutate production
- edit target-repo source unless the operator explicitly asked for a local draft file and the path is outside protected production systems
- create/update GitHub issues, labels, branches, commits, or PRs
- install upstream skill packs into live Hermes/OpenClaw profiles
- print or store secrets; redact credentials, tokens, and PII

If implementation work is needed, stop at a draft artifact / issue packet for human filing into the normal Production Loop.


## Process

Re-pitch immediately:

1. one-sentence context of where we are
2. plain-language explanation (short sentences, concrete words)
3. use project vocabulary from `CONTEXT.md` / issue contract when present
4. state the current recommendation and the exact decision needed
5. no new scope, no tool side effects, no implementation

## Output

A short re-pitch only. If a decision is needed, end with one clear question.
