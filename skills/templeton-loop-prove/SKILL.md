---
name: templeton-loop-prove
description: Run a trusted Templeton proof manifest with one explicit strategist, concurrent lower-cost workers, independent containerized verification, bounded retries, and durable evidence. Artifact-only in v1.0; never edits the source tree, merges, or deploys.
---

# Templeton Loop — Prove

Use this skill when an operator supplies or asks for a bounded proof manifest whose tasks can produce independently verifiable artifacts. The v1.0 runtime-neutral kernel uses the Hermes host adapter in this edition: it spends one explicit high-capability model call on strategy, then hands that persisted strategy to cheaper worker models for concurrent execution.

## Trust boundary

The manifest is a **trusted plan**, not untrusted input. Read it before running it. In particular, inspect every copied source path, artifact path, verifier argv, timeout, retry count, provider/profile selection, model name, and claim that tasks are independent. Verifiers execute argv directly without a shell, but trusted-plan status is still required because a verifier is executable authority.

The v1.0 lane is artifact-oriented:

- declared source paths are copied into a disposable read-only snapshot;
- workers are instructed to write only inside their isolated run workspaces;
- the deterministic runner never targets the original source tree and fails the proof if its before/after SHA-256 inventory detects a declared source change;
- the runner fails closed unless Hermes workers and independent verifiers use digest-pinned, air-gapped Docker sandboxes with no forwarded credentials, a read-only container root, dropped capabilities, and non-root execution;
- strategy is bounded and runs exactly once;
- independent tasks may run concurrently in separate workspaces;
- every task receives the persisted strategy plus its original brief;
- a task may override the default worker model explicitly;
- verification is independent of worker claims and checks declared non-empty artifacts;
- configured failures may retry only within the manifest's bounded budget, with real failure evidence preserved.

Never merge, deploy, enable auto-merge, publish, install, update, or mutate production from this skill. It has no merge/deploy authority. It does not install auto-update behavior or global hooks. It contains no Ringer-derived code or assets.

## Model policy

1. Require the manifest to name an explicit `strategy.model` and `worker.model`.
2. Use a high-capability strategy model only for the strategy phase. Do not silently reuse it for worker tasks.
3. Use the cheaper default worker model for each task unless that task declares a per-task model override justified by its workload.
4. Before execution, use dry-run output to confirm the exact phase-to-model routing, task concurrency, retry caps, and verifier argv.
5. Do not substitute models implicitly. If an explicitly named model/provider/profile is unavailable, stop with evidence and let the operator revise the trusted plan.

This concentrates expensive reasoning into one bounded strategy artifact while allowing routine implementation, analysis, rendering, or transformation work to use lower-cost models. Per-task overrides are an exception for genuinely harder tasks, not a reason to erase the default-worker economy.

## Procedure

From the Templeton Coding Loop checkout or installed bundle:

```bash
# Validate schema and safety constraints; makes no model calls.
.venv/bin/templeton-loop prove examples/proof-review.json --lint

# Show exact routing and execution intent; makes no model calls.
.venv/bin/templeton-loop --json prove examples/proof-review.json --dry-run
```

Review the output. Confirm:

- strategy model, optional provider/profile, and bounded turns;
- default worker model and every per-task override;
- copied source paths are necessary and contain no secrets;
- declared tasks are independent if scheduled concurrently;
- artifact destinations are relative, bounded, and non-empty-file checks are meaningful;
- verifier commands are structured argv, non-interactive, narrowly scoped, and time-bounded;
- retry limits are finite and appropriate;
- the selected run root is disposable and has sufficient space.

Then execute the trusted plan:

```bash
.venv/bin/templeton-loop prove examples/proof-review.json \
  --run-root .templeton-proof-runs
```

Use `--json` before the subcommand when machine-readable operator output is needed. Do not bypass manifest validation or add shell wrappers around verifier argv.

## Evaluate the result

A completed run emits durable evidence under the reported run directory. Preserve and inspect:

- the reviewed manifest snapshot and bounded strategy artifact;
- timestamped append-only event JSONL for every strategy, worker, verifier, retry, and run transition;
- atomic JSON state projection;
- isolated attempt directories and declared artifacts;
- final Markdown and escaped HTML reports identifying strategy and worker models, attempts, verification results, artifacts, and final status.

Treat an artifact as proved only when its declared verifier succeeds and the runner confirms the artifact exists and is non-empty. A worker saying that it succeeded is not evidence. Do not delete failed attempt records: retry history is part of the proof.

## Failure handling

- **Lint failure:** revise the manifest; do not run it.
- **Routing mismatch:** stop before model calls and correct the trusted plan.
- **Strategy failure:** preserve evidence and stop; the strategist does not loop.
- **Worker/verifier failure:** allow only the configured bounded retry. The retry must receive the original brief plus actual failure evidence.
- **Retry exhausted:** report the task and whole run as failed; do not hand-edit artifacts to manufacture green evidence.
- **Source mutation detected:** stop, preserve the run directory, and escalate. v1.0 has no proof-runner source-edit lane.
- **Missing model/provider/profile:** stop with the exact unavailable route rather than silently falling back.

## Out of scope in v1.0

Source-tree edits, branch/PR creation, merges, deployments, production mutation, unbounded autonomous repair, dependency-driven task graphs, auto-update, and global hooks are out of scope. The runtime-neutral proof kernel uses explicit, edition-specific Hermes or OpenClaw host adapters and never silently changes the manifest's model routes.
