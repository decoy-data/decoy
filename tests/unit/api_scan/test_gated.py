"""`decoy.scan()` reaches the engine only through the scan gate (S1c.2a, T2-api-gated)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from tests.unit.api_scan.test_parity import write_csv

import decoy
import decoy.api as api


@pytest.fixture
def gate_calls(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    calls: list[Any] = []
    real = api.scan_prepared_sources

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(api, "scan_prepared_sources", spy)
    return calls


def test_a_path_scan_calls_the_gate_once(tmp_path: Path, gate_calls: list[Any]) -> None:
    decoy.scan(write_csv(tmp_path / "x.csv"), has_header=True)
    assert len(gate_calls) == 1


def test_a_dataframe_scan_calls_the_gate_once(gate_calls: list[Any]) -> None:
    decoy.scan(pd.DataFrame({"a": [1, 2, 3]}))
    assert len(gate_calls) == 1


def test_a_gate_refusal_removes_the_staged_dataframe_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staged: list[Path] = []
    real_stage = api._stage_source_entry

    def record(name: str, data: Any, tmp_paths: list[Path]) -> Any:
        entry = real_stage(name, data, tmp_paths)
        staged.extend(tmp_paths)
        return entry

    def refuse(*_a: Any, **_k: Any) -> Any:
        raise ValueError("refused at the gate")

    monkeypatch.setattr(api, "_stage_source_entry", record)
    monkeypatch.setattr(api, "scan_prepared_sources", refuse)
    with pytest.raises(ValueError, match="refused at the gate"):
        decoy.scan(pd.DataFrame({"a": [1]}))
    assert staged
    assert not any(p.exists() for p in staged)
