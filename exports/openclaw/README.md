# Templeton Production Loop — OpenClaw Edition

Version **1.1.0**. This standalone repository is fixed to OpenClaw; the CLI has no `--runtime` option. Its coding-loop roles and live `prove` command execute through explicit OpenClaw adapters. Live proof requires a dedicated `prove` agent and an existing, empty, non-symlink one-shot workspace; preflight and post-preflight checks fail closed on policy mismatch or workspace mutation.

## Requirements

- Python 3.11+
- OpenClaw 2026.7.1 or newer
- Git and authenticated GitHub CLI
- Docker
- a trusted worker image pinned as `name@sha256:<64 lowercase hex characters>`

## Install and verify

If you received this source as an archive, authenticate its archive digest against a separately reviewed commit, signed tag, attestation, or secure release channel **before extraction**. `MANIFEST.json` and `MANIFEST.sha256` detect internal drift but are not authenticity proofs.

```bash
python3.11 exports/validate_bundle.py
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install .
templeton-loop --help
```

Expected validator prefix: `TEMPLETON_LOOP_BUNDLE_OK runtime=openclaw`.
Run the validator before installation or tests create unmanifested build/cache files.

## Install skills

Install the bundled skills into each dedicated OpenClaw agent that needs them:

```bash
templeton-loop install-skills --agent AGENT_ID
templeton-loop install-skills --agent AGENT_ID --apply
```

Installed roles:

- `templeton-loop-spec`
- `templeton-loop-plan-review`
- `templeton-loop-build`
- `templeton-loop-review`
- `templeton-loop-qa`
- `templeton-loop-status`
- `templeton-loop-prove`

For a new project or material change, use `templeton-loop run spec`; never invoke the installed spec skill directly. On the first turn, the broker prepares and secret-scans a bounded packet from current issue metadata, tracked repository guidance, the trusted host's brief/research file, and explicit `--include` files. Every turn creates a fresh OpenClaw session, verifies the explicit wildcard deny-all spec policy (`tools.deny: ["*"]`) and empty read-only workspace, preserves transcript state under Git's `templeton-loop/spec/` metadata path, and accepts one trusted-host answer through `--answer-file`. The child never gets research tools, GitHub mutation capability, deployment access, or arbitrary workspace reads.

The state file contains bounded product context and interview history. It is mode-restricted, excluded from source staging and release archives, and remains confidential local operator data.

## Create least-authority role policies

Generate one policy entry per role and replace the image placeholder with a digest-pinned trusted image:

```bash
REPO=/absolute/path/to/repo
AGENT_ID=templeton-build
templeton-loop --json policy-template \
  --agent "$AGENT_ID" \
  --role build \
  --workspace "$REPO/.git/templeton-loop/openclaw-workspaces/$AGENT_ID" \
  --image 'YOUR_IMAGE@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
  > ./templeton-build-agent.json
```

Repeat for `spec`, `plan-review`, `review`, `qa`, `status`, and `prove`. The dedicated spec workspace must exist and remain empty. Add each generated object to `agents.list` using your normal reviewed OpenClaw configuration procedure, validate the configuration, restart/reload only as required by your deployment, then inspect the effective session policy:

```bash
openclaw config validate
openclaw sandbox explain --agent templeton-build --session agent:templeton-build:main --json
```

Templeton fails closed unless the stored agent policy proves:

- `sandbox.mode=all`, `scope=session`, Docker backend;
- digest-pinned image, `network=none`, read-only root, all capabilities dropped, no extra binds;
- exact role tool allowlist and required deny rules;
- elevated execution disabled.

The fresh `sandbox explain` output must independently prove `mode=all`, `scope=session`, Docker backend, sandboxed execution, top-level elevated execution disabled, a sandbox tool envelope that does not block required role tools, and exact staged workspace routing. Writable roles map the staged workspace to `/workspace`; read-only roles use a session sandbox at `/workspace` and mount the staged workspace read-only at `/agent`. OpenClaw 2026.7.1 does not expose the stored Docker hardening or direct agent tool policy in this command, so Templeton verifies those fields from `agents.list` without claiming they appeared in the effective explanation.

The gateway remains trusted host software. Only child tool execution is sandboxed. Keep GitHub/cloud/registry/deployment credentials out of the role agents. The `run` broker independently governs `spec`, `build`, `review`, and `qa`; the `prove` command governs proof execution. `plan-review` and `status` remain direct, human-invoked report roles. The spec broker supplies the bounded packet in the prompt, verifies policy before every fresh model session, requires an empty workspace, and hands back a sink-checked issue packet without any GitHub mutation phase.

## Outer GitHub loop

```bash
templeton-loop doctor --repo /path/to/repo
templeton-loop init --repo /path/to/repo --apply

templeton-loop run spec --repo /path/to/repo --agent templeton-spec \
  --session new-product --brief-file ./brief-and-research.md --include src/relevant.py
templeton-loop run spec --repo /path/to/repo --agent templeton-spec \
  --session new-product --answer-file ./answer.md
templeton-loop run spec --repo /path/to/repo --agent templeton-spec \
  --session new-product --confirm
templeton-loop run build --repo /path/to/repo --agent templeton-build --dry-run
templeton-loop run review --repo /path/to/repo --agent templeton-review --dry-run
templeton-loop run qa --repo /path/to/repo --agent templeton-qa --dry-run
```

Remove `--dry-run` for one bounded pass. Watched mode is explicit:

```bash
templeton-loop run build --repo /path/to/repo --agent templeton-build --forever --interval 300
```

Tony must approve the issue contract and alone may apply `loop:agent-ready`. Tony or a trusted host may file the approved packet with `loop:spec-draft`; Tony or another authorized human may merge. Agents cannot merge, deploy, publish, purchase, or mutate production.

## Artifact proof runner

Review every proof manifest as trusted executable configuration. Configure a dedicated `prove` agent with `workspaceAccess=rw`; its workspace must be outside the manifest's `source_root` and exactly equal `--run-root`. Live proof workspaces are one-shot: they must be empty before execution, then archived outside the agent workspace and cleared before another run. This prevents a later model session from reaching prior-run evidence.
The shipped example is runtime-neutral and intentionally omits Hermes-only `profile` overrides.

```bash
templeton-loop prove examples/proof-manifest.json --agent templeton-prove --lint
templeton-loop prove examples/proof-manifest.json --agent templeton-prove --dry-run
templeton-loop prove examples/proof-manifest.json \
  --agent templeton-prove \
  --run-root /absolute/openclaw/proof-workspace
```

## Evidence and operations

The deterministic host broker owns GitHub effects. Models receive filtered staged source and bounded role context. Build changes are derived from an exact tree comparison; review and QA use clean report-only snapshots.

Evidence includes runtime policy proof, model routes, source inventories, normalized findings, SHA-pinned review identity, verifier outcomes, freshness, capability coverage, and health summaries in a hash-chained ledger.

No hooks, cron jobs, automatic updates, deployments, or credentials are installed. See `SECURITY.md`, `PROVENANCE.md`, and `AGENTS.example.md`.
