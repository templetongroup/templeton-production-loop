# gstack concept review for Templeton Production Loop

Date: 2026-07-23
Reviewer: Nikki Templeton
Upstream: `garrytan/gstack`
Pinned commit: `a3259400a366593e0c909dd9ac3e59752efd2488`
Commit date: 2026-07-14T18:33:46-07:00
Upstream version inspected: `1.60.1.0`
License: MIT
Review mode: read-only checkout; targeted existing free tests executed in place by an independent reviewer; no upstream setup, installation, host mutation, paid/network eval, or source modification

## Executive decision

gstack contains several strong product and engineering concepts worth adapting, especially around empirically measured model routing, phase-aware workflow orchestration, skill/eval coverage, conditional specialist review, sink redaction, and single-source multi-host generation.

Templeton should **not** import gstack as a framework or expand into a similarly broad skill suite. The inspected checkout has 56 skill templates totaling 792,137 bytes and 278 top-level test files. That breadth is evidence of substantial iteration, but it also creates a large prompt, maintenance, routing, and semantic-drift surface. Templeton's advantage should remain a smaller enforceable kernel with explicit human authority and proof artifacts.

The right move is to treat these as **v0.4+ clean-room product requirements**, not as additions to the already-open v0.3 release. v0.3 should first close its current verifier-integrity, retry-contract, export-parity, and security-review blockers.

**Immediate comparison findings:**

1. Templeton's current bundled `scripts/validate_bundle.py` checks skill inventory and selected safety phrases but does not verify `MANIFEST.json` or `MANIFEST.sha256`. A disposable tamper probe appended `TAMPER_PROBE` to the staged Hermes bundle README; the validator still returned `TEMPLETON_LOOP_BUNDLE_OK`. Full manifest/hash verification, missing/extra-file checks, and tamper tests are a v0.3 release blocker—not a v0.4 enhancement.
2. The ordinary build/review launcher currently expresses "Never merge/deploy/publish" only inside the child prompt (`/Users/ai/projects/templeton/coding-loop/templeton_loop/cli.py:391-397`). Its test proves the words are present in argv (`/Users/ai/projects/templeton/coding-loop/tests/test_cli.py:91-108`), not that the child lacks terminal, GitHub, credential, or network capability to perform a forbidden action. Runtime-enforced least authority and falsifiable denial canaries are also v0.3 security gates.

## Concepts to adopt

### 1. Runtime-enforced authority and capability policy

**Upstream evidence**

- `browse/src/token-registry.ts:14-24` and `:188-243` model scoped, revocable capabilities rather than relying on instructions.
- `browse/src/server.ts:291-343` enforces path and command allowlists; `:1036-1059` checks resource ownership.
- `browse/src/browser-skill-commands.ts:237-297` and `:331-401` add per-spawn revocation, timeouts, output caps, and scrubbed environments.
- `test/skill-e2e-hermetic-canary.test.ts:67-121` and `:130-180` test effects—environment/config isolation and actual tool behavior—not whether a warning sentence appeared in a prompt.

**Templeton adaptation**

Define a fail-closed role/capability policy before spawning any child. A build, review, QA, or proof task should receive only the tool surface, credentials, paths, network destinations, and GitHub operations its contract requires. Enforce the policy through constrained runtime profiles/toolsets, scoped credentials, a brokered GitHub mutation surface, and OS/container isolation where necessary—not by prompt prose alone.

Add hermetic denial canaries that attempt forbidden merge/deploy/publish commands, inherited-secret access, unexpected MCP/tool access, profile/config leakage, and source-tree mutation. The gate passes only when the effects are denied. If a host cannot enforce a required restriction, its adapter must fail closed or explicitly require a stronger isolated environment.

### 2. Empirical model routing instead of static model preferences

**Upstream evidence**

- `benchmark-models/SKILL.md.tmpl:1-18` defines a cross-model benchmark over latency, token use, cost, and optional judged quality.
- `bin/gstack-model-benchmark:105-147` builds a dry-run-aware provider batch and emits table, JSON, or Markdown.
- `test/helpers/benchmark-runner.ts:15-45` defines a provider-neutral result envelope; `:53-98` runs providers concurrently; `:101-149` reports latency, input/output tokens, estimated cost, quality, and tool calls.
- `benchmark-models/SKILL.md.tmpl:145-151` requires auth preflight, visible cost, and explicit consent for a paid judge.

