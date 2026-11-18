"""A printed filesystem path is never folded, whatever the terminal width."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_OK
from decoy.ui.output import OutputMode, _keep_lines_whole, setup_output

runner = CliRunner()
WIDTH = "40"


@pytest.fixture
def long_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    deep = tmp_path / ("d" * 30) / ("e" * 30) / "proj"
    deep.mkdir(parents=True)
    (deep / ".git").mkdir()
    monkeypatch.chdir(deep)
    monkeypatch.delenv("DECOY_LIBRARY", raising=False)
    monkeypatch.setenv("COLUMNS", WIDTH)
    return deep / ".decoy"


def test_library_path_prints_the_root_on_one_line(long_root: Path) -> None:
    result = runner.invoke(app, ["library", "path"])
    assert result.exit_code == EXIT_OK, result.output
    line = f"root: {long_root.resolve()}"
    assert len(line) > int(WIDTH)
    assert line in result.output.splitlines()


def test_a_text_line_is_never_folded_on_either_console(
    long_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = setup_output(False, False, False)
    assert state.mode is OutputMode.default
    state.console.print("OK", str(long_root.resolve()))
    state.err_console.print("OK", str(long_root.resolve()))
    captured = capsys.readouterr()
    for text in (captured.out, captured.err):
        assert f"OK {long_root.resolve()}" in text.splitlines()


def _wrapped(*, terminal: bool, width: int = 40) -> tuple[Console, io.StringIO]:
    out = io.StringIO()
    return _keep_lines_whole(Console(file=out, force_terminal=terminal, width=width)), out


# Longer than 80: the suite sets TERM=dumb, which makes Rich ignore a narrower `width=`.
PROSE = " ".join(["alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima"] * 2)


def test_on_a_terminal_long_prose_word_wraps_at_spaces() -> None:
    console, out = _wrapped(terminal=True)
    console.print(PROSE)
    lines = out.getvalue().splitlines()
    assert len(lines) > 1
    assert " ".join(lines).split() == PROSE.split()  # no word split mid-way


def test_off_a_terminal_the_same_prose_stays_one_line() -> None:
    console, out = _wrapped(terminal=False)
    console.print(PROSE)
    assert out.getvalue().splitlines() == [PROSE]


def test_off_a_terminal_a_table_and_a_panel_keep_their_layout() -> None:
    console, out = _wrapped(terminal=False)
    table = Table("Field", "Value")
    table.add_row("name", "x" * 10)
    console.print(table)
    console.print(Panel("body text " * 12, width=30))
    lines = out.getvalue().splitlines()
    assert all(len(line) <= 80 for line in lines)  # not widened by soft wrap
    assert sum("body" in line for line in lines) > 1  # panel text wrapped inside its box
    assert any("x" * 10 in line for line in lines)  # cell kept whole
