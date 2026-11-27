"""C2a-1: a fixed folder and a host without the engine's lock use the pass-through.

AT-49 (`--out-dir`), AT-74b (no pointer), AT-82 (the root decides the stage, not the route).
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from decoy.cli.io import (
    DeliveryRoot,
    Fixed,
    NoLocalOutput,
    Relative,
    Split,
    _pointer,
    delivery_root,
)
from tests.e2e.delivery_sink._support import document, latest, project, run, runs


def test_at49_out_dir_delivers_in_place_and_says_so(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    out = tmp_path / "out_here"
    result = run(yml, "--out-dir", str(out))
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in out.glob("*.csv")) == ["t1.csv", "t2.csv"]
    doc = document(result)
    assert doc["delivery"]["mode"] == "in_place"
    assert doc["delivery"]["outcome"] == "delivered"
    assert latest(root) is None


def test_at74b_a_host_without_the_pointer_keeps_todays_writes(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    with mock.patch.object(_pointer, "_pointer_supported", return_value=False):
        result = run(yml)
    assert result.exit_code == 0, result.output
    (folder,) = runs(root)
    assert sorted(p.name for p in folder.glob("*.csv")) == ["t1.csv", "t2.csv"]
    assert latest(root) == folder.name
    assert document(result)["delivery"]["mode"] == "in_place"


def test_at82_an_absolute_only_project_run_is_kind_a_with_no_run_folder(tmp_path: Path) -> None:
    root, yml = project(tmp_path, targets="absolute")
    result = run(yml)
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in (tmp_path / "abs").glob("*.csv")) == ["t1.csv", "t2.csv"]
    assert not (root / "out").exists()
    assert document(result)["delivery"]["mode"] == "in_place"


def _cfg(*paths: str) -> dict:
    return {
        "targets": {
            f"t{i}": {"type": "file", "format": "csv", "path": p} for i, p in enumerate(paths)
        }
    }


def test_at82d_every_delivery_root_variant(tmp_path: Path) -> None:
    folder = tmp_path / "f"
    folder.mkdir()
    out = tmp_path / "o"
    out.mkdir()
    cases: list[tuple[dict, Path | None, DeliveryRoot]] = [
        (_cfg("a.csv", "b.csv"), None, Relative()),
        (_cfg(str(folder / "a.csv"), str(folder / "b.csv")), None, Fixed(folder)),
        (_cfg("a.csv", str(out / "b.csv")), out, Fixed(out)),
        (_cfg(), None, NoLocalOutput()),
        (_cfg(), out, Fixed(out)),
    ]
    for config, fixed, expected in cases:
        got = delivery_root(config, fixed)
        assert type(got) is type(expected)
        if isinstance(expected, Fixed):
            assert isinstance(got, Fixed) and got.folder.resolve() == expected.folder.resolve()
    split = delivery_root(_cfg("a.csv", str(folder / "b.csv")), None)
    assert isinstance(split, Split)
    assert (split.first, split.second) == ("targets.t0.path", "targets.t1.path")


def test_at82d_a_split_root_is_refused_at_open(tmp_path: Path) -> None:
    from decoy.cli.io import DeliverySink, LayoutError, RunLayout

    layout = RunLayout.fixed(tmp_path)
    config = _cfg("a.csv", str(tmp_path / "x" / "b.csv"))
    with pytest.raises(LayoutError) as raised:
        DeliverySink.open(layout, config, mock.Mock(), "op-1")
    assert raised.value.code == "layout.delivery_root_split"


def test_at14b_the_sink_only_hands_the_stage_the_decision(tmp_path: Path) -> None:
    """The sink holds a `SinkStage` and calls `deliver(decision, before_visible, reconcile)`
    once; it knows no stage-specific name, so a new stage needs no sink change."""
    from decoy_engine.publication import DeliveryReceipt, StageDecision

    from decoy.cli.io import DeliveryHooks, DeliverySink, Ledger, RunLayout
    from decoy.cli.io._delivery import RootKind, _Direct

    calls: list[tuple] = []

    class Recording:
        mode = "in_place"

        def abort(self) -> None:
            calls.append(("abort",))

        def deliver(self, decision, before_visible, reconcile=None):
            calls.append(("deliver", decision, callable(before_visible), callable(reconcile)))
            return DeliveryReceipt("delivered")

    layout = RunLayout.fixed(tmp_path)
    hooks = DeliveryHooks(
        write_attempts=lambda staged: None,
        publish_attempts=lambda: None,
        discard_attempts=lambda: None,
        show_warning=lambda item: None,
    )
    sink = DeliverySink(RootKind.fixed_folder, Recording(), _Direct(layout), layout, hooks)
    decision = StageDecision(True, frozenset({"t1"}))
    sink.deliver(decision, Ledger())
    assert calls == [("deliver", decision, True, True)]
