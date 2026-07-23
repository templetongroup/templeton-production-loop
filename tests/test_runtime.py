from __future__ import annotations

import json
from pathlib import Path

import pytest

from templeton_loop import runtime
from templeton_loop.policy import openclaw_agent_template
from templeton_loop.runtime import RuntimePolicyError, verify_hermes_runtime, verify_openclaw_runtime


PINNED = "worker@sha256:" + "a" * 64


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
    responses = iter(
        [
            [agent],
            {
                "sandbox": {
                    "mode": "all",
                    "backend": "docker",
                    "network": "none",
                    "image": PINNED,
                    "readOnlyRoot": True,
                    "capDrop": ["ALL"],
                    "binds": [],
                    "sessionIsSandboxed": True,
                    "workspaceAccess": "rw",
                    "effectiveHostWorkspaceRoot": str(workspace),
                },
                "tools": agent["tools"],
            },
        ]
    )
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


def test_verify_openclaw_runtime_rejects_wrong_effective_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = openclaw_agent_template("reviewer", "review", str(workspace), PINNED)
    monkeypatch.setattr(runtime, "_verify_local_image", lambda image, _env: image)
    responses = iter(
        [
            [agent],
            {
                "sandbox": {
                    "mode": "all",
                    "backend": "docker",
                    "network": "none",
                    "image": PINNED,
                    "readOnlyRoot": True,
                    "capDrop": ["ALL"],
                    "binds": [],
                    "sessionIsSandboxed": True,
                    "workspaceAccess": "rw",
                    "effectiveHostWorkspaceRoot": str(workspace),
                },
                "tools": agent["tools"],
            },
        ]
    )
    monkeypatch.setattr(runtime, "_run_json", lambda *_args, **_kwargs: next(responses))
    with pytest.raises(RuntimePolicyError, match="workspace access"):
        verify_openclaw_runtime(
            executable="openclaw",
            agent_id="reviewer",
            role="review",
            workspace=workspace,
            session_id="run-2",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("security", "allowlist", "full sandbox security"),
        ("ask", "on-miss", "full sandbox security"),
        ("applyPatch", {"workspaceOnly": False}, "workspace-only patching"),
    ],
)
def test_denial_canary_rejects_effective_openclaw_execution_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = openclaw_agent_template("builder", "build", str(workspace), PINNED)
    effective_tools = json.loads(json.dumps(agent["tools"]))
    effective_tools["exec"][field] = value
    responses = iter(
        [
            [agent],
            {
                "sandbox": {
                    "mode": "all",
                    "backend": "docker",
                    "network": "none",
                    "image": PINNED,
                    "readOnlyRoot": True,
                    "capDrop": ["ALL"],
                    "binds": [],
                    "sessionIsSandboxed": True,
                    "workspaceAccess": "rw",
                    "effectiveHostWorkspaceRoot": str(workspace),
                },
                "tools": effective_tools,
            },
        ]
    )
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
        ("image", "worker@sha256:" + "b" * 64, "configured pinned digest"),
        ("readOnlyRoot", False, "readOnlyRoot must be true"),
        ("capDrop", [], "capDrop must include ALL"),
        ("binds", ["/host:/sandbox"], "define no binds"),
    ],
)
def test_verify_openclaw_runtime_rejects_effective_container_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agent = openclaw_agent_template("builder", "build", str(workspace), PINNED)
    effective = {
        "mode": "all",
        "backend": "docker",
        "network": "none",
        "image": PINNED,
        "readOnlyRoot": True,
        "capDrop": ["ALL"],
        "binds": [],
        "sessionIsSandboxed": True,
        "workspaceAccess": "rw",
        "effectiveHostWorkspaceRoot": str(workspace),
    }
    effective[field] = value
    responses = iter([[agent], {"sandbox": effective, "tools": agent["tools"]}])
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
