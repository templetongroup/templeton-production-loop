from __future__ import annotations

from pathlib import Path

import pytest

from templeton_loop import staging as staging_module

from templeton_loop.staging import (
    StagingError,
    apply_staged_tree,
    compare_tree,
    stage_source,
)


ROOT = Path(__file__).resolve().parent.parent


def test_project_source_tree_passes_its_own_secret_and_path_staging_gate(tmp_path: Path):
    records = stage_source(ROOT, tmp_path / "stage")
    assert "templeton_loop/staging.py" in records
    assert "tests/test_staging.py" in records
    assert not any(path.startswith("dist/") for path in records)


def test_stage_source_excludes_git_secrets_and_dependencies(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (source / ".env").write_text("TOKEN=do-not-copy\n", encoding="utf-8")
    (source / ".git").mkdir()
    (source / ".git" / "config").write_text("secret\n", encoding="utf-8")
    (source / "node_modules").mkdir()
    (source / "node_modules" / "x.js").write_text("ignored\n", encoding="utf-8")

    destination = tmp_path / "stage"
    records = stage_source(source, destination)

    assert list(records) == ["app.py"]
    assert (destination / "app.py").read_text(encoding="utf-8") == "print('ok')\n"
    assert not (destination / ".env").exists()
    assert not (destination / ".git").exists()


def test_stage_source_excludes_root_credentials_and_rejects_key_content(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (source / "credentials.json").write_text('{"token":"present"}\n', encoding="utf-8")
    (source / ".npmrc").write_text("//registry/:_authToken=present\n", encoding="utf-8")
    records = stage_source(source, tmp_path / "stage-safe")
    assert list(records) == ["app.py"]

    (source / "notes.txt").write_text(
        "-----BEGIN OPENSSH " + "PRIVATE KEY-----\nnot-a-release-file\n",
        encoding="utf-8",
    )
    with pytest.raises(StagingError, match="private-key material"):
        stage_source(source, tmp_path / "stage-rejected")


@pytest.mark.parametrize(
    "relative",
    [
        ".netrc",
        "nested/_netrc",
        "nested/.authinfo",
        ".git-credentials",
        ".docker/config.json",
        ".config/gh/hosts.yml",
        ".config/gcloud/application_default_credentials.json",
        ".azure/accessTokens.json",
        ".kube/config",
        ".terraform.d/credentials.tfrc.json",
        "nested/auth.json",
        "nested/settings.xml",
        "nested/pip.conf",
    ],
)
def test_stage_source_excludes_netrc_and_equivalent_credential_files(
    tmp_path: Path, relative: str
):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("print('ok')\n", encoding="utf-8")
    credential = source / relative
    credential.parent.mkdir(parents=True, exist_ok=True)
    credential.write_text("credential material that must never be staged\n", encoding="utf-8")

    destination = tmp_path / "stage"
    records = stage_source(source, destination)

    assert list(records) == ["app.py"]
    assert not (destination / relative).exists()


def test_stage_source_rejects_symlink(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("outside", encoding="utf-8")
    (source / "link").symlink_to(outside)

    with pytest.raises(StagingError, match="Symbolic links"):
        stage_source(source, tmp_path / "stage")


def test_stage_source_revalidates_the_bytes_that_were_copied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source"
    source.mkdir()
    declared = source / "safe.txt"
    declared.write_text("safe\n", encoding="utf-8")
    real_copyfile = staging_module.shutil.copyfile

    def swap_then_copy(src: object, dst: object) -> object:
        Path(src).write_text("ghp_" + "A" * 40, encoding="utf-8")
        return real_copyfile(src, dst)

    monkeypatch.setattr(staging_module.shutil, "copyfile", swap_then_copy)
    destination = tmp_path / "stage"
    with pytest.raises(StagingError, match="credential-like"):
        stage_source(source, destination)
    assert not destination.exists()


def test_compare_and_apply_staged_tree(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "keep.txt").write_text("before\n", encoding="utf-8")
    (source / "delete.txt").write_text("delete\n", encoding="utf-8")
    baseline_root = tmp_path / "baseline"
    baseline = stage_source(source, baseline_root)
    candidate = tmp_path / "candidate"
    stage_source(source, candidate)
    (candidate / "keep.txt").write_text("after\n", encoding="utf-8")
    (candidate / "delete.txt").unlink()
    (candidate / "new.txt").write_text("new\n", encoding="utf-8")

    changes = compare_tree(baseline, candidate)
    assert changes == {
        "added": ["new.txt"],
        "modified": ["keep.txt"],
        "deleted": ["delete.txt"],
    }

    apply_staged_tree(candidate, source, baseline, changes)
    assert (source / "keep.txt").read_text(encoding="utf-8") == "after\n"
    assert not (source / "delete.txt").exists()
    assert (source / "new.txt").read_text(encoding="utf-8") == "new\n"


def test_compare_rejects_agent_created_sensitive_path(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("pass\n", encoding="utf-8")
    baseline_root = tmp_path / "baseline"
    baseline = stage_source(source, baseline_root)
    candidate = tmp_path / "candidate"
    stage_source(source, candidate)
    (candidate / ".env").write_text("TOKEN=leak\n", encoding="utf-8")

    with pytest.raises(StagingError, match="forbidden sensitive"):
        compare_tree(baseline, candidate)


def test_compare_rejects_agent_created_netrc(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("pass\n", encoding="utf-8")
    baseline = stage_source(source, tmp_path / "baseline")
    candidate = tmp_path / "candidate"
    stage_source(source, candidate)
    (candidate / ".netrc").write_text("machine example.test password exposed\n", encoding="utf-8")

    with pytest.raises(StagingError, match="forbidden sensitive"):
        compare_tree(baseline, candidate)
