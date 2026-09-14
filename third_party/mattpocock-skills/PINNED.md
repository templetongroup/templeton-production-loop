# Pinned Matt Pocock skill provenance

Upstream: https://github.com/mattpocock/skills
Tree pin: `8b78b531ab965735c5dc74f6f7a219e1e37326df`

## Selected upstream paths

### Engineering
- `skills/engineering/improve-codebase-architecture`
- `skills/engineering/codebase-design`

### Productivity
- `skills/productivity/grill-me`
- `skills/productivity/grilling`
- `skills/productivity/handoff`
- `skills/productivity/to-questionnaire`
- `skills/productivity/wait-what`
- `skills/productivity/writing-for-agents`

## Current repository treatment

The upstream skill source files and former `optional-skills/templeton-*` wrappers were removed in Templeton Production Loop v1.2 when their selected procedures were consolidated into `skills/templeton-build/references/`.

This directory now retains only compact provenance records:

- upstream MIT `LICENSE`;
- this exact commit/path record;
- `UPSTREAM_FILES.json`, the historical source-file digest inventory.

No skill in this directory is installed or exported. `teach`, setup plugins, triage/implement/to-tickets, and automatic agent-ready behavior remain excluded. The consolidated Templeton procedures cannot bypass broker role policies, human merge authority, or deployment approval.
