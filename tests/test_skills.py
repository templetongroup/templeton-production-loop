from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {
    "templeton-loop-spec",
    "templeton-loop-build",
    "templeton-loop-review",
    "templeton-loop-status",
}


def test_skill_inventory_and_frontmatter():
    for folder in ("skills", "skills-openclaw"):
        actual = {path.name for path in (ROOT / folder).iterdir() if path.is_dir()}
        assert actual == EXPECTED
        for name in EXPECTED:
            text = (ROOT / folder / name / "SKILL.md").read_text()
            assert text.startswith("---\n")
            frontmatter = text.split("---\n", 2)[1]
            assert f"name: {name}\n" in frontmatter
            assert "description:" in frontmatter


def test_human_gates_are_present_in_role_skills():
    for folder in ("skills", "skills-openclaw"):
        spec = (ROOT / folder / "templeton-loop-spec/SKILL.md").read_text()
        build = (ROOT / folder / "templeton-loop-build/SKILL.md").read_text()
        review = (ROOT / folder / "templeton-loop-review/SKILL.md").read_text()
        assert "Never add `loop:agent-ready`" in spec
        assert "Never merge, enable auto-merge, deploy" in build
        assert "at most two builder repair rounds" in build
        assert "gh pr checks NUMBER --required" in review
        assert "No required CI means `loop:needs-human-review`" in review
        assert "Never push code" in review
        assert "Templeton Loop review of COMMIT_SHA" in review


def test_openclaw_builder_requires_isolated_worktree():
    build = (ROOT / "skills-openclaw/templeton-loop-build/SKILL.md").read_text()
    assert "dedicated git worktree" in build
    assert "Never edit a dirty checkout" in build
    assert "GitHub assignment is a cooperative lock" in build
