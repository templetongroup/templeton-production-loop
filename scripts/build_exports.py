#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
STAGE = DIST / "stage"
VERSION = "1.1.0"
RUNTIMES = ("hermes", "openclaw")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256sums(checksum_path: Path, directory: Path) -> dict[str, str]:
    """Verify the detached archive digests before any archive is unpacked."""

    records: dict[str, str] = {}
    for number, line in enumerate(checksum_path.read_text(encoding="utf-8").splitlines(), start=1):
        if "  " not in line:
            raise RuntimeError(f"Malformed SHA256SUMS line {number}")
        digest, name = line.split("  ", 1)
        if (
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not name
            or Path(name).name != name
        ):
            raise RuntimeError(f"Unsafe SHA256SUMS line {number}")
        if name in records:
            raise RuntimeError(f"Duplicate SHA256SUMS entry: {name}")
        archive = directory / name
        if not archive.is_file() or archive.is_symlink():
            raise RuntimeError(f"Missing or unsafe release archive: {name}")
        actual = sha256(archive)
        if actual != digest:
            raise RuntimeError(f"External SHA-256 mismatch: {name}")
        records[name] = digest
    if not records:
        raise RuntimeError("SHA256SUMS must contain at least one archive")
    return records


def reject_symlinks(root: Path) -> None:
    """Reject links and non-regular filesystem objects without following them."""

    pending = [root]
    while pending:
        current = pending.pop()
        mode = current.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise RuntimeError(f"Release tree contains a symbolic link: {current}")
        if stat.S_ISDIR(mode):
            pending.extend(current / entry.name for entry in os.scandir(current))
        elif not stat.S_ISREG(mode):
            raise RuntimeError(f"Release tree contains a non-regular file: {current}")


def copy_regular_file(source: Path, destination: Path) -> None:
    reject_symlinks(source)
    if not stat.S_ISREG(source.lstat().st_mode):
        raise RuntimeError(f"Release source is not a regular file: {source}")
    shutil.copy2(source, destination)
    reject_symlinks(destination)


def copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Required export source is missing: {source}")
    reject_symlinks(source)
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        symlinks=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )
    reject_symlinks(destination)


def runtime_pyproject(runtime: str) -> str:
    source = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    source = source.replace('name = "templeton-production-loop"', f'name = "templeton-production-loop-{runtime}"')
    source = source.replace(
        'description = "Human-gated GitHub production loop and runtime-neutral artifact proof runner"',
        f'description = "Templeton Production Loop {runtime.title()} edition"',
    )
    return source


