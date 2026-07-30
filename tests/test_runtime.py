from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from templeton_loop import runtime
from templeton_loop.policy import openclaw_agent_template
from templeton_loop.runtime import RuntimePolicyError, verify_hermes_runtime, verify_openclaw_runtime


PINNED = "worker@sha256:" + "a" * 64
OPENCLAW = shutil.which("openclaw")
SANDBOX_ALLOW = ["exec", "process", "read", "write", "edit", "apply_patch", "image"]


def openclaw_explanation(workspace: Path, *, writable: bool) -> dict[str, Any]:
    if writable:
        effective_root = workspace
        source = "agent"
        mounts = [
            {
                "containerRoot": "/workspace",
                "hostRoot": str(workspace),
                "source": "workspace",
                "writable": True,
            }
        ]
    else:
        effective_root = workspace.parent / "session-sandbox"
        source = "sandbox"
        mounts = [
            {
                "containerRoot": "/workspace",
                "hostRoot": str(effective_root),
                "source": "workspace",
                "writable": False,
            },
            {
                "containerRoot": "/agent",
                "hostRoot": str(workspace),
                "source": "agent",
                "writable": False,
            },
        ]
    return {
        "sandbox": {
            "mode": "all",
            "scope": "session",
            "backend": "docker",
            "sessionIsSandboxed": True,
            "workspaceAccess": "rw" if writable else "ro",
            "workspaceSource": source,
            "effectiveHostWorkspaceRoot": str(effective_root),
            "workspaceMounts": mounts,
            "tools": {"allow": list(SANDBOX_ALLOW), "deny": ["browser"]},
        },
        "elevated": {"enabled": False},
    }


def test_verify_hermes_runtime_requires_dedicated_air_gapped_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    home = tmp_path / "hermes-home"
    home.mkdir()
    (home / "TEMPLETON_RUNTIME.json").write_text(
        json.dumps({"product": "templeton-coding-loop", "schema": 1}), encoding="utf-8"
    )
    config = {
        "backend": "docker",
        "docker_mount_cwd_to_workspace": True,
        "docker_network": False,
        "docker_forward_env": [],
        "env_passthrough": [],
        "container_persistent": False,
        "docker_run_as_host_user": True,
        "docker_volumes": [],
        "shell_init_files": [],
        "docker_persist_across_processes": False,
        "docker_extra_args": [
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
        ],
        "docker_image": PINNED,
    }
    monkeypatch.setattr(runtime.shutil, "which", lambda *_args, **_kwargs: "/usr/bin/docker")

    def runtime_json(argv, **_kwargs):
        if argv[0] == "/usr/bin/docker" and argv[1] == "info":
            return "25.0.0"
        if argv[0] == "/usr/bin/docker" and argv[1:3] == ["image", "inspect"]:
            return [PINNED]
        return config

    monkeypatch.setattr(runtime, "_run_json", runtime_json)

    result = verify_hermes_runtime(environ={"HERMES_HOME": str(home), "PATH": "/bin"})
    assert result["network"] == "none"
    assert result["image"] == PINNED
    assert result["docker_version"] == "25.0.0"

    config["docker_network"] = True
    with pytest.raises(RuntimePolicyError, match="docker_network"):
        verify_hermes_runtime(environ={"HERMES_HOME": str(home), "PATH": "/bin"})

    config["docker_network"] = False
    config["docker_extra_args"].append("--privileged")
    with pytest.raises(RuntimePolicyError, match="exactly"):
        verify_hermes_runtime(environ={"HERMES_HOME": str(home), "PATH": "/bin"})


def test_denial_canary_selected_hermes_profile_is_the_profile_preflighted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    home = tmp_path / "hermes-home"
    home.mkdir()
    (home / "TEMPLETON_RUNTIME.json").write_text(
        json.dumps({"product": "templeton-coding-loop", "schema": 1}), encoding="utf-8"
    )
    config = {
        "backend": "docker",
        "docker_mount_cwd_to_workspace": True,
        "docker_network": False,
        "docker_forward_env": [],
        "env_passthrough": [],
        "container_persistent": False,
        "docker_run_as_host_user": True,
        "docker_volumes": [],
        "shell_init_files": [],
        "docker_persist_across_processes": False,
        "docker_extra_args": [
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
        ],
        "docker_image": PINNED,
    }
    commands: list[list[str]] = []
    monkeypatch.setattr(runtime.shutil, "which", lambda *_args, **_kwargs: "/usr/bin/docker")
    monkeypatch.setattr(runtime, "_verify_local_image", lambda image, _env: image)

    def runtime_json(argv, **_kwargs):
        commands.append(list(argv))
        return "25.0.0" if argv[0] == "/usr/bin/docker" else config

    monkeypatch.setattr(runtime, "_run_json", runtime_json)
    verify_hermes_runtime(
        environ={"HERMES_HOME": str(home), "PATH": "/bin"},
        profile="isolated-profile",
    )
    assert [
        "hermes",
        "--profile",
        "isolated-profile",
        "config",
        "get",
        "terminal",
        "--json",
    ] in commands


