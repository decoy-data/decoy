"""AT-11 and the AT-13 sentries: one sweep, and the publication and Slack paths stay in findings.py.

The scans are syntax-tree walks over string constants and imports, so a moved path or an aliased
import is still seen. Planted snippets prove each scan finds what it claims to.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
QA = ROOT / "scripts" / "qa"
JOURNEY = ROOT / "tests/e2e/first_user/journey/test_cli_journey.py"
CHECKLIST = ROOT / "docs/qa/cli-v1-checklist.md"


def _modules() -> list[Path]:
    return sorted(p for p in QA.rglob("*.py") if "__pycache__" not in p.parts)


def records_or_slack(source: str) -> list[str]:
    """Where code names `docs/records` or Slack, other than in a docstring."""
    tree = ast.parse(source)
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Module | ast.FunctionDef | ast.ClassDef)
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    found = []
    for node in ast.walk(tree):
        text = ""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = "" if id(node) in docstrings else node.value
        elif isinstance(node, ast.Name | ast.Attribute | ast.alias | ast.arg):
            text = getattr(node, "id", getattr(node, "attr", getattr(node, "name", "")))
        low = text.lower()
        if "slack" in low or "docs/records" in low or low == "records":
            found.append(f"{getattr(node, 'lineno', 0)}")
    return found


@pytest.mark.parametrize(
    "snippet",
    [
        "p = 'docs/records/x.md'",
        "p = root / 'docs' / 'records'",
        "run(['slack-notify.sh'])",
        "import slack_sdk",
        "from x import post_to_slack",
        "SLACK = 1",
    ],
)
def test_the_scan_sees_each_spelling(snippet: str) -> None:
    assert records_or_slack(snippet), snippet


def test_the_scan_ignores_docstrings_and_other_text() -> None:
    assert (
        records_or_slack('"""Notes on Slack."""\ndef f():\n    """docs/records"""\nx = "ok"') == []
    )


def test_only_findings_publish_writes_records_or_calls_slack() -> None:
    offenders = {
        p.relative_to(ROOT).as_posix(): lines
        for p in _modules()
        if p != QA / "findings.py" and (lines := records_or_slack(p.read_text(encoding="utf-8")))
    }
    assert offenders == {}, "route this through scripts/qa/findings.py publish"
    assert records_or_slack((QA / "findings.py").read_text(encoding="utf-8"))  # the scan sees it


def test_the_journey_calls_the_one_sweep_and_has_no_second_implementation() -> None:
    source = JOURNEY.read_text(encoding="utf-8")
    assert "from scripts.qa import sweep as qa_sweep" in source
    assert "qa_sweep.sweep(" in source
    tree = ast.parse(source)
    sweeper = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_sweep"
    )
    loops = [
        n
        for n in ast.walk(sweeper)
        if isinstance(n, ast.Compare) and any(isinstance(o, ast.In) for o in n.ops)
    ]
    assert loops == [], "the journey must not match needles itself"


def test_the_checklist_sweep_step_calls_the_one_sweep() -> None:
    text = CHECKLIST.read_text(encoding="utf-8")
    assert "python -m scripts.qa.sweep --needles data/markers.txt" in text
    assert "grep -rFf" not in text
