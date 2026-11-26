"""CI lane sentry (CI-L1b): every CLI workflow job, marker and test folder has an automatic lane.

The real tree is the negative control; each seeded case edits a deep copy of it and asserts its own
finding. The rules and their differences from the engine copy are in
tests/sentry/tooling/_ci_lanes.py. Acceptance items 12 to 15 of the CI-L1 handoff are marked.
"""

from __future__ import annotations

import copy
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from tests.sentry.tooling import _ci_lanes as lanes

TREE = lanes.load()


def seeded() -> lanes.Tree:
    return copy.deepcopy(TREE)


def job(tree: lanes.Tree, wf: str, key: str) -> dict[str, Any]:
    return tree.workflows[wf]["jobs"][key]


def pytest_steps(tree: lanes.Tree) -> list[dict[str, Any]]:
    return [s for s in job(tree, "ci.yml", "pytest")["steps"] if "pytest" in s.get("run", "")]


def par_step(tree: lanes.Tree) -> dict[str, Any]:
    (step,) = [s for s in pytest_steps(tree) if "not serial" in s["run"]]
    return step


def ser_step(tree: lanes.Tree) -> dict[str, Any]:
    (step,) = [s for s in pytest_steps(tree) if "-m serial" in s["run"]]
    return step


def with_on(doc: dict[Any, Any], on: Any) -> dict[Any, Any]:
    """The workflow with its triggers replaced. YAML 1.1 parses the `on:` key as True."""
    out = {k: v for k, v in doc.items() if k not in (True, "on")}
    out[True] = on
    return out


def has(found: list[str], text: str) -> bool:
    return any(text in f for f in found)


def test_real_tree_has_no_findings() -> None:
    assert lanes.findings(TREE) == []


# --- item 12: the merge tier matches the workflows in both directions ----------------------


def test_required_jobs_match_workflows() -> None:
    t = seeded()
    ci = t.workflows["ci.yml"]["jobs"]
    ci["ruff-renamed"] = ci.pop("ruff")
    found = lanes.findings(t)
    assert has(found, "R2 ci.yml:ruff: merge job does not exist")
    assert has(found, "R3 ci.yml:ruff-renamed")
    t = seeded()
    t.workflows["ci.yml"]["jobs"]["extra"] = {"runs-on": "ubuntu-latest", "timeout-minutes": 1}
    assert has(lanes.findings(t), "R3 ci.yml:extra")
    t = seeded()
    t.required["merge"][0]["jobs"].remove("pytest")
    assert has(lanes.findings(t), "R3 ci.yml:pytest")


def test_matrix_must_be_the_supported_pythons() -> None:
    t = seeded()
    job(t, "ci.yml", "pytest")["strategy"]["matrix"]["python"].append("3.13")
    assert has(lanes.findings(t), "R2 ci.yml:pytest: merge job has a templated name")
    t = seeded()
    job(t, "ci.yml", "pytest")["name"] = "pytest ${{ matrix.os }}"
    assert has(lanes.findings(t), "R2 ci.yml:pytest")
    t = seeded()
    job(t, "ci.yml", "ruff")["name"] = "ruff ${{ github.ref }}"
    assert has(lanes.findings(t), "R2 ci.yml:ruff")


def test_merge_job_rules() -> None:
    t = seeded()
    job(t, "ci.yml", "ruff")["if"] = "always()"
    assert has(lanes.findings(t), "R2 ci.yml:ruff: merge job has an `if`")
    t = seeded()
    job(t, "ci.yml", "ruff")["runs-on"] = ["self-hosted", "x"]
    assert has(lanes.findings(t), "is self-hosted")
    t = seeded()
    t.required["merge"].append({"workflow": "release-smoke.yml", "jobs": ["fresh-install"]})
    assert has(lanes.findings(t), "R2 release-smoke.yml: merge workflow has no pull")


def test_registry_schema_is_closed() -> None:
    cases: list[tuple[str, lanes.Tree]] = []
    t = seeded()
    t.unlaned["path_filter"][0]["extra"] = 1
    cases.append(("keys", t))
    t = seeded()
    t.unlaned["path_filter"][0]["reason"] = " "
    cases.append(("non-empty", t))
    t = seeded()
    t.unlaned["path_filter"].append(dict(t.unlaned["path_filter"][0]))
    cases.append(("duplicate", t))
    t = seeded()
    t.required["bogus"] = []
    cases.append(("unknown table", t))
    for text, tree in cases:
        assert has(lanes.findings(tree), "R1"), text
        assert has(lanes.findings(tree), text), text


