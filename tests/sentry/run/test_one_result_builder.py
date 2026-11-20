"""G-RESULT-ONE-BUILDER: one place in `src/decoy/` builds the run result document.

`build_run_result(` is called once, in `cli/run/_result.py`. Nothing else in `src/decoy/` builds a
`RunResult` or `RunResultRead` by hand, copies one, or spells the `decoy-run-result/v1` tag, and
every `DeliveryFacts` is built by the one provider `delivery_facts` in that module. A second
builder or a second delivery source would decide the status, the exit code or the delivery state
twice.

Named limit: a name built from parts at run time is invisible.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"
OWNER = "cli/run/_result.py"
PROVIDER = "delivery_facts"
SCHEMA = "decoy-run-result/v1"
MODEL_NAMES = {"RunResult", "RunResultRead"}
TRACKED = {"build_run_result", "DeliveryFacts", *MODEL_NAMES}
COPY_METHODS = {"model_construct", "model_validate", "model_copy"}


def _canon(node: ast.AST, table: dict[str, str]) -> str | None:
    """The canonical symbol an expression names.

    A bare name resolves through the alias table; an attribute chain names its last attribute,
    so `rr.build_run_result` and `a.b.build_run_result` are `build_run_result`. A bound method
    of a tracked class keeps its class (`RunResultRead.model_validate`,
    `DeliveryFacts.not_applicable`), so a rebinding of the method is still the method.
    `getattr(x, "name")` with a literal name is read the same way. Lexical shadowing and a name
    built at run time are a named limit.
    """
    if isinstance(node, ast.Name):
        return table.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        owner = _canon(node.value, table)
        if (owner in MODEL_NAMES and node.attr in COPY_METHODS) or (
            owner == "DeliveryFacts" and node.attr == "not_applicable"
        ):
            return f"{owner}.{node.attr}"
        return node.attr
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    ):
        owner = _canon(node.args[0], table)
        attr = node.args[1].value
        if (owner in MODEL_NAMES and attr in COPY_METHODS) or (
            owner == "DeliveryFacts" and attr == "not_applicable"
        ):
            return f"{owner}.{attr}"
        return attr
    return None


def _bind(target: ast.AST, value: ast.AST, table: dict[str, str]) -> bool:
    """Record `target = value` (names, tuple unpacking, walrus); True when the table grew."""
    if isinstance(target, ast.Name):
        canon = _canon(value, table)
        # Only tracked symbols are recorded, so a swap such as `a, b = b, a` cannot flip forever.
        if canon is not None and canon.split(".")[0] in TRACKED and table.get(target.id) != canon:
            table[target.id] = canon
            return True
    elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)):
        return any([_bind(t, v, table) for t, v in zip(target.elts, value.elts, strict=False)])
    return False


def _aliases(tree: ast.Module) -> dict[str, str]:
    """Local name to canonical symbol: `from m import x as y`, `y = x`, `y = mod.x`, chained and
    tuple assignments, annotated assignments and walrus bindings, to a fixed point.

    `import m as n` needs no entry: `n.x` already names the canonical `x` by attribute.
    """
    table: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for item in node.names:
                table[item.asname or item.name] = item.name
    changed, passes = True, 0
    while changed and passes < 10:
        changed, passes = False, passes + 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    changed |= _bind(target, node.value, table)
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                changed |= _bind(node.target, node.value, table)
            elif isinstance(node, ast.NamedExpr):
                changed |= _bind(node.target, node.value, table)
    return table


def _name(node: ast.AST, table: dict[str, str]) -> str | None:
    return _canon(node, table)


def builder_violations(source: str, rel: str) -> list[str]:
    found: list[str] = []
    calls = 0
    tree = ast.parse(source)
    table = _aliases(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.alias) and "build_run_result" in node.name and rel != OWNER:
            found.append(f"{rel}: build_run_result imported outside _result.py")
        if isinstance(node, ast.Call):
            callee = _name(node.func, table)
            if callee == "build_run_result":
                calls += 1
                if rel != OWNER:
                    found.append(f"{rel}:{node.lineno}: build_run_result( outside _result.py")
            if callee in MODEL_NAMES:
                found.append(f"{rel}:{node.lineno}: {callee}( built by hand")
            if callee is not None and callee.split(".")[0] in MODEL_NAMES and "." in callee:
                found.append(f"{rel}:{node.lineno}: {callee} on a run result model")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and SCHEMA in node.value:
            found.append(f"{rel}:{node.lineno}: the schema tag is spelled out")
    if calls > 1:
        found.append(f"{rel}: build_run_result( called {calls} times")
    return found


def delivery_violations(source: str, rel: str) -> list[str]:
    """Every `DeliveryFacts(` and `DeliveryFacts.not_applicable(` outside `delivery_facts`,
    by canonical name, so an aliased import or a rebinding is counted the same."""
    found: list[str] = []
    tree = ast.parse(source)
    table = _aliases(tree)

    def walk(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = (
                child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else scope
            )
            if isinstance(child, ast.alias) and child.name == "DeliveryFacts" and rel != OWNER:
                found.append(f"{rel}: DeliveryFacts imported outside _result.py")
            if isinstance(child, ast.Call):
                callee = _name(child.func, table)
                if callee in ("DeliveryFacts", "DeliveryFacts.not_applicable") and (
                    rel,
                    scope,
                ) != (OWNER, PROVIDER):
                    found.append(f"{rel}:{child.lineno}: DeliveryFacts built outside {PROVIDER}")
            walk(child, inner)

    walk(tree, "")
    return found


def _scan() -> tuple[list[str], int, int]:
    out: list[str] = []
    builds = provides = 0
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        text = path.read_text(encoding="utf-8")
        out.extend(builder_violations(text, rel))
        out.extend(delivery_violations(text, rel))
        if rel == OWNER:
            builds = text.count("build_run_result(")
            provides = text.count("DeliveryFacts")
    return out, builds, provides


def test_one_result_builder() -> None:
    out, builds, _ = _scan()
    assert out == []
    assert builds == 1, "the owner no longer calls the engine builder once"


def test_one_delivery_facts_provider() -> None:
    out, _, provides = _scan()
    assert not [line for line in out if "DeliveryFacts" in line]
    assert provides >= 1, "the owner no longer builds delivery facts"


def test_seeded_second_builder_is_caught() -> None:
    assert builder_violations("x = build_run_result(a=1)\n", "cli/run/_render.py")
    twice = "build_run_result(a=1)\nbuild_run_result(a=2)\n"
    assert builder_violations(twice, OWNER)


def test_seeded_hand_built_models_are_caught() -> None:
    assert builder_violations("RunResult(a=1)\n", "cli/x.py")
    assert builder_violations("m.RunResultRead(a=1)\n", "cli/x.py")
    assert builder_violations("RunResult.model_construct(a=1)\n", "cli/x.py")
    assert builder_violations("RunResultRead.model_validate(d)\n", "cli/x.py")
    assert builder_violations("RunResult.model_copy()\n", "cli/x.py")
    assert builder_violations("tag = 'decoy-run-result/v1'\n", "cli/x.py")


def test_seeded_import_alias_is_caught() -> None:
    alias = "from decoy_engine.run_result import build_run_result as b\n"
    assert builder_violations(alias, "cli/run/_render.py")
    assert delivery_violations(
        "from decoy_engine.run_result import DeliveryFacts as D\n", "cli/run/_render.py"
    )


def test_seeded_aliased_calls_are_counted_by_canonical_name() -> None:
    owner_twice = (
        "from decoy_engine.run_result import build_run_result as b\n"
        "def f():\n    b(a=1)\n    b(a=2)\n"
    )
    assert any("called 2 times" in v for v in builder_violations(owner_twice, OWNER))
    other = "from decoy_engine.run_result import build_run_result as b\nb(a=1)\n"
    assert any("outside" in v for v in builder_violations(other, "cli/run/_render.py"))
    rebound = "b = build_run_result\nb(a=1)\nb(a=2)\n"
    assert any("called 2 times" in v for v in builder_violations(rebound, OWNER))


def test_seeded_aliased_models_and_facts_are_caught() -> None:
    model = "from decoy_engine.run_result import RunResult as R\nR(a=1)\n"
    assert any("built by hand" in v for v in builder_violations(model, "cli/x.py"))
    read = "from m import RunResultRead as R\nR.model_validate(d)\n"
    assert any("model_validate" in v for v in builder_violations(read, "cli/x.py"))
    facts = "from m import DeliveryFacts as D\nD('in_place', 'not_used', {})\nD.not_applicable()\n"
    assert len([v for v in delivery_violations(facts, "cli/run/_render.py") if "built" in v]) == 2
    module_attr = "import decoy_engine.run_result as rr\nrr.build_run_result(a=1)\n"
    assert builder_violations(module_attr, "cli/run/_render.py")


_MOD = "import decoy_engine.run_result as rr\n"


def test_seeded_module_attribute_rebindings_are_counted() -> None:
    build = _MOD + "b = rr.build_run_result\nb(a=1)\nb(a=2)\n"
    assert any("called 2 times" in v for v in builder_violations(build, OWNER))
    assert any(
        "outside" in v for v in builder_violations(_MOD + "b = rr.build_run_result\nb()\n", "x")
    )
    deep = "import a\nb = a.run_result.build_run_result\nb()\n"
    assert any("outside" in v for v in builder_violations(deep, "cli/x.py"))
    for name in ("RunResult", "RunResultRead"):
        for where in (OWNER, "cli/x.py"):
            built = _MOD + f"R = rr.{name}\nR(a=1)\n"
            assert any("built by hand" in v for v in builder_violations(built, where))
            copied = _MOD + f"R = rr.{name}\nm = R.model_validate\nm(d)\nR.model_copy()\n"
            assert any("model_validate" in v for v in builder_violations(copied, where))
    facts = (
        _MOD + "D = rr.DeliveryFacts\nD('in_place', 'not_used', {})\nna = D.not_applicable\nna()\n"
    )
    assert len(delivery_violations(facts, "cli/x.py")) == 2
    assert len(delivery_violations(facts, OWNER)) == 2


def test_seeded_other_binding_forms_are_counted() -> None:
    forms = [
        "from m import build_run_result as b\nc = b\nc()\n",
        "import m\nb: object = m.build_run_result\nb()\n",
        "import m\nx, b = 1, m.build_run_result\nb()\n",
        "import m\nb = c = m.build_run_result\nc()\n",
        "import m\nif (b := m.build_run_result):\n    b()\n",
        "import m\nb = getattr(m, 'build_run_result')\nb()\n",
    ]
    for source in forms:
        assert any("outside" in v for v in builder_violations(source, "cli/x.py")), source
    twice = "import m\nb = m.build_run_result\nc = b\nc()\nb()\n"
    assert any("called 2 times" in v for v in builder_violations(twice, OWNER))


def test_unrelated_validate_is_not_flagged() -> None:
    assert builder_violations("ScanSet.model_validate(d)\n", "cli/io/_scan_set.py") == []


def test_seeded_delivery_facts_outside_the_provider_are_caught() -> None:
    assert delivery_violations("DeliveryFacts('in_place', 'not_used', {})\n", "cli/run/_render.py")
    assert delivery_violations("x = DeliveryFacts.not_applicable()\n", "cli/run/_render.py")
    other = "def helper():\n    return DeliveryFacts.not_applicable()\n"
    assert delivery_violations(other, OWNER)


def test_the_provider_may_build_them() -> None:
    inside = (
        "def delivery_facts(ctx):\n"
        "    if ctx.rows:\n"
        "        return DeliveryFacts.not_applicable()\n"
        "    return DeliveryFacts('in_place', 'not_used', {})\n"
    )
    assert delivery_violations(inside, OWNER) == []
