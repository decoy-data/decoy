"""Fixtures shared by the e2e tests that drive the native companion."""

from __future__ import annotations

import sys

import pytest


@pytest.fixture
def force_absent_companion(monkeypatch: pytest.MonkeyPatch) -> None:
    """The companion is genuinely absent for the CLI probe and the engine's own admission.

    Setting the module to None makes any import of it raise ImportError, whether or not a real
    companion is installed in this environment.
    """
    monkeypatch.setitem(sys.modules, "decoy_engine_native", None)
