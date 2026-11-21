"""AT-C1l and AT-C1w value cells: a table the pre-pass reads whole equals its resident twin.

When the engine reads a candidate whole (a vault run, a declared-casting table) it uses its own
reader, not the CLI's `read_source`. For each CSV dialect and fixed-width layout the plan lists,
the table the pre-pass returns must equal `read_source` on the same resolved descriptor in column
names, Arrow types and values, and the final target bytes must equal the base run's.

Documented exception: a CSV column whose every field is empty is `null` resident and `string`
lazy. The values are all null in both, and the output bytes do not differ.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
import yaml

from decoy.cli._sources import read_source
from tests.csv_sources import csv_source, file_source
from tests.e2e.run_stream._support import install_probe, run_both, write_config
from tests.keyed_secret import TEST_MASK_SECRET_REF, secret_env

_ROWS = 40

_DECLARED = {
    "logical_type": "integer",
    "parse_format": {"id": "integer/ascii/v1", "signed": True, "bit_width": 64},
    "error_policy": "fail",
    "output_format": {"id": "integer/zero-pad/v1", "width": 3, "width_unit": "code_points"},
}


@pytest.fixture(autouse=True)
def _secret(monkeypatch: pytest.MonkeyPatch) -> None:
    for var, value in secret_env().items():
        monkeypatch.setenv(var, value)


def _csv(path: Path, header: list[str] | None, rows: list[list[str]], delimiter: str = ",") -> None:
    def cell(value: str) -> str:
        quote = delimiter in value or '"' in value or "\n" in value
        return '"' + value.replace('"', '""') + '"' if quote else value

    lines = [] if header is None else [delimiter.join(header)]
    lines += [delimiter.join(cell(v) for v in row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def _base_rows(
    *, newline: bool = False, empty: bool = False, note: bool = False
) -> list[list[str]]:
    rows = []
    for i in range(_ROWS):
        email = f"user{i}@example.invalid"
        if newline and i == 3:
            email = "first line\nsecond line"
        if empty and i == 5:
            email = ""
        rows.append([str(i), email, str(10 + i)] + ([""] if note else []))
    return rows


def _csv_case(tmp: Path, kind: str) -> tuple[dict[str, Any], list[str]]:
    path = tmp / "data" / f"{kind}.csv"
    path.parent.mkdir(exist_ok=True)
    cols = ["id", "email", "n"]
    if kind == "semi":
        _csv(path, cols, _base_rows(), ";")
        return csv_source(path, delimiter=";"), cols
    if kind == "headerless":
        _csv(path, None, _base_rows())
        return csv_source(path, has_header=False, column_names=cols), cols
    if kind == "newline_and_empty":
        _csv(path, cols, _base_rows(newline=True, empty=True))
        return csv_source(path), cols
    _csv(path, [*cols, "note"], _base_rows(note=True))
    return csv_source(path), [*cols, "note"]


_FW_TYPED = {
    "columns": [
        {"name": "id", "start": 0, "width": 6},
        {"name": "name", "start": 6, "width": 10},
        {"name": "age", "start": 16, "width": 3, "type": "int", "align": "right"},
        {"name": "score", "start": 19, "width": 7, "type": "float", "align": "right"},
    ]
}
_FW_TEXT = {
    "exact_record_width": True,
    "columns": [
        {"name": "id", "start": 0, "width": 6},
        {"name": "name", "start": 6, "width": 10},
        {"name": "n", "start": 16, "width": 3},
    ],
}


def _fw_case(tmp: Path, *, typed: bool) -> tuple[dict[str, Any], list[str]]:
    path = tmp / "data" / "f.dat"
    path.parent.mkdir(exist_ok=True)
    lines = []
    for i in range(_ROWS):
        if typed:
            score = "nan" if i == 4 else f"{i * 1.5:.2f}"
            lines.append(f"{i:<6}{f'name{i}':<10}{i % 90:>3}{score:>7}")
        else:
            lines.append(f"{i:<6}{f'name{i}':<10}{10 + i:03d}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    layout = _FW_TYPED if typed else _FW_TEXT
    return file_source(path, "fixed_width", layout=layout), [c["name"] for c in layout["columns"]]


def _builder(
    tmp: Path, source: dict[str, Any], columns: list[str], mode: str, text_col: str
) -> Any:
    cols: list[dict[str, Any]] = []
    for name in columns:
        if name == text_col and mode == "vault":
            cols.append({"name": name, "strategy": "hash", "namespace": "ns", "vault": True})
        elif name == "n" and mode == "declared":
            cols.append(
                {
                    "name": "n",
                    "strategy": "bucketize",
                    "provider_config": {"width": 10, "format": "lower"},
                    **_DECLARED,
                }
            )
        else:
            cols.append({"name": name, "strategy": "passthrough"})

    def build(out: Path) -> tuple[Path, list[Path]]:
        cfg = {
            "version": 2,
            "global_settings": {"seed": 3, "mask_secret_ref": TEST_MASK_SECRET_REF},
            "sources": {"t": source},
            "tables": [{"name": "t", "columns": cols}],
            "targets": {"t": {"type": "file", "format": "csv", "path": str(out / "t.csv")}},
        }
        return write_config(out / "p.yaml", cfg), [out / "t.csv"]

    return build


def _resolved(config: Path) -> dict[str, Any]:
    from decoy.cli._sources import resolved_source_config

    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    return resolved_source_config(cfg, config.parent)["sources"]["t"]


def _assert_twin(
    lazy_table: pa.Table, twin: pa.Table, *, null_columns: tuple[str, ...] = ()
) -> None:
    assert lazy_table.column_names == twin.column_names
    for name in twin.column_names:
        if name in null_columns:
            # The documented exception: resident `null`, lazy `string`, all values null.
            assert twin.schema.field(name).type == pa.null()
            assert lazy_table.schema.field(name).type == pa.string()
            assert lazy_table.column(name).null_count == lazy_table.num_rows
        else:
            assert lazy_table.schema.field(name).type == twin.schema.field(name).type, name
    assert lazy_table.to_pylist() == twin.to_pylist()


def _cell(
    tmp: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: dict[str, Any],
    columns: list[str],
    mode: str,
    text_col: str,
    null_columns: tuple[str, ...] = (),
) -> None:
    probe = install_probe(monkeypatch)
    build = _builder(tmp, source, columns, mode, text_col)
    args = ("--vault", "{out}/vault.db") if mode == "vault" else ()
    lazy, base, seen = run_both(monkeypatch, tmp, build, args=args, probe=probe)
    assert lazy.exit_code == 0, lazy.output
    assert lazy.exit_code == base.exit_code
    assert lazy.files == base.files
    assert seen is not None
    assert len(seen.prepass_tables) == 1
    config = tmp / "lazy" / "p.yaml"
    twin = read_source("t", _resolved(config), config.parent)
    _assert_twin(seen.prepass_tables[0], twin, null_columns=null_columns)


@pytest.mark.parametrize("mode", ["vault", "declared"])
@pytest.mark.parametrize("kind", ["semi", "headerless", "newline_and_empty", "all_empty"])
def test_csv_prepass_table_equals_its_resident_twin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, mode: str
) -> None:
    source, columns = _csv_case(tmp_path, kind)
    null_columns = ("note",) if kind == "all_empty" else ()
    _cell(tmp_path, monkeypatch, source, columns, mode, "email", null_columns)


def test_fixed_width_typed_prepass_table_equals_its_resident_twin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, columns = _fw_case(tmp_path, typed=True)
    _cell(tmp_path, monkeypatch, source, columns, "vault", "name")


def test_fixed_width_text_prepass_table_equals_its_resident_twin_under_declared_casting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, columns = _fw_case(tmp_path, typed=False)
    _cell(tmp_path, monkeypatch, source, columns, "declared", "name")
