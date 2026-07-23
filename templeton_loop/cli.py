from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


LABELS: dict[str, tuple[str, str]] = {
    "loop:spec-draft": ("D4C5F9", "Spec drafted; awaiting human approval"),
    "loop:agent-ready": ("0E8A16", "Human-approved contract ready for an agent"),
    "loop:building": ("1D76DB", "Claimed by the coding loop"),
    "loop:blocked": ("B60205", "Agent needs one concrete human decision"),
    "loop:awaiting-review": ("FBCA04", "Builder PR awaiting fresh-context review"),
    "loop:approved": ("0E8A16", "SHA-pinned loop review and required CI passed"),
    "loop:changes-requested": ("D93F0B", "Loop reviewer found must-fix items"),
    "loop:needs-human-review": ("B60205", "Automated lane stopped for human judgment"),
    "loop:stuck": ("5319E7", "Repair budget exhausted"),
}
TERMINAL_REVIEW_LABELS = {
    "loop:approved",
    "loop:changes-requested",
    "loop:needs-human-review",
}
PRIORITY_LABELS = {
    "priority:p0": 0,
    "priority:urgent": 0,
    "priority:p1": 1,
    "priority:high": 1,
    "priority:p2": 2,
    "priority:medium": 2,
    "priority:p3": 3,
    "priority:low": 3,
}
REVIEW_PREFIX = "Templeton Loop review of "


class LoopError(RuntimeError):
    pass


@dataclass(frozen=True)
class Repo:
    root: Path
    slug: str
    url: str
    default_branch: str


@dataclass(frozen=True)
class Candidate:
    number: int
    title: str
    url: str
    head_sha: str | None = None
    kind: str = "issue"


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise LoopError(f"Command failed ({result.returncode}): {shlex.join(args)}\n{detail}")
    return result


def _json(result: subprocess.CompletedProcess[str]) -> Any:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise LoopError(f"Expected JSON from command; got: {result.stdout[:500]}") from exc


def resolve_repo(path: str | Path) -> Repo:
    requested = Path(path).expanduser().resolve()
    root_result = _run(["git", "rev-parse", "--show-toplevel"], cwd=requested)
    root = Path(root_result.stdout.strip()).resolve()
    data = _json(
        _run(
            [
                "gh",
                "repo",
                "view",
                "--json",
                "nameWithOwner,url,defaultBranchRef",
            ],
            cwd=root,
        )
    )
    branch = (data.get("defaultBranchRef") or {}).get("name")
    if not branch:
        raise LoopError("GitHub did not return the repository default branch")
    return Repo(root=root, slug=data["nameWithOwner"], url=data["url"], default_branch=branch)


def label_names(item: dict[str, Any]) -> set[str]:
    return {
        label["name"] if isinstance(label, dict) else str(label)
        for label in item.get("labels", [])
    }


def issue_priority(issue: dict[str, Any]) -> int:
    names = {name.lower() for name in label_names(issue)}
    return min((PRIORITY_LABELS[name] for name in names if name in PRIORITY_LABELS), default=4)


def choose_build_issue(issues: Iterable[dict[str, Any]]) -> Candidate | None:
    eligible: list[dict[str, Any]] = []
    for issue in issues:
        names = label_names(issue)
        if "loop:agent-ready" not in names:
            continue
        if {"loop:blocked", "loop:building"} & names:
            continue
        if issue.get("assignees"):
            continue
        eligible.append(issue)
    if not eligible:
        return None
    eligible.sort(key=lambda item: (issue_priority(item), item.get("createdAt", ""), item["number"]))
    chosen = eligible[0]
    return Candidate(chosen["number"], chosen["title"], chosen["url"])


def latest_review_sha(comments: Iterable[dict[str, Any]]) -> str | None:
    latest: tuple[str, str] | None = None
    for comment in comments:
        first = (comment.get("body") or "").splitlines()[0].strip()
        if not first.startswith(REVIEW_PREFIX):
            continue
        sha = first[len(REVIEW_PREFIX) :].strip().split()[0]
        created = comment.get("created_at") or comment.get("createdAt") or ""
        if sha and (latest is None or created >= latest[0]):
            latest = (created, sha)
    return latest[1] if latest else None


