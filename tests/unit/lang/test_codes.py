"""G-ONE-LANG-CODE: every `lang.*` diagnostic is built from the registry `lang/_codes.py`.

- no string literal under `src/decoy` outside the registry holds a `lang.<code>` token
  (docstrings aside), so a code is spelled once and a message is written once;
- no module but `lang/_errors.py` builds a `Diagnostic` (through any alias or attribute),
  so a diagnostic cannot skip the registry's message;
- the registry is well formed: every descriptor names a registered code, every code has a
  descriptor, and every descriptor is used somewhere.

Named limit: a code assembled at run time (`"lang." + name`) is not seen.
"""

from __future__ import annotations

import ast
import re
import string
from pathlib import Path

import decoy.lang as public
from decoy.lang import _codes as registry

SRC = Path(__file__).resolve().parents[3] / "src" / "decoy"
LANG = SRC / "lang"
_TOKEN = re.compile(r"(?<![\w.])lang\.[a-z]+(?:_[a-z]+)*")
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)


def _docstrings(tree: ast.AST) -> set[int]:
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, _SCOPES) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                found.add(id(first.value))
    return found


def literal_findings(source: str, rel: str) -> list[str]:
    """`file:line` of each string literal, including the pieces of an f-string, with a code."""
    if rel == "lang/_codes.py":
        return []
    tree = ast.parse(source)
    docs = _docstrings(tree)
    return [
        f"{rel}:{node.lineno} {match.group(0)}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs
        for match in _TOKEN.finditer(node.value)
    ]


def diagnostic_findings(source: str, rel: str) -> list[str]:
    """`file:line` of each call that builds a `Diagnostic`, by name, alias or attribute."""
    if rel == "lang/_errors.py":
        return []
    tree = ast.parse(source)
    aliases = {"Diagnostic"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            aliases |= {a.asname for a in node.names if a.name == "Diagnostic" and a.asname}
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id in aliases) or (
            isinstance(func, ast.Attribute) and func.attr == "Diagnostic"
        ):
            found.append(f"{rel}:{node.lineno} Diagnostic(...)")
    return found


def _scan(finder) -> list[str]:  # type: ignore[no-untyped-def]
    out: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        out += finder(path.read_text(encoding="utf-8"), path.relative_to(SRC).as_posix())
    return out


def test_no_code_is_written_outside_the_registry() -> None:
    assert _scan(literal_findings) == []


def test_no_diagnostic_is_built_outside_the_error_module() -> None:
    assert _scan(diagnostic_findings) == []


def test_the_scan_sees_each_seeded_spelling() -> None:
    assert literal_findings('x = "lang.syntax"', "lang/_lower.py")
    assert literal_findings('x = "lang.nesting"', "cli/anything.py")  # outside the package too
    assert literal_findings('CODE = "lang.syntax"\nfail(CODE, "m")', "lang/_lower.py")  # alias
    assert literal_findings('errors.fail("lang.option_repeated", "m")', "lang/_lower.py")
    assert literal_findings('print(f"error[lang.convert]: {x}")', "lang/__main__.py")
    assert not literal_findings('"""A `lang.syntax` docstring."""\nx = 1', "lang/_lower.py")
    assert not literal_findings('x = "lang.syntax"', "lang/_codes.py")
    assert not literal_findings('x = "a language.syntax"', "lang/_lower.py")
    assert diagnostic_findings('Diagnostic(CODE, "m")', "lang/_lower.py")
    assert diagnostic_findings(
        "from decoy.lang._errors import Diagnostic as D\nD(CODE, 'm')", "lang/_lower.py"
    )
    assert diagnostic_findings("_errors.Diagnostic(CODE, 'm')", "lang/_lower.py")
    assert not diagnostic_findings("Diagnostic(CODE, 'm')", "lang/_errors.py")
    assert not diagnostic_findings("diagnostic(CODE)", "lang/_lower.py")


def test_a_raw_literal_added_to_a_real_module_is_caught() -> None:
    source = (LANG / "_lower.py").read_text(encoding="utf-8")
    assert literal_findings(source, "lang/_lower.py") == []
    mutant = source + '\n_EXTRA = "lang.option_repeated"\n'
    assert literal_findings(mutant, "lang/_lower.py")


def test_the_registry_is_well_formed() -> None:
    descriptors = [v for v in vars(registry).values() if isinstance(v, registry.Code)]
    assert set(descriptors) == set(registry.DESCRIPTORS)
    assert len(registry.DESCRIPTORS) == len(descriptors)
    assert {d.code for d in descriptors} == set(registry.CODES)
    assert all(re.fullmatch(r"lang\.[a-z]+(_[a-z]+)*", code) for code in registry.CODES)
    assert all(meaning.strip() for meaning in registry.CODES.values())


def test_every_descriptor_is_used() -> None:
    text = "\n".join(
        p.read_text(encoding="utf-8") for p in LANG.glob("*.py") if p.name != "_codes.py"
    )
    names = [n for n, v in vars(registry).items() if isinstance(v, registry.Code)]
    unused = [n for n in names if not re.search(rf"\b{n}\b", text)]
    assert unused == []


def test_every_message_fills_from_its_own_fields() -> None:
    for code in registry.DESCRIPTORS:
        fields = {name for _, name, _, _ in string.Formatter().parse(code.message) if name}
        assert code.message.format(**dict.fromkeys(fields, "x"))


def test_the_registry_is_public() -> None:
    assert "CODES" in public.__all__
    assert public.CODES is registry.CODES
