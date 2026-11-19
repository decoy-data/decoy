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
COPY_METHODS = {"model_construct", "model_validate", "model_copy"}


def _name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _receiver(node: ast.Attribute) -> str | None:
    return _name(node.value)


def builder_violations(source: str, rel: str) -> list[str]:
    found: list[str] = []
    calls = 0
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.alias) and "build_run_result" in node.name and rel != OWNER:
            found.append(f"{rel}: build_run_result imported outside _result.py")
        if isinstance(node, ast.Call):
            callee = _name(node.func)
            if callee == "build_run_result":
                calls += 1
                if rel != OWNER:
                    found.append(f"{rel}:{node.lineno}: build_run_result( outside _result.py")
            if callee in MODEL_NAMES:
                found.append(f"{rel}:{node.lineno}: {callee}( built by hand")
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in COPY_METHODS
                and _receiver(node.func) in MODEL_NAMES
            ):
                found.append(f"{rel}:{node.lineno}: {node.func.attr} on a run result model")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and SCHEMA in node.value:
            found.append(f"{rel}:{node.lineno}: the schema tag is spelled out")
    if calls > 1:
        found.append(f"{rel}: build_run_result( called {calls} times")
    return found


def delivery_violations(source: str, rel: str) -> list[str]:
    """Every `DeliveryFacts(` and `DeliveryFacts.not_applicable(` outside `delivery_facts`."""
    found: list[str] = []

    def walk(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = (
                child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else scope
            )
            if isinstance(child, ast.alias) and child.name == "DeliveryFacts" and rel != OWNER:
                found.append(f"{rel}: DeliveryFacts imported outside _result.py")
            if isinstance(child, ast.Call):
                func = child.func
                direct = _name(func) == "DeliveryFacts"
                named = (
                    isinstance(func, ast.Attribute)
                    and func.attr == "not_applicable"
                    and _name(func.value) == "DeliveryFacts"
                )
                if (direct or named) and (rel, scope) != (OWNER, PROVIDER):
                    found.append(f"{rel}:{child.lineno}: DeliveryFacts built outside {PROVIDER}")
            walk(child, inner)

    walk(ast.parse(source), "")
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
