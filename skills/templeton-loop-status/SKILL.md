---
name: templeton-loop-status
description: Inspect Templeton queue, policy, evidence, and recovery state without mutation.
version: 1.0.0
license: MIT
---

# Templeton Loop Status

Use read-only operator commands:

```bash
templeton-loop doctor --repo OWNER/REPO
templeton-loop queue --repo OWNER/REPO
templeton-loop health --repo OWNER/REPO
```

Summarize the next build/review candidate, trusted config presence, ledger integrity, outcomes, and incomplete runs. This skill must never mutate GitHub, source, labels, branches, configuration, deployments, or production. Report missing prerequisites and stale evidence explicitly; do not invent success.
