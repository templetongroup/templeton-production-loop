---
name: templeton-handoff
description: Compact the current Templeton work session into a secret-redacted handoff document in the OS temp directory for a fresh agent or human operator.
version: 1.0.0
license: MIT
metadata:
  templeton:
    role_class: optional-helper
    authority: report-only
    outer_loop: false
    upstream:
      repo: https://github.com/mattpocock/skills
      paths: [skills/productivity/handoff]
      pinned_commit: 8b78b531ab965735c5dc74f6f7a219e1e37326df
---

# Templeton Handoff (optional)

Write a compact handoff so a fresh agent or operator can continue without replaying the whole chat.

Adapted from Matt Pocock's MIT-licensed `handoff` skill at pin `8b78b531ab965735c5dc74f6f7a219e1e37326df`.
Vendored source: `third_party/mattpocock-skills/productivity/handoff/`.


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

1. Identify the goal, current state, settled decisions, and next action.
2. Prefer references over duplication: issue URLs, PR SHAs, file paths, proof run dirs, ADRs, specs.
3. Redact secrets, tokens, credentials, private personal data, and raw env values.
4. Write to OS temp only:
   - `$TMPDIR` / `/tmp` / `%TEMP%`
   - filename: `templeton-handoff-<timestamp>.md`
5. Include:
   - objective
   - repo/path and branch/SHA if known
   - what changed / what was proven
   - open blockers and exact questions
   - suggested Templeton skills/roles for the next session
   - explicit non-actions (no merge/deploy/agent-ready)

## Output

Return the absolute handoff path and a 5-line summary. Do not write the handoff into the target repository unless the operator explicitly requests a repo path.
