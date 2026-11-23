"""`decoy run --chunked` route label, native intent and companion cases.

PARQUET-CHUNKED-NULLABLE-INT S2 (AT-C6, AT-C11, AT-C12 companion cell, AT-C16). They share
the config helpers and the companion fixtures of `tests/e2e/test_run_native.py`.
"""

from __future__ import annotations

import json as _json
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.exit_codes import EXIT_USAGE
from tests.e2e.test_run_native import _hash_eligible_config, _requires_real_companion

pytestmark = pytest.mark.usefixtures("mask_secret")

runner = CliRunner()


@pytest.fixture
def force_absent_companion(monkeypatch: pytest.MonkeyPatch) -> None:
    """The companion is genuinely absent for the CLI probe and the engine's own admission."""
    monkeypatch.setitem(sys.modules, "decoy_engine_native", None)


def _no_kernel_table(name: str, src: Path, out: Path) -> tuple[dict, dict, dict]:
    """A table the engine admits natively but that runs no kernel (`text_redact` has none)."""
    pd.DataFrame({"note": [f"call {i}" for i in range(6)]}).to_parquet(src, index=False)
    table = {"name": name, "columns": [{"name": "note", "strategy": "text_redact"}]}
    source = {"type": "file", "format": "parquet", "path": str(src)}
    target = {"type": "file", "format": "csv", "path": str(out)}
    return table, source, target


def _chunked_labels(tmp_path: Path, *, native: bool, no_kernel: bool) -> dict:
    """Run a one- or two-table `--chunked` job and return its `--json` document."""
    cfg = _json.loads(_json.dumps(yaml.safe_load(_hash_eligible_config(tmp_path).read_text())))
    if no_kernel:
        table, source, target = _no_kernel_table(
            "notes", tmp_path / "note.parquet", tmp_path / "note_out.csv"
        )
        if native:  # one native table beside the no-kernel one
            cfg["tables"].append(table)
            cfg["sources"]["notes"] = source
            cfg["targets"]["notes"] = target
        else:
            cfg["tables"] = [table]
            cfg["sources"] = {"notes": source}
            cfg["targets"] = {"notes": target}
    path = tmp_path / "chunked.yaml"
    path.write_text(yaml.dump(cfg))
    result = runner.invoke(app, ["run", str(path), "--chunked", "--json"])
    assert result.exit_code == 0, result.output
    return _json.loads(result.stdout)


def test_chunked_label_is_pandas_for_an_admitted_table_with_no_kernel(tmp_path: Path):
    payload = _chunked_labels(tmp_path, native=False, no_kernel=True)
    assert payload["native_route"]["applicable"] is False
    assert payload["native_route"]["state"] is None
    assert payload["native_route"]["label"] == "chunked stream (pandas)"


def test_chunked_label_is_pandas_without_a_companion(tmp_path: Path, force_absent_companion: None):
    payload = _chunked_labels(tmp_path, native=True, no_kernel=False)
    assert payload["native_route"]["label"] == "chunked stream (pandas)"


@_requires_real_companion
def test_chunked_label_is_native_with_a_companion(tmp_path: Path):
    payload = _chunked_labels(tmp_path, native=True, no_kernel=False)
    assert payload["native_route"]["applicable"] is False
    assert payload["native_route"]["state"] is None
    assert payload["native_route"]["label"] == "chunked stream (native)"


@_requires_real_companion
def test_chunked_label_is_mixed_for_one_native_and_one_no_kernel_table(tmp_path: Path):
    payload = _chunked_labels(tmp_path, native=True, no_kernel=True)
    assert payload["native_route"]["label"] == "chunked stream (mixed)"


def test_native_with_chunked_says_the_chunked_text(tmp_path: Path):
    """AT-C11: the refusal keeps its code and exit; the old 'could never' text is gone."""
    config = _hash_eligible_config(tmp_path)
    result = runner.invoke(app, ["run", str(config), "--native", "--chunked", "--json"])
    assert result.exit_code == EXIT_USAGE
    payload = _json.loads(result.stdout)
    assert payload["code"] == "native_require_not_a_candidate"
    assert "--native is not supported with --chunked" in payload["error"]
    assert "could never show" not in payload["error"]
    assert not (tmp_path / "out.csv").exists()


def _capture_evidence(monkeypatch: pytest.MonkeyPatch) -> list:
    import decoy_engine

    sinks: list = []
    real = decoy_engine.run_mask_chunked

    def spy(*args, **kwargs):
        sinks.append(kwargs.get("route_evidence_sink"))
        return real(*args, **kwargs)

    monkeypatch.setattr(decoy_engine, "run_mask_chunked", spy)
    return sinks


def test_no_native_chunked_runs_the_oracle_leg_and_matches_the_default_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """AT-C12 companion cell (M-C6): `--no-native` reroutes every table with a recorded
    reason, runs no kernel, and changes no output byte."""
    config = _hash_eligible_config(tmp_path)
    out = tmp_path / "out.csv"
    sinks = _capture_evidence(monkeypatch)
    default = runner.invoke(app, ["run", str(config), "--chunked", "--json"])
    assert default.exit_code == 0, default.output
    default_bytes = out.read_bytes()
    out.unlink()
    sinks.clear()
    result = runner.invoke(app, ["run", str(config), "--chunked", "--no-native", "--json"])
    assert result.exit_code == 0, result.output
    (sink,) = sinks
    assert sink, "the engine recorded no route evidence"
    for item in sink:
        assert item.native_admitted is False
        assert item.reroute_reason == "adapter_requested"
        assert item.compiled_kernel_executed is False
        assert item.pool_select_executed is False
    assert _json.loads(result.stdout)["native_route"]["label"] == "chunked stream (pandas)"
    assert out.read_bytes() == default_bytes


def test_broken_companion_does_not_refuse_a_chunked_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """AT-C16: a companion that imports but cannot report its ABI does not refuse a chunked
    run (the gate does not classify it), and the engine falls back to pandas, so the label says
    so. The companion is simulated at its import boundary, a package whose `_kernel` raises."""
    import importlib.machinery
    import types

    package = types.ModuleType("decoy_engine_native")
    package.__spec__ = importlib.machinery.ModuleSpec("decoy_engine_native", None)
    package.__path__ = []
    kernel = types.ModuleType("decoy_engine_native._kernel")

    def _abi_version():
        raise RuntimeError("broken companion")

    kernel.abi_version = _abi_version
    package._kernel = kernel
    monkeypatch.setitem(sys.modules, "decoy_engine_native", package)
    monkeypatch.setitem(sys.modules, "decoy_engine_native._kernel", kernel)
    config = _hash_eligible_config(tmp_path)
    out = tmp_path / "out.csv"
    result = runner.invoke(app, ["run", str(config), "--chunked", "--json"])
    assert result.exit_code == 0, result.output
    assert _json.loads(result.stdout)["native_route"]["label"] == "chunked stream (pandas)"
    chunked_bytes = out.read_bytes()
    out.unlink()
    result = runner.invoke(app, ["run", str(config), "--chunked", "--no-native", "--json"])
    assert result.exit_code == 0, result.output
    assert out.read_bytes() == chunked_bytes
