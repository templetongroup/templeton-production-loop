from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath


class GitMetadataError(RuntimeError):
    pass


def git_metadata_path(repo_root: Path, relative: str) -> Path:
    """Resolve a Templeton state path for normal repos and linked worktrees."""
    normalized = PurePosixPath(relative)
    if normalized.is_absolute() or not normalized.parts or any(
        part in {"", ".", ".."} for part in normalized.parts
    ):
        raise GitMetadataError(f"Unsafe Git metadata path: {relative!r}")
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", normalized.as_posix()],
            cwd=repo_root,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitMetadataError(f"Unable to resolve Git metadata path: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or "git rev-parse failed"
        raise GitMetadataError(f"Unable to resolve Git metadata path: {detail}")
    raw = result.stdout.strip()
    if not raw:
        raise GitMetadataError("Git returned an empty metadata path")
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    return path.absolute()
