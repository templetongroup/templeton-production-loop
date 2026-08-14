---
name: templeton-writing-for-agents
description: Write or edit Templeton agent-facing docs and optional skills with clear context pointers, low always-on load, and no authority leakage.
version: 1.0.0
license: MIT
metadata:
  templeton:
    role_class: optional-helper
    authority: report-only
    outer_loop: false
    upstream:
      repo: https://github.com/mattpocock/skills
      paths: [skills/productivity/writing-for-agents]
      pinned_commit: 8b78b531ab965735c5dc74f6f7a219e1e37326df
---

# Templeton Writing for Agents (optional)

Reference skill for writing documents agents consume: optional skills, `AGENTS.md`, role prompts, and pointer docs.

Adapted from Matt Pocock's MIT-licensed `writing-for-agents` skill at pin `8b78b531ab965735c5dc74f6f7a219e1e37326df`.
Vendored sources: `third_party/mattpocock-skills/productivity/writing-for-agents/`.


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


## Templeton rules layered on upstream

- Outer-loop authority stays in the seven core roles + human gates.
- Optional skills must say they are optional and report-only when they are.
- Never write instructions that allow merge/deploy/agent-ready from a helper.
- Prefer progressive disclosure: short always-on pointers, deeper refs on demand.
- Keep descriptions trigger-rich and short; put procedure in the body.
- Distinguish steps vs reference; do not bury must-do safety in optional appendixes.

## Process

1. Identify audience (builder/reviewer/operator/optional helper).
2. Define the always-on pointer text and the branches that should load the doc.
3. Write steps in order; move deep reference out of the main path.
4. Add explicit non-goals and forbidden side effects.
5. If editing a core loop skill, preserve existing safety contract phrases and tests.

## Output

Draft markdown and a short checklist of what is always-on vs disclosed. Do not install skills into live profiles unless the operator explicitly requests installation through the normal trusted host path.
