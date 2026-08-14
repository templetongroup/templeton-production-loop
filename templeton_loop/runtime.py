from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Mapping, Sequence

from .policy import (
    PolicyError,
    denial_canaries,
    find_and_verify_openclaw_agent,
    get_role_policy,
    validate_agent_id,
)


class RuntimePolicyError(PolicyError):
    pass


def _verify_local_image(image: str, environment: Mapping[str, str]) -> str:
    docker = shutil.which("docker", path=environment.get("PATH"))
    if docker is None:
        raise RuntimePolicyError("Docker is required to verify the pinned worker image")
    digests = _run_json(
        [docker, "image", "inspect", image, "--format", "{{json .RepoDigests}}"],
        env=environment,
    )
    if not isinstance(digests, list) or image not in digests:
        raise RuntimePolicyError(f"Pinned worker image is not available locally at the exact digest: {image}")
    return docker


def _run_json(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    timeout: int = 30,
) -> Any:
    completed = subprocess.run(
        list(argv),
        check=False,
        capture_output=True,
        text=True,
        env=None if env is None else dict(env),
        timeout=timeout,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise RuntimePolicyError(f"Runtime preflight failed: {' '.join(argv)}: {detail}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimePolicyError(f"Runtime preflight did not return JSON: {' '.join(argv)}") from exc


def verify_hermes_runtime(
    *,
    executable: str = "hermes",
    environ: Mapping[str, str] | None = None,
    profile: str | None = None,
    role: str = "build",
) -> dict[str, Any]:
    environment = dict(os.environ if environ is None else environ)
    hermes_home = environment.get("HERMES_HOME")
    if not hermes_home:
        raise RuntimePolicyError("HERMES_HOME must point to a dedicated Templeton runtime home")
    home = Path(hermes_home).expanduser().resolve()
    marker = home / "TEMPLETON_RUNTIME.json"
    if not marker.is_file():
        raise RuntimePolicyError(f"Dedicated runtime marker is missing: {marker}")
    try:
        marker_data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimePolicyError(f"Dedicated runtime marker is invalid: {marker}") from exc
    if marker_data != {"product": "templeton-production-loop", "schema": 1}:
        raise RuntimePolicyError("Dedicated runtime marker has unexpected content")
    policy = get_role_policy(role)
    if not policy.writable_workspace:
        # Review/QA consume the bounded GitHub diff and issue contract already
        # embedded in their prompt. Safe mode and a todo-only tool allowlist
        # leave no filesystem, shell, code, web, or messaging mutation path.
        return {
            "ok": True,
            "runtime": "hermes",
            "home": str(home),
            "profile": profile or "default",
            "writable_workspace": False,
            "toolsets": list(policy.hermes_toolsets),
            "isolation": "safe-mode report-only prompt context",
            "denial_canaries": denial_canaries(role),
        }
    docker_executable = shutil.which("docker", path=environment.get("PATH"))
    if docker_executable is None:
        raise RuntimePolicyError("Docker is required for the Hermes least-authority runtime")
    docker_version = _run_json(
        [docker_executable, "info", "--format", "{{json .ServerVersion}}"],
        env=environment,
    )
    if not isinstance(docker_version, str) or not docker_version.strip():
        raise RuntimePolicyError("Docker daemon did not report a server version")

    config_command = [executable]
    if profile:
        validate_agent_id(profile)
        config_command.extend(["--profile", profile])
    config_command.extend(["config", "get", "terminal", "--json"])
    terminal = _run_json(config_command, env=environment)
    if not isinstance(terminal, dict):
        raise RuntimePolicyError("Hermes terminal configuration must be an object")
    required = {
        "backend": "docker",
        "docker_mount_cwd_to_workspace": True,
        "docker_network": False,
        "docker_forward_env": [],
        "env_passthrough": [],
        "container_persistent": False,
        "docker_run_as_host_user": True,
        "docker_volumes": [],
        "shell_init_files": [],
    }
    for key, expected in required.items():
        if terminal.get(key) != expected:
            raise RuntimePolicyError(
                f"Hermes terminal policy {key} must be {expected!r}; got {terminal.get(key)!r}"
            )
    if terminal.get("docker_persist_across_processes") not in (None, False):
        raise RuntimePolicyError("Hermes Docker persistence across processes must be disabled")
    extra = terminal.get("docker_extra_args")
    required_extra = {"--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges"}
    if not isinstance(extra, list) or set(extra) != required_extra or len(extra) != len(required_extra):
        raise RuntimePolicyError(
            "Hermes docker_extra_args must contain exactly --read-only, --cap-drop=ALL, "
            "and --security-opt=no-new-privileges"
        )
    image = terminal.get("docker_image")
    if not isinstance(image, str) or not re.search(r"@sha256:[0-9a-f]{64}$", image):
        raise RuntimePolicyError("Hermes Docker image must be pinned by sha256 digest")
    _verify_local_image(image, environment)
    return {
        "ok": True,
        "runtime": "hermes",
        "home": str(home),
        "backend": "docker",
        "network": "none",
        "image": image,
        "docker_version": docker_version,
        "profile": profile or "default",
        "denial_canaries": denial_canaries("prove"),
    }


def verify_openclaw_runtime(
    *,
    executable: str,
    agent_id: str,
    role: str,
    workspace: Path,
    session_id: str,
) -> dict[str, Any]:
    validate_agent_id(agent_id)
    entries = _run_json([executable, "config", "get", "agents.list", "--json"])
    if not isinstance(entries, list):
        raise RuntimePolicyError("OpenClaw agents.list must be a JSON array")
    try:
        configured = find_and_verify_openclaw_agent(entries, agent_id, role, workspace)
    except PolicyError as exc:
        raise RuntimePolicyError(str(exc)) from exc
    explained = _run_json(
        [
            executable,
            "sandbox",
            "explain",
            "--agent",
            agent_id,
            "--session",
            session_id,
            "--json",
        ]
    )
    if not isinstance(explained, dict):
        raise RuntimePolicyError("OpenClaw sandbox explain must return an object")
    effective = explained.get("sandbox")
    if not isinstance(effective, dict):
        raise RuntimePolicyError("OpenClaw sandbox explain must include sandbox state")
    if effective.get("sessionIsSandboxed") is not True:
        raise RuntimePolicyError("OpenClaw effective session is not sandboxed")
    if effective.get("mode") != "all":
        raise RuntimePolicyError("OpenClaw effective sandbox mode must be all")
    if effective.get("scope") != "session":
        raise RuntimePolicyError("OpenClaw effective sandbox scope must be session")
    if effective.get("backend") != "docker":
        raise RuntimePolicyError("OpenClaw effective sandbox backend must be docker")

    policy = get_role_policy(role)
    expected_access = "rw" if policy.writable_workspace else "ro"
    if effective.get("workspaceAccess") != expected_access:
        raise RuntimePolicyError(
            f"OpenClaw effective workspace access must be {expected_access}"
        )

    effective_root = effective.get("effectiveHostWorkspaceRoot")
    if not isinstance(effective_root, str) or not effective_root:
        raise RuntimePolicyError("OpenClaw effective host workspace root must be present")
    effective_path = Path(effective_root).expanduser()
    configured_path = Path(str(configured["workspace"])).expanduser()
    requested_path = workspace.expanduser()
    if effective_path.is_symlink() or configured_path.is_symlink() or requested_path.is_symlink():
        raise RuntimePolicyError(
            "OpenClaw effective workspace must not use symbolic-link indirection"
        )
    resolved_effective = effective_path.absolute()
    configured_root = configured_path.absolute()
    if requested_path.absolute() != configured_root:
        raise RuntimePolicyError("OpenClaw configured workspace must equal the exact staged workspace")

    mounts = effective.get("workspaceMounts")
    if not isinstance(mounts, list) or any(not isinstance(item, dict) for item in mounts):
        raise RuntimePolicyError("OpenClaw sandbox explain must include explicit workspace mounts")
    workspace_mounts = [item for item in mounts if item.get("source") == "workspace"]
    agent_mounts = [item for item in mounts if item.get("source") == "agent"]
    if policy.writable_workspace:
        if effective.get("workspaceSource") != "agent" or resolved_effective != configured_root:
            raise RuntimePolicyError(
                "OpenClaw writable sandbox must use the exact configured agent workspace"
            )
        if len(mounts) != 1 or len(workspace_mounts) != 1 or agent_mounts:
            raise RuntimePolicyError("OpenClaw writable sandbox must expose exactly one workspace mount")
        mount = workspace_mounts[0]
        if (
            mount.get("containerRoot") != "/workspace"
            or mount.get("writable") is not True
            or not isinstance(mount.get("hostRoot"), str)
            or Path(mount["hostRoot"]).expanduser().absolute() != configured_root
        ):
            raise RuntimePolicyError(
                "OpenClaw writable workspace mount must map the staged workspace to /workspace"
            )
    else:
        if effective.get("workspaceSource") != "sandbox":
            raise RuntimePolicyError("OpenClaw read-only role must use a session sandbox workspace")
        if len(mounts) != 2 or len(workspace_mounts) != 1 or len(agent_mounts) != 1:
            raise RuntimePolicyError(
                "OpenClaw read-only sandbox must expose workspace and agent mounts only"
            )
        workspace_mount = workspace_mounts[0]
        if (
            workspace_mount.get("containerRoot") != "/workspace"
            or workspace_mount.get("writable") is not False
            or not isinstance(workspace_mount.get("hostRoot"), str)
            or Path(workspace_mount["hostRoot"]).expanduser().absolute() != resolved_effective
        ):
            raise RuntimePolicyError("OpenClaw session workspace mount must be read-only at /workspace")
        agent_mount = agent_mounts[0]
        if (
            agent_mount.get("containerRoot") != "/agent"
            or agent_mount.get("writable") is not False
            or not isinstance(agent_mount.get("hostRoot"), str)
            or Path(agent_mount["hostRoot"]).expanduser().absolute() != configured_root
        ):
            raise RuntimePolicyError(
                "OpenClaw read-only agent mount must map the staged workspace to /agent"
            )

    elevated = explained.get("elevated")
    if not isinstance(elevated, dict) or elevated.get("enabled") is not False:
        raise RuntimePolicyError("OpenClaw effective elevated execution must be disabled")

    # OpenClaw 2026.7.1 exposes the sandbox-level tool envelope here, not the
    # direct agents.list[].tools policy. The direct role policy was verified
    # above from config; this check ensures its allowed tools remain available
    # inside the sandbox without claiming unavailable fields were observed.
    sandbox_tools = effective.get("tools")
    if not isinstance(sandbox_tools, dict):
        raise RuntimePolicyError("OpenClaw sandbox explain must include sandbox tools policy")
    sandbox_allow = sandbox_tools.get("allow")
    sandbox_deny = sandbox_tools.get("deny")
    if not isinstance(sandbox_allow, list) or any(not isinstance(item, str) for item in sandbox_allow):
        raise RuntimePolicyError("OpenClaw sandbox tools.allow must be an explicit string array")
    if not isinstance(sandbox_deny, list) or any(not isinstance(item, str) for item in sandbox_deny):
        raise RuntimePolicyError("OpenClaw sandbox tools.deny must be an explicit string array")
    sandbox_denied = {item.lower() for item in sandbox_deny}
    blocked_role_tools = {
        tool
        for tool in policy.openclaw_allow
        if any(fnmatchcase(tool.lower(), pattern) for pattern in sandbox_denied)
    }
    if blocked_role_tools:
        raise RuntimePolicyError(
            f"Effective OpenClaw sandbox denies required role tools: {sorted(blocked_role_tools)}"
        )
    missing_sandbox_tools = {
        item.lower() for item in policy.openclaw_allow
    } - {item.lower() for item in sandbox_allow}
    if missing_sandbox_tools:
        raise RuntimePolicyError(
            f"OpenClaw sandbox tools policy blocks required role tools: {sorted(missing_sandbox_tools)}"
        )

    _verify_local_image(str(configured["image"]), os.environ)
    configured["session"] = session_id
    configured["configured_policy_verified"] = True
    configured["sandbox_explain_verified"] = True
    configured["effective_policy_verified"] = True
    configured["denial_canaries"] = denial_canaries(role)
    return configured
