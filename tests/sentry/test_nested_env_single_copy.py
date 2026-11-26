"""The rule "a nested pytest or gates run drops the outer xdist state" has one home.

`tests/child_env.py` owns it. A second copy that spells the `PYTEST_XDIST_` prefix or the
`PYTEST_CURRENT_TEST` name is the next place a new variable gets forgotten, which shows up only
in the parallel T3 run. The scan reads the syntax tree, so quoting style and line breaks do not
hide a copy.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.child_env import child_env

TESTS = Path(__file__).resolve().parents[1]
OWNER = TESTS / "child_env.py"
NAMES = {"PYTEST_XDIST_", "PYTEST_CURRENT_TEST"}


def copies(root: Path, owner: Path) -> list[str]:
    found = []
    for path in sorted(root.rglob("*.py")):
        if path in (owner, Path(__file__).resolve()):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and node.value in NAMES:
                found.append(f"{path.relative_to(root)}:{node.lineno}")
    return found


def test_only_the_helper_spells_the_child_env_filter() -> None:
    assert OWNER.is_file()
    assert copies(TESTS, OWNER) == []


def test_a_nested_child_env_drops_the_outer_xdist_state() -> None:
    outer = {
        "PYTEST_XDIST_WORKER": "gw3",
        "PYTEST_XDIST_WORKER_COUNT": "4",
        "PYTEST_XDIST_TESTRUNUID": "abc",
        "PYTEST_CURRENT_TEST": "tests/x.py::t (call)",
        "PYTEST_DEBUG_TEMPROOT": "/tmp/gt.keep",
        "GATES_WORKERS": "4",
        "PATH": "/usr/bin",
    }
    keep = {"PYTEST_DEBUG_TEMPROOT": "/tmp/gt.keep", "GATES_WORKERS": "4", "PATH": "/usr/bin"}
    assert child_env(outer) == keep
    assert child_env(outer, drop_prefixes=("PYTEST_", "GATES_")) == {"PATH": "/usr/bin"}


def test_the_scan_sees_a_seeded_second_copy(tmp_path: Path) -> None:
    owner = tmp_path / "child_env.py"
    owner.write_text('DROP = "PYTEST_XDIST_"\n', encoding="utf-8")
    (tmp_path / "test_x.py").write_text(
        "def f(env):\n    return {k: v for k, v in env.items() if k != 'PYTEST_CURRENT_TEST'}\n",
        encoding="utf-8",
    )
    assert copies(tmp_path, owner) == ["test_x.py:2"]