def test_hermes_report_roles_require_no_host_or_terminal_tool(tmp_path: Path):
    home = tmp_path / "hermes-home"
    home.mkdir()
    (home / "TEMPLETON_RUNTIME.json").write_text(
        json.dumps({"product": "templeton-coding-loop", "schema": 1}), encoding="utf-8"
    )

    result = verify_hermes_runtime(
        environ={"HERMES_HOME": str(home), "PATH": ""},
        profile="isolated-review",
        role="review",
    )

    assert result["writable_workspace"] is False
    assert result["toolsets"] == ["todo"]
    assert result["isolation"].startswith("safe-mode")


def test_verify_openclaw_runtime_checks_effective_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = openclaw_agent_template("builder", "build", str(workspace), PINNED)
    monkeypatch.setattr(runtime, "_verify_local_image", lambda image, _env: image)
    responses = iter([[agent], openclaw_explanation(workspace, writable=True)])
    monkeypatch.setattr(runtime, "_run_json", lambda *_args, **_kwargs: next(responses))

    result = verify_openclaw_runtime(
        executable="openclaw",
        agent_id="builder",
        role="build",
        workspace=workspace,
        session_id="run-1",
    )
    assert result["effective_policy_verified"] is True
    assert result["denial_canaries"]["method"] == "effective-tool-policy-exactness"
    assert result["denial_canaries"]["active_probes_run"] is False


@pytest.mark.skipif(OPENCLAW is None, reason="OpenClaw CLI is not installed")
def test_verify_openclaw_runtime_supports_installed_cli_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    agent = openclaw_agent_template("templeton-spec", "spec", str(workspace), PINNED)
    config = tmp_path / "openclaw.json"
    config.write_text(json.dumps({"agents": {"list": [agent]}}), encoding="utf-8")
    monkeypatch.setenv("OPENCLAW_CONFIG_PATH", str(config))
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(state))
    monkeypatch.setattr(runtime, "_verify_local_image", lambda image, _env: image)

    result = verify_openclaw_runtime(
        executable=str(OPENCLAW),
        agent_id="templeton-spec",
        role="spec",
        workspace=workspace,
        session_id="agent:templeton-spec:integration-probe",
    )

    assert result["effective_policy_verified"] is True
    assert result["workspace_access"] == "ro"