def write_manifest(stage: Path, name: str, runtime: str) -> None:
    reject_symlinks(stage)
    records = []
    for path in sorted(stage.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Staged release contains a symbolic link: {path}")
        if path.is_file() and path.name not in {"MANIFEST.json", "MANIFEST.sha256"}:
            records.append(
                {
                    "path": path.relative_to(stage).as_posix(),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                    "mode": format(stat.S_IMODE(path.stat().st_mode), "04o"),
                }
            )
    manifest = {
        "schema_version": 1,
        "name": name,
        "version": VERSION,
        "runtime": runtime,
        "files": records,
    }
    manifest_path = stage / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [f"{record['sha256']}  {record['path']}" for record in records]
    lines.append(f"{sha256(manifest_path)}  MANIFEST.json")
    (stage / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ci(stage: Path) -> None:
    workflow = stage / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        """name: CI
on:
  push:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    env:
      PIP_DISABLE_PIP_VERSION_CHECK: "1"
      PYTHONDONTWRITEBYTECODE: "1"
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7
        with:
          python-version: '3.11'
      - run: python exports/validate_bundle.py
      - run: python -m pip install --require-hashes -r requirements-ci.lock
      - run: python -m pip install --no-build-isolation --no-deps .
      - name: Test without network access
        run: sudo -E unshare --net "$(command -v python)" -m pytest -q -p no:cacheprovider
      - name: Compile without network access
        run: sudo -E unshare --net "$(command -v python)" -m compileall -q templeton_loop tests scripts
""",
        encoding="utf-8",
    )


def normalize_modes(stage: Path) -> None:
    for path in sorted(stage.rglob("*")):
        if path.is_dir():
            path.chmod(0o755)
        elif path.is_file():
            executable = path.suffix == ".py" and path.read_bytes().startswith(b"#!")
            path.chmod(0o755 if executable else 0o644)


def stage_bundle(runtime: str) -> tuple[str, Path]:
    if runtime not in RUNTIMES:
        raise ValueError(f"Unsupported release runtime: {runtime}")
    name = f"templeton-production-loop-{runtime}-v{VERSION}"
    stage = STAGE / name
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)

    copy_tree(ROOT / "templeton_loop", stage / "templeton_loop")
    copy_tree(ROOT / "tests", stage / "tests")
    # Release-generator tests exercise both editions and stay in the canonical repository.
    (stage / "tests" / "test_exports.py").unlink(missing_ok=True)
    (stage / "tests" / "test_release_archives.py").unlink(missing_ok=True)
    copy_tree(ROOT / "scripts", stage / "scripts")
    (stage / "scripts" / "build_exports.py").unlink(missing_ok=True)
    copy_tree(ROOT / "schemas", stage / "schemas")
    copy_tree(ROOT / "docs", stage / "docs")
    copy_tree(ROOT / "examples", stage / "examples")
    copy_tree(ROOT / "exports" / runtime, stage)

    skill_source = ROOT / ("skills-openclaw" if runtime == "openclaw" else "skills")
    skill_destination = stage / ("skills-openclaw" if runtime == "openclaw" else "skills")
    copy_tree(skill_source, skill_destination)
    copy_tree(skill_source, stage / "templeton_loop" / "resources" / "skills")

    for filename in ("LICENSE", "SECURITY.md", "PROVENANCE.md", "CONTRIBUTING.md", "CHANGELOG.md"):
        copy_regular_file(ROOT / filename, stage / filename)
    copy_regular_file(ROOT / "requirements-ci.lock", stage / "requirements-ci.lock")
    (stage / "exports").mkdir(parents=True, exist_ok=True)
    copy_regular_file(ROOT / "exports" / "validate_bundle.py", stage / "exports" / "validate_bundle.py")

    (stage / "templeton_loop" / "edition.py").write_text(
        "from __future__ import annotations\n\n"
        "# Fixed by the release generator; this standalone repository cannot switch runtimes.\n"
        f"EDITION: str | None = {runtime!r}\n",
        encoding="utf-8",
    )
    (stage / "pyproject.toml").write_text(runtime_pyproject(runtime), encoding="utf-8")
    (stage / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    (stage / "THIRD_PARTY_NOTICES.md").write_text(
        "# Third-Party Notices\n\n"
        "Templeton Production Loop is an MIT-licensed adaptation of Alex Finn's Finn-loop: "
        "https://github.com/finna/Finn-loop\n\n"
        "The guided-interview behavior in `templeton-loop-spec` adapts concepts from "
        "Matt Pocock's MIT-licensed `grill-me`, `grilling`, and `grill-with-docs` skills "
        "at commit 2ab958093e83e0ec752e6c1c5932da465bf23e0c: "
        "https://github.com/mattpocock/skills\n\n"
        "MIT License\n\n"
        "Copyright (c) 2026 Matt Pocock\n\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy "
        "of this software and associated documentation files (the \"Software\"), to deal "
        "in the Software without restriction, including without limitation the rights "
        "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell "
        "copies of the Software, and to permit persons to whom the Software is furnished "
        "to do so, subject to the following conditions:\n\n"
        "The above copyright notice and this permission notice shall be included in all "
        "copies or substantial portions of the Software.\n\n"
        "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR "
        "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, "
        "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE "
        "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER "
        "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, "
        "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n\n"
        "Linear-specific state was replaced with GitHub Issues. This edition targets "
        f"{runtime.title()}. No credentials are included. Templeton Proof Runner v1.0 "
        "contains no Ringer- or gstack-derived code or assets.\n",
        encoding="utf-8",
    )
    write_ci(stage)
    normalize_modes(stage)
    write_manifest(stage, name, runtime)
    return name, stage


def archive_bundle(name: str, stage: Path) -> Path:
    reject_symlinks(stage)
    archive = DIST / f"{name}.zip"
    if archive.exists():
        archive.unlink()
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "315532800"))
    fixed = datetime.fromtimestamp(max(epoch, 315532800), tz=timezone.utc)
    date_time = (fixed.year, fixed.month, fixed.day, fixed.hour, fixed.minute, fixed.second)
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, strict_timestamps=True
    ) as bundle:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(
                    f"{name}/{path.relative_to(stage).as_posix()}", date_time=date_time
                )
                info.create_system = 3
                mode = 0o755 if path.suffix == ".py" and path.read_bytes().startswith(b"#!") else 0o644
                info.external_attr = (stat.S_IFREG | mode) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                bundle.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return archive


