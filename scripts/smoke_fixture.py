#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run(args, *, cwd, env):
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"{args} failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="templeton-loop-smoke-") as temp:
        base = Path(temp)
        repo = base / "widget"
        fakebin = base / "bin"
        fakebin.mkdir()
        repo.mkdir()
        label_log = base / "labels.log"

        gh = fakebin / "gh"
        gh.write_text(
            """#!/usr/bin/env python3
import json, os, sys
args=sys.argv[1:]
if args[:2] == ['repo','view']:
    print(json.dumps({'nameWithOwner':'acme/widget','url':'https://github.com/acme/widget','defaultBranchRef':{'name':'main'}}))
elif args[:2] == ['auth','status']:
    print('authenticated', file=sys.stderr)
elif args[:2] == ['label','list']:
    print('[]')
elif args[:2] == ['label','create']:
    with open(os.environ['FAKE_LABEL_LOG'],'a') as f: f.write(args[2]+'\\n')
elif args[:2] == ['issue','list']:
    print(json.dumps([{'number':12,'title':'Fixture issue','url':'https://github.com/acme/widget/issues/12','createdAt':'2026-01-01T00:00:00Z','labels':[{'name':'loop:agent-ready'}],'assignees':[]}]))
elif args[:2] == ['pr','list']:
    print('[]')
elif args and args[0] == 'api' and '/protection' in args[-1]:
    print(json.dumps({'required_status_checks':{'checks':[{'context':'test'}],'contexts':[]}}))
else:
    print('unhandled fake gh: '+repr(args), file=sys.stderr); sys.exit(2)
""",
            encoding="utf-8",
        )
        gh.chmod(0o755)

        hermes = fakebin / "hermes"
        hermes.write_text(
            """#!/usr/bin/env python3
import sys
print('FAKE_HERMES_BUILD_PASS_OK')
""",
            encoding="utf-8",
        )
        hermes.chmod(0o755)

        openclaw_log = base / "openclaw.log"
        openclaw = fakebin / "openclaw"
        openclaw.write_text(
            """#!/usr/bin/env python3
import json, os, sys
with open(os.environ['FAKE_OPENCLAW_LOG'],'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
print(json.dumps({'ok':True,'reply':'FAKE_OPENCLAW_BUILD_PASS_OK'}))
""",
            encoding="utf-8",
        )
        openclaw.chmod(0o755)

        env = os.environ.copy()
        env["PATH"] = f"{fakebin}:{env['PATH']}"
        env["FAKE_LABEL_LOG"] = str(label_log)
        env["FAKE_OPENCLAW_LOG"] = str(openclaw_log)

        run(["git", "init", "-b", "main"], cwd=repo, env=env)
        run(["git", "config", "user.email", "loop@example.test"], cwd=repo, env=env)
        run(["git", "config", "user.name", "Loop Fixture"], cwd=repo, env=env)
        (repo / "README.md").write_text("fixture\n", encoding="utf-8")
        run(["git", "add", "README.md"], cwd=repo, env=env)
        run(["git", "commit", "-m", "fixture"], cwd=repo, env=env)
        run(["git", "remote", "add", "origin", "https://github.com/acme/widget.git"], cwd=repo, env=env)

        cli = [sys.executable, "-m", "templeton_loop.cli"]
        doctor = json.loads(run(cli + ["--json", "doctor", "--repo", str(repo)], cwd=ROOT, env=env).stdout)
        assert doctor["repo"] == "acme/widget"
        assert doctor["required_checks"]["checks"] == ["test"]

        run(cli + ["--json", "init", "--repo", str(repo), "--apply"], cwd=ROOT, env=env)
        assert len(label_log.read_text().splitlines()) == 9

        queue = json.loads(run(cli + ["--json", "queue", "--repo", str(repo)], cwd=ROOT, env=env).stdout)
        assert queue["next_build"]["number"] == 12
        assert queue["next_review"] is None

        built = json.loads(
            run(
                cli
                + [
                    "--json",
                    "run",
                    "build",
                    "--repo",
                    str(repo),
                    "--profile",
                    "nikki",
                    "--timeout",
                    "30",
                ],
                cwd=ROOT,
                env=env,
            ).stdout
        )
        assert built["status"] == "completed"
        assert built["candidate"]["number"] == 12
        assert "FAKE_HERMES_BUILD_PASS_OK" in built["output"]
        log = Path(built["log"]).read_text()
        assert "--worktree" in log
        assert "Never merge" in log

        openclaw_built = json.loads(
            run(
                cli
                + [
                    "--json",
                    "run",
                    "build",
                    "--runtime",
                    "openclaw",
                    "--agent",
                    "builder",
                    "--repo",
                    str(repo),
                    "--timeout",
                    "30",
                ],
                cwd=ROOT,
                env=env,
            ).stdout
        )
        assert openclaw_built["status"] == "completed"
        assert "FAKE_OPENCLAW_BUILD_PASS_OK" in openclaw_built["output"]
        invocation = json.loads(openclaw_log.read_text().splitlines()[-1])
        assert invocation[:2] == ["agent", "--agent"]
        assert "builder" in invocation
        assert any(value.startswith("agent:builder:templeton-loop-build-12-") for value in invocation)
        assert "--json" in invocation

        install_preview = json.loads(
            run(
                cli + ["--json", "install-skills", "--runtime", "openclaw", "--agent", "builder"],
                cwd=ROOT,
                env=env,
            ).stdout
        )
        assert install_preview["status"] == "dry-run"
        assert len(install_preview["skills"]) == 4

        review = json.loads(
            run(cli + ["--json", "run", "review", "--repo", str(repo), "--timeout", "30"], cwd=ROOT, env=env).stdout
        )
        assert review["status"] == "idle"
        print("TEMPLETON_LOOP_FIXTURE_OK doctor labels hermes-build openclaw-build review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
