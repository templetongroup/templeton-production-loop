from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "templeton_build_exports", ROOT / "scripts" / "build_exports.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(stage: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(stage / "exports" / "validate_bundle.py")],
        cwd=stage,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.fixture()
def staged_editions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    builder = load_builder()
    dist = tmp_path / "dist"
    monkeypatch.setattr(builder, "DIST", dist)
    monkeypatch.setattr(builder, "STAGE", dist / "stage")
    builder.STAGE.mkdir(parents=True)
    result: dict[str, Path] = {}
    for runtime in ("hermes", "openclaw"):
        _name, stage = builder.stage_bundle(runtime)
        result[runtime] = stage
    return result


def test_generated_editions_are_fixed_installable_and_valid(staged_editions: dict[str, Path]):
    for runtime, stage in staged_editions.items():
        result = validate(stage)
        assert result.returncode == 0, result.stderr or result.stdout
        assert f"runtime={runtime}" in result.stdout

        edition = (stage / "templeton_loop" / "edition.py").read_text(encoding="utf-8")
        assert f"EDITION: str | None = '{runtime}'" in edition
        project = (stage / "pyproject.toml").read_text(encoding="utf-8")
        assert f'name = "templeton-coding-loop-{runtime}"' in project
        assert 'version = "1.0.0"' in project

    hermes_help = subprocess.run(
        [sys.executable, "-m", "templeton_loop.cli", "--help"],
        cwd=staged_editions["hermes"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    openclaw_help = subprocess.run(
        [sys.executable, "-m", "templeton_loop.cli", "--help"],
        cwd=staged_editions["openclaw"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "prove" in hermes_help and "--runtime" not in hermes_help
    assert "prove" in openclaw_help and "--runtime" not in openclaw_help


def test_validator_rejects_modified_missing_extra_and_manifest_tampering(
    staged_editions: dict[str, Path], tmp_path: Path
):
    source = staged_editions["hermes"]
    cases = []

    modified = tmp_path / "modified"
    shutil.copytree(source, modified)
    (modified / "README.md").write_text("tampered\n", encoding="utf-8")
    cases.append(modified)

    missing = tmp_path / "missing"
    shutil.copytree(source, missing)
    (missing / "README.md").unlink()
    cases.append(missing)

    extra = tmp_path / "extra"
    shutil.copytree(source, extra)
    (extra / "unexpected.txt").write_text("extra\n", encoding="utf-8")
    cases.append(extra)

    manifest = tmp_path / "manifest"
    shutil.copytree(source, manifest)
    data = json.loads((manifest / "MANIFEST.json").read_text(encoding="utf-8"))
    data["runtime"] = "openclaw"
    (manifest / "MANIFEST.json").write_text(json.dumps(data), encoding="utf-8")
    cases.append(manifest)

    for case in cases:
        result = validate(case)
        assert result.returncode != 0, case.name


def test_validator_rejects_symlinks(staged_editions: dict[str, Path], tmp_path: Path):
    stage = tmp_path / "symlink"
    shutil.copytree(staged_editions["openclaw"], stage)
    link = stage / "README-link.md"
    try:
        link.symlink_to("README.md")
    except OSError:
        pytest.skip("symlinks unavailable")
    result = validate(stage)
    assert result.returncode != 0
    assert "symbolic link" in (result.stderr + result.stdout) or "extra=" in (
        result.stderr + result.stdout
    )


def test_validator_rejects_non_regular_files_before_reading(
    staged_editions: dict[str, Path], tmp_path: Path
):
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFOs unavailable")
    stage = tmp_path / "fifo"
    shutil.copytree(staged_editions["hermes"], stage)
    os.mkfifo(stage / "unexpected.pipe")
    result = validate(stage)
    assert result.returncode != 0
    assert "non-regular filesystem object" in (result.stderr + result.stdout)


def test_validator_accepts_only_matching_external_manifest_digest(
    staged_editions: dict[str, Path]
):
    stage = staged_editions["hermes"]
    digest = __import__("hashlib").sha256((stage / "MANIFEST.json").read_bytes()).hexdigest()
    validator = stage / "exports" / "validate_bundle.py"
    accepted = subprocess.run(
        [sys.executable, str(validator), "--expected-manifest-sha256", digest],
        cwd=stage,
        text=True,
        capture_output=True,
    )
    rejected = subprocess.run(
        [sys.executable, str(validator), "--expected-manifest-sha256", "0" * 64],
        cwd=stage,
        text=True,
        capture_output=True,
    )
    assert accepted.returncode == 0
    assert rejected.returncode != 0
    assert "externally authenticated digest" in (rejected.stderr + rejected.stdout)


def test_release_check_rejects_extra_nodes_symlinks_and_stage_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    builder = load_builder()
    dist = tmp_path / "dist"
    monkeypatch.setattr(builder, "DIST", dist)
    monkeypatch.setattr(builder, "STAGE", dist / "stage")
    builder.main()

    extra = dist / "templeton-coding-loop-hermes-v0.9.0.zip"
    extra.write_bytes(b"stale")
    with pytest.raises(RuntimeError, match="unexpected"):
        builder.check_outputs()
    extra.unlink()

    extra_regular = dist / "unexpected.txt"
    extra_regular.write_text("unexpected\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="unexpected"):
        builder.check_outputs()
    extra_regular.unlink()

    staged_readme = next((dist / "stage").glob("*/README.md"))
    staged_readme.write_text("stale stage\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="changed"):
        builder.check_outputs()
    builder.main()

    archive = dist / "templeton-coding-loop-hermes-v1.0.0.zip"
    external = tmp_path / "external.zip"
    shutil.copyfile(archive, external)
    archive.unlink()
    try:
        archive.symlink_to(external)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(RuntimeError, match="symbolic link"):
        builder.check_outputs()

    archive.unlink()
    builder.main()
    extra_link = dist / "unexpected-link"
    try:
        extra_link.symlink_to(dist / "SHA256SUMS")
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(RuntimeError, match="symbolic link"):
        builder.check_outputs()
