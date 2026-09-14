# Internal Production Loop Procedure

This is an internal least-authority broker mode of `templeton-build`, not a standalone operator skill. The explicit broker envelope and host policy determine authority.

# Templeton Loop Status

Use read-only operator commands:

```bash
templeton-loop doctor --repo OWNER/REPO
templeton-loop queue --repo OWNER/REPO
templeton-loop health --repo OWNER/REPO
```

Summarize the next build/review candidate, trusted config presence, ledger integrity, outcomes, and incomplete runs. This skill must never mutate GitHub, source, labels, branches, configuration, deployments, or production. Report missing prerequisites and stale evidence explicitly; do not invent success.