from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {
    "templeton-loop-spec",
    "templeton-loop-build",
    "templeton-loop-review",
    "templeton-loop-status",
}


def test_skill_inventory_and_frontmatter():
    actual = {path.name for path in (ROOT / "skills").iterdir() if path.is_dir()}
    assert actual == EXPECTED
    for name in EXPECTED:
        text = (ROOT / "skills" / name / "SKILL.md").read_text()
        assert text.startswith("---\n")
        frontmatter = text.split("---\n", 2)[1]
        assert f"name: {name}\n" in frontmatter
        assert "description:" in frontmatter


def test_human_gates_are_present_in_role_skills():
    spec = (ROOT / "skills/templeton-loop-spec/SKILL.md").read_text()
    build = (ROOT / "skills/templeton-loop-build/SKILL.md").read_text()
    review = (ROOT / "skills/templeton-loop-review/SKILL.md").read_text()
    assert "Never add `loop:agent-ready`" in spec
    assert "Never merge, enable auto-merge, deploy" in build
    assert "at most two builder repair rounds" in build
    assert "gh pr checks NUMBER --required" in review
    assert "No required CI means `loop:needs-human-review`" in review
    assert "Never push code" in review
    assert "Templeton Loop review of COMMIT_SHA" in review
