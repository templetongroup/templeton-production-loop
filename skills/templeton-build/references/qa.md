# Internal Production Loop Procedure

This is an internal least-authority broker mode of `templeton-build`, not a standalone operator skill. The explicit broker envelope and host policy determine authority.

# Templeton Loop QA

QA is report-only:

```bash
templeton-loop run qa --repo OWNER/REPO
```

For OpenClaw, also pass the configured `--agent AGENT_ID`. The host broker provides a secret-filtered, read-only snapshot without `.git`, verifies the effective air-gapped sandbox, validates returned scenarios and findings, records evidence freshness, and writes the result to the run ledger.

Do not edit source, push, comment directly, relabel, merge, deploy, publish, purchase, or change production. Browser or device checks are allowed only when the trusted host explicitly supplies an approved, non-production test target.