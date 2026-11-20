"""The shared scan call (`decoy.cli.scanning.scan_descriptors`): rows rule, checks, forwarding."""

from __future__ import annotations

from typing import Any

import pytest

from decoy.cli.scanning import SampleStrategy, ScanUsageError, check_scan_options, scan_descriptors


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    import decoy_engine

    calls: list[dict[str, Any]] = []

    def fake_scan(descriptors: Any, **kwargs: Any) -> str:
        calls.append(kwargs)
        return "RESULT"

    monkeypatch.setattr(decoy_engine, "scan_sources", fake_scan)
    monkeypatch.setattr(decoy_engine, "scan_set_to_dict", lambda r, *, detail: {"r": r, "d": detail})
    return calls


@pytest.mark.parametrize("rows", [0, None])
def test_zero_and_none_read_every_row(engine: list[dict[str, Any]], rows: int | None) -> None:
    scan_descriptors({}, rows=rows, strategy="head")
    assert engine[0]["sample_rows"] is None
    assert engine[0]["strategy"] == "full"


def test_a_bounded_sample_keeps_rows_and_strategy(engine: list[dict[str, Any]]) -> None:
    scan_descriptors({}, rows=5, strategy="random")
    assert (engine[0]["sample_rows"], engine[0]["strategy"]) == (5, "random")


def test_full_strategy_reads_every_row(engine: list[dict[str, Any]]) -> None:
    scan_descriptors({}, rows=5, strategy="full")
    assert (engine[0]["sample_rows"], engine[0]["strategy"]) == (None, "full")


def test_bad_options_raise_before_the_engine(engine: list[dict[str, Any]]) -> None:
    with pytest.raises(ScanUsageError, match="rows must be 0 or more, got -1"):
        scan_descriptors({}, rows=-1, strategy="head")
    allowed = [s.value for s in SampleStrategy]
    with pytest.raises(ScanUsageError) as info:
        scan_descriptors({}, rows=1, strategy="sideways")
    assert str(allowed) in str(info.value)
    with pytest.raises(ScanUsageError):
        check_scan_options(-3, "head")
    assert engine == []


def test_pre_scan_reaches_the_engine_unchanged(engine: list[dict[str, Any]]) -> None:
    sentinel = object()
    scan_descriptors({}, rows=1, strategy="head", pre_scan=sentinel)  # type: ignore[arg-type]
    assert engine[0]["pre_scan"] is sentinel
    scan_descriptors({}, rows=1, strategy="head")
    assert engine[1]["pre_scan"] is None


def test_on_stage_runs_after_the_scan_and_after_the_core(engine: list[dict[str, Any]]) -> None:
    ticks: list[int] = []
    run = scan_descriptors({}, rows=1, strategy="head", on_stage=lambda: ticks.append(len(engine)))
    assert ticks == [1, 1]
    assert run.core == {"r": "RESULT", "d": False}
    assert run.result == "RESULT"
