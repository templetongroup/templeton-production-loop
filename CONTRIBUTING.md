# Contributing

Contributions are welcome when they preserve the project's human gates, verification model, security boundary, and independent provenance.

## Before opening a pull request

1. Open or reference a bounded issue describing the behavior and acceptance proof.
2. Keep changes focused and add tests at the public behavioral seam.
3. Create a development environment and run the release checks:

   ```bash
   python -m pip install -e '.[dev]'
   python -m pytest -q
   python -m compileall -q templeton_loop tests scripts
   git diff --check
   python scripts/build_exports.py
   python dist/stage/templeton-production-loop-hermes-v1.1.0/exports/validate_bundle.py
   python dist/stage/templeton-production-loop-openclaw-v1.1.0/exports/validate_bundle.py
   ```

4. Do not include credentials, private logs, generated run evidence, model transcripts, or local absolute paths.
5. Do not contribute code, prose, fixtures, templates, UI assets, or schemas copied from Ringer or another incompatibly licensed/source-available project. Read `PROVENANCE.md`.

## Developer Certificate of Origin

By adding a `Signed-off-by` line to each commit, you certify the [Developer Certificate of Origin 1.1](https://developercertificate.org/): you created the contribution or have the right to submit it under this project's MIT license.

```bash
git commit -s -m "type: concise description"
```

## Safety boundary

Model children receive no `.git` data or GitHub credentials. The report-only spec role receives no tools or repository workspace: the broker prepares and scans bounded context in the prompt, verifies policy before every turn, and returns a sink-checked issue packet without mutation. Build roles receive staged source trees. Children may propose bounded staged changes or report findings, but they do not run Git/GitHub effects or trusted verifiers. The deterministic host broker validates and applies accepted build changes, runs pinned container verifiers, and may push branches or open pull requests. Neither children nor the broker may merge, enable auto-merge, deploy, publish, purchase, or mutate production without explicit human authorization.
