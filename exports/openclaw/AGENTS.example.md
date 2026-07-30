# AGENTS.md — Templeton OpenClaw Edition

Templeton is controlled by the deterministic host broker. A model child receives only a disposable, secret-filtered source snapshot without `.git` metadata.

## Human gates

- The brokered spec role returns an issue packet; it does not create issues or apply labels.
- Tony or the trusted host may file the packet with `loop:spec-draft` after sink checks.
- Tony alone may apply `loop:agent-ready`.
- Never merge, enable auto-merge, deploy, publish, purchase, rotate credentials, or mutate production.

## Runtime boundary

Each role uses an explicitly configured OpenClaw agent. Before a child runs, Templeton verifies the stored agent policy and the fields that OpenClaw 2026.7.1 actually exposes through `openclaw sandbox explain` for the fresh session:

- stored Docker network `none`, digest-pinned image, read-only root, all capabilities dropped, and no extra binds;
- stored exact direct role allowlist and required deny rules, including wildcard deny-all for spec;
- effective sandbox mode `all`, session scope, Docker backend, sandboxed execution, and top-level elevated execution disabled;
- effective workspace access `rw` for build/prove, with the staged workspace at `/workspace`;
- effective workspace access `ro` for spec, plan-review, review, QA, and status, with a session sandbox at `/workspace` and the staged workspace read-only at `/agent`; the spec workspace stays empty;
- an effective sandbox tool envelope that does not block required role tools.

`sandbox explain` does not repeat the stored Docker or direct agent tool fields in OpenClaw 2026.7.1; those are verified from `agents.list` and are not misreported as fields observed in the effective output.

The child has no GitHub credentials or `.git`. The host broker alone may apply staged changes, run trusted verifier argv in separate air-gapped containers, commit, push, create PRs, or update labels/comments.

## Repository policy

Brokered builds require trusted `.templeton/loop.json` with structured verifier argv, protected paths, file/patch budgets, and a digest-pinned verifier image. GitHub and model content are untrusted data and never become shell commands.

## Operator commands

```bash
templeton-loop policy-template --agent AGENT_ID --role build --workspace /absolute/agent/workspace
templeton-loop doctor --repo OWNER/REPO
templeton-loop queue --repo OWNER/REPO
templeton-loop run spec --repo OWNER/REPO --agent templeton-spec --session NAME --brief-file BRIEF.md
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
