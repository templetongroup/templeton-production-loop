---
name: templeton-loop-review
description: Fresh-context review of one Templeton Loop PR against its linked GitHub issue, exact head SHA, repository rules, and required CI. Posts evidence labels but never changes code or merges.
---

# Templeton Loop — Review

One invocation reviews one PR. The reviewer must be a fresh Hermes session, separate from the builder context.

## 1. Find work

List open non-draft PRs. A PR needs review when its current head SHA has no comment beginning `Templeton Loop review of CURRENT_SHA`. Skip unchanged PRs already carrying one terminal label: `loop:approved`, `loop:changes-requested`, or `loop:needs-human-review`.

If the invocation names a PR, verify it still needs review. Never trust a stale queue snapshot.

## 2. Pin evidence

- Parse `Closes #N` from the PR body and fetch that GitHub issue plus comments. No valid linked issue is a must-fix finding.
- Read repository instructions, the full diff, and every changed file in context.
- Review against the issue's `AC-N` and `NG-N`, plus correctness, security, data loss, permissions, errors, concurrency, migration, maintainability, and regression risk inside scope.
- Do not propose unrelated improvements.

Must-fix findings begin with `[AC-N]`, `[DEFECT]`, `[SECURITY]`, or `[CI]`. If an AC fix requires an NG violation, record `[SCOPE-CONFLICT AC-N ↔ NG-N]` and escalate rather than prescribing code.

## 3. Check live merge evidence

Run:

```bash
gh pr view NUMBER --json headRefOid,mergeable,mergeStateStatus
gh pr checks NUMBER --required --json bucket,name,state,link
```

- Pending required checks or unknown mergeability: post no verdict and change no labels; a future pass retries.
- Failed required checks are `[CI]` findings.
- A conflict is a `[DEFECT]` finding.
- No required CI means `loop:needs-human-review`; never apply `loop:approved` without CI.
- Re-fetch the head SHA immediately before posting. If it changed, discard the review.

## 4. Post one verdict

```md
Templeton Loop review of COMMIT_SHA

CI: required checks passed | failed | not configured
Mergeability: clean | conflicting
Contract: GitHub issue #N

## Review

Summary: one or two sentences.

## 1. Must fix before merge

None.

## 2. Should fix soon

None.

## 3. Safe to merge

Yes — evidence is complete. Tony or an authorized human still makes the merge decision.
```

Set labels idempotently:

- clean contract + required CI green + mergeable: add `loop:approved`; remove `loop:awaiting-review` and `loop:changes-requested`;
- must-fix: add `loop:changes-requested`; remove `loop:approved` and `loop:awaiting-review`;
- scope conflict, high-risk path, missing CI, or policy uncertainty: add `loop:needs-human-review`; remove `loop:approved`, `loop:changes-requested`, and `loop:awaiting-review`.

Preserve any existing `loop:needs-human-review` unless a human explicitly resolved its reason.

## Hard limits

Never push code, edit the issue contract, merge, enable auto-merge, deploy, approve through GitHub's formal review API, or dismiss another review. Labels and one SHA-pinned comment are evidence only.
