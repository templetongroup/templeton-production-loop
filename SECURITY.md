# Security Policy

## Supported release

Templeton Coding Loop 1.0.x is the supported release line.

## Trust model

Templeton separates a trusted deterministic broker from untrusted model workers.

The trusted operator controls:

- the manifest or GitHub issue contract;
- target repository and protected paths;
- runtime configuration and digest-pinned worker image;
- verifier commands;
- GitHub credentials and branch/PR effects;
- final merge, deployment, publishing, purchasing, and production access.

Model workers receive only a filtered staged tree, bounded task context, and role-specific sandbox tools. They do not receive `.git`, host `HOME`, GitHub/cloud/registry credentials, deployment tools, browser access, messaging tools, or network egress.

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

Hermes model sessions receive only `terminal` and `todo`; terminal commands execute inside that container. Verifier commands run in separate short-lived Docker containers with `--network none`, `--read-only`, `--cap-drop=ALL`, `no-new-privileges`, non-root UID/GID, and resource limits.

### OpenClaw

Each Templeton role uses an explicitly configured agent whose effective policy is checked with `openclaw sandbox explain`. The agent must use:

- `sandbox.mode=all`, `scope=session`, and Docker backend;
- a digest-pinned image;
- `docker.network=none`, read-only root, all capabilities dropped, and no extra binds;
- exact role tool allowlists and required deny rules;
- elevated execution disabled;
- staged workspace access only (`rw` for build, `ro` for review and QA).

The OpenClaw gateway itself remains trusted host software. Only tool execution is sandboxed.

## Source and artifact integrity

- Staging rejects symlinks, unsafe paths, secret-bearing files, oversized files, and `.git` metadata.
- Build output is derived from an exact tree comparison; the model does not supply the authoritative patch.
- Protected-path edits, excessive changed files, and oversized patches fail closed.
- Review and QA run against clean read-only staged snapshots.
- Each exported edition includes an exact file manifest, per-file SHA-256 values, byte counts, a detached manifest digest, and a validator that rejects missing, extra, modified, symlinked, or unsafe paths.

## Data boundaries

External and model-provided data is wrapped with type, source, byte count, and SHA-256 provenance. Before prompts, GitHub effects, reports, logs, or other external sinks are written, Templeton applies deterministic size and secret checks.

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
