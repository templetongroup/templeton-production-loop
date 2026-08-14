# Graph Patterns Inside Templeton Proof Runner

Status: design note / post-pilot backlog  
Owner: Nikki  
Date: 2026-08-14  
Pinned source: Templeton Production Loop `v1.1.0` @ `1c108c6c61df2ce1eae631955aeabfb7fc5fe228`  
Related: `OPEN CLAW/TKS/TKS - Templeton Production Loop.md` (2026-08-14 graph-engineering pack fit)

## Goal

Turn graph-engineering ideas into **concrete, Templeton-native Proof Runner patterns** without replacing the outer GitHub/human-governance loop.

This note is intentionally implementation-ready for a later issue. It is **not** authorization to change the schema, ship a release, install into a live fleet, or schedule the outer loop.

## Architecture boundary

```text
Outer loop (unchanged authority)
  idea
    → GitHub issue contract
    → Tony applies loop:agent-ready
    → isolated builder pass
    → fresh SHA-pinned review
    → Tony merges

Inner loop (Proof Runner)
  trusted manifest
    → one strategy node
    → parallel worker nodes
    → deterministic verifiers on every edge
    → sealed evidence
```

Graph engineering sharpens the **inner** loop only:

- better task decomposition
- real edges only
- independent checkers
- cheap fan-out / expensive judgment
- failure containment where isolation allows
- ground-truth anchors that cannot be argued away

It does **not** become a second tracker, a fleet install, or a way for agents to merge/deploy.

## Current contract (what already exists)

Pinned against:

- `schemas/proof-manifest-v1.schema.json`
- `templeton_loop/proof.py`
- `docs/model-routing.md`
- `examples/proof-manifest.json`
- `examples/proof-review.json`

### Shipped graph shape today

| Graph concept | Current Proof Runner surface |
| --- | --- |
| Node contract | task `id` + self-contained `brief` + `expected_files` + ≥1 `verifiers[]` |
| Strategy node | one `strategy.model` pass; writes `strategy.md`; does not grade pass/fail |
| Fan-out | independent `tasks[]` up to `max_parallel` (1–32) |
| Worker routing | default `worker.model`; per-task `model`/`provider`/`profile` override |
| Edge gate | argv-only, network-disabled, digest-pinned containerized verifier |
| Retry | manifest/task `retries` capped at 1; failure evidence attached |
| Isolation | disposable run dir; per-task attempt workspaces; original source never worker cwd |
| Evidence | append-only events, sealed digests, Markdown/HTML reports |
| Anchors | expected non-empty files + verifier exit 0 + source/artifact integrity |

### Explicit current limits

These are product facts, not bugs to hand-wave:

1. **No `depends_on` / stages.** All tasks are launched after strategy succeeds. There is no multi-wave DAG.
2. **No optional tasks.** Run status is `passed` only if strategy + **every** task + source/artifact integrity pass.
3. **No first-class reduce node.** Flatten/dedupe/merge must be either:
   - a normal task with deterministic verifiers, or
   - pure code inside a verifier / external script invoked by argv.
4. **No model judge as pass authority.** Judges may write findings artifacts; only argv verifiers decide pass/fail.
5. **No outer-loop authority.** `prove` never merges, labels issues, deploys, or applies `loop:agent-ready`.

These limits are good defaults. Graph patterns should exploit them first, then extend only where a real dependency or partial-success case is proven.

## Pattern catalog

### P0 — usable now, no schema change

#### P0.1 False-arrow audit (authoring rule)

**Rule:** two tasks share an edge only if task B consumes an artifact or finding produced by task A.

If both tasks only need the shared strategy + source snapshot, they are siblings, not a chain.

**Proof Runner mapping:**

- put independent work as sibling entries in `tasks[]`
- raise `max_parallel` only for truly independent work
- do not invent serial briefs (“then also…”) inside one task when the work is separable

**Author checklist before filing a proof plan:**

1. List candidate nodes on paper.
2. For every “and then”, ask: does the next step **read** the previous output?
3. Delete fake arrows.
4. Keep one strategy prompt that names the split and the merge criteria.
5. Give every leaf node its own artifact + argv verifier.

#### P0.2 Diamond with independent lenses

**Shape:**

```text
strategy
  ├─ lens-a worker → artifact + verifier
  ├─ lens-b worker → artifact + verifier
  └─ lens-c worker → artifact + verifier
```

**Current example already close:** `examples/proof-review.json`

- `contract-review` and `safety-review` fan out after one strategy
- each has structured artifact headings checked by argv
- safety lens overrides to a stronger model while contract stays on the cheap default

