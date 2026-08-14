#!/usr/bin/env python3
"""Validate one unpacked Templeton runtime bundle.

An independently authenticated archive or manifest digest is the external trust anchor.
This validator proves internal completeness and cross-consistency: exact file set,
manifest metadata, sizes, content hashes, and the detached hash of MANIFEST.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

ROOT = Path(__file__).resolve().parent.parent
CORE_SKILLS = {
    "templeton-loop-spec",
    "templeton-loop-plan-review",
    "templeton-loop-build",
    "templeton-loop-review",
    "templeton-loop-qa",
    "templeton-loop-status",
    "templeton-loop-prove",
}
HERMES_SKILLS = CORE_SKILLS
MANIFEST_NAMES = {"MANIFEST.json", "MANIFEST.sha256"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def fail(message: str) -> "NoReturn":
    raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(raw: Any, field: str) -> str:
    if not isinstance(raw, str) or not raw:
        fail(f"{field} must be a non-empty string")
    path = PurePosixPath(raw)
    if path.is_absolute() or raw.startswith("./") or "\\" in raw or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        fail(f"{field} is not a safe normalized relative path: {raw!r}")
    normalized = path.as_posix()
    if raw != normalized:
        fail(f"{field} is not normalized: {raw!r}")
    return normalized


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"Duplicate JSON object key: {key}")
        result[key] = value
    return result


def validate_tree_nodes() -> None:
    """Reject links, devices, sockets, and FIFOs before opening any bundle path."""

    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT).as_posix()
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            fail(f"Could not inspect bundle path {relative}: {exc}")
        if stat.S_ISLNK(mode):
            fail(f"Bundle contains a symbolic link: {relative}")
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            fail(f"Bundle contains a non-regular filesystem object: {relative}")


def load_manifest() -> dict[str, Any]:
    path = ROOT / "MANIFEST.json"
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Invalid MANIFEST.json: {exc}")
    required = {"schema_version", "name", "version", "runtime", "files"}
    if not isinstance(data, dict) or set(data) != required or data.get("schema_version") != 1:
        fail("MANIFEST.json has an unsupported shape or schema_version")
    if not isinstance(data["files"], list):
        fail("MANIFEST.json files must be an array")
    return data


def parse_shasums() -> dict[str, str]:
    path = ROOT / "MANIFEST.sha256"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        fail(f"Could not read MANIFEST.sha256: {exc}")
    if not lines:
        fail("MANIFEST.sha256 must not be empty")
    result: dict[str, str] = {}
    for number, line in enumerate(lines, start=1):
        if "  " not in line:
            fail(f"Malformed MANIFEST.sha256 line {number}")
        digest, raw_path = line.split("  ", 1)
        relative = safe_relative(raw_path, f"MANIFEST.sha256 line {number}")
        if not _SHA256_RE.fullmatch(digest):
            fail(f"Invalid SHA-256 on MANIFEST.sha256 line {number}")
        if relative in result:
            fail(f"Duplicate MANIFEST.sha256 path: {relative}")
        result[relative] = digest
    return result


def validate_integrity(manifest: dict[str, Any], shasums: dict[str, str]) -> None:
    records: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(manifest["files"]):
        if not isinstance(raw, dict) or set(raw) != {"path", "sha256", "bytes", "mode"}:
            fail(f"MANIFEST.json files[{index}] must contain exactly path, sha256, bytes, mode")
        relative = safe_relative(raw["path"], f"MANIFEST.json files[{index}].path")
        if relative in MANIFEST_NAMES:
            fail(f"Manifest files must not appear as ordinary records: {relative}")
        if relative in records:
            fail(f"Duplicate MANIFEST.json path: {relative}")
        if not isinstance(raw["sha256"], str) or not _SHA256_RE.fullmatch(raw["sha256"]):
            fail(f"Invalid SHA-256 for {relative}")
        if isinstance(raw["bytes"], bool) or not isinstance(raw["bytes"], int) or raw["bytes"] < 0:
            fail(f"Invalid byte count for {relative}")
        if raw["mode"] not in {"0644", "0755"}:
            fail(f"Invalid normalized file mode for {relative}")
        records[relative] = raw

    expected_shasum_paths = set(records) | {"MANIFEST.json"}
    if set(shasums) != expected_shasum_paths:
        missing = sorted(expected_shasum_paths - set(shasums))
        extra = sorted(set(shasums) - expected_shasum_paths)
        fail(f"MANIFEST.sha256 path set mismatch: missing={missing} extra={extra}")
    if shasums["MANIFEST.json"] != sha256(ROOT / "MANIFEST.json"):
        fail("MANIFEST.json digest does not match MANIFEST.sha256")

    actual: set[str] = set()
    for path in ROOT.rglob("*"):
        if ".git" in path.relative_to(ROOT).parts:
            continue
        if path.is_symlink():
            fail(f"Bundle contains a symbolic link: {path.relative_to(ROOT).as_posix()}")
        if path.is_file():
            actual.add(path.relative_to(ROOT).as_posix())
    expected_actual = set(records) | MANIFEST_NAMES
    if actual != expected_actual:
        fail(
            "Bundle file set mismatch: "
            f"missing={sorted(expected_actual - actual)} extra={sorted(actual - expected_actual)}"
        )

    for relative, record in sorted(records.items()):
        path = ROOT / relative
        if path.stat().st_size != record["bytes"]:
            fail(f"Byte count mismatch: {relative}")
        actual_mode = format(stat.S_IMODE(path.stat().st_mode), "04o")
        if actual_mode != record["mode"]:
            fail(f"File mode mismatch: {relative}")
        digest = sha256(path)
        if digest != record["sha256"]:
            fail(f"MANIFEST.json digest mismatch: {relative}")
        if digest != shasums[relative]:
            fail(f"MANIFEST.sha256 digest mismatch: {relative}")


def validate_runtime(manifest: dict[str, Any]) -> tuple[str, set[str]]:
    candidates = [ROOT / "skills", ROOT / "skills-openclaw"]
    present = [path for path in candidates if path.is_dir()]
    if len(present) != 1:
        fail(f"Expected exactly one runtime skill directory; found: {present}")
    skill_root = present[0]
    runtime = "openclaw" if skill_root.name == "skills-openclaw" else "hermes"
    expected = CORE_SKILLS if runtime == "openclaw" else HERMES_SKILLS

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    expected_name = f"templeton-production-loop-{runtime}-v{version}"
    if manifest["runtime"] != runtime or manifest["version"] != version or manifest["name"] != expected_name:
        fail(
            "Manifest identity mismatch: "
            f"expected name={expected_name!r} version={version!r} runtime={runtime!r}"
        )

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if pyproject.get("name") != f"templeton-production-loop-{runtime}" or pyproject.get("version") != version:
        fail("pyproject.toml identity does not match the bundle")
    init_text = (ROOT / "templeton_loop" / "__init__.py").read_text(encoding="utf-8")
    if f'__version__ = "{version}"' not in init_text:
        fail("templeton_loop.__version__ does not match VERSION")
    edition_text = (ROOT / "templeton_loop" / "edition.py").read_text(encoding="utf-8")
    if f"EDITION: str | None = {runtime!r}" not in edition_text:
        fail("Fixed edition does not match the bundle runtime")
    if version not in (ROOT / "README.md").read_text(encoding="utf-8"):
        fail("README version does not match VERSION")

    actual = {path.name for path in skill_root.iterdir() if path.is_dir()}
    if actual != expected:
        fail(f"Skill inventory mismatch: expected {sorted(expected)}, got {sorted(actual)}")
    return runtime, expected


def validate_skills(runtime: str, expected: set[str]) -> int:
    skill_root = ROOT / ("skills-openclaw" if runtime == "openclaw" else "skills")
    combined: dict[str, str] = {}
    for name in sorted(expected):
        path = skill_root / name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            fail(f"Missing YAML frontmatter: {path}")
        frontmatter = text.split("---\n", 2)[1]
        if not re.search(rf"^name:\s*{re.escape(name)}\s*$", frontmatter, re.MULTILINE):
            fail(f"Frontmatter name mismatch: {path}")
        if not re.search(r"^description:\s*\S", frontmatter, re.MULTILINE):
            fail(f"Missing description: {path}")
        combined[name] = text

    shipped_markdown = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(ROOT.rglob("*.md"))
    )
    forbidden_authority = (
        "Humans retain `loop:agent-ready`",
        "Human-approved contract ready for an agent",
        "awaiting human approval",
    )

    checks = {
        "spec human gate": "Never add `loop:agent-ready`" in combined["templeton-loop-spec"],
        "spec one-question interview": (
            "Ask exactly one decision question at a time" in combined["templeton-loop-spec"]
        ),
        "spec bounded research context": (
            "bounded, secret-filtered repository and research context"
            in combined["templeton-loop-spec"]
            and "Use only that bounded context" in combined["templeton-loop-spec"]
        ),
        "spec researched facts": (
            "Look up facts inside the supplied context" in combined["templeton-loop-spec"]
        ),
        "spec shared-understanding gate": (
            "Do not create or update an issue at any point" in combined["templeton-loop-spec"]
            and "shared understanding" in combined["templeton-loop-spec"]
        ),
        "spec report-only issue packet": (
            "Output an approved issue packet" in combined["templeton-loop-spec"]
            and "never runs `gh`" in combined["templeton-loop-spec"]
        ),
        "spec Tony-only agent-ready": "Tony alone may apply" in combined["templeton-loop-spec"],
        "spec broker-only invocation": (
            '<templeton-spec-broker schema="1">' in combined["templeton-loop-spec"]
            and "Refuse direct invocation" in combined["templeton-loop-spec"]
        ),
        "plan review advisory": "report-only" in combined["templeton-loop-plan-review"].lower(),
        "plan review Tony-only gate": "Tony alone owns approval" in combined["templeton-loop-plan-review"],
        "build no merge/deploy": "Never merge, enable auto-merge, deploy" in combined["templeton-loop-build"],
        "build retry cap": "at most two builder repair rounds" in combined["templeton-loop-build"],
        "review required CI": "gh pr checks NUMBER --required" in combined["templeton-loop-review"],
        "review no code push": "Never push code" in combined["templeton-loop-review"],
        "review SHA pin": "Templeton Loop review of COMMIT_SHA" in combined["templeton-loop-review"],
        "qa report only": "report-only" in combined["templeton-loop-qa"].lower(),
        "status read only": "never mutate" in combined["templeton-loop-status"].lower(),
    }
    prove = combined["templeton-loop-prove"]
    checks.update(
        {
            "prove trusted plan": "trusted plan" in prove.lower(),
            "prove no source edits": "never targets the original source tree" in prove,
            "prove no merge/deploy": "Never merge, deploy" in prove,
            "prove no hooks/update": "auto-update" in prove.lower() and "global hooks" in prove.lower(),
            "prove provenance": "Ringer-derived code or assets" in prove,
        }
    )
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    checks.update(
        {
            "Matt Pocock guided-interview pin": (
                "2ab958093e83e0ec752e6c1c5932da465bf23e0c" in notices
            ),
            "Matt Pocock architecture pin": (
                "8b78b531ab965735c5dc74f6f7a219e1e37326df" in notices
            ),
            "Matt Pocock copyright": "Copyright (c) 2026 Matt Pocock" in notices,
            "Matt Pocock MIT grant": "Permission is hereby granted, free of charge" in notices,
        }
    )
    specification = (ROOT / "templeton_loop" / "specification.py").read_text(encoding="utf-8")
    policy = (ROOT / "templeton_loop" / "policy.py").read_text(encoding="utf-8")
    runtime_source = (ROOT / "templeton_loop" / "runtime.py").read_text(encoding="utf-8")
    runtime_tests = (ROOT / "tests" / "test_runtime.py").read_text(encoding="utf-8")
    cli = (ROOT / "templeton_loop" / "cli.py").read_text(encoding="utf-8")
    workflow = (ROOT / "templeton_loop" / "workflow.py").read_text(encoding="utf-8")
    gitmeta = (ROOT / "templeton_loop" / "gitmeta.py").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.example.md").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    checks.update(
        {
            "brokered spec CLI": 'choices=("spec", "build", "review", "qa")' in cli,
            "spec context and transcript digests": (
                "spec-context-packet" in specification
                and "context_sha256" in specification
                and "spec-resumed-transcript" in specification
            ),
            "spec per-turn runtime preflight": "_preflight_spec_runtime(" in specification,
            "spec explicit confirmation gate": (
                "explicit broker confirmation" in specification and "--confirm" in cli
            ),
            "spec alternative tradeoffs": (
                "one to four objects with non-empty option and tradeoff" in specification
                and 'set(item) != {"option", "tradeoff"}' in specification
            ),
            "spec final sink check": 'sink="github-issue-packet"' in specification,
            "spec replay boundary": (
                'wrap_untrusted(\n        "spec-transcript"' in specification
                and "\\u003c/templeton-spec-transcript\\u003e" not in specification
            ),
            "linked-worktree metadata routing": (
                '"rev-parse"' in gitmeta
                and "--git-path" in gitmeta
                and "git_metadata_path" in specification
                and "git_metadata_path" in cli
                and "git_metadata_path" in workflow
                and ' / ".git" / "templeton-loop"' not in workflow
            ),
            "Tony-scoped shipped authority": (
                "Tony-approved contract ready for an agent" in cli
                and "awaiting Tony's approval" in cli
                and not any(phrase in shipped_markdown for phrase in forbidden_authority)
            ),
            "spec operator-file boundary": (
                "stat.S_ISLNK" in specification
                and "regular non-sensitive file" in specification
                and "spec-brief-file" in specification
                and "spec-user-answer" in specification
            ),
            "OpenClaw spec deny-all policy": (
                'denied.add("*")' in policy
                and 'sorted(required_openclaw_denies(role))' in policy
                and "find_and_verify_openclaw_agent" in runtime_source
                and "configured_policy_verified" in runtime_source
                and "workspaceMounts" in runtime_source
                and 'explained.get("elevated")' in runtime_source
            ),
            "OpenClaw installed CLI schema integration": (
                "OPENCLAW_CONFIG_PATH" in runtime_tests
                and "OPENCLAW_STATE_DIR" in runtime_tests
                and "supports_installed_cli_schema" in runtime_tests
            ),
            "shipped Tony-only gate": "Tony alone may apply `loop:agent-ready`" in agents,
            "shipped report-only filing contract": (
                "spec role returns an issue packet" in agents
                and "does not create issues or apply labels" in agents
            ),
            "supported 1.1 security line": "1.1.x is the supported release line" in security,
        }
    )

    optional = ROOT / "optional-skills" / "templeton-architecture-review" / "SKILL.md"
    if optional.is_file():
        optional_text = optional.read_text(encoding="utf-8")
        checks.update(
            {
                "optional architecture report-only": "report-only" in optional_text.lower(),
                "optional architecture no agent-ready": "loop:agent-ready" in optional_text
                and "Never" in optional_text,
                "optional architecture no source mutation": "edit source" in optional_text,
                "optional architecture outside core roles": (
                    "not one of the seven" in optional_text.lower()
                    or "outside" in optional_text.lower()
                ),
                "optional architecture upstream pin": (
                    "8b78b531ab965735c5dc74f6f7a219e1e37326df" in optional_text
                ),
            }
        )
    vendor_pin = ROOT / "third_party" / "mattpocock-skills" / "PINNED.md"
    if vendor_pin.is_file():
        pin_text = vendor_pin.read_text(encoding="utf-8")
        checks["vendored architecture pin file"] = (
            "8b78b531ab965735c5dc74f6f7a219e1e37326df" in pin_text
        )

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        fail("Safety contract validation failed: " + ", ".join(failed))
    return len(checks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-manifest-sha256",
        help="Externally authenticated SHA-256 digest of MANIFEST.json",
    )
    args = parser.parse_args(argv)
    validate_tree_nodes()
    if args.expected_manifest_sha256 is not None:
        if not _SHA256_RE.fullmatch(args.expected_manifest_sha256):
            fail("--expected-manifest-sha256 must be 64 lowercase hexadecimal characters")
        if sha256(ROOT / "MANIFEST.json") != args.expected_manifest_sha256:
            fail("MANIFEST.json does not match the externally authenticated digest")
    manifest = load_manifest()
    shasums = parse_shasums()
    validate_integrity(manifest, shasums)
    runtime, expected = validate_runtime(manifest)
    safety_checks = validate_skills(runtime, expected)
    print(
        f"TEMPLETON_LOOP_BUNDLE_OK runtime={runtime} skills={len(expected)} "
        f"safety_checks={safety_checks} files={len(manifest['files'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
