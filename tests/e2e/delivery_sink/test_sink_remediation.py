"""C2a-1 review round 1: the cases the first review found missing, each against rev 6.8 section 19.

19.1 locks on the strict route only, 19.2 a withheld run, 19.3 the vault fact, 19.4 the report
path, 19.5 attempt names, 19.6 the collision inventory, 19.7 the depth limit, plus the current
link and the registry guards. AT-18, 31, 33, 36 and 82 (b, c, e) are at the end.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from decoy.__main__ import app
from decoy.cli.io import _delivery, _placement, _pointer
from decoy.cli.io._placement import OutputPlacement
from decoy.cli.io._run_outputs import run_outputs
from decoy.cli.run import _deliver, _evidence
from decoy.cli.run._context import CLI_REFUSAL_CODES, DELIVERY_SIDE_FILE_BUSY
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
LOCK = ".decoy-lock"


def _locks(base: Path) -> list[str]:
    return sorted(str(p.relative_to(base)) for p in base.rglob(f"*{LOCK}"))


def _body(result) -> dict:
    return json.loads(result.output[result.output.index("{") :])


def _withhold(*_a, **_k) -> bool:
    return True


def _hold(path: Path):
    """The engine's lock on `path`, held by the test (the way another run holds it)."""
    from decoy_engine.fileaccess import FileRequest, FileRole, current

    request = FileRequest(FileRole.TARGET_OUTPUT, "write", str(path), "test")
    return current().output_dir(request).lock(0.0)


# --- 19.1: locks on the strict route only ---------------------------------------------------


def test_the_pass_through_takes_no_lock_and_makes_no_lock_file(tmp_path: Path) -> None:
    _root, yml = project(tmp_path)
    out = tmp_path / "out_here"
    result = run(
        yml,
        "--out-dir",
        str(out),
        "--evidence-out",
        str(tmp_path / "e.json"),
    )
    assert result.exit_code == 0, result.output
    assert _locks(tmp_path) == []


def test_a_host_without_the_pointer_takes_no_lock_either(tmp_path: Path, monkeypatch) -> None:
    _root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    with mock.patch.object(_pointer, "_pointer_supported", return_value=False):
        result = run(yml, "--vault", str(tmp_path / "v.db"), "--evidence-out", str(tmp_path / "e"))
    assert result.exit_code == 0, result.output
    assert [p for p in _locks(tmp_path) if "orders" not in p] == []


@posix
def test_the_strict_route_locks_the_vault_and_evidence_leaves(tmp_path: Path, monkeypatch) -> None:
    _root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    result = run(yml, "--vault", str(tmp_path / "v.db"), "--evidence-out", str(tmp_path / "e.json"))
    assert result.exit_code == 0, result.output
    names = {Path(p).name for p in _locks(tmp_path)}
    assert {".v.db.decoy-lock", ".e.json.decoy-lock"} <= names


@posix
def test_a_leaf_held_by_another_run_refuses_before_any_write(tmp_path: Path, monkeypatch) -> None:
    root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    side = tmp_path / "side"
    side.mkdir()
    vault = side / "v.db"
    # Another spelling of the same file: both must resolve to one lock.
    alias = side / ".." / "side" / "v.db"
    with _hold(vault):
        result = run(yml, "--vault", str(alias))
    assert result.exit_code == 3, result.output
    assert DELIVERY_SIDE_FILE_BUSY in result.output
    assert not vault.exists()
    assert latest(root) is None
    assert (
        not any(p.suffix == ".csv" for p in (root / "out").rglob("*"))
        if (root / "out").exists()
        else True
    )


@posix
def test_a_final_symlink_shares_the_lock_of_the_file_it_names(tmp_path: Path) -> None:
    """`--evidence-out` follows a final link, so the lock is the target's, not the link's."""
    root, yml = project(tmp_path, tables=1)
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link.json").symlink_to(real / "e.json")
    with _hold(real / "e.json"):
        result = run(yml, "--evidence-out", str(tmp_path / "link.json"))
    assert result.exit_code == 3, result.output
    assert DELIVERY_SIDE_FILE_BUSY in result.output
    assert latest(root) is None


