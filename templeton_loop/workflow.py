from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .boundaries import prepare_sink
from .evidence import EvidenceError, Finding, RunLedger, evidence_freshness, redact, redact_text, validate_findings
from .gitmeta import git_metadata_path
from .routing import Outcome, append_outcome
from .staging import apply_staged_tree, compare_tree, stage_source


class WorkflowError(RuntimeError):
    pass


REPAIR_ATTEMPT_MARKER = "<!-- templeton-loop-repair-attempt-v1 -->"
MAX_REPAIR_ATTEMPTS = 2
_LINKED_ISSUE_RE = re.compile(
    r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:https://github\.com/[^/]+/[^/]+/issues/)?#?(\d+)"
)


def _linked_issue_number(pr_body: str) -> int:
    matches = {int(value) for value in _LINKED_ISSUE_RE.findall(pr_body or "")}
    if len(matches) != 1:
        raise WorkflowError(
            "Repair PR must link exactly one issue contract using Closes/Fixes/Resolves"
        )
    return next(iter(matches))


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Verifier:
    argv: tuple[str, ...]
    timeout_seconds: int


@dataclass(frozen=True)
class LoopConfig:
    verifiers: tuple[Verifier, ...]
    protected_paths: tuple[str, ...]
    max_patch_bytes: int
    max_changed_files: int
    verifier_engine: str | None
    verifier_image: str | None

    @classmethod
    def load(cls, repo_root: Path) -> "LoopConfig":
        path = repo_root / ".templeton" / "loop.json"
        if not path.is_file():
            raise WorkflowError(
                f"Missing trusted repository config {path}; brokered builds require structured verifier argv"
            )
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"Invalid {path}: {exc}") from exc
        if not isinstance(value, dict) or value.get("version") != 1:
            raise WorkflowError(".templeton/loop.json version must be 1")
        raw_verifiers = value.get("verifiers")
        if not isinstance(raw_verifiers, list) or not raw_verifiers:
            raise WorkflowError(".templeton/loop.json requires at least one verifier")
        verifiers: list[Verifier] = []
        for index, raw in enumerate(raw_verifiers):
            if not isinstance(raw, dict) or set(raw) - {"argv", "timeout_seconds"}:
                raise WorkflowError(f"Invalid verifier {index}")
            argv = raw.get("argv")
            timeout = raw.get("timeout_seconds", 900)
            if (
                not isinstance(argv, list)
                or not argv
                or any(not isinstance(item, str) or not item for item in argv)
                or isinstance(timeout, bool)
                or not isinstance(timeout, int)
                or not 1 <= timeout <= 3600
            ):
                raise WorkflowError(f"Invalid verifier {index}")
            verifiers.append(Verifier(tuple(argv), timeout))
        protected = value.get(
            "protected_paths",
            [".git", ".github/workflows", ".templeton/loop.json", "CODEOWNERS"],
        )
        if not isinstance(protected, list) or any(not isinstance(item, str) for item in protected):
            raise WorkflowError("protected_paths must be a string array")
        max_patch_bytes = value.get("max_patch_bytes", 1_000_000)
        max_changed_files = value.get("max_changed_files", 100)
        if not isinstance(max_patch_bytes, int) or not 1 <= max_patch_bytes <= 10_000_000:
            raise WorkflowError("max_patch_bytes must be between 1 and 10000000")
        if not isinstance(max_changed_files, int) or not 1 <= max_changed_files <= 1000:
            raise WorkflowError("max_changed_files must be between 1 and 1000")
        sandbox = value.get("verifier_sandbox")
        if not isinstance(sandbox, dict) or set(sandbox) != {"engine", "image"}:
            raise WorkflowError("verifier_sandbox must contain only engine and image")
        verifier_engine = sandbox.get("engine")
        verifier_image = sandbox.get("image")
        if verifier_engine not in {"docker", "podman"}:
            raise WorkflowError("verifier_sandbox.engine must be docker or podman")
        if not isinstance(verifier_image, str) or not re.search(
            r"@sha256:[0-9a-f]{64}$", verifier_image
        ):
            raise WorkflowError("verifier_sandbox.image must be pinned by sha256 digest")
        return cls(
            tuple(verifiers),
            tuple(protected),
            max_patch_bytes,
            max_changed_files,
            verifier_engine,
            verifier_image,
        )


