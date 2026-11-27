"""Parallel-safety sentry (CLI-PAR S1): a test that needs the whole host is marked `serial`.

`gates.sh` and CI run `serial` tests alone after the parallel pass. Two checks run on one real
collection of the suite (a scrubbed subprocess, cached per session):

1. an AST scan finds tests that assert a wall-clock bound, a memory envelope, a speedup ratio, an
   absolute thread count, a fixed port, an in-process rlimit, or that list the checkout's
   untracked files; any such test without the mark must be on the shrink-only allowlist
   (`baselines/serial-resources.json`);
2. every test the required-serial registry names must carry the mark at collection.

Ported from the engine's tests/sentry/parallel/test_serial_resources.py (ENGINE-PAR P2); the
scanner is `_serial_resources.py`, loaded by path like the engine's helper.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from tests.child_env import child_env
from tests.sentry._ratchet import load_allowlist
from tests.sentry.tooling import gate_args

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "required_serial.toml"
GATES = ROOT / "scripts" / "dev" / "gates.sh"


def _load_scanner():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "_serial_resources", HERE / "_serial_resources.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses resolve string annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


res = _load_scanner()


def collect_suite(
    root: Path, expr: str | None, dump_dir: Path, target: str = "tests"
) -> dict[str, list[dict[str, object]]]:
    """Collect `target` under `root` in a clean subprocess and return the dump plugin's report."""
    out = dump_dir / "dump.json"
    out.unlink(missing_ok=True)
    env = child_env(drop_prefixes=("PYTEST_",))
    env[res.DUMP_ENV] = str(out)
    env["PYTHONPATH"] = os.pathsep.join([str(HERE), env.get("PYTHONPATH", "")])
    cmd = [
        sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
        "-p", "no:xdist", "-p", "_serial_resources", "-o", "addopts=",
        *(("-m", expr) if expr else ()), target,
    ]  # fmt: skip
    proc = subprocess.run(
        cmd, cwd=root, env=env, capture_output=True, text=True, timeout=900, check=False
    )
    assert out.exists(), f"collection wrote no dump (rc {proc.returncode}): {proc.stdout[-800:]}"
    data = json.loads(out.read_text())
    out.unlink()
    return data


def as_items(data: dict[str, list[dict[str, object]]]) -> list[object]:
    return [res.Collected(**i) for i in data["items"]]  # type: ignore[arg-type]


@pytest.fixture(scope="session")
def suite(tmp_path_factory: pytest.TempPathFactory) -> dict[str, list[dict[str, object]]]:
    expr = gate_args.marker_expr(GATES.read_text(encoding="utf-8"))
    return collect_suite(ROOT, expr, tmp_path_factory.mktemp("serial-dump"))


# --- the one reader of gates.sh's `-m` expression -------------------------------------------


def test_the_real_gates_line_has_no_marker_filter_and_the_passes_are_plain() -> None:
    text = GATES.read_text(encoding="utf-8")
    assert gate_args.marker_expr(text) is None
    assert gate_args.pass_expressions(text) == ("not serial", "serial")


@pytest.mark.parametrize(
    ("text", "expr", "passes"),
    [
        ("PYTEST_ARGS=()\n", None, ("not serial", "serial")),
        ("PYTEST_ARGS=(  # nothing yet\n)\n", None, ("not serial", "serial")),
        (
            "PYTEST_ARGS=(-m 'not slow')\n",
            "not slow",
            ("(not slow) and not serial", "(not slow) and serial"),
        ),
        (
            "PYTEST_ARGS=(\n  -m 'a and b'  # why\n  --strict-markers\n)\n",
            "a and b",
            ("(a and b) and not serial", "(a and b) and serial"),
        ),
    ],
)
def test_the_marker_reader_handles_empty_and_present_arrays(
    text: str, expr: str | None, passes: tuple[str, str]
) -> None:
    assert gate_args.marker_expr(text) == expr
    assert gate_args.pass_expressions(text) == passes


@pytest.mark.parametrize(
    "text",
    [
        "# no array at all\n",
        "PYTEST_ARGS=(-m)\n",  # -m with no expression
        "PYTEST_ARGS=(-m '')\n",  # an empty expression
        "PYTEST_ARGS=(-m '  ')\n",
    ],
)
def test_the_marker_reader_refuses_a_malformed_declaration(text: str) -> None:
    with pytest.raises(ValueError, match="PYTEST_ARGS"):
        gate_args.marker_expr(text)


def test_the_shell_reader_keeps_a_quoted_token_whole_and_skips_comments() -> None:
    text = "X=1\nSENTRY_PATHS=(\n  tests/sentry  # dir\n  # whole line\n  'a b'\n)\n"
    assert gate_args.shell_array("SENTRY_PATHS", text) == ["tests/sentry", "a b"]
    assert gate_args.shell_array("MISSING", text) is None


