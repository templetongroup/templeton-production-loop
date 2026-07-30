from __future__ import annotations

import json
import shlex
import stat
import subprocess
import uuid
from pathlib import Path
from typing import Any, Iterable, Protocol

from .boundaries import BoundaryError, prepare_sink, wrap_untrusted
from .evidence import atomic_write_json, redact_text
from .gitmeta import git_metadata_path
from .policy import hermes_policy_args, validate_agent_id
from .runtime import verify_hermes_runtime, verify_openclaw_runtime
from .staging import StagingError, is_sensitive_path, validate_staged_file
from .workflow import extract_json_object


class SpecError(RuntimeError):
    """Raised when the brokered discovery workflow fails closed."""


class RepoLike(Protocol):
    @property
    def root(self) -> Path: ...

    @property
    def slug(self) -> str: ...

    @property
    def url(self) -> str: ...

    @property
    def default_branch(self) -> str: ...


_CONTEXT_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    ".templeton/loop.json",
)
_RESPONSE_KEYS = {"schema", "status", "summary", "question", "issue_packet"}


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        detail = redact_text((result.stderr or result.stdout).strip())
        raise SpecError(f"Command failed ({result.returncode}): {shlex.join(args)}\n{detail}")
    return result


def _safe_repo_file(repo: RepoLike, relative: str, *, max_bytes: int = 100_000) -> dict[str, Any]:
    pure = Path(relative)
    if pure.is_absolute() or not relative or any(part in {"", ".", ".."} for part in pure.parts):
        raise SpecError(f"Unsafe spec context path: {relative}")
    normalized = pure.as_posix()
    if is_sensitive_path(normalized):
        raise SpecError(f"Sensitive paths cannot be added to spec context: {normalized}")
    target = repo.root / pure
    try:
        target.resolve().relative_to(repo.root.resolve())
    except ValueError as exc:
        raise SpecError(f"Spec context path escapes the repository: {normalized}") from exc
    if target.is_symlink() or not target.is_file():
        raise SpecError(f"Spec context path must be a regular file: {normalized}")
    if target.stat().st_size > max_bytes:
        raise SpecError(f"Spec context file exceeds {max_bytes} bytes: {normalized}")
    try:
        validate_staged_file(target, normalized)
    except StagingError as exc:
        raise SpecError(str(exc)) from exc
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SpecError(f"Spec context file must be UTF-8 text: {normalized}") from exc
    prepared = prepare_sink(text, sink=f"spec-context-file:{normalized}", max_bytes=max_bytes)
    return {"path": normalized, "bytes": prepared.byte_count, "sha256": prepared.sha256, "text": text}


def _read_operator_file(path: Path, *, sink: str, max_bytes: int) -> str:
    requested = path.expanduser()
    normalized = requested.as_posix().lstrip("/")
    try:
        metadata = requested.lstat()
    except OSError as exc:
        raise SpecError(f"Unable to inspect operator input {requested}: {exc}") from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or is_sensitive_path(normalized)
        or is_sensitive_path(requested.name)
    ):
        raise SpecError(f"Operator input must be a regular non-sensitive file: {requested}")
    if metadata.st_size > max_bytes:
        raise SpecError(f"Operator input exceeds {max_bytes} bytes: {requested}")
    try:
        text = requested.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SpecError(f"Unable to read UTF-8 operator input {requested}: {exc}") from exc
    return prepare_sink(text, sink=sink, max_bytes=max_bytes).text


