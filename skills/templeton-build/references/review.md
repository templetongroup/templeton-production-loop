# Internal Production Loop Procedure

This is an internal least-authority broker mode of `templeton-build`, not a standalone operator skill. The explicit broker envelope and host policy determine authority.

# Templeton Loop Review

Use the fixed-edition CLI from a trusted host session:

```bash
templeton-loop run review --repo OWNER/REPO
```

For OpenClaw, also pass the configured `--agent AGENT_ID`. This mode is report-only. The host broker stages the PR head without `.git`, verifies a read-only air-gapped child runtime, validates normalized findings, checks evidence freshness, and owns the final GitHub comment and labels.

Required CI remains a host-side check equivalent to `gh pr checks NUMBER --required`. The broker pins each verdict to the current comparison using `Templeton Loop review of HEAD_SHA against BASE_SHA`; a changed head or base invalidates prior approval. No required CI means `loop:needs-human-review`; failed required CI means `loop:changes-requested`.

## Enforced review controls

- The trusted host freezes the head SHA, base SHA, complete status-bearing inventory, and diff as one comparison before dispatch. The reviewer returns a **frozen changed-file coverage manifest** with exactly one `reviewed` or reasoned `skipped` outcome for every `(path, status)` entry. The broker independently reconciles the GitHub changed-file count, inventory count, and review outcomes.
- A partial or skipped run records evidence but applies no new terminal verdict. The broker removes stale `loop:approved` and `loop:changes-requested` labels, adds or preserves `loop:awaiting-review`, and preserves an existing `loop:needs-human-review` gate. Any head/base change aborts publication.
- The comment's second line is a broker-controlled `Review-State: verdict=<approved|changes-requested|needs-human-review|awaiting-review>; coverage=<complete|partial|skipped>` record written before model-controlled text. A passing record is exactly `Review-State: verdict=approved; coverage=complete`. Queue scans trust review evidence only from the authenticated broker actor and settle a complete review only when its exact expected terminal label is present without an incompatible automated label. Partial, skipped, missing, malformed, mismatched, or untrusted state always requeues.
- Start with a local diff pass for every changed file, then retrieve only the repository context needed to verify callers, contracts, schemas, configuration, and dependencies. More context is not automatically better.
- For a substantial diff that fits the trusted context boundary, partition every file into exactly one bounded primary set of **semantic groups**, review each group, then perform one cross-group integration pass. Changed tests remain in scope. Any diff or metadata truncation fails closed and requires a dedicated reviewed batch or smaller PR.
- Route **artifact-specific** risks instead of pasting one universal checklist: CI permissions and untrusted events; dependency provenance and lockfiles; schema/migration compatibility, reversibility, and data preservation; template encoding; and config/i18n parity.
- Before reporting, recheck each finding against the pinned diff and subject-file context, deduplicate the underlying defect, and verify any quoted **changed-code anchor** exists. Use a file- or contract-level location instead of inventing a line, and drop unsupported or preference-only findings.

Never push code, edit source, merge, deploy, publish, or expose credentials. Findings must describe a concrete failure scenario and source evidence; weak or stale evidence is rejected.