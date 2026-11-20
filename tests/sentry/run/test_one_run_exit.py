"""G-RUN-ONE-EXIT: one module writes the envelope of a `decoy run` and ends it.

`emit_json(`, `emit_error(` and every form that ends the process appear only in
`cli/run/_result.py` (`emit`, `finish`, `report_error`, `finish_error`). Every other module
raises a typed refusal or calls `_result.finish`, so the exit integer of a run is the integer in
its document.

Scope: every module that can end `decoy run`: all of `cli/run/` (recursive), the `--all`
fan-out `cli/project/_run_all.py`, and `cli/io/`, whose helpers the run calls (a helper that
exits there is a second exit path beside the choke point; the two listed io functions serve
other commands, not `decoy run`). The `--all` summary has no single run and so no
document; its two functions are the reasoned, shrink-only entries of `run-exit-owners.json`. Each
entry pins the exact exits and writer calls its function holds (`hits`), so one more call inside a
listed function fails too. A stale entry fails, so the list only shrinks.

Covered forms, matched by what the name resolves to through the module's imports:
`typer.Exit`, `typer.Abort`, `click.Abort`, `click.exceptions.Exit`, `click.exceptions.Abort`,
`SystemExit` (each raised, bare or constructed), a call of `sys.exit` or the `exit` builtin,
and a call of `emit_json` or `emit_error`; reached through `from typer import Exit`, an `as`
alias or a module alias (`import sys as s; s.exit(1)`, `import typer as t; raise t.Exit()`).
A bare re-raise inside `except typer.Exit` is not a new exit and is not matched.

Named limit: `getattr` and `importlib` are invisible.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from tests.sentry._ratchet import load_allowlist

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"
OWNER = "cli/run/_result.py"
RUN_ALL = "cli/project/_run_all.py"
EXIT_FORMS = frozenset(
    {
        "typer.Exit",
        "typer.Abort",
        "click.Abort",
        "click.exceptions.Exit",
        "click.exceptions.Abort",
        "SystemExit",
    }
)
CALL_FORMS = frozenset({"sys.exit", "exit"})
WRITERS = ("emit_json", "emit_error")


def in_scope(rel: str) -> bool:
    return (rel.startswith(("cli/run/", "cli/io/")) or rel == RUN_ALL) and rel != OWNER


def _bindings(tree: ast.Module) -> dict[str, str]:
    """Local name to the dotted path it stands for, from `import` and `from ... import`."""
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                bound[item.asname or item.name.split(".")[0]] = (
                    item.name if item.asname else item.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            for item in node.names:
                bound[item.asname or item.name] = f"{node.module}.{item.name}"
    return bound


def _dotted(node: ast.AST, bound: dict[str, str]) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return ".".join([bound.get(node.id, node.id), *reversed(parts)])


def _hits(source: str) -> list[tuple[str, int, str]]:
    """`(enclosing function, line, what)` for every exit form and writer call in the source."""
    tree = ast.parse(source)
    bound = _bindings(tree)
    found: list[tuple[str, int, str]] = []

    def walk(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = (
                child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else scope
            )
            if isinstance(child, ast.Raise) and child.exc is not None:
                target = child.exc.func if isinstance(child.exc, ast.Call) else child.exc
                name = _dotted(target, bound)
                if name in EXIT_FORMS:
                    found.append((scope, child.lineno, f"raises {name}"))
            elif isinstance(child, ast.Call):
                name = _dotted(child.func, bound)
                if name in CALL_FORMS:
                    found.append((scope, child.lineno, f"calls {name}"))
                elif name is not None and name.split(".")[-1] in WRITERS:
                    found.append((scope, child.lineno, f"calls {name.split('.')[-1]}"))
            walk(child, inner)

    walk(tree, "")
    return found


def violations(
    source: str, rel: str, allowed: Mapping[str, Sequence[str]] | None = None
) -> list[str]:
    """Every breach in one module beyond the pinned `hits` of an allowlisted `file::function`."""
    if not in_scope(rel):
        return []
    budget = {key: Counter(hits) for key, hits in (allowed or {}).items()}
    out: list[str] = []
    for scope, line, what in _hits(source):
        left = budget.get(f"{rel}::{scope}")
        if left is not None and left[what] > 0:
            left[what] -= 1
            continue
        out.append(f"{rel}:{line}: {what} in {scope or '<module>'}")
    return out


def _modules() -> list[Path]:
    return [
        *sorted((SRC / "cli" / "run").rglob("*.py")),
        *sorted((SRC / "cli" / "io").rglob("*.py")),
        SRC / RUN_ALL,
    ]


def _allowed() -> dict[str, list[str]]:
    return {key: list(entry["hits"]) for key, entry in load_allowlist("run-exit-owners").items()}


def test_no_exit_or_writer_outside_the_owner() -> None:
    out: list[str] = []
    for path in _modules():
        rel = path.relative_to(SRC).as_posix()
        out.extend(violations(path.read_text(encoding="utf-8"), rel, _allowed()))
    assert out == []


def test_the_scope_reaches_every_run_module() -> None:
    rels = {p.relative_to(SRC).as_posix() for p in _modules()}
    assert RUN_ALL in rels
    assert "cli/io/_integrity_report.py" in rels
    assert {"cli/run/_flow.py", "cli/run/_errors.py", "cli/run/__init__.py"} <= rels
    assert all(p.exists() for p in _modules())


def test_the_allowlist_only_shrinks() -> None:
    live: set[str] = set()
    for path in _modules():
        rel = path.relative_to(SRC).as_posix()
        if rel == OWNER:
            continue
        live |= {f"{rel}::{scope}" for scope, _, _ in _hits(path.read_text(encoding="utf-8"))}
    assert set(_allowed()) - live == set(), "stale allowlist entries: remove them"


def test_the_owner_ends_the_run() -> None:
    text = (SRC / OWNER).read_text(encoding="utf-8")
    assert "emit_json(" in text
    assert "emit_error(" in text
    assert "raise typer.Exit(" in text


R = "cli/run/_flow.py"
SEEDED = [
    "import typer\nraise typer.Exit(code=1)\n",
    "import typer\nraise typer.Exit\n",
    "import typer\nraise typer.Abort()\n",
    "from typer import Exit\nraise Exit(code=2)\n",
    "from typer import Exit as E\nraise E()\n",
    "import typer as t\nraise t.Exit()\n",
    "import click\nraise click.exceptions.Exit(1)\n",
    "from click.exceptions import Exit\nraise Exit(1)\n",
    "import click\nraise click.Abort()\n",
    "raise SystemExit(1)\n",
    "import sys\nsys.exit(1)\n",
    "import sys as s\ns.exit(1)\n",
    "from sys import exit as leave\nleave(1)\n",
    "from decoy.ui.output import emit_json\nemit_json(state, {})\n",
    "from decoy.ui.output import emit_json as out\nout(state, {})\n",
    "import decoy.ui.output as o\no.emit_json(state, {})\n",
    "from decoy.ui.output import emit_error\nemit_error(state, 'run', 'm')\n",
    "from decoy.ui.output import emit_error as err\nerr(state, 'run', 'm')\n",
    "import decoy.ui.output as o\no.emit_error(state, 'run', 'm')\n",
]


def test_seeded_shapes_are_caught_in_every_scoped_module() -> None:
    for rel in (R, "cli/run/__init__.py", "cli/run/sub/_x.py", "cli/io/_x.py", RUN_ALL):
        for source in SEEDED:
            assert violations(source, rel), (rel, source)


def test_a_new_function_in_run_all_is_not_covered_by_the_allowlist() -> None:
    allowed = {f"{RUN_ALL}::run_all": ["calls emit_error"]}
    source = (
        "from decoy.ui.output import emit_error\ndef other(s):\n    emit_error(s, 'run', 'm')\n"
    )
    assert violations(source, RUN_ALL, allowed)
    listed = source.replace("def other", "def run_all")
    assert violations(listed, RUN_ALL, allowed) == []


def test_the_owner_and_other_code_are_not_flagged() -> None:
    assert violations(SEEDED[0], OWNER) == []
    assert violations(SEEDED[0], "cli/gate/_run.py") == []
    assert violations(SEEDED[0], "cli/project/_list.py") == []
    reraise = "import typer\ntry:\n    pass\nexcept typer.Exit:\n    raise\n"
    assert violations(reraise, R) == []


def test_one_more_call_inside_a_listed_function_is_caught() -> None:
    allowed = {f"{RUN_ALL}::run_all": ["calls emit_error"]}
    once = (
        "from decoy.ui.output import emit_error\ndef run_all(s):\n    emit_error(s, 'run', 'm')\n"
    )
    assert violations(once, RUN_ALL, allowed) == []
    twice = once + "    emit_error(s, 'run', 'n')\n"
    assert violations(twice, RUN_ALL, allowed)
