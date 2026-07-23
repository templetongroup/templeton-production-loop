# Templeton Coding Loop

A human-gated software factory adapted from [Finn-loop](https://github.com/finna/Finn-loop) for the tools Tony and Nikki already use:

**idea → GitHub issue contract → Tony applies `loop:agent-ready` → Hermes/Nikki builds in an isolated worktree → a fresh Hermes reviewer posts a SHA-pinned verdict → Tony merges.**

Linear is removed. GitHub Issues are the durable specification, approval queue, block state, and dependency surface. GitHub PRs remain the code-review and CI surface. Hermes supplies skills, isolated worktrees, fresh sessions, tools, delegation, session logs, and optional scheduling.

## What was retained from Finn-loop

- spec quality is the bottleneck;
- stable acceptance criteria (`AC-N`) and binding non-goals (`NG-N`);
- one issue per PR;
- an explicit human approval label before agents may build;
- cooperative claim state;
- builder and reviewer run in separate contexts;
- review evidence is pinned to the exact PR head SHA;
- required CI is mandatory for automated approval;
- blocked and escalated work leaves the automated queue;
- agents never merge or deploy;
- bounded repair rounds prevent infinite agent arguments.

## Templeton tool mapping

| Finn-loop | Templeton loop |
| --- | --- |
| Linear issue | GitHub issue |
| Linear `agent-ready` | GitHub `loop:agent-ready`, applied only by Tony/human |
| Linear assignee + workflow state | GitHub assignee + `loop:building` |
| Linear blocked relation | `loop:blocked` plus explicit `Blocked by #N` issue contract |
| Claude `/loop` | `templeton-loop run ...` spawning one fresh Hermes session per pass |
| Claude Code skill | Hermes profile skill |
| Claude isolated session | Hermes `chat --worktree` fresh session |
| Separate review loop | Fresh Hermes reviewer session, exact SHA pinned |
| Slack control plane | Telegram/Hermes status output now; no shadow state |

## Components

- `templeton-loop-spec` — interactive repository research and GitHub issue drafting.
- `templeton-loop-build` — one repair or one issue-to-PR build pass.
- `templeton-loop-review` — one fresh-context, SHA-pinned PR review pass.
- `templeton-loop-status` — read-only operator queue and action list.
- `templeton-loop` CLI — doctor, label bootstrap, deterministic queue selection, runtime-aware skill install, and bounded/persistent Hermes or OpenClaw runners.
- `skills/` — Hermes-native role skills.
- `skills-openclaw/` — OpenClaw-native role skills with explicit git-worktree isolation.
- `scripts/build_exports.py` — creates shareable, checksummed Hermes and OpenClaw ZIP bundles.

## Safety boundaries

- `init` and `install-skills` are dry-run unless `--apply` is present.
- A runner defaults to one pass. Persistent mode requires `--forever`.
- One local builder process per repository is enforced with a file lock.
- Each agent pass starts in a Hermes isolated git worktree.
- The runner re-reads GitHub before selecting work; the skill re-reads before mutation.
- Missing required CI prevents `loop:approved`.
- Builders get two repair rounds; the third unresolved review becomes `loop:stuck` + `loop:needs-human-review`.
- No loop role may merge, auto-merge, deploy, publish, purchase, or mutate production.
- GitHub assignment is a cooperative lock, not an atomic distributed lease. Run only one builder loop per repository.

## Install the CLI

```bash
cd /Users/ai/projects/templeton/coding-loop
/Users/ai/.hermes/hermes-agent/venv/bin/python -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/templeton-loop --help
```

The explicit interpreter uses the installed Hermes Python 3.11 runtime; macOS `/usr/bin/python3` may still be Python 3.9 and is intentionally not used.

Install the four skills into Nikki's Hermes profile:

```bash
.venv/bin/templeton-loop install-skills --profile nikki
.venv/bin/templeton-loop install-skills --profile nikki --apply
```

The first command previews paths. The second changes profile-local state. Restart/reset the Nikki session after installing if an already-running session must see the new skills.

## Initialize a target repository

From any GitHub-backed local clone:

```bash
# Read-only preflight
/path/to/coding-loop/.venv/bin/templeton-loop --json doctor --repo .

# Preview label commands
/path/to/coding-loop/.venv/bin/templeton-loop init --repo .

# Create/update the loop labels
/path/to/coding-loop/.venv/bin/templeton-loop init --repo . --apply

# Read-only queue
/path/to/coding-loop/.venv/bin/templeton-loop --json queue --repo .
```

`doctor` reports GitHub authentication, default branch, dirty-tree state, labels, and required branch checks. A repository with no required CI can use the loop, but every PR remains `loop:needs-human-review` rather than receiving `loop:approved`.

## Daily use

### 1. Create a spec

Ask Nikki in the repository context to use `templeton-loop-spec`. She researches first, interviews for genuine product decisions, shows the full contract, and creates a GitHub issue carrying only `loop:spec-draft` after approval.

Tony reads the issue and manually adds `loop:agent-ready`. This is the non-delegable build authorization.

### 2. Run one safe builder pass

```bash
/path/to/coding-loop/.venv/bin/templeton-loop run build --repo /path/to/repo --profile nikki
```

Preview the exact Hermes command without launching it:

```bash
/path/to/coding-loop/.venv/bin/templeton-loop --json run build --repo /path/to/repo --dry-run
```

### 3. Run one independent reviewer pass

```bash
/path/to/coding-loop/.venv/bin/templeton-loop run review --repo /path/to/repo --profile nikki
```

### 4. Keep a watched loop open

Only after one-pass use is proven on that repository:

```bash
/path/to/coding-loop/.venv/bin/templeton-loop run build --repo /path/to/repo --forever --interval 300
/path/to/coding-loop/.venv/bin/templeton-loop run review --repo /path/to/repo --forever --interval 300
```

For a durable unattended worker, use a launch agent or Hermes scheduled job only after repository-specific one-pass proof. Keep build and review as separate fresh sessions. Do not schedule spec interviews.

## GitHub labels

| Label | Meaning |
| --- | --- |
| `loop:spec-draft` | issue awaiting human approval |
| `loop:agent-ready` | human-approved contract |
| `loop:building` | claimed by builder |
| `loop:blocked` | human answer required |
| `loop:awaiting-review` | PR needs fresh review |
| `loop:approved` | SHA-pinned review + required CI passed |
| `loop:changes-requested` | must-fix findings |
| `loop:needs-human-review` | automated lane stopped |
| `loop:stuck` | repair budget exhausted |

## Verification

```bash
cd /Users/ai/projects/templeton/coding-loop
.venv/bin/python -m pytest
.venv/bin/python -m compileall -q templeton_loop tests
.venv/bin/templeton-loop --help
```

## Portable exports

```bash
cd /Users/ai/projects/templeton/coding-loop
.venv/bin/python scripts/build_exports.py
```

This produces separate checksummed Hermes and OpenClaw ZIP archives under `dist/`. The OpenClaw edition uses fresh `openclaw agent` session keys and OpenClaw-local skills; it does not invoke Hermes.

## Attribution

This implementation uses the architecture and safety ideas of Alex Finn's MIT-licensed Finn-loop. It is a clean adaptation rather than a direct installation: Linear-specific state was replaced with GitHub Issues, Claude `/loop` was replaced with bounded fresh Hermes passes, and Templeton's explicit production/deployment approval gates were added.