**Authoring rules:**

- one lens = one job = one primary artifact
- verifier checks structure and required claims, not vibes
- do not ask one worker to “also double-check the other lens”

#### P0.3 Deterministic reduce, not agent plumbing

**Rule:** if combining means flatten, sort, dedupe, count, or schema-validate, use code.

**Current-legal techniques:**

1. **Verifier-as-reduce** on a single worker artifact when that worker already owns the full set.
2. **Post-run operator script** outside `prove` that reads sealed task artifacts from a completed run directory.
3. **Later P1 reduce task** once dependencies exist.

Do **not** spawn a worker whose only job is “combine the markdown files” unless judgment is required and the output has a hard verifier.

#### P0.4 Cheap fan-out / expensive judgment

Already documented in `docs/model-routing.md`:

- one strong `strategy.model`
- cheap default `worker.model`
- override only hard lenses
- never let model confidence override verifier failure

Graph addition: treat **security / authority / provenance** lenses as the default expensive overrides; treat extraction/classification as cheap.

#### P0.5 Negative tests for “done”

Every node needs a verifier that can fail.

Minimum viable verifier classes:

| Class | Example |
| --- | --- |
| Existence | expected file non-empty (built-in) |
| Structure | required headings/keys present |
| Exactness | checksum / exact string / JSON schema |
| Behavioral | `pytest` / CLI probe on produced artifact |
| Negative | assert forbidden claim/path/secret marker absent |

A node without a red-capable check is not a graph node; it is a hope.

### P1 — small schema/runtime extensions after pilot

Only open these after one successful outer-loop pilot and a human-approved issue.

#### P1.1 Optional task outcomes (`on_failure`)

**Problem:** diamond fan-in currently fails the whole run if one lens fails. That is correct for release gates, wrong for “collect what you can” discovery sweeps.

**Proposal:**

```json
{
  "id": "route-auth-scan",
  "brief": "...",
  "expected_files": ["findings.json"],
  "verifiers": [{"argv": ["python3", "verify_findings.py"]}],
  "on_failure": "fail_run"
}
```

Allowed values:

- `fail_run` (default; current behavior)
- `drop` — task marks `failed_dropped`; run may still pass if required tasks pass
- `require_review` — run becomes `needs_review` rather than hard pass (report-only signal; still no merge authority)

**Invariants:**

- security/authority tasks cannot use `drop` unless the manifest sets an explicit `allow_drop_security: true` top-level break-glass flag defaulting false
- dropped tasks still seal evidence
- reports must list dropped/failed nodes prominently

#### P1.2 Explicit dependencies (`needs`)

**Problem:** true diamonds with a synthesize node need wave-2 execution after wave-1 artifacts exist.

**Proposal:**

```json
{
  "id": "synthesize",
  "needs": ["contract-review", "safety-review"],
  "brief": "Read only the listed sibling artifacts and write synthesis.md ...",
  "expected_files": ["synthesis.md"],
  "inputs_from": {
    "contract-review": ["contract-review.md"],
    "safety-review": ["safety-review.md"]
  },
  "verifiers": [{"argv": ["python3", "verify_synthesis.py"]}]
}
```

**Runtime rules:**

1. Build a DAG from `needs`; reject cycles.
2. Schedule ready tasks only; preserve `max_parallel` within a wave.
3. Copy declared `inputs_from` artifacts read-only into the dependent task workspace.
4. If a needed upstream used `on_failure: drop` and dropped, dependents either skip or fail according to `if_upstream_dropped`: `skip` | `fail` (default `fail`).
5. Workers still cannot see undeclared sibling outputs.

This is the minimum real-edge primitive. Do not add a general workflow language.

#### P1.3 Code reduce steps (`reduce` nodes)

**Problem:** agent-merge is expensive and weakly typed for flatten/dedupe.

**Proposal:** allow a non-model node type:

```json
{
  "id": "dedupe-findings",
  "type": "reduce",
  "needs": ["scan-a", "scan-b", "scan-c"],
  "argv": ["python3", "dedupe_findings.py"],
  "expected_files": ["findings.deduped.json"],
  "verifiers": [{"argv": ["python3", "verify_deduped.py"]}]
}
```

**Rules:**

- `type` defaults to `worker` (current tasks)
- `reduce` nodes run argv in the air-gapped verifier style, not via Hermes/OpenClaw chat
- no model field allowed on reduce nodes
- still require expected files + verifier
- use for plumbing only