@posix
def test_a_lock_that_cannot_be_taken_refuses_and_never_proceeds_unlocked(
    tmp_path: Path, monkeypatch
) -> None:
    from decoy_engine.fileaccess import LockUnavailable
    from decoy_engine.fileaccess._local import LocalOutputDir

    root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    vault = tmp_path / "v.db"

    real = LocalOutputDir.lock

    def unavailable(self, *a, **k):
        # Only the side-file request fails; the engine's own pointer lock must still work, or
        # the run would stop for a different reason and hide a side lock that is skipped.
        if Path(self.locator) == vault:
            raise LockUnavailable("no lock here")
        return real(self, *a, **k)

    with mock.patch.object(LocalOutputDir, "lock", unavailable):
        result = run(yml, "--vault", str(vault))
    assert result.exit_code == 3, result.output
    assert DELIVERY_SIDE_FILE_BUSY in result.output
    assert not vault.exists()
    assert latest(root) is None


@posix
def test_an_absolute_only_project_run_reserves_no_lock_name(tmp_path: Path, monkeypatch) -> None:
    """Absolute targets pass through the engine's stage, which makes no lock file, so a name
    that looks like a lock is free for another output (the gate and the sink share one rule)."""
    _root, yml = project(tmp_path, tables=1, targets="absolute")
    vaulted(yml, monkeypatch)
    folder = tmp_path / "side"
    folder.mkdir()
    result = run(
        yml,
        "--vault",
        str(folder / "v.db"),
        "--evidence-out",
        str(folder / ".v.db.decoy-lock"),
    )
    assert result.exit_code == 0, result.output[-400:]
    # The only such name is the evidence file the run was asked to write.
    assert _locks(tmp_path) == ["side/.v.db.decoy-lock"]


def test_one_rule_says_which_roots_take_the_strict_stage() -> None:
    from decoy.cli.io._placement import Fixed, NoLocalOutput, Relative, Split, strict_route

    assert strict_route(Relative()) is _pointer.pointer_supported()
    assert strict_route(Relative(), chunked=True) is False
    assert strict_route(Fixed(Path("/x"))) is False
    assert strict_route(NoLocalOutput()) is False
    assert strict_route(Split("a", "b")) is False


def test_the_report_sibling_names_follow_the_run_id_rule() -> None:
    from decoy.cli.io._run_outputs import in_flight_name

    run_id = "20261128T120000000000Z-0a1b2c3d"
    assert in_flight_name(f"{run_id}.post-scan.json")
    assert in_flight_name(f".{run_id}.post-scan.json.decoy-lock")
    assert not in_flight_name(f"{run_id}.post-scan.json.decoy-lock")  # no leading dot
    assert not in_flight_name(f".{run_id}.post-scan.json")  # a report has no leading dot
    assert not in_flight_name("20261128T120000000000Z-0a1b2.post-scan.json")  # not a run id
    assert not in_flight_name("20261128T120000000000Z-0a1b2c3d1.post-scan.json")


def test_the_busy_code_is_registered() -> None:
    assert DELIVERY_SIDE_FILE_BUSY == "delivery_side_file_busy"
    assert DELIVERY_SIDE_FILE_BUSY in CLI_REFUSAL_CODES
    assert frozenset({DELIVERY_SIDE_FILE_BUSY}) == CLI_REFUSAL_CODES


# --- 19.2: a withheld run -------------------------------------------------------------------


@posix
def test_a_withheld_run_takes_no_side_file_lock_and_keeps_exit_4(tmp_path: Path) -> None:
    root, yml = project(tmp_path, tables=1)
    post_scan(yml)
    evidence = tmp_path / "e.json"
    with _hold(evidence), mock.patch.object(_deliver, "_gate_withholds", _withhold):
        result = run(yml, "--evidence-out", str(evidence))
    assert result.exit_code == 4, result.output[-500:]
    assert latest(root) is None


