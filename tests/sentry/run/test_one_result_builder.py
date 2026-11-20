"""G-RESULT-ONE-BUILDER: one place in `src/decoy/` builds the run result document.

The rule counts REFERENCES to four engine symbols, not calls and not binding forms:
`build_run_result`, `RunResult`, `RunResultRead` and `DeliveryFacts`.

- Outside `cli/run/_result.py` any reference is a violation: an import of the name, an
  attribute with that name (so `rr.build_run_result` with no call is caught), a bare name, or
  the name as a string (`getattr(m, "build_run_result")`), plus the `decoy-run-result/v1` tag
  and a star import of the engine's `run_result` package. A `functools.partial`, an alias, a
  rebinding or a tuple unpack all have to name the symbol, so all of them are seen.
- Inside the owner, `build_run_result` is referenced exactly once (the one call). A second
  reference of any kind (a partial, an assignment, a second call) is a violation.
  `DeliveryFacts` is referenced only inside `delivery_facts`, and the owner's real counts are
  pinned in `OWNER_REFERENCES`.

Allowed exceptions: none. The tree has no type-only use of these names outside the owner.

Named limit: a name built from parts at run time, and `importlib`, are invisible; the engine's
own sentry covers construction inside the engine. Lexical shadowing is not modelled.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"
OWNER = "cli/run/_result.py"
PROVIDER = "delivery_facts"
SCHEMA = "decoy-run-result/v1"
TRACKED = ("build_run_result", "RunResult", "RunResultRead", "DeliveryFacts")
ENGINE_PACKAGE = "decoy_engine.run_result"
# Allowed references outside the owner, each with its reason. Empty on purpose.
ALLOWED: dict[tuple[str, str], str] = {}
# The owner's real load-reference counts (imports are not loads).
OWNER_REFERENCES = {"build_run_result": 1, "RunResult": 0, "RunResultRead": 0, "DeliveryFacts": 2}


def _bound_names(tree: ast.Module) -> dict[str, str]:
    """Local name to tracked symbol for every `from m import x [as y]` of a tracked `x`."""
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for item in node.names:
                if item.name in TRACKED:
                    bound[item.asname or item.name] = item.name
    return bound


def _references(tree: ast.Module) -> list[tuple[str, ast.AST]]:
    """Every load reference to a tracked symbol: (symbol, node). Imports are not loads."""
    bound = _bound_names(tree)
    found: list[tuple[str, ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            symbol = bound.get(node.id, node.id if node.id in TRACKED else None)
            if symbol is not None:
                found.append((symbol, node))
        elif isinstance(node, ast.Attribute) and node.attr in TRACKED:
            found.append((node.attr, node))
        elif isinstance(node, ast.Constant) and node.value in TRACKED:
            found.append((str(node.value), node))
    return found


def violations(source: str, rel: str) -> list[str]:
    """Every breach of the rule in one module."""
    tree = ast.parse(source)
    found: list[str] = []
    refs = _references(tree)
    if rel != OWNER:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for item in node.names:
                    if item.name in TRACKED and (rel, item.name) not in ALLOWED:
                        found.append(f"{rel}:{node.lineno}: {item.name} imported")
                    if item.name == "*" and (node.module or "").startswith(ENGINE_PACKAGE):
                        found.append(f"{rel}:{node.lineno}: star import of the run result package")
        for symbol, node in refs:
            if (rel, symbol) not in ALLOWED:
                found.append(f"{rel}:{getattr(node, 'lineno', 0)}: {symbol} referenced")
    else:
        built = [n for s, n in refs if s == "build_run_result"]
        if len(built) > 1:
            found.append(f"{rel}: build_run_result referenced {len(built)} times")
        found.extend(_facts_outside_provider(tree, rel))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and SCHEMA in node.value:
            found.append(f"{rel}:{node.lineno}: the schema tag is spelled out")
    return found


def _facts_outside_provider(tree: ast.Module, rel: str) -> list[str]:
    found: list[str] = []

    def walk(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = (
                child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else scope
            )
            if scope != PROVIDER and _is_facts(child, tree):
                found.append(
                    f"{rel}:{getattr(child, 'lineno', 0)}: DeliveryFacts outside {PROVIDER}"
                )
            walk(child, inner)

    walk(tree, "")
    return found


def _is_facts(node: ast.AST, tree: ast.Module) -> bool:
    bound = _bound_names(tree)
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        return bound.get(node.id, node.id) == "DeliveryFacts"
    if isinstance(node, ast.Attribute):
        return node.attr == "DeliveryFacts"
    return isinstance(node, ast.Constant) and node.value == "DeliveryFacts"


def owner_counts(source: str) -> dict[str, int]:
    counts = dict.fromkeys(TRACKED, 0)
    for symbol, _node in _references(ast.parse(source)):
        counts[symbol] += 1
    return counts


def _scan() -> tuple[list[str], dict[str, int]]:
    out: list[str] = []
    counts: dict[str, int] = {}
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        text = path.read_text(encoding="utf-8")
        out.extend(violations(text, rel))
        if rel == OWNER:
            counts = owner_counts(text)
    return out, counts


def test_no_reference_outside_the_owner_and_one_build() -> None:
    out, counts = _scan()
    assert out == []
    assert counts["build_run_result"] == 1


def test_owner_reference_counts_are_pinned() -> None:
    _, counts = _scan()
    assert counts == OWNER_REFERENCES


def test_one_delivery_facts_provider() -> None:
    out, counts = _scan()
    assert not [line for line in out if "DeliveryFacts" in line]
    assert counts["DeliveryFacts"] >= 1, "the owner no longer builds delivery facts"


_MOD = "import decoy_engine.run_result as rr\n"


def test_seeded_second_builder_is_caught() -> None:
    assert violations("x = build_run_result(a=1)\n", "cli/run/_render.py")
    twice = "def f():\n    build_run_result(a=1)\n    build_run_result(a=2)\n"
    assert any("2 times" in v for v in violations(twice, OWNER))


def test_seeded_partial_is_caught_everywhere() -> None:
    owner = (
        "import functools\nfrom decoy_engine.run_result import build_run_result\n"
        "def f():\n    build_run_result(a=1)\n    p = functools.partial(build_run_result, a=2)\n"
    )
    assert any("2 times" in v for v in violations(owner, OWNER))
    partial = _MOD + "import functools\nb = functools.partial(rr.build_run_result, a=1)\n"
    assert violations(partial, "cli/run/_render.py")
    model = _MOD + "import functools\nm = functools.partial(rr.RunResult, a=1)\n"
    assert violations(model, "cli/run/_render.py")


def test_seeded_plain_second_reference_in_the_owner_is_caught() -> None:
    source = (
        "from decoy_engine.run_result import build_run_result as b\n"
        "def f():\n    b(a=1)\n    again = b\n"
    )
    assert any("2 times" in v for v in violations(source, OWNER))
    attr = _MOD + "def f():\n    rr.build_run_result(a=1)\n    keep = rr.build_run_result\n"
    assert any("2 times" in v for v in violations(attr, OWNER))


def test_seeded_attribute_reference_without_a_call_is_caught() -> None:
    assert violations(_MOD + "keep = rr.build_run_result\n", "cli/run/_render.py")
    assert violations(_MOD + "kind = rr.RunResultRead\n", "cli/x.py")
    assert violations(_MOD + "D = rr.DeliveryFacts\n", "cli/x.py")
    deep = "import a\nb = a.run_result.build_run_result\n"
    assert violations(deep, "cli/x.py")


def test_seeded_imports_names_and_strings_are_caught() -> None:
    assert violations("from decoy_engine.run_result import RunResult as R\n", "cli/x.py")
    assert violations("from decoy_engine.run_result import build_run_result as b\n", "cli/x.py")
    assert violations("from decoy_engine.run_result import *\n", "cli/x.py")
    assert violations("RunResult(a=1)\n", "cli/x.py")
    assert violations("RunResultRead.model_validate(d)\n", "cli/x.py")
    assert violations("getattr(m, 'build_run_result')\n", "cli/x.py")
    assert violations("tag = 'decoy-run-result/v1'\n", "cli/x.py")


def test_seeded_delivery_facts_outside_the_provider_are_caught() -> None:
    assert violations("DeliveryFacts('in_place', 'not_used', {})\n", OWNER)
    assert violations("x = DeliveryFacts.not_applicable()\n", "cli/run/_render.py")
    other = "def helper():\n    return DeliveryFacts.not_applicable()\n"
    assert violations(other, OWNER)
    aliased = "from m import DeliveryFacts as D\ndef helper():\n    return D()\n"
    assert violations(aliased, OWNER)


def test_the_provider_may_build_them() -> None:
    inside = (
        "def delivery_facts(ctx):\n"
        "    if ctx.rows:\n"
        "        return DeliveryFacts.not_applicable()\n"
        "    return DeliveryFacts('in_place', 'not_used', {})\n"
    )
    assert violations(inside, OWNER) == []
    one = "def f():\n    return build_run_result(a=1)\n"
    assert violations(one, OWNER) == []


def test_unrelated_names_are_not_flagged() -> None:
    assert violations("ScanSet.model_validate(d)\n", "cli/io/_scan_set.py") == []
    assert violations("from m import RunResultCollector\nRunResultCollector()\n", "cli/x.py") == []
