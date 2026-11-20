"""AT-10 (briefs): every brief carries the fields the plan requires, and the finding template
holds the finding record fields (plan 5.6 and 15.2.4)."""

from __future__ import annotations

import re

import pytest
from tests.unit.qa._paths import BRIEFS, REPO

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

CHARTERS = (
    "p1-solo-developer",
    "p2-data-engineer",
    "p3-ci-engineer",
    "p4-compliance-reviewer",
    "p5-careless-user",
)
OTHER_BRIEFS = ("checklist-pass", "doc-walk", "triager")
ALL_BRIEFS = CHARTERS + OTHER_BRIEFS

ALL_SECTIONS = ("Mission", "Time box", "Sandbox rule", "No-values rule", "Submit rule")
CHARTER_SECTIONS = ("Persona", "Corpus items", "Node", "Debrief questions")

FINDING_FIELDS = {
    "schema_version", "id", "layer", "persona", "group",
    "platform", "cli_version", "engine_version", "bundle_digest",
    "corpus_item", "command", "config",
    "expected", "actual", "exit",
    "repro", "proposed_tier", "confusing",
}  # fmt: skip


def _text(name: str) -> str:
    return (BRIEFS / f"{name}.md").read_text(encoding="utf-8")


def _sections(text: str) -> dict[str, str]:
    parts = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
    return {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def test_the_brief_set_is_exactly_the_eight_the_plan_names() -> None:
    names = {p.stem for p in BRIEFS.glob("*.md")}
    assert names == set(ALL_BRIEFS)


@pytest.mark.parametrize("name", ALL_BRIEFS)
def test_every_brief_has_the_shared_sections_filled(name: str) -> None:
    sections = _sections(_text(name))
    for key in ALL_SECTIONS:
        assert sections.get(key), f"{name}: section '{key}' is missing or empty"


@pytest.mark.parametrize("name", CHARTERS)
def test_every_charter_has_the_charter_sections_filled(name: str) -> None:
    sections = _sections(_text(name))
    for key in CHARTER_SECTIONS:
        assert sections.get(key), f"{name}: section '{key}' is missing or empty"


@pytest.mark.parametrize("name", CHARTERS)
def test_a_charter_time_box_is_two_hours_and_names_the_node(name: str) -> None:
    sections = _sections(_text(name))
    assert "2 hours" in sections["Time box"]
    assert sections["Node"].strip()


@pytest.mark.parametrize("name", ALL_BRIEFS)
def test_the_rule_sections_name_their_mechanism(name: str) -> None:
    sections = _sections(_text(name))
    assert "docs" in sections["Sandbox rule"].lower()
    assert "never" in sections["No-values rule"].lower()
    submit = sections["Submit rule"]
    assert "findings.py" in submit
    if name != "triager":
        assert "findings.py write" in submit


@pytest.mark.parametrize("name", ALL_BRIEFS)
def test_briefs_have_no_em_dash_and_no_marker_text(name: str) -> None:
    text = _text(name)
    assert "—" not in text
    assert "qamark" not in text.lower()


def test_the_finding_template_holds_every_record_field_and_version_one() -> None:
    path = REPO / "docs" / "qa" / "finding-template.toml"
    record = tomllib.loads(path.read_text(encoding="utf-8"))
    assert set(record) == FINDING_FIELDS
    assert record["schema_version"] == 1


def test_the_finding_template_holds_no_marker_text_or_secret_shape() -> None:
    text = (REPO / "docs" / "qa" / "finding-template.toml").read_text(encoding="utf-8")
    assert "qamark" not in text.lower()
    assert "—" not in text