def extract_json_object(text: str) -> dict[str, Any]:
    candidates = [text.strip()]
    candidates.extend(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE))
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        for start, character in enumerate(candidate):
            if character != "{":
                continue
            try:
                value, _ = decoder.raw_decode(candidate[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    raise WorkflowError("Agent did not return one valid JSON object")


def validate_builder_response(value: dict[str, Any], max_patch_bytes: int) -> dict[str, Any]:
    del max_patch_bytes  # retained for API compatibility with v0 callers
    allowed = {"schema", "status", "summary", "questions"}
    if set(value) - allowed:
        raise WorkflowError(f"Unexpected builder response fields: {sorted(set(value) - allowed)}")
    if value.get("schema") != "templeton.result.v1":
        raise WorkflowError("Builder response schema must be templeton.result.v1")
    if value.get("status") not in {"ready", "blocked", "no-change", "needs-human"}:
        raise WorkflowError("Builder status must be ready, blocked, no-change, or needs-human")
    if not isinstance(value.get("summary"), str) or not value["summary"].strip():
        raise WorkflowError("Builder summary must not be empty")
    questions = value.get("questions", [])
    if not isinstance(questions, list) or any(not isinstance(item, str) for item in questions):
        raise WorkflowError("Builder questions must be a string array")
    return value


def _run(
    args: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    if check and result.returncode != 0:
        detail = redact_text((result.stderr or result.stdout).strip())
        raise WorkflowError(f"Command failed ({result.returncode}): {shlex.join(args)}\n{detail}")
    return result


def _json_command(args: list[str], *, cwd: Path, check: bool = True) -> Any:
    result = _run(args, cwd=cwd, check=check)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"Expected JSON from {shlex.join(args)}") from exc


def _changed_paths(worktree: Path) -> list[str]:
    result = _run(["git", "status", "--porcelain=v1", "-z"], cwd=worktree)
    entries = result.stdout.split("\0")
    paths: list[str] = []
    for entry in entries:
        if not entry:
            continue
        raw = entry[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(raw)
    return sorted(set(paths))


def _stage_and_validate_patch(worktree: Path, config: LoopConfig) -> str:
    """Stage every change so untracked additions are included in all patch gates."""

    _run(["git", "add", "--all"], cwd=worktree)
    cached_diff = _run(
        ["git", "diff", "--cached", "--no-ext-diff", "--binary"],
        cwd=worktree,
        timeout=300,
    ).stdout
    if len(cached_diff.encode("utf-8")) > config.max_patch_bytes:
        raise WorkflowError("Broker-generated patch exceeds max_patch_bytes")
    if redact_text(cached_diff) != cached_diff:
        raise WorkflowError("Patch contains a value matching a secret pattern")
    _run(["git", "diff", "--cached", "--check"], cwd=worktree)
    return cached_diff


def validate_changed_paths(worktree: Path, paths: list[str], config: LoopConfig) -> None:
    if not paths:
        raise WorkflowError("Agent patch produced no changed files")
    if len(paths) > config.max_changed_files:
        raise WorkflowError(f"Changed file count exceeds {config.max_changed_files}")
    root = worktree.resolve()
    for relative in paths:
        if relative.startswith("/") or ".." in Path(relative).parts:
            raise WorkflowError(f"Unsafe changed path: {relative}")
        normalized = relative.rstrip("/")
        if any(normalized == item or normalized.startswith(item.rstrip("/") + "/") for item in config.protected_paths):
            raise WorkflowError(f"Patch touched protected path: {relative}")
        path = worktree / relative
        if path.is_symlink():
            raise WorkflowError(f"Patch created or changed a symbolic link: {relative}")
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise WorkflowError(f"Changed path escapes worktree: {relative}") from exc


def verifier_container_command(
    workspace: Path,
    verifier: Verifier,
    config: LoopConfig,
) -> list[str]:
    if not config.verifier_engine or not config.verifier_image:
        raise WorkflowError(
            "verifier_sandbox with a pinned image is required; host verifier execution is forbidden"
        )
    if shutil.which(config.verifier_engine) is None:
        raise WorkflowError(f"Verifier sandbox engine is unavailable: {config.verifier_engine}")
    return [
        config.verifier_engine,
        "run",
        "--rm",
        "--pull",
        "never",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "256",
        "--memory",
        "4g",
        "--cpus",
        "2",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--mount",
        f"type=bind,src={workspace.resolve()},dst=/workspace,ro",
        "--workdir",
        "/workspace",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=256m",
        config.verifier_image,
        *verifier.argv,
    ]


def verify_local_verifier_image(repo_root: Path, config: LoopConfig) -> None:
    if not config.verifier_engine or not config.verifier_image:
        raise WorkflowError("A pinned verifier sandbox image is required")
    if shutil.which(config.verifier_engine) is None:
        raise WorkflowError(f"Verifier sandbox engine is unavailable: {config.verifier_engine}")
    result = _run(
        [
            config.verifier_engine,
            "image",
            "inspect",
            config.verifier_image,
            "--format",
            "{{json .RepoDigests}}",
        ],
        cwd=repo_root,
        check=False,
    )
    try:
        digests = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError as exc:
        raise WorkflowError("Verifier image inspection returned invalid JSON") from exc
    if result.returncode != 0 or not isinstance(digests, list) or config.verifier_image not in digests:
        raise WorkflowError(
            f"Pinned verifier image is not available locally at the exact digest: {config.verifier_image}"
        )


def _run_verifiers(worktree: Path, config: LoopConfig) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="templeton-verify-") as temporary:
        for index, verifier in enumerate(config.verifiers, start=1):
            verifier_workspace = Path(temporary) / f"workspace-{index}"
            stage_source(worktree, verifier_workspace)
            command = verifier_container_command(verifier_workspace, verifier, config)
            started = time.monotonic()
            result = _run(command, cwd=worktree, timeout=verifier.timeout_seconds, check=False)
            record = {
                "argv": list(verifier.argv),
                "sandbox": config.verifier_engine,
                "image": config.verifier_image,
                "network": "none",
                "exit_code": result.returncode,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "stdout_tail": redact_text(result.stdout[-2000:]),
                "stderr_tail": redact_text(result.stderr[-2000:]),
            }
            results.append(record)
            if result.returncode != 0:
                raise WorkflowError(f"Verifier failed: {shlex.join(verifier.argv)}")
    return results


def _select_workspace(repo_root: Path, run_dir: Path, agent_workspace: Path | None) -> Path:
    if agent_workspace is None:
        return run_dir / "workspace"
    base = git_metadata_path(repo_root, "templeton-loop/openclaw-workspaces")
    requested = agent_workspace.expanduser().absolute()
    if requested.parent != base.absolute():
        raise WorkflowError("OpenClaw agent workspace must be a direct child of the trusted workspace root")
    if base.exists() and (base.is_symlink() or base.absolute() != base.resolve()):
        raise WorkflowError("OpenClaw workspace root must not contain symbolic-link indirection")
    base.mkdir(parents=True, exist_ok=True)
    if requested.is_symlink():
        raise WorkflowError("OpenClaw agent workspace must not be a symbolic link")
    return requested


def _worktree(repo_root: Path, revision: str, branch: str) -> tuple[Path, Callable[[], None]]:
    base = git_metadata_path(repo_root, "templeton-loop/worktrees")
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{branch.replace('/', '-')}-{uuid.uuid4().hex[:10]}"
    _run(["git", "worktree", "add", "--detach", str(path), revision], cwd=repo_root, timeout=300)
    _run(["git", "switch", "-c", branch], cwd=path)

    def cleanup() -> None:
        _run(["git", "worktree", "remove", "--force", str(path)], cwd=repo_root, check=False, timeout=300)

    return path, cleanup


def broker_build(
    *,
    repo: Any,
    candidate: Any,
    agent_command: list[str],
    timeout: int,
    preflight: Callable[[Path], dict[str, Any]],
    agent_workspace: Path | None = None,
) -> dict[str, Any]:
    config = LoopConfig.load(repo.root)
    issue_number = candidate.number
    run_id = uuid.uuid4().hex
    if candidate.kind == "pr-repair":
        contract = _json_command(
            [
                "gh", "pr", "view", str(candidate.number), "--repo", repo.slug,
                "--json", "number,title,body,url,headRefOid,baseRefName,comments",
            ],
            cwd=repo.root,
        )
        revision = contract["headRefOid"]
        repair_attempts = sum(
            1
            for comment in contract.get("comments", [])
            if isinstance(comment, dict) and REPAIR_ATTEMPT_MARKER in str(comment.get("body", ""))
        )
        if repair_attempts >= MAX_REPAIR_ATTEMPTS:
            _run(
                [
                    "gh", "pr", "edit", str(candidate.number), "--repo", repo.slug,
                    "--add-label", "loop:stuck", "--add-label", "loop:needs-human-review",
                    "--remove-label", "loop:changes-requested", "--remove-label", "loop:building",
                ],
                cwd=repo.root,
            )
            return {
                "status": "stuck",
                "role": "build",
                "candidate": vars(candidate),
                "repair_attempts": repair_attempts,
                "reason": "Automated repair budget exhausted",
            }
        linked_issue = _linked_issue_number(str(contract.get("body") or ""))
    else:
        contract = _json_command(
            ["gh", "issue", "view", str(issue_number), "--repo", repo.slug, "--json", "number,title,body,url,labels"],
            cwd=repo.root,
        )
        _run(["git", "fetch", "origin", repo.default_branch], cwd=repo.root, timeout=300)
        revision = f"origin/{repo.default_branch}"

    verify_local_verifier_image(repo.root, config)
    branch = f"loop/{run_id}"
    run_dir = git_metadata_path(repo.root, f"templeton-loop/runs/{run_id}")
    run_dir.mkdir(parents=True, exist_ok=False)
    ledger_path = run_dir / "events.jsonl"
    ledger = RunLedger(ledger_path)
    ledger.append({"type": "run_started", "role": "build", "candidate": vars(candidate), "revision": revision})
    worktree, cleanup = _worktree(repo.root, revision, branch)
    baseline_root = run_dir / "baseline"
    workspace = _select_workspace(repo.root, run_dir, agent_workspace)
    if workspace.exists():
        shutil.rmtree(workspace)
    claimed = False
    try:
        baseline = stage_source(worktree, baseline_root)
        stage_source(worktree, workspace)
        policy_evidence = preflight(workspace)
        ledger.append({"type": "runtime_preflight", "evidence": policy_evidence})
        if candidate.kind == "pr-repair":
            _run(
                ["gh", "pr", "edit", str(candidate.number), "--repo", repo.slug,
                 "--add-label", "loop:building", "--remove-label", "loop:changes-requested"],
                cwd=repo.root,
            )
        else:
            _run(
                ["gh", "issue", "edit", str(issue_number), "--repo", repo.slug,
                 "--add-label", "loop:building", "--remove-label", "loop:agent-ready"],
                cwd=repo.root,
            )
        claimed = True
        if candidate.kind == "pr-repair":
            _run(
                [
                    "gh", "pr", "comment", str(candidate.number), "--repo", repo.slug,
                    "--body", REPAIR_ATTEMPT_MARKER,
                ],
                cwd=repo.root,
            )
            ledger.append(
                {
                    "type": "repair_attempt_claimed",
                    "attempt": repair_attempts + 1,
                    "maximum": MAX_REPAIR_ATTEMPTS,
                }
            )
        started = time.monotonic()
        safe_env = os.environ.copy()
        safe_env["HERMES_WRITE_SAFE_ROOT"] = str(workspace)
        result = _run(agent_command, cwd=workspace, timeout=timeout, check=False, env=safe_env)
        ledger.append({
            "type": "agent_completed",
            "exit_code": result.returncode,
            "duration_ms": round((time.monotonic() - started) * 1000),
        })
        if result.returncode != 0:
            raise WorkflowError(f"Build agent failed: {redact_text(result.stderr[-2000:])}")
        response = validate_builder_response(extract_json_object(result.stdout), config.max_patch_bytes)
        prepare_sink(
            json.dumps(response, ensure_ascii=False, sort_keys=True),
            sink="builder-result",
            max_bytes=20_000,
        )
        safe_summary = prepare_sink(
            response["summary"], sink="builder-summary", max_bytes=2_000
        ).text
        changes = compare_tree(baseline, workspace)
        changed_paths = sorted([*changes["added"], *changes["modified"], *changes["deleted"]])
        if response["status"] != "ready":
            if changed_paths:
                raise WorkflowError("Non-ready builder response mutated the staged workspace")
            stop_label = (
                "loop:needs-human-review"
                if response["status"] == "needs-human"
                else "loop:blocked"
            )
            target_kind = "pr" if candidate.kind == "pr-repair" else "issue"
            _run(
                [
                    "gh", target_kind, "edit", str(issue_number), "--repo", repo.slug,
                    "--add-label", stop_label, "--remove-label", "loop:building",
                ],
                cwd=repo.root,
            )
            ledger.append({"type": "run_completed", "status": response["status"], "summary": safe_summary})
            return {
                "status": response["status"], "role": "build", "candidate": vars(candidate),
                "summary": safe_summary, "questions": response.get("questions", []),
                "ledger": str(ledger_path),
            }
        validate_changed_paths(worktree, changed_paths, config)
        apply_staged_tree(workspace, worktree, baseline, changes)
        paths = _changed_paths(worktree)
        validate_changed_paths(worktree, paths, config)
        _run(["git", "diff", "--check"], cwd=worktree)
        _stage_and_validate_patch(worktree, config)
        verifier_results = _run_verifiers(worktree, config)
        paths = _changed_paths(worktree)
        validate_changed_paths(worktree, paths, config)
        _stage_and_validate_patch(worktree, config)
        _run(["git", "diff", "--cached", "--check"], cwd=worktree)
        commit_message = prepare_sink(
            f"fix: address #{issue_number} {safe_summary[:72]}",
            sink="git-commit-message",
            max_bytes=240,
        ).text
        _run(["git", "commit", "-m", commit_message], cwd=worktree)
        commit_sha = _run(["git", "rev-parse", "HEAD"], cwd=worktree).stdout.strip()
        _run(["git", "push", "origin", f"HEAD:refs/heads/{branch}"], cwd=worktree, timeout=300)

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            if candidate.kind == "pr-repair":
                handle.write(f"Supersedes repair work for #{issue_number}.\n\n")
                handle.write(f"Fixes #{linked_issue}\n\n")
            else:
                handle.write(f"Closes #{issue_number}\n\n")
            handle.write("## Templeton broker evidence\n\n")
            for verifier in verifier_results:
                handle.write(
                    f"- `{shlex.join(verifier['argv'])}` — passed in "
                    f"{verifier['duration_ms']} ms in an air-gapped container\n"
                )
            body_path = Path(handle.name)
        prepared_body = prepare_sink(
            body_path.read_text(encoding="utf-8"),
            sink="github-pr-body",
            max_bytes=20_000,
        ).text
        body_path.write_text(prepared_body, encoding="utf-8")
        title = prepare_sink(
            safe_summary[:200], sink="github-pr-title", max_bytes=512
        ).text
        try:
            pr_url = _run(
                ["gh", "pr", "create", "--repo", repo.slug, "--base", repo.default_branch,
                 "--head", branch, "--title", title, "--body-file", str(body_path)],
                cwd=repo.root,
            ).stdout.strip()
        finally:
            body_path.unlink(missing_ok=True)
        if candidate.kind == "pr-repair":
            try:
                created_pr = int(pr_url.rstrip("/").rsplit("/", 1)[-1])
            except ValueError as exc:
                raise WorkflowError(f"Could not determine created PR number from {pr_url!r}") from exc
            _run(
                ["gh", "pr", "edit", str(issue_number), "--repo", repo.slug,
                 "--remove-label", "loop:building"],
                cwd=repo.root,
            )
            _run(
                ["gh", "pr", "edit", str(created_pr), "--repo", repo.slug,
                 "--add-label", "loop:awaiting-review"],
                cwd=repo.root,
            )
        else:
            _run(
                ["gh", "issue", "edit", str(issue_number), "--repo", repo.slug,
                 "--add-label", "loop:awaiting-review", "--remove-label", "loop:building"],
                cwd=repo.root,
            )
        duration_ms = round((time.monotonic() - started) * 1000)
        ledger.append({
            "type": "run_completed", "status": "completed", "commit_sha": commit_sha,
            "pr_url": pr_url, "verifiers": verifier_results, "changed_paths": paths,
            "duration_ms": duration_ms,
        })
        append_outcome(
            git_metadata_path(repo.root, "templeton-loop/outcomes.jsonl"),
            Outcome("build", "runtime", "configured-agent", True, duration_ms, 1),
        )
        return {
            "status": "completed", "role": "build", "candidate": vars(candidate),
            "commit_sha": commit_sha, "pr_url": pr_url, "changed_paths": paths,
            "verifiers": verifier_results, "ledger": str(ledger_path), "branch": branch,
        }
    except Exception:
        if claimed:
            target_kind = "pr" if candidate.kind == "pr-repair" else "issue"
            _run(
                ["gh", target_kind, "edit", str(issue_number), "--repo", repo.slug,
                 "--add-label", "loop:blocked", "--remove-label", "loop:building"],
                cwd=repo.root,
                check=False,
            )
        raise
    finally:
        cleanup()
        shutil.rmtree(baseline_root, ignore_errors=True)
        shutil.rmtree(workspace, ignore_errors=True)

def _run_staged_readonly_agent(
    *,
    repo: Any,
    revision: str,
    role: str,
    agent_command: list[str],
    timeout: int,
    preflight: Callable[[Path], dict[str, Any]],
    agent_workspace: Path | None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    run_id = uuid.uuid4().hex
    run_dir = git_metadata_path(repo.root, f"templeton-loop/runs/{run_id}")
    run_dir.mkdir(parents=True, exist_ok=False)
    ledger_path = run_dir / "events.jsonl"
    ledger = RunLedger(ledger_path)
    worktree, cleanup = _worktree(repo.root, revision, f"loop/{role}-{run_id}")
    baseline_root = run_dir / "baseline"
    workspace = _select_workspace(repo.root, run_dir, agent_workspace)
    if workspace.exists():
        shutil.rmtree(workspace)
    try:
        baseline = stage_source(worktree, baseline_root)
        stage_source(worktree, workspace)
        policy_evidence = preflight(workspace)
        ledger.append({
            "type": "run_started",
            "role": role,
            "revision": revision,
            "runtime_policy": policy_evidence,
        })
        environment = os.environ.copy()
        environment["HERMES_WRITE_SAFE_ROOT"] = str(workspace)
        started = time.monotonic()
        result = _run(
            agent_command,
            cwd=workspace,
            timeout=timeout,
            check=False,
            env=environment,
        )
        changes = compare_tree(baseline, workspace)
        if any(changes.values()):
            raise WorkflowError(f"Report-only {role} agent mutated its staged workspace")
        ledger.append({
            "type": "agent_completed",
            "exit_code": result.returncode,
            "duration_ms": round((time.monotonic() - started) * 1000),
        })
        return result, ledger_path
    finally:
        cleanup()
        shutil.rmtree(baseline_root, ignore_errors=True)
        shutil.rmtree(workspace, ignore_errors=True)


def format_review_comment(sha: str, summary: str, findings: list[Finding], ci: str, mergeability: str) -> str:
    must_fix = [finding for finding in findings if finding.disposition == "must-fix"]
    lines = [
        f"Templeton Loop review of {sha}",
        "",
        f"CI: {ci}",
        f"Mergeability: {mergeability}",
        "",
        "## Review",
        "",
        summary,
        "",
        "## Must fix before merge",
        "",
    ]
    if not must_fix:
        lines.append("None.")
    else:
        for finding in must_fix:
            location = f" ({finding.location})" if finding.location else ""
            lines.append(f"- **{finding.severity.upper()}** {finding.summary}{location} — {finding.failure_scenario}")
    lines.extend(["", "## Safe to merge", "", "Yes — evidence is complete. Human merge required." if not must_fix and ci == "required checks passed" and mergeability == "clean" else "No."])
    return "\n".join(lines) + "\n"


_CONTRACT_MARKER_RE = re.compile(r"(?mi)^\s*(?:[-*]\s*)?((?:AC|NG)-\d+)\s*:")


def _linked_contract_markers(repo: Any, pr_body: str) -> set[str]:
    numbers = sorted({int(value) for value in _LINKED_ISSUE_RE.findall(pr_body or "")})
    if len(numbers) != 1:
        raise WorkflowError(
            "Review PR must link exactly one issue contract using Closes/Fixes/Resolves"
        )
    markers: set[str] = set()
    for number in numbers:
        issue = _json_command(
            [
                "gh",
                "issue",
                "view",
                str(number),
                "--repo",
                repo.slug,
                "--json",
                "number,title,body,url",
            ],
            cwd=repo.root,
        )
        markers.update(_CONTRACT_MARKER_RE.findall(str(issue.get("body") or "")))
    if not any(marker.startswith("AC-") for marker in markers):
        raise WorkflowError("Linked issue contract must define at least one AC-N acceptance criterion")
    return markers


def broker_review(
    *,
    repo: Any,
    candidate: Any,
    agent_command: list[str],
    timeout: int,
    preflight: Callable[[Path], dict[str, Any]],
    agent_workspace: Path | None = None,
) -> dict[str, Any]:
    pr = _json_command(["gh", "pr", "view", str(candidate.number), "--repo", repo.slug, "--json", "number,title,body,url,headRefOid,mergeable,mergeStateStatus"], cwd=repo.root)
    reviewed_sha = pr["headRefOid"]
    contract_markers = _linked_contract_markers(repo, str(pr.get("body") or ""))
    started = time.monotonic()
    result, ledger_path = _run_staged_readonly_agent(
        repo=repo,
        revision=reviewed_sha,
        role="review",
        agent_command=agent_command,
        timeout=timeout,
        preflight=preflight,
        agent_workspace=agent_workspace,
    )
    if result.returncode != 0:
        raise WorkflowError(f"Review agent failed: {redact_text(result.stderr[-2000:])}")
    response = extract_json_object(result.stdout)
    prepare_sink(
        json.dumps(response, ensure_ascii=False, sort_keys=True),
        sink="review-result",
        max_bytes=200_000,
    )
    if set(response) - {"summary", "findings"}:
        raise WorkflowError("Unexpected review response fields")
    if not isinstance(response.get("summary"), str) or not isinstance(response.get("findings"), list):
        raise WorkflowError("Review response requires summary and findings")
    findings = validate_findings(response["findings"])
    for finding in findings:
        marker = finding.acceptance_criterion or finding.non_goal
        if marker not in contract_markers:
            raise WorkflowError(f"Finding {finding.finding_id} references unknown contract marker {marker}")

    current = _json_command(["gh", "pr", "view", str(candidate.number), "--repo", repo.slug, "--json", "headRefOid,mergeable,mergeStateStatus"], cwd=repo.root)
    freshness = evidence_freshness(
        reviewed_sha,
        current["headRefOid"],
        datetime.now(timezone.utc).isoformat(),
    )
    if freshness.status != "current":
        return {"status": "stale", "role": "review", "candidate": vars(candidate), "freshness": vars(freshness)}
    checks_result = _run(["gh", "pr", "checks", str(candidate.number), "--repo", repo.slug, "--required", "--json", "bucket,name,state,link"], cwd=repo.root, check=False)
    try:
        checks = json.loads(checks_result.stdout) if checks_result.stdout.strip() else []
    except json.JSONDecodeError as exc:
        raise WorkflowError("Invalid required-check response") from exc
    buckets = {str(item.get("bucket", "")).lower() for item in checks}
    if not checks:
        ci = "not configured"
    elif buckets & {"pending", "cancel", "skipping"}:
        return {"status": "pending", "role": "review", "candidate": vars(candidate), "checks": checks}
    elif checks_result.returncode != 0 or buckets & {"fail"}:
        ci = "failed"
    else:
        ci = "required checks passed"
    current = _json_command(["gh", "pr", "view", str(candidate.number), "--repo", repo.slug, "--json", "headRefOid,mergeable,mergeStateStatus"], cwd=repo.root)
    if current["headRefOid"] != reviewed_sha:
        return {
            "status": "stale",
            "role": "review",
            "candidate": vars(candidate),
            "reviewed_sha": reviewed_sha,
            "current_sha": current["headRefOid"],
        }
    mergeability = "clean" if str(current.get("mergeable", "")).upper() == "MERGEABLE" else "conflicting"
    comment = format_review_comment(reviewed_sha, response["summary"], findings, ci, mergeability)
    comment = prepare_sink(comment, sink="github-review-comment", max_bytes=60_000).text
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(comment)
        comment_path = Path(handle.name)
    try:
        comment_head = _json_command(
            ["gh", "pr", "view", str(candidate.number), "--repo", repo.slug, "--json", "headRefOid"],
            cwd=repo.root,
        )
        if comment_head.get("headRefOid") != reviewed_sha:
            return {
                "status": "stale",
                "role": "review",
                "candidate": vars(candidate),
                "reviewed_sha": reviewed_sha,
                "current_sha": comment_head.get("headRefOid"),
            }
        _run(["gh", "pr", "comment", str(candidate.number), "--repo", repo.slug, "--body-file", str(comment_path)], cwd=repo.root)
    finally:
        comment_path.unlink(missing_ok=True)
    must_fix = any(finding.disposition == "must-fix" for finding in findings)
    if must_fix or ci == "failed" or mergeability != "clean":
        add, remove, verdict = "loop:changes-requested", "loop:approved", "changes-requested"
    elif ci != "required checks passed":
        add, remove, verdict = "loop:needs-human-review", "loop:approved", "needs-human-review"
    else:
        add, remove, verdict = "loop:approved", "loop:changes-requested", "approved"
    before_label = _json_command(
        ["gh", "pr", "view", str(candidate.number), "--repo", repo.slug, "--json", "headRefOid"],
        cwd=repo.root,
    )
    if before_label["headRefOid"] != reviewed_sha:
        return {
            "status": "stale",
            "role": "review",
            "candidate": vars(candidate),
            "reviewed_sha": reviewed_sha,
            "current_sha": before_label["headRefOid"],
        }
    _run(["gh", "pr", "edit", str(candidate.number), "--repo", repo.slug, "--add-label", add, "--remove-label", remove, "--remove-label", "loop:awaiting-review"], cwd=repo.root)
    after_label = _json_command(
        ["gh", "pr", "view", str(candidate.number), "--repo", repo.slug, "--json", "headRefOid"],
        cwd=repo.root,
    )
    if after_label.get("headRefOid") != reviewed_sha:
        _run(
            [
                "gh",
                "pr",
                "edit",
                str(candidate.number),
                "--repo",
                repo.slug,
                "--remove-label",
                add,
                "--add-label",
                "loop:awaiting-review",
            ],
            cwd=repo.root,
        )
        return {
            "status": "stale",
            "role": "review",
            "candidate": vars(candidate),
            "reviewed_sha": reviewed_sha,
            "current_sha": after_label.get("headRefOid"),
        }
    duration_ms = round((time.monotonic() - started) * 1000)
    append_outcome(
        git_metadata_path(repo.root, "templeton-loop/outcomes.jsonl"),
        Outcome(
            "review",
            "runtime",
            "configured-agent",
            verdict == "approved",
            duration_ms,
            1,
            failure_class=None if verdict == "approved" else verdict,
        ),
    )
    return {"status": verdict, "role": "review", "candidate": vars(candidate), "reviewed_sha": reviewed_sha, "findings": [finding.to_dict() for finding in findings], "ci": ci, "mergeability": mergeability, "duration_ms": duration_ms, "ledger": str(ledger_path)}


def broker_qa(
    *,
    repo: Any,
    candidate: Any,
    agent_command: list[str],
    timeout: int,
    preflight: Callable[[Path], dict[str, Any]],
    agent_workspace: Path | None = None,
) -> dict[str, Any]:
    reviewed_sha = candidate.head_sha or ""
    if not reviewed_sha:
        raise WorkflowError("QA requires an exact PR head SHA")
    pr = _json_command(
        [
            "gh",
            "pr",
            "view",
            str(candidate.number),
            "--repo",
            repo.slug,
            "--json",
            "body,headRefOid",
        ],
        cwd=repo.root,
    )
    if pr.get("headRefOid") != reviewed_sha:
        return {
            "status": "stale",
            "role": "qa",
            "candidate": vars(candidate),
            "reviewed_sha": reviewed_sha,
            "current_sha": pr.get("headRefOid"),
        }
    contract_markers = _linked_contract_markers(repo, str(pr.get("body") or ""))
    started = time.monotonic()
    result, ledger_path = _run_staged_readonly_agent(
        repo=repo,
        revision=reviewed_sha,
        role="qa",
        agent_command=agent_command,
        timeout=timeout,
        preflight=preflight,
        agent_workspace=agent_workspace,
    )
    if result.returncode != 0:
        raise WorkflowError(f"QA agent failed: {redact_text(result.stderr[-2000:])}")
    response = extract_json_object(result.stdout)
    prepare_sink(
        json.dumps(response, ensure_ascii=False, sort_keys=True),
        sink="qa-result",
        max_bytes=200_000,
    )
    if set(response) - {"summary", "findings", "scenarios"}:
        raise WorkflowError("Unexpected QA response fields")
    if (
        not isinstance(response.get("summary"), str)
        or not isinstance(response.get("findings"), list)
        or not isinstance(response.get("scenarios", []), list)
    ):
        raise WorkflowError("QA response requires summary, findings, and optional scenarios")
    findings = validate_findings(response["findings"])
    for finding in findings:
        marker = finding.acceptance_criterion or finding.non_goal
        if marker not in contract_markers:
            raise WorkflowError(
                f"Finding {finding.finding_id} references unknown contract marker {marker}"
            )
    current = _json_command(
        [
            "gh",
            "pr",
            "view",
            str(candidate.number),
            "--repo",
            repo.slug,
            "--json",
            "headRefOid",
        ],
        cwd=repo.root,
    )
    freshness = evidence_freshness(
        reviewed_sha,
        current["headRefOid"],
        datetime.now(timezone.utc).isoformat(),
    )
    evidence = {
        "schema_version": 1,
        "role": "qa",
        "candidate": vars(candidate),
        "summary": response["summary"],
        "scenarios": response.get("scenarios", []),
        "findings": [finding.to_dict() for finding in findings],
        "freshness": vars(freshness),
        "duration_ms": round((time.monotonic() - started) * 1000),
        "ledger": str(ledger_path),
    }
    output = git_metadata_path(
        repo.root,
        f"templeton-loop/qa/pr-{candidate.number}-{reviewed_sha[:12]}-{uuid.uuid4().hex[:8]}.json",
    )
    from .evidence import atomic_write_json

    prepare_sink(
        json.dumps(evidence, ensure_ascii=False, sort_keys=True),
        sink="qa-evidence",
        max_bytes=200_000,
    )
    atomic_write_json(output, evidence)
    verdict = (
        "stale"
        if freshness.status != "current"
        else "failed"
        if any(finding.disposition == "must-fix" for finding in findings)
        else "passed"
    )
    return {"status": verdict, "evidence": str(output), **evidence}