def main() -> int:
    DIST.mkdir(parents=True, exist_ok=True)
    for stale in DIST.glob("templeton-production-loop-*-v*.zip"):
        stale.unlink()
    (DIST / "SHA256SUMS").unlink(missing_ok=True)
    (DIST / "exports.json").unlink(missing_ok=True)
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    archives: list[Path] = []
    for runtime in RUNTIMES:
        name, stage = stage_bundle(runtime)
        subprocess.run(
            [sys.executable, str(stage / "exports" / "validate_bundle.py")],
            cwd=stage,
            check=True,
        )
        archives.append(archive_bundle(name, stage))

    checksum_lines = [f"{sha256(path)}  {path.name}" for path in archives]
    checksum_path = DIST / "SHA256SUMS"
    checksum_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    verified = verify_sha256sums(checksum_path, DIST)
    if set(verified) != {path.name for path in archives}:
        raise RuntimeError("SHA256SUMS does not match the complete generated archive set")
    for line in checksum_lines:
        print(line)
    return 0


def release_output_inventory(root: Path) -> dict[str, tuple[str, int, str]]:
    """Return an exact, non-following inventory of every generated output node."""

    try:
        root_mode = root.lstat().st_mode
    except FileNotFoundError as exc:
        raise RuntimeError(f"Release output directory is missing: {root}") from exc
    if not stat.S_ISDIR(root_mode) or root.is_symlink():
        raise RuntimeError(f"Release output root must be a real directory: {root}")
    inventory: dict[str, tuple[str, int, str]] = {}
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in sorted(entries, key=lambda item: item.name):
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                metadata = entry.stat(follow_symlinks=False)
                mode = metadata.st_mode
                permissions = stat.S_IMODE(mode)
                if stat.S_ISLNK(mode):
                    raise RuntimeError(f"Release outputs contain a symbolic link: {relative}")
                if stat.S_ISDIR(mode):
                    inventory[relative] = ("directory", permissions, "")
                    pending.append(path)
                elif stat.S_ISREG(mode):
                    inventory[relative] = ("file", permissions, sha256(path))
                else:
                    raise RuntimeError(
                        f"Release outputs contain a non-regular filesystem object: {relative}"
                    )
    return dict(sorted(inventory.items()))


def check_outputs() -> int:
    """Regenerate elsewhere and fail unless every checked-in/out release output is identical."""

    global DIST, STAGE
    original_dist, original_stage = DIST, STAGE
    original_inventory = release_output_inventory(original_dist)
    with tempfile.TemporaryDirectory(prefix="templeton-export-check-") as temporary:
        try:
            DIST = Path(temporary) / "dist"
            STAGE = DIST / "stage"
            main()
            fresh_inventory = release_output_inventory(DIST)
        finally:
            DIST, STAGE = original_dist, original_stage
    if original_inventory != fresh_inventory:
        original_paths = set(original_inventory)
        fresh_paths = set(fresh_inventory)
        added = sorted(original_paths - fresh_paths)
        missing = sorted(fresh_paths - original_paths)
        changed = sorted(
            path
            for path in original_paths & fresh_paths
            if original_inventory[path] != fresh_inventory[path]
        )
        raise RuntimeError(
            f"Release outputs are stale or inexact: "
            f"unexpected={added} missing={missing} changed={changed}"
        )
    print("TEMPLETON_LOOP_EXPORTS_CURRENT")
    return 0


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic Templeton runtime editions")
    parser.add_argument("--check", action="store_true", help="Fail if dist differs from a fresh build")
    args = parser.parse_args(argv)
    return check_outputs() if args.check else main()


if __name__ == "__main__":
    raise SystemExit(cli())
