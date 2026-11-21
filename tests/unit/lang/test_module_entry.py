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
        'decoy 1\npipeline { seed 987654\n mask t from csv("secret-path.csv", header: true) to csv("b.csv")'
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
    assert "unexpected quoted text" in err
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


def test_format_prints_the_canonical_layout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    program = tmp_path / "p.decoy"
    program.write_text(
        'decoy 1\npipeline { seed 1  # fixed\n mask t from csv("a.csv", header: true) to csv("b.csv") { x : redact } }\n',
        encoding="utf-8",
    )
    assert main(["--format", str(program)]) == 0
    assert capsys.readouterr().out == (
        "decoy 1\n\npipeline {\n  seed 1  # fixed\n\n"
        '  mask t from csv("a.csv", header: true) to csv("b.csv") {\n    x : redact\n  }\n}\n'
    )
    program.write_text("decoy 1\npipeline { seed }\n", encoding="utf-8")
    assert main(["--format", str(program)]) == 2


def test_to_decoy_converts_a_pipeline_yaml(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pipeline = tmp_path / "pipeline.yaml"
    pipeline.write_text(get_template("pci").body, encoding="utf-8")
    assert main(["--to-decoy", str(pipeline)]) == 0
    assert capsys.readouterr().out == (_TWINS / "pci.decoy").read_text(encoding="utf-8")
    pipeline.write_text("version: 2\n", encoding="utf-8")
    assert main(["--to-decoy", str(pipeline)]) == 2
    assert "error[lang.convert]" in capsys.readouterr().err


def test_a_program_with_unreviewed_rules_is_not_compiled_to_yaml(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    program = tmp_path / "p.decoy"
    program.write_text(
        'decoy 1\npipeline { seed 1\n mask t from csv("a.csv", header: true) to csv("b.csv") {\n'
        "  x : redact ?\n  keep y\n } }\n",
        encoding="utf-8",
    )
    assert main([str(program)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "p.decoy:4:3: error[lang.unreviewed]" in captured.err
    assert "remove the `?`" in captured.err