**Templeton adaptation**

Add a benchmark/eval layer that measures candidate models by **task class**, not one universal leaderboard:

- strategy decomposition;
- narrow artifact execution;
- code review/security review;
- verifier-failure repair;
- skill routing.

A route should be promoted only from repeatable fixtures with minimum quality and reliability floors. Store the model, provider, price basis, latency, tokens, success/failure, verifier outcome, and benchmark timestamp. Use the result to populate named routing profiles such as `strategy`, `worker-cheap`, `review`, and `repair`.

Do not let an LLM judge alone select a model. Deterministic verifier success and task completion come first; judged quality is supplemental.

### 3. A free gate tier plus an explicit paid/periodic eval tier

**Upstream evidence**

- `package.json:21-30` separates free tests, E2E evals, gate evals, periodic evals, and provider-specific suites.
- `test/skill-coverage-matrix.ts:1-18` defines `gate` as CI-blocking and low-cost/free, and `periodic` as deeper, potentially paid evaluation.
- `test/skill-coverage-matrix.test.ts:25-70` fails when a skill lacks gate coverage or the registry drifts from disk.
- `test/skill-coverage-floor.test.ts:44-153` applies structural checks to every generated skill.
- `test/helpers/touchfiles.ts` and `test/touchfiles.test.ts:63-189` select expensive evals from changed-file impact rather than running the entire matrix.
- `test/skill-routing-e2e.test.ts:24-58` combines diff selection with gate/periodic tiers and records cost.

**Templeton adaptation**

Create a compact `eval-matrix.json` or Python registry mapping every Templeton role, host export, and proof-runner capability to:

- deterministic gate tests;
- fake-agent behavioral tests;
- optional paid periodic evals;
- files that should trigger each eval;
- maximum allowed spend and timeout.

CI should fail if a skill/capability is present without at least one deterministic gate. Paid evals should be opt-in or scheduled, never silently triggered by a normal local test command.

### 4. One canonical workflow definition compiled into host-specific editions

**Upstream evidence**

- `docs/ADDING_A_HOST.md:1-32` describes declarative host definitions consumed by generation, setup, health checks, worktree handling, and tests.
- `scripts/host-config.ts:17-112` models paths, frontmatter policies, skill inclusion, content/tool rewrites, runtime assets, install behavior, and host-specific boundaries.
- `scripts/host-config.ts:114-202` validates names, paths, resolver references, and cross-host uniqueness.
- `test/gen-skill-docs.test.ts:159-284` checks template/generated-file parity, strict frontmatter parsing, freshness, and unresolved placeholders.
- `test/template-context-parity.test.ts:26-58` protects parent/section generation context.

**Templeton adaptation**

Replace hand-maintained Hermes/OpenClaw role duplication with a canonical structured role definition plus typed host capabilities. Generate runtime editions and validate:

- frontmatter schema;
- tool capability mapping;
- unsupported feature suppression;
- no source-host path leakage;
- generated-file freshness;
- bundle inventory parity.

Do **not** rely mainly on literal prose replacement. Host transformations should operate on structured steps/capabilities so semantic differences are explicit and testable.

### 5. Pre-approval contract critique, conditional review lenses, and persisted readiness

**Upstream evidence**

- `autoplan/SKILL.md.tmpl:103-145` requires ordered phase completion, output checks, and explicit evidence for sections with no findings.
- `autoplan/SKILL.md.tmpl:191-230` detects UI and developer-experience scope and conditionally loads relevant review lenses.
- `review/SKILL.md.tmpl:123-145` applies core categories and scope-aware specialist review.
- `review/SKILL.md.tmpl:205-213` requires evidence for claims instead of "probably" or "looks fine."
- `review/SKILL.md.tmpl:271-295` persists reviewer status, issue counts, specialist participation, finding fingerprints, actions, and commit.
- `ship/SKILL.md.tmpl:62-70` distinguishes rerunnable verification from idempotent actions.

