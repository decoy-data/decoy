"""AT-X4: the README, `decoy explain exit-codes`, `docs/ci-contracts.md` and the `run --all` help
agree with the exit-code constants.

The code side is the public `EXIT_` constants, `_EXIT_INTERRUPTED`, `_EXIT_CRASH` and
`PRECEDENCE`. The doc side is parsed, so a doc that drops a code, keeps the old "seven", lacks
the shared precedence line or loses the crash wording fails here. Each parse asserts a minimum
count first, so a regex that matches nothing cannot pass.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli import exit_codes
from decoy.cli.run import run as run_command

ROOT = Path(__file__).resolve().parents[3]
README = ROOT / "README.md"
CI_CONTRACTS = ROOT / "docs" / "ci-contracts.md"
MIN_CODES = 8

runner = CliRunner()


def _public_codes() -> set[int]:
    named = {getattr(exit_codes, n) for n in exit_codes.__all__ if n.startswith("EXIT_")}
    return named | {exit_codes._EXIT_INTERRUPTED}


def _precedence_line() -> str:
    return " > ".join(str(code) for code in exit_codes.PRECEDENCE)


def _flat(text: str) -> str:
    return " ".join(text.split())


def _readme_section(text: str) -> str:
    """The README from `## Exit codes` to the next `## ` heading, so no other table counts."""
    found = re.search(r"^## Exit codes\n(.*?)(?=^## |\Z)", text, re.DOTALL | re.MULTILINE)
    assert found is not None, "README has no `## Exit codes` section"
    return found.group(1)


def _readme_rows(text: str) -> dict[int, str]:
    found = re.finditer(r"^\|\s*(\d+)\s*\|.*$", _readme_section(text), re.MULTILINE)
    rows = {int(m.group(1)): m.group(0) for m in found}
    assert len(rows) >= MIN_CODES, sorted(rows)
    return rows


def _explain_text() -> str:
    result = runner.invoke(app, ["explain", "exit-codes"])
    assert result.exit_code == 0, result.output
    return result.output


def _explain_entries(text: str) -> dict[int, str]:
    """Each `  N  text` entry with its continuation lines, keyed by N."""
    entries: dict[int, str] = {}
    current: int | None = None
    for line in text.splitlines():
        row = re.match(r"^  (\d+)\s+\S", line)
        if row:
            current = int(row.group(1))
            entries[current] = line
        elif current is not None and line.startswith("      "):
            entries[current] += " " + line.strip()
        else:
            current = None
    assert len(entries) >= MIN_CODES, sorted(entries)
    return entries


def _all_help() -> str:
    return inspect.signature(run_command).parameters["all_"].default.help


def test_readme_and_explain_list_every_exit_code() -> None:
    expected = _public_codes()
    assert set(_readme_rows(README.read_text(encoding="utf-8"))) == expected
    assert set(_explain_entries(_explain_text())) == expected


def test_a_numeric_table_outside_the_exit_codes_section_is_ignored() -> None:
    text = README.read_text(encoding="utf-8")
    real = set(_readme_rows(text))
    decoy_table = "\n## Elsewhere\n\n| 42 | `X` | planted |\n| 99 | `Y` | planted |\n"
    after = text + decoy_table
    before = text.replace("## Exit codes", decoy_table + "\n## Exit codes", 1)
    assert set(_readme_rows(after)) == real
    assert set(_readme_rows(before)) == real


def test_precedence_line_matches_the_code() -> None:
    line = _precedence_line()
    assert len(exit_codes.PRECEDENCE) == 7
    assert line in _flat(_readme_section(README.read_text(encoding="utf-8")))
    assert line in _flat(_explain_text())
    assert line in _flat(CI_CONTRACTS.read_text(encoding="utf-8"))
    assert line in _flat(_all_help())


def test_crash_code_names_the_internal_error() -> None:
    crash = exit_codes._EXIT_CRASH
    assert crash == exit_codes.EXIT_USAGE
    readme_row = _readme_rows(README.read_text(encoding="utf-8"))[crash]
    explain_entry = _explain_entries(_explain_text())[crash]
    assert "internal error" in readme_row
    assert "internal error" in _flat(explain_entry)
    assert "seven" not in _readme_section(README.read_text(encoding="utf-8"))
    assert "seven" not in _explain_text()
