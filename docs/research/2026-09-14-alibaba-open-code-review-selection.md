# Alibaba Open Code Review — Templeton Selection

Date: 2026-09-14
Upstream: https://github.com/alibaba/open-code-review
Pinned inspection commit: `6e5cd8cf2578768b6c6d1fafa1d14f66801d5f2b`
License inspected: Apache License 2.0
Benchmark paper: https://arxiv.org/abs/2601.19494

## Decision

Adopt four independently written review controls inside Templeton Production Loop. Do not install, vendor, or require the OCR CLI, model runner, bundled prompts, ruleset, automatic installer, or default test-file exclusions.

1. Freeze a complete, status-bearing PR file inventory before model review. Require one reviewed or reasoned-skipped outcome per `(path, status)` and reconcile coverage in deterministic host code.
2. Review in two passes: local diff correctness first, then targeted repository context. Do not assume that retrieving more context always improves judgment.
3. For substantial diffs, use coverage-preserving semantic groups followed by a cross-group integration pass. Changed tests stay in scope.
4. Route checks by artifact risk and validate every candidate finding against the pinned diff and subject-file context before reporting.

## Templeton implementation boundary

- GitHub remains the durable issue, PR, CI, review, and human-merge surface.
- The trusted broker fetches the complete PR file inventory through paginated GitHub REST and records only path and status in the review scope.
- The model returns a per-file coverage ledger; host validation rejects missing, extra, duplicate, malformed, or reasonless-skipped entries.
- Complete coverage means every selected entry was reviewed. Any skipped entry produces `partial`, is written to the evidence ledger and review comment, and receives no terminal review label.
- The reviewer remains report-only and receives no merge, deploy, publication, payment, production, or credential authority.

## Why selective rather than wholesale

AACR-Bench contains 200 pull requests from 50 repositories across 10 languages and 1,505 expert-verified findings. Its results support both local and repository-context review but also show a material precision/recall trade-off and context noise. The upstream benchmark and performance claims are vendor-authored and were not independently reproduced in this evaluation.

The inspected OCR repository also had open issues involving incomplete-review success semantics, timeout exit status, staged-file coverage, path normalization, token-budget enforcement, and release provenance. Those findings make the CLI unsuitable as a Templeton merge gate without a separate pinned pilot and effect-based verification.

## Originality and attribution

Templeton's schema, broker behavior, prompts, tests, reporting format, safety boundaries, and skill prose were independently written for the existing Templeton architecture. No OCR implementation code, prompt text, templates, rules, assets, or generated output was copied. This note preserves the conceptual source and exact inspected commit.

## Fresh-review hardening

A fresh-context review of the first Templeton candidate found four failure modes. The candidate was hardened to:

- remove stale automated approval/change-request labels when a coverage run is partial, while preserving the awaiting-review state and any existing human-review gate;
- freeze and pass one head SHA, base SHA, inventory, and diff from context construction through broker validation and publication;
- structurally bound the untrusted envelope and fail closed if any diff or metadata would be truncated; and
- compare the paginated REST inventory against GitHub's independent `changedFiles` total, detecting the endpoint's 3,000-file cap.