def pr_needs_review(pr: dict[str, Any], comments: Iterable[dict[str, Any]]) -> bool:
    if pr.get("isDraft"):
        return False
    current = pr.get("headRefOid")
    if not current:
        return True
    reviewed = latest_review_sha(comments)
    names = label_names(pr)
    return not (reviewed == current and bool(names & TERMINAL_REVIEW_LABELS))


def list_issues(repo: Repo) -> list[dict[str, Any]]:
    return _json(
        _run(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                repo.slug,
                "--state",
                "open",
                "--limit",
                "100",
                "--label",
                "loop:agent-ready",
                "--json",
                "number,title,url,createdAt,labels,assignees",
            ],
            cwd=repo.root,
        )
    )


def list_prs(repo: Repo) -> list[dict[str, Any]]:
    return _json(
        _run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                repo.slug,
                "--state",
                "open",
                "--limit",
                "100",
                "--json",
                "number,title,url,isDraft,headRefOid,updatedAt,labels",
            ],
            cwd=repo.root,
        )
    )


def pr_comments(repo: Repo, number: int) -> list[dict[str, Any]]:
    pages = _json(
        _run(
            [
                "gh",
                "api",
                "--paginate",
                "--slurp",
                f"repos/{repo.slug}/issues/{number}/comments",
            ],
            cwd=repo.root,
        )
    )
    return [comment for page in pages for comment in page]


def choose_repair_pr(prs: Iterable[dict[str, Any]]) -> Candidate | None:
    eligible: list[dict[str, Any]] = []
    for pr in prs:
        names = label_names(pr)
        if "loop:changes-requested" not in names:
            continue
        if {"loop:needs-human-review", "loop:stuck"} & names:
            continue
        if pr.get("isDraft"):
            continue
        eligible.append(pr)
    if not eligible:
        return None
    eligible.sort(key=lambda item: (item.get("updatedAt", ""), item["number"]))
    chosen = eligible[0]
    return Candidate(
        chosen["number"],
        chosen["title"],
        chosen["url"],
        head_sha=chosen.get("headRefOid"),
        kind="pr-repair",
    )


def choose_review_pr(repo: Repo, prs: Iterable[dict[str, Any]] | None = None) -> Candidate | None:
    pending: list[dict[str, Any]] = []
    for pr in prs if prs is not None else list_prs(repo):
        if pr_needs_review(pr, pr_comments(repo, pr["number"])):
            pending.append(pr)
    if not pending:
        return None
    pending.sort(key=lambda item: (item.get("updatedAt", ""), item["number"]))
    chosen = pending[0]
    return Candidate(
        chosen["number"],
        chosen["title"],
        chosen["url"],
        head_sha=chosen.get("headRefOid"),
    )


def build_candidate(repo: Repo) -> Candidate | None:
    return choose_repair_pr(list_prs(repo)) or choose_build_issue(list_issues(repo))