**Templeton adaptation**

Before Tony applies `loop:agent-ready`, optionally run a compact read-only contract critique that checks premises, acceptance-criteria executability, non-goals, existing-code leverage, failure/rescue paths, and missing product decisions. It may propose an issue amendment but must not change the issue or apply the approval label. Tony remains the gate.

After implementation, extend the existing fresh reviewer with a small deterministic lens router:

- product/strategy for material behavior changes;
- design/accessibility for frontend scope;
- engineering for all code changes;
- security for auth, secrets, shell, data, networking, or production-sensitive scope;
- developer experience for CLI/API/SDK/install changes.

Persist lens applicability, whether it ran, reviewer identity/model, exact SHA, findings, disposition, and proof command. Missing mandatory lenses should be visible in `templeton-loop status` and should prevent automated approval. If adaptive hit-rate gating is added later, security and destructive-data lenses remain non-skippable insurance controls.

### 6. Decision classes that preserve human authority

**Upstream evidence**

- `autoplan/SKILL.md.tmpl:69-101` separates mechanical decisions, taste decisions, and changes that challenge the user's stated direction.
- `autoplan/SKILL.md.tmpl:123-127` keeps premises and user-direction challenges human-gated.
- `autoplan/SKILL.md.tmpl:162-190` captures a restore point before mutating a reviewed plan.

**Templeton adaptation**

Classify proposed changes and review findings as:

- `mechanical`: safe to execute within an approved contract;
- `judgment`: multiple valid tradeoffs; request operator decision;
- `contract-change`: changes acceptance criteria, non-goals, authority, risk, data handling, cost, deployment, or architecture; requires explicit human amendment;
- `security-blocker`: cannot continue safely without resolution.

The existing GitHub issue contract and `loop:agent-ready` label should remain authoritative. Agents may not silently widen it. Any automated plan rewrite should produce a restorable prior artifact and an amendment diff.

### 7. Redaction and instruction boundaries at every external sink

**Upstream evidence**

- `spec/SKILL.md.tmpl:168-220` runs semantic and deterministic redaction before a second-model dispatch and prevents blocked raw content from reaching downstream sinks.
- `spec/SKILL.md.tmpl:222-240` wraps user content as untrusted data with explicit delimiters.
- `lib/redact-patterns.ts:1-30` centralizes a tiered taxonomy shared by runtime, hooks, and generated docs.
- `test/spec-template-invariants.test.ts:171-200` checks the no-persist-on-block and prompt-injection invariants.
- `test/secret-sink-harness.test.ts` uses positive controls to prove the test harness detects leaks.

**Templeton adaptation**

Before sending a GitHub issue body, PR body, model prompt, report, telemetry row, or exported bundle across a boundary:

1. scan exact outgoing bytes;
2. block high-confidence secrets;
3. require human disposition for ambiguous PII/legal/internal findings;
4. pass the sanitized artifact—not the original—to every downstream sink;
5. store only content-free audit metadata and a hash when blocked;
6. delimit source, strategy, verifier output, and user-authored content as untrusted data.

This belongs in deterministic code, not only skill prose. The scanner itself must use bounded input, linear-time patterns, no shell interpolation, positive leak controls, and explicit false-positive tiers; regex screening is a guardrail, not a sandbox or proof that content is safe.

## Concepts to adapt selectively

### 8. Code-grounded spec interrogation and duplicate detection

`spec/SKILL.md.tmpl:76-161` requires a verified current behavior, measurable done state, explicit non-goals, rollback/failure modes, repository evidence before technical questions, and best-effort duplicate issue detection.

Templeton's spec role already researches the repository and emits acceptance criteria/non-goals. Add duplicate-issue search, explicit rollback/failure-mode fields, and a machine-readable specification quality check. Do not copy the long conversational five-phase script wholesale.

### 9. Append-only context checkpoints

`context-save/SKILL.md.tmpl:55-180` captures branch, status, diffs, decisions, remaining work, and gotchas in collision-safe append-only files. `context-restore/SKILL.md.tmpl:59-121` restores by canonical timestamp and warns on branch mismatch.

