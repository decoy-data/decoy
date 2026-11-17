"""The CLI pins one engine, so it calls the names that pin ships and does not probe for them."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from decoy import _native_gate
from decoy._native_gate import PreGateResult
from decoy.cli.run import _progress

SRC = Path(__file__).resolve().parents[2] / "src" / "decoy"
PROBED = {"native_companion_status", "estimate_job_capacity", "EnvFlagError"}
SITES = (
    "_native_gate.py",
    "cli/info.py",
    "cli/preflight.py",
    "distribution/selfcheck.py",
)


def _without_the_keywords(config, sources=None, *, engine_version):
    raise AssertionError("never called")


def test_no_native_passes_the_keyword_whatever_the_run_pipeline_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("decoy_engine.run_pipeline", _without_the_keywords)
    disabled = PreGateResult(unified_slice_enabled=False)
    assert _native_gate.run_pipeline_kwargs(disabled) == {"unified_slice_enabled": False}
    assert _native_gate.run_pipeline_kwargs(PreGateResult(unified_slice_enabled=True)) == {}


def test_the_progress_sink_is_passed_whenever_a_fanout_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("decoy_engine.run_pipeline", _without_the_keywords)
    fanout = _progress.build()
    assert _progress.run_pipeline_kwargs(_without_the_keywords, fanout) == {"progress": fanout}
    assert _progress.run_pipeline_kwargs(_without_the_keywords, None) == {}


def test_the_signature_probe_is_gone() -> None:
    assert not hasattr(_native_gate, "run_pipeline_accepts")
    assert "inspect" not in vars(_native_gate)


@pytest.mark.parametrize("rel", SITES)
def test_pinned_engine_names_are_not_probed_by_string(rel: str) -> None:
    tree = ast.parse((SRC / rel).read_text(encoding="utf-8"))
    probes = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"getattr", "hasattr"}
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value in PROBED
    ]
    assert probes == []
