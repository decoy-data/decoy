"""The progress sink is passed whenever a fanout is set; the tests live in this package."""

from __future__ import annotations

from pathlib import Path

import pytest

from decoy.cli.run import _progress

ROOT = Path(__file__).resolve().parents[3]


def _run_pipeline_without_progress(config, sources=None, *, engine_version):
    raise AssertionError("never called")


def test_the_progress_sink_is_passed_whenever_a_fanout_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("decoy_engine.run_pipeline", _run_pipeline_without_progress)
    fanout = _progress.build()
    assert _progress.run_pipeline_kwargs(_run_pipeline_without_progress, fanout) == {
        "progress": fanout
    }
    assert _progress.run_pipeline_kwargs(_run_pipeline_without_progress, None) == {}


def test_the_progress_tests_are_not_in_the_flat_unit_folder() -> None:
    assert list((ROOT / "tests" / "unit").glob("test_progress*.py")) == []