Templeton should standardize a concise `handoff.md`/run-checkpoint artifact for long agent tasks and fresh-session transfers. Do not build a second general memory system: Hermes session history, skills, persistent memory, GitHub, and TKS already own those responsibilities.

### 10. Project learning lifecycle with staleness checks

`learn/SKILL.md.tmpl:37-103` provides search, prune, contradiction, deleted-file, and latest-entry-wins behavior.

Adopt the lifecycle—source, confidence, related files, verification state, contradiction/supersession—not gstack's separate store. Route reusable procedures to Hermes skills, stable project facts to TKS, and conversation history to session search.

### 11. Health trends and regression deltas

`health/SKILL.md.tmpl:43-181` detects project checks and builds a weighted health view; `:229-289` persists history and reports category regressions.

A narrow Templeton health surface could track proof pass rate, retries, verifier timeouts, review turnaround, stale exports, test/lint/build status, and per-route cost. Avoid a universal opaque composite score; retain the raw metrics and explicit thresholds.

### 12. Prompt/skill size budgets

`test/skill-size-budget.test.ts:58-134` detects growth against a baseline, records explicit override reasons, and also guards accidental shrinkage and catalog token cost (`:136-233`).

Templeton should add modest budgets for always-loaded skill descriptions, generated skill files, proof strategy size, worker briefs, verifier evidence, and reports. Overrides should be explicit and audited. A budget is a regression alarm, not a target to game.

### 13. Diff-aware expensive testing

`test/touchfiles.test.ts:63-189` proves changed-file routing and global trigger behavior. This can lower eval spend as Templeton adds behavioral model tests.

Start with a transparent registry. If selection is uncertain or a shared generator/runtime changed, run the broader suite. Never use cost optimization to skip deterministic safety gates.

### 14. Evidence-normalized findings

`review/SKILL.md.tmpl:205-213` requires evidence rather than speculation, while gstack's specialist result contract adds severity, confidence, location, category, fix, and fingerprint (`scripts/resolvers/review-army.ts:106-168`).

Templeton should require every review finding to identify the affected `AC-N`/`NG-N` or policy, exact `path:line` when applicable, concrete failure scenario, severity, confidence, evidence source, stable fingerprint, and disposition. Specialist outputs feed one fresh SHA-pinned verdict; they do not become competing label writers.

### 15. Structured run ledger

The useful part of `context-save/SKILL.md.tmpl:55-180` is its compact current state, decisions, remaining work, and evidence handoff. Templeton's outer build/review loop currently retains a command log and bounded output, while Proof Runner already has append-only events and atomic projections.

Extend outer-loop passes with a machine-readable ledger containing candidate, issue/PR, starting and ending SHA, state transitions, checks, findings, unresolved questions, and next action. GitHub remains authoritative; the ledger is reconstructible evidence and crash-recovery support, not shadow workflow state.

### 16. Report-only runtime QA and evidence freshness

`qa/SKILL.md.tmpl` maps affected surfaces to executable journeys and screenshots, while `ship/SKILL.md.tmpl:62-70` distinguishes rerunnable verification from idempotent mutation.

For user-visible or integration changes, add an independent report-only QA lane that executes explicit journeys, preserves screenshots/logs, maps results to acceptance criteria, and requests bounded repair without editing code itself. Status should expose reviewed SHA, current SHA, test/review timestamps, and exact stale-evidence reasons.

## Concepts to reject or defer

### Reject: broad automatic install/update/team hooks

The README's team mode installs repo policy and performs throttled auto-update checks (`README.md:53-63`). Templeton's current no-auto-update/no-global-hook rule is safer and should remain. Installation and upgrades must be explicit, previewable, reversible, and host-local.

### Reject as a security boundary: prompt-only or tool-specific safety skills

`freeze/SKILL.md.tmpl:18-29` uses host hooks to block Edit/Write, but `:81-86` correctly admits Bash can bypass it. `careful/SKILL.md.tmpl:17-24` pattern-checks Bash and allows operator override. These are usability guardrails, not isolation.

Templeton should enforce filesystem, process, credential, and network boundaries in runtime code/container policy. Prompt instructions may supplement but must never be reported as containment.