#### P1.4 Perspective-diverse review pack (outer-loop adjacent)

For large PR review, keep `templeton-loop-review` as the authority role, but allow an optional **inner** proof plan that produces lens artifacts the reviewer must read:

- `correctness.md`
- `security.md`
- `reproduce.md`
- `synthesis.md` (reduce or judge-authored, still argv-gated)

The outer reviewer remains:

- fresh context
- SHA-pinned
- report-only
- unable to merge

Do not collapse builder self-check into final review.

#### P1.5 Loop-until-dry discovery (bounded cycle)

For unknown-size sweeps only (bug hunt, secret sweep, dead link crawl):

```text
wave n finders → reduce/dedupe against all_seen → verify survivors →
if new_confirmed == 0 for K consecutive waves: stop else wave n+1
```

**Hard caps required in manifest:**

- `max_waves`
- `max_total_tasks`
- `max_wall_seconds`
- `stop_after_empty_waves` (default 2)

**Critical rule from the graph notes:** dedupe against **everything seen**, including rejected findings, or the cycle rediscovers dead ends forever.

This should not ship in the first dependency PR. It is a separate issue after `needs` + `reduce` exist.

## Anti-patterns (reject)

1. **Graph as branding** — renaming Templeton Loop without new enforceable edges.
2. **Agent plumbing** — model calls for sort/dedupe/format.
3. **Self-grading** — worker confidence or strategy prose overriding verifier failure.
4. **Fake barriers** — serializing independent lenses “for cleanliness.”
5. **Unanchored watcher graphs** — loops that only check other loops’ reports.
6. **Authority leakage** — any path from prove/review to merge, deploy, publish, or `loop:agent-ready`.
7. **Graph everything** — one-off debug stays a single agent loop until the shape is stable enough to promote.

## Mapping to outer-loop roles

| Role | Graph job |
| --- | --- |
| `templeton-loop-spec` | define nodes, edges, anchors, and non-goals in the issue contract |
| `templeton-loop-plan-review` | false-arrow audit + missing verifier/anchor critique before approval |
| `templeton-loop-build` | implement one bounded issue; may run a proof plan as evidence |
| `templeton-loop-prove` | execute inner graph; seal evidence |
| `templeton-loop-review` | independent skeptic on exact SHA + CI + evidence |
| `templeton-loop-qa` | report-only contract/proof replay checks |
| `templeton-loop-status` | expose blocked/missing proof/review signals to Tony |
| Tony | last yes on agent-ready and merge |

## Worked examples against current schema

### Example A — adversarial doc/review diamond (works today)

Already represented by `examples/proof-review.json`:

- strategy once
- parallel contract + safety lenses
- structural argv verifiers
- safety lens model override

**Improve without schema changes:**

- add a third `reproduce-claims` lens only if claims are mechanically checkable
- tighten verifiers to assert forbidden phrases (“implemented”, “tested in prod”) when snapshot is docs-only
- keep `max_parallel` equal to independent lens count

### Example B — multi-file port / translation diamond (works today if files independent)

```json
{
  "version": 1,
  "name": "port-module-files",
  "source_paths": ["src/module_a.py", "src/module_b.py", "tests/"],
  "strategy": {
    "model": "STRONG",
    "prompt": "Split the port into per-file tasks. Each worker owns exactly one file and must keep public behavior stable."
  },
  "worker": {"model": "CHEAP"},
  "max_parallel": 2,
  "retries": 1,
  "tasks": [
    {
      "id": "port-a",
      "brief": "Port only module_a into out/module_a.py. Do not touch module_b.",
      "expected_files": ["out/module_a.py"],
      "verifiers": [
        {"argv": ["python3", "-m", "pytest", "tests/test_module_a.py", "-q"]}
      ]
    },
    {
      "id": "port-b",
      "brief": "Port only module_b into out/module_b.py. Do not touch module_a.",
      "expected_files": ["out/module_b.py"],
      "verifiers": [
        {"argv": ["python3", "-m", "pytest", "tests/test_module_b.py", "-q"]}
      ]
    }
  ]
}
```

Note: today’s worker writes artifacts in the task workspace; if the real verifier needs the original test tree, the manifest must copy those tests via `source_paths` and the verifier must run against the produced artifact layout. Do not assume implicit shared mutable state.

### Example C — synthesize-after-lenses (needs P1.2)

```text
strategy
  ├─ correctness-lens
  ├─ security-lens
  └─ reproduce-lens
        ↓ needs all three
     synthesis (worker or reduce)
        ↓
     argv verifier on synthesis.md / findings.json
```

