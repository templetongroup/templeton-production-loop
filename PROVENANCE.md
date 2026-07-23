# Provenance and Independent Implementation

Templeton Coding Loop is original MIT-licensed work by The Templeton Group built on general software-engineering practices and an acknowledged adaptation of Alex Finn's MIT-licensed Finn-loop workflow concepts.

## Proof Runner v1.0

Before Proof Runner was implemented, the team evaluated Nate Jones Media LLC's Ringer project to understand the product category and licensing boundary. Ringer is distributed under PolyForm Shield 1.0.0, not an OSI-approved permissive license.

The Templeton implementation therefore follows these provenance rules:

- no Ringer source code was copied, translated, vendored, or used as an implementation base;
- no Ringer skill prose, templates, schemas, tests, fixtures, command names, UI code, screenshots, logos, or trade dress were incorporated;
- the implementation uses an independently written requirements document based on Templeton's existing workflow, Hermes Agent's public CLI, and general concepts such as explicit task contracts, model-role separation, isolated workspaces, external verification, bounded retries, and append-only evidence;
- the public interface, file layout, evidence format, tests, and documentation were created for this repository;
- the first implementation intentionally excludes Ringer-specific dashboards, hooks, self-update behavior, model scoreboards, engine registry, and native application.

A factual link to Ringer in review/history material is not an assertion of affiliation or endorsement. “Ringer” and “Ringside” remain names associated with their respective owner.

## gstack Concept Review

On 2026-07-23, the team reviewed Garry Tan's MIT-licensed `garrytan/gstack` repository at pinned commit `a3259400a366593e0c909dd9ac3e59752efd2488` as a source of workflow concepts and counterexamples.

The review produced independently written Templeton requirements around runtime capability enforcement, model-route benchmarking, test/eval coverage, host adapters, pre-approval contract critique, evidence-normalized review, report-only QA, and deterministic data-boundary checks. No gstack implementation code, skill prose, templates, schemas, tests, or assets were copied into Templeton by that review.

If a future contribution copies or vendors a substantial portion of gstack code or prose, it must identify the exact source files and commit and retain the upstream MIT copyright and permission notice.

Contributors must certify that submissions are their own work or are compatible with this repository's MIT license. Do not submit code or protected assets copied from source-available or incompatible projects.
