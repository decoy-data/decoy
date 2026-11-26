"""Hypothesis keeps its files out of the checkout: one fresh storage root per pytest process.

CLI-PAR S1 (H14). `tests/conftest.py` gives every pytest process its own storage directory, so a
parallel worker, a nested run or a plain `pytest` never writes `.hypothesis/` at the repo root,
where the untracked-file scanners in tests/sentry/release would meet files that appear and vanish
between their listing and their read.

The children below load the real root conftest as a plugin (`-p tests.conftest`) and run a
property test against a fresh source module, which makes Hypothesis build its constants cache
(cold discovery) and write to its example database while the child is still alive."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from _gates_harness import GIT, REPO, child_env

_SOURCE = "FRESH_CONSTANT = 7919\nFRESH_TEXT = 'cold-constants-probe'\n\n\ndef f(x):\n    return x + FRESH_CONSTANT\n"

_CHILD = """\
import json
import os
from pathlib import Path

from hypothesis import given, settings, strategies as st

import fresh_src

CHECKOUT = Path({repo!r})


@given(st.integers(), st.text())
def prop(x, s):
    fresh_src.f(x)


def test_child():
    prop()
    root = Path(os.environ["HYPOTHESIS_STORAGE_DIRECTORY"])
    settings.default.database.save(b"decoy-probe-key", b"decoy-probe-value")
    consts = root / "constants"
    examples = root / "examples"
    report = {{
        "root": str(root),
        "constants": sorted(p.name for p in consts.rglob("*") if p.is_file()),
        "constants_nonempty": any(p.stat().st_size > 0 for p in consts.rglob("*") if p.is_file()),
        "examples_written": any(p.is_file() for p in examples.rglob("*")),
        "checkout_has_hypothesis": (CHECKOUT / ".hypothesis").exists(),
    }}
    Path(os.environ["CHILD_REPORT"]).write_text(json.dumps(report))
"""


def run_child(
    tmp_path: Path, name: str, shared_parent: Path | None, worker: str | None
) -> tuple[dict[str, object], subprocess.CompletedProcess[str]]:
    work = tmp_path / name
    work.mkdir()
    (work / "fresh_src.py").write_text(_SOURCE)
    (work / "test_child.py").write_text(_CHILD.format(repo=str(REPO)))
    env = child_env() | {"PYTHONPATH": os.pathsep.join([str(work), str(REPO)])}
    env["CHILD_REPORT"] = str(work / "report.json")
    for var in ("PYTEST_DEBUG_TEMPROOT", "PYTEST_XDIST_WORKER", "HYPOTHESIS_STORAGE_DIRECTORY"):
        env.pop(var, None)
    if shared_parent is not None:
        env["PYTEST_DEBUG_TEMPROOT"] = str(shared_parent)
    if worker is not None:
        env["PYTEST_XDIST_WORKER"] = worker
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "tests.conftest",
         "-p", "no:xdist", "-q", "--rootdir", str(work), str(work / "test_child.py")],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=300, check=False,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-1500:] + proc.stderr[-1500:]
    return json.loads((work / "report.json").read_text()), proc


def checkout_hypothesis_listing() -> list[str] | None:
    folder = REPO / ".hypothesis"
    if not folder.exists():
        return None
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*"))


def test_each_process_gets_its_own_storage_root_outside_the_checkout(tmp_path: Path) -> None:
    shared = tmp_path / "gates-temp-root"
    before = checkout_hypothesis_listing()
    runs = [
        run_child(tmp_path, "a", shared, "gw0")[0],
        run_child(tmp_path, "b", shared, "gw0")[0],  # the same worker label as `a`
        run_child(tmp_path, "c", shared, None)[0],
        run_child(tmp_path, "plain", None, None)[0],  # no gates temp root: the system temp dir
    ]
    roots = [Path(str(r["root"])) for r in runs]
    assert len({str(r) for r in roots}) == 4, roots
    for r, root in zip(runs, roots, strict=True):
        assert REPO not in (root, *root.parents), root
        assert r["constants_nonempty"], f"no constants cache written under {root}"
        assert r["examples_written"], f"no example database write under {root}"
        assert r["checkout_has_hypothesis"] is (before is not None), "the checkout changed mid-run"
        assert not root.exists(), f"the storage root outlived its process: {root}"
    for root in roots[:3]:
        assert root.parent == shared
    assert roots[0].name.startswith("decoy-hyp-gw0-") and roots[1].name.startswith("decoy-hyp-gw0-")
    assert roots[2].name.startswith("decoy-hyp-main-")
    assert checkout_hypothesis_listing() == before, "a child wrote .hypothesis into the checkout"


@pytest.mark.skipif(GIT is None, reason="needs git")
def test_the_checkout_ignores_the_hypothesis_folder() -> None:
    for path in (".hypothesis/examples/x", ".hypothesis/constants/y"):
        proc = subprocess.run(
            [str(GIT), "check-ignore", "-q", path],
            cwd=REPO, capture_output=True, text=True, check=False,
        )  # fmt: skip
        assert proc.returncode == 0, f"`.hypothesis/` must be in .gitignore ({path})"


def test_a_test_level_database_still_wins_over_the_profile(tmp_path: Path) -> None:
    from hypothesis import settings
    from hypothesis.database import DirectoryBasedExampleDatabase

    mine = DirectoryBasedExampleDatabase(tmp_path / "mine")

    @settings(database=mine)
    def probe() -> None: ...

    assert probe._hypothesis_internal_use_settings.database is mine  # type: ignore[attr-defined]
    assert settings.default.database is not mine
