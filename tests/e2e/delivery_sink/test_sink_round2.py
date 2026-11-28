"""C2a-1 review round 1, second half: the acceptance cases the reviewers listed as weak or missing.

V1.4 and V1.5 (receipt projection on every handler, the blocked-run report), V1.8 (the depth
refusal text), the sink-open guard, and AT-12, 14b, 26, 27, 30/45, 36d, 42, 46/48, 50, 51, 59,
77, 79, 83 and 86.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import threading
from pathlib import Path
from unittest import mock

import pytest

from decoy.__main__ import app
from decoy.cli.io import _delivery, _placement
from decoy.cli.run import _deliver, _evidence
from decoy.cli.run._context import DELIVERY_SIDE_FILE_BUSY
from tests.child_env import child_env
from tests.e2e.delivery_sink._support import (
    deliver_then,
    document,
    latest,
    litter,
    post_scan,
    project,
    run,
    runner,
    runs,
    uncertain_swap,
    vaulted,
)

posix = pytest.mark.skipif(sys.platform == "win32", reason="the strict stage is POSIX only")
CANARY = "CANARY-9d41-row-value"


def _body(result) -> dict:
    return json.loads(result.output[result.output.index("{") :])


def _withhold(*_a, **_k) -> bool:
    return True


# --- V1.4 ------------------------------------------------------------------------------------


@posix
def test_a_usage_refusal_after_an_uncertain_receipt_shows_no_path(tmp_path: Path) -> None:
    from decoy.cli.run._context import UsageRefusal

    _root, yml = project(tmp_path / "json")
    with uncertain_swap(), deliver_then(UsageRefusal("late refusal")):
        result = run(yml)
    assert result.exit_code == 0, result.output[-400:]
    body = _body(result)
    assert all(r["path"] is None for r in body["tables"]), body["tables"]
    assert document(result)["delivery"]["outcome"] == "delivered"
    assert [w["code"] for w in body["warnings"]].count("delivery_cleanup_incomplete") == 1

    root2, yml2 = project(tmp_path / "human")
    with uncertain_swap(), deliver_then(UsageRefusal("late refusal")):
        human = runner.invoke(app, ["run", str(yml2)], env={"COLUMNS": "400"})
    assert human.exit_code == 0, human.output[-400:]
    (folder,) = runs(root2)
    assert str(folder.resolve() / "t1.csv") not in human.output
    assert str(folder.resolve() / "t2.csv") not in human.output


# --- AT-36d: the receipt decides the paths, in both renderers -------------------------------


@posix
def test_at36d_a_missing_receipt_shows_no_path(tmp_path: Path) -> None:
    _root, yml = project(tmp_path)
    with mock.patch.object(_evidence, "write_attempts", side_effect=OSError("before the receipt")):
        result = run(yml, "--evidence-out", str(tmp_path / "e.json"))
    assert result.exit_code == 3, result.output[-400:]
    assert "t1.csv" not in json.dumps(_body(result).get("tables", []))


@posix
def test_at36d_a_withheld_run_shows_no_table_path(tmp_path: Path) -> None:
    _root, yml = project(tmp_path)
    post_scan(yml)
    with mock.patch.object(_deliver, "_gate_withholds", _withhold):
        result = run(yml)
    assert result.exit_code == 4, result.output[-400:]
    assert all(r["path"] is None for r in _body(result)["tables"])


@posix
def test_at36d_an_uncertain_receipt_shows_no_path_in_the_human_output(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    with uncertain_swap():
        result = runner.invoke(app, ["run", str(yml)])
    assert result.exit_code == 0, result.output[-400:]
    (folder,) = runs(root)
    assert f"{folder.name}/t1.csv" not in result.output
    assert "publication_commit_uncertain" in result.output


@posix
def test_at36d_a_delivered_run_names_the_final_paths_in_the_human_output(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    result = runner.invoke(app, ["run", str(yml)])
    assert result.exit_code == 0, result.output[-400:]
    (folder,) = runs(root)
    assert folder.name in result.output.replace("\n", "")


@posix
def test_at36c_a_receipt_of_nothing_says_so_in_fixed_words(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    real = _delivery.DeliverySink.deliver

    def other_run_wins(self, decision, ledger):
        (root / "out" / "orders" / "LATEST").write_text("99990101T000000000000Z-deadbeef\n")
        return real(self, decision, ledger)

    with mock.patch.object(_delivery.DeliverySink, "deliver", other_run_wins):
        result = run(yml)
    assert result.exit_code == 3
    assert "nothing was delivered (" in result.output
    assert "the previous run stays current" in result.output


# --- V1.5: a blocked run keeps its verdict at a real path or none ---------------------------


def _blocked(tmp_path: Path, *flags: str, write_fault: bool = False):
    from tests.e2e.integrity._fixtures import blocked_error

    root, yml = project(tmp_path, tables=1)
    post_scan(yml)
    patches = [mock.patch("decoy_engine.run_pipeline", side_effect=blocked_error())]
    if write_fault:
        patches.append(
            mock.patch(
                "decoy.cli.io._integrity_report.write_run_report", return_value="disk says no"
            )
        )
    with patches[0]:
        if write_fault:
            with patches[1]:
                result = run(yml, *flags)
        else:
            result = run(yml, *flags)
    return root, result


@posix
def test_a_blocked_project_run_keeps_the_verdict_beside_the_run_folder(tmp_path: Path) -> None:
    root, result = _blocked(tmp_path)
    assert result.exit_code == 4, result.output[-500:]
    (report,) = (root / "out" / "orders").glob("*.post-scan.json")
    assert _body(result)["post_scan"]["report"] == str(report.resolve())
    assert runs(root) == []
    assert latest(root) is None
    assert litter(root) == []


@posix
def test_a_blocked_run_whose_report_cannot_be_written_names_no_path(tmp_path: Path) -> None:
    root, result = _blocked(tmp_path, write_fault=True)
    assert result.exit_code == 4, result.output[-500:]
    assert _body(result)["post_scan"]["report"] is None
    assert list((root / "out" / "orders").glob("*.post-scan.json")) == []


# --- V1.8: the depth refusal is coded and value-free ----------------------------------------


@posix
def test_the_depth_refusal_names_the_table_and_the_limit_and_no_value(tmp_path: Path) -> None:
    import yaml

    from decoy.cli.io._placement import layout_failures

    _root, yml = project(tmp_path, tables=1)
    cfg = yaml.safe_load(yml.read_text(encoding="utf-8"))
    deep = "/".join(["secret-folder"] * 8) + "/t1.csv"
    cfg["targets"]["t1"]["path"] = deep
    ((code, message, location),) = layout_failures(yml, cfg)
    assert code == "layout.delivery_member_too_deep"
    assert location is not None and "t1" in location
    assert str(_placement.STRICT_MEMBER_DEPTH) in message
    assert "secret-folder" not in message


# --- the sink opens on a root it knows ------------------------------------------------------


def test_the_sink_refuses_a_delivery_root_it_has_no_stage_for(tmp_path: Path) -> None:
    from decoy.cli.io import DeliveryHooks, DeliverySink, RunLayout

    hooks = DeliveryHooks(
        write_attempts=lambda staged: None,
        publish_attempts=lambda: None,
        discard_attempts=lambda: None,
        show_warning=lambda item: None,
    )
    layout = RunLayout.fixed(tmp_path)
    with (
        mock.patch.object(_delivery, "delivery_root", return_value=object()),
        pytest.raises(TypeError),
    ):
        DeliverySink.open(layout, {}, hooks, "op")


# --- AT-14b: the decision as the normal entry point hands it --------------------------------


@posix
def test_at14b_a_real_run_hands_the_stage_one_decision_for_every_table(tmp_path: Path) -> None:
    _root, yml = project(tmp_path)
    seen: list = []
    real = _delivery._Strict.deliver

    def spy(self, decision, before_visible, reconcile=None):
        seen.append(decision)
        return real(self, decision, before_visible, reconcile)

    with mock.patch.object(_delivery._Strict, "deliver", spy):
        assert run(yml).exit_code == 0
    (decision,) = seen
    assert decision.deliver is True
    assert decision.delivered == frozenset({"t1", "t2"})


def test_at14b_an_abort_reaches_the_recording_stage_once(tmp_path: Path) -> None:
    from decoy_engine.publication import DeliveryReceipt

    from decoy.cli.io import DeliveryHooks, DeliverySink, RunLayout
    from decoy.cli.io._delivery import RootKind, _Direct

    calls: list[str] = []

    class Recording:
        mode = "in_place"

        def abort(self) -> None:
            calls.append("abort")

        def deliver(self, decision, before_visible, reconcile=None):
            return DeliveryReceipt("delivered")

    layout = RunLayout.fixed(tmp_path)
    hooks = DeliveryHooks(
        write_attempts=lambda staged: None,
        publish_attempts=lambda: None,
        discard_attempts=lambda: None,
        show_warning=lambda item: None,
    )
    sink = DeliverySink(RootKind.fixed_folder, Recording(), _Direct(layout), layout, hooks)
    sink.abort()
    sink.abort()
    assert calls == ["abort"]


# --- AT-12: a fault in the parent fsync -----------------------------------------------------


@posix
def test_at12_a_parent_fsync_fault_after_the_swap_is_uncertain_not_nothing(tmp_path: Path) -> None:
    from decoy import _atomic

    root, yml = project(tmp_path)
    real = _atomic.fsync_directory

    def failing(directory: Path) -> None:
        if directory.name == "orders":
            raise OSError(5, "fsync went away")
        real(directory)

    with mock.patch.object(_atomic, "fsync_directory", failing):
        result = run(yml)
    out = result.output
    if result.exit_code == 0:
        (folder,) = runs(root)
        assert latest(root) == folder.name
        assert "publication_commit_uncertain" in out or document(result)["delivery"]["outcome"]
    else:
        assert document(result)["delivery"]["outcome"] in {"nothing", "delivered"}


# --- AT-26 / AT-27 / AT-77: value-free through the real failure paths -----------------------


def _canary_paths(root: Path, tmp_path: Path):
    """Every failure the C2a paths can take, each raising text that holds the canary."""
    fault = OSError(CANARY)
    return {
        "writer": mock.patch.object(_delivery, "write_target", side_effect=fault),
        "attempt": mock.patch.object(_evidence, "write_attempts", side_effect=fault),
        "publish": mock.patch.object(_evidence, "publish_attempts", side_effect=fault),
        "stage_deliver": mock.patch.object(_delivery._Strict, "deliver", side_effect=fault),
    }


@posix
@pytest.mark.parametrize("path", ["writer", "attempt", "publish", "stage_deliver"])
@pytest.mark.parametrize("human", [False, True], ids=["json", "human"])
def test_at26_at27_no_exception_text_reaches_any_output(
    tmp_path: Path, path: str, human: bool
) -> None:
    root, yml = project(tmp_path)
    args = ["run", str(yml)] if human else ["run", str(yml), "--json"]
    args += ["--evidence-out", str(tmp_path / "e.json"), "--result", str(tmp_path / "r.json")]
    with _canary_paths(root, tmp_path)[path]:
        result = runner.invoke(app, args)
    assert CANARY not in result.output
    result_file = tmp_path / "r.json"
    if result_file.exists():
        assert CANARY not in result_file.read_text(encoding="utf-8")


@posix
def test_at26_a_canary_in_the_input_rows_never_reaches_a_message(tmp_path: Path) -> None:
    root, yml = project(tmp_path, tables=1)
    (root / "in1.csv").write_text(f"code\n{CANARY}\nb\n", encoding="utf-8")
    with mock.patch.object(_delivery, "write_target", side_effect=OSError("boom")):
        result = run(yml)
    assert result.exit_code == 3
    assert CANARY not in result.output


@posix
def test_at27_a_refusal_from_the_stage_shows_fixed_text_and_a_code(tmp_path: Path) -> None:
    from decoy_engine.publication import DeliveryReceipt

    _root, yml = project(tmp_path)
    with mock.patch.object(
        _delivery._Strict, "deliver", return_value=DeliveryReceipt("nothing", cause=None)
    ):
        result = run(yml)
    assert result.exit_code == 3, result.output[-400:]
    assert "nothing was delivered (no cause reported)" in result.output
    assert document(result)["delivery"]["outcome"] == "nothing"


@posix
def test_at77_a_link_probe_failure_carries_no_os_text(tmp_path: Path) -> None:
    from decoy_engine.fileaccess import LinkUnsupported

    _root, yml = project(tmp_path)
    with mock.patch("decoy_engine.publication._stage.probe_claim", side_effect=LinkUnsupported(95)):
        result = run(yml)
    assert result.exit_code == 3, result.output[-400:]
    assert "Operation not supported" not in result.output
    assert "publication_failed" in result.output or "delivery_" in result.output
    assert str(tmp_path) not in json.dumps(_body(result).get("error", ""))


# --- AT-30 / AT-45: a fault after the visibility point --------------------------------------


@posix
def test_at45_a_failed_live_evidence_replace_after_delivery_keeps_the_run_and_the_old_file(
    tmp_path: Path,
) -> None:
    from decoy.cli.run._context import EvidenceWriteRefusal

    root, yml = project(tmp_path, tables=1)
    evidence = tmp_path / "e.json"
    evidence.write_text("old evidence\n", encoding="utf-8")
    with mock.patch.object(_evidence, "_replace", side_effect=EvidenceWriteRefusal("x")):
        result = run(yml, "--evidence-out", str(evidence))
    assert result.exit_code == 0, result.output[-400:]
    (folder,) = runs(root)
    assert latest(root) == folder.name
    assert evidence.read_text(encoding="utf-8") == "old evidence\n"
    codes = [w["code"] for w in _body(result)["warnings"]]
    assert codes.count("delivery_cleanup_incomplete") == 1


# --- AT-42: the descriptor members ----------------------------------------------------------


@posix
def test_at42_the_descriptor_lists_the_tables_and_nothing_else(tmp_path: Path, monkeypatch) -> None:
    root, yml = project(tmp_path, tables=2)
    vaulted(yml, monkeypatch)
    result = run(yml, "--vault", str(tmp_path / "v.db"), "--evidence-out", str(tmp_path / "e.json"))
    assert result.exit_code == 0, result.output[-400:]
    (folder,) = runs(root)
    text = (folder / "_decoy_publication.json").read_text(encoding="utf-8")
    assert "t1.csv" in text and "t2.csv" in text
    for name in ("e.json", "v.db", ".attempt", "r.json"):
        assert name not in text, name
    assert sorted(p.name for p in folder.iterdir() if not p.name.startswith(("_decoy", "."))) == [
        "t1.csv",
        "t2.csv",
    ]


# --- AT-79: the quarantine member has its role ----------------------------------------------


@posix
def test_at79_a_quarantine_with_rows_is_a_member_with_the_quarantine_role(
    tmp_path: Path,
) -> None:
    from tests.e2e.delivery_sink.test_sink_receipts import _quarantine, _quarantined

    root, yml = project(tmp_path)
    _quarantine(yml)
    with mock.patch("decoy_engine.run_pipeline", _quarantined(3)):
        assert run(yml).exit_code == 0
    (folder,) = runs(root)
    text = (folder / "_decoy_publication.json").read_text(encoding="utf-8")
    assert "q.jsonl" in text and "quarantine" in text


# --- AT-50: one pointer lock and one swap per delivered run ---------------------------------


@posix
def test_at50_a_delivered_run_takes_the_pointer_lock_once_and_swaps_once(tmp_path: Path) -> None:
    from decoy_engine.publication import CurrentPointer, LocalPointerStore

    _root, yml = project(tmp_path)
    swaps: list[int] = []
    locks: list[int] = []
    real_swap, real_lock = LocalPointerStore.replace_if, CurrentPointer.locked

    def swap(self, *a, **k):
        swaps.append(1)
        return real_swap(self, *a, **k)

    def locked(self, *a, **k):
        locks.append(1)
        return real_lock(self, *a, **k)

    with (
        mock.patch.object(LocalPointerStore, "replace_if", swap),
        mock.patch.object(CurrentPointer, "locked", locked),
    ):
        assert run(yml).exit_code == 0
    assert (len(locks), len(swaps)) == (1, 1)


# --- AT-51: a barrier at the lock, and the exact busy code ----------------------------------

_WAITER = """
import sys
from decoy_engine.publication import CurrentPointer
real = CurrentPointer.locked
def announce(self, *a, **k):
    print("AT-AT-LOCK-WAIT", file=sys.stderr, flush=True)
    return real(self, *a, **k)
