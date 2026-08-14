# Matt Pocock improve-codebase-architecture incorporation

Date: 2026-08-14  
Product: Templeton Production Loop  
Upstream: https://github.com/mattpocock/skills/tree/main/skills/engineering/improve-codebase-architecture

## Decision

Incorporate **selectively** as an optional inner engineering helper, not as an outer-loop authority role.

Shipped:

- vendored upstream sources under `third_party/mattpocock-skills/`
- Templeton-native wrapper: `optional-skills/templeton-architecture-review/`
- pinned commit `8b78b531ab965735c5dc74f6f7a219e1e37326df`

Not shipped as core runtime skills:

- upstream `improve-codebase-architecture` direct install into Hermes/OpenClaw core inventory
- upstream `triage` / `implement` / `to-tickets` / setup plugin flows

## Why

The upstream skill is strong on:

- deep-module vocabulary
- hot-spot-weighted architecture scan
- visual candidate report
- grilling one candidate before interface design

Templeton already owns:

- GitHub issue contracts
- Tony-only `loop:agent-ready`
- isolated build + fresh SHA-pinned review
- proof runner verification

So the right seam is:

architecture helper → issue packet draft → normal production loop

## Boundaries preserved

- report-only default
- no source mutation from the optional skill
- no label/issue/PR mutation
- no automatic agent-ready
- core skill inventory remains exactly the seven loop roles (+ prove)

## Operator use

From a trusted host session with repo access:

1. Load `optional-skills/templeton-architecture-review/SKILL.md`
2. Point it at a target repository
3. Review the temp HTML report
4. Grill one candidate
5. If useful, file the returned packet as `loop:spec-draft`
6. Continue with plan-review → agent-ready → build/review/merge