# --- item 13: markers and workflow triggers ------------------------------------------------


def test_new_deselected_marker_needs_a_lane_or_an_unlaned_entry() -> None:
    t = seeded()
    ini = t.pyproject["tool"]["pytest"]["ini_options"]
    ini["markers"] = ["slowx: x"]
    ini["addopts"] = '-m "not slowx"'
    assert has(lanes.findings(t), "M2 marker 'slowx'")
    t.unlaned["marker"] = [{"name": "slowx", "reason": "test"}]
    assert lanes.findings(t) == []


def test_unreadable_expression_is_no_lane() -> None:
    t = seeded()
    job(t, "ci.yml", "pytest")["steps"] = [{"run": 'pytest tests -m "a + b"'}]
    assert has(lanes.findings(t), "M4 ci.yml:pytest")


@pytest.mark.parametrize(
    "run",
    [
        "pytest -m x tests/unit",
        "python -m pytest -mx tests/unit",
        "pytest -qm x tests/unit",
        "pytest -xvmx tests/unit",
        "uv run --frozen pytest -m y -m x tests/unit",
        'bash -c "pytest -m x tests/unit"',
        "FOO=1 pytest tests/unit \\\n  -m x --tb=short",
    ],
)
def test_spellings_are_read_as_the_lane(run: str) -> None:
    t = seeded()
    job(t, "ci.yml", "pytest")["steps"] = [{"run": run}]
    (lane,) = [ln for ln in lanes.lanes(t) if ln.job == "pytest"]
    assert lane.expr == "x" and lane.paths == ("tests/unit",) and not lane.bad


def test_workflow_without_automatic_trigger_needs_an_unlaned_entry() -> None:
    t = seeded()
    t.workflows["release-smoke.yml"] = with_on(
        t.workflows["release-smoke.yml"], {"workflow_dispatch": None}
    )
    assert has(lanes.findings(t), "T1 release-smoke.yml: no automatic trigger")
    t.unlaned["workflow"] = [{"file": "release-smoke.yml", "reason": "x"}]
    assert not has(lanes.findings(t), "T1")
    t.unlaned["workflow"].append({"file": "ci.yml", "reason": "x"})
    assert has(lanes.findings(t), "T1 ci.yml: has an automatic trigger")


def test_path_filter_needs_its_named_exception() -> None:
    t = seeded()
    t.unlaned["path_filter"] = []
    assert has(lanes.findings(t), "T2 regen-diagrams.yml: path filter on push")
    t = seeded()
    t.workflows["ci.yml"] = with_on(t.workflows["ci.yml"], {"pull_request": {"paths": ["src/**"]}})
    assert has(lanes.findings(t), "T2 ci.yml")
    t = seeded()
    t.unlaned["path_filter"].append({"file": "gone.yml", "reason": "x"})
    assert has(lanes.findings(t), "'gone.yml' does not exist")
    t = seeded()
    del lanes._on(t.workflows["regen-diagrams.yml"])["push"]["paths"]
    assert has(lanes.findings(t), "T2 path_filter workflow 'regen-diagrams.yml' has no path filter")


def test_timeout_and_concurrency_rules() -> None:
    t = seeded()
    del job(t, "ci.yml", "ruff")["timeout-minutes"]
    assert has(lanes.findings(t), "T3 ci.yml:ruff")
    t = seeded()
    del t.workflows["ci.yml"]["concurrency"]
    assert has(lanes.findings(t), "T4 ci.yml: pull_request workflow lacks")


# --- item 14: test paths and the daily cron ------------------------------------------------


def test_lanes_collect_every_test_folder() -> None:
    assert TREE.test_dirs == ["tests/e2e", "tests/sentry", "tests/unit"]
    t = seeded()
    steps = job(t, "ci.yml", "pytest")["steps"]
    job(t, "ci.yml", "pytest")["steps"] = [s for s in steps if "pytest" not in s.get("run", "")]
    assert has(lanes.findings(t), "P1 tests/e2e: no automatic pytest lane")


def test_ignored_file_must_run_in_another_job() -> None:
    t = seeded()
    t = replace(t, scripts={k: v.replace("test_import_layers", "x") for k, v in t.scripts.items()})
    assert has(lanes.findings(t), "--ignore tests/sentry/layout/test_import_layers.py")
    t = seeded()
    del t.workflows["ci.yml"]["jobs"]["layers-gate"]
    assert has(lanes.findings(t), "runs in no other job")


