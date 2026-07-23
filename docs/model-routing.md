# Model Routing: Strategy First, Economical Execution

Templeton Proof Runner separates model roles instead of paying the strongest-model rate for every task.

## Three layers

1. **Strategy — one high-capability call**
   - The manifest's `strategy.model` should be the strongest reliable reasoning model available for the job.
   - It studies the copied source snapshot and produces one bounded strategy artifact.
   - The strategy is persisted before workers start and is included in every worker brief.
   - It does not execute tasks or decide whether artifacts passed.

2. **Execution — cheaper parallel workers**
   - `worker.model` is the economical default used for every task.
   - Independent tasks run concurrently up to `max_parallel`.
   - A task may set `model`, `provider`, or `profile` only when its workload justifies an override.
   - A retry normally uses the same worker route plus actual failure evidence. It is not generic “try again” prompting.

3. **Verification — deterministic air-gapped commands**
   - Verification does not call a model.
   - Declared files must exist and be non-empty.
   - Each `verifiers[].argv` command executes directly without a shell in a digest-pinned, network-disabled container and must return exit code 0 within its timeout.
   - A passing verifier that mutates a declared artifact is rejected.
   - Worker confidence and strategy quality never override a failed verifier.

## Why this saves money

The high-capability model sees the whole problem once, where architecture and decomposition have the highest leverage. Lower-cost models receive smaller, well-scoped tasks plus the same strategic context. Deterministic verification then catches weak execution without paying another model to grade its own work.

## Routing policy

- Model selection is explicit and visible in lint/dry-run output; the runner never silently substitutes a model.
- Use one strong strategist per run, not one per task.
- Keep the cheaper worker as the default. Override only tasks with demonstrated complexity or failure history.
- If a required model/provider/profile is unavailable, stop with evidence rather than falling back invisibly.
- Store model names with every attempt so later releases can recommend routes from local evidence without rewriting history.

## Evidence-based route recommendations

Version 1.0 records provider-neutral outcomes and exposes `templeton-loop route` for explainable recommendations after a configurable minimum sample count and pass-rate floor. `templeton-loop capability-coverage` checks whether configured candidates cover required task classes. Recommendations remain user-overridable and derive only from append-only verified outcomes; the router does not silently substitute a model.