# --- 19.3: the vault fact is the writer's own outcome ---------------------------------------


@posix
def test_a_vault_file_that_is_not_this_runs_does_not_make_the_fact_committed(
    tmp_path: Path, monkeypatch
) -> None:
    root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    vault = tmp_path / "v.db"
    real = _delivery.DeliverySink.deliver

    def other_run_wins(self, decision, ledger):
        (root / "out" / "orders" / "LATEST").write_text("99990101T000000000000Z-deadbeef\n")
        return real(self, decision, ledger)

    # The preflight refuses an existing vault, so another run makes the file after it.
    real_attach = _delivery.DeliverySink.attach_vault

    def appears_later(self, *a, **k):
        real_attach(self, *a, **k)
        vault.write_bytes(b"someone else's file")

    with (
        mock.patch.object(_delivery.DeliverySink, "attach_vault", appears_later),
        mock.patch.object(_delivery.DeliverySink, "deliver", other_run_wins),
    ):
        result = run(yml, "--vault", str(vault))
    assert result.exit_code == 3, result.output
    # The file is there, yet this run wrote nothing: the fact is the writer's, not lexists.
    assert document(result)["delivery"]["vault"] == "not_used"
    assert vault.read_bytes() == b"someone else's file"


# --- 19.4: an uncertain receipt shows no path, however the run ends -------------------------


def _faults():
    import typer

    from decoy.cli.run._context import UsageRefusal

    return [
        pytest.param(lambda: typer.Exit(3), id="exit"),
        pytest.param(lambda: RuntimeError("late"), id="error"),
        pytest.param(lambda: UsageRefusal("late refusal"), id="usage-refusal"),
    ]


@posix
@pytest.mark.parametrize("make_fault", _faults())
def test_an_uncertain_receipt_that_is_recovered_shows_no_path(tmp_path: Path, make_fault) -> None:
    root, yml = project(tmp_path / "json")
    with uncertain_swap(), deliver_then(make_fault()):
        result = run(yml)
    assert result.exit_code == 0, result.output[-400:]
    out = result.output
    body = json.loads(out[out.index("{") :])
    assert all(r["path"] is None for r in body["tables"]), body["tables"]
    _assert_no_location(out, root)
    codes = [w["code"] for w in body["warnings"]]
    assert codes.count("delivery_cleanup_incomplete") == 1

    root2, yml2 = project(tmp_path / "human")
    with uncertain_swap(), deliver_then(make_fault()):
        human = runner.invoke(app, ["run", str(yml2)], env={"COLUMNS": "400"})
    assert human.exit_code == 0, human.output[-400:]
    assert human.output.count("cleaning up after it did not") == 1
    _assert_no_location(human.output, root2)


def _assert_no_location(output: str, root: Path) -> None:
    """The whole response, not a member of it: no path into the project's `out/` folder (the
    run's own config path may appear) and no table file name."""
    for form in {str(root / "out"), str(root.resolve() / "out")}:
        assert form not in output, form
    assert "t1.csv" not in output
    assert "t2.csv" not in output


@posix
def test_an_uncertain_receipt_names_no_report_of_an_earlier_run(tmp_path: Path) -> None:
    root, yml = project(tmp_path / "json", tables=1)
    post_scan(yml)
    earlier = tmp_path / "verdicts" / "report.json"
    earlier.parent.mkdir()
    earlier.write_text("an earlier verdict\n", encoding="utf-8")
    with uncertain_swap():
        result = run(yml, "--integrity-out", str(earlier))
    assert result.exit_code == 0, result.output[-400:]
    assert earlier.read_text(encoding="utf-8") == "an earlier verdict\n"
    assert "report.json" not in result.output
    assert str(earlier.parent) not in result.output
    _assert_no_location(result.output, root)

    root2, yml2 = project(tmp_path / "human", tables=1)
    post_scan(yml2)
    with uncertain_swap():
        human = runner.invoke(
            app,
            ["run", str(yml2), "--integrity-out", str(earlier)],
            env={"COLUMNS": "400"},
        )
    assert human.exit_code == 0, human.output[-400:]
    assert "report.json" not in human.output
    _assert_no_location(human.output, root2)


