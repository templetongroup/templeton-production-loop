# Templeton Proof Runner v0.3 Implementation Plan

> **For Hermes:** Execute this plan directly in the existing repository with behavioral tests and independent spec/quality review.

**Goal:** Add a portable verified-delegation runner that uses a high-capability Hermes model for strategy, hands the strategy to cheaper worker models for parallel execution, independently verifies outputs, retries bounded failures, and emits durable evidence.

**Architecture:** `templeton_loop.proof` owns a versioned JSON manifest, model-specific Hermes CLI command construction, isolated per-task workspaces, argv-only verification, bounded retries, append-only events, atomic state projections, and deterministic Markdown/HTML reports. `templeton-loop prove PLAN` is the public entry point. The first release is artifact-oriented and copies only declared source paths into disposable read-only snapshots; it does not merge, deploy, install hooks, auto-update, or edit the original source tree.

**Tech Stack:** Python 3.11+ standard library, Hermes CLI, pytest, existing setuptools package and export builder.

---

## Acceptance criteria

- AC-1: A manifest explicitly names a strategy model and a default worker model; commands prove each model is routed to the correct phase.
- AC-2: The strategist runs once, read-only against a copied source snapshot, and its bounded output is persisted and injected into every worker brief.
- AC-3: Independent tasks run concurrently in separate workspaces and can override the default worker model.
- AC-4: Verifiers use structured argv only, inherit a minimal environment, enforce timeouts, and verify declared non-empty artifacts.
- AC-5: A failed worker or verifier receives one bounded retry when configured, with original brief plus real failure evidence; every attempt remains in append-only evidence.
- AC-6: State writes use unique temporary files and atomic replacement; final JSON, JSONL, Markdown, and HTML evidence identify strategy and worker models.
- AC-7: Dry-run/lint modes make no model calls and expose the exact routing plan.
- AC-8: The feature is documented as trusted-plan, artifact-oriented v1 with no merge/deploy/production authority, no auto-update, no global hooks, and no Ringer-derived code/assets.
- AC-9: Hermes skill/export packaging includes `templeton-loop-prove`; OpenClaw packaging remains valid and clearly labels the proof runner Hermes-native in v0.3.
- AC-10: Unit and fake-Hermes end-to-end tests prove strategy→cheap-worker handoff, per-task override, retry, verification, evidence, reports, and no original-source mutation.

## Task 1: Core manifest and routing types

**Files:**
- Create: `templeton_loop/proof.py`
- Create: `tests/test_proof.py`

1. Write failing tests for schema validation, path safety, strategy/worker model requirements, source path resolution, and command construction.
2. Run focused tests and confirm failure.
3. Implement immutable dataclasses and strict JSON parsing.
4. Build Hermes commands with explicit `--model`, optional `--provider`/`--profile`, bounded turns, quiet/tool source flags, and no yolo/auto-hook flags.
5. Rerun focused tests.

## Task 2: Safe workspaces, execution, verification, and retry

**Files:**
- Modify: `templeton_loop/proof.py`
- Modify: `tests/test_proof.py`

1. Add failing tests using a fake `hermes` executable that records models, emits strategy, writes declared worker artifacts, and intentionally fails one first attempt.
2. Implement run directories, declared source copying, read-only source snapshots, per-task output directories, child environment allowlisting, parallel worker execution, argv verifier execution, expected-file checks, and retry evidence.
3. Ensure retries preserve attempt directories and append event rows.
4. Rerun focused tests.

## Task 3: Evidence and operator reports

**Files:**
- Modify: `templeton_loop/proof.py`
- Modify: `tests/test_proof.py`

1. Add failing assertions for atomic versioned state, events JSONL, strategy artifact, final Markdown, and escaped HTML.
2. Implement a single-writer evidence recorder with unique temp files.
3. Render deterministic final reports containing model routing, attempts, verification results, artifacts, and final status.
4. Rerun focused tests.

## Task 4: CLI and skill integration

**Files:**
- Modify: `templeton_loop/cli.py`
- Modify: `tests/test_cli.py`
- Create: `skills/templeton-loop-prove/SKILL.md`
- Modify: `tests/test_skills.py`
- Modify: `exports/validate_bundle.py`

1. Add failing CLI/parser and skill-inventory tests.
2. Add `templeton-loop prove PLAN` with `--lint`, `--dry-run`, `--run-root`, and JSON output support.
3. Write the Hermes skill with explicit trigger, strategy/worker model policy, trusted-plan boundary, and proof commands.
4. Keep OpenClaw inventory valid without claiming dynamic per-run model support.
5. Rerun CLI and skill tests.

## Task 5: Documentation, example, and exports

**Files:**
- Create: `examples/proof-review.json`
- Modify: `README.md`
- Modify: `exports/hermes/README.md`
- Modify: `exports/openclaw/README.md`
- Modify: `scripts/build_exports.py`
- Modify: `pyproject.toml`
- Modify: `exports/hermes/AGENTS.example.md`

1. Add a safe example using a strong strategy model and cheaper worker default.
2. Document model-routing economics, trust boundaries, commands, evidence paths, limitations, and extension path.
3. Bump package/export version to 0.3.0 and rebuild checksummed bundles.
4. Validate both runtime bundles.

## Task 6: Final verification and review

1. Run `pytest`, `compileall`, CLI help, lint/dry-run example, and fake-Hermes end-to-end proof.
2. Build exports and run bundled validators from each staged bundle.
3. Review `git diff --check`, `git status`, and changed-file scope.
4. Dispatch independent spec-compliance and engineering-quality reviews.
5. Fix critical/important findings and rerun all proof.
6. Update TKS and Hermes Structure skill/change-log notes after the source and exported artifact state is final.