def required_checks(repo: Repo) -> dict[str, Any]:
    result = _run(
        [
            "gh",
            "api",
            f"repos/{repo.slug}/branches/{repo.default_branch}/protection",
        ],
        cwd=repo.root,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        return {
            "status": "not_configured_or_unavailable",
            "checks": [],
            "detail": detail[-1] if detail else "GitHub branch protection was unavailable",
        }
    data = _json(result)
    required = data.get("required_status_checks") or {}
    checks = [check.get("context") for check in required.get("checks", []) if check.get("context")]
    checks.extend(context for context in required.get("contexts", []) if context not in checks)
    return {"status": "configured" if checks else "not_configured", "checks": checks}


def remote_labels(repo: Repo) -> set[str]:
    data = _json(
        _run(
            ["gh", "label", "list", "--repo", repo.slug, "--limit", "200", "--json", "name"],
            cwd=repo.root,
        )
    )
    return {item["name"] for item in data}


def doctor(repo: Repo) -> dict[str, Any]:
    auth = _run(["gh", "auth", "status"], cwd=repo.root, check=False)
    dirty = bool(_run(["git", "status", "--porcelain"], cwd=repo.root).stdout.strip())
    labels = remote_labels(repo)
    return {
        "ok": auth.returncode == 0,
        "repo": repo.slug,
        "repo_url": repo.url,
        "repo_root": str(repo.root),
        "default_branch": repo.default_branch,
        "gh_authenticated": auth.returncode == 0,
        "working_tree_clean": not dirty,
        "labels": {
            "present": sorted(labels & LABELS.keys()),
            "missing": sorted(LABELS.keys() - labels),
        },
        "required_checks": required_checks(repo),
    }


def init_labels(repo: Repo, *, apply: bool) -> list[list[str]]:
    commands: list[list[str]] = []
    for name, (color, description) in LABELS.items():
        command = [
            "gh",
            "label",
            "create",
            name,
            "--repo",
            repo.slug,
            "--color",
            color,
            "--description",
            description,
            "--force",
        ]
        commands.append(command)
        if apply:
            _run(command, cwd=repo.root)
    return commands


def queue_state(repo: Repo) -> dict[str, Any]:
    issue = build_candidate(repo)
    review = choose_review_pr(repo)
    return {
        "repo": repo.slug,
        "next_build": vars(issue) if issue else None,
        "next_review": vars(review) if review else None,
    }


def agent_command(
    *,
    repo: Repo,
    role: str,
    candidate: Candidate,
    profile: str,
    max_turns: int,
) -> list[str]:
    if role == "build":
        skill = "templeton-loop-build"
        subject = (
            f"GitHub PR #{candidate.number} repair at head {candidate.head_sha or 'unknown'}"
            if candidate.kind == "pr-repair"
            else f"GitHub issue #{candidate.number}"
        )
    elif role == "review":
        skill = "templeton-loop-review"
        subject = f"GitHub PR #{candidate.number} at head {candidate.head_sha or 'unknown'}"
    else:
        raise LoopError(f"Unknown role: {role}")
    prompt = (
        f"Run exactly one Templeton coding-loop {role} pass for {subject} in "
        f"{repo.slug}. Follow the loaded skill and repository instructions. "
        "Re-read live GitHub state before every mutation. Stop after this one unit of work. "
        "Never merge, enable auto-merge, deploy, publish, purchase, or mutate production. "
        "Return result, evidence, risk, and next action."
    )
    command = ["hermes"]
    if profile:
        command.extend(["--profile", profile])
    command.extend(
        [
            "chat",
            "--worktree",
            "--skills",
            skill,
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


@contextlib.contextmanager
def role_lock(repo: Repo, role: str):
    lock_dir = repo.root / ".git" / "templeton-loop"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{role}.lock"
    with lock_path.open("w") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LoopError(f"A {role} loop already holds {lock_path}") from exc
        handle.write(f"pid={os.getpid()} started={datetime.now(timezone.utc).isoformat()}\n")
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def run_pass(
    repo: Repo,
    *,
    role: str,
    profile: str,
    max_turns: int,
    timeout: int,
    dry_run: bool,
) -> dict[str, Any]:
    candidate = build_candidate(repo) if role == "build" else choose_review_pr(repo)
    if candidate is None:
        return {"status": "idle", "role": role, "repo": repo.slug}
    command = agent_command(
        repo=repo,
        role=role,
        candidate=candidate,
        profile=profile,
        max_turns=max_turns,
    )
    if dry_run:
        return {
            "status": "dry-run",
            "role": role,
            "candidate": vars(candidate),
            "command": command,
        }

    log_dir = repo.root / ".git" / "templeton-loop" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = log_dir / f"{role}-{candidate.number}-{stamp}.log"
    result = _run(command, cwd=repo.root, check=False, timeout=timeout)
    log_path.write_text(
        f"$ {shlex.join(command)}\n\nSTDOUT\n{result.stdout}\n\nSTDERR\n{result.stderr}\n",
        encoding="utf-8",
    )
    return {
        "status": "completed" if result.returncode == 0 else "failed",
        "role": role,
        "candidate": vars(candidate),
        "exit_code": result.returncode,
        "log": str(log_path),
        "output": result.stdout.strip()[-4000:],
        "error": result.stderr.strip()[-2000:],
    }


def install_skills(profile: str, *, apply: bool, force: bool) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parent.parent
    source = project_root / "skills"
    config_cmd = ["hermes"]
    if profile:
        config_cmd.extend(["--profile", profile])
    config_cmd.extend(["config", "path"])
    config_path = Path(_run(config_cmd).stdout.strip()).expanduser().resolve()
    destination = config_path.parent / "skills"
    planned: list[dict[str, str]] = []
    for skill_dir in sorted(path for path in source.iterdir() if path.is_dir()):
        target = destination / skill_dir.name
        planned.append({"source": str(skill_dir), "destination": str(target)})
        if not apply:
            continue
        if target.exists():
            if not force:
                raise LoopError(f"Skill already exists: {target}; pass --force to replace it")
            shutil.rmtree(target)
        shutil.copytree(skill_dir, target)
    return {
        "status": "installed" if apply else "dry-run",
        "profile": profile or "default",
        "config": str(config_path),
        "skills": planned,
    }


def print_result(data: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}: {json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value}")
    else:
        print(data)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="templeton-loop")
    root.add_argument("--json", action="store_true", help="Emit JSON")
    sub = root.add_subparsers(dest="command", required=True)

    for name in ("doctor", "queue"):
        command = sub.add_parser(name)
        command.add_argument("--repo", default=".")

    init = sub.add_parser("init")
    init.add_argument("--repo", default=".")
    init.add_argument("--apply", action="store_true", help="Create/update GitHub labels")

    run = sub.add_parser("run")
    run.add_argument("role", choices=("build", "review"))
    run.add_argument("--repo", default=".")
    run.add_argument("--profile", default="nikki")
    run.add_argument("--max-turns", type=int, default=90)
    run.add_argument("--timeout", type=int, default=3600)
    run.add_argument("--interval", type=int, default=300)
    run.add_argument("--max-passes", type=int, default=1)
    run.add_argument("--forever", action="store_true")
    run.add_argument("--dry-run", action="store_true")

    install = sub.add_parser("install-skills")
    install.add_argument("--profile", default="nikki")
    install.add_argument("--apply", action="store_true")
    install.add_argument("--force", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "install-skills":
            print_result(
                install_skills(args.profile, apply=args.apply, force=args.force),
                as_json=args.json,
            )
            return 0

        repo = resolve_repo(args.repo)
        if args.command == "doctor":
            data = doctor(repo)
        elif args.command == "queue":
            data = queue_state(repo)
        elif args.command == "init":
            commands = init_labels(repo, apply=args.apply)
            data = {
                "status": "applied" if args.apply else "dry-run",
                "repo": repo.slug,
                "commands": [shlex.join(command) for command in commands],
            }
        elif args.command == "run":
            passes = 0
            with role_lock(repo, args.role):
                while args.forever or passes < args.max_passes:
                    data = run_pass(
                        repo,
                        role=args.role,
                        profile=args.profile,
                        max_turns=args.max_turns,
                        timeout=args.timeout,
                        dry_run=args.dry_run,
                    )
                    print_result(data, as_json=args.json)
                    passes += 1
                    if args.dry_run or (not args.forever and passes >= args.max_passes):
                        break
                    time.sleep(args.interval)
            return 0
        else:
            raise LoopError(f"Unsupported command: {args.command}")
        print_result(data, as_json=args.json)
        return 0
    except (LoopError, subprocess.TimeoutExpired) as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
