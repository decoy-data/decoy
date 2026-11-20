"""G-RUN-ONE-EXIT: one module under `src/decoy/cli/run/` writes the envelope and ends the run.

`emit_json(` and every form that ends the process appear only in `cli/run/_result.py` (the
`emit` and `finish` functions). Every other module raises a typed refusal or calls
`_result.finish`, so the exit integer of a run is the integer in its document.

Covered exit forms, matched by what the name resolves to through the module's imports:
`typer.Exit`, `typer.Abort`, `click.exceptions.Exit`, `click.exceptions.Abort`, `click.Abort`,
`SystemExit`, and a call of `sys.exit` or the `exit` builtin; each raised or called, bare or
constructed, and reached through `from typer import Exit`, an `as` alias or a module alias
(`import sys as s; s.exit(1)`, `import typer as t; raise t.Exit()`). A bare re-raise inside
`except typer.Exit` is not a new exit and is not matched.

Named limit: `getattr` and `importlib` are invisible.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"
PKG = "cli/run/"
OWNER = "cli/run/_result.py"
EXIT_FORMS = frozenset(
    {
        "typer.Exit",
        "typer.Abort",
        "click.Abort",
        "click.exceptions.Exit",
        "click.exceptions.Abort",
        "SystemExit",
        "sys.exit",
        "exit",
    }
)
RAISE_ONLY = frozenset({"typer.Exit", "typer.Abort", "click.Abort", "SystemExit"})
EMIT = "emit_json"


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
    base = bound.get(node.id, node.id)
    return ".".join([base, *reversed(parts)])


def _canon(name: str) -> str:
    # `typer` re-exports Click's classes; `click.exceptions.X` and `click.X` are one name.
    return name.replace("click.exceptions.Abort", "click.Abort")


def violations(source: str, rel: str) -> list[str]:
    """Every breach of the rule in one module, as `rel:line: what`."""
    if rel == OWNER or not rel.startswith(PKG):
        return []
    tree = ast.parse(source)
    bound = _bindings(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and node.exc is not None:
            target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            name = _dotted(target, bound)
            if name is not None and _canon(name) in EXIT_FORMS | {"click.exceptions.Exit"}:
                found.append(f"{rel}:{node.lineno}: raises {name}")
        elif isinstance(node, ast.Call):
            name = _dotted(node.func, bound)
            if name is None:
                continue
            if name.endswith(EMIT) and name.split(".")[-1] == EMIT:
                found.append(f"{rel}:{node.lineno}: calls {EMIT}")
            elif name in {"sys.exit", "exit"}:
                found.append(f"{rel}:{node.lineno}: calls {name}")
    return found


def _scan() -> list[str]:
    out: list[str] = []
    for path in sorted((SRC / "cli" / "run").glob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        out.extend(violations(path.read_text(encoding="utf-8"), rel))
    return out


def test_no_exit_or_envelope_outside_the_owner() -> None:
    assert _scan() == []


def test_the_owner_ends_the_run() -> None:
    text = (SRC / OWNER).read_text(encoding="utf-8")
    assert "emit_json(" in text
    assert "raise typer.Exit(" in text


R = "cli/run/_flow.py"


def test_seeded_shapes_are_caught() -> None:
    cases = [
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
    ]
    for source in cases:
        assert violations(source, R), source


def test_the_owner_and_other_code_are_not_flagged() -> None:
    assert violations("import typer\nraise typer.Exit(code=1)\n", OWNER) == []
    assert violations("import typer\nraise typer.Exit(code=1)\n", "cli/gate/_run.py") == []
    reraise = "import typer\ntry:\n    pass\nexcept typer.Exit:\n    raise\n"
    assert violations(reraise, R) == []
    assert (
        violations("from decoy.ui.output import emit_error\nemit_error(s, 'run', 'm')\n", R) == []
    )
