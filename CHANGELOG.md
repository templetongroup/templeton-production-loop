# Changelog

All notable changes to Templeton Production Loop are documented here.

## Unreleased

### Added
- Optional architecture helper adapted from Matt Pocock's `improve-codebase-architecture` + `codebase-design` (pinned `8b78b531ab965735c5dc74f6f7a219e1e37326df`):
  - vendored sources in `third_party/mattpocock-skills/`
  - Templeton-native report-only wrapper `optional-skills/templeton-architecture-review/`
  - research note `docs/research/2026-08-14-mattpocock-improve-codebase-architecture.md`
- Selected Matt Pocock productivity helpers (same pin), vendored under `third_party/mattpocock-skills/productivity/` with Templeton wrappers:
  - `optional-skills/templeton-grill`
  - `optional-skills/templeton-handoff`
  - `optional-skills/templeton-questionnaire`
  - `optional-skills/templeton-wait-what`
  - `optional-skills/templeton-writing-for-agents`
  - research note `docs/research/2026-08-14-mattpocock-productivity-selection.md`
- Optional helpers are not part of the seven outer-loop authority roles and cannot apply `loop:agent-ready`. `teach` was evaluated and not incorporated.

### Changed
- Public product name is **Templeton Production Loop** (`templeton-production-loop`); CLI remains `templeton-loop`.
- Added `docs/research/2026-08-14-graph-patterns-in-proof-runner.md` for inner Proof Runner graph patterns.

## 1.1.0 — 2026-07-30

### Added

- A trusted-host-grounded guided interview before issue drafting: one decision at a time, recommended answers, structured alternative/trade-off pairs, dependent decision traversal, collaborative idea generation, and periodic understanding checks.
- An explicit shared-understanding gate that prevents issue-packet generation, source changes, or builder startup until Tony confirms the summarized project contract.
- A first-class, one-turn-at-a-time `templeton-loop run spec` broker that prepares and scans bounded context, persists digest-checked interview state, re-verifies runtime policy before every model call, requires explicit `--confirm`, and scans the final report-only issue packet without writing GitHub state.
- Untrusted-envelope encoding for replayed model transcripts and Git-resolved state paths that support normal repositories and linked worktrees.
- Pinned provenance and generated-edition MIT attribution for the adapted `mattpocock/skills` interview concepts.

### Changed

- `templeton-loop-spec` now runs report-only from bounded, secret-filtered host context, shows the exact issue packet only after the interview gate, and hands the approved packet back for sink-checked filing. The role never mutates GitHub or source state, and Tony alone may apply `loop:agent-ready`.
- GitHub label metadata, bundled plans, and release validation now identify Tony—not a generic human—as the sole `loop:agent-ready` authority.
- Hermes spec turns run in safe mode with only `todo`; OpenClaw spec turns use an explicit wildcard deny-all policy (`tools.deny: ["*"]`), a fresh preflight-verified session, and an empty read-only workspace. Direct skill invocation is unsupported and must refuse prompts without the broker envelope.
- Standalone Hermes and OpenClaw package versions advance to 1.1.0; all existing merge, deployment, credential, review, QA, and runtime-authority boundaries remain unchanged.
- OpenClaw preflight now validates the actual 2026.7.1 `sandbox explain` schema, exact writable/read-only mount routing, top-level elevated state, and sandbox tool allow/deny envelope, with an isolated installed-CLI integration test. Documentation advertises only the implemented `--answer-file` continuation option.
- Generated-bundle CI now installs hash-locked test dependencies in an isolated virtual environment, asserts that `templeton_loop` resolves inside that environment, and runs each edition's shipped tests with the same interpreter; edition-neutral parser coverage explicitly targets the source parser.

## 1.0.0 — 2026-07-23

### Added

- Fixed-runtime standalone Hermes and OpenClaw editions.
- Secret-filtered source staging and exact SHA-256 tree inventories.
- Fail-closed Hermes and OpenClaw Docker policy preflight.
- Air-gapped, non-root, capability-dropped verifier containers.
- Typed untrusted-data envelopes and deterministic external-sink limits.
- Hash-chained run ledgers, normalized findings, evidence freshness, routing metrics, capability coverage, and health summaries.
- Independent strategy, build, review, QA, and bounded repair roles.
- Exact bundle manifests, detached checksums, tamper detection, and generated-output validation.

### Changed

- Build agents edit disposable staged trees; the deterministic host broker alone applies validated changes and performs GitHub effects.
- QA and review roles are report-only and operate from clean read-only snapshots.
- Runtime selection is fixed in each standalone edition rather than exposed as a public CLI switch.
- OpenClaw proof execution requires an exact, existing, empty one-shot agent workspace and refuses reuse while prior-run evidence remains.

### Security

- Child agents receive no GitHub, cloud, registry, deployment, payment, or production credentials.
- Child terminal execution requires an air-gapped Docker sandbox with a digest-pinned image.
- Secret-positive sink payloads are blocked; blocked evidence records store only rule names, byte count, and content hash.
- Completed proof runs seal artifact, verifier-output, and report digests into the hash-chained ledger so post-run evidence changes are detected.

## 0.3.0 — unreleased development line

- Introduced the Hermes-native artifact proof runner. Superseded by the hardened 1.0.0 release.

## 0.2.0

- Added the initial GitHub issue → build → review → human merge workflow and portable runtime bundles.
