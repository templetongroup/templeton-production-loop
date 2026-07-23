---
name: templeton-loop-review
description: Run a fresh-context, SHA-pinned, report-only Templeton review pass.
version: 1.0.0
license: MIT
---

# Templeton Loop Review

Use the fixed-edition CLI from a trusted host session:

```bash
templeton-loop run review --repo OWNER/REPO
```

For OpenClaw, also pass the configured `--agent AGENT_ID`. The host broker stages the PR head without `.git`, verifies a read-only air-gapped child runtime, validates normalized findings, checks evidence freshness, and owns the final GitHub comment and labels.

Required CI remains a host-side check equivalent to `gh pr checks NUMBER --required`. The broker pins each verdict to the current head using `Templeton Loop review of COMMIT_SHA`; a changed head invalidates prior approval. No required CI means `loop:needs-human-review`; failed required CI means `loop:changes-requested`.

Never push code, edit source, merge, deploy, publish, or expose credentials. Findings must describe a concrete failure scenario and source evidence; weak or stale evidence is rejected.
