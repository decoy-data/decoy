"""`python -m decoy.lang`: the experimental compile step."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from decoy.lang.__main__ import main
from decoy.templates import get_template

_TWINS = Path(__file__).parent / "twins"


def test_prints_the_pipeline_yaml(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(_TWINS / "pci.decoy")]) == 0
    captured = capsys.readouterr()
    assert yaml.safe_load(captured.out) == yaml.safe_load(get_template("pci").body)
    assert captured.err == ""


def test_a_program_that_does_not_compile_exits_2_with_positions_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    program = tmp_path / "bad.decoy"
    program.write_text(
        'decoy 1\npipeline { seed 987654\n mask t from csv("secret-path.csv") to csv("b.csv")'
        " { ssn : redcat } }\n",
        encoding="utf-8",
    )
    assert main([str(program)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    first, hint = captured.err.splitlines()
    assert first.startswith("bad.decoy:3:")
    assert first.endswith(
        "error[lang.unknown_strategy]: `redcat` is not a strategy or a `let` name"
    )
    assert hint == "  hint: did you mean `redact`?"
    assert "secret-path" not in captured.err


def test_errors_never_show_the_source_line_or_a_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    program = tmp_path / "bad.decoy"
    program.write_text('decoy 1\npipeline { seed 987654 "secret-text" }\n', encoding="utf-8")
    assert main([str(program)]) == 2
    err = capsys.readouterr().err
    assert "unexpected a quoted string" in err
    assert "987654" not in err
    assert "secret-text" not in err


def test_an_unreadable_file_exits_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path / "missing.decoy")]) == 3
    assert "FileNotFoundError" in capsys.readouterr().err
    binary = tmp_path / "binary.decoy"
    binary.write_bytes(b"\xff\xfe\x00")
    assert main([str(binary)]) == 3


@pytest.mark.parametrize("argv", [[], ["a.decoy", "b.decoy"], ["--help"]])
def test_wrong_arguments_print_usage(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv) == 2
    assert capsys.readouterr().err.startswith("usage: python -m decoy.lang")
