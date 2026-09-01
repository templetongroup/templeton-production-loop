# Templeton Production Loop

Templeton Production Loop is one model- and harness-neutral, human-gated software delivery system for bounded GitHub changes and independently verified artifact work. A deterministic host broker owns authority; least-authority model workers enter through one connector interface.

Version: **1.2.0**

## One loop, many models and harnesses

The workflow never forks by model or platform:

- Claude, Gemini, GLM, Kimi, GPT, and local models are routing choices.
- Claude Code, Codex, Gemini CLI, OpenClaw, Hermes, and future agent products are harnesses.
- A harness implements the strict [Templeton connector protocol](docs/connector-protocol.md); the workflow, evidence, labels, and human gates stay shared.
- Web, macOS, iOS, backend, and other delivery targets supply project-specific verifiers rather than separate loops.

Hermes and OpenClaw remain built-in adapters. The release generator can produce fixed-runtime installation archives from this canonical repository, but those archives are generated outputs—not separately maintained repositories.

## Operating model

```text
idea
  → trusted host supplies bounded, secret-filtered repository context
  → report-only guided interview
  → shared-understanding confirmation
  → GitHub issue contract
  → pre-approval plan review
  → designated human applies loop:agent-ready
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

Choose one runtime path:

- a trusted connector implementing `docs/connector-protocol.md` for any model or harness;
- Hermes Agent for the built-in Hermes adapter;
- OpenClaw 2026.7.1 or newer for the built-in OpenClaw adapter.

## Install from the canonical repository

```bash
git clone https://github.com/templetongroup/templeton-production-loop.git
cd templeton-production-loop
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install .
templeton-loop --help
```

Fixed-runtime archives remain available for installations that want an edition-pinned CLI. Validate an archive before installing it because installation and tests create files intentionally absent from its signed manifest.

## First-use sequence

### 1. Inspect the target repository

```bash
templeton-loop doctor --repo /path/to/repo
templeton-loop init --repo /path/to/repo
templeton-loop init --repo /path/to/repo --apply
```

### 2. Connect a harness or install built-in runtime skills

Any model or harness:

```bash
cp examples/connector.example.json ./connector.json
# Replace its id and absolute connector executable.
templeton-loop run build --repo /path/to/repo \
  --runtime connector --connector-config ./connector.json --dry-run
```

The connector owns provider-specific normalization. Templeton passes explicit proof-model routes through it, so Gemini, GLM, Kimi, Claude, GPT, or local models do not require workflow forks.

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

Connectors must prove their exact role, workspace, structured-output, fresh-session, isolation, network, credential, and verifier-image policy before every model call. Hermes uses a dedicated `HERMES_HOME` and Docker terminal policy. OpenClaw uses one explicit sandboxed agent per role. See `docs/connector-protocol.md`, the edition README, and `SECURITY.md`; runtime preflight fails closed if required settings are absent or drifted.

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

Add `--runtime connector --connector-config ./connector.json` in the canonical install, `--profile templeton` in the Hermes edition, or `--agent templeton-spec` in the OpenClaw edition. The final output is a sink-checked issue packet labeled only `loop:spec-draft`; the broker never files it. A trusted host may file that packet. Only the designated human operator may later apply `loop:agent-ready`.

### 4. Preview a role pass

```bash
# Any connector-backed harness
templeton-loop run build --repo /path/to/repo \
  --runtime connector --connector-config ./connector.json --dry-run

# Hermes edition
templeton-loop run build --repo /path/to/repo --profile templeton --dry-run

# OpenClaw edition
templeton-loop run review --repo /path/to/repo --agent AGENT_ID --dry-run
templeton-loop run qa --repo /path/to/repo --agent AGENT_ID --dry-run
```

Then run one bounded pass without `--dry-run`. Watched mode is explicit through `--forever --interval SECONDS`; it is never enabled by installation.

## Artifact proof runner

The canonical loop and both fixed editions can validate a trusted proof manifest, preview exact routing without model calls, and execute through a dedicated isolated runtime:

```bash
templeton-loop prove plan.json --lint
templeton-loop prove plan.json --dry-run
templeton-loop prove plan.json --run-root ./proof-runs

# Any connector-backed harness; strategy and worker model routes come from plan.json
templeton-loop prove plan.json --runtime connector \
  --connector-config ./connector.json --run-root /absolute/empty-proof-workspace

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