### Reject: one giant automatic ship/deploy command for Templeton v1

`ship/SKILL.md.tmpl` and `land-and-deploy` combine many review, mutation, versioning, Git, PR, merge, and production concerns. Templeton deliberately separates build, review, human merge, and deployment authority. Keep those boundaries. A future release coordinator may aggregate status and propose actions, but should not erase approval gates.

### Defer: broad browser/design/iOS/productivity suite

Those are useful gstack product features but are not the coding-loop kernel. Templeton can invoke existing Hermes/Jasper/browser capabilities when a lens requires them rather than vendoring a parallel suite.

### Reject: broad transcript ingestion and remote-by-default telemetry

Templeton should not sweep raw coding-agent transcripts into shared project memory or send detailed prompts, outputs, paths, or repository data to a remote analytics surface by default. Preserve narrow local operational metrics and explicitly reviewed promotions only. GitHub/TKS/Hermes session history remain their respective sources of truth.

### Reject: marketing claims as proof

The checkout has impressive test infrastructure, but not every advertised eval is complete. For example, `test/skill-llm-eval-spec.test.ts:25-46` registers a periodic surface yet currently ends in `expect(true).toBe(true)` with the real judge flow described as follow-up work. Templeton should distinguish implemented proof from planned evaluation in docs and release reports.

## Proposed Templeton roadmap

### Release gate: finish v0.3 without gstack scope expansion

1. Make the bundle validator verify every `MANIFEST.json` record and `MANIFEST.sha256` line, reject missing/extra/changed files, and add corruption tests. A disposable README tamper probe currently passes validation.
2. Replace prompt-only merge/deploy/publish prohibitions with a fail-closed role/capability policy and effect-based denial canaries.
3. Close current verifier-integrity and retry-contract findings.
4. Reconcile Hermes/OpenClaw export parity and rebuild from current source.
5. Re-run full deterministic, fake-Hermes, clean-install, bundle, archive, and independent security/spec verification.
6. Pilot one low-risk repository through issue → build → fresh review → human merge.

### v0.4 — measured routing and eval governance

1. Add a versioned capability/eval matrix.
2. Add deterministic skill/export freshness and coverage gates.
3. Extend attempt evidence with monotonic duration and normalized provider/model metadata, then add a provider-neutral benchmark result schema and dry-run/auth preflight.
4. Create representative fixtures for strategy, cheap execution, repair, and review.
5. Add optional paid periodic cross-model runs with explicit spend caps.
6. Promote routing profiles only from verifier-backed results.

### v0.5 — canonical roles and smart review routing

1. Define canonical role/workflow documents and typed host capability configs.
2. Generate Hermes/OpenClaw editions; fail on unsupported capability or stale generated output.
3. Add evidence-normalized findings, scope-based review lenses, and persisted review-readiness records.
4. Add a report-only runtime QA lane plus evidence-freshness status.
5. Add decision classes, contract-amendment artifacts, and restore points.

### v0.6 — boundary and operations hardening

1. Add deterministic exact-byte sink scanning/redaction.
2. Add untrusted-data envelopes for source, strategy, verifier, and user content.
3. Add concise run checkpoints and TKS/skill promotion hooks without a parallel memory store.
4. Add raw health/cost/reliability trends and explicit regression thresholds.

## Verification

- Independent targeted gstack free suite: 346 passed, 0 failed across coverage, overlays, telemetry stripping, and benchmark helpers.
- Templeton local suite after documentation/provenance integration: 39 passed.
- Source citation validation: 49 references checked, 0 missing or out-of-range.
- `git diff --check`: passed.
- No paid or network model evaluations were run; the pinned gstack checkout remained clean.

## Provenance guidance

The inspected repository is MIT-licensed, so copying is legally more permissive than the earlier PolyForm Shield Ringer review. Still, Templeton should prefer independently specified concepts and original implementation to keep provenance clear, avoid importing gstack's product assumptions, and prevent its very large prompt surface from becoming Templeton's architecture.

If any substantial gstack code or prose is copied later, preserve its MIT copyright/license notice and record the specific files and commit in `PROVENANCE.md`. This review itself copies no upstream implementation into Templeton runtime or skills.
