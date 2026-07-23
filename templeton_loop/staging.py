from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


class StagingError(RuntimeError):
    pass


SENSITIVE_EXCLUDES = (
    ".git",
    ".git/**",
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
    ".ssh/**",
    "**/.ssh/**",
    ".aws/**",
    "**/.aws/**",
    ".npmrc",
    "**/.npmrc",
    ".pypirc",
    "**/.pypirc",
    ".netrc",
    "**/.netrc",
    "_netrc",
    "**/_netrc",
    ".authinfo",
    "**/.authinfo",
    ".authinfo.gpg",
    "**/.authinfo.gpg",
    ".git-credentials",
    "**/.git-credentials",
    ".docker/**",
    "**/.docker/**",
    ".config/gh/**",
    "**/.config/gh/**",
    ".config/gcloud/**",
    "**/.config/gcloud/**",
    ".azure/**",
    "**/.azure/**",
    ".kube/**",
    "**/.kube/**",
    ".terraform.d/credentials.tfrc.json",
    "**/.terraform.d/credentials.tfrc.json",
    "credentials.tfrc.json",
    "**/credentials.tfrc.json",
    "auth.json",
    "**/auth.json",
    "settings.xml",
    "**/settings.xml",
    "pip.conf",
    "**/pip.conf",
    "credentials.json",
    "**/credentials.json",
    "secrets.json",
    "**/secrets.json",
    "id_rsa",
    "**/id_rsa",
    "id_ed25519",
    "**/id_ed25519",
    "*.pem",
    "**/*.pem",
    "*.key",
    "**/*.key",
    "*.p12",
    "**/*.p12",
    "*.pfx",
    "**/*.pfx",
)

_SENSITIVE_CONTENT = (
    b"-----BEGIN " + b"PRIVATE KEY-----",
    b"-----BEGIN RSA " + b"PRIVATE KEY-----",
    b"-----BEGIN EC " + b"PRIVATE KEY-----",
    b"-----BEGIN OPENSSH " + b"PRIVATE KEY-----",
)

