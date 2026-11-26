"""`decoy.scan()` input rules, error text and staging (freeze item 3 C2)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml
from tests.unit.api_scan.test_parity import write_csv, write_fixed

import decoy
from decoy.cli.scanning import resolve_sources

MARKER = "SECRETMARKER"


@pytest.fixture
def engine_must_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import decoy_engine

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("the engine was called")

    monkeypatch.setattr(decoy_engine, "scan_sources", boom)


def _text(exc: BaseException) -> str:
    return str(exc) + (getattr(exc, "hint_text", None) or "")


def test_at4_a_csv_without_has_header_is_refused_in_api_spelling(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "x.csv")
    with pytest.raises(ValueError) as info:
        decoy.scan(path)
    # The message names the file; a run label such as `PIN--0.28.4` in its temp path holds `--`.
    text = _text(info.value).replace(str(path), "")
    assert "has_header=True" in text and "has_header=False" in text
    assert "--" not in text


def test_at4_a_headerless_csv_needs_column_names(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "x.csv")
    with pytest.raises(ValueError) as info:
        decoy.scan(path, has_header=False)
    text = _text(info.value)
    assert "column_names=" in text and "--" not in text


def test_at4_a_repeated_column_name_is_refused_in_api_spelling(tmp_path: Path) -> None:
    path = write_csv(tmp_path / "x.csv")
    with pytest.raises(ValueError) as info:
        decoy.scan(path, has_header=False, column_names=["a", "a"])
    text = _text(info.value)
    assert "column_names must not repeat a name" in text and "--" not in text


def test_at4_fixed_width_without_a_layout_names_the_keyword(tmp_path: Path) -> None:
    path, _ = write_fixed(tmp_path / "x.dat")
    with pytest.raises(ValueError) as info:
        decoy.scan(path, format="fixed-width")
    text = _text(info.value)
    assert "layout=" in text and "--" not in text


def _engine_error(path: Path) -> BaseException:
    import decoy_engine

    descriptors, _ = resolve_sources(
        [path], fmt=None, layout=None, has_header=None, column_names=None
    )
    with pytest.raises(Exception) as info:
        decoy_engine.scan_sources(descriptors, sample_rows=10_000, strategy="head")
    return info.value


def test_at7_a_parquet_with_a_repeated_name_is_refused_as_the_engine_refuses_it(
    tmp_path: Path,
) -> None:
    path = tmp_path / "dup.parquet"
    table = pa.Table.from_arrays([pa.array([MARKER]), pa.array([MARKER])], names=["a", "a"])
    pq.write_table(table, path)
    want = _engine_error(path)
    with pytest.raises(Exception) as info:
        decoy.scan(path)
    got = info.value
    assert type(got) is type(want) and type(got).__name__ == "TransformError"
    assert got.code == want.code  # type: ignore[attr-defined]
    assert MARKER not in str(got)


def test_at7_a_file_that_is_not_parquet_is_a_class_only_scan_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.parquet"
    path.write_text(f"not parquet {MARKER}", encoding="utf-8")
    want = _engine_error(path)
    with pytest.raises(Exception) as info:
        decoy.scan(path)
    got = info.value
    assert type(got) is type(want) and type(got).__name__ == "ScanSourceError"
    assert (got.table, got.cause_class) == (want.table, want.cause_class)  # type: ignore[attr-defined]
    assert MARKER not in str(got)


def _staged(tmp: Path) -> list[str]:
    return sorted(p.name for p in tmp.iterdir())


@pytest.fixture
def private_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp))
    return tmp


def test_at10_a_dataframe_is_staged_under_a_fixed_name_and_removed(
    private_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import decoy_engine

    seen: list[list[str]] = []
    real = decoy_engine.scan_sources

    def spy(descriptors: Any, **kwargs: Any):
        seen.append(_staged(private_tmp))
        return real(descriptors, **kwargs)

    monkeypatch.setattr(decoy_engine, "scan_sources", spy)
    decoy.scan(pd.DataFrame({"a": [1, 2, 3]}), source_label="secret_label")
    assert len(seen) == 1 and len(seen[0]) == 1
    assert seen[0][0].startswith(".decoy-mask-scan-")
    assert "secret_label" not in seen[0][0]
    assert _staged(private_tmp) == []


def test_at10_the_staged_file_is_removed_when_the_engine_fails(
    private_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import decoy_engine

    def fail(*_a: object, **_k: object) -> None:
        raise RuntimeError("engine down")

    monkeypatch.setattr(decoy_engine, "scan_sources", fail)
    with pytest.raises(RuntimeError, match="engine down"):
        decoy.scan(pd.DataFrame({"a": [1]}), source_label="secret_label")
    assert _staged(private_tmp) == []


def _mixed_frame() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, MARKER, 3]})


def _no_chain(exc: BaseException) -> None:
    assert type(exc) is TypeError
    assert str(exc).startswith("data could not be converted to Arrow: Arrow")
    assert MARKER not in str(exc)
    assert exc.__cause__ is None and exc.__context__ is None


def test_at11_scan_reports_an_arrow_failure_by_class_only() -> None:
    with pytest.raises(TypeError) as info:
        decoy.scan(_mixed_frame())
    _no_chain(info.value)


def test_at11_mask_reports_an_arrow_failure_by_class_only(tmp_path: Path) -> None:
    config = {
        "version": 2,
        "global_settings": {"seed": 1},
        "tables": [{"name": "t", "columns": [{"name": "a", "strategy": "passthrough"}]}],
    }
    with pytest.raises(TypeError) as info:
        decoy.mask(_mixed_frame(), config, out=str(tmp_path / "o.csv"))
    _no_chain(info.value)


def test_at13_an_unknown_format_lists_the_allowed_ones(
    tmp_path: Path, engine_must_not_run: None
) -> None:
    path = write_csv(tmp_path / "x.csv")
    with pytest.raises(ValueError, match=r"\['delimited', 'fixed-width', 'parquet'\]"):
        decoy.scan(path, format="xml", has_header=True)


def test_at13_a_missing_path_is_a_usage_error(tmp_path: Path, engine_must_not_run: None) -> None:
    with pytest.raises(ValueError, match="file not found"):
        decoy.scan(tmp_path / "nope.csv", has_header=True)


def test_at13_a_directory_is_a_usage_error(tmp_path: Path, engine_must_not_run: None) -> None:
    with pytest.raises(ValueError, match="is a directory"):
        decoy.scan(tmp_path, has_header=True)


def test_at13_file_options_with_a_dataframe_are_refused(engine_must_not_run: None) -> None:
    with pytest.raises(ValueError):
        decoy.scan(pd.DataFrame({"a": [1]}), has_header=True)


def test_at13_a_bad_layout_list_reads_as_a_bad_layout_file(
    tmp_path: Path, engine_must_not_run: None
) -> None:
    path, _ = write_fixed(tmp_path / "x.dat")
    bad = [{"name": "a", "start": 0, "width": 0}]
    layout = tmp_path / "bad.yaml"
    layout.write_text(yaml.safe_dump({"columns": bad}), encoding="utf-8")
    with pytest.raises(ValueError) as from_file:
        decoy.scan(path, layout=layout)
    with pytest.raises(ValueError) as from_list:
        decoy.scan(path, layout=bad)
    assert from_file.value.__cause__ is None and from_list.value.__cause__ is None
    assert str(from_file.value).replace("layout file bad.yaml", "the layout list") == str(
        from_list.value
    )
