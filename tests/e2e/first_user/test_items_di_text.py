"""Distribution-integrity QA text items (row 24e, slice C2): template, explain topics and help.

Each cell reproduces text that read wrong in the DI QA: a stale `mode: generate` line, a key
topic too long to find the one answer, a faker note that hid broken joins, a history line in
`explain modes`, and source line references in command help.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app

runner = CliRunner()

ROOT = Path(__file__).resolve().parents[3]


def _topic(name: str) -> dict:
    result = runner.invoke(app, ["explain", name, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def _help(*args: str) -> str:
    result = runner.invoke(app, [*args, "--help"], terminal_width=200)
    assert result.exit_code == 0, result.output
    return result.output


def test_generate_template_carries_no_mode_generate() -> None:
    result = runner.invoke(app, ["show", "template", "generate"])
    assert result.exit_code == 0, result.output
    assert "mode: generate" not in result.output


def test_no_bundled_example_carries_mode_generate() -> None:
    for path in sorted((ROOT / "examples").glob("*.yaml")):
        assert "mode: generate" not in path.read_text(encoding="utf-8"), path.name


def test_explain_keys_leads_with_the_two_keys_and_stays_short() -> None:
    payload = _topic("keys")
    assert len(payload["summary"]) <= 70, payload["summary"]
    lines = payload["body"].splitlines()
    assert len(lines) <= 30, len(lines)
    assert all(len(line) <= 100 for line in lines)
    head = "\n".join(lines[:3])
    assert "--master-key" in head and "generation" in head.lower()
    assert "--mask-secret" in head and "masking" in head.lower()
    assert "64 hex characters (32 bytes)" in payload["body"]


def test_explain_keys_key_length_matches_master_key_help() -> None:
    run_help = " ".join(_help("run").split())
    assert "64-char hex" in run_help
    assert "32-byte hex" not in _topic("keys")["body"]


def test_explain_transforms_faker_says_equal_values_get_different_fakes() -> None:
    body = " ".join(_topic("transforms")["body"].split())
    assert "equal source values get different fakes unless the column is deterministic" in body


def test_explain_modes_has_no_v1_history_line() -> None:
    body = _topic("modes")["body"]
    assert "V1 had" not in body
    assert "graph" not in body and "convert" not in body


@pytest.mark.parametrize("args", [("report", "fidelity"), ("report", "integrity")])
def test_report_help_has_no_source_reference_or_platform_text(args: tuple[str, ...]) -> None:
    text = _help(*args)
    assert not re.search(r"\b\w+\.py:\d+", text)
    assert not re.search(r"\bBF\d+\b", text)
    assert "the platform's" not in text