@pytest.mark.parametrize(
    "extra",
    [
        "--ignore-glob=tests/e2e/**",
        "--ignore-glob 'tests/e2e/**'",
        "--deselect=tests/e2e",
        "--deselect tests/e2e/test_x.py::test_y",
    ],
)
def test_other_exclusions_must_run_in_another_job(extra: str) -> None:
    t = seeded()
    step = par_step(t)
    step["run"] += f" {extra}"
    assert has(lanes.findings(t), "runs in no other job"), extra


@pytest.mark.parametrize("extra", ["-k smoke", "-ksmoke", "-qk smoke", "-qksmoke", "-xvk smoke"])
def test_name_filter_fails_closed(extra: str) -> None:
    t = seeded()
    step = par_step(t)
    step["run"] += f" {extra}"
    assert has(lanes.findings(t), "P1 ci.yml:pytest: -k smoke narrows"), extra


def test_deselected_node_counts_as_its_file() -> None:
    """P1 reads a deselected node as its file, which runs in the layers job. M5 still objects to
    the extra option, because the passes no longer match gates.sh."""
    t = seeded()
    par_step(t)["run"] += " --deselect tests/sentry/layout/test_import_layers.py::test_x"
    assert not has(lanes.findings(t), "P1")


def test_yaml_workflows_are_read(tmp_path: Path) -> None:
    for d in (".github", "ci", "scripts"):
        shutil.copytree(lanes.ROOT / d, tmp_path / d)
    shutil.copy(lanes.ROOT / "pyproject.toml", tmp_path)
    (tmp_path / "tests").symlink_to(lanes.ROOT / "tests")
    flow = (
        "on: workflow_dispatch\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps: [{run: echo}]\n"
    )
    (tmp_path / ".github/workflows/bypass.yaml").write_text(flow)
    found = lanes.findings(lanes.load(tmp_path))
    assert has(found, "T1 bypass.yaml") and has(found, "T3 bypass.yaml:a"), found


def test_ci_cron_is_daily() -> None:
    crons = [e["cron"] for e in lanes._on(TREE.workflows["ci.yml"])["schedule"]]
    assert crons and all(c.split()[2:] == ["*", "*", "*"] for c in crons), crons


# --- item 15: the drift canary is the one reported, unrequired scheduled lane -------------


def test_drift_canary_is_reported_once_and_not_required() -> None:
    assert lanes.reported(TREE) == [("release-smoke.yml", "fresh-install")]
    t = seeded()
    t.required["merge"].append({"workflow": "release-smoke.yml", "jobs": ["fresh-install"]})
    assert has(lanes.findings(t), "not one reported, unrequired lane")
    t = seeded()
    (site,) = [s for s in t.policy["engine_site"] if s["kind"] == "drift-canary"]
    site["reason"] = ""
    assert has(lanes.findings(t), "drift canary has no reason")


# --- M5: the two-pass split in ci.yml is the one gates.sh builds -------------------------------

PAR = 'pytest tests -m "not serial" -n 4 --dist loadfile --ignore=tests/sentry/layout/test_import_layers.py --tb=short'
SER = "pytest tests -m serial --ignore=tests/sentry/layout/test_import_layers.py --tb=short"


def m5(found: list[str]) -> bool:
    return has(found, "M5")


def test_gates_builds_the_two_passes_the_ci_split_mirrors() -> None:
    by_mark = {a[a.index("-m") + 1]: a for a in map(list, TREE.gates_argvs)}
    assert sorted(by_mark) == ["not serial", "serial"], TREE.gates_argvs
    par, ser = by_mark["not serial"], by_mark["serial"]
    assert par[par.index("-n") + 1] == "4" and par[par.index("--dist") + 1] == "loadfile"
    assert "-n" not in ser and "--dist" not in ser
    assert "--ignore=tests/sentry/layout/test_import_layers.py" in par + ser
    assert par[-1] == ser[-1] == "tests"


def test_the_ci_passes_are_whole_suite_lanes_and_loadfile_is_no_path() -> None:
    ours = [ln for ln in lanes.lanes(TREE) if (ln.workflow, ln.job) == ("ci.yml", "pytest")]
    assert len(ours) == 2 and all(ln.whole_suite and ln.paths == ("tests",) for ln in ours)
    assert sorted(ln.expr for ln in ours) == ["not serial", "serial"]


