"""G-KIND-CANARY's runnable half: every registered canary case runs its producer and is checked.

`tests/e2e/library/_canary.py` holds `CASES`, one per writable record kind whose producer exists:
the producer runs with a canary in every cell, the positive check finds a record of that kind,
and the negative check finds the canary in no file under `.decoy/library/` or `.decoy/logs/`.
The sentry (`tests/sentry/defects/test_kind_canary.py`) derives coverage from the same registry.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from decoy.cli.io import DECOY_DIR
from decoy.cli.library import open_library
from tests.e2e.library._canary import CANARY, CASES, kinds_written, leaks
from tests.unit.library._helpers import envelope


@pytest.mark.parametrize("kind", sorted(CASES))
def test_a_canary_run_writes_its_kind_and_no_canary(kind: str, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    CASES[kind].produce(project)
    assert kind in kinds_written(project / DECOY_DIR)  # positive: the producer wrote the kind
    assert leaks(project / DECOY_DIR) == []  # negative: the canary reached no library file


def test_the_negative_check_sees_a_planted_canary(tmp_path: Path) -> None:
    root = tmp_path / DECOY_DIR
    open_library(root).put(envelope(0))
    assert leaks(root) == []
    (root / "logs").mkdir()
    (root / "logs" / "job.jsonl").write_text(f'{{"cell": "{CANARY}"}}\n', encoding="utf-8")
    assert leaks(root) == ["logs/job.jsonl"]


def test_the_positive_check_sees_a_written_kind(tmp_path: Path) -> None:
    root = tmp_path / DECOY_DIR
    open_library(root).put(envelope(0))
    assert kinds_written(root) == {"sample-run"}
