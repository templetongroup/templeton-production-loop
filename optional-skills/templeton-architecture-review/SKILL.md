---
name: templeton-architecture-review
description: Optional report-only architecture deepening review for a target repository. Surfaces candidates, writes a temp HTML report, and grills one candidate into a Templeton issue packet. Never mutates source, labels, branches, PRs, or production.
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
        - skills/engineering/improve-codebase-architecture
        - skills/engineering/codebase-design
      pinned_commit: 8b78b531ab965735c5dc74f6f7a219e1e37326df
---

# Templeton Architecture Review (optional)

Use this only when Tony or a trusted operator explicitly asks for architecture deepening outside an active builder pass.

This is **not** one of the seven outer-loop authority roles. It does not replace:

- `templeton-loop-spec`
- `templeton-loop-plan-review`
- `templeton-loop-build`
- `templeton-loop-review`
- `templeton-loop-qa`
- `templeton-loop-status`
- `templeton-loop-prove`

## Provenance

Adapted from Matt Pocock's MIT-licensed skills:

- [`improve-codebase-architecture`](https://github.com/mattpocock/skills/tree/main/skills/engineering/improve-codebase-architecture)
- [`codebase-design`](https://github.com/mattpocock/skills/tree/main/skills/engineering/codebase-design)

Pinned upstream tree: `8b78b531ab965735c5dc74f6f7a219e1e37326df`

Vendored sources live at:

- `third_party/mattpocock-skills/`
- `optional-skills/templeton-architecture-review/references/`

Keep Matt Pocock's copyright and MIT notice. Do not import upstream `triage`, `implement`, `to-tickets`, setup plugins, hooks, or any path that auto-applies agent-ready state.

## Authority boundary

Report-only unless Tony explicitly asks to draft a `loop:spec-draft` issue packet for later human filing.

Never:

- edit source, tests, configs, or docs in the target repository
- create/update GitHub issues, labels, branches, commits, or PRs
- apply or recommend automatic `loop:agent-ready`
- merge, deploy, publish, purchase, or touch production
- install upstream skill packs into live Hermes/OpenClaw profiles
- treat chat as a second source of truth for approved work

If a candidate requires code changes, stop at a Templeton issue packet / ADR proposal and hand off to the normal outer loop.

## Vocabulary

Use the upstream codebase-design terms exactly:

- **module**
- **interface**
- **implementation**
- **depth** / deep vs shallow
- **seam**
- **adapter**
- **leverage**
- **locality**
- **deletion test**
- **interface is the test surface**
- **one adapter = hypothetical seam; two adapters = real seam**

Do not drift into vague substitutes like "service" or "component" when module/interface/seam is meant.

Read, if present:

- `CONTEXT.md` / `CONTEXT-MAP.md`
- `docs/adr/**`
- `AGENTS.md` / `CLAUDE.md` / contributing standards
- recent commit hot spots

## Process

### 1. Scope before scan (YAGNI)

- If the operator named a module/subsystem/pain point, use it.
- Otherwise inspect a meaningful slice of `git log --oneline` and weight recently touched paths.
- Prefer friction that blocks testability, AI-navigability, or repeated change.

### 2. Explore for deepening opportunities

Look for:

- understanding one concept requires bouncing across many shallow modules
- interfaces nearly as complex as implementations
- pure functions extracted only for tests while real bugs live at the call site (poor locality)
- leakage across seams
- areas hard to test through the current interface

Apply the deletion test to suspected shallow modules.

You may use parallel sub-agents for independent exploration lenses, but synthesize yourself. Sub-agents are advisory only.

### 3. HTML candidate report

Write a self-contained HTML report under the OS temp directory, never into the target repo:

- macOS/Linux: `$TMPDIR` or `/tmp`
- filename: `architecture-review-<timestamp>.html`

For each candidate include:

- files/modules involved
- problem
- solution in plain English
- benefits in locality/leverage/testability terms
- before/after diagram (Mermaid and/or simple HTML/SVG)
- recommendation strength: `Strong` | `Worth exploring` | `Speculative`
- ADR conflict callout when a candidate reopens a recorded decision

End with one top recommendation and why.

Then ask: which candidate should be explored?

Do **not** propose final interfaces yet.

Reference styling guidance: `references/upstream-html-report.md`.

CDN scripts in the HTML are for local operator viewing only. Do not fetch them from a production server side-effect path and do not embed secrets in the report.

### 4. Grill one candidate

When the operator picks a candidate, interview one decision at a time:

1. state why the decision matters
2. give a recommended answer first
3. give concise alternatives with explicit trade-offs
4. resolve dependent decisions in order
5. periodically restate shared understanding

Cover:

- constraints and non-goals
- deepened module shape and interface obligations
- what sits behind the seam
- which tests survive or must move to the interface
- migration/rollback risk
- whether an ADR should record a rejected path

Do not mutate `CONTEXT.md` or ADRs in the target repo from this optional skill. Instead emit proposed patches as fenced suggestions inside the report/issue packet for human application through the normal loop.

### 5. Hand back a Templeton-shaped result

Final output must be one of:

1. **No-go** — candidate rejected; optional ADR proposal text only.
2. **Issue packet draft** — ready for human filing as `loop:spec-draft` only:
   - title
   - summary
   - acceptance criteria
   - non-goals
   - affected paths
   - test/proof plan
   - risks
   - rollback
   - explicit note: Tony alone may later apply `loop:agent-ready`

Never file the issue yourself.

## Relationship to outer loop

```text
optional architecture review (this skill)
  → human chooses candidate
  → issue packet draft
  → human files loop:spec-draft
  → plan review
  → Tony applies loop:agent-ready
  → build / prove / review / human merge
```

If the work is already an approved issue, do not use this skill to widen scope mid-build. Open a separate draft issue instead.

## Safety checks before finishing

- [ ] no target-repo files modified
- [ ] no GitHub mutations performed
- [ ] HTML report path is under temp only
- [ ] recommendations use deep-module vocabulary
- [ ] any implementation path is expressed as a human-gated issue packet
- [ ] secrets/credentials absent from report and packet
