# Templeton Coding Loop — Hermes Edition

Version 0.2.0. Adapted from Alex Finn's MIT-licensed Finn-loop.

This bundle replaces Linear with GitHub Issues and runs bounded build/review passes as fresh Hermes sessions.

## Requirements

- Hermes Agent with profile support and worktree mode
- Python 3.11+
- `git`
- GitHub CLI `gh`, authenticated for the target repository
- a GitHub repository with pull requests enabled
- required branch-protection CI if automated `loop:approved` verdicts are desired

No Linear account or connector is required.

## Install

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -e .

# Preview the skill destinations
.venv/bin/templeton-loop install-skills --runtime hermes --profile YOUR_PROFILE

# Install the four skills
.venv/bin/templeton-loop install-skills --runtime hermes --profile YOUR_PROFILE --apply

# Confirm they are visible
hermes --profile YOUR_PROFILE skills list
```

Reset/restart an already-running Hermes session if it must see newly installed skills immediately.

## Initialize one target repository

```bash
# Read-only preflight
.venv/bin/templeton-loop --json doctor --repo /path/to/repo

# Preview nine GitHub label operations
.venv/bin/templeton-loop init --repo /path/to/repo

# Apply labels
.venv/bin/templeton-loop init --repo /path/to/repo --apply
```

## Use the loop

1. Ask the profile to use `templeton-loop-spec` for one small change.
2. Read the resulting GitHub issue and manually add `loop:agent-ready`.
3. Run one builder pass:

```bash
.venv/bin/templeton-loop run build \
  --runtime hermes \
  --profile YOUR_PROFILE \
  --repo /path/to/repo
```

4. Run one fresh reviewer pass:

```bash
.venv/bin/templeton-loop run review \
  --runtime hermes \
  --profile YOUR_PROFILE \
  --repo /path/to/repo
```

5. A human reviews and merges the PR. Agents never merge or deploy.

Preview either worker without launching it by adding `--dry-run`.

## Watched mode

Only after proving one complete cycle in that repository:

```bash
.venv/bin/templeton-loop run build --runtime hermes --profile YOUR_PROFILE --repo /path/to/repo --forever --interval 300
.venv/bin/templeton-loop run review --runtime hermes --profile YOUR_PROFILE --repo /path/to/repo --forever --interval 300
```

Run one builder process per repository. Keep build and review as separate fresh sessions. Never schedule the interactive spec role.

## Validate this bundle

```bash
python3.11 scripts/validate_bundle.py
shasum -a 256 -c MANIFEST.sha256
```

## Human gates

- A human applies `loop:agent-ready`.
- Required CI and a SHA-pinned fresh review are required for `loop:approved`.
- A human makes the merge decision.
- Agents never auto-merge, deploy, publish, purchase, or mutate production.
- Two repair rounds are allowed; a third unresolved round becomes `loop:stuck`.
