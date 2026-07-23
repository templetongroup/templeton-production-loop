from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PolicyError(ValueError):
    """Raised when a runtime cannot prove the required least-authority boundary."""


@dataclass(frozen=True)
class RolePolicy:
    role: str
    writable_workspace: bool
    hermes_toolsets: tuple[str, ...]
    openclaw_allow: tuple[str, ...]
    forbidden_effects: tuple[str, ...]


FORBIDDEN_EFFECTS = (
    "merge",
    "auto_merge",
    "deploy",
    "publish",
    "purchase",
    "production_mutation",
    "credential_read",
    "cross_workspace_write",
    "session_send",
    "gateway_mutation",
)

_READ_ONLY = ("read", "exec", "process")
_MUTATING = ("read", "write", "edit", "apply_patch", "exec", "process")
_HERMES_SANDBOX_TOOLS = ("terminal", "todo")
_HERMES_REPORT_TOOLS = ("todo",)

ROLE_POLICIES: dict[str, RolePolicy] = {
    "spec": RolePolicy("spec", False, _HERMES_REPORT_TOOLS, _READ_ONLY, FORBIDDEN_EFFECTS),
    "plan-review": RolePolicy("plan-review", False, _HERMES_REPORT_TOOLS, _READ_ONLY, FORBIDDEN_EFFECTS),
    "build": RolePolicy("build", True, _HERMES_SANDBOX_TOOLS, _MUTATING, FORBIDDEN_EFFECTS),
    "review": RolePolicy("review", False, _HERMES_REPORT_TOOLS, _READ_ONLY, FORBIDDEN_EFFECTS),
    "qa": RolePolicy("qa", False, _HERMES_REPORT_TOOLS, _READ_ONLY, FORBIDDEN_EFFECTS),
    "status": RolePolicy("status", False, _HERMES_REPORT_TOOLS, _READ_ONLY, FORBIDDEN_EFFECTS),
    "prove": RolePolicy("prove", True, _HERMES_SANDBOX_TOOLS, _MUTATING, FORBIDDEN_EFFECTS),
}

_REQUIRED_DENIES = {
    "group:runtime",
    "group:web",
    "group:ui",
    "group:automation",
    "group:messaging",
    "group:sessions",
    "group:memory",
    "group:nodes",
    "group:agents",
    "group:media",
    "group:plugins",
    "gateway",
    "cron",
    "browser",
}

_AGENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def get_role_policy(role: str) -> RolePolicy:
    try:
        return ROLE_POLICIES[role]
    except KeyError as exc:
        raise PolicyError(f"Unknown role policy: {role}") from exc


def validate_agent_id(agent_id: str) -> str:
    if not isinstance(agent_id, str) or not _AGENT_ID_RE.fullmatch(agent_id):
        raise PolicyError(
            "OpenClaw agent id must be 1-64 characters using only letters, digits, '.', '_' or '-'"
        )
    return agent_id


def required_openclaw_denies() -> set[str]:
    return set(_REQUIRED_DENIES)


def denial_canaries(role: str) -> dict[str, Any]:
    """Verify static policy exactness without claiming effect probes were executed."""

    policy = get_role_policy(role)
    granted = set(policy.openclaw_allow) | set(policy.hermes_toolsets)
    escaped = sorted(granted & set(policy.forbidden_effects))
    if escaped:
        raise PolicyError(f"Role {role} grants forbidden capabilities: {escaped}")
    if policy.forbidden_effects != FORBIDDEN_EFFECTS:
        raise PolicyError(f"Role {role} does not deny every forbidden effect")
    return {
        "role": role,
        "passed": True,
        "method": "effective-tool-policy-exactness",
        "active_probes_run": False,
        "denied": list(policy.forbidden_effects),
    }


def hermes_policy_args(role: str) -> list[str]:
    policy = get_role_policy(role)
    if not policy.writable_workspace:
        return [
            "--safe-mode",
            "--ignore-rules",
            "--toolsets",
            ",".join(policy.hermes_toolsets),
        ]
    # Hermes defines --safe-mode as --ignore-user-config. Using it here would
    # discard the dedicated Docker terminal configuration that preflight just
    # verified, so preserve that profile and constrain the call explicitly.
    return ["--ignore-rules", "--toolsets", ",".join(policy.hermes_toolsets)]


def openclaw_agent_template(
    agent_id: str,
    role: str,
    workspace: str,
    image: str = "templeton-worker@sha256:REPLACE_WITH_PINNED_DIGEST",
) -> dict[str, Any]:
    validate_agent_id(agent_id)
    policy = get_role_policy(role)
    return {
        "id": agent_id,
        "workspace": workspace,
        "sandbox": {
            "mode": "all",
            "backend": "docker",
            "scope": "session",
            "workspaceAccess": "rw" if policy.writable_workspace else "ro",
            "docker": {
                "image": image,
                "readOnlyRoot": True,
                "network": "none",
                "capDrop": ["ALL"],
                "binds": [],
            },
        },
        "tools": {
            "allow": list(policy.openclaw_allow),
            "deny": sorted(_REQUIRED_DENIES),
            "fs": {"workspaceOnly": True},
            "exec": {
                "host": "sandbox",
                "security": "full",
                "ask": "off",
                "applyPatch": {"workspaceOnly": True},
            },
            "elevated": {"enabled": False},
        },
    }


