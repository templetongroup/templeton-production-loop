from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CORE_SKILLS = {
    "templeton-loop-spec",
    "templeton-loop-plan-review",
    "templeton-loop-build",
    "templeton-loop-review",
    "templeton-loop-qa",
    "templeton-loop-status",
}
HERMES_SKILLS = CORE_SKILLS | {"templeton-loop-prove"}
OPENCLAW_SKILLS = CORE_SKILLS | {"templeton-loop-prove"}
RUNTIME_SKILLS = {
    "skills": HERMES_SKILLS,
    "skills-openclaw": OPENCLAW_SKILLS,
}


def present_runtime_skills() -> dict[str, set[str]]:
    return {
        folder: expected
        for folder, expected in RUNTIME_SKILLS.items()
        if (ROOT / folder).is_dir()
    }


def test_skill_inventory_and_frontmatter():
    for folder, expected in present_runtime_skills().items():
        actual = {path.name for path in (ROOT / folder).iterdir() if path.is_dir()}
        assert actual == expected
        for name in expected:
            text = (ROOT / folder / name / "SKILL.md").read_text()
            assert text.startswith("---\n")
            frontmatter = text.split("---\n", 2)[1]
            assert f"name: {name}\n" in frontmatter
            assert "description:" in frontmatter


def test_human_gates_are_present_in_role_skills():
    for folder in present_runtime_skills():
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
        plan_review = (ROOT / folder / "templeton-loop-plan-review/SKILL.md").read_text()
        qa = (ROOT / folder / "templeton-loop-qa/SKILL.md").read_text()
        assert "report-only" in plan_review.lower()
        assert "Blocking User Decision" in plan_review
        assert "report-only" in qa.lower()
        assert "evidence freshness" in qa.lower()


def test_spec_requires_guided_interview_before_issue_mutation():
    required_contract = (
        "Never run it unattended",
        "bounded, secret-filtered repository and research context",
        "Use only that bounded context",
        "Look up facts inside the supplied context",
        "Ask exactly one decision question at a time",
        "provide the recommended answer first",
        "Surface better options and new ideas",
        "shared understanding",
        "Do not create or update an issue at any point",
        "Output an approved issue packet",
        "Tony alone may apply",
        "interview transcripts and chat are not hidden scope",
    )
    runtime_specs = []
    for folder in present_runtime_skills():
        spec = (ROOT / folder / "templeton-loop-spec/SKILL.md").read_text()
        runtime_specs.append(spec)
        for requirement in required_contract:
            assert requirement in spec
    assert len(set(runtime_specs)) == 1


def test_openclaw_builder_requires_secret_filtered_staging():
    if not (ROOT / "skills-openclaw").is_dir():
        return
    build = (ROOT / "skills-openclaw/templeton-loop-build/SKILL.md").read_text()
    assert "stages a secret-filtered tree without `.git`" in build
    assert "Children never receive GitHub credentials" in build
    assert "deterministic host broker" in build


def test_proof_skills_preserve_v1_boundaries():
    for directory in ("skills", "skills-openclaw"):
        if not (ROOT / directory).is_dir():
            continue
        prove = (ROOT / directory / "templeton-loop-prove/SKILL.md").read_text()
        assert "trusted plan" in prove.lower()
        assert "strategy" in prove.lower()
        assert "model" in prove.lower()
    assert "per-task" in prove.lower()
    assert "source tree" in prove.lower()
    assert "Never merge, deploy" in prove
    assert "auto-update" in prove.lower()
    assert "global hooks" in prove.lower()
    assert "Ringer-derived code or assets" in prove


def test_optional_architecture_review_is_report_only_and_outside_core_inventory():
    optional = ROOT / "optional-skills" / "templeton-architecture-review" / "SKILL.md"
    assert optional.is_file()
    text = optional.read_text()
    assert text.startswith("---\n")
    assert "name: templeton-architecture-review\n" in text
    assert "report-only" in text.lower()
    assert "loop:agent-ready" in text
    assert "Never" in text
    assert "edit source" in text
    assert "8b78b531ab965735c5dc74f6f7a219e1e37326df" in text
    # must not leak into core runtime skill inventories
    for folder, expected in present_runtime_skills().items():
        assert "templeton-architecture-review" not in expected
        actual = {path.name for path in (ROOT / folder).iterdir() if path.is_dir()}
        assert "templeton-architecture-review" not in actual


def test_vendored_mattpocock_architecture_sources_are_pinned():
    vendor = ROOT / "third_party" / "mattpocock-skills"
    assert (vendor / "PINNED.md").is_file()
    assert (vendor / "UPSTREAM_FILES.json").is_file()
    assert (vendor / "improve-codebase-architecture" / "SKILL.md").is_file()
    assert (vendor / "codebase-design" / "SKILL.md").is_file()
    assert (vendor / "LICENSE").is_file()
    pin = (vendor / "PINNED.md").read_text()
    assert "8b78b531ab965735c5dc74f6f7a219e1e37326df" in pin
    license_text = (vendor / "LICENSE").read_text()
    assert "Copyright (c) 2026 Matt Pocock" in license_text


def test_optional_productivity_helpers_are_outside_core_inventory_and_gated():
    expected = {
        "templeton-architecture-review",
        "templeton-grill",
        "templeton-handoff",
        "templeton-questionnaire",
        "templeton-wait-what",
        "templeton-writing-for-agents",
    }
    optional_root = ROOT / "optional-skills"
    actual = {path.name for path in optional_root.iterdir() if path.is_dir()}
    assert expected.issubset(actual)
    for name in sorted(expected):
        text = (optional_root / name / "SKILL.md").read_text()
        assert text.startswith("---\n")
        assert f"name: {name}\n" in text
        assert "loop:agent-ready" in text
        assert "Never" in text
        assert "8b78b531ab965735c5dc74f6f7a219e1e37326df" in text
    for folder, core in present_runtime_skills().items():
        assert expected.isdisjoint(core)
        actual_core = {path.name for path in (ROOT / folder).iterdir() if path.is_dir()}
        assert expected.isdisjoint(actual_core)


def test_vendored_mattpocock_productivity_selection_excludes_teach():
    vendor = ROOT / "third_party" / "mattpocock-skills"
    pin = (vendor / "PINNED.md").read_text()
    assert "skills/productivity/handoff" in pin
    assert "skills/productivity/teach" in pin  # listed as not incorporated
    assert "Not incorporated" in pin
    assert (vendor / "productivity" / "handoff" / "SKILL.md").is_file()
    assert (vendor / "productivity" / "grilling" / "SKILL.md").is_file()
    assert (vendor / "productivity" / "writing-for-agents" / "SKILL.md").is_file()
    assert not (vendor / "productivity" / "teach").exists()
    # Templeton grill remains one-at-a-time
    grill = (ROOT / "optional-skills" / "templeton-grill" / "SKILL.md").read_text()
    assert "one decision question at a time" in grill.lower() or "one question at a time" in grill.lower()
