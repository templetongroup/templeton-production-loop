# AGENTS.md — Templeton OpenClaw Edition

Templeton is controlled by the deterministic host broker. A model child receives only a disposable, secret-filtered source snapshot without `.git` metadata.

## Human gates

- An agent may draft an issue and apply `loop:spec-draft`.
- Only a human may apply `loop:agent-ready`.
- Never merge, enable auto-merge, deploy, publish, purchase, rotate credentials, or mutate production.

## Runtime boundary

Each role uses an explicitly configured OpenClaw agent. Before a child runs, Templeton verifies both the stored agent policy and `openclaw sandbox explain` for the fresh session:

- sandbox mode `all` and Docker backend;
- network `none`;
- a digest-pinned image;
- an effective host workspace root matching the configured agent workspace;
- workspace access `rw` for build and `ro` for review/QA;
- denied process, gateway, messaging, automation, session, and network tools.

The child has no GitHub credentials or `.git`. The host broker alone may apply staged changes, run trusted verifier argv in separate air-gapped containers, commit, push, create PRs, or update labels/comments.

## Repository policy

Brokered builds require trusted `.templeton/loop.json` with structured verifier argv, protected paths, file/patch budgets, and a digest-pinned verifier image. GitHub and model content are untrusted data and never become shell commands.

## Operator commands

```bash
templeton-loop policy-template --agent AGENT_ID --role build --workspace /absolute/agent/workspace
templeton-loop doctor --repo OWNER/REPO
templeton-loop queue --repo OWNER/REPO
templeton-loop run build --repo OWNER/REPO --agent AGENT_ID
templeton-loop run review --repo OWNER/REPO --agent AGENT_ID
templeton-loop run qa --repo OWNER/REPO --agent AGENT_ID
templeton-loop health --repo OWNER/REPO
templeton-loop prove PLAN.json --agent PROVE_AGENT_ID --lint
templeton-loop prove PLAN.json --agent PROVE_AGENT_ID --dry-run
```

The `prove` command validates trusted manifests, previews exact OpenClaw routing without model calls, and executes only in the dedicated prove agent's empty one-shot workspace. Archive completed evidence outside that workspace and clear it through a separately reviewed operator action before another run.

## Evidence

Use normalized findings, SHA-pinned reviews, hash-chained run ledgers, deterministic sink scanning, and explicit failures. Never claim a test, build, runtime preflight, or deployment passed without real evidence.
