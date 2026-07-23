# Templeton Coding Loop — Hermes Edition

Version **1.0.0**. This standalone repository is fixed to Hermes; the CLI has no `--runtime` option.

## Requirements

- Python 3.11+
- Hermes Agent
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

Expected validator prefix: `TEMPLETON_LOOP_BUNDLE_OK runtime=hermes`.
Run the validator before installation or tests create unmanifested build/cache files.

## Dedicated least-authority Hermes runtime

Do not run model workers through your everyday Hermes profile. Create a dedicated runtime home containing this exact marker:

```json
{"product":"templeton-coding-loop","schema":1}
```

Save it as `$HERMES_HOME/TEMPLETON_RUNTIME.json`. Configure that Hermes home with a model provider and the following terminal policy:

```yaml
terminal:
  backend: docker
  docker_image: "YOUR_IMAGE@sha256:YOUR_DIGEST"
  docker_mount_cwd_to_workspace: true
  docker_network: false
  docker_forward_env: []
  env_passthrough: []
  container_persistent: false
  docker_run_as_host_user: true
  docker_volumes: []
  shell_init_files: []
  docker_extra_args:
    - "--read-only"
    - "--cap-drop=ALL"
    - "--security-opt=no-new-privileges"
```

Templeton checks the effective Hermes config and Docker daemon before the first model call. It does not forward GitHub, cloud, registry, deployment, or host credential environment variables into the worker container.

Build and proof roles preserve this verified profile because they require the air-gapped Docker terminal. Review, QA, spec, plan-review, and status roles are report-only: they receive the bounded issue/PR/diff context in the prompt and run with Hermes safe mode plus a `todo`-only tool allowlist. Those roles receive no terminal, file, code-execution, web, messaging, session, or host-write tool.

The worker image must contain the language runtimes and test tools your tasks require. Pin the immutable digest, not a mutable tag.

## Install skills

```bash
templeton-loop install-skills --profile templeton
templeton-loop install-skills --profile templeton --apply
```

Installed roles:

- `templeton-loop-spec`
- `templeton-loop-plan-review`
- `templeton-loop-build`
- `templeton-loop-review`
- `templeton-loop-qa`
- `templeton-loop-status`
- `templeton-loop-prove`

## Outer GitHub loop

```bash
templeton-loop doctor --repo /path/to/repo
templeton-loop init --repo /path/to/repo --apply

templeton-loop run build --repo /path/to/repo --profile templeton --dry-run
templeton-loop run review --repo /path/to/repo --profile templeton --dry-run
templeton-loop run qa --repo /path/to/repo --profile templeton --dry-run
```

Remove `--dry-run` for one bounded pass. Watched mode is explicit:

```bash
templeton-loop run build --repo /path/to/repo --profile templeton --forever --interval 300
```

Tony or another authorized human must create/approve the issue contract, apply `loop:agent-ready`, and merge. Agents cannot merge, deploy, publish, purchase, or mutate production.

## Artifact proof runner

Review every manifest as trusted executable configuration, especially source paths, artifact paths, models/providers, verifier argv, timeouts, and retry limits.
The shipped example is runtime-neutral and uses the active Hermes profile. A manifest `profile` override is optional for Hermes and unsupported by the OpenClaw edition.

```bash
templeton-loop prove examples/proof-manifest.json --lint
templeton-loop prove examples/proof-manifest.json --dry-run
templeton-loop prove examples/proof-manifest.json --run-root ./proof-runs
```

The runner copies filtered sources into disposable snapshots, performs one strategy call, runs workers in isolated air-gapped Hermes containers, verifies artifacts in fresh air-gapped Docker containers, preserves every attempt, and rejects source mutation. Verifier commands are argv arrays and never run through a shell.

## Evidence and operations

- Outer-loop evidence is stored under the target repository's `.git/templeton-loop/` area.
- Proof evidence is stored under the selected run root.
- Logs and sink payloads are size-bounded and secret-checked.
- Blocked secret-positive records never retain the raw payload.
- No hooks, cron jobs, automatic updates, deployments, or credentials are installed.

See `SECURITY.md`, `PROVENANCE.md`, and `AGENTS.example.md`.
