---
name: templeton-questionnaire
description: Turn a decision Templeton cannot answer alone into a Markdown questionnaire for one recipient. Operator-assist only; no GitHub mutation.
version: 1.0.0
license: MIT
metadata:
  templeton:
    role_class: optional-helper
    authority: report-only
    outer_loop: false
    upstream:
      repo: https://github.com/mattpocock/skills
      paths: [skills/productivity/to-questionnaire]
      pinned_commit: 8b78b531ab965735c5dc74f6f7a219e1e37326df
---

# Templeton Questionnaire (optional)

When a blocked loop decision needs knowledge from one specific person, draft a discovery questionnaire.

Adapted from Matt Pocock's MIT-licensed `to-questionnaire` skill at pin `8b78b531ab965735c5dc74f6f7a219e1e37326df`.
Vendored source: `third_party/mattpocock-skills/productivity/to-questionnaire/`.


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

Grill the **send**, not the subject:

1. Who is the recipient (role, expertise, relationship)?
2. What concrete decisions/facts must come back?
3. Draft the questionnaire covering every item from step 2.

Default write location: OS temp `templeton-questionnaire-<slug>.md`.
Write into the current workspace only if the operator explicitly asks.

## Document shape

- Purpose and decision riding on it
- From / To / how answers will be used
- Short context
- How to answer (deadline, partial answers OK)
- Themed questions, most-important first, one idea each, answer stub beneath
- Closing "anything else?"

## Output

Absolute file path + the list of decisions the answers will unlock. Do not email/send/post the questionnaire unless the operator explicitly asks another system owner to do so.
