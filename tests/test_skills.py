from __future__ import annotations

import re
from pathlib import Path

import pytest

from templeton_loop.edition import EDITION


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "templeton-build"
REFERENCE_FILES = {
    "understand.md",
    "discovery.md",
    "setup.md",
    "implementation.md",
    "frontend.md",
    "review-and-qa.md",
    "release-and-handoff.md",
    "broker-modes.md",
    "spec.md",
    "plan-review.md",
    "build.md",
    "review.md",
    "qa.md",
    "status.md",
    "prove.md",
}
FORBIDDEN_STANDALONE_SKILLS = {
    "templeton-loop-spec",
    "templeton-loop-plan-review",
    "templeton-loop-build",
    "templeton-loop-review",
    "templeton-loop-qa",
    "templeton-loop-status",
    "templeton-loop-prove",
    "templeton-architecture-review",
    "templeton-grill",
    "templeton-handoff",
    "templeton-questionnaire",
    "templeton-wait-what",
    "templeton-writing-for-agents",
}


def _skill_roots() -> tuple[Path, ...]:
    roots = [ROOT / "skills", ROOT / "skills-openclaw"]
    if EDITION == "hermes":
        roots.append(ROOT / "templeton_loop" / "resources" / "skills")
    return tuple(path for path in roots if path.exists())


def _frontmatter(text: str) -> str:
    assert text.startswith("---\n")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    assert match is not None
    return match.group(1)


@pytest.mark.parametrize("root", _skill_roots(), ids=lambda path: path.as_posix())
def test_exactly_one_templeton_build_skill_is_shipped(root: Path) -> None:
    directories = sorted(path.name for path in root.iterdir() if path.is_dir())
    assert directories == [SKILL_NAME]

    skill_dir = root / SKILL_NAME
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = _frontmatter(text)
    assert re.search(r"^name:\s*templeton-build\s*$", frontmatter, re.M)
    assert "description:" in frontmatter
    assert "Use when" in frontmatter

    references = skill_dir / "references"
    reference_paths = [path for path in references.iterdir() if path.is_file()]
    assert {path.name for path in reference_paths} == REFERENCE_FILES
    assert all(not path.read_text(encoding="utf-8").startswith("---\n") for path in reference_paths)


@pytest.mark.parametrize("root", _skill_roots(), ids=lambda path: path.as_posix())
def test_combined_skill_preserves_internal_role_separation(root: Path) -> None:
    skill_dir = root / SKILL_NAME
    main = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    modes = (skill_dir / "references" / "broker-modes.md").read_text(encoding="utf-8")
    review = (skill_dir / "references" / "review-and-qa.md").read_text(encoding="utf-8")

    for mode in ("spec", "plan-review", "build", "review", "qa", "status", "prove"):
        assert f"`{mode}`" in main
    assert "One skill name is a simpler interface, not permission aggregation" in main
    assert "Never combine worker authority" in modes
    assert "The reviewer is report-only and cannot edit code" in review
    assert "Templeton Loop review of HEAD_SHA against BASE_SHA" in review
    assert "Review-State: verdict=<approved|changes-requested|needs-human-review|awaiting-review>" in review
    assert "partial coverage and cannot support approval" in review
    assert "reconcile totals programmatically" in review.lower()

    exact_review = (skill_dir / "references" / "review.md").read_text(encoding="utf-8")
    build = (skill_dir / "references" / "build.md").read_text(encoding="utf-8")
    spec = (skill_dir / "references" / "spec.md").read_text(encoding="utf-8")
    prove = (skill_dir / "references" / "prove.md").read_text(encoding="utf-8")
    discovery = (skill_dir / "references" / "discovery.md").read_text(encoding="utf-8")
    setup = (skill_dir / "references" / "setup.md").read_text(encoding="utf-8")
    assert 'templeton-spec-broker schema="1"' in spec
    assert "Tony alone may apply" in spec
    assert "at most two builder repair rounds" in build
    assert "gh pr checks NUMBER --required" in exact_review
    assert "verdict=approved; coverage=complete" in exact_review
    assert "never targets the original source tree" in prove
    assert "does not scaffold" in discovery
    assert "Require explicit operator confirmation" in discovery
    assert "Setup-only mode never scaffolds" in setup


def test_superseded_standalone_skill_directories_are_absent() -> None:
    for parent in (ROOT / "skills", ROOT / "skills-openclaw"):
        if not parent.exists():
            continue
        names = {path.name for path in parent.iterdir() if path.is_dir()}
        assert names.isdisjoint(FORBIDDEN_STANDALONE_SKILLS)
    assert not (ROOT / "optional-skills").exists()
    third_party = ROOT / "third_party"
    if third_party.exists():
        assert not list(third_party.rglob("SKILL.md"))


def test_combined_skill_has_direct_operator_workflow() -> None:
    root = _skill_roots()[0]
    text = (root / SKILL_NAME / "SKILL.md").read_text(encoding="utf-8")
    assert "The operator describes the outcome in plain English" in text
    assert "Do not force a questionnaire, project seed, GitHub issue" in text
    assert "fresh independent reviewer" in text
    assert "Done means the requested artifact exists and was exercised" in text
