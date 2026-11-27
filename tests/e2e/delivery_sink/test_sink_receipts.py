"""C2a-1: what a run says about its delivery, and what it writes beside the run folder.

AT-12 (uncertain swap), AT-36b (the ledger type), AT-36d (table paths follow the receipt), AT-37
(a missing report withholds), AT-42 (writer order), AT-44 (`--result` after delivery), AT-48
(Ctrl-C at the swap), AT-59 (the not-delivered report), AT-79 (quarantine).
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

from decoy.__main__ import app
from decoy.cli.io import Ledger, _delivery
from decoy.cli.io._published import LocalOutput
from decoy.cli.run._context import RunContext
from tests.e2e.delivery_sink._support import (
    document,
    latest,
    litter,
    post_scan,
    project,
    run,
    runner,
    runs,
    vaulted,
)

posix = pytest.mark.skipif(sys.platform == "win32", reason="the strict stage is POSIX only")


def body(result) -> dict:
    """The top-level `--json` object of a run (the run result is its `result` member)."""
    out = result.output
    return json.loads(out[out.index("{") :])


# --- AT-36b: the ledger holds published outputs only ----------------------------------------


def test_at36b_the_ledger_refuses_a_bare_path(tmp_path: Path) -> None:
    ledger = Ledger()
    ledger["t1"] = LocalOutput(tmp_path / "a.csv")
    members = RunContext.published_members(types.SimpleNamespace(_published=ledger, layout=None))
    assert members == {"outputs": [{"table": "t1", "path": str((tmp_path / "a.csv").resolve())}]}
    with pytest.raises(TypeError):
        ledger["t2"] = tmp_path / "b.csv"  # type: ignore[assignment]
    with pytest.raises(TypeError):
        ledger.update({"t2": LocalOutput(tmp_path / "b.csv")})
    assert list(ledger) == ["t1"]


# --- AT-36d: a table path is the bound file under the run folder, and only once delivered ---


@posix
def test_at36d_json_and_human_paths_name_the_delivered_files(tmp_path: Path) -> None:
    root, yml = project(tmp_path / "json")
    result = run(yml)
    assert result.exit_code == 0, result.output
    (folder,) = runs(root)
    doc = body(result)
    for record in doc["tables"]:
        expected = folder.resolve() / f"{record['name']}.csv"
        assert Path(record["path"]) == expected
        assert expected.is_file()  # the stage is gone: this is the bound file, not a slot
    assert [o["path"] for o in doc["outputs"]] == [t["path"] for t in doc["tables"]]

    root2, yml2 = project(tmp_path / "human")
    human = runner.invoke(app, ["run", str(yml2)], env={"COLUMNS": "400"})
    assert human.exit_code == 0, human.output
    (folder2,) = runs(root2)
    for name in ("t1", "t2"):
        assert str(folder2.resolve() / f"{name}.csv") in human.output


# --- AT-12: an uncertain swap is delivered, with one warning -------------------------------


@posix
def test_at12_a_swap_that_cannot_confirm_is_uncertain_not_nothing(tmp_path: Path) -> None:
    from decoy_engine.publication import LocalPointerStore

    root, yml = project(tmp_path)
    real = LocalPointerStore.replace_if

    def replace_then_doubt(self, expected, payload):
        real(self, expected, payload)
        return "uncertain"

    with mock.patch.object(LocalPointerStore, "replace_if", replace_then_doubt):
        result = run(yml)
    assert result.exit_code == 0, result.output
    (folder,) = runs(root)
    assert latest(root) == folder.name
    assert result.output.count("publication_commit_uncertain") == 1
    assert document(result)["delivery"]["outcome"] == "delivered"
    # AT-36d: an uncertain receipt counts as delivered but shows no table path.
    assert all(record["path"] is None for record in body(result)["tables"])


# --- AT-37: a requested integrity report that never came withholds the run ------------------


@posix
def test_at37_a_missing_integrity_report_delivers_nothing(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    # The config asks for no report; the predicate says one was due, so none exists to check.
    with mock.patch("decoy_engine.config.post_scan_integrity_requested", return_value=True):
        result = run(yml)
    assert result.exit_code == 4, result.output
    (empty,) = runs(root)  # the folder P4 made stays, with nothing in it
    assert list(empty.iterdir()) == []
    assert latest(root) is None
    assert document(result)["delivery"]["outcome"] == "nothing"


# --- AT-42: the order of the writers --------------------------------------------------------


@posix
def test_at42_the_writers_run_in_the_documented_order(tmp_path: Path, monkeypatch) -> None:
    from decoy_engine.publication import LocalPointerStore

    from decoy.cli.run import _evidence, _flow, _result

    root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    events: list[str] = []

    def record(name: str, real):
        def wrapper(*args, **kwargs):
            result = real(*args, **kwargs)
            events.append(name)
            return result

        return wrapper

    stage = __import__("decoy_engine.publication._stage", fromlist=["x"])
    publish = __import__("decoy_engine.publication._publish", fromlist=["x"])
    patches = [
        mock.patch.object(_evidence, "write_attempts", record("attempt", _evidence.write_attempts)),
        mock.patch.object(publish, "_commit_vault", record("vault", publish._commit_vault)),
        mock.patch.object(stage, "publish_unit", record("bind", stage.publish_unit)),
        mock.patch.object(
            LocalPointerStore, "replace_if", record("swap", LocalPointerStore.replace_if)
        ),
        mock.patch.object(
            _evidence, "publish_attempts", record("live_evidence", _evidence.publish_attempts)
        ),
        mock.patch.object(
            _evidence, "discard_attempts", record("cleanup", _evidence.discard_attempts)
        ),
        mock.patch.object(
            _delivery.DeliverySink, "_fill", record("ledger", _delivery.DeliverySink._fill)
        ),
        mock.patch.object(
            _flow,
            "_dispatch_run_notifications",
            record("notify", _flow._dispatch_run_notifications),
        ),
        mock.patch.object(_result, "build", record("document", _result.build)),
        mock.patch.object(_result, "_write_file", record("result_file", _result._write_file)),
    ]
    out = tmp_path / "ev.json"
    from contextlib import ExitStack

    with ExitStack() as stack:
        for patch in patches:
            stack.enter_context(patch)
        result = run(
            yml,
            "--vault",
            str(tmp_path / "v.db"),
            "--evidence-out",
            str(out),
            "--result",
            str(tmp_path / "r.json"),
        )
    assert result.exit_code == 0, result.output[-600:]
    order = [
        e
        for e in events
        if e
        in {
            "attempt",
            "vault",
            "bind",
            "swap",
            "live_evidence",
            "cleanup",
            "ledger",
            "notify",
            "document",
            "result_file",
        }
    ]
    assert order[:5] == ["attempt", "vault", "bind", "swap", "live_evidence"], order
    assert order.index("cleanup") > order.index("live_evidence")
    assert order.index("ledger") > order.index("swap")
    tail = order[order.index("notify") :]
    assert tail.index("document") < tail.index("result_file")
    (folder,) = runs(root)
    assert not (folder / "r.json").exists()  # the result document is never a run member
    assert litter(root) == []


# --- AT-44: the result file is written after delivery ---------------------------------------


@posix
def test_at44_a_result_file_that_cannot_be_written_does_not_undo_a_delivery(
    tmp_path: Path,
) -> None:
    root, yml = project(tmp_path)
    result = run(yml, "--result", str(tmp_path / "missing" / "r.json"))
    assert result.exit_code == 0, result.output[-600:]
    (folder,) = runs(root)
    assert latest(root) == folder.name
    assert body(result)["result_status"]["file"] == "failed"


# --- AT-48: Ctrl-C at the swap is settled under the lock -----------------------------------


@posix
@pytest.mark.parametrize("when", ["after_replace", "after_fsync"])
def test_at48_an_interrupt_at_the_swap_leaves_the_run_settled(tmp_path: Path, when: str) -> None:
    import os

    from decoy_engine.publication import LocalPointerStore

    root, yml = project(tmp_path, tables=1)
    out = tmp_path / "ev.json"
    out.write_text("old\n", encoding="utf-8")
    seen: list[str] = []
    real_reconcile = _delivery.DeliverySink._reconcile

    def spy(self, receipt, decision, ledger):
        seen.append(receipt.state)
        return real_reconcile(self, receipt, decision, ledger)

    if when == "after_fsync":
        real_swap = LocalPointerStore.replace_if

        def interrupted(self, expected, payload):
            real_swap(self, expected, payload)
            raise KeyboardInterrupt

        trap = mock.patch.object(LocalPointerStore, "replace_if", interrupted)
    else:
        real_replace = os.replace

        def replace_then_interrupt(src, dst, *a, **k):
            real_replace(src, dst, *a, **k)
            if Path(str(dst)).name == "LATEST":
                raise KeyboardInterrupt

        trap = mock.patch("os.replace", replace_then_interrupt)
    with trap, mock.patch.object(_delivery.DeliverySink, "_reconcile", spy):
        result = run(yml, "--evidence-out", str(out))
    assert result.exit_code != 0
    assert seen and seen[0] in {"delivered", "uncertain"}, seen
    assert len(seen) == 1  # reconcile ran once, under the held lock
    (folder,) = runs(root)
    assert latest(root) == folder.name
    assert litter(root) == []
    assert not list(tmp_path.glob(".*.attempt"))
    if seen[0] == "uncertain":
        assert out.read_text(encoding="utf-8") == "old\n"  # old evidence stays on an uncertain swap


# --- AT-59: a run that delivers nothing keeps its post-scan verdict beside the run folder -


def _withhold(*_args, **_kwargs) -> bool:
    return True


@posix
def test_at59_a_blocked_run_leaves_only_the_side_report(tmp_path: Path) -> None:
    from decoy.cli.run import _deliver

    root, yml = project(tmp_path)
    post_scan(yml)
    with mock.patch.object(_deliver, "_gate_withholds", _withhold):
        result = run(yml)
    assert result.exit_code == 4, result.output[-600:]
    pipeline = root / "out" / "orders"
    (empty,) = runs(root)
    assert list(empty.iterdir()) == []  # the run folder stays empty; the verdict is beside it
    assert latest(root) is None
    (report,) = pipeline.glob("*.post-scan.json")
    assert report.name == f"{empty.name}.post-scan.json"
    assert json.loads(report.read_text(encoding="utf-8"))
    assert litter(root) == []


@posix
def test_at59_an_explicit_integrity_out_gets_the_report_and_no_side_copy(tmp_path: Path) -> None:
    from decoy.cli.run import _deliver

    root, yml = project(tmp_path)
    post_scan(yml)
    explicit = tmp_path / "r.json"
    with mock.patch.object(_deliver, "_gate_withholds", _withhold):
        result = run(yml, "--integrity-out", str(explicit))
    assert result.exit_code == 4, result.output[-600:]
    assert json.loads(explicit.read_text(encoding="utf-8"))
    assert list((root / "out" / "orders").glob("*.post-scan.json")) == []


@posix
def test_at59_a_lost_swap_writes_no_second_copy(tmp_path: Path) -> None:
    """The decision was to deliver; the pointer moved. The bound folder, not a side file, holds it."""
    root, yml = project(tmp_path)
    post_scan(yml)
    real = _delivery.DeliverySink.deliver

    def other_run_wins(self, decision, ledger):
        (root / "out" / "orders" / "LATEST").write_text("99990101T000000000000Z-deadbeef\n")
        return real(self, decision, ledger)

    with mock.patch.object(_delivery.DeliverySink, "deliver", other_run_wins):
        result = run(yml)
    assert result.exit_code == 3, result.output[-600:]
    assert list((root / "out" / "orders").glob("*.post-scan.json")) == []


@posix
def test_at59_a_fault_in_the_side_report_is_one_warning_and_keeps_exit_4(
    tmp_path: Path,
) -> None:
    from decoy.cli.io import _integrity_report
    from decoy.cli.run import _deliver

    _root, yml = project(tmp_path)
    post_scan(yml)
    real = _integrity_report.write_run_report

    def fail_for_the_side_file(report, path, sha):
        if path.parent.name == "orders":
            return "disk says no"
        return real(report, path, sha)

    with (
        mock.patch.object(_deliver, "_gate_withholds", _withhold),
        mock.patch.object(_deliver, "write_run_report", fail_for_the_side_file),
    ):
        result = run(yml)
    assert result.exit_code == 4, result.output[-600:]
    codes = [w["code"] for w in body(result)["warnings"]]
    assert codes.count("post_scan_report_write_failed") == 1
    assert "disk says no" not in result.output


# --- AT-79: the quarantine file is a member only when the engine reports rows --------------


def _quarantined(rows: int):
    """`run_pipeline` that reports `rows` quarantined and leaves a file in its slot either way."""
    import decoy_engine

    real = decoy_engine.run_pipeline

    def wrapped(config, *args, **kwargs):
        result = real(config, *args, **kwargs)
        slot = kwargs.get("quarantine_path")
        if slot:
            Path(slot).write_bytes(b'{"row": 1}\n')
        result.quality_metrics["quarantine"] = {"total_quarantined": rows}
        return result

    return wrapped


def _quarantine(yml: Path) -> None:
    import yaml

    cfg = yaml.safe_load(yml.read_text(encoding="utf-8"))
    cfg["quarantine"] = {"enabled": True, "output_path": "q.jsonl", "triggers": ["format_error"]}
    yml.write_text(yaml.safe_dump(cfg), encoding="utf-8")


@posix
@pytest.mark.parametrize("rows", [0, 3])
def test_at79_the_engine_report_decides_not_the_slot_file(tmp_path: Path, rows: int) -> None:
    root, yml = project(tmp_path)
    _quarantine(yml)
    with mock.patch("decoy_engine.run_pipeline", _quarantined(rows)):
        result = run(yml)
    assert result.exit_code == 0, result.output[-800:]
    (folder,) = runs(root)
    assert (folder / "q.jsonl").exists() is (rows > 0)


# --- AT-30, AT-45: a failed attempt-evidence write delivers nothing ------------------------


@posix
def test_at30_at45_a_failed_attempt_write_delivers_nothing_and_keeps_the_old_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    from decoy._atomic import AtomicWriteError

    root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    evidence, vault = tmp_path / "e.json", tmp_path / "v.db"
    evidence.write_text("old evidence\n", encoding="utf-8")

    def refuse(path, data):
        raise AtomicWriteError("ATOMIC_WRITE_FAILED", "x")

    with mock.patch("decoy.cli.run._evidence._put", refuse):
        result = run(yml, "--vault", str(vault), "--evidence-out", str(evidence))
    assert result.exit_code == 3, result.output[-600:]
    assert document(result)["delivery"]["outcome"] == "nothing"
    assert evidence.read_text(encoding="utf-8") == "old evidence\n"
    assert not vault.exists()  # the vault is published inside the bind, which never ran
    assert runs(root) == []
    assert latest(root) is None
    assert litter(root) == []
    assert not list(tmp_path.glob(".*.attempt"))