def test_dropping_the_serial_step_is_red_for_the_serial_marker_and_the_split() -> None:
    t = seeded()
    steps = job(t, "ci.yml", "pytest")["steps"]
    steps.remove(ser_step(t))
    found = lanes.findings(t)
    assert has(found, "M1 marker 'serial'") and m5(found), found


def test_a_single_unfiltered_lane_is_not_the_split() -> None:
    t = seeded()
    steps = job(t, "ci.yml", "pytest")["steps"]
    steps.remove(ser_step(t))
    par_step(t)["run"] = (
        "pytest tests --ignore=tests/sentry/layout/test_import_layers.py --tb=short"
    )
    assert m5(lanes.findings(t))


@pytest.mark.parametrize(
    ("which", "old", "new"),
    [
        ("par", " --ignore=tests/sentry/layout/test_import_layers.py", ""),  # one pass drops it
        ("ser", " --ignore=tests/sentry/layout/test_import_layers.py", ""),
        ("par", " --tb=short", " --tb=short tests/unit"),  # one pass adds a path
        ("ser", "pytest tests", "pytest tests tests/e2e"),
        ("par", '-m "not serial"', '-m "not slow"'),  # not gates.sh's expression
        ("ser", "-m serial", '-m "serial or slow"'),
        ("par", "-n 4", "-n 2"),  # a changed worker value
        ("par", "-n 4", ""),  # no workers at all
        ("par", " --dist loadfile", ""),  # omitted distribution
        ("par", "--dist loadfile", "--dist load"),  # changed distribution
        ("ser", "--ignore=", "-n 4 --dist loadfile --ignore="),  # the serial pass runs parallel
        ("par", " --tb=short", " --tb=short -x"),  # an option only one pass has
    ],
)
def test_a_ci_split_that_differs_from_gates_sh_is_red(which: str, old: str, new: str) -> None:
    t = seeded()
    step = par_step(t) if which == "par" else ser_step(t)
    assert old in step["run"], (old, step["run"])
    step["run"] = step["run"].replace(old, new, 1)
    assert m5(lanes.findings(t)), step["run"]


def test_the_serial_step_must_run_after_a_red_parallel_pass() -> None:
    t = seeded()
    assert ser_step(t)["if"] == "${{ !cancelled() }}"
    for bad in (None, "always()", "${{ success() }}", "${{ !cancelled() && true }}"):
        t = seeded()
        if bad is None:
            del ser_step(t)["if"]
        else:
            ser_step(t)["if"] = bad
        assert m5(lanes.findings(t)), bad
    t = seeded()
    par_step(t)["if"] = "${{ !cancelled() }}"  # the parallel pass is not conditional
    assert m5(lanes.findings(t))


@pytest.mark.parametrize(
    "spelling",
    [
        "-n 4 --dist loadfile",
        "-n4 --dist loadfile",
        "-n=4 --dist loadfile",
        "--numprocesses 4 --dist loadfile",
        "--numprocesses=4 --dist=loadfile",
        "--dist=loadfile -n 4",
        "--dist loadfile -n4",
    ],
)
def test_equivalent_spellings_of_the_worker_and_dist_options_agree(spelling: str) -> None:
    t = seeded()
    par_step(t)["run"] = par_step(t)["run"].replace("-n 4 --dist loadfile", spelling)
    assert lanes.findings(t) == [], spelling


def test_a_gates_only_drift_is_red_even_when_both_ci_passes_agree() -> None:
    for i, old, new in (
        (0, "4", "3"),  # gates.sh builds the parallel pass with another worker count
        (0, "loadfile", "load"),
        (0, "--ignore=tests/sentry/layout/test_import_layers.py", "--ignore=tests/other.py"),
        (1, "serial", "serial or slow"),
    ):
        argvs = [list(a) for a in TREE.gates_argvs]
        argvs[i] = [new if a == old else a for a in argvs[i]]
        t = replace(seeded(), gates_argvs=tuple(tuple(a) for a in argvs))
        assert m5(lanes.findings(t)), (i, old, new)


def test_a_gates_sh_that_builds_one_pass_is_red() -> None:
    t = replace(seeded(), gates_argvs=TREE.gates_argvs[:1])
    assert m5(lanes.findings(t))
    assert m5(lanes.findings(replace(seeded(), gates_argvs=())))
