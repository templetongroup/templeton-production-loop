# Templeton Coding Loop v1 implementation plan

**Goal:** ship a release-ready, clean-room Templeton Coding Loop kernel with deterministic evidence, enforced runtime capabilities, measured routing, host-specific Hermes/OpenClaw adapters, and two independently installable private GitHub repositories.

## Product contract

- GitHub Issues and PRs remain the durable contract/review surfaces.
- Humans retain `loop:agent-ready`, merge, deploy, publish, purchase, and production authority.
- Agent prohibitions must be backed by runtime policy, not only prompt text.
- Deterministic checks are release gates; model review is advisory unless a human accepts it.
- All model-produced findings map to `AC-N`/`NG-N` and carry evidence/freshness metadata.
- Hermes and OpenClaw editions are separate generated products from one canonical source tree.
- No gstack or Ringer code/prose is copied; concepts are clean-room adaptations with provenance.

## Milestone 1 — close v0.3 blockers

1. Recheck expected artifacts after every verifier and require at least one verifier per task.
2. Emit verifier start/completion events and include argv/status/log evidence in reports.
3. Cap retries at one in parser and schema.
4. Reject run roots inside source roots.
5. Verify `MANIFEST.json`, `MANIFEST.sha256`, every listed digest/size, unexpected files, runtime/version/name consistency, and manifest self-digests in bundled validator.
6. Make export generation deterministic and test source-to-stage parity plus ZIP checksums.
7. Resolve OpenClaw proof-runner parity by shipping a runtime-neutral proof kernel and explicit host adapter.

## Milestone 2 — runtime-enforced authority

1. Add typed capability policies for `spec`, `plan-review`, `build`, `review`, `qa`, and `prove`.
2. Writable Hermes build/proof children use a dedicated preflight-verified Docker profile, explicit toolsets, ignored repository rules, and `HERMES_WRITE_SAFE_ROOT`; they do not use `--safe-mode`, because that would ignore the verified terminal profile. Report-only review/QA/spec/status children instead consume bounded prompt context under `--safe-mode` with a `todo`-only allowlist and receive no terminal or file tools.
3. OpenClaw execution requires a dedicated agent whose effective tool policy and sandbox declaration match the shipped template; preflight fails closed when it cannot prove the contract.
4. Parent orchestration owns deterministic GitHub state transitions; children emit artifacts/findings rather than receiving merge/deploy/publish authority.
5. Add denial canaries for forbidden capabilities and policy/config mismatch.

## Milestone 3 — evidence and routing

1. Add provider-neutral attempt records: provider, model, route, duration, usage, cost when reported, verifier result, and retry relation.
2. Add an offline benchmark/evaluation schema and append-only evidence store.
3. Add explainable route recommendations from verified pass rate, first-attempt pass rate, latency, and cost; never silently substitute.
4. Add capability/evaluation coverage matrices and fail release validation when required cells are missing.
5. Check all generated outputs, not only the first generated path.

## Milestone 4 — workflow quality

1. Add canonical role contracts with thin Hermes/OpenClaw adapters.
2. Add pre-approval plan review with outcome, premise, alternatives, citations, AC-to-proof mapping, unresolved decisions, scope conflicts, and recommendation.
3. Add normalized review findings with fingerprint/deduplication and blocking-versus-advisory disposition.
4. Add structured outer-loop run ledgers with candidate/SHA/transitions/checks/findings/next action.
5. Add independent report-only QA and evidence freshness states.
6. Add decision classes: `Blocking User Decision`, `Engineering Discretion`, `Reversible Default`, `Deferred Follow-up`.

## Milestone 5 — boundaries and operations

1. Add deterministic secret redaction at logs, events, state, Markdown, HTML, and export sinks.
2. Wrap external/source/model material in explicit untrusted-data envelopes.
3. Add checkpoint/resume projection from append-only events.
4. Add health/reliability reporting: queue age, pass/failure/retry rates, stale evidence, stuck loops, runtime-policy failures, and cost/latency when available.

## Milestone 6 — verification and publication

1. Full pytest, compileall, CLI smokes, manifest lint/dry-run.
2. Adversarial verifier mutation, retry overflow, run-root, redaction, authority, and bundle-tamper probes.
3. Rebuild twice and compare artifact digests.
4. Clean-install and validate each standalone edition.
5. Independent specification and security reviews; close release-blocking findings.
6. Initialize standalone `templeton-coding-loop-hermes` and `templeton-coding-loop-openclaw` repositories, create initial release commits/tags, publish private GitHub repositories, and verify clones/install/help/tests.

## Release evidence

The release report must include files changed, exact commands and real outcomes, test counts, bundle/repository SHAs, GitHub URLs, residual risks, and the next operator action.
