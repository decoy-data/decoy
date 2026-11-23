"""`decoy.scan()` reaches the engine only through the scan gate (S1c.2a, T2-api-gated)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from tests.unit.api_scan.test_parity import write_csv

import decoy
import decoy.api as api


@pytest.fixture
def gate_calls(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """The `base_dir` of each gate call; the real gate still runs."""
    calls: list[Path] = []
    real = api.scan_prepared_sources

    def spy(
        config: dict[str, Any], *, base_dir: Path, tables: Sequence[str] | None = None
    ) -> object:
        calls.append(base_dir)
        return real(config, base_dir=base_dir, tables=tables)

    monkeypatch.setattr(api, "scan_prepared_sources", spy)
    return calls


def test_a_path_scan_calls_the_gate_once(tmp_path: Path, gate_calls: list[Path]) -> None:
    decoy.scan(write_csv(tmp_path / "x.csv"), has_header=True)
    assert len(gate_calls) == 1


def test_a_dataframe_scan_calls_the_gate_once(gate_calls: list[Path]) -> None:
    decoy.scan(pd.DataFrame({"a": [1, 2, 3]}))
    assert len(gate_calls) == 1


def test_a_gate_refusal_removes_the_staged_dataframe_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staged: list[Path] = []
    real_stage = api._stage_source_entry

    def record(name: str, data: object, tmp_paths: list[Path]) -> dict[str, Any]:
        entry = real_stage(name, data, tmp_paths)
        staged.extend(tmp_paths)
        return entry

    def refuse(config: dict[str, Any], *, base_dir: Path) -> None:
        raise ValueError("refused at the gate")

    monkeypatch.setattr(api, "_stage_source_entry", record)
    monkeypatch.setattr(api, "scan_prepared_sources", refuse)
    with pytest.raises(ValueError, match="refused at the gate"):
        decoy.scan(pd.DataFrame({"a": [1]}))
    assert staged
    assert not any(p.exists() for p in staged)
