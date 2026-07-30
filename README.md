# Templeton Coding Loop

Templeton Coding Loop is a human-gated software delivery system for bounded GitHub changes and independently verified artifact work. It combines deterministic host-side control with least-authority model workers for Hermes Agent and OpenClaw.

Version: **1.1.0**

## Editions

The release generator produces two standalone private repositories:

- `templeton-coding-loop-hermes` — Hermes roles plus the artifact proof runner.
- `templeton-coding-loop-openclaw` — OpenClaw-native coding-loop roles plus live artifact proof execution through an explicit adapter and a dedicated empty one-shot workspace.

Each generated repository has a fixed runtime identity. Its installed CLI does not expose a runtime switch.

## Operating model

```text
idea
  → trusted host supplies bounded, secret-filtered repository context
  → report-only guided interview
  → shared-understanding confirmation
  → GitHub issue contract
  → pre-approval plan review
  → Tony applies loop:agent-ready
  → isolated staged build
  → deterministic host validation and branch/PR effects
  → fresh SHA-pinned review
  → report-only QA
  → human merge
```

The deterministic broker owns GitHub credentials and effects. Child agents receive only filtered source, bounded task context, and role-specific tools inside air-gapped Docker sandboxes. They cannot merge, deploy, publish, purchase, mutate production, or access operator credentials.

## Requirements

Common:

- Python 3.11+
- Git
- GitHub CLI authenticated as the intended operator
- Docker with a trusted worker image pinned by SHA-256 digest
- a target GitHub repository with required CI configured

Runtime-specific:

- Hermes Agent for the Hermes edition
- OpenClaw 2026.7.1 or newer for the OpenClaw edition

## Install from a standalone repository

```bash
python3.11 exports/validate_bundle.py
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install .
templeton-loop --help
```

Validate before installing: installation and tests create files that are intentionally absent from the signed bundle manifest.

## First-use sequence

### 1. Inspect the target repository

```bash
templeton-loop doctor --repo /path/to/repo
templeton-loop init --repo /path/to/repo
templeton-loop init --repo /path/to/repo --apply
```

### 2. Install runtime skills

Hermes edition:

```bash
templeton-loop install-skills --profile templeton
templeton-loop install-skills --profile templeton --apply
```

OpenClaw edition:

```bash
templeton-loop install-skills --agent AGENT_ID
templeton-loop install-skills --agent AGENT_ID --apply
```

### 3. Configure least-authority workers

Hermes uses a dedicated `HERMES_HOME` and Docker terminal policy. OpenClaw uses one explicit sandboxed agent per role. See the edition README and `SECURITY.md`; runtime preflight fails closed if required settings are absent or drifted.

For a new project or material change, use the brokered `run spec` flow—never invoke the installed spec skill directly. The host reads current GitHub issue metadata and tracked repository files, combines them with a trusted brief/research file, rejects sensitive paths and secret-positive or oversized payloads, and then invokes the report-only role with the exact runtime policy. Each invocation performs one stateful interview turn, verifies runtime policy again, and scans the model result before preserving it under Git's `templeton-loop/spec/` metadata path (`.git/templeton-loop/spec/` in a normal checkout, or the linked worktree's administrative directory).

Spec state contains bounded, secret-filtered product context and interview history. It is mode-restricted, stays below `.git`, is excluded from source staging and release archives, and must still be handled as confidential local operator data.

```bash
# First turn; add --include for relevant tracked UTF-8 source/test files.
templeton-loop run spec --repo /path/to/repo --session new-product \
  --brief-file ./brief-and-research.md --include src/relevant.py --dry-run
templeton-loop run spec --repo /path/to/repo --session new-product \
  --brief-file ./brief-and-research.md --include src/relevant.py

# One answer or correction per later turn.
templeton-loop run spec --repo /path/to/repo --session new-product \
  --answer-file ./answer.md

# Only after reviewing the returned shared-understanding summary.
templeton-loop run spec --repo /path/to/repo --session new-product --confirm
```

Add `--profile templeton` in the Hermes edition or `--agent templeton-spec` in the OpenClaw edition. The final output is a sink-checked issue packet labeled only `loop:spec-draft`; the broker never files it. Tony or the trusted host may file that packet. Tony alone may later apply `loop:agent-ready`.

