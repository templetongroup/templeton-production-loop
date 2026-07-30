from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "templeton_release_builder", ROOT / "scripts" / "build_exports.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_to_stage_parity_is_explicit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    builder = load_builder()
    dist = tmp_path / "dist"
    monkeypatch.setattr(builder, "DIST", dist)
    monkeypatch.setattr(builder, "STAGE", dist / "stage")
    for runtime in ("hermes", "openclaw"):
        _name, stage = builder.stage_bundle(runtime)
        for source in sorted((ROOT / "templeton_loop").glob("*.py")):
            if source.name != "edition.py":
                assert (stage / "templeton_loop" / source.name).read_bytes() == source.read_bytes()
        skills = ROOT / ("skills" if runtime == "hermes" else "skills-openclaw")
        for source in sorted(skills.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(skills)
            assert (stage / skills.name / relative).read_bytes() == source.read_bytes()
            packaged = stage / "templeton_loop" / "resources" / "skills" / relative
            assert packaged.read_bytes() == source.read_bytes()


def test_archives_are_reproducible_and_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    builder = load_builder()
    dist = tmp_path / "dist"
    monkeypatch.setattr(builder, "DIST", dist)
    monkeypatch.setattr(builder, "STAGE", dist / "stage")
    dist.mkdir()
    (dist / "templeton-coding-loop-hermes-v0.3.0.zip").write_bytes(b"stale")
    (dist / "exports.json").write_text('{"path":"/private/stale"}\n', encoding="utf-8")
    assert builder.main() == 0
    assert not (dist / "exports.json").exists()
    assert {path.name for path in dist.glob("*.zip")} == {
        "templeton-coding-loop-hermes-v1.1.0.zip",
        "templeton-coding-loop-openclaw-v1.1.0.zip",
    }
    before = {path.name: sha256(path) for path in dist.glob("*.zip")}
    assert builder.main() == 0
    after = {path.name: sha256(path) for path in dist.glob("*.zip")}
    assert before == after
    assert builder.check_outputs() == 0

    archive = next(dist.glob("*.zip"))
    archive.write_bytes(archive.read_bytes() + b"stale")
    with pytest.raises(RuntimeError, match="stale"):
        builder.check_outputs()
    assert builder.main() == 0

    for archive in dist.glob("*.zip"):
        expected_root = archive.stem + "/"
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            names = [entry.filename for entry in entries]
            assert len(names) == len(set(names))
            assert all(name.startswith(expected_root) for name in names)
            assert all(".." not in Path(name).parts and not name.startswith("/") for name in names)
            assert all(stat.S_ISREG(entry.external_attr >> 16) for entry in entries)


def test_matt_pocock_notice_is_preserved_in_both_editions_and_archives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    builder = load_builder()
    dist = tmp_path / "dist"
    monkeypatch.setattr(builder, "DIST", dist)
    monkeypatch.setattr(builder, "STAGE", dist / "stage")
    required = (
        "2ab958093e83e0ec752e6c1c5932da465bf23e0c",
        "Copyright (c) 2026 Matt Pocock",
        "Permission is hereby granted, free of charge",
    )
    for runtime in ("hermes", "openclaw"):
        _name, stage = builder.stage_bundle(runtime)
        notice = (stage / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        assert all(value in notice for value in required)

    assert builder.main() == 0
    for archive in dist.glob("*.zip"):
        with zipfile.ZipFile(archive) as bundle:
            notice = bundle.read(f"{archive.stem}/THIRD_PARTY_NOTICES.md").decode("utf-8")
        assert all(value in notice for value in required)


def test_validator_accepts_git_metadata_but_not_build_noise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    builder = load_builder()
    dist = tmp_path / "dist"
    monkeypatch.setattr(builder, "DIST", dist)
    monkeypatch.setattr(builder, "STAGE", dist / "stage")
    _name, stage = builder.stage_bundle("hermes")
    subprocess.run(["git", "init", "-q"], cwd=stage, check=True)
    validator = stage / "exports" / "validate_bundle.py"
    clean = subprocess.run([sys.executable, str(validator)], cwd=stage, text=True, capture_output=True)
    assert clean.returncode == 0, clean.stderr
    cache = stage / ".pytest_cache" / "v" / "cache"
    cache.mkdir(parents=True)
    (cache / "nodeids").write_text("[]\n", encoding="utf-8")
    noisy = subprocess.run([sys.executable, str(validator)], cwd=stage, text=True, capture_output=True)
    assert noisy.returncode != 0


@pytest.mark.parametrize("runtime", ["hermes", "openclaw"])
def test_generated_ci_is_pinned_least_privilege_and_offline_for_tests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runtime: str
):
    builder = load_builder()
    dist = tmp_path / "dist"
    monkeypatch.setattr(builder, "DIST", dist)
    monkeypatch.setattr(builder, "STAGE", dist / "stage")
    _name, stage = builder.stage_bundle(runtime)
    workflow = (stage / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in workflow
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in workflow
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflow
    assert "persist-credentials: false" in workflow
    assert "pip install --require-hashes -r requirements-ci.lock" in workflow
    assert "pip install --no-build-isolation --no-deps ." in workflow
    assert workflow.count("unshare --net") == 2
    assert 'requires = ["setuptools==80.9.0"]' in (stage / "pyproject.toml").read_text()


def test_openclaw_docs_only_advertise_supported_spec_answer_option():
    readme = (ROOT / "exports" / "openclaw" / "README.md").read_text(encoding="utf-8")
    assert "`--answer`" not in readme
    assert "--answer-file" in readme


def test_ci_bundle_validator_paths_match_export_version():
    builder = load_builder()
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for runtime in builder.RUNTIMES:
        expected = (
            f"dist/stage/templeton-coding-loop-{runtime}-v{builder.VERSION}/"
            "exports/validate_bundle.py"
        )
        assert expected in workflow
    assert "v1.0.0/exports/validate_bundle.py" not in workflow


def test_release_builder_rejects_source_and_stage_symlinks(tmp_path: Path):
    builder = load_builder()
    source = tmp_path / "source"
    source.mkdir()
    (source / "real.txt").write_text("real\n", encoding="utf-8")
    link = source / "link.txt"
    try:
        link.symlink_to("real.txt")
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(RuntimeError, match="symbolic link"):
        builder.copy_tree(source, tmp_path / "copy")

    directory_link = source / "linked-directory"
    outside = tmp_path / "outside"
    outside.mkdir()
    directory_link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symbolic link"):
        builder.copy_tree(source, tmp_path / "copy-2")

    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "README.md").write_text("safe\n", encoding="utf-8")
    (stage / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symbolic link"):
        builder.archive_bundle("unsafe", stage)


def test_external_archive_checksum_detects_coordinated_internal_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    builder = load_builder()
    dist = tmp_path / "dist"
    monkeypatch.setattr(builder, "DIST", dist)
    monkeypatch.setattr(builder, "STAGE", dist / "stage")
    assert builder.main() == 0
    archive = next(path for path in dist.glob("*hermes*.zip"))
    expected = dict(
        line.split("  ", 1)[::-1]
        for line in (dist / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    )[archive.name]

    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extracted)
    root = extracted / archive.stem
    readme = root / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\ncoordinated tamper\n", encoding="utf-8")
    manifest_path = root / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # pathlib's ZIP extraction does not restore Unix modes. Reapply the signed
    # manifest modes so this probe tests coordinated content tampering rather
    # than the extraction library's permission behavior.
    for item in manifest["files"]:
        (root / item["path"]).chmod(int(item["mode"], 8))
    record = next(item for item in manifest["files"] if item["path"] == "README.md")
    record["sha256"] = sha256(readme)
    record["bytes"] = readme.stat().st_size
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shasums = root / "MANIFEST.sha256"
    replacements = {"README.md": sha256(readme), "MANIFEST.json": sha256(manifest_path)}
    lines = []
    for line in shasums.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        lines.append(f"{replacements.get(relative, digest)}  {relative}")
    shasums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    internal = subprocess.run(
        [sys.executable, str(root / "exports" / "validate_bundle.py")],
        cwd=root,
        text=True,
        capture_output=True,
    )
    assert internal.returncode == 0, internal.stderr or internal.stdout
    tampered = dist / "tampered.zip"
    with zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                bundle.write(path, f"{root.name}/{path.relative_to(root).as_posix()}")
    assert sha256(tampered) != expected


@pytest.mark.parametrize("runtime", ["hermes", "openclaw"])
def test_clean_bundle_install_and_tests_outside_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runtime: str
):
    builder = load_builder()
    dist = tmp_path / "dist"
    monkeypatch.setattr(builder, "DIST", dist)
    monkeypatch.setattr(builder, "STAGE", dist / "stage")
    _name, stage = builder.stage_bundle(runtime)
    validator = stage / "exports" / "validate_bundle.py"
    subprocess.run([sys.executable, str(validator)], cwd=stage, check=True)
    venv = tmp_path / f"venv-{runtime}"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    python = venv / "bin" / "python"
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--require-hashes",
            "-r",
            str(stage / "requirements-ci.lock"),
        ],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-build-isolation", "--no-deps", str(stage)],
        cwd=tmp_path,
        check=True,
    )
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run(
        [
            str(python),
            "-c",
            (
                "import pathlib, sys, templeton_loop; "
                "package = pathlib.Path(templeton_loop.__file__).resolve(); "
                "prefix = pathlib.Path(sys.prefix).resolve(); "
                "assert package.is_relative_to(prefix), (package, prefix); "
                "print(templeton_loop.__version__)"
            ),
        ],
        cwd=tmp_path,
        env=env,
        check=True,
    )
    subprocess.run(
        [str(python), "-m", "templeton_loop.cli", "--help"],
        cwd=tmp_path,
        env=env,
        check=True,
    )
    subprocess.run(
        [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider", str(stage / "tests")],
        cwd=tmp_path,
        env=env,
        check=True,
    )
