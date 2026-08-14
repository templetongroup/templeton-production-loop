# Matt Pocock productivity skills — selective incorporation

Date: 2026-08-14  
Product: Templeton Production Loop  
Upstream tree: https://github.com/mattpocock/skills/tree/main/skills/productivity  
Pin: `8b78b531ab965735c5dc74f6f7a219e1e37326df`

## Decision

Incorporate only the productivity components that improve Templeton Production Loop operator quality **without** weakening human gates or expanding outer-loop authority.

## Selected

| Upstream | Templeton wrapper | Why it helps |
| --- | --- | --- |
| `grill-me` / `grilling` | `optional-skills/templeton-grill` | Better pre-spec decision quality; already culturally aligned with guided interview. Templeton keeps **one question at a time**. |
| `handoff` | `optional-skills/templeton-handoff` | Clean fresh-session continuity; reduces context rot between builder/reviewer/operator turns. |
| `to-questionnaire` | `optional-skills/templeton-questionnaire` | Unblocks `loop:blocked` decisions that need one human outside the chat. |
| `wait-what` | `optional-skills/templeton-wait-what` | Low-cost clarification move when status/recommendation did not land. |
| `writing-for-agents` | `optional-skills/templeton-writing-for-agents` | Improves skill/AGENTS prose quality and pointer discipline. |

## Rejected for now

| Upstream | Why not |
| --- | --- |
| `teach` | Multi-session teaching-workspace product. Valuable elsewhere, not part of the production-loop kernel. |

## Boundaries

- Core skill inventory remains the seven authority roles (+ prove).
- Selected productivity skills ship as **optional-skills** + vendored third_party sources only.
- No automatic GitHub mutation, no agent-ready, no merge/deploy authority.
- `templeton-grill` intentionally differs from upstream multi-question frontier rounds: one decision per turn.

## Operator path

```text
grill / questionnaire / wait-what / handoff / writing-for-agents
  → human-gated issue/spec/review artifacts
  → normal Templeton Production Loop
```
