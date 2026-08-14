# Security Policy

## Supported release

Templeton Production Loop 1.1.x is the supported release line.

## Trust model

Templeton separates a trusted deterministic broker from untrusted model workers.

The trusted operator controls:

- the manifest or GitHub issue contract;
- target repository and protected paths;
- runtime configuration and digest-pinned worker image;
- verifier commands;
- GitHub credentials and branch/PR effects;
- final merge, deployment, publishing, purchasing, and production access.

Model workers receive only a filtered staged tree or, for the no-tools spec role, a bounded packet in the prompt, plus role-specific sandbox tools. OpenClaw's spec policy uses an explicit wildcard deny (`tools.deny: ["*"]`); an empty allow list is not treated as a no-tools boundary. Workers do not receive `.git`, host `HOME`, GitHub/cloud/registry credentials, deployment tools, browser access, messaging tools, or network egress.

## Enforced runtime boundary

A run fails closed before its first model call unless the selected runtime proves its policy.

### Hermes

The operator must use a dedicated `HERMES_HOME` containing `TEMPLETON_RUNTIME.json`. Effective Hermes terminal configuration must use Docker with:

- network disabled;
- a digest-pinned image;
- no forwarded environment variables or extra volumes;
- no persistent container;
- host-user execution;
- read-only root filesystem and all Linux capabilities dropped.

Hermes build/prove sessions receive only `terminal` and `todo`; terminal commands execute inside that container. Report-only sessions receive only `todo` under safe mode, and the spec broker supplies all facts in the prompt. Verifier commands run in separate short-lived Docker containers with `--network none`, `--read-only`, `--cap-drop=ALL`, `no-new-privileges`, non-root UID/GID, and resource limits.

### OpenClaw

Each Templeton role uses an explicitly configured agent. Before every child run, Templeton verifies the stored `agents.list` entry and then checks the fresh session with `openclaw sandbox explain`. The stored agent must use:

- `sandbox.mode=all`, `scope=session`, and Docker backend;
- a digest-pinned image;
- `docker.network=none`, read-only root, all capabilities dropped, and no extra binds;
- exact role tool allowlists and required deny rules;
- elevated execution disabled;
- staged workspace access only (`rw` for build and prove; `ro` for spec, plan-review, review, QA, and status). The spec workspace must remain empty and its direct tool policy uses wildcard deny-all.

OpenClaw 2026.7.1 does not repeat the stored Docker hardening or direct agent tool policy in `sandbox explain`. Its fresh-session proof instead must report `mode=all`, `scope=session`, Docker backend, sandboxed execution, elevated execution disabled, a sandbox tool envelope that does not block required role tools, and exact workspace routing. Writable roles map the configured staged workspace to `/workspace`; read-only roles use a session sandbox at `/workspace` and mount the configured staged workspace read-only at `/agent`. Templeton does not claim fields absent from this runtime output were effectively observed.

The OpenClaw gateway itself remains trusted host software. Only tool execution is sandboxed.

## Source and artifact integrity

- Staging rejects symlinks, unsafe paths, secret-bearing files, oversized files, and `.git` metadata.
- Build output is derived from an exact tree comparison; the model does not supply the authoritative patch.
- Protected-path edits, excessive changed files, and oversized patches fail closed.
- Review and QA run against clean read-only staged snapshots.
- Each exported edition includes an exact file manifest, per-file SHA-256 values, byte counts, a detached manifest digest, and a validator that rejects missing, extra, modified, symlinked, or unsafe paths.

## Data boundaries

External and model-provided data is wrapped with type, source, byte count, and SHA-256 provenance. Before prompts, GitHub effects, reports, logs, or other external sinks are written, Templeton applies deterministic size and secret checks.

The guided interview is supported only through `templeton-loop run spec`. The trusted broker prepares and scans the bounded repository/research packet, verifies the report-only policy before every model turn, stores bounded multi-turn state under Git's `templeton-loop/spec/` metadata path, requires explicit confirmation before accepting an issue packet, and scans that packet for handoff. Replayed model transcripts are encoded in an untrusted envelope so response text cannot inject broker closing tags on a later turn. It never files the issue or applies a label. Direct invocation of the installed spec skill is outside the supported boundary and the skill must refuse prompts without the broker envelope.

Spec state files contain bounded product context and interview history. They are written with restricted file permissions below the Git-resolved metadata path, including the correct administrative directory for linked worktrees. Locks, runs, outcomes, and OpenClaw workspaces use the same Git-resolved routing. These files are excluded from source staging and archives and must be handled as confidential local operator data even after secret scanning.

Secret-positive payloads are rejected rather than silently altered. Blocked records contain only matched rule names, byte count, and content hash—never the raw payload. This is defense in depth, not a guarantee that arbitrary secrets can always be recognized.

## Explicit non-goals

Templeton does not grant child agents authority to:

- merge or enable auto-merge;
- deploy or publish;
- change DNS, billing, or account ownership;
- purchase goods or services;
- rotate credentials;
- mutate production;
- modify global hooks or self-update.

The host operator remains responsible for reviewing trusted manifests, verifier commands, generated diffs, and GitHub actions. A malicious Docker daemon, compromised host, privileged container runtime, or unsafe digest-pinned image is outside this boundary.

## Vulnerability reporting

Report suspected vulnerabilities privately to The Templeton Group. Do not include live credentials, private repository contents, or production data. Include the version, runtime, minimal reproduction, impact, and suggested mitigation when known.
