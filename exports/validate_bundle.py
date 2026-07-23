#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {
    "templeton-loop-spec",
    "templeton-loop-build",
    "templeton-loop-review",
    "templeton-loop-status",
}


def main() -> int:
    candidates = [ROOT / "skills", ROOT / "skills-openclaw"]
    present = [path for path in candidates if path.is_dir()]
    if len(present) != 1:
        raise SystemExit(f"Expected exactly one runtime skill directory; found: {present}")
    skill_root = present[0]
    actual = {path.name for path in skill_root.iterdir() if path.is_dir()}
    if actual != EXPECTED:
        raise SystemExit(f"Skill inventory mismatch: expected {sorted(EXPECTED)}, got {sorted(actual)}")

    combined: dict[str, str] = {}
    for name in sorted(EXPECTED):
        path = skill_root / name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            raise SystemExit(f"Missing YAML frontmatter: {path}")
        frontmatter = text.split("---\n", 2)[1]
        if not re.search(rf"^name:\s*{re.escape(name)}\s*$", frontmatter, re.MULTILINE):
            raise SystemExit(f"Frontmatter name mismatch: {path}")
        if not re.search(r"^description:\s*\S", frontmatter, re.MULTILINE):
            raise SystemExit(f"Missing description: {path}")
        combined[name] = text

    checks = {
        "spec human gate": "Never add `loop:agent-ready`" in combined["templeton-loop-spec"],
        "build no merge/deploy": "Never merge, enable auto-merge, deploy" in combined["templeton-loop-build"],
        "build retry cap": "at most two builder repair rounds" in combined["templeton-loop-build"],
        "review required CI": "gh pr checks NUMBER --required" in combined["templeton-loop-review"],
        "review no code push": "Never push code" in combined["templeton-loop-review"],
        "review SHA pin": "Templeton Loop review of COMMIT_SHA" in combined["templeton-loop-review"],
        "status read only": "never mutate" in combined["templeton-loop-status"].lower(),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise SystemExit("Safety contract validation failed: " + ", ".join(failed))

    runtime = "openclaw" if skill_root.name == "skills-openclaw" else "hermes"
    print(f"TEMPLETON_LOOP_BUNDLE_OK runtime={runtime} skills={len(EXPECTED)} safety_checks={len(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
