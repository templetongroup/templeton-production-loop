# Internal Production Loop Procedure

This is an internal least-authority broker mode of `templeton-build`, not a standalone operator skill. The explicit broker envelope and host policy determine authority.

# Templeton Loop Build

Use the fixed-edition CLI from a trusted host session:

```bash
templeton-loop doctor --repo OWNER/REPO
templeton-loop run build --repo OWNER/REPO
```

For OpenClaw, also pass the configured `--agent AGENT_ID`. The deterministic host broker selects one approved issue or repair PR, stages a secret-filtered tree without `.git`, verifies the runtime sandbox, invokes the child, validates changed paths and patch budgets, runs trusted argv verifiers in an air-gapped pinned container, then owns commits, pushes, labels, and PR creation.

Children never receive GitHub credentials and never run Git, GitHub, verifier, or deployment effects. Never merge, enable auto-merge, deploy, publish, purchase, or mutate production.

A PR may receive at most two builder repair rounds. Each repair PR preserves the original PR's single `Closes`/`Fixes`/`Resolves` issue contract and receives `loop:awaiting-review`; the superseded PR is removed from the active repair queue. The broker records durable repair markers; before a third attempt it applies `loop:stuck` and `loop:needs-human-review`, removes `loop:changes-requested`, and stops.