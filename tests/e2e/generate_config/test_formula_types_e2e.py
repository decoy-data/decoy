"""A generate `formula` over a sequence runs as numbers, and its refusals reach the right exit.

GEN-FORMULA-SEQ C1 (roadmap row 24y). The engine half (0.24.0 and later) types the formula's
input and raises `generate_formula_evaluation_failed` instead of writing nulls; these tests pin
what the CLI does with that.

AT-C1-1: `round(a / 3)` over a sequence gives numbers, not nulls.
AT-C1-2: a formula that raises exits 1, writes no output and quotes no cell value.
AT-C1-3: a number used as text is refused by `validate` and `run` with exit 1.
AT-C1-4: `decoy explain exit-codes` names the run failure under exit 1.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner, Result

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_USAGE

runner = CliRunner()
_WIDE = {"COLUMNS": "10000"}
_EVAL_FAILED = "generate_formula_evaluation_failed"
_TEXT_USE = "generate_formula_number_used_as_text"
_SENTINEL = "SENTINEL-X1"
_SEQ = {"name": "a", "type": "sequence", "start": 1}


def _config(folder: Path, columns: list[dict[str, Any]], rows: int = 5) -> Path:
    cfg = {
        "version": 2,
        "global_settings": {"seed": 42},
        "tables": [{"name": "t", "row_count": rows, "generate_columns": columns}],
        "targets": {"t": {"type": "file", "format": "csv", "path": str(folder / "out" / "t.csv")}},
    }
    path = folder / "gen.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return path


def _formula(expr: str, *references: str) -> dict[str, Any]:
    return {"name": "f", "type": "formula", "formula": expr, "references": list(references)}


def _stderr(result: Result) -> str:
    try:
        return result.stderr
    except ValueError:
        return ""


def _no_output(folder: Path) -> None:
    assert not (folder / "out" / "t.csv").exists()
    assert not list(folder.rglob("*.csv"))


def test_at_c1_1_a_formula_over_a_sequence_computes_numbers(tmp_path: Path) -> None:
    cfg = _config(tmp_path, [_SEQ, _formula("round(a / 3)", "a")])
    result = runner.invoke(app, ["run", str(cfg)], env=_WIDE)
    assert result.exit_code == 0, result.output
    with (tmp_path / "out" / "t.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["f"] for r in rows] == ["0", "1", "1", "1", "2"]


@pytest.mark.parametrize("json_flag", [True, False], ids=["json", "human"])
def test_at_c1_2_a_failing_formula_exits_1_and_writes_nothing(
    tmp_path: Path, json_flag: bool
) -> None:
    cfg = _config(tmp_path, [_SEQ, _formula("1 / (a - 3)", "a")])
    args = ["run", str(cfg)] + (["--json"] if json_flag else [])
    result = runner.invoke(app, args, env=_WIDE)
    assert result.exit_code == EXIT_USAGE, result.output
    _no_output(tmp_path)
    if json_flag:
        payload = json.loads(result.stdout)
        assert _EVAL_FAILED in payload["error"], payload
        if "reason" in payload:
            assert payload["reason"]["code"] == _EVAL_FAILED, payload
    else:
        assert _EVAL_FAILED in " ".join(_stderr(result).split()), result.output


@pytest.mark.parametrize("json_flag", [True, False], ids=["json", "human"])
def test_at_c1_2_a_failing_formula_quotes_no_cell_value(tmp_path: Path, json_flag: bool) -> None:
    code = {"name": "code", "type": "categorical", "categories": [_SENTINEL]}
    cfg = _config(tmp_path, [code, _formula("int(code)", "code")])
    args = ["run", str(cfg)] + (["--json"] if json_flag else [])
    result = runner.invoke(app, args, env=_WIDE)
    assert result.exit_code == EXIT_USAGE, result.output
    _no_output(tmp_path)
    assert _EVAL_FAILED in (result.stdout if json_flag else _stderr(result)).replace("\n", " ")
    for stream in (result.output, result.stdout, _stderr(result)):
        assert _SENTINEL not in stream


def test_at_c1_3_validate_refuses_a_number_used_as_text(tmp_path: Path) -> None:
    cfg = _config(tmp_path, [_SEQ, _formula("'ORD-' + a", "a")])
    result = runner.invoke(app, ["validate", str(cfg), "--json"], env=_WIDE)
    assert result.exit_code == EXIT_USAGE, result.output
    codes = [m["code"] for m in json.loads(result.stdout)["messages"]]
    assert any(_TEXT_USE in c for c in codes), codes


@pytest.mark.parametrize("json_flag", [True, False], ids=["json", "human"])
def test_at_c1_3_run_refuses_a_number_used_as_text(tmp_path: Path, json_flag: bool) -> None:
    cfg = _config(tmp_path, [_SEQ, _formula("'ORD-' + a", "a")])
    args = ["run", str(cfg)] + (["--json"] if json_flag else [])
    result = runner.invoke(app, args, env=_WIDE)
    assert result.exit_code == EXIT_USAGE, result.output
    _no_output(tmp_path)
    if json_flag:
        assert _TEXT_USE in " ".join(result.stdout.split()), result.stdout
    else:
        # The human gate line carries the engine's text, not the code (`validate` lists it).
        assert "uses a number reference as text" in " ".join(result.output.split())


def test_at_c1_4_explain_exit_codes_names_the_formula_failure() -> None:
    result = runner.invoke(app, ["explain", "exit-codes"], env=_WIDE)
    assert result.exit_code == 0, result.output
    body = " ".join(result.stdout.replace("│", " ").split())
    start = body.index("1 Usage error")
    end = body.index("2 Warnings")
    assert _EVAL_FAILED in body[start:end]