# --- the two checks on the real collection --------------------------------------------------


def unverifiable(data: dict[str, list[dict[str, object]]]) -> dict[str, str]:
    return {str(e["file"]): str(e["reason"]) for e in [*data["skipped"], *data["errors"]]}


def registry_ids(text: str) -> list[str]:
    return [row["id"] for row in tomllib.loads(text).get("serial", [])]


def test_every_host_resource_test_is_serial_or_allowlisted(
    suite: dict[str, list[dict[str, object]]],
) -> None:
    scanner = res.Scanner(ROOT)

    def scan(item: object) -> frozenset[object]:
        path = ROOT / item.source  # type: ignore[attr-defined]
        if not item.source or not path.is_file():  # type: ignore[attr-defined]
            assert not item.qualname, f"no source file for {item.nodeid}"  # type: ignore[attr-defined]
            return frozenset()
        return scanner.hits(path, item.qualname)  # type: ignore[attr-defined,no-any-return]

    failures, stale = res.resource_failures(
        as_items(suite), scan, set(load_allowlist("serial-resources"))
    )
    assert failures == [], "\n".join(failures[:40])
    assert stale == [], "allowlist rows no longer needed (drop them):\n" + "\n".join(stale)


def test_the_required_serial_registry_is_marked(suite: dict[str, list[dict[str, object]]]) -> None:
    failures, unverified = res.unmarked_registry_entries(
        registry_ids(REGISTRY.read_text()), as_items(suite), unverifiable(suite)
    )
    problems = res.registry_problems(
        failures, unverified, bool(os.environ.get("DECOY_GATE_VENV_STRICT"))
    )
    assert problems == [], "\n".join(problems)


def test_the_registry_names_the_known_whole_host_tests() -> None:
    ids = set(registry_ids(REGISTRY.read_text()))
    assert {
        "tests/e2e/first_user/journey/test_cli_journey.py",
        "tests/e2e/run_stream/test_lazy_perf.py",
        "tests/e2e/cli_fmt/test_csv_target_speed.py",
        "tests/unit/test_telemetry_exporter.py::test_flush_black_hole_is_bounded",
        "tests/e2e/test_ci_staged_scan.py::test_git_timeout_is_a_runtime_failure_not_a_clean_scan",
        "tests/e2e/test_run_otel.py::test_dead_collector_keeps_exit_code_and_bounds_exit",
    } <= ids


def test_strict_mode_turns_an_entry_whose_file_skips_at_collection_red() -> None:
    skipped = {"tests/x/test_gone.py": "could not import module"}
    failures, unverified = res.unmarked_registry_entries(
        ["tests/x/test_gone.py::test_a"], [], skipped
    )
    assert failures == [] and len(unverified) == 1
    assert res.registry_problems(failures, unverified, strict=False) == []
    strict = res.registry_problems(failures, unverified, strict=True)
    assert len(strict) == 1 and "tests/x/test_gone.py::test_a" in strict[0]


def test_the_registry_only_grows() -> None:
    base = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "origin/main", "HEAD"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if base.returncode != 0:
        pytest.skip("no origin/main merge base")
    old = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{base.stdout.strip()}:{REGISTRY.relative_to(ROOT)}"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if old.returncode != 0:
        return  # the registry is new on this branch
    current = tomllib.loads(REGISTRY.read_text())
    cur = {
        "serial": [r["id"] for r in current.get("serial", [])],
        "removed": [f"{r['id']}|{r.get('reason', '')}" for r in current.get("removed", [])],
    }
    assert res.removed_without_reason(set(registry_ids(old.stdout)), cur) == []


# --- seeded bypasses: each spelling in the plan's mutation list is caught -------------------


def scan_text(tmp_path: Path, body: str, name: str = "test_x.py", qual: str | None = None):  # type: ignore[no-untyped-def]
    (tmp_path / name).write_text(body)
    scanner = res.Scanner(tmp_path)
    funcs = scanner.module(tmp_path / name).funcs
    names = [qual] if qual else [q for q, fn in funcs.items() if fn.name.startswith("test")]
    return frozenset().union(*(scanner.hits(tmp_path / name, q) for q in names))