Do not fake this today by telling three workers to “also write the final summary.” That recreates fake edges and duplicated judgment.

## Implementation plan (post-pilot, issue-sized)

> For Hermes later: implement only after Tony files/approves a `loop:agent-ready` issue. Prefer one vertical slice per issue.

### Issue 1 — Docs-only adoption (no runtime change)

**Goal:** make graph authoring rules discoverable.

**Files:**

- Keep this note at `docs/research/2026-08-14-graph-patterns-in-proof-runner.md`
- Add short pointer from `docs/model-routing.md` and README proof section
- Add `examples/proof-diamond-lenses.json` cloned from proof-review with a third lens only if verifiable

**Proof:**

```bash
.venv/bin/templeton-loop prove examples/proof-review.json --lint
.venv/bin/templeton-loop prove examples/proof-review.json --dry-run
pytest tests/test_proof.py -q
```

### Issue 2 — `needs` + read-only artifact inputs

**Goal:** real DAG edges for synthesize nodes.

**Files (expected):**

- `schemas/proof-manifest-v1.schema.json` or v2 bump if compatibility requires
- `templeton_loop/proof.py` scheduler + input staging
- `tests/test_proof.py` cycle rejection, wave scheduling, input isolation, upstream failure handling
- example synthesize manifest

**Acceptance criteria:**

1. Independent tasks still run concurrently.
2. Dependent task starts only after all `needs` succeed (default).
3. Dependent sees only declared `inputs_from` files, read-only.
4. Cycles fail at lint.
5. Undeclared sibling leakage fails the run.
6. Evidence records wave/attempt lineage.
7. No original source mutation.

### Issue 3 — `on_failure` drop/fail_run

**Goal:** failure containment for discovery graphs without weakening release graphs.

**Acceptance criteria:**

1. Default remains fail-run.
2. Dropped tasks seal evidence and appear in reports.
3. Release-style example manifests still fail closed.
4. Security tasks cannot silently drop.

### Issue 4 — `type: reduce` code nodes

**Goal:** free deterministic fan-in plumbing.

**Acceptance criteria:**

1. Reduce nodes never invoke a model.
2. Same argv sandbox posture as verifiers.
3. Still require expected files + verifier.
4. Example dedupe reduce with unit tests.

### Issue 5 — loop-until-dry controller

**Goal:** bounded unknown-size discovery only after Issues 2–4.

**Acceptance criteria:**

1. Hard caps enforced.
2. Dedupe against all seen, including rejected.
3. Stop after N empty waves.
4. Budget/time ceilings halt with evidence, not silent continue.

## Test matrix (for later implementation)

| Risk | Test |
| --- | --- |
| Fake dependency ignored | dependent starts before upstream artifact exists → fail |
| Cycle | `a needs b needs a` → lint error |
| Sibling leakage | task reads undeclared sibling path → fail |
| Optional drop abuse | security task with drop without break-glass → lint error |
| Reduce uses model fields | reject |
| Verifier mutation | passing verifier rewriting artifact → fail (already exists) |
| Retry bound | second failure stops (already exists) |
| Source mutation | declared source change fails run (already exists) |
| All-seen dedupe | rejected finding does not reappear as new work |

## Sequencing decision

1. **Now:** use this note as authoring guidance; keep outer pilot first.
2. **After pilot:** Issue 1 docs/examples only.
3. **Next runtime slice:** Issue 2 (`needs`) as the first real graph primitive.
4. **Then:** Issue 3/4 as needed by a concrete Templeton workload.
5. **Last:** Issue 5 cycles.

Do not block the first human-merge pilot on any P1 work.

## Non-goals

- Replacing GitHub Issues/PRs with a graph UI
- Importing LangGraph/AutoGen/Ringer/gstack runtime
- Hermes research cron graphs inside `prove`
- Automatic model substitution
- Worker self-approval
- Watched/scheduled outer coding loop

## Source confidence

- Local graph pack: `* IN PROGRESS/Graph Engineering.md`, Hermes graph clipping, loop-converge clipping
- Prior TKS decision 2026-07-27 (Yarchi article useful, not installable architecture)
- Live Templeton Proof Runner schema/runtime/tests as pinned above

Where graph essays and Templeton governance conflict, **Templeton governance wins**.

## Next action

Tony chooses one:

1. Run the already-required low-risk outer-loop pilot first (recommended default), or
2. File a `loop:spec-draft` issue for Issue 1 (docs/examples only), or
3. After pilot, open Issue 2 (`needs`) as the first runtime graph primitive.
