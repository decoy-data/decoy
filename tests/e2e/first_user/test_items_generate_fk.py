"""The bundled generate example joins a parent and a child table by a `reference` column."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app

runner = CliRunner()

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "generate_example.yaml"


def _reference_columns(cfg: dict) -> list[tuple[str, dict]]:
    return [
        (table["name"], col)
        for table in cfg["tables"]
        for col in table.get("generate_columns", [])
        if col.get("type") == "reference"
    ]


def test_example_has_a_child_table_with_a_reference_column() -> None:
    cfg = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    refs = _reference_columns(cfg)
    assert refs, "no `type: reference` column in examples/generate_example.yaml"
    table, col = refs[0]
    assert col["reference_table"] != table


def test_example_runs_and_writes_no_orphan_key(tmp_path: Path) -> None:
    cfg = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    (_, ref), *_ = _reference_columns(cfg)
    cfg_path = tmp_path / "pipeline.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    result = runner.invoke(app, ["run", str(cfg_path), "--quiet"])
    assert result.exit_code == 0, result.output
    outputs = {
        name: pd.read_csv(next(tmp_path.rglob(Path(t["path"]).name)))
        for name, t in cfg["targets"].items()
    }
    child_name, child_col = next((n, c["name"]) for n, c in _reference_columns(cfg) if c is ref)
    parent = outputs[ref["reference_table"]][ref["reference_column"]]
    child = outputs[child_name][child_col]
    assert len(child) > 0
    assert set(child) <= set(parent)