def prepare_spec_context(
    repo: RepoLike,
    *,
    brief: str,
    includes: Iterable[str],
    issue_context: list[dict[str, Any]],
) -> str:
    """Build one bounded, secret-filtered packet before the report-only role runs."""

    safe_brief = prepare_sink(brief, sink="spec-brief", max_bytes=100_000)
    tracked_result = _run(["git", "ls-files", "-z"], cwd=repo.root)
    tracked = sorted(
        path for path in tracked_result.stdout.split("\0") if path and not is_sensitive_path(path)
    )
    selected: list[str] = []
    for relative in [*_CONTEXT_FILES, *includes]:
        normalized = Path(relative).as_posix()
        if normalized in selected:
            continue
        if normalized in _CONTEXT_FILES and not (repo.root / normalized).is_file():
            continue
        if normalized not in tracked:
            if normalized in _CONTEXT_FILES:
                continue
            raise SpecError(f"Explicit spec context file is not tracked by git: {normalized}")
        selected.append(normalized)
    files = [_safe_repo_file(repo, relative) for relative in selected]
    safe_issues = prepare_sink(
        json.dumps(issue_context, ensure_ascii=False, sort_keys=True),
        sink="spec-github-read-context",
        max_bytes=100_000,
    )
    packet = {
        "schema": "templeton.spec-context.v1",
        "repository": {
            "slug": repo.slug,
            "url": repo.url,
            "default_branch": repo.default_branch,
            "tracked_paths": tracked[:2_000],
            "tracked_path_count": len(tracked),
        },
        "brief_and_host_research": safe_brief.text,
        "open_issue_context": json.loads(safe_issues.text),
        "files": files,
    }
    envelope = wrap_untrusted(
        "spec-context",
        packet,
        {"source": "trusted-host-packet-builder", "repository": repo.slug},
    )
    return prepare_sink(envelope, sink="spec-context-packet", max_bytes=300_000).text


def validate_spec_response(value: dict[str, Any], *, confirmed: bool) -> dict[str, Any]:
    if set(value) != _RESPONSE_KEYS:
        raise SpecError(f"Spec response keys must be exactly {sorted(_RESPONSE_KEYS)}")
    if value.get("schema") != "templeton.spec.v1":
        raise SpecError("Spec response schema must be templeton.spec.v1")
    status = value.get("status")
    if status not in {"question", "confirmation", "ready", "blocked"}:
        raise SpecError("Spec status must be question, confirmation, ready, or blocked")
    if confirmed and status != "ready":
        raise SpecError("After explicit broker confirmation the spec role must return a ready issue packet")
    summary = value.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise SpecError("Spec summary must not be empty")
    question = value.get("question")
    issue_packet = value.get("issue_packet")
    if status == "question":
        required = {"text", "why", "recommendation", "alternatives"}
        if not isinstance(question, dict) or set(question) != required or issue_packet is not None:
            raise SpecError("A question response must contain exactly one question and no issue packet")
        for key in ("text", "why", "recommendation"):
            if not isinstance(question.get(key), str) or not question[key].strip():
                raise SpecError(f"Spec question {key} must not be empty")
        alternatives = question.get("alternatives")
        if (
            not isinstance(alternatives, list)
            or not 1 <= len(alternatives) <= 4
            or any(
                not isinstance(item, dict)
                or set(item) != {"option", "tradeoff"}
                or not isinstance(item.get("option"), str)
                or not item["option"].strip()
                or not isinstance(item.get("tradeoff"), str)
                or not item["tradeoff"].strip()
                for item in alternatives
            )
        ):
            raise SpecError(
                "Spec question alternatives must contain one to four objects with non-empty option and tradeoff"
            )
    elif status in {"confirmation", "blocked"}:
        if question is not None or issue_packet is not None:
            raise SpecError(f"A {status} response cannot contain a question or issue packet")
    else:
        if not confirmed:
            raise SpecError("A ready issue packet requires explicit broker confirmation")
        if question is not None or not isinstance(issue_packet, dict):
            raise SpecError("A ready response must contain one issue packet and no question")
        required = {"title", "body", "dependencies", "labels"}
        if set(issue_packet) != required:
            raise SpecError(f"Issue packet keys must be exactly {sorted(required)}")
        if any(
            not isinstance(issue_packet.get(key), str) or not issue_packet[key].strip()
            for key in ("title", "body")
        ):
            raise SpecError("Issue packet title and body must not be empty")
        dependencies = issue_packet.get("dependencies")
        if not isinstance(dependencies, list) or any(not isinstance(item, str) for item in dependencies):
            raise SpecError("Issue packet dependencies must be a string array")
        if issue_packet.get("labels") != ["loop:spec-draft"]:
            raise SpecError("Issue packet labels must be exactly ['loop:spec-draft']")
    prepare_sink(
        json.dumps(value, ensure_ascii=False, sort_keys=True),
        sink="spec-model-response",
        max_bytes=100_000,
    )
    return value


