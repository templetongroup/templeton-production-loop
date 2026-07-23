---
name: templeton-loop-build
description: Claim one human-approved GitHub issue, implement its exact contract in an isolated Hermes worktree, verify it, and open a PR. One invocation performs one bounded pass.
---

# Templeton Loop — Build

One pass repairs one PR carrying `loop:changes-requested`, or builds one approved issue. Never merge or deploy.

## 0. Preflight

- Confirm the intended GitHub repository and reachable `origin`.
- Detect the default branch with `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`.
- Require a clean current worktree. If Hermes launched this pass with `--worktree`, keep its existing `hermes/...` branch; do not create or check out another branch.
- Read repository instructions and commands before editing.

## 1. Repair queue first

List open PRs labeled `loop:changes-requested`. Skip `loop:needs-human-review` and `loop:stuck`. Choose the least recently updated. Read the linked GitHub issue and latest `Templeton Loop review of COMMIT_SHA` verdict. Fix only must-fix findings, rerun relevant checks, push, remove `loop:changes-requested`, and comment with evidence. End the pass.

If a requested fix crosses a non-goal or requires product judgment, add `loop:needs-human-review`, remove `loop:changes-requested`, post one precise question, and stop.

## 2. Pick and claim

If the invocation names an issue, verify it still meets every condition. Otherwise list open GitHub issues that are:

- labeled `loop:agent-ready`;
- not labeled `loop:blocked` or `loop:building`;
- unassigned; and
- not blocked by an open dependency named in the issue.

Choose priority P0→P3, then oldest first. Claim before deep work by assigning `@me`, adding `loop:building`, and removing `loop:spec-draft`. Re-fetch immediately. If the state changed or another assignee owns it, release your claim and stop.

Only one builder loop may run per repository. GitHub assignment is a cooperative lock, not an atomic distributed lease.

## 3. Read the contract

Read the full issue and comments. Compare every `AC-N` to every `NG-N`. Implement only the acceptance criteria; non-goals are binding. If the contract is ambiguous, contradictory, or blocked, follow the blocked path instead of guessing.

## 4. Build and verify

- Work from the latest remote default branch.
- Preserve existing architecture, style, and unrelated behavior.
- Add tests at the behavioral seam for changed logic, data flow, permissions, integrations, or visible behavior.
- Run the narrowest trustworthy tests, then relevant lint, typecheck, and build checks.
- Review `git diff`, `git status`, and changed-file scope. Stop on unrelated work or secret-like output.

## 5. Ship a proposal

Commit and push the current branch. Open a PR whose body includes:

- `Closes #ISSUE_NUMBER`;
- what changed and why;
- one evidence line per `AC-N`;
- one preservation line per `NG-N`;
- `Other behavior changes: None`;
- exact automated checks and results;
- numbered manual verification steps;
- risk and rollback;
- deployment status: `Not deployed` unless Tony explicitly requested deployment.

Add `loop:awaiting-review` to the PR. Comment the PR URL on the issue. Remove `loop:building` from the issue but leave it assigned while the PR is open. Never merge, enable auto-merge, deploy, or mutate production.

## 6. Blocked path

Comment one concrete question with options, the recommended choice, and affected `AC-N`. Add `loop:blocked`, remove `loop:building`, unassign yourself, and stop. Leave `loop:agent-ready` so the issue re-enters only after a human answers and removes `loop:blocked`.

## Failure budget

A PR may receive at most two builder repair rounds. On a third unresolved must-fix verdict, add `loop:stuck`, remove `loop:changes-requested`, add `loop:needs-human-review`, and stop.