Build both fixed-runtime archives from the canonical repository:

```bash
python scripts/build_exports.py
```

After artifacts exist, verify that a fresh deterministic build is identical without replacing `dist/`:

```bash
python scripts/build_exports.py --check
```

`dist/SHA256SUMS` is a detached checksum list, not a self-authenticating signature. Obtain or approve its digest through an independent authenticated channel (for example, a reviewed repository commit, signed tag, or release attestation), then verify the archives **before** extraction or installation:

```bash
cd dist
shasum -a 256 -c SHA256SUMS       # macOS
# sha256sum -c SHA256SUMS          # Linux
```

Validate staged bundles:

```bash
python dist/stage/templeton-production-loop-hermes-v1.2.0/exports/validate_bundle.py
python dist/stage/templeton-production-loop-openclaw-v1.2.0/exports/validate_bundle.py
```

The validator rejects missing, extra, altered, unsafe, or symlinked files and verifies `MANIFEST.json`, `MANIFEST.sha256`, version, runtime identity, skill inventory, and safety-contract markers. Internal manifests detect accidental or uncoordinated changes; they are not authenticity proofs. A `SHA256SUMS` file downloaded beside the archives is also insufficient unless its digest or signature was authenticated separately. For an authenticated repository checkout, you may additionally pin the externally reviewed manifest digest with `--expected-manifest-sha256 DIGEST`.

## Development verification

```bash
python -m pytest -q
python -m compileall -q templeton_loop tests scripts
python scripts/build_exports.py
git diff --check
```

## Graph patterns

Inner Proof Runner graph authoring and post-pilot DAG primitives are documented in:

- `docs/research/2026-08-14-graph-patterns-in-proof-runner.md`

Use those patterns to sharpen task fan-out, independent lenses, and verifier anchors. They do not replace the outer GitHub/human-governance loop.

## Optional architecture review

For codebase deepening opportunities before filing work into the loop, use the optional report-only helper:

- `optional-skills/templeton-architecture-review/SKILL.md`
- vendored upstream sources: `third_party/mattpocock-skills/`
- research note: `docs/research/2026-08-14-mattpocock-improve-codebase-architecture.md`

This helper adapts Matt Pocock's MIT-licensed `improve-codebase-architecture` flow: scan hot spots, produce a temp HTML candidate report, grill one candidate, and return a `loop:spec-draft` issue packet for human filing. It is not one of the seven outer-loop authority roles and never applies `loop:agent-ready`, edits source, or mutates GitHub state.

## Optional productivity helpers

Selected Matt Pocock productivity skills are vendored and wrapped as optional operator helpers:

- `optional-skills/templeton-grill` — one-question-at-a-time design interview
- `optional-skills/templeton-handoff` — temp-dir secret-redacted session handoff
- `optional-skills/templeton-questionnaire` — blocked-decision questionnaire for one recipient
- `optional-skills/templeton-wait-what` — plain re-pitch when a status update did not land
- `optional-skills/templeton-writing-for-agents` — agent-doc/skill writing guidance

Upstream sources: `third_party/mattpocock-skills/productivity/`  
Selection note: `docs/research/2026-08-14-mattpocock-productivity-selection.md`  
Not incorporated: `teach` and any automatic agent-ready path.

## Governance and provenance

Only the designated human operator applies `loop:agent-ready`. An authorized human may review the resulting PR and evidence and merge. Installation does not add hooks, automatic updates, cron jobs, deployments, or production credentials.

Templeton Production Loop is MIT-licensed original Templeton work adapted from Alex Finn's MIT-licensed Finn-loop concepts. Its guided-interview behavior adapts bounded MIT-licensed concepts from Matt Pocock's `grill-me`, `grilling`, and `grill-with-docs` skills with attribution. Its optional architecture and selected productivity helpers adapt `improve-codebase-architecture`, `codebase-design`, `grill-me`/`grilling`, `handoff`, `to-questionnaire`, `wait-what`, and `writing-for-agents` under the same MIT attribution model. Ringer and gstack were reviewed as product/research inputs; no Ringer- or gstack-derived source, skill prose, templates, schemas, tests, or assets are included. See `PROVENANCE.md` and `THIRD_PARTY_NOTICES.md` in generated editions.

CLI and Python import names remain `templeton-loop` / `templeton_loop` for compatibility.
