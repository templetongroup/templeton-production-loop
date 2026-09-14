# Release, GitHub, Evidence, and Handoffs

## Git and GitHub

Verify the repository, remote, branch, and authentication without exposing secrets. Inspect staged/unstaged/untracked work before edits and before commit. Use concise commits and evidence-backed pull requests. External posts, labels, pushes, issues, PRs, releases, and merges are side effects; perform only within the authorized scope and read back the exact target.

A coding task may be completed locally unless the operator requested publication. Opening a PR does not imply merge authority.

## Deployment

Deploy only when explicitly requested or unmistakably included in the task with a known safe workflow. Before deployment identify changed services, environment variables, migrations, dependencies, flags, rollback, monitoring, and post-deploy probes. Back up consequential state. Verify the live URL/API/job/user path and capture the deployment handle. Never report deployment from a local build alone.

## Evidence

Evidence must name exact commands and real outcomes. Use tests, lint/typecheck/build, smoke probes, browser screenshots, HTTP responses, CI links, commit SHAs, PR URLs, deployment IDs, and live probes as appropriate. Report partial or unavailable checks honestly.

## Handoffs

A durable handoff contains goal, repo/path, owner/requester, constraints, success criteria, allowed deployment scope, current branch/commit, changes made, files touched, commands and results, blockers, risk, and recommended next action. Redact secrets and keep transient logs out of durable knowledge systems.

## Operator response

Return a concise handoff with:

- Result
- Evidence
- Files changed
- Risk
- Next action

Do not leak scratch reasoning or narrate tool selection. Do not claim complete merely because a plan was executed; the requested artifact and proof must exist.
