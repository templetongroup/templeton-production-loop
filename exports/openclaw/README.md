# Templeton Coding Loop — OpenClaw Edition

Version 0.2.0. Adapted from Alex Finn's MIT-licensed Finn-loop.

This bundle replaces Linear with GitHub Issues and runs bounded build/review passes through fresh OpenClaw session keys.

## Requirements

- OpenClaw with local workspace skills and `openclaw agent`
- Python 3.11+
- `git`
- GitHub CLI `gh`, authenticated for the target repository
- terminal/file tools enabled for the selected OpenClaw agents
- a GitHub repository with pull requests enabled
- required branch-protection CI if automated `loop:approved` verdicts are desired

Tested against OpenClaw 2026.7.1. No Linear account or connector is required.

## Recommended role split

Use different OpenClaw agents—or at minimum different fresh sessions—for these roles:

- **intake/spec agent:** `templeton-loop-spec` and `templeton-loop-status`
- **builder agent:** `templeton-loop-build`
- **reviewer agent:** `templeton-loop-review`

Do not let the builder reuse its own context as the reviewer. GitHub is the source of truth; A2A messages are coordination only.

## Install the CLI

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -e .
```

## Install skills

Install only the role each agent needs:

```bash
openclaw skills install ./skills-openclaw/templeton-loop-spec --agent INTAKE_AGENT --as templeton-loop-spec
openclaw skills install ./skills-openclaw/templeton-loop-status --agent INTAKE_AGENT --as templeton-loop-status
openclaw skills install ./skills-openclaw/templeton-loop-build --agent BUILDER_AGENT --as templeton-loop-build
openclaw skills install ./skills-openclaw/templeton-loop-review --agent REVIEWER_AGENT --as templeton-loop-review
```

Or preview/install all four on one pilot agent with the helper:

```bash
.venv/bin/templeton-loop install-skills --runtime openclaw --agent PILOT_AGENT
.venv/bin/templeton-loop install-skills --runtime openclaw --agent PILOT_AGENT --apply
```

Verify visibility:

```bash
openclaw skills check --agent PILOT_AGENT --json
```

Copy the relevant routing block from `AGENTS.example.md` into the target agent's `AGENTS.md`. If direct user requests enter through a central orchestrator, wire that intake surface too; installing private skills alone does not make the workflow operational.

## Initialize one target repository

```bash
.venv/bin/templeton-loop --json doctor --repo /path/to/repo
.venv/bin/templeton-loop init --repo /path/to/repo
.venv/bin/templeton-loop init --repo /path/to/repo --apply
```

## Use the loop

1. Ask the intake agent to use `templeton-loop-spec` for one small change.
2. Read the resulting GitHub issue and manually add `loop:agent-ready`.
3. Run one builder pass using a fresh OpenClaw session key:

```bash
.venv/bin/templeton-loop run build \
  --runtime openclaw \
  --agent BUILDER_AGENT \
  --repo /path/to/repo
```

4. Run one independent reviewer pass:

```bash
.venv/bin/templeton-loop run review \
  --runtime openclaw \
  --agent REVIEWER_AGENT \
  --repo /path/to/repo
```

5. A human reviews and merges the PR. Agents never merge or deploy.

Add `--dry-run` to preview the exact OpenClaw command without launching an agent.

## Watched mode

Only after proving one complete cycle in that repository:

```bash
.venv/bin/templeton-loop run build --runtime openclaw --agent BUILDER_AGENT --repo /path/to/repo --forever --interval 300
.venv/bin/templeton-loop run review --runtime openclaw --agent REVIEWER_AGENT --repo /path/to/repo --forever --interval 300
```

The runner enforces one same-host process lock per repository and role. GitHub assignment remains a cooperative, not atomic, cross-machine lock. Run only one builder per repository.

## Validate this bundle

```bash
python3.11 scripts/validate_bundle.py
shasum -a 256 -c MANIFEST.sha256
```

## Human gates

- A human applies `loop:agent-ready`.
- Required CI and a SHA-pinned independent review are required for `loop:approved`.
- A human makes the merge decision.
- Agents never auto-merge, deploy, publish, purchase, or mutate production.
- Two repair rounds are allowed; a third unresolved round becomes `loop:stuck`.