# --- 19.4: the not-delivered report ---------------------------------------------------------


@posix
def test_the_not_delivered_report_is_create_only(tmp_path: Path) -> None:
    root, yml = project(tmp_path, tables=1)
    post_scan(yml)
    taken = root / "out" / "orders" / "taken.post-scan.json"
    taken.parent.mkdir(parents=True)
    taken.write_text("an earlier verdict\n", encoding="utf-8")
    with (
        mock.patch.object(_deliver, "_gate_withholds", _withhold),
        mock.patch.object(_delivery, "not_delivered_report_name", return_value=taken.name),
    ):
        result = run(yml)
    assert result.exit_code == 4, result.output[-500:]
    assert taken.read_text(encoding="utf-8") == "an earlier verdict\n"
    assert "post_scan_report_write_failed" in result.output
    assert _body(result)["post_scan"]["report"] is None


@posix
def test_a_failure_before_the_bind_keeps_the_verdict_and_names_it(tmp_path: Path) -> None:
    from decoy.cli.run._context import EvidenceWriteRefusal

    root, yml = project(tmp_path, tables=1)
    post_scan(yml)
    with mock.patch.object(_evidence, "write_attempts", side_effect=EvidenceWriteRefusal("x")):
        result = run(yml, "--evidence-out", str(tmp_path / "e.json"))
    assert result.exit_code == 3, result.output[-500:]
    (report,) = (root / "out" / "orders").glob("*.post-scan.json")
    assert json.loads(report.read_text(encoding="utf-8"))


@posix
def test_the_rendered_report_is_where_it_was_written_or_none(tmp_path: Path) -> None:
    root, yml = project(tmp_path, tables=1)
    post_scan(yml)
    with mock.patch.object(_deliver, "_gate_withholds", _withhold):
        result = run(yml)
    (report,) = (root / "out" / "orders").glob("*.post-scan.json")
    assert _body(result)["post_scan"]["report"] == str(report.resolve())


# --- 19.5: attempt names --------------------------------------------------------------------


@posix
def test_a_255_byte_evidence_name_still_has_an_attempt_name(tmp_path: Path) -> None:
    _root, yml = project(tmp_path, tables=1)
    # Short enough for the engine's `.<name>.decoy-lock`, long enough that `.<name>.<id>.attempt`
    # does not fit in one component without the bound.
    name = "é" * 95 + "a" * 45 + ".json"
    assert len(name.encode()) == 240
    result = run(yml, "--evidence-out", str(tmp_path / name))
    assert result.exit_code == 0, result.output[-500:]
    assert (tmp_path / name).is_file()
    assert [p for p in tmp_path.iterdir() if p.name.endswith(".attempt")] == []


def test_the_attempt_name_stays_inside_one_component() -> None:
    ctx = mock.Mock(invocation_id="0123456789abcdef0123")
    for name in ("e.json", "x" * 255, "é" * 127 + "a"):
        attempt = _evidence._attempt_name(ctx, Path("/d") / name, "e")
        assert len(attempt.name.encode()) <= 255
        assert attempt.parent == Path("/d")
    # The roles keep the two attempts of one name apart.
    a = _evidence._attempt_name(ctx, Path("/d/x"), "e")
    b = _evidence._attempt_name(ctx, Path("/d/x"), "i")
    assert a != b


@posix
def test_an_attempt_that_published_and_then_failed_is_still_cleaned_up(tmp_path: Path) -> None:
    from decoy._atomic import AtomicWriteError

    root, yml = project(tmp_path, tables=1)
    real = _evidence._put

    def put_then_fail(path, data):
        real(path, data)
        raise AtomicWriteError("ATOMIC_WRITE_FAILED", "x")

    with mock.patch.object(_evidence, "_put", put_then_fail):
        result = run(yml, "--evidence-out", str(tmp_path / "e.json"))
    assert result.exit_code == 3, result.output[-500:]
    assert [p for p in tmp_path.iterdir() if p.name.endswith(".attempt")] == []
    assert litter(root) == []


