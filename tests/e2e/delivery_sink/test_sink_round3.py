"""C2a-1 review round 1, last gaps: AT-48 (what an interrupt leaves), AT-83 (errors after
delivery, the tail and the spies), the UsageRefusal handler on the strict route, AT-42 order."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from decoy.cli.io import _delivery
from decoy.cli.run import _errors, _evidence, _render
from decoy.cli.run._context import UsageRefusal
from tests.e2e.delivery_sink._support import latest, litter, project, run, runs, vaulted

posix = pytest.mark.skipif(sys.platform == "win32", reason="the strict stage is POSIX only")


def _body(result) -> dict:
    return json.loads(result.output[result.output.index("{") :])


# --- AT-48: an interrupt right after the swap -----------------------------------------------


@posix
def test_at48_an_interrupt_after_the_swap_leaves_the_bound_run_the_vault_and_new_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    from decoy_engine.publication import LocalPointerStore

    root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    vault, evidence = tmp_path / "v.db", tmp_path / "e.json"
    evidence.write_text('{"old": true}\n', encoding="utf-8")
    real = LocalPointerStore.replace_if

    def swap_then_interrupt(self, expected, payload):
        real(self, expected, payload)
        raise KeyboardInterrupt

    with mock.patch.object(LocalPointerStore, "replace_if", swap_then_interrupt):
        result = run(yml, "--vault", str(vault), "--evidence-out", str(evidence))
    # Ctrl-C ends the run through the interrupt path: the exit code is not a success.
    assert result.exit_code == INTERRUPT_EXIT, (result.exit_code, result.output[-300:])
    (folder,) = runs(root)
    assert latest(root) == folder.name
    assert (root / "out" / "orders" / "current").resolve() == folder.resolve()
    assert sorted(p.name for p in folder.glob("*.csv")) == ["t1.csv"]
    assert vault.stat().st_size > 0
    # An interrupt at the swap makes the receipt uncertain: the old evidence stays (rule 5.5).
    assert json.loads(evidence.read_text(encoding="utf-8")) == {"old": True}
    assert litter(root) == []
    assert [p for p in tmp_path.iterdir() if p.name.endswith(".attempt")] == []


INTERRUPT_EXIT = 130


@posix
def test_at48_an_interrupt_after_the_visibility_work_leaves_new_evidence_with_a_run_id(
    tmp_path: Path, monkeypatch
) -> None:
    root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    vault, evidence = tmp_path / "v.db", tmp_path / "e.json"
    evidence.write_text('{"old": true}\n', encoding="utf-8")
    with mock.patch.object(_delivery.DeliverySink, "_fill", side_effect=KeyboardInterrupt):
        result = run(yml, "--vault", str(vault), "--evidence-out", str(evidence))
    assert result.exit_code == INTERRUPT_EXIT, (result.exit_code, result.output[-300:])
    (folder,) = runs(root)
    assert latest(root) == folder.name
    assert vault.stat().st_size > 0
    live = json.loads(evidence.read_text(encoding="utf-8"))
    assert "old" not in live and live["run_id"]
    assert litter(root) == []


# --- the UsageRefusal handler, strict route -------------------------------------------------


@posix
def test_a_usage_refusal_after_the_stage_opened_cleans_up_and_shows_no_path(
    tmp_path: Path,
) -> None:
    root, yml = project(tmp_path)
    with mock.patch.object(
        _delivery.DeliverySink, "write_outputs", side_effect=UsageRefusal("refused here")
    ):
        result = run(yml, "--evidence-out", str(tmp_path / "e.json"))
    assert result.exit_code == 1, result.output[-300:]  # the one code of a usage refusal
    assert runs(root) == []
    assert latest(root) is None
    assert litter(root) == []
    assert not (tmp_path / "e.json").exists()
    assert "t1.csv" not in result.output


# --- AT-83: an error after delivery ---------------------------------------------------------


def _after_delivery_error():
    real = _delivery.DeliverySink.deliver

    def deliver_then_fail(self, decision, ledger):
        real(self, decision, ledger)
        raise RuntimeError("scope exit")

    return mock.patch.object(_delivery.DeliverySink, "deliver", deliver_then_fail)


@posix
def test_at83_the_success_tail_runs_once_and_the_failure_path_never_runs(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    with (
        _after_delivery_error(),
        mock.patch.object(_render, "finish", wraps=_render.finish) as finish,
        mock.patch.object(_errors, "fail", wraps=_errors.fail) as fail,
    ):
        result = run(yml)
    assert result.exit_code == 0, result.output[-300:]
    assert finish.call_count == 1
    fail.assert_not_called()
    (folder,) = runs(root)
    assert latest(root) == folder.name  # abandon after delivery removed nothing


@posix
def test_at83_the_stage_abort_is_not_called_after_a_delivery(tmp_path: Path) -> None:
    _root, yml = project(tmp_path)
    aborts: list[str] = []
    real = _delivery._Strict.abort

    def spy(self):
        aborts.append("abort")
        return real(self)

    with _after_delivery_error(), mock.patch.object(_delivery._Strict, "abort", spy):
        assert run(yml).exit_code == 0
    assert aborts == []


@posix
def test_at83_a_cleanup_fault_and_a_late_error_still_give_one_cleanup_warning(
    tmp_path: Path,
) -> None:
    _root, yml = project(tmp_path)
    with (
        _after_delivery_error(),
        mock.patch("decoy.cli.io._pointer.replace_symlink", side_effect=OSError("x")),
        mock.patch.object(_evidence, "publish_attempts", side_effect=OSError("y")),
    ):
        result = run(yml, "--evidence-out", str(tmp_path / "e.json"))
    assert result.exit_code == 0, result.output[-300:]
    codes = [w["code"] for w in _body(result)["warnings"]]
    assert codes.count("delivery_cleanup_incomplete") == 1


def test_at83_a_late_error_on_a_fixed_folder_keeps_the_files_and_the_exit(tmp_path: Path) -> None:
    _root, yml = project(tmp_path)
    out = tmp_path / "o"
    with _after_delivery_error():
        result = run(yml, "--out-dir", str(out))
    assert result.exit_code == 0, result.output[-300:]
    assert sorted(p.name for p in out.glob("*.csv")) == ["t1.csv", "t2.csv"]
    codes = [w["code"] for w in _body(result)["warnings"]]
    assert codes.count("delivery_cleanup_incomplete") == 1


@posix
def test_at83_the_plain_branch_writes_before_it_delivers(tmp_path: Path) -> None:
    _root, yml = project(tmp_path)
    events: list[str] = []
    w, d = _delivery.DeliverySink.write_outputs, _delivery.DeliverySink.deliver

    def write(self, *a, **k):
        events.append("write")
        return w(self, *a, **k)

    def deliver(self, *a, **k):
        events.append("deliver")
        return d(self, *a, **k)

    with (
        mock.patch.object(_delivery.DeliverySink, "write_outputs", write),
        mock.patch.object(_delivery.DeliverySink, "deliver", deliver),
    ):
        assert run(yml).exit_code == 0
    assert events == ["write", "deliver"]


def test_at83_the_cleanup_warning_is_recorded_once_however_often_it_is_noted() -> None:
    from decoy.cli.run import _deliver

    seen: list[dict] = []

    class Ctx:
        _cli_warnings = seen

        def add_cli_warning(self, code: str, text: str) -> None:
            seen.append({"code": code, "text": text})

    _deliver.note_cleanup(Ctx())  # type: ignore[arg-type]
    _deliver.note_cleanup(Ctx())  # type: ignore[arg-type]
    assert [w["code"] for w in seen] == ["delivery_cleanup_incomplete"]
