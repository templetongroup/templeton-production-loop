from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


CONNECTOR_SCHEMA = "templeton.connector.v1"
PREFLIGHT_SCHEMA = "templeton.connector-preflight.v1"
CONNECTOR_ROLES = ("spec", "build", "review", "qa", "prove")
_EXPECTED_ACCESS = {
    "spec": "none",
    "build": "rw",
    "review": "ro",
    "qa": "ro",
    "prove": "rw",
}
_PREFLIGHT_KEYS = {
    "schema",
    "id",
    "role",
    "workspace",
    "workspace_access",
    "structured_output",
    "fresh_session",
    "isolation",
    "network",
    "credentials",
    "verifier_image",
}


class ConnectorError(RuntimeError):
    """Raised when a universal harness connector violates its contract."""


@dataclass(frozen=True)
class ConnectorConfig:
    id: str
    command: tuple[str, ...]
    roles: tuple[str, ...]
    path: Path
    sha256: str


def _regular_file(path: Path, field: str) -> Path:
    target = path.expanduser()
    if target.is_symlink() or not target.is_file():
        raise ConnectorError(f"{field} must be a regular non-symlink file: {target}")
    return target.resolve()


def load_connector_config(value: str | Path) -> ConnectorConfig:
    path = _regular_file(Path(value), "Connector config")
    if path.stat().st_size > 100_000:
        raise ConnectorError("Connector config exceeds 100000 bytes")
    try:
        raw = path.read_bytes()
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConnectorError(f"Invalid connector config {path}: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"schema", "id", "command", "roles"}:
        raise ConnectorError(
            "Connector config keys must be exactly schema, id, command, and roles"
        )
    if data.get("schema") != CONNECTOR_SCHEMA:
        raise ConnectorError(f"Connector config schema must be {CONNECTOR_SCHEMA}")
    connector_id = data.get("id")
    if not isinstance(connector_id, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9._-]{0,63}", connector_id
    ):
        raise ConnectorError(
            "Connector id must be 1-64 lowercase letters, digits, dots, dashes, or underscores"
        )
    command = data.get("command")
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(item, str) or not item or "\x00" in item for item in command)
    ):
        raise ConnectorError("Connector command must be a non-empty string array")
    executable = Path(command[0]).expanduser()
    if not executable.is_absolute():
        raise ConnectorError("Connector command executable must be an absolute path")
    try:
        executable = executable.resolve(strict=True)
    except OSError as exc:
        raise ConnectorError(f"Connector executable cannot be resolved: {executable}") from exc
    if not executable.is_file():
        raise ConnectorError(
            f"Connector executable must resolve to a regular file: {executable}"
        )
    if not os.access(executable, os.X_OK):
        raise ConnectorError(f"Connector executable is not executable: {executable}")
    normalized_command = (str(executable), *command[1:])
    roles = data.get("roles")
    if (
        not isinstance(roles, list)
        or not roles
        or any(not isinstance(role, str) or role not in CONNECTOR_ROLES for role in roles)
        or len(set(roles)) != len(roles)
    ):
        raise ConnectorError(
            f"Connector roles must be a unique non-empty subset of {list(CONNECTOR_ROLES)}"
        )
    return ConnectorConfig(
        id=connector_id,
        command=normalized_command,
        roles=tuple(roles),
        path=path,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def connector_command(
    config: ConnectorConfig,
    *,
    role: str,
    prompt: str,
    max_turns: int,
    timeout: int,
    model: str | None = None,
    provider: str | None = None,
    profile: str | None = None,
    phase: str | None = None,
) -> list[str]:
    if role not in config.roles:
        raise ConnectorError(f"Connector {config.id} does not support role {role}")
    command = [
        *config.command,
        "invoke",
        "--role",
        role,
        "--workspace",
        ".",
        "--message",
        prompt,
        "--max-turns",
        str(max_turns),
        "--timeout",
        str(timeout),
        "--json",
    ]
    if phase:
        command.extend(["--phase", phase])
    if model:
        command.extend(["--model", model])
    if provider:
        command.extend(["--provider", provider])
    if profile:
        command.extend(["--profile", profile])
    return command


def verify_connector_runtime(
    config: ConnectorConfig,
    *,
    role: str,
    workspace: Path,
    environ: Mapping[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    if role not in config.roles:
        raise ConnectorError(f"Connector {config.id} does not support role {role}")
    requested = workspace.expanduser()
    if requested.is_symlink() or not requested.is_dir():
        raise ConnectorError(
            "Connector workspace must be an existing non-symlink directory: "
            f"{requested}"
        )
    resolved = requested.resolve()
    command = [
        *config.command,
        "preflight",
        "--role",
        role,
        "--workspace",
        str(resolved),
        "--json",
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=None if environ is None else dict(environ),
        timeout=timeout,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise ConnectorError(
            f"Connector preflight failed with code {completed.returncode}: {detail[:2000]}"
        )
    try:
        evidence = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ConnectorError("Connector preflight did not return JSON") from exc
    if not isinstance(evidence, dict) or set(evidence) != _PREFLIGHT_KEYS:
        raise ConnectorError(
            f"Connector preflight keys must be exactly {sorted(_PREFLIGHT_KEYS)}"
        )
    expected_access = _EXPECTED_ACCESS[role]
    expected = {
        "schema": PREFLIGHT_SCHEMA,
        "id": config.id,
        "role": role,
        "workspace": str(resolved),
        "workspace_access": expected_access,
        "structured_output": True,
        "fresh_session": True,
        "isolation": "enforced",
        "network": "none",
        "credentials": "none",
    }
    for key, value in expected.items():
        if evidence.get(key) != value:
            raise ConnectorError(
                f"Connector preflight {key} must be {value!r}; got {evidence.get(key)!r}"
            )
    image = evidence.get("verifier_image")
    if role == "prove":
        if not isinstance(image, str) or not re.search(r"@sha256:[0-9a-f]{64}$", image):
            raise ConnectorError("Proof connector must return a digest-pinned verifier_image")
    elif image is not None:
        raise ConnectorError("verifier_image must be null outside the prove role")
    return {
        **evidence,
        "connector_config": str(config.path),
        "connector_config_sha256": config.sha256,
    }


def connector_workspace(root: Path, connector_id: str, role: str) -> Path:
    if role not in CONNECTOR_ROLES:
        raise ConnectorError(f"Unknown connector role: {role}")
    path = root / "connector-workspaces" / connector_id / role
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise ConnectorError(f"Unsafe connector workspace: {path}")
    return path