def test_the_pass_through_writes_the_integrity_report_once(tmp_path: Path) -> None:
    from decoy.cli.io import _integrity_report

    _root, yml = project(tmp_path, tables=1)
    post_scan(yml)
    calls: list[Path] = []
    real = _integrity_report.write_run_report

    def spy(report, path, sha, **kw):
        calls.append(path)
        return real(report, path, sha, **kw)

    explicit = tmp_path / "r.json"
    with (
        mock.patch("decoy.cli.run._flow.write_run_report", spy),
        mock.patch.object(_deliver, "write_run_report", spy),
        mock.patch.object(_evidence, "write_run_report", spy),
    ):
        result = run(yml, "--out-dir", str(tmp_path / "o"), "--integrity-out", str(explicit))
    assert result.exit_code == 0, result.output[-500:]
    assert [p for p in calls if p.name == "r.json"] == [explicit]


# --- 19.6: the collision inventory ----------------------------------------------------------


def test_a_pass_through_route_reserves_no_stage_file_name(tmp_path: Path) -> None:
    from decoy_engine.fileaccess import DESCRIPTOR_NAME

    base = tmp_path / "out" / "orders" / "20261109T101500123456Z-0a1b2c3d"
    cfg = {"targets": {"t": {"type": "file", "format": "csv", "path": "t.csv"}}}
    placement = OutputPlacement(kind="project")

    def names(strict: bool) -> set[str]:
        got = run_outputs(cfg, placement, tmp_path / "p.yaml", base, strict=strict)
        return {o.path.name for o in got}

    assert DESCRIPTOR_NAME in names(True)
    assert DESCRIPTOR_NAME not in names(False)
    assert not any(n.endswith(".post-scan.json") for n in names(False))


# --- 19.7: the depth limit ------------------------------------------------------------------


@posix
def test_a_target_deeper_than_eight_components_is_refused_at_preflight(tmp_path: Path) -> None:
    import yaml

    root, yml = project(tmp_path, tables=1)
    cfg = yaml.safe_load(yml.read_text(encoding="utf-8"))
    cfg["targets"]["t1"]["path"] = "/".join(["d"] * 8) + "/t1.csv"  # 9 components
    yml.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    result = run(yml)
    assert result.exit_code != 0
    assert "layout.delivery_member_too_deep" in result.output
    assert not (root / "out").exists()
    cfg["targets"]["t1"]["path"] = "/".join(["d"] * 7) + "/t1.csv"  # 8 components
    yml.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    assert run(yml).exit_code == 0


def test_a_pass_through_host_keeps_the_deep_target(tmp_path: Path) -> None:
    import yaml

    _root, yml = project(tmp_path, tables=1)
    cfg = yaml.safe_load(yml.read_text(encoding="utf-8"))
    cfg["targets"]["t1"]["path"] = "/".join(["d"] * 8) + "/t1.csv"
    yml.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with mock.patch.object(_pointer, "_pointer_supported", return_value=False):
        assert run(yml).exit_code == 0


def test_the_depth_limit_equals_the_engines() -> None:
    from decoy_engine._canonical import UNIT_PATH_MAX_DEPTH

    assert _placement.STRICT_MEMBER_DEPTH == UNIT_PATH_MAX_DEPTH


def test_the_deliverable_target_set_equals_the_engines() -> None:
    from decoy_engine.delivery._plan import DELIVERABLE_TARGET_TYPES

    assert _deliver.DELIVERABLE_TYPES == DELIVERABLE_TARGET_TYPES


# --- the `current` link ---------------------------------------------------------------------