def _string_set(value: Any, field: str) -> set[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PolicyError(f"{field} must be an explicit string array")
    return {item.lower() for item in value}


def verify_openclaw_agent(agent: dict[str, Any], role: str) -> dict[str, Any]:
    """Fail closed unless one agent explicitly carries the complete policy."""

    policy = get_role_policy(role)
    if not isinstance(agent, dict):
        raise PolicyError("OpenClaw agent entry must be an object")
    validate_agent_id(agent.get("id"))
    sandbox = agent.get("sandbox")
    tools = agent.get("tools")
    if not isinstance(sandbox, dict) or not isinstance(tools, dict):
        raise PolicyError("Agent must define explicit sandbox and tools policies")
    if sandbox.get("mode") != "all" or sandbox.get("scope") != "session":
        raise PolicyError("Agent sandbox must use mode=all and scope=session")
    if sandbox.get("backend") != "docker":
        raise PolicyError("Agent sandbox backend must be docker")
    expected_access = "rw" if policy.writable_workspace else "ro"
    if sandbox.get("workspaceAccess") != expected_access:
        raise PolicyError(f"Agent sandbox workspaceAccess must be {expected_access}")
    docker = sandbox.get("docker")
    if not isinstance(docker, dict):
        raise PolicyError("Agent sandbox must define docker policy")
    image = docker.get("image")
    if not isinstance(image, str) or not re.search(r"@sha256:[0-9a-f]{64}$", image):
        raise PolicyError("Docker image must be pinned by a sha256 digest")
    if docker.get("network") != "none" or docker.get("readOnlyRoot") is not True:
        raise PolicyError("Docker sandbox must use network=none and readOnlyRoot=true")
    if docker.get("capDrop") != ["ALL"] or docker.get("binds") != []:
        raise PolicyError("Docker sandbox must drop all capabilities and define no extra binds")

    allowed = _string_set(tools.get("allow"), "tools.allow")
    expected_allowed = {item.lower() for item in policy.openclaw_allow}
    if allowed != expected_allowed:
        raise PolicyError(
            f"tools.allow must be exactly {sorted(expected_allowed)}; got {sorted(allowed)}"
        )
    denied = _string_set(tools.get("deny"), "tools.deny")
    if not _REQUIRED_DENIES <= denied:
        raise PolicyError(f"tools.deny is missing {sorted(_REQUIRED_DENIES - denied)}")
    elevated = tools.get("elevated")
    if not isinstance(elevated, dict) or elevated.get("enabled") is not False:
        raise PolicyError("tools.elevated.enabled must be explicitly false")
    fs = tools.get("fs")
    execution = tools.get("exec")
    if not isinstance(fs, dict) or fs.get("workspaceOnly") is not True:
        raise PolicyError("tools.fs.workspaceOnly must be explicitly true")
    if not isinstance(execution, dict):
        raise PolicyError("tools.exec must be explicit")
    patching = execution.get("applyPatch")
    if (
        execution.get("host") != "sandbox"
        or execution.get("security") != "full"
        or execution.get("ask") != "off"
        or not isinstance(patching, dict)
        or patching.get("workspaceOnly") is not True
    ):
        raise PolicyError("tools.exec must be sandbox-only with workspace-only patching")
    return {
        "ok": True,
        "agent": agent.get("id"),
        "role": role,
        "workspace_access": expected_access,
        "allowed_tools": sorted(allowed),
        "image": image,
        "network": "none",
        "forbidden_effects": list(policy.forbidden_effects),
    }


def find_and_verify_openclaw_agent(
    entries: list[dict[str, Any]],
    agent_id: str,
    role: str,
    expected_workspace: Path | None = None,
) -> dict[str, Any]:
    validate_agent_id(agent_id)
    matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("id") == agent_id]
    if len(matches) != 1:
        raise PolicyError(f"Expected exactly one OpenClaw agent with id {agent_id!r}")
    entry = matches[0]
    evidence = verify_openclaw_agent(entry, role)
    if expected_workspace is not None:
        configured = entry.get("workspace")
        if not isinstance(configured, str) or not configured:
            raise PolicyError("Agent must define an explicit workspace")
        configured_path = Path(configured).expanduser()
        expected_path = expected_workspace.expanduser()
        if configured_path.is_symlink() or expected_path.is_symlink():
            raise PolicyError("Agent workspace must not use symbolic-link indirection")
        workspace = configured_path.absolute()
        expected = expected_path.absolute()
        if expected != workspace:
            raise PolicyError(
                f"Agent workspace must equal the exact staged workspace: expected {expected}, got {workspace}"
            )
        evidence["workspace"] = str(workspace)
    return evidence


def write_policy_template(
    path: Path,
    agent_id: str,
    role: str,
    workspace: str,
    image: str = "templeton-worker@sha256:REPLACE_WITH_PINNED_DIGEST",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(openclaw_agent_template(agent_id, role, workspace, image), indent=2) + "\n",
        encoding="utf-8",
    )
