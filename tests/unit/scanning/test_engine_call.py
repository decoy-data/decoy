"""The shared scan call (`decoy.cli.scanning.scan_descriptors`): rows rule, checks, forwarding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from decoy.cli._sources import csv_file_source, scan_prepared_sources
from decoy.cli.scanning import SampleStrategy, ScanUsageError, check_scan_options, scan_descriptors


@pytest.fixture
def prepared(tmp_path: Path) -> Any:
    """A scan capability from the real gate; the file need not exist (the gate opens no data)."""
    source = csv_file_source(tmp_path / "t.csv", has_header=True)
    return scan_prepared_sources({"sources": {"t": source}}, base_dir=tmp_path)


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    import decoy_engine

    calls: list[dict[str, Any]] = []

    def fake_scan(descriptors: Any, **kwargs: Any) -> str:
        calls.append(kwargs)
        return "RESULT"

    monkeypatch.setattr(decoy_engine, "scan_sources", fake_scan)
    monkeypatch.setattr(
        decoy_engine, "scan_set_to_dict", lambda r, *, detail: {"r": r, "d": detail}
    )
    return calls


@pytest.mark.parametrize("rows", [0, None])
def test_zero_and_none_read_every_row(
    engine: list[dict[str, Any]], prepared: Any, rows: int | None
) -> None:
    scan_descriptors(prepared, rows=rows, strategy="head")
    assert engine[0]["sample_rows"] is None
    assert engine[0]["strategy"] == "full"


def test_a_bounded_sample_keeps_rows_and_strategy(
    engine: list[dict[str, Any]], prepared: Any
) -> None:
    scan_descriptors(prepared, rows=5, strategy="random")
    assert (engine[0]["sample_rows"], engine[0]["strategy"]) == (5, "random")


def test_full_strategy_reads_every_row(engine: list[dict[str, Any]], prepared: Any) -> None:
    scan_descriptors(prepared, rows=5, strategy="full")
    assert (engine[0]["sample_rows"], engine[0]["strategy"]) == (None, "full")


def test_bad_options_raise_before_the_engine(engine: list[dict[str, Any]], prepared: Any) -> None:
    with pytest.raises(ScanUsageError, match="rows must be 0 or more, got -1"):
        scan_descriptors(prepared, rows=-1, strategy="head")
    allowed = [s.value for s in SampleStrategy]
    with pytest.raises(ScanUsageError) as info:
        scan_descriptors(prepared, rows=1, strategy="sideways")
    assert str(allowed) in str(info.value)
    with pytest.raises(ScanUsageError):
        check_scan_options(-3, "head")
    assert engine == []


def test_pre_scan_reaches_the_engine_unchanged(engine: list[dict[str, Any]], prepared: Any) -> None:
    sentinel = object()
    scan_descriptors(prepared, rows=1, strategy="head", pre_scan=sentinel)  # type: ignore[arg-type]
    assert engine[0]["pre_scan"] is sentinel
    scan_descriptors(prepared, rows=1, strategy="head")
    assert engine[1]["pre_scan"] is None


def test_on_stage_runs_after_the_scan_and_after_the_core(
    engine: list[dict[str, Any]], prepared: Any
) -> None:
    ticks: list[int] = []
    run = scan_descriptors(
        prepared, rows=1, strategy="head", on_stage=lambda: ticks.append(len(engine))
    )
    assert ticks == [1, 1]
    assert run.core == {"r": "RESULT", "d": False}
    assert run.result == "RESULT"


def test_the_engine_gets_exactly_the_declaration(
    engine: list[dict[str, Any]], prepared: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import decoy_engine

    seen: list[Any] = []
    monkeypatch.setattr(
        decoy_engine, "scan_sources", lambda d, **kw: seen.append((d, kw)) or "RESULT"
    )
    scan_descriptors(prepared, rows=1, strategy="head", integrity=False)
    declaration = prepared.scan_declaration
    descriptors, kwargs = seen[0]
    assert descriptors is declaration.descriptors
    assert kwargs["tables"] is declaration.tables
    assert kwargs["relationships"] is declaration.relationships
    assert kwargs["relationship_positions"] is declaration.relationship_positions
    assert kwargs["integrity"] is False


def test_a_mapping_is_refused_before_the_engine(engine: list[dict[str, Any]]) -> None:
    with pytest.raises(TypeError):
        scan_descriptors({"t": {"type": "file"}}, rows=1, strategy="head")  # type: ignore[arg-type]
    assert engine == []


def test_a_capability_from_another_request_is_refused(engine: list[dict[str, Any]]) -> None:
    from decoy_engine import DeclarationRequest, prepare_declared_sources

    other = prepare_declared_sources(DeclarationRequest.for_supplied({"version": 2}, {}))
    with pytest.raises(TypeError):
        scan_descriptors(other, rows=1, strategy="head")
    assert engine == []
