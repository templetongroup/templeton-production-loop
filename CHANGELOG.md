# Changelog

All notable changes to Templeton Coding Loop are documented here.

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