def spec_agent_command(
    *,
    repo: RepoLike,
    runtime: str,
    profile: str,
    agent: str,
    prompt: str,
    timeout: int,
    max_turns: int,
    session: str,
) -> list[str]:
    del repo
    validate_agent_id(session)
    prompt = prepare_sink(prompt, sink="spec-model-prompt", max_bytes=300_000).text
    if runtime == "hermes":
        command = ["hermes"]
        if profile:
            validate_agent_id(profile)
            command.extend(["--profile", profile])
        command.extend(
            [
                "chat",
                *hermes_policy_args("spec"),
                "--skills",
                "templeton-loop-spec",
                "--query",
                prompt,
                "--quiet",
                "--source",
                "tool",
                "--max-turns",
                str(max_turns),
            ]
        )
        return command
    if runtime == "openclaw":
        if not agent:
            raise SpecError("OpenClaw spec runs require --agent AGENT_ID")
        validate_agent_id(agent)
        nonce = uuid.uuid4().hex[:12]
        return [
            "openclaw",
            "agent",
            "--agent",
            agent,
            "--session-key",
            f"agent:{agent}:templeton-loop-spec-{session}-{nonce}",
            "--message",
            prompt,
            "--thinking",
            "high",
            "--timeout",
            str(max(60, timeout)),
            "--json",
        ]
    raise SpecError(f"Unknown runtime: {runtime}")


def _state_path(repo: RepoLike, session: str) -> Path:
    validate_agent_id(session)
    return git_metadata_path(repo.root, f"templeton-loop/spec/{session}.json")