@pytest.mark.parametrize(
    ("body", "kind"),
    [
        (
            "import time\ndef test_t():\n    t=time.perf_counter()\n    assert time.perf_counter()-t < 2.0\n",
            "clock",
        ),
        (
            "from time import perf_counter_ns as pc\ndef test_t():\n    t=pc()\n    elapsed=pc()-t\n    assert elapsed < 5\n",
            "clock",
        ),
        (
            "import time as tm\ndef test_t():\n    t0=tm.monotonic()\n    d=tm.monotonic()-t0\n    assert d < 1\n",
            "clock",
        ),
        (
            "import pytest\nBOUND_S=3\ndef test_t():\n    wall=1\n    if wall > BOUND_S:\n        pytest.fail('x')\n",
            "clock",
        ),
        (
            "import unittest\nclass T(unittest.TestCase):\n    def test_t(self):\n        elapsed=1\n        self.assertLess(elapsed, 1.0)\n",
            "clock",
        ),
        (
            "import resource\ndef test_t():\n    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss\n    assert rss < 10\n",
            "memory",
        ),
        ("def test_t(ev):\n    assert ev.suspected_memory_pressure == 1\n", "memory"),
        ("import threading\ndef test_t():\n    assert threading.active_count() == 3\n", "threads"),
        (
            "import socket\ndef test_t():\n    s=socket.socket()\n    s.bind(('127.0.0.1', 8080))\n",
            "port",
        ),
        (
            "import resource\ndef test_t():\n    resource.setrlimit(resource.RLIMIT_AS, (1, 1))\n",
            "rlimit",
        ),
        (  # Guard 4: the tracked-and-untracked file lister, run in the checkout
            "import subprocess\nfrom pathlib import Path\nROOT = Path('.')\n"
            "def test_t():\n    subprocess.run(['git', 'ls-files', '-z', '--cached', '--others'], cwd=ROOT, check=True)\n",
            "untracked",
        ),
        (  # no cwd: the process cwd, which is the checkout under pytest
            "import subprocess\ndef test_t():\n    subprocess.run(['git', 'ls-files', '--others'])\n",
            "untracked",
        ),
        (  # a git helper that takes the arguments as words
            "def git(*a): ...\ndef test_t(repo):\n    git('ls-files', '--others', '--exclude-standard', cwd=repo)\n",
            "untracked",
        ),
    ],
)
def test_the_scan_catches_each_spelling(tmp_path: Path, body: str, kind: str) -> None:
    assert kind in {h.kind for h in scan_text(tmp_path, body)}


def test_the_scan_ignores_a_child_rlimit_and_port_zero(tmp_path: Path) -> None:
    body = (
        "import resource, socket, subprocess\n"
        "def test_t():\n"
        "    subprocess.run(['x'], preexec_fn=lambda: resource.setrlimit(1, (1, 1)))\n"
        "    socket.socket().bind(('127.0.0.1', 0))\n"
    )
    assert scan_text(tmp_path, body) == frozenset()


def test_the_scan_ignores_a_lister_in_a_scratch_repo_and_a_plain_git_call(tmp_path: Path) -> None:
    body = (
        "import subprocess\n"
        "def test_t(tmp_path):\n"
        "    subprocess.run(['git', 'ls-files', '--others'], cwd=tmp_path / 'scratch')\n"
        "    subprocess.run(['git', 'ls-files', '--cached'])\n"
        "    subprocess.run(['git', 'status'])\n"
    )
    assert scan_text(tmp_path, body) == frozenset()


def test_the_scan_follows_a_helper_module_and_a_local_call(tmp_path: Path) -> None:
    (tmp_path / "tests" / "connectors").mkdir(parents=True)
    (tmp_path / "tests" / "connectors" / "_x.py").write_text(
        "def finished(run):\n    assert run['wall'] < 3\n"
    )
    body = (
        "from tests.connectors import _x\n"
        "def _check(run):\n    _x.finished(run)\n"
        "def test_t():\n    _check({})\n"
    )
    assert scan_text(tmp_path, body, qual="test_t") != frozenset()


@pytest.mark.parametrize(
    ("helper_path", "import_line"),
    [
        ("tests/shared.py", "from tests import shared as h"),  # tests/*.py
        ("tests/unit/sub/_h.py", "from tests.unit.sub import _h as h"),  # tests/**/_*.py
        ("tests/unit/sub/_bare.py", "import _bare as h"),  # a bare `_name` beside the test
    ],
)
def test_the_scan_follows_every_helper_naming_the_cli_uses(
    tmp_path: Path, helper_path: str, import_line: str
) -> None:
    helper = tmp_path / helper_path
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text("def finished(run):\n    assert run['wall'] < 3\n")
    test = tmp_path / "tests" / "unit" / "sub" / "test_t.py"
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text(f"{import_line}\ndef test_t():\n    h.finished({{}})\n")
    scanner = res.Scanner(tmp_path)
    assert {h.kind for h in scanner.hits(test, "test_t")} == {"clock"}