### 4. Preview a role pass

```bash
# Hermes edition
templeton-loop run build --repo /path/to/repo --profile templeton --dry-run

# OpenClaw edition
templeton-loop run review --repo /path/to/repo --agent AGENT_ID --dry-run
templeton-loop run qa --repo /path/to/repo --agent AGENT_ID --dry-run
```

Then run one bounded pass without `--dry-run`. Watched mode is explicit through `--forever --interval SECONDS`; it is never enabled by installation.

## Artifact proof runner

Both editions can validate a trusted proof manifest, preview exact routing without model calls, and execute through a dedicated isolated runtime:

```bash
templeton-loop prove plan.json --lint
templeton-loop prove plan.json --dry-run
templeton-loop prove plan.json --run-root ./proof-runs

# OpenClaw edition: run root must be the configured, existing, empty prove-agent workspace
templeton-loop prove plan.json --agent templeton-prove --lint
templeton-loop prove plan.json --agent templeton-prove --dry-run
templeton-loop prove plan.json --agent templeton-prove --run-root /absolute/openclaw/empty-proof-workspace
```

Execution performs one strategy pass, concurrent isolated workers, independent containerized verification, and the manifest's bounded repair count. Every attempt and verifier result is preserved in a hash-chained ledger with a sealed digest inventory of artifacts, verifier output, and reports. The original source tree is inventoried before and after and is never the worker workspace. OpenClaw refuses non-empty run roots, preventing a later session from reaching prior-run evidence; archive and clear a completed workspace only through a separately reviewed operator action.

## Evidence

Runs write bounded, redacted evidence under the target repository's Git metadata directory or the selected proof run root. Evidence includes:

- run and policy identity;
- model route and provider-neutral outcome;
- staged-tree and source inventories;
- normalized findings and applicability;
- verifier argv, exit code, duration, and bounded output;
- retry lineage;
- evidence freshness;
- capability/eval coverage and health summaries;
- append-only hash-chain fields.

Evidence is proof of what the runner observed, not authority to merge or deploy.

## Release integrity

Build both editions:

```bash
python scripts/build_exports.py
```

After artifacts exist, verify that a fresh deterministic build is identical without replacing `dist/`:

```bash
python scripts/build_exports.py --check
```

`dist/SHA256SUMS` is a detached checksum list, not a self-authenticating signature. Obtain or approve its digest through an independent authenticated channel (for example, a reviewed private-repository commit, signed tag, or release attestation), then verify the archives **before** extraction or installation:

```bash
cd dist
shasum -a 256 -c SHA256SUMS       # macOS
# sha256sum -c SHA256SUMS          # Linux
```

Validate staged bundles:

```bash
python dist/stage/templeton-coding-loop-hermes-v1.1.0/exports/validate_bundle.py
python dist/stage/templeton-coding-loop-openclaw-v1.1.0/exports/validate_bundle.py
```

The validator rejects missing, extra, altered, unsafe, or symlinked files and verifies `MANIFEST.json`, `MANIFEST.sha256`, version, runtime identity, skill inventory, and safety-contract markers. Internal manifests detect accidental or uncoordinated changes; they are not authenticity proofs. A `SHA256SUMS` file downloaded beside the archives is also insufficient unless its digest or signature was authenticated separately. For an authenticated repository checkout, you may additionally pin the externally reviewed manifest digest with `--expected-manifest-sha256 DIGEST`.

## Development verification

```bash
python -m pytest -q
python -m compileall -q templeton_loop tests scripts
python scripts/build_exports.py
git diff --check
```

## Governance and provenance

Tony alone applies `loop:agent-ready`. Tony or another authorized human may review the resulting PR and evidence and merge. Installation does not add hooks, automatic updates, cron jobs, deployments, or production credentials.

Templeton Coding Loop is MIT-licensed original Templeton work adapted from Alex Finn's MIT-licensed Finn-loop concepts. Its guided-interview behavior adapts bounded MIT-licensed concepts from Matt Pocock's `grill-me`, `grilling`, and `grill-with-docs` skills with attribution. Ringer and gstack were reviewed as product/research inputs; no Ringer- or gstack-derived source, skill prose, templates, schemas, tests, or assets are included. See `PROVENANCE.md` and `THIRD_PARTY_NOTICES.md` in generated editions.