GENERATED_EXCLUDES = (
    "**/.DS_Store",
    "**/__pycache__/**",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.ruff_cache/**",
    "node_modules/**",
    "**/node_modules/**",
    ".venv/**",
    "**/.venv/**",
    "venv/**",
    "**/venv/**",
    "dist/**",
    "**/dist/**",
    "build/**",
    "**/build/**",
    "*.egg-info/**",
    "**/*.egg-info/**",
)

DEFAULT_EXCLUDES = (*SENSITIVE_EXCLUDES, *GENERATED_EXCLUDES)


@dataclass(frozen=True)
class StagedFile:
    path: str
    sha256: str
    bytes: int
    mode: int


def _matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def is_sensitive_path(relative: str) -> bool:
    """Return whether a normalized source-relative path is credential-bearing by policy."""

    return _matches(relative, SENSITIVE_EXCLUDES) or _matches(relative + "/**", SENSITIVE_EXCLUDES)


def _safe_relative(path: Path, root: Path) -> str:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise StagingError(f"Path escapes source root: {path}") from exc
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise StagingError(f"Unsafe source path: {relative}")
    return relative


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _reject_sensitive_content(path: Path, relative: str) -> None:
    content = path.read_bytes()
    if any(marker in content for marker in _SENSITIVE_CONTENT):
        raise StagingError(f"Source file contains private-key material: {relative}")
    text = content.decode("utf-8", errors="ignore")
    token_patterns = (
        r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"\bAKIA[0-9A-Z]{16}\b",
    )
    if any(re.search(pattern, text) for pattern in token_patterns):
        raise StagingError(f"Source file contains credential-like material: {relative}")


def validate_staged_file(path: Path, relative: str) -> None:
    """Apply the reusable sensitive-path/content gate to one regular source file."""

    if is_sensitive_path(relative):
        raise StagingError(f"Source path is forbidden by the sensitive-path policy: {relative}")
    _reject_sensitive_content(path, relative)


def inventory_tree(
    root: Path,
    *,
    exclude: Iterable[str] = DEFAULT_EXCLUDES,
    max_file_bytes: int = 20_000_000,
) -> dict[str, StagedFile]:
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise StagingError(f"Source tree is not a directory: {resolved}")
    result: dict[str, StagedFile] = {}
    for directory, names, files in os.walk(resolved, topdown=True, followlinks=False):
        current = Path(directory)
        kept: list[str] = []
        for name in sorted(names):
            candidate = current / name
            relative = _safe_relative(candidate, resolved)
            if _matches(relative, exclude) or _matches(relative + "/**", exclude):
                continue
            if candidate.is_symlink():
                raise StagingError(f"Symbolic links are forbidden in staging: {relative}")
            kept.append(name)
        names[:] = kept
        for name in sorted(files):
            candidate = current / name
            relative = _safe_relative(candidate, resolved)
            if _matches(relative, exclude):
                continue
            metadata = candidate.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise StagingError(f"Symbolic links are forbidden in staging: {relative}")
            if not stat.S_ISREG(metadata.st_mode):
                raise StagingError(f"Unsupported source file type: {relative}")
            if metadata.st_size > max_file_bytes:
                raise StagingError(f"Source file exceeds {max_file_bytes} bytes: {relative}")
            _reject_sensitive_content(candidate, relative)
            result[relative] = StagedFile(
                path=relative,
                sha256=sha256(candidate),
                bytes=metadata.st_size,
                mode=stat.S_IMODE(metadata.st_mode),
            )
    return dict(sorted(result.items()))


def stage_source(
    source: Path,
    destination: Path,
    *,
    exclude: Iterable[str] = DEFAULT_EXCLUDES,
    max_file_bytes: int = 20_000_000,
) -> dict[str, StagedFile]:
    if destination.exists():
        raise StagingError(f"Staging destination already exists: {destination}")
    records = inventory_tree(source, exclude=exclude, max_file_bytes=max_file_bytes)
    destination.mkdir(parents=True, mode=0o700)
    try:
        for relative, record in records.items():
            source_path = source / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(source_path, target)
            target.chmod(record.mode & 0o755)
            # Validate the bytes that actually landed in the isolated stage.
            # The source may change after inventory and before/during copy.
            validate_staged_file(target, relative)
            metadata = target.lstat()
            copied = StagedFile(
                path=relative,
                sha256=sha256(target),
                bytes=metadata.st_size,
                mode=stat.S_IMODE(metadata.st_mode),
            )
            if copied != record:
                raise StagingError(f"Source changed while staging: {relative}")
        return records
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def compare_tree(
    baseline: dict[str, StagedFile],
    candidate_root: Path,
    *,
    exclude: Iterable[str] = DEFAULT_EXCLUDES,
    max_file_bytes: int = 20_000_000,
) -> dict[str, list[str]]:
    resolved = candidate_root.resolve()
    for directory, names, files in os.walk(resolved, topdown=True, followlinks=False):
        current = Path(directory)
        for name in [*names, *files]:
            candidate_path = current / name
            relative = _safe_relative(candidate_path, resolved)
            if _matches(relative, SENSITIVE_EXCLUDES) or _matches(
                relative + "/**", SENSITIVE_EXCLUDES
            ):
                raise StagingError(f"Candidate created a forbidden sensitive path: {relative}")
    candidate = inventory_tree(candidate_root, exclude=exclude, max_file_bytes=max_file_bytes)
    before = set(baseline)
    after = set(candidate)
    modified = sorted(
        path
        for path in before & after
        if (
            baseline[path].sha256,
            baseline[path].bytes,
            baseline[path].mode,
        )
        != (candidate[path].sha256, candidate[path].bytes, candidate[path].mode)
    )
    return {
        "added": sorted(after - before),
        "modified": modified,
        "deleted": sorted(before - after),
    }


def apply_staged_tree(
    candidate_root: Path,
    trusted_worktree: Path,
    baseline: dict[str, StagedFile],
    changes: dict[str, list[str]],
) -> None:
    trusted_root = trusted_worktree.resolve()
    for relative in changes["deleted"]:
        target = trusted_worktree / relative
        target.resolve().relative_to(trusted_root)
        if target.exists() or target.is_symlink():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
    for relative in [*changes["added"], *changes["modified"]]:
        source = candidate_root / relative
        target = trusted_worktree / relative
        source.resolve().relative_to(candidate_root.resolve())
        target.resolve().relative_to(trusted_root)
        if source.is_symlink() or not source.is_file():
            raise StagingError(f"Candidate is not a regular file: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(stat.S_IMODE(source.stat().st_mode) & 0o755)
