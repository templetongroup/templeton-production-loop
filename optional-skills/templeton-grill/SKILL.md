---
name: templeton-grill
description: Relentless one-question-at-a-time design interview for Templeton plans and issue contracts. Resolves the design tree before implementation. Report-only; never applies loop:agent-ready.
version: 1.0.0
license: MIT
metadata:
  templeton:
    role_class: optional-helper
    authority: report-only
    outer_loop: false
    upstream:
      repo: https://github.com/mattpocock/skills
      paths:
        - skills/productivity/grill-me
        - skills/productivity/grilling
      pinned_commit: 8b78b531ab965735c5dc74f6f7a219e1e37326df
---

# Templeton Grill (optional)

Stress-test a plan, product idea, architecture choice, or issue contract until shared understanding is real.

Adapted from Matt Pocock's MIT-licensed `grill-me` / `grilling` skills at pin `8b78b531ab965735c5dc74f6f7a219e1e37326df`.
Vendored sources: `third_party/mattpocock-skills/productivity/grill-me/` and `.../grilling/`.

Templeton difference from upstream default: **ask exactly one decision question at a time** (Tony preference), not a full multi-question frontier round.


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

1. Build a design tree: root goal, decisions, dependent branches, unresolved assumptions.
2. Look up facts yourself from the supplied repo/context/tools. Do not ask the operator for facts you can retrieve.
3. Identify the frontier: decisions whose prerequisites are settled.
4. Ask **one** frontier question:
   - why it matters
   - recommended answer first
   - concise alternatives, each with an explicit trade-off
5. Wait for the answer. Recompute the frontier. Repeat.
6. Periodically restate shared understanding.
7. Stop only when the frontier is empty and the operator confirms shared understanding.

## Output

When done, produce:

- settled decisions
- rejected alternatives and why
- remaining risks/unknowns
- if implementation is next: a `loop:spec-draft` issue packet for **human** filing only

Do not implement, branch, or label.