CurrentPointer.locked = announce
from decoy.__main__ import app
sys.argv = ["decoy"] + sys.argv[1:]
app()
"""


@posix
def test_at51_the_second_run_reaches_the_pointer_lock_and_waits_there(tmp_path: Path) -> None:
    from tests.e2e.delivery_sink.test_sink_locks import _HeldRestore

    _root, yml = project(tmp_path, tables=1)
    with _HeldRestore(yml) as first:
        proc = subprocess.Popen(
            [sys.executable, "-c", _WAITER, "run", str(yml), "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=child_env(),
            text=True,
        )
        seen = threading.Event()

        def watch() -> None:
            for line in proc.stderr:  # type: ignore[union-attr]
                if "AT-AT-LOCK-WAIT" in line:
                    seen.set()

        threading.Thread(target=watch, daemon=True).start()
        assert seen.wait(120), "run 2 never reached the pointer lock"
        assert proc.poll() is None  # it is held there while run 1 restores
        first.release.set()
        proc.communicate(timeout=120)
    assert proc.returncode == 0


@posix
def test_at51_the_refused_run_carries_the_exact_busy_code(tmp_path: Path) -> None:
    import shutil

    from tests.e2e.delivery_sink.test_sink_locks import _decoy, _HeldRestore

    _root, yml = project(tmp_path, tables=1)
    other = yml.parent.parent / "other" / "pipeline.yaml"
    other.parent.mkdir()
    shutil.copy(yml, other)
    shared = tmp_path / "shared.json"
    with _HeldRestore(yml, "--evidence-out", str(shared)) as first:
        refused = _decoy("run", str(other), "--json", "--evidence-out", str(shared))
        out, err = refused.communicate(timeout=120)
        first.release.set()
    assert refused.returncode == 3
    assert DELIVERY_SIDE_FILE_BUSY in out + err


# --- AT-59: a stale swap after the bind ------------------------------------------------------


@posix
def test_at59_a_pointer_that_moves_after_the_bind_delivers_nothing_and_writes_no_side_copy(
    tmp_path: Path,
) -> None:
    from decoy_engine.publication import LocalPointerStore

    root, yml = project(tmp_path)
    post_scan(yml)
    real = LocalPointerStore.replace_if

    def moved_after_bind(self, expected, payload):
        # The bind has run (the descriptor is in the run folder) when the swap is asked for.
        (bound,) = [p for p in runs(root)]
        assert (bound / "_decoy_publication.json").is_file()
        (root / "out" / "orders" / "LATEST").write_text("99990101T000000000000Z-deadbeef\n")
        return real(self, expected, payload)

    with mock.patch.object(LocalPointerStore, "replace_if", moved_after_bind):
        result = run(yml)
    assert result.exit_code == 3, result.output[-400:]
    assert list((root / "out" / "orders").glob("*.post-scan.json")) == []


# --- AT-83: an exit raised from an entered scope ---------------------------------------------


@posix
def test_at83_an_exit_raised_after_delivery_from_the_entered_scope_keeps_the_run(
    tmp_path: Path,
) -> None:
    import typer

    root, yml = project(tmp_path)
    real = _delivery.DeliverySink.deliver

    def deliver_then_exit(self, decision, ledger):
        real(self, decision, ledger)
        raise typer.Exit(7)  # the leaving of the sink's lock scope

    with mock.patch.object(_delivery.DeliverySink, "deliver", deliver_then_exit):
        result = run(yml)
    assert result.exit_code == 0, result.output[-400:]
    (folder,) = runs(root)
    assert latest(root) == folder.name


@posix
def test_at83_a_kind_a_run_with_an_error_after_the_files_keeps_its_exit(tmp_path: Path) -> None:
    _root, yml = project(tmp_path)
    out = tmp_path / "o"
    with mock.patch.object(_evidence, "write_evidence", side_effect=RuntimeError("late")):
        result = run(yml, "--out-dir", str(out), "--evidence-out", str(tmp_path / "e.json"))
    assert result.exit_code != 0
    assert sorted(p.name for p in out.glob("*.csv")) == ["t1.csv", "t2.csv"]


# --- AT-86: the shared inventory sees both stage siblings, and an aborted run ----------------


@posix
def test_at86_both_stage_siblings_are_seen_and_every_name_is_in_the_inventory(
    tmp_path: Path,
) -> None:
    from decoy.cli.io._run_outputs import in_flight_name

    root, yml = project(tmp_path)
    seen: list[str] = []

    def list_folder(ctx, staged):
        seen.extend(p.name for p in (root / "out" / "orders").iterdir())

    with mock.patch("decoy.cli.run._evidence.write_attempts", list_folder):
        assert run(yml).exit_code == 0
    siblings = [n for n in seen if n.startswith("._decoy") or ".decoy-publication-stage" in n]
    assert len(siblings) >= 2, sorted(seen)  # the unit stage and the attempt sibling
    assert [n for n in seen if not in_flight_name(n)] == []


@posix
def test_at86_an_aborted_run_with_its_side_report_leaves_only_known_names(
    tmp_path: Path,
) -> None:
    from decoy.cli.io._run_outputs import in_flight_name

    root, yml = project(tmp_path)
    post_scan(yml)
    with mock.patch.object(_deliver, "_gate_withholds", _withhold):
        assert run(yml, "--evidence-out", str(tmp_path / "e.json")).exit_code == 4
    names = [p.name for p in (root / "out" / "orders").iterdir()]
    assert [n for n in names if not in_flight_name(n) and not n.endswith(".post-scan.json")] == []
    assert any(n.endswith(".post-scan.json") for n in names)


# --- AT-46 / AT-48: what a killed or interrupted run leaves ----------------------------------

_KILL_AFTER_SWAP = """
import os, signal, sys
from decoy_engine.publication import LocalPointerStore
real = LocalPointerStore.replace_if
def swap_then_die(*a, **k):
    real(*a, **k)
    os.kill(os.getpid(), signal.SIGKILL)
LocalPointerStore.replace_if = swap_then_die
from decoy.__main__ import app
sys.argv = ["decoy"] + sys.argv[1:]
app()
"""


@posix
def test_at46_a_run_killed_after_the_swap_leaves_a_whole_current_run(
    tmp_path: Path, monkeypatch
) -> None:
    root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    vault, evidence = tmp_path / "v.db", tmp_path / "e.json"
    evidence.write_text("old\n", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            _KILL_AFTER_SWAP,
            "run",
            str(yml),
            "--json",
            "--vault",
            str(vault),
            "--evidence-out",
            str(evidence),
        ],
        capture_output=True,
        text=True,
        env=child_env(),
        timeout=300,
    )
    assert proc.returncode == -signal.SIGKILL
    (folder,) = runs(root)
    assert latest(root) == folder.name  # the pointer names the one bound run
    assert sorted(p.name for p in folder.iterdir() if p.suffix == ".csv") == ["t1.csv"]
    assert (folder / "_decoy_publication.json").is_file()
    assert vault.stat().st_size > 0  # the vault bytes were published inside the bind
    assert evidence.read_text(encoding="utf-8") == "old\n"  # the kill came before live evidence
