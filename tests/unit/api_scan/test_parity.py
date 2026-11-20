"""`decoy.scan()` returns the document `decoy scan --output` writes (freeze item 3 C2).

Each cell runs the CLI and the API on the same file with the same options and compares the
two documents byte for byte through `core_bytes`, once `scanned_at` (the one wall-clock member)
is set to the same value.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from typer.testing import CliRunner

import decoy
from decoy.__main__ import app
from decoy.cli.scanning import DEFAULT_SCAN_ROWS, core_bytes

runner = CliRunner()
_EPOCH = "1970-01-01T00:00:00+00:00"
_LAYOUT = [
    {"name": "a", "start": 0, "width": 3},
    {"name": "b", "start": 3, "width": 2},
    {"name": "c", "start": 5, "width": 1},
]
_LAYOUT_YAML = "columns:\n" + "".join(
    f"  - {{name: {c['name']}, start: {c['start']}, width: {c['width']}}}\n" for c in _LAYOUT
)


def cli_doc(argv: list[str], tmp_path: Path) -> dict[str, Any]:
    out = tmp_path / "cli-scan.json"
    result = runner.invoke(app, ["scan", *argv, "--output", str(out)])
    assert result.exit_code == 0, result.output
    return json.loads(out.read_text(encoding="utf-8"))


def same_bytes(cli: dict[str, Any], api: dict[str, Any]) -> None:
    cli, api = {**cli, "scanned_at": _EPOCH}, {**api, "scanned_at": _EPOCH}
    assert core_bytes(api) == core_bytes(cli)


def write_csv(path: Path, rows: int = 40, header: str = "id,mail") -> Path:
    body = "".join(f"{i},u{i}@example.com\n" for i in range(rows))
    path.write_text(f"{header}\n{body}", encoding="utf-8")
    return path


def write_fixed(path: Path) -> tuple[Path, Path]:
    path.write_text("".join(f"{i:03d}ab{i % 7}\n" for i in range(30)), encoding="utf-8")
    layout = path.with_suffix(".yaml")
    layout.write_text(_LAYOUT_YAML, encoding="utf-8")
    return path, layout


def _cells(tmp_path: Path) -> dict[str, tuple[list[str], Path, dict[str, Any]]]:
    csv = write_csv(tmp_path / "c.csv")
    big = write_csv(tmp_path / "big.csv", rows=10_050)
    tsv = tmp_path / "t.tsv"
    tsv.write_text("id\tmail\n" + "".join(f"{i}\tu{i}@example.com\n" for i in range(20)))
    headerless = tmp_path / "h.csv"
    headerless.write_text("".join(f"{i},u{i}@example.com\n" for i in range(20)))
    suspect = tmp_path / "s.csv"
    suspect.write_text(
        "alice@example.com,555-12-3456\n"
        + "".join(f"user{i}@example.com,555-12-{1000 + i}\n" for i in range(30))
    )
    repeated = tmp_path / "r.csv"
    repeated.write_text("a,a,b\n1,2,3\n4,5,6\n")
    pqf = tmp_path / "p.parquet"
    pd.DataFrame({"pid": range(12), "note": ["x"] * 12}).to_parquet(pqf)
    fw, layout = write_fixed(tmp_path / "f.fwf")
    fw2, _ = write_fixed(tmp_path / "g.fwf")
    head = ["--has-header"]
    return {
        "csv default rows": ([*head], csv, {"has_header": True}),
        "csv rows 0": ([*head, "--rows", "0"], csv, {"has_header": True, "rows": 0}),
        "csv rows 5 random": (
            [*head, "--rows", "5", "--strategy", "random"],
            csv,
            {"has_header": True, "rows": 5, "strategy": "random"},
        ),
        "csv rows 5 full": (
            [*head, "--rows", "5", "--strategy", "full"],
            csv,
            {"has_header": True, "rows": 5, "strategy": "full"},
        ),
        "csv 10050 rows default": ([*head], big, {"has_header": True}),
        "tsv": ([*head], tsv, {"has_header": True}),
        "headerless": (
            ["--no-header", "--column-names", "id,mail"],
            headerless,
            {"has_header": False, "column_names": ["id", "mail"]},
        ),
        "header suspect": ([*head], suspect, {"has_header": True}),
        "repeated csv header": ([*head], repeated, {"has_header": True}),
        "parquet": ([], pqf, {}),
        "fixed width layout file": (["--layout", str(layout)], fw, {"layout": layout}),
        "fixed width layout list": (["--layout", str(layout)], fw2, {"layout": _LAYOUT}),
    }


_NAMES = [
    "csv default rows",
    "csv rows 0",
    "csv rows 5 random",
    "csv rows 5 full",
    "csv 10050 rows default",
    "tsv",
    "headerless",
    "header suspect",
    "repeated csv header",
    "parquet",
    "fixed width layout file",
    "fixed width layout list",
]


@pytest.mark.parametrize("cell", _NAMES)
def test_at1_api_document_matches_the_cli_output_file(tmp_path: Path, cell: str) -> None:
    flags, path, kwargs = _cells(tmp_path)[cell]
    cli = cli_doc([str(path), *flags], tmp_path)
    api = decoy.scan(path, **kwargs)
    assert isinstance(api, dict), "decoy.scan() must return the scan-set/v1 dict"
    same_bytes(cli, api)


def test_at1_cells_cover_the_drift_rows(tmp_path: Path) -> None:
    cells = _cells(tmp_path)
    assert list(cells) == _NAMES
    suspect = decoy.scan(cells["header suspect"][1], has_header=True)
    assert [f["name"] for f in suspect["tables"][0]["fields"]] == ["c0", "c1"]
    repeated = decoy.scan(cells["repeated csv header"][1], has_header=True)
    assert [f["name"] for f in repeated["tables"][0]["fields"]] == ["a", "a.1", "b"]
    big = decoy.scan(cells["csv 10050 rows default"][1], has_header=True)["tables"][0]
    assert big["basis"] != "whole"
    assert big["row_count"] > big["scanned_rows"]


def test_at2_dataframe_matches_the_same_data_as_a_parquet_file(tmp_path: Path) -> None:
    df = pd.DataFrame({"pid": range(12), "mail": [f"u{i}@example.com" for i in range(12)]})
    path = tmp_path / "t.parquet"
    df.to_parquet(path)
    cli = cli_doc([str(path)], tmp_path)
    api = decoy.scan(df, source_label="t")
    assert api["tables"][0]["descriptor"]["path"] == "<dataframe>"
    cli["tables"][0]["descriptor"]["path"] = "<dataframe>"
    same_bytes(cli, api)


def test_at3_the_default_is_the_cli_default(tmp_path: Path) -> None:
    assert inspect.signature(decoy.scan).parameters["rows"].default is DEFAULT_SCAN_ROWS
    big = write_csv(tmp_path / "big.csv", rows=10_050)
    cli = cli_doc([str(big), "--has-header"], tmp_path)
    api = decoy.scan(big, has_header=True)
    assert api["tables"][0]["scanned_rows"] == DEFAULT_SCAN_ROWS
    same_bytes(cli, api)


def _keys(node: Any) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {k for v in node.values() for k in _keys(v)}
    if isinstance(node, list):
        return {k for v in node for k in _keys(v)}
    return set()


def test_at5_the_result_is_the_value_free_core(tmp_path: Path) -> None:
    from decoy_engine.profiling import ScanSetCoreRead

    df = pd.DataFrame({"tier": ["gold"] * 30 + ["silver"] * 29 + ["ZQRARELABEL"]})
    doc = decoy.scan(df, source_label="tiers")
    ScanSetCoreRead.model_validate(doc)
    assert not _keys(doc) & {"detail", "top_values", "mode", "min", "max"}
    assert "ZQRARELABEL" not in json.dumps(doc)
