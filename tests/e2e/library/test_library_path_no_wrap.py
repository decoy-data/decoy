"""A printed filesystem path is never folded, whatever the terminal width."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_OK
from decoy.ui.output import OutputMode, setup_output

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