@posix
def test_a_failed_current_link_keeps_the_layout_warning_and_warns_once(tmp_path: Path) -> None:
    _root, yml = project(tmp_path)
    with mock.patch.object(_pointer, "replace_symlink", side_effect=OSError("x")):
        result = run(yml)
    assert result.exit_code == 0, result.output
    assert result.output.count("layout.latest_link_failed") == 1
    codes = [w["code"] for w in json.loads(result.output[result.output.index("{") :])["warnings"]]
    assert codes.count("delivery_cleanup_incomplete") == 1


# --- AT-18 / AT-33: the vault is published inside the bind -----------------------------------

_KILL = """
import os, signal, sys
from decoy_engine.publication import LocalPointerStore
real = LocalPointerStore.replace_if
def die(*a, **k):
    os.kill(os.getpid(), signal.SIGKILL)
LocalPointerStore.replace_if = die
from decoy.__main__ import app
sys.argv = ["decoy"] + sys.argv[1:]
app()
"""


@posix
def test_at18_a_kill_after_the_bind_leaves_the_old_run_current_and_an_orphan_vault(
    tmp_path: Path, monkeypatch
) -> None:
    root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    assert run(yml).exit_code == 0
    (old,) = runs(root)
    vault = tmp_path / "v.db"
    proc = subprocess.run(
        [sys.executable, "-c", _KILL, "run", str(yml), "--json", "--vault", str(vault)],
        capture_output=True,
        text=True,
        env=child_env(),
        timeout=300,
    )
    assert proc.returncode == -signal.SIGKILL
    assert latest(root) == old.name
    bound = [p for p in runs(root) if p != old]
    assert len(bound) == 1 and (bound[0] / "_decoy_publication.json").is_file()
    assert vault.is_file()
    rerun = run(yml, "--vault", str(vault))
    assert rerun.exit_code == 1
    assert "vault_exists" in rerun.output


@posix
def test_at33_a_fault_after_the_vault_and_before_the_bind_keeps_the_orphan(
    tmp_path: Path, monkeypatch
) -> None:
    root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    vault, evidence = tmp_path / "v.db", tmp_path / "e.json"
    evidence.write_text("old evidence\n", encoding="utf-8")
    stage = __import__("decoy_engine.publication._publish", fromlist=["x"])

    def refuse_bind(*_a, **_k):
        raise OSError("the bind is refused")

    with mock.patch.object(stage, "_bind", refuse_bind):
        result = run(yml, "--vault", str(vault), "--evidence-out", str(evidence))
    assert result.exit_code == 3, result.output[-500:]
    assert vault.is_file()  # rule V ran: the orphan stays, nothing unlinks it
    assert evidence.read_text(encoding="utf-8") == "old evidence\n"
    assert latest(root) is None
    again = run(yml, "--vault", str(vault))
    assert again.exit_code == 1
    assert "vault_exists" in again.output


@posix
def test_at33_an_unrelated_file_at_the_vault_path_is_never_replaced(
    tmp_path: Path, monkeypatch
) -> None:
    root, yml = project(tmp_path, tables=1)
    vaulted(yml, monkeypatch)
    vault = tmp_path / "v.db"
    vault.write_bytes(b"not a vault")
    result = run(yml, "--vault", str(vault))
    assert result.exit_code == 1, result.output[-500:]
    assert vault.read_bytes() == b"not a vault"
    assert latest(root) is None


# --- AT-31: an interrupt after the visibility point ------------------------------------------


@posix
def test_at31_an_interrupt_after_the_visibility_point_leaves_the_run_delivered(
    tmp_path: Path,
) -> None:
    root, yml = project(tmp_path)
    seen: list[_delivery.DeliverySink] = []
    real_init = _delivery.DeliverySink.__init__

    def spy(self, *a, **k):
        real_init(self, *a, **k)
        seen.append(self)

    with (
        mock.patch.object(_delivery.DeliverySink, "__init__", spy),
        mock.patch.object(_delivery.DeliverySink, "_fill", side_effect=KeyboardInterrupt),
    ):
        run(yml)
    (folder,) = runs(root)
    assert latest(root) == folder.name
    (sink,) = seen
    assert sink.state == "delivered"  # set in the statement that passes the visibility point


