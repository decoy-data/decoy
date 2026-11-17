"""The progress tests live in this package, not the flat `tests/unit/`."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_the_progress_tests_are_not_in_the_flat_unit_folder() -> None:
    assert list((ROOT / "tests" / "unit").glob("test_progress*.py")) == []
