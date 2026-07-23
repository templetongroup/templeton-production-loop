---
name: templeton-loop-prove
description: Run a trusted Templeton proof manifest through the OpenClaw host adapter with explicit per-task model routing, a dedicated one-shot workspace, independent verification, bounded retries, and sealed evidence.
---

# Templeton Loop — Prove (OpenClaw)

Use this role for a bounded artifact proof manifest. The manifest is a trusted plan and executable configuration. One strategy turn is persisted, then workers use the declared default or per-task model route.

## Trust boundary

Before execution, review every source path, output path, model/provider, verifier argv, timeout, concurrency limit, and retry count. OpenClaw profile overrides are invalid; model routes are passed explicitly with `openclaw agent --model`.

The deterministic runner:

- never targets the original source tree and copies declared sources into read-only snapshots;
- requires a dedicated `prove` agent whose configured workspace exactly equals `--run-root`;
- requires that workspace to exist, contain no symlinks, and be completely empty before a live run;
- refuses to reuse a workspace containing a prior run; archive verified evidence and clear the workspace through a separately reviewed operator action;
- verifies configured and effective OpenClaw sandbox/tool policy before the first model call;
- uses unique sessions, explicit per-task model overrides, bounded timeouts, and no implicit fallback;
- detects source, cross-task artifact, ledger, verifier-output, and report mutation through final inventories, sealed digests, and a hash-chained event ledger;
- executes verifier argv without a shell in digest-pinned, air-gapped, read-only Docker containers;
- rejects missing, empty, escaping, or symlinked artifacts.

A one-shot empty workspace prevents access to prior-run evidence. Final integrity checks detect a model that alters another task or the current run's evidence before trusted completion.

Never merge, deploy, enable auto-merge, publish, purchase, install, update, or mutate production. This skill installs no auto-update behavior or global hooks. It contains no Ringer-derived code or assets.

## Prepare the dedicated agent

```bash
templeton-loop --json policy-template \
  --agent templeton-prove \
  --role prove \
  --workspace /absolute/path/to/empty-proof-workspace \
  --image 'trusted-worker@sha256:REPLACE_WITH_DIGEST'
```

The operator—not this skill—owns reviewed OpenClaw configuration changes or restarts. Templeton does not mutate live OpenClaw configuration.

## Procedure

```bash
# Schema and path validation only; no model calls.
templeton-loop prove examples/proof-manifest.json --lint --agent templeton-prove

# Exact strategy/worker commands and model routes; no model calls.
templeton-loop --json prove examples/proof-manifest.json \
  --dry-run \
  --agent templeton-prove

# Execute once in the configured empty workspace.
templeton-loop prove examples/proof-manifest.json \
  --agent templeton-prove \
  --run-root /absolute/path/to/empty-proof-workspace
```

## Evaluate the result

Treat an artifact as proved only when final status is `passed`, original and copied source integrity passed, final artifact integrity passed, every declared artifact is present and non-empty, every independent verifier passed, and `events.jsonl` verifies both its hash chain and sealed evidence inventory. A worker's success claim is never evidence.

## Failure handling

- Policy mismatch or non-empty workspace: stop before model calls.
- Source, artifact, or evidence mutation: fail and preserve evidence.
- Worker/verifier failure: use only the manifest's bounded retry budget.
- Retry exhausted: report failure; never hand-edit artifacts to manufacture green proof.

Source-tree edits, GitHub writes, merges, deployments, production mutation, unbounded repair, auto-update, and global hooks are out of scope in v1.0.