# --- AT-36: the paths follow what was delivered ----------------------------------------------


@posix
def test_at36_delivered_shows_final_paths_and_an_abort_shows_none(tmp_path: Path) -> None:
    root, yml = project(tmp_path)
    ok = run(yml)
    (folder,) = runs(root)
    body = json.loads(ok.output[ok.output.index("{") :])
    assert sorted(r["path"] for r in body["tables"]) == [
        str(folder / "t1.csv"),
        str(folder / "t2.csv"),
    ]
    with mock.patch.object(_evidence, "write_attempts", side_effect=OSError("x")):
        bad = run(yml, "--evidence-out", str(tmp_path / "e.json"))
    assert bad.exit_code != 0
    assert document(bad).get("outputs") in ({}, [], None)


# --- AT-82 (b), (c), (e) ----------------------------------------------------------------------


def test_at82b_an_absolute_project_run_whose_second_table_fails_changes_no_latest(
    tmp_path: Path,
) -> None:
    root, yml = project(tmp_path, targets="absolute")
    with mock.patch(
        "decoy.cli.io._delivery.write_targets", side_effect=OSError("second table failed")
    ):
        result = run(yml)
    assert result.exit_code == 3, result.output[-500:]
    assert latest(root) is None
    assert not (root / "out").exists()


def test_at82c_a_project_run_with_no_local_file_target_is_kind_a(tmp_path: Path) -> None:
    import yaml

    root, yml = project(tmp_path, tables=1)
    cfg = yaml.safe_load(yml.read_text(encoding="utf-8"))
    cfg["targets"] = {}
    yml.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    result = run(yml, "--evidence-out", str(tmp_path / "e.json"))
    body = json.loads(result.output[result.output.index("{") :])
    assert (
        "output_dir" not in json.dumps(body["result"]) or body["result"].get("output_dir") is None
    )
    assert latest(root) is None
    assert not (root / "out").exists()
    assert _locks(tmp_path) == []


def test_at82e_out_dir_with_a_relative_and_an_absolute_target_in_that_folder(
    tmp_path: Path,
) -> None:
    import yaml

    root, yml = project(tmp_path)
    out = tmp_path / "here"
    out.mkdir()
    cfg = yaml.safe_load(yml.read_text(encoding="utf-8"))
    cfg["targets"]["t2"]["path"] = str(out / "t2.csv")
    yml.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    result = run(yml, "--out-dir", str(out))
    assert result.exit_code == 0, result.output[-500:]
    assert sorted(p.name for p in out.glob("*.csv")) == ["t1.csv", "t2.csv"]
    assert document(result)["delivery"]["mode"] == "in_place"
    assert latest(root) is None


# --- 19.7: a split with an over-deep member -------------------------------------------------


@posix
def test_a_split_with_an_over_deep_member_reports_the_split_first(tmp_path: Path) -> None:
    """The depth limit belongs to the strict stage, and a split never reaches it: the split is
    reported first, and the depth refusal appears once the split is gone. Both are refused."""
    import yaml

    root, yml = project(tmp_path, tables=2)
    cfg = yaml.safe_load(yml.read_text(encoding="utf-8"))
    cfg["targets"]["t1"]["path"] = "/".join(["d"] * 8) + "/t1.csv"  # relative, 9 components
    cfg["targets"]["t2"]["path"] = str(tmp_path / "abs" / "t2.csv")  # absolute: a second root
    yml.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    result = run(yml)
    assert result.exit_code != 0
    assert "layout.delivery_root_split" in result.output
    assert "layout.delivery_member_too_deep" not in result.output
    assert not (root / "out").exists()

    cfg["targets"]["t2"]["path"] = "t2.csv"  # the split is gone; the deep member remains
    yml.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    again = run(yml)
    assert again.exit_code != 0
    assert "layout.delivery_member_too_deep" in again.output
    assert "layout.delivery_root_split" not in again.output