def test_verify_openclaw_runtime_requires_configured_spec_deny_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = openclaw_agent_template("templeton-spec", "spec", str(workspace), PINNED)
    agent["tools"]["deny"].remove("*")
    responses = iter([[agent]])
    monkeypatch.setattr(runtime, "_run_json", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(runtime, "_verify_local_image", lambda image, _env: image)

    with pytest.raises(RuntimePolicyError, match="deny-all"):
        verify_openclaw_runtime(
            executable="openclaw",
            agent_id="templeton-spec",
            role="spec",
            workspace=workspace,
            session_id="spec-deny-all",
        )


def test_verify_openclaw_runtime_rejects_wrong_effective_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = openclaw_agent_template("reviewer", "review", str(workspace), PINNED)
    monkeypatch.setattr(runtime, "_verify_local_image", lambda image, _env: image)
    explanation = openclaw_explanation(workspace, writable=False)
    explanation["sandbox"]["workspaceAccess"] = "rw"
    responses = iter([[agent], explanation])
    monkeypatch.setattr(runtime, "_run_json", lambda *_args, **_kwargs: next(responses))
    with pytest.raises(RuntimePolicyError, match="workspace access"):
        verify_openclaw_runtime(
            executable="openclaw",
            agent_id="reviewer",
            role="review",
            workspace=workspace,
            session_id="run-2",
        )


def test_verify_openclaw_runtime_rejects_wrong_readonly_agent_mount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = openclaw_agent_template("reviewer", "review", str(workspace), PINNED)
    explanation = openclaw_explanation(workspace, writable=False)
    explanation["sandbox"]["workspaceMounts"][1]["hostRoot"] = str(tmp_path / "wrong")
    responses = iter([[agent], explanation])
    monkeypatch.setattr(runtime, "_run_json", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(runtime, "_verify_local_image", lambda image, _env: image)

    with pytest.raises(RuntimePolicyError, match="read-only agent mount"):
        verify_openclaw_runtime(
            executable="openclaw",
            agent_id="reviewer",
            role="review",
            workspace=workspace,
            session_id="run-wrong-mount",
        )


def test_verify_openclaw_runtime_rejects_effective_elevated_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = openclaw_agent_template("builder", "build", str(workspace), PINNED)
    explanation = openclaw_explanation(workspace, writable=True)
    explanation["elevated"]["enabled"] = True
    responses = iter([[agent], explanation])
    monkeypatch.setattr(runtime, "_run_json", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(runtime, "_verify_local_image", lambda image, _env: image)

    with pytest.raises(RuntimePolicyError, match="elevated execution"):
        verify_openclaw_runtime(
            executable="openclaw",
            agent_id="builder",
            role="build",
            workspace=workspace,
            session_id="run-elevated",
        )


def test_verify_openclaw_runtime_rejects_sandbox_tool_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = openclaw_agent_template("builder", "build", str(workspace), PINNED)
    explanation = openclaw_explanation(workspace, writable=True)
    explanation["sandbox"]["tools"]["allow"].remove("apply_patch")
    responses = iter([[agent], explanation])
    monkeypatch.setattr(runtime, "_run_json", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(runtime, "_verify_local_image", lambda image, _env: image)

    with pytest.raises(RuntimePolicyError, match="blocks required role tools"):
        verify_openclaw_runtime(
            executable="openclaw",
            agent_id="builder",
            role="build",
            workspace=workspace,
            session_id="run-tool-block",
        )


def test_verify_openclaw_runtime_rejects_sandbox_tool_deny(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = openclaw_agent_template("builder", "build", str(workspace), PINNED)
    explanation = openclaw_explanation(workspace, writable=True)
    explanation["sandbox"]["tools"]["deny"] = ["read"]
    responses = iter([[agent], explanation])
    monkeypatch.setattr(runtime, "_run_json", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(runtime, "_verify_local_image", lambda image, _env: image)

    with pytest.raises(RuntimePolicyError, match="denies required role tools"):
        verify_openclaw_runtime(
            executable="openclaw",
            agent_id="builder",
            role="build",
            workspace=workspace,
            session_id="run-tool-deny",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("security", "allowlist", "sandbox-only with workspace-only patching"),
        ("ask", "on-miss", "sandbox-only with workspace-only patching"),
        ("applyPatch", {"workspaceOnly": False}, "sandbox-only with workspace-only patching"),
    ],
)
def test_denial_canary_rejects_configured_openclaw_execution_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = openclaw_agent_template("builder", "build", str(workspace), PINNED)
    agent["tools"]["exec"][field] = value
    responses = iter([[agent]])
    monkeypatch.setattr(runtime, "_run_json", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(runtime, "_verify_local_image", lambda image, _env: image)
    with pytest.raises(RuntimePolicyError, match=message):
        verify_openclaw_runtime(
            executable="openclaw",
            agent_id="builder",
            role="build",
            workspace=workspace,
            session_id="run-canary",
        )


def test_denial_canary_requires_exact_local_worker_digest(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(runtime.shutil, "which", lambda *_args, **_kwargs: "/usr/bin/docker")
    monkeypatch.setattr(runtime, "_run_json", lambda *_args, **_kwargs: ["worker@sha256:" + "b" * 64])
    with pytest.raises(RuntimePolicyError, match="not available locally"):
        runtime._verify_local_image(PINNED, {"PATH": "/bin"})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("image", "worker:latest", "pinned by a sha256 digest"),
        ("readOnlyRoot", False, "network=none and readOnlyRoot=true"),
        ("capDrop", [], "drop all capabilities"),
        ("binds", ["/host:/sandbox"], "drop all capabilities"),
    ],
)
def test_verify_openclaw_runtime_rejects_configured_container_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = openclaw_agent_template("builder", "build", str(workspace), PINNED)
    agent["sandbox"]["docker"][field] = value
    responses = iter([[agent]])
    monkeypatch.setattr(runtime, "_run_json", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(runtime, "_verify_local_image", lambda image, _env: image)

    with pytest.raises(RuntimePolicyError, match=message):
        verify_openclaw_runtime(
            executable="openclaw",
            agent_id="builder",
            role="build",
            workspace=workspace,
            session_id="run-container-drift",
        )