def test_an_unmarked_caller_of_a_helper_is_flagged_not_exempted_with_the_helper(
    tmp_path: Path,
) -> None:
    """A helper on the allowlist's side still has its callers judged one by one."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "_timing.py").write_text("def bound(run):\n    assert run['wall'] < 3\n")
    (tmp_path / "tests" / "test_a.py").write_text(
        "from tests import _timing\n"
        "def test_marked():\n    _timing.bound({})\n"
        "def test_unmarked():\n    _timing.bound({})\n"
    )
    scanner = res.Scanner(tmp_path)
    items = [
        res.Collected("tests/test_a.py::test_marked", "tests/test_a.py", "test_marked", True),
        res.Collected("tests/test_a.py::test_unmarked", "tests/test_a.py", "test_unmarked", False),
    ]
    failures, _stale = res.resource_failures(
        items, lambda i: scanner.hits(tmp_path / i.source, i.qualname), set()
    )
    assert [f.split(":")[0] for f in failures] == ["tests/test_a.py"], failures
    assert "test_unmarked" in failures[0] and "test_marked" not in failures[0]


# --- judging: mutations of the marks and of the registry -----------------------------------


def item(nodeid: str, serial: bool, qual: str = "test_t", source: str = "tests/x.py") -> object:
    return res.Collected(nodeid, source, qual, serial)


def test_an_unmarked_registry_test_is_red() -> None:
    items = [item("tests/connectors/test_gcs_timeouts.py::test_a[1]", False)]
    fail, _ = res.unmarked_registry_entries(
        ["tests/connectors/test_gcs_timeouts.py::test_a"], items, {}
    )
    assert fail


def test_a_misspelled_registry_id_is_red() -> None:
    items = [item("tests/a.py::test_a", True)]
    fail, unverified = res.unmarked_registry_entries(["tests/a.py::test_aa"], items, {})
    assert fail and not unverified


def test_a_registry_id_in_a_skipped_file_is_unverified_not_green() -> None:
    fail, unverified = res.unmarked_registry_entries(
        ["tests/a.py::test_a"], [], {"tests/a.py": "needs x"}
    )
    assert not fail and unverified == ["tests/a.py::test_a: needs x"]


def test_a_dropped_serial_directory_is_red() -> None:
    items = [item("tests/perf/test_p.py::test_p", False)]
    fail, _ = res.unmarked_registry_entries(["tests/perf/"], items, {})
    assert fail


def test_a_seeded_unmarked_clock_bound_is_a_failure_off_the_allowlist() -> None:
    failures, _ = res.resource_failures(
        [item("tests/a.py::test_t", False)], lambda _i: frozenset({res.Hit("clock", 3)}), set()
    )
    assert failures and "clock" in failures[0] and "tests/a.py::test_t" in failures[0]


def test_a_stale_allowlist_row_is_reported() -> None:
    _fail, stale = res.resource_failures(
        [item("tests/a.py::t", True)], lambda _i: frozenset(), {"tests/x.py::gone"}
    )
    assert stale == ["tests/x.py::gone"]


def test_removing_a_registry_id_needs_a_reason() -> None:
    cur = {"serial": ["a"], "removed": ["b|"]}
    assert res.removed_without_reason({"a", "b"}, cur) == ["b"]
    cur = {"serial": ["a"], "removed": ["b|moved into a directory prefix"]}
    assert res.removed_without_reason({"a", "b"}, cur) == []


# --- the collection hook and the real marks -------------------------------------------------


def test_a_conftest_pytestmark_does_not_mark_a_directory(tmp_path: Path) -> None:
    """A pytestmark in a conftest is ignored by pytest, so only the collection hook can mark."""
    d = tmp_path / "scratch"
    d.mkdir()
    (d / "conftest.py").write_text("import pytest\npytestmark = pytest.mark.serial\n")
    (d / "test_s.py").write_text("def test_s():\n    rss = 1\n    assert rss < 5\n")
    (tmp_path / "pytest.ini").write_text("[pytest]\nmarkers = serial: x\n")
    (tmp_path / "out").mkdir()
    data = collect_suite(tmp_path, "not benchmark", tmp_path / "out", "scratch")
    assert [i["serial"] for i in data["items"]] == [False]


def test_the_collection_hook_marks_every_item_under_a_serial_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests import conftest

    class FakeItem:
        def __init__(self, rel: str) -> None:
            self.path = ROOT / rel
            self.nodeid = f"{rel}::t"
            self.marks: list[object] = []

        def add_marker(self, mark: object) -> None:
            self.marks.append(mark)

    monkeypatch.setattr(conftest, "SERIAL_DIRS", ("tests/slowdir",))
    inside, outside = FakeItem("tests/slowdir/test_a.py"), FakeItem("tests/slowdir2/test_b.py")
    conftest.pytest_collection_modifyitems(None, [inside, outside])  # type: ignore[arg-type]
    assert len(inside.marks) == 1 and outside.marks == []
