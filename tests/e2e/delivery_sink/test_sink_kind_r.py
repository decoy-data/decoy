"""C2a-1: the plain `decoy run` delivers through the sink, strict in a project.

AT-14 (both tables visible), AT-15 (a failure leaves the previous run current), AT-19 (a lost
compare-and-swap), AT-36c (receipt projection), AT-50 (cleanup faults), AT-77 (link probe),
AT-78 (vault fact), AT-83 (error after delivery).
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path
from unittest import mock

import pytest

from decoy._atomic import AtomicWriteError
from decoy.cli.io import _delivery
from decoy.cli.run._context import EvidenceWriteRefusal
from tests.e2e.delivery_sink._support import (
    document,
    latest,
    litter,
    project,
    run,
    runs,
)
from tests.e2e.delivery_sink._support import (
    vaulted as _vaulted,
)

posix = pytest.mark.skipif(sys.platform == "win32", reason="the strict stage is POSIX only")
MOVED_ID = "99990101T000000000000Z-deadbeef"


@posix
def test_at14_both_tables_become_current_together(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    result = run(yml)
    assert result.exit_code == 0, result.output
    (folder,) = runs(root)
    assert latest(root) == folder.name
    assert sorted(p.name for p in folder.glob("*.csv")) == ["t1.csv", "t2.csv"]
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert (root / "out" / "orders" / "current").resolve() == folder.resolve()
    doc = document(result)
    assert doc["delivery"] == {"mode": "strict", "outcome": "delivered", "vault": "not_used"}
    assert litter(root) == [] or litter(root) == [".LATEST.decoy-lock"]


@posix
def test_at15_a_failed_second_table_leaves_the_previous_run_current(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    assert run(yml).exit_code == 0
    (first,) = runs(root)
    real = _delivery.write_target
    calls: list[str] = []

    def fail_second(name, entry, table, path, published):
        calls.append(str(name))
        if len(calls) == 2:
            raise OSError("boom")
        return real(name, entry, table, path, published)

    with mock.patch.object(_delivery, "write_target", fail_second):
        result = run(yml)
    assert result.exit_code == 3, result.output
    assert latest(root) == first.name
    assert runs(root) == [first]
    assert sorted(p.name for p in first.glob("*.csv")) == ["t1.csv", "t2.csv"]
    doc = document(result)
    assert doc["delivery"]["outcome"] == "nothing"


@posix
def test_at19_a_lost_swap_delivers_nothing_and_exits_3(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    real = _delivery.DeliverySink.deliver

    def other_run_wins(self, decision, ledger):
        (root / "out" / "orders" / "LATEST").write_text(MOVED_ID + "\n", encoding="utf-8")
        return real(self, decision, ledger)

    with mock.patch.object(_delivery.DeliverySink, "deliver", other_run_wins):
        result = run(yml)
    assert result.exit_code == 3, result.output
    assert "delivery_pointer_moved" in result.output
    assert latest(root) == MOVED_ID
    doc = document(result)
    assert doc["delivery"]["outcome"] == "nothing"
    assert {t["delivery"]["state"] for t in doc["tables"]} == {"none"}
    assert all(t["delivery"]["output"] is None for t in doc["tables"])


@posix
def test_at36c_a_receipt_of_nothing_shows_no_path(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    real = _delivery.DeliverySink.deliver

    def other_run_wins(self, decision, ledger):
        (root / "out" / "orders" / "LATEST").write_text(MOVED_ID + "\n", encoding="utf-8")
        return real(self, decision, ledger)

    with mock.patch.object(_delivery.DeliverySink, "deliver", other_run_wins):
        result = run(yml)
    assert "outputs" not in result.output.split('"result"')[0]


@posix
@pytest.mark.parametrize(
    "fault",
    [AtomicWriteError("ATOMIC_WRITE_FAILED", "x"), OSError("x"), EvidenceWriteRefusal("x")],
    ids=["atomic_write_error", "os_error", "evidence_write_refusal"],
)
def test_at50_a_fault_in_the_cleanup_never_unmakes_a_delivery(tmp_path: Path, fault) -> None:
    root, yml = project(tmp_path)
    with mock.patch("decoy.cli.run._evidence.publish_attempts", side_effect=fault):
        result = run(yml)
    assert result.exit_code == 0, result.output
    (folder,) = runs(root)
    assert latest(root) == folder.name
    assert (root / "out" / "orders" / "current").resolve() == folder.resolve()
    codes = [w["code"] for w in __import__("json").loads(result.output)["warnings"]]
    assert codes.count("delivery_cleanup_incomplete") == 1
    assert document(result)["delivery"]["outcome"] == "delivered"


@posix
def test_at50_a_failed_current_link_keeps_latest_and_warns_once(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    with mock.patch("decoy.cli.io._pointer.link_current", side_effect=OSError("x")):
        result = run(yml)
    assert result.exit_code == 0, result.output
    (folder,) = runs(root)
    assert latest(root) == folder.name
    codes = [w["code"] for w in __import__("json").loads(result.output)["warnings"]]
    assert codes.count("delivery_cleanup_incomplete") == 1


@posix
def test_at50_a_fault_in_the_abort_callback_keeps_the_exit(tmp_path: Path) -> None:
    root, yml = project(tmp_path)

    def fail_open(self, decision, ledger):
        raise RuntimeError("before the receipt")

    with (
        mock.patch.object(_delivery.DeliverySink, "deliver", fail_open),
        mock.patch.object(
            _delivery._Strict, "abort", side_effect=AtomicWriteError("ATOMIC_WRITE_FAILED", "x")
        ),
    ):
        result = run(yml)
    assert result.exit_code == 3, result.output
    assert "Traceback" not in result.output
    assert latest(root) is None


@posix
def test_at50_a_keyboard_interrupt_in_the_cleanup_still_propagates(tmp_path: Path) -> None:
    _root, yml = project(tmp_path)
    with mock.patch("decoy.cli.run._evidence.publish_attempts", side_effect=KeyboardInterrupt):
        result = run(yml)
    assert result.exit_code != 0


@posix
def test_at77_a_target_that_cannot_link_exits_3_before_any_writer(tmp_path: Path) -> None:
    from decoy_engine.fileaccess import LinkUnsupported

    root, yml = project(tmp_path)
    with (
        mock.patch("decoy_engine.publication._stage.probe_claim", side_effect=LinkUnsupported(95)),
        mock.patch.object(_delivery, "write_target") as writer,
    ):
        result = run(yml)
    assert result.exit_code == 3, result.output
    writer.assert_not_called()
    assert runs(root) == []
    assert latest(root) is None


@posix
def test_at78_a_delivered_vault_run_reports_the_vault_committed(
    tmp_path: Path, monkeypatch
) -> None:
    _root, yml = project(tmp_path, tables=1)
    _vaulted(yml, monkeypatch)
    vault = tmp_path / "v.db"
    result = run(yml, "--vault", str(vault))
    assert result.exit_code == 0, result.output[-800:]
    assert vault.exists()
    assert document(result)["delivery"] == {
        "mode": "strict",
        "outcome": "delivered",
        "vault": "committed",
    }


@posix
def test_at78_a_lost_swap_binds_nothing_so_no_vault_is_published(
    tmp_path: Path, monkeypatch
) -> None:
    """The compare-and-swap is judged before the bind, and rule V runs inside the bind."""
    root, yml = project(tmp_path, tables=1)
    _vaulted(yml, monkeypatch)
    vault = tmp_path / "v.db"
    real = _delivery.DeliverySink.deliver

    def other_run_wins(self, decision, ledger):
        (root / "out" / "orders" / "LATEST").write_text(MOVED_ID + "\n", encoding="utf-8")
        return real(self, decision, ledger)

    with mock.patch.object(_delivery.DeliverySink, "deliver", other_run_wins):
        result = run(yml, "--vault", str(vault))
    assert result.exit_code == 3, result.output
    assert not vault.exists()
    doc = document(result)
    assert doc["delivery"]["outcome"] == "nothing"
    assert doc["delivery"]["vault"] == "not_used"


@posix
def test_at78_a_vault_publish_that_fails_is_reported_failed(tmp_path: Path, monkeypatch) -> None:
    from decoy_engine import VaultError, reasons

    _root, yml = project(tmp_path, tables=1)
    _vaulted(yml, monkeypatch)
    fault = VaultError(code=reasons.runtime.VAULT_COMMIT_FAILED, message="x")
    with mock.patch("decoy_engine.publication._publish._commit_vault", side_effect=fault):
        result = run(yml, "--vault", str(tmp_path / "v.db"))
    assert result.exit_code == 3, result.output
    assert document(result)["delivery"]["vault"] == "failed"


@posix
def test_at83_an_error_after_delivery_keeps_the_run_delivered(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    real = _delivery.DeliverySink.deliver

    def deliver_then_fail(self, decision, ledger):
        real(self, decision, ledger)
        raise RuntimeError("scope exit")

    with mock.patch.object(_delivery.DeliverySink, "deliver", deliver_then_fail):
        result = run(yml)
    assert result.exit_code == 0, result.output
    (folder,) = runs(root)
    assert latest(root) == folder.name
    codes = [w["code"] for w in __import__("json").loads(result.output)["warnings"]]
    assert codes.count("delivery_cleanup_incomplete") == 1


@posix
def test_at83_control_a_failure_before_delivery_keeps_its_exit(tmp_path: Path) -> None:
    root, yml = project(tmp_path)

    def fail_open(self, decision, ledger):
        raise RuntimeError("before the receipt")

    with mock.patch.object(_delivery.DeliverySink, "deliver", fail_open):
        result = run(yml)
    assert result.exit_code == 3
    assert latest(root) is None
    assert runs(root) == []


@posix
def test_at86_every_name_in_the_pipeline_folder_mid_delivery_is_a_known_shape(
    tmp_path: Path,
) -> None:
    """Listed from inside `before_visible`, while the stages are open: the stage siblings the
    engine makes are gone by the time a run ends, so only this view can see them."""
    root, yml = project(tmp_path)
    seen: list[str] = []

    def list_folder(ctx, staged):
        seen.extend(p.name for p in (root / "out" / "orders").iterdir())

    with mock.patch("decoy.cli.run._evidence.write_attempts", list_folder):
        assert run(yml).exit_code == 0
    from decoy.cli.io._run_outputs import in_flight_name

    unknown = [name for name in seen if not in_flight_name(name)]
    assert not unknown, sorted(unknown)
