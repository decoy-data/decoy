"""`decoy run` asks the installed engine what `run_pipeline` takes in one place (#216 review).

`decoy._native_gate.run_pipeline_accepts` is the one capability check; the progress sink and the
native lane both call it instead of reading `inspect.signature` themselves. The progress tests
live in this package, not the flat `tests/unit/`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from decoy import _native_gate
from decoy.cli.run import _progress

ROOT = Path(__file__).resolve().parents[3]


def _fake(progress: object = None, unified_slice_enabled: bool = True) -> None:
    del progress, unified_slice_enabled


def test_the_progress_sink_uses_the_one_capability_check(monkeypatch: pytest.MonkeyPatch) -> None:
    fanout = _progress.build()
    assert _progress.run_pipeline_kwargs(_fake, fanout) == {"progress": fanout}  # control
    asked: list[str] = []

    def accepts(name: str, run_pipeline: object = None) -> bool:
        asked.append(name)
        return False

    monkeypatch.setattr(_native_gate, "run_pipeline_accepts", accepts)
    assert _progress.run_pipeline_kwargs(_fake, fanout) == {}
    assert asked == ["progress"]


def test_the_check_reads_the_signature_it_is_given() -> None:
    assert _native_gate.run_pipeline_accepts("progress", _fake) is True
    assert _native_gate.run_pipeline_accepts("nope", _fake) is False


def test_no_run_module_reads_the_engine_signature_itself() -> None:
    for path in (ROOT / "src" / "decoy" / "cli" / "run").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = [
            n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "signature"
        ]
        assert calls == [], path.name


def test_the_progress_tests_are_not_in_the_flat_unit_folder() -> None:
    assert list((ROOT / "tests" / "unit").glob("test_progress*.py")) == []
