"""Pin the sub-key sets the --json snapshot treats as opaque.

`write_shapes.py` declares `info /native_companion` and `run /warnings` opaque, so a
renamed sub-key would pass the snapshot. These tests call the real builders instead.
"""

from __future__ import annotations

from types import SimpleNamespace

import decoy_engine

from decoy.cli.info import _companion_report
from decoy.cli.io import LayoutWarning
from decoy.cli.project._common import warning_records


def test_companion_report_key_set(monkeypatch) -> None:
    status = SimpleNamespace(
        present=True, ok=True, reason="ok", abi_expected="1", abi_actual="1", version="0.1"
    )
    monkeypatch.setattr(decoy_engine, "native_companion_status", lambda: status, raising=False)
    report = _companion_report()
    assert report is not None
    assert set(report) == {"present", "ok", "reason", "abi_expected", "abi_actual", "version"}


def test_warning_record_key_set() -> None:
    records = warning_records([LayoutWarning(code="X-1", message="m")])
    assert len(records) == 1
    assert set(records[0]) == {"code", "message"}
