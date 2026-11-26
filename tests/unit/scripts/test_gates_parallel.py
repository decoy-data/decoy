"""scripts/dev/gates.sh with GATES_WORKERS > 1: the two passes, the reporter and the mode.

Ported from the engine's test_gates_parallel.py (ENGINE-PAR P2), minus the order-map cells (the
CLI keeps collection order) and plus the CLI's own: an empty marker expression, the temp root,
the outcomes file and the worker rule."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from _gates_harness import (
    BASH,
    DEV,
    GIT,
    REPO,
    at_main,
    child_env,
    git,
    pytest_argvs,
    pytest_calls,
    pytest_envs,
    recording_venv,
    report_module,
    run,
    seeded_clone,
)
from _gates_harness import gates as run_gates
from tests.sentry.tooling import gate_args

pytestmark = pytest.mark.skipif(BASH is None or GIT is None, reason="needs bash and git")

TESTS_ONLY = ("--steps", "tests", "tests/_seeded")
WHOLE = ("--steps", "tests", "--full")


def commit(clone: Path, message: str) -> None:
    git(clone, "add", "-A")
    proc = run(
        [str(GIT), "-c", "user.name=gates-test", "-c", "user.email=gates-test@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "--no-verify", "--allow-empty", "-qm", message],
        clone,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stdout + proc.stderr


def parallel_clone(tmp_path: Path) -> Path:
    """A seeded clone that carries the xdist report scrubber, as a tree after this change does."""
    clone = seeded_clone(tmp_path)
    shutil.copy2(REPO / "tests" / "_xdist_safe_reports.py", clone / "tests")
    commit(clone, "scrubber")
    at_main(clone)
    return clone


def last_mark(call: list[str]) -> str:
    """The `-m` value that wins: the last one on the command line."""
    return call[len(call) - call[::-1].index("-m")]


# --- AT-1: the worker rule -----------------------------------------------------------------


def worker_module():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("_gate_workers", DEV / "_gate_workers.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def reporter_workers(**env: str) -> subprocess.CompletedProcess[str]:
    base = child_env() | {"GATES_WORKERS": "1"} | env
    return subprocess.run(
        [sys.executable, str(DEV / "_gates_report.py"), "--workers"],
        env=base, capture_output=True, text=True, timeout=60, check=False,
    )  # fmt: skip


@pytest.mark.parametrize(
    ("value", "count"), [("4", 4), ("1", 1), ("0", 1), ("-3", 1), (" 4 ", 4), ("3\n", 3)]
)
def test_a_number_is_the_worker_count_with_a_minimum_of_one(value: str, count: int) -> None:
    pytest.importorskip("xdist")
    proc = reporter_workers(GATES_WORKERS=value)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.split()[0] == str(count), proc.stdout


@pytest.mark.parametrize("value", ["x", "4x", "1.5", "4 5", "four"])
def test_a_value_that_is_not_a_number_or_auto_is_a_usage_error(value: str) -> None:
    proc = reporter_workers(GATES_WORKERS=value)
    assert proc.returncode == 64, proc.stdout + proc.stderr
    assert value not in proc.stdout, "the bad value stays out of stdout"


def test_gates_sh_exits_2_for_a_bad_worker_value(tmp_path: Path) -> None:
    clone = parallel_clone(tmp_path)
    venv, log = recording_venv(tmp_path)
    rc, out = run_gates(clone, venv, *TESTS_ONLY, GATES_WORKERS="lots")
    assert rc == 2, out
    assert pytest_calls(log) == []


def test_auto_is_capped_by_cpus_and_memory() -> None:
    w = worker_module()
    gb = 1024 * 1024
    assert w.choose("auto", 28, 64 * gb, 40 * gb, None)[0] == 4
    assert w.choose("", 2, 64 * gb, 40 * gb, None)[0] == 2
    assert w.choose("auto", 28, 8 * gb, 6 * gb, None)[0] == 2, "a host under 14 GB gets 2"
    assert w.choose("auto", 28, 8 * gb, 2 * gb, None)[0] == 1, "under 4 GB free gets 1"
    assert w.choose("auto", 28, 64 * gb, 40 * gb, 8 * gb * 1024)[0] == 2, "a cgroup limit counts"


def test_more_than_one_worker_without_xdist_becomes_one_and_says_why(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    w = worker_module()
    monkeypatch.setenv("GATES_WORKERS", "4")
    monkeypatch.setattr(w.importlib.util, "find_spec", lambda _name: None)
    assert w.main() == 0
    count, _, why = capsys.readouterr().out.strip().partition(" ")
    assert count == "1" and "pytest-xdist is not installed" in why, why


# --- AT-2, AT-4: the command shape ------------------------------------------------------


def test_workers_one_is_the_plain_single_pytest_run(tmp_path: Path) -> None:
    clone = parallel_clone(tmp_path)
    venv, log = recording_venv(tmp_path)
    rc, out = run_gates(clone, venv, *TESTS_ONLY, GATES_WORKERS="1")
    assert rc == 0, out
    (call,) = pytest_calls(log)
    assert "-n" not in call and "--dist" not in call and "serial" not in " ".join(call), call
    assert "workers:    1 (GATES_WORKERS=1)" in out, out
    assert "tests-serial" not in out, out


def test_workers_two_run_a_parallel_pass_then_a_serial_pass(tmp_path: Path) -> None:
    clone = parallel_clone(tmp_path)
    venv, log = recording_venv(tmp_path)
    rc, out = run_gates(clone, venv, *TESTS_ONLY, GATES_WORKERS="2", FAKE_TOTAL="3")
    assert rc == 0, out
    assert "workers:    2 (GATES_WORKERS=2)" in out, out
    par, ser = pytest_argvs(log)  # exactly two pytest runs, in this order
    assert par[par.index("-n") + 1] == "2" and par[par.index("--dist") + 1] == "loadfile", par
    assert last_mark(par) == "not serial", par  # the CLI's own PYTEST_ARGS holds no -m
    assert "-n" not in ser and "--dist" not in ser, ser
    assert last_mark(ser) == "serial", ser
    assert any(a.endswith("branch-tests.xml") for a in par), par
    assert any(a.endswith("branch-tests-serial.xml") for a in ser), ser
    assert re.search(r"\[tests\] PASS passed=4 failed=0", out), out  # 3 plain + 1 serial


def test_a_seeded_marker_expression_is_parenthesised_in_both_passes(tmp_path: Path) -> None:
    clone = parallel_clone(tmp_path)
    gates = clone / "scripts" / "dev" / "gates.sh"
    text = gates.read_text()
    assert "\nPYTEST_ARGS=()\n" in text
    gates.write_text(text.replace("\nPYTEST_ARGS=()\n", "\nPYTEST_ARGS=(-m 'not slow')\n"))
    assert gate_args.marker_expr(gates.read_text()) == "not slow"
    venv, log = recording_venv(tmp_path)
    rc, out = run_gates(clone, venv, *TESTS_ONLY, GATES_WORKERS="2")
    assert rc == 0, out
    par, ser = pytest_argvs(log)
    assert (last_mark(par), last_mark(ser)) == (
        "(not slow) and not serial",
        "(not slow) and serial",
    )
    for call in (par, ser):
        assert " and " not in " ".join(a for a in call if a != last_mark(call)), call
        assert not last_mark(call).startswith(("and", "()")), call


@pytest.mark.parametrize(
    ("env", "rc"),
    [
        ({"FAKE_NO_PARALLEL": "1"}, 0),  # (5, 0): only serial tests selected
        ({"FAKE_NO_SERIAL": "1"}, 0),  # (0, 5): no serial tests selected
        ({"FAKE_NO_PARALLEL": "1", "FAKE_NO_SERIAL": "1"}, 1),  # (5, 5): nothing ran at all
        ({"FAKE_NO_SERIAL": "1", "FAKE_FAIL": "tests/a.py::test_x"}, 1),  # (1, 5)
        ({"FAKE_NO_PARALLEL": "1", "FAKE_SERIAL_FAIL": "s_bad"}, 1),  # (5, 1)
    ],
)
def test_an_empty_partition_is_not_a_failure_but_two_are(
    tmp_path: Path, env: dict[str, str], rc: int
) -> None:
    clone = parallel_clone(tmp_path)
    venv, log = recording_venv(tmp_path)
    got, out = run_gates(clone, venv, *TESTS_ONLY, GATES_WORKERS="2", FAKE_TOTAL="3", **env)
    assert got == rc, out
    assert len(pytest_calls(log)) == 2, "both passes run whatever the first returned"


@pytest.mark.parametrize(
    "env",
    [
        {"FAKE_NO_PARALLEL": "1", "FAKE_INTERRUPT": "serial"},  # (5, 2)
        {"FAKE_NO_SERIAL": "1", "FAKE_INTERRUPT": "parallel"},  # (2, 5)
    ],
)
def test_an_interrupted_pass_beside_an_empty_one_keeps_its_crash_code(
    tmp_path: Path, env: dict[str, str]
) -> None:
    # The empty pass (pytest 5) must not turn the other pass's 2 into a pass or a plain 1: the
    # step reports rc=2 whichever order the two ran in; gates itself exits 1 for a failed step.
    clone = parallel_clone(tmp_path)
    venv, log = recording_venv(tmp_path)
    got, out = run_gates(clone, venv, *TESTS_ONLY, GATES_WORKERS="2", FAKE_TOTAL="3", **env)
    assert got == 1, out
    assert "[tests] FAIL(rc=2)" in out, out
    assert len(pytest_calls(log)) == 2, "both passes run whatever the first returned"


def test_the_serial_pass_runs_and_counts_when_the_parallel_pass_fails(tmp_path: Path) -> None:
    clone = parallel_clone(tmp_path)
    venv, log = recording_venv(tmp_path)
    rc, out = run_gates(
        clone, venv, *TESTS_ONLY, GATES_WORKERS="2", FAKE_FAIL="tests/a.py::test_x", FAKE_TOTAL="3",
        FAKE_SERIAL_FAIL="s_bad",
    )  # fmt: skip
    assert rc == 1, out
    assert len(pytest_calls(log)) == 2, "the serial pass must run after a parallel failure"
    ids = out.split("FAILING TEST IDS", 1)[-1]
    assert "tests/a.py::test_x" in ids and "tests/s.py::s_bad" in ids, out  # both reds show


def test_a_failure_only_in_the_serial_pass_is_a_failing_id(tmp_path: Path) -> None:
    clone = parallel_clone(tmp_path)
    venv, _log = recording_venv(tmp_path)
    rc, out = run_gates(
        clone, venv, *TESTS_ONLY, GATES_WORKERS="2", FAKE_SERIAL_FAIL="s_bad", FAKE_TOTAL="3"
    )
    assert rc == 1, out
    assert "tests/s.py::s_bad" in out.split("FAILING TEST IDS", 1)[-1], out


# --- AT-10: a tree without the scrubber stays serial ---------------------------------------


def test_a_baseline_tree_without_the_scrubber_runs_serial_and_says_so(tmp_path: Path) -> None:
    clone = seeded_clone(tmp_path)
    scrubber = clone / "tests" / "_xdist_safe_reports.py"
    scrubber.unlink(missing_ok=True)  # origin/main predates the scrubber ...
    commit(clone, "main without the scrubber")
    at_main(clone)
    shutil.copy2(REPO / "tests" / "_xdist_safe_reports.py", scrubber)  # ... the branch adds it
    commit(clone, "branch adds the scrubber")
    venv, log = recording_venv(tmp_path)
    rc, out = run_gates(clone, venv, *TESTS_ONLY, "--baseline", GATES_WORKERS="2")
    assert rc == 0, out
    calls = pytest_calls(log)
    par = [c for c in calls if "-n" in c]
    assert len(par) == 1, calls  # the branch side only
    base_section = out.split("-- baseline --", 1)[1]
    assert "no tests/_xdist_safe_reports.py" in base_section and " -n " not in base_section, out


# --- AT-3: the passes partition the real selection -----------------------------------------


def collected_ids(expr: str, *targets: str) -> set[str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", "-o", "addopts=", "--strict-markers", "-m", expr, *targets],
        cwd=REPO, env=child_env(), capture_output=True, text=True, timeout=900, check=False,
    )  # fmt: skip
    assert proc.returncode in (0, 5), proc.stdout[-1500:] + proc.stderr[-1500:]
    return {ln for ln in proc.stdout.splitlines() if "::" in ln}


def test_the_two_passes_partition_the_real_selection(tmp_path: Path) -> None:
    """Take the two -m expressions from what gates.sh runs, then collect the real tree."""
    clone = parallel_clone(tmp_path)
    venv, log = recording_venv(tmp_path)
    rc, out = run_gates(clone, venv, *TESTS_ONLY, GATES_WORKERS="2")
    assert rc == 0, out
    par, ser = pytest_argvs(log)
    par_expr, ser_expr = (last_mark(c) for c in (par, ser))
    scope = (
        "tests/unit/scripts",
        "tests/unit/test_telemetry_exporter.py",
        "tests/e2e/run_stream/test_lazy_perf.py",
        "tests/e2e/cli_fmt/test_csv_target_speed.py",
    )
    parallel = collected_ids(par_expr, *scope)
    serial = collected_ids(ser_expr, *scope)
    everything = collected_ids("not serial or serial", *scope)
    assert serial, "no test carries the serial marker"
    assert parallel, "nothing left for the parallel pass"
    assert not parallel & serial, "a test would run in both passes"
    assert parallel | serial == everything


# --- AT-5: the reporter reads both JUnit files ---------------------------------------------

_CASES = (
    '<testcase classname="tests.test_a" name="test_ok" file="tests/test_a.py"/>'
    '<testcase classname="tests.test_a" name="test_bad" file="tests/test_a.py"><failure/></testcase>'
    '<testcase classname="tests.test_a" name="test_skip" file="tests/test_a.py"><skipped/></testcase>'
    '<testcase classname="tests.test_b.TestK" name="test_ok" file="tests/test_b.py"/>'
)
_SERIAL_CASES = (
    '<testcase classname="tests.test_s.TestS" name="test_timing" file="tests/test_s.py"><failure/></testcase>'
    '<testcase classname="tests.test_s.TestS" name="test_mem" file="tests/test_s.py"/>'
)


def _suite(cases: str, tests: int, failures: int, skipped: int) -> str:
    return (
        f'<testsuites><testsuite name="pytest" tests="{tests}" failures="{failures}" errors="0" '
        f'skipped="{skipped}">{cases}</testsuite></testsuites>'
    )


def _out_dir(root: Path, name: str, two_files: bool) -> Path:
    out = root / name
    out.mkdir()
    (out / "branch.steps").write_text("tests\t1\tpytest\n")
    (out / "meta").write_text("repo: decoy\n")
    if two_files:
        (out / "branch-tests.xml").write_text(_suite(_CASES, 4, 1, 1))
        (out / "branch-tests-serial.xml").write_text(_suite(_SERIAL_CASES, 2, 1, 0))
        (out / "branch-tests.log").write_text("1 failed, 1 passed, 1 skipped in 1.00s (0:00:01)\n")
        (out / "branch-tests-serial.log").write_text("1 failed, 1 passed in 0.50s\n")
    else:
        (out / "branch-tests.xml").write_text(_suite(_CASES + _SERIAL_CASES, 6, 2, 1))
        (out / "branch-tests.log").write_text("2 failed, 3 passed, 1 skipped in 1.50s\n")
    return out


def test_reporter_counts_are_identical_for_one_or_two_junit_files(tmp_path: Path) -> None:
    gr = report_module()
    one = _out_dir(tmp_path, "one", two_files=False)
    two = _out_dir(tmp_path, "two", two_files=True)
    assert gr.collected(one, "branch") == gr.collected(two, "branch") == 6
    assert gr.skipped(one, "branch") == gr.skipped(two, "branch") == 1
    assert gr._counts(one, "branch", "tests") == gr._counts(two, "branch", "tests")
    assert sorted(gr.junit_failing_ids(one, "branch")) == sorted(
        gr.junit_failing_ids(two, "branch")
    )
    assert gr.junit_failing_ids(two, "branch") == [
        "tests/test_a.py::test_bad",
        "tests/test_s.py::TestS::test_timing",
    ]
    assert gr.junit_failure_elements(one, "branch") == gr.junit_failure_elements(two, "branch") == 2
    assert gr.pytest_totals_failed(one, "branch") == gr.pytest_totals_failed(two, "branch") == 2
    assert gr.branch_only_steps(two) == gr.branch_only_steps(one) == ["tests"]


def test_suite_collected_sums_both_junit_files(tmp_path: Path) -> None:
    one = _out_dir(tmp_path, "one", two_files=False)
    two = _out_dir(tmp_path, "two", two_files=True)
    for out in (one, two):
        proc = subprocess.run(
            [sys.executable, str(DEV / "_gates_report.py"), "--suite-collected", str(out)],
            capture_output=True, text=True, timeout=60, check=False,
        )  # fmt: skip
        assert proc.stdout.strip() == "6", proc.stdout + proc.stderr


def test_reporter_reads_the_serial_junit_of_a_step(tmp_path: Path) -> None:
    """A serial-pass failure of any step with a `-serial.xml` shows in its counts and ids."""
    gr = report_module()
    out = tmp_path / "sentry"
    out.mkdir()
    (out / "branch.steps").write_text("sentry\t1\tpytest\n")
    (out / "branch-sentry.xml").write_text(
        _suite(_CASES.split('<testcase classname="tests.test_a" name="test_bad"')[0], 1, 0, 0)
    )
    (out / "branch-sentry-serial.xml").write_text(_suite(_SERIAL_CASES, 2, 1, 0))
    assert gr.failing_ids(out, "branch") == ["tests/test_s.py::TestS::test_timing"]
    assert gr._counts(out, "branch", "sentry").startswith("passed=2 failed=1")


def test_reporter_refuses_a_serial_log_without_a_totals_line(tmp_path: Path) -> None:
    two = _out_dir(tmp_path, "two", two_files=True)
    (two / "branch-tests-serial.log").write_text("Killed\n")
    assert report_module().pytest_totals_failed(two, "branch") is None


def test_a_written_baseline_stores_the_ids_of_both_passes(tmp_path: Path) -> None:
    clone = parallel_clone(tmp_path)
    venv, _log = recording_venv(tmp_path)
    dest = tmp_path / "base.json"
    rc, out = run_gates(
        clone, venv, *WHOLE, "--write-baseline", str(dest), GATES_WORKERS="2", FAKE_TOTAL="3",
        FAKE_FAIL="tests/a.py::test_x", FAKE_SERIAL_FAIL="s_bad",
    )  # fmt: skip
    assert rc == 1 and dest.exists(), out  # main has known failures, so the exit is still 1
    data = json.loads(dest.read_text())
    assert data["failing"] == ["tests/a.py::test_x", "tests/s.py::s_bad"]
    assert data["collected"] == 5 and data["workers"] == 2 and data["dist"] == "loadfile"


# --- AT-6, AT-7: real xdist -----------------------------------------------------------------


def _real_xdist(tmp_path: Path, body: str) -> Path:
    """Run `body` as one test file under a real `-n 2` and copy the JUnit file where the reporter
    expects it. Pinned to 2 workers so an outer `-n 4` run does not start 4 per worker."""
    pytest.importorskip("xdist")
    (tmp_path / "test_x.py").write_text(body)
    shutil.copy2(REPO / "tests" / "_xdist_safe_reports.py", tmp_path / "xdist_safe_reports.py")
    junit = tmp_path / "out.xml"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "xdist_safe_reports",
         "-q", "-n", "2", "-o", "junit_family=xunit1", f"--junitxml={junit}",
         "--rootdir", str(tmp_path), str(tmp_path / "test_x.py")],
        cwd=tmp_path, env=child_env() | {"PYTHONPATH": str(tmp_path)},
        capture_output=True, text=True, timeout=300, check=False,
    )  # fmt: skip
    assert proc.returncode == 1, proc.stdout + proc.stderr  # a failure, never a pass or a crash
    assert "INTERNALERROR" not in proc.stdout + proc.stderr
    out = tmp_path / "o"
    out.mkdir()
    shutil.copy(junit, out / "branch-tests.xml")
    return out


def test_a_worker_crash_is_a_failing_id_of_that_test(tmp_path: Path) -> None:
    out = _real_xdist(
        tmp_path, "import os\n\ndef test_ok():\n    pass\n\ndef test_dies():\n    os.abort()\n"
    )
    ids = report_module().junit_failing_ids(out, "branch")
    assert any(i.endswith("test_x.py::test_dies") for i in ids), ids


def test_a_lone_surrogate_in_a_failing_log_does_not_stop_the_run(tmp_path: Path) -> None:
    out = _real_xdist(
        tmp_path,
        "import logging\n\ndef test_ok():\n    pass\n\n"
        "def test_logs_it():\n    logging.getLogger('x').error('\\ud800')\n    assert False\n",
    )
    ids = report_module().junit_failing_ids(out, "branch")
    assert any(i.endswith("test_x.py::test_logs_it") for i in ids), ids


# --- AT-8: mode-bound baselines ---------------------------------------------------------------


def _write_parallel(clone: Path, venv: Path, dest: Path, *extra: str, **env: str):  # type: ignore[no-untyped-def]
    return run_gates(clone, venv, *WHOLE, "--write-baseline", str(dest), *extra, **env)


def test_a_parallel_baseline_records_workers_and_dist(tmp_path: Path) -> None:
    clone = parallel_clone(tmp_path)
    venv, _log = recording_venv(tmp_path)
    dest = tmp_path / "a.json"
    rc, out = _write_parallel(clone, venv, dest, GATES_WORKERS="2", FAKE_TOTAL="3")
    assert rc == 0, out
    data = json.loads(dest.read_text())
    assert (data["workers"], data["dist"], data["order"]) == (2, "loadfile", "collection")
    rc, out = run_gates(clone, venv, *WHOLE, "--baseline-file", str(dest), GATES_WORKERS="1")
    assert rc == 2 and "run mode differs in workers, dist" in out, out
    rc, out = run_gates(clone, venv, *WHOLE, "--baseline-file", str(dest), GATES_WORKERS="2")
    assert rc == 0, out


# --- AT-9: nested runs do not inherit the outer worker state (the helper's test is in
# tests/sentry/test_nested_env_single_copy.py) -----------------------------


def test_the_gates_harness_pins_one_worker_whatever_the_outer_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GATES_WORKERS", "4")
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw1")
    clone = parallel_clone(tmp_path)
    venv, log = recording_venv(tmp_path)
    rc, out = run_gates(clone, venv, *TESTS_ONLY)
    assert rc == 0, out
    (call,) = pytest_calls(log)
    assert "-n" not in call, call
    assert all("PYTEST_XDIST_WORKER" not in e for e in pytest_envs(log)), pytest_envs(log)


# --- AT-11: the outcomes file ----------------------------------------------------------------


def test_the_outcomes_file_lists_every_id_once_sorted_from_both_files(tmp_path: Path) -> None:
    two = _out_dir(tmp_path, "two", two_files=True)
    # A failure message the file must never carry: only ids and the four outcome words.
    xml = (
        (two / "branch-tests.xml")
        .read_text()
        .replace(
            "<failure/>", '<failure message="SECRET-VALUE-9f3a">trace SECRET-VALUE-9f3a</failure>'
        )
    )
    (two / "branch-tests.xml").write_text(xml)
    dest = tmp_path / "outcomes.txt"
    proc = subprocess.run(
        [sys.executable, str(DEV / "_gates_report.py"), str(two), "--outcomes-file", str(dest)],
        capture_output=True, text=True, timeout=60, check=False,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = dest.read_text().splitlines()
    assert lines == sorted(lines) and len(lines) == len(set(lines)) == 6, lines
    assert {ln.split("\t", 1)[0] for ln in lines} <= {"passed", "failed", "error", "skipped"}
    assert "failed\ttests/test_a.py::test_bad" in lines
    assert "skipped\ttests/test_a.py::test_skip" in lines
    assert "failed\ttests/test_s.py::TestS::test_timing" in lines, "the serial file is read too"
    assert "SECRET-VALUE" not in dest.read_text()


def test_the_outcomes_of_one_file_and_of_two_files_are_byte_equal(tmp_path: Path) -> None:
    files = []
    for name, two in (("one", False), ("two", True)):
        out = _out_dir(tmp_path, name, two_files=two)
        dest = tmp_path / f"{name}.txt"
        subprocess.run(
            [sys.executable, str(DEV / "_gates_report.py"), str(out), "--outcomes-file", str(dest)],
            capture_output=True, text=True, timeout=60, check=True,
        )  # fmt: skip
        files.append(dest.read_bytes())
    assert files[0] == files[1]


def test_gates_sh_passes_the_outcomes_file_to_the_reporter(tmp_path: Path) -> None:
    clone = parallel_clone(tmp_path)
    venv, _log = recording_venv(tmp_path)
    dest = tmp_path / "outcomes.txt"
    rc, out = run_gates(
        clone, venv, *TESTS_ONLY, "--outcomes-file", str(dest), GATES_WORKERS="2", FAKE_TOTAL="3"
    )
    assert rc == 0, out
    assert len(dest.read_text().splitlines()) == 4, dest.read_text()  # 3 plain + 1 serial


# --- AT-16: the temp root -------------------------------------------------------------------


def test_every_pass_has_a_basetemp_under_one_temp_root_that_is_removed(tmp_path: Path) -> None:
    clone = parallel_clone(tmp_path)
    venv, log = recording_venv(tmp_path)
    long_tmp = tmp_path / ("long-" * 12)
    long_tmp.mkdir()
    rc, out = run_gates(
        clone, venv, *TESTS_ONLY, GATES_WORKERS="2", FAKE_FAIL="tests/a.py::test_x", FAKE_TOTAL="3",
        TMPDIR=str(long_tmp),
    )  # fmt: skip
    assert rc == 1, out  # a red step still removes the root
    roots = set()
    for call in pytest_argvs(log):
        (base,) = (a.split("=", 1)[1] for a in call if a.startswith("--basetemp="))
        assert re.fullmatch(r"/tmp/gt\.[A-Za-z0-9]+/branch-tests(-serial)?", base), base
        roots.add(base.rsplit("/", 1)[0])
    (root,) = roots
    envs = pytest_envs(log)
    assert envs and all(e.get("PYTEST_DEBUG_TEMPROOT") == f"{root}/root" for e in envs), envs
    assert not Path(root).exists(), "the temp root outlived the run"