def _load_state(path: Path, repo: RepoLike, session: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise SpecError(f"Spec state is missing or unsafe: {path}")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpecError(f"Invalid spec state {path}: {exc}") from exc
    required = {
        "schema",
        "repo",
        "session",
        "context",
        "context_sha256",
        "transcript_sha256",
        "confirmed",
        "last_status",
        "transcript",
    }
    if not isinstance(state, dict) or set(state) != required:
        raise SpecError("Spec state has an invalid shape")
    if (
        state["schema"] != "templeton.spec-state.v1"
        or state["repo"] != repo.slug
        or state["session"] != session
    ):
        raise SpecError("Spec state identity does not match this repository and session")
    if not isinstance(state["context"], str) or not isinstance(state["transcript"], list):
        raise SpecError("Spec state context or transcript is invalid")
    if (
        not isinstance(state["confirmed"], bool)
        or state["last_status"] not in {"question", "confirmation", "ready", "blocked"}
    ):
        raise SpecError("Spec state status is invalid")
    prepared = prepare_sink(state["context"], sink="spec-resumed-context", max_bytes=300_000)
    if prepared.sha256 != state["context_sha256"]:
        raise SpecError("Spec state context digest mismatch")
    transcript_prepared = prepare_sink(
        json.dumps(state["transcript"], ensure_ascii=False, sort_keys=True),
        sink="spec-resumed-transcript",
        max_bytes=300_000,
    )
    if transcript_prepared.sha256 != state["transcript_sha256"]:
        raise SpecError("Spec state transcript digest mismatch")
    return state


def _prompt(state: dict[str, Any]) -> str:
    transcript = wrap_untrusted(
        "spec-transcript",
        state["transcript"],
        {"source": "broker-state", "confirmed": bool(state["confirmed"])},
    )
    confirmed_instruction = (
        "Tony explicitly confirmed the shared-understanding summary. Return status ready with the final issue packet now."
        if state["confirmed"]
        else "Tony has not confirmed shared understanding. Do not return status ready."
    )
    return (
        '<templeton-spec-broker schema="1">\n'
        "You are the report-only Templeton specification role. Use only the bounded context packet and transcript. "
        "You have no authority to read the repository, use the network, write files, create or update GitHub issues, "
        "or apply labels. Ask exactly one decision at a time. A question response must include one recommended answer, "
        "why it is recommended, and one to four alternatives, each with its concise tradeoff. Researchable facts missing "
        "from the packet require status "
        "blocked, not a question to Tony. When understanding appears complete, return status confirmation with the full "
        "shared-understanding summary. After explicit host confirmation, return status ready with an issue packet labeled "
        "only loop:spec-draft. Never include loop:agent-ready; Tony alone owns that later gate. Return exactly one JSON "
        "object with keys schema, status, summary, question, issue_packet. schema must be templeton.spec.v1. status must be "
        "question, confirmation, ready, or blocked. question is null except for status question, where it has exactly text, "
        "why, recommendation, alternatives. alternatives must be an array of objects with exactly option and tradeoff. "
        "issue_packet is null except for status ready, where it has exactly title, body, "
        f"dependencies, labels. {confirmed_instruction}\n"
        f"{state['context']}\n"
        f"<templeton-spec-transcript>{transcript}</templeton-spec-transcript>\n"
        "</templeton-spec-broker>"
    )


def _workspace(repo: RepoLike, agent: str) -> Path:
    return git_metadata_path(repo.root, f"templeton-loop/openclaw-workspaces/{agent}")


def _require_empty_workspace(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise SpecError(f"OpenClaw spec workspace must be an existing empty directory: {path}")
    if any(path.iterdir()):
        raise SpecError(f"OpenClaw spec workspace must remain empty: {path}")


def _preflight_spec_runtime(
    *, runtime: str, repo: RepoLike, profile: str, agent: str, command: list[str]
) -> dict[str, Any]:
    if runtime == "hermes":
        return verify_hermes_runtime(executable="hermes", profile=profile or None, role="spec")
    if runtime == "openclaw":
        if not agent:
            raise SpecError("OpenClaw spec runs require --agent AGENT_ID")
        workspace = _workspace(repo, agent)
        _require_empty_workspace(workspace)
        try:
            session_key = command[command.index("--session-key") + 1]
        except (ValueError, IndexError) as exc:
            raise SpecError("OpenClaw spec command is missing a fresh session key") from exc
        return verify_openclaw_runtime(
            executable="openclaw",
            agent_id=agent,
            role="spec",
            workspace=workspace,
            session_id=session_key,
        )
    raise SpecError(f"Unknown runtime: {runtime}")


def _adapter_output(runtime: str, stdout: str) -> str:
    if runtime == "hermes":
        return stdout
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise SpecError("OpenClaw spec adapter did not return JSON") from exc
    candidates: list[Any] = []
    if isinstance(payload, dict):
        containers = [payload]
        for key in ("result", "data"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                containers.append(nested)
        for container in containers:
            candidates.extend(
                [container.get("text"), container.get("message"), container.get("response")]
            )
            nested_payloads = container.get("payloads")
            if isinstance(nested_payloads, list):
                candidates.extend(
                    item.get("text") for item in nested_payloads if isinstance(item, dict)
                )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    raise SpecError("OpenClaw spec adapter response contained no text payload")


def run_spec_turn(
    repo: RepoLike,
    *,
    runtime: str,
    profile: str,
    agent: str,
    session: str,
    brief_file: Path | None,
    answer_file: Path | None,
    confirm: bool,
    includes: Iterable[str],
    max_turns: int,
    timeout: int,
    dry_run: bool,
    issue_context: list[dict[str, Any]],
) -> dict[str, Any]:
    include_values = list(includes)
    if confirm and answer_file is not None:
        raise SpecError("Use either --confirm or --answer-file, not both")
    state_path = _state_path(repo, session)
    if state_path.exists() or state_path.is_symlink():
        if brief_file is not None or include_values:
            raise SpecError("A resumed spec session cannot replace its brief or include files")
        state = _load_state(state_path, repo, session)
        if state["last_status"] in {"ready", "blocked"}:
            raise SpecError(f"Spec session is already {state['last_status']}; start a new session")
        if confirm:
            if state["last_status"] != "confirmation":
                raise SpecError("--confirm is valid only after a confirmation response")
            state["confirmed"] = True
            state["transcript"].append(
                {"role": "user", "kind": "confirmation", "text": "CONFIRM"}
            )
        else:
            if answer_file is None:
                raise SpecError("A resumed spec question requires --answer-file or --confirm")
            answer = _read_operator_file(
                answer_file, sink="spec-user-answer", max_bytes=50_000
            )
            state["confirmed"] = False
            state["transcript"].append(
                {
                    "role": "user",
                    "kind": "answer-or-correction",
                    "text": wrap_untrusted(
                        "spec-answer", answer, {"source": answer_file.name}
                    ),
                }
            )
    else:
        if confirm or answer_file is not None:
            raise SpecError(
                "A new spec session requires --brief-file and cannot start with an answer or confirmation"
            )
        if brief_file is None:
            raise SpecError("A new spec session requires --brief-file")
        brief = _read_operator_file(
            brief_file, sink="spec-brief-file", max_bytes=100_000
        )
        context = prepare_spec_context(
            repo,
            brief=brief,
            includes=include_values,
            issue_context=issue_context,
        )
        context_prepared = prepare_sink(
            context, sink="spec-state-context", max_bytes=300_000
        )
        state = {
            "schema": "templeton.spec-state.v1",
            "repo": repo.slug,
            "session": session,
            "context": context,
            "context_sha256": context_prepared.sha256,
            "transcript_sha256": prepare_sink(
                "[]", sink="spec-initial-transcript", max_bytes=300_000
            ).sha256,
            "confirmed": False,
            "last_status": "question",
            "transcript": [],
        }
    prompt = _prompt(state)
    command = spec_agent_command(
        repo=repo,
        runtime=runtime,
        profile=profile,
        agent=agent,
        prompt=prompt,
        timeout=timeout,
        max_turns=max_turns,
        session=session,
    )
    if dry_run:
        prompt_prepared = prepare_sink(prompt, sink="spec-dry-run-prompt", max_bytes=300_000)
        display_command = list(command)
        prompt_flag = "--query" if runtime == "hermes" else "--message"
        prompt_index = display_command.index(prompt_flag) + 1
        display_command[prompt_index] = (
            f"<bounded-spec-prompt bytes={prompt_prepared.byte_count} "
            f"sha256={prompt_prepared.sha256}>"
        )
        return {
            "status": "dry-run",
            "role": "spec",
            "repo": repo.slug,
            "session": session,
            "state": str(state_path),
            "command": display_command,
            "context_sha256": state["context_sha256"],
            "policy": {
                "verified": False,
                "required": "report-only runtime preflight before every turn",
            },
        }
    policy = _preflight_spec_runtime(
        runtime=runtime,
        repo=repo,
        profile=profile,
        agent=agent,
        command=command,
    )
    result = _run(command, cwd=repo.root, check=False, timeout=timeout)
    if result.returncode != 0:
        raise SpecError(f"Spec agent failed: {redact_text(result.stderr[-2000:])}")
    response = validate_spec_response(
        extract_json_object(_adapter_output(runtime, result.stdout)),
        confirmed=state["confirmed"],
    )
    state["last_status"] = response["status"]
    state["transcript"].append({"role": "assistant", "response": response})
    state["transcript_sha256"] = prepare_sink(
        json.dumps(state["transcript"], ensure_ascii=False, sort_keys=True),
        sink="spec-transcript-state",
        max_bytes=300_000,
    ).sha256
    atomic_write_json(state_path, state)
    if runtime == "openclaw":
        _require_empty_workspace(_workspace(repo, agent))
    output: dict[str, Any] = {
        "status": response["status"],
        "role": "spec",
        "repo": repo.slug,
        "session": session,
        "state": str(state_path),
        "summary": response["summary"],
        "question": response["question"],
        "issue_packet": response["issue_packet"],
        "policy": policy,
    }
    if response["issue_packet"] is not None:
        prepared = prepare_sink(
            json.dumps(response["issue_packet"], ensure_ascii=False, sort_keys=True),
            sink="github-issue-packet",
            max_bytes=100_000,
        )
        output["issue_packet_sha256"] = prepared.sha256
        output["handoff"] = (
            "Tony or the trusted host may file this packet as loop:spec-draft; "
            "Tony alone may later apply loop:agent-ready."
        )
    return output
