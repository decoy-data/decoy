"""G-REPORT-DISPLAY: report and library output prints only the display copy of a recorded value.

The plan is `docs/plans/2026-11-28-d6-manifest-display-boundary.md`, section 5. Four rules:

- R1 (`decoy.cli.report`, `decoy.cli.library`): `read_manifest` is called only as `return
  read_manifest(...)` inside `_load_manifest`. A `_load_manifest` call is only the right side of
  a plain name assignment, and that name is loaded only as a direct positional argument of
  `display_manifest`, `manifest_hash_ok`, `verify_manifest`, `compare_manifests` or
  `compare_data`.
- R2 (`src/decoy`): a call to `compare_manifests`, `compare_data` or `diff_payloads` is the
  direct argument of `display_safe(...)`, except the forwarder `library._diff._evidence`, which
  only `diff_payloads` reaches. The forwarder list must equal the unwrapped sites found.
- R3: each private document function annotates its input `DisplayCopy` and names no raw reader,
  and the public `render_html` and `render_markdown` hand it only a display copy.
- R4: `DisplayCopy` is called only inside `decoy/safe_url.py`, matched on the resolved name so
  an import alias does not hide the call.

Calls are resolved with `tests/sentry/io_policy/_calls.py`; a bare call to a function defined in
the same module resolves to `<module>.<name>`. The seeded mutations prove each rule fails alone.
No baseline or allow-list: every rule holds on the whole tree.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.sentry.io_policy._calls import Site, qualified, sites

SRC = Path(__file__).resolve().parents[3] / "src"

_LOADER = "decoy.cli.report._shared._load_manifest"
_RAW_READS = frozenset(
    {"display_manifest", "manifest_hash_ok", "verify_manifest", "compare_manifests", "compare_data"}
)
_SINKS = frozenset({"compare_manifests", "compare_data", "diff_payloads"})
# (module, function) -> the sink it may call unwrapped, and the only function that may call it.
_FORWARDERS = {("decoy.cli.library._diff", "_evidence"): ("compare_manifests", "diff_payloads")}
# (module, function, parameter): the private document functions.
_DOCUMENTS = (
    ("decoy.cli.report._html", "_html_document", "manifest"),
    ("decoy.cli.report._markdown", "_markdown_document", "manifest"),
    ("decoy.ui.evidence_card", "render_manifest_card", "shown"),
    ("decoy.cli.report._diff", "_render_manifest_compare", "diff"),
    ("decoy.cli.report._diff", "_render_data_diff", "diff_result"),
)
_PUBLIC = (
    ("decoy.cli.report._html", "render_html", "_html_document"),
    ("decoy.cli.report._markdown", "render_markdown", "_markdown_document"),
)
_FORBIDDEN_IN_DOCUMENTS = frozenset(
    {"read_manifest", "_load_manifest", "redacted_location", "compare_manifests", "compare_data"}
)


def _sources() -> dict[str, str]:
    return {
        ".".join(p.relative_to(SRC).with_suffix("").parts): p.read_text(encoding="utf-8")
        for p in sorted((SRC / "decoy").rglob("*.py"))
    }


class _Module:
    def __init__(self, name: str, source: str) -> None:
        self.name = name
        self.tree = ast.parse(source)
        self.defs = {
            n.name: n
            for n in self.tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.sites = sites(self.tree)

    def resolve(self, call: ast.AST, site: Site) -> str | None:
        """The dotted name of a call's callee: a bound import, else a same-module function."""
        if not isinstance(call, ast.Call):
            return None
        name = qualified(call, site.bound)
        if name is None and isinstance(call.func, ast.Name) and call.func.id in self.defs:
            name = f"{self.name}.{call.func.id}"
        return name

    def calls(self) -> Iterator[tuple[Site, str]]:
        for site in self.sites:
            name = self.resolve(site.node, site)
            if name is not None:
                yield site, name


def _leaf(name: str) -> str:
    return name.rpartition(".")[2]


def _is_decoy_cli(name: str, member: str) -> bool:
    return name.startswith("decoy.cli.") and _leaf(name) == member


def _loader_names(mod: _Module, found: list[str]) -> dict[str, set[str]]:
    """Per scope, the names bound to a `_load_manifest` result; bad loader and reader calls are
    added to `found`."""
    bound: dict[str, set[str]] = {}
    for site, name in mod.calls():
        parent, field = site.ancestors[-1]
        if _is_decoy_cli(name, "read_manifest"):
            ok = mod.name == "decoy.cli.report._shared" and site.scope == "_load_manifest"
            if not (ok and isinstance(parent, ast.Return)):
                found.append(f"{mod.name}:{site.lineno} read_manifest outside the forwarder")
        elif name == _LOADER or (
            _is_decoy_cli(name, "_load_manifest") and name.startswith("decoy.cli.report")
        ):
            targets = parent.targets if isinstance(parent, ast.Assign) else []
            if field != "value" or len(targets) != 1 or not isinstance(targets[0], ast.Name):
                found.append(f"{mod.name}:{site.lineno} _load_manifest not assigned to a name")
                continue
            bound.setdefault(site.scope, set()).add(targets[0].id)
    return bound


def _r1(modules: dict[str, _Module]) -> list[str]:
    found: list[str] = []
    for mod in modules.values():
        if not mod.name.startswith(("decoy.cli.report", "decoy.cli.library")):
            continue
        bound = _loader_names(mod, found)
        for site in mod.sites:
            node = site.node
            if not (isinstance(node, ast.Name) and node.id in bound.get(site.scope, ())):
                continue
            parent, field = site.ancestors[-1]
            name = mod.resolve(parent, site) if field == "args" else None
            if name is None or _leaf(name) not in _RAW_READS:
                found.append(f"{mod.name}:{site.lineno} raw manifest `{node.id}` read directly")
    return found


def _r2(modules: dict[str, _Module]) -> list[str]:
    found: list[str] = []
    unwrapped: set[tuple[str, str]] = set()
    for mod in modules.values():
        for site, name in mod.calls():
            if not name.startswith("decoy.cli."):
                continue
            key = (mod.name, site.scope)
            if _leaf(name) in _SINKS:
                parent, field = site.ancestors[-1]
                wrapper = mod.resolve(parent, site) if field == "args" else None
                if wrapper == "decoy.safe_url.display_safe":
                    continue
                if _FORWARDERS.get(key, ("",))[0] == _leaf(name):
                    unwrapped.add(key)
                    continue
                found.append(f"{mod.name}:{site.lineno} `{_leaf(name)}` result not displayed")
                unwrapped.add(key)
            forwarder = (name.rpartition(".")[0], _leaf(name))
            if forwarder in _FORWARDERS and site.scope != _FORWARDERS[forwarder][1]:
                found.append(f"{mod.name}:{site.lineno} forwarder `{_leaf(name)}` called directly")
    if unwrapped != set(_FORWARDERS):
        found.append(f"forwarder list {sorted(_FORWARDERS)} != unwrapped sites {sorted(unwrapped)}")
    return found


def _names(node: ast.AST) -> set[str]:
    return {
        n.id if isinstance(n, ast.Name) else n.attr
        for n in ast.walk(node)
        if isinstance(n, (ast.Name, ast.Attribute))
    }


def _displays(value: ast.expr | None, param: str) -> bool:
    """`display_manifest(param)`, or `param if isinstance(param, DisplayCopy) else` that."""

    def is_display(node: ast.expr) -> bool:
        return (
            isinstance(node, ast.Call)
            and "display_manifest" in _names(node.func)
            and [ast.unparse(a) for a in node.args] == [param]
        )

    if value is not None and is_display(value):
        return True
    return (
        isinstance(value, ast.IfExp)
        and ast.unparse(value.test) == f"isinstance({param}, DisplayCopy)"
        and ast.unparse(value.body) == param
        and is_display(value.orelse)
    )


def _r3(modules: dict[str, _Module]) -> list[str]:
    found: list[str] = []
    for module, func, param in _DOCUMENTS:
        node = modules[module].defs.get(func)
        args = {a.arg: a for a in node.args.args + node.args.kwonlyargs} if node else {}
        if param not in args:
            found.append(f"{module}.{func} has no parameter `{param}`")
            continue
        if ast.unparse(args[param].annotation or ast.Constant(None)) != "DisplayCopy":
            found.append(f"{module}.{func}({param}) is not annotated DisplayCopy")
        assert node is not None
        named = set().union(*(_names(stmt) for stmt in node.body)) & _FORBIDDEN_IN_DOCUMENTS
        if named:
            found.append(f"{module}.{func} names {sorted(named)}")
    for module, func, document in _PUBLIC:
        node = modules[module].defs.get(func)
        if node is None:
            found.append(f"{module}.{func} is missing")
            continue
        param = node.args.args[0].arg
        assigned = {
            t.id: stmt.value
            for stmt in ast.walk(node)
            if isinstance(stmt, ast.Assign)
            for t in stmt.targets
            if isinstance(t, ast.Name)
        }
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call) and ast.unparse(call.func) == document):
                continue
            arg = call.args[0] if call.args else None
            if not (isinstance(arg, ast.Name) and _displays(assigned.get(arg.id), param)):
                found.append(f"{module}.{func} passes `{ast.unparse(call)}` undisplayed")
    return found


def _r4(modules: dict[str, _Module]) -> list[str]:
    """A call resolved to `DisplayCopy` through any import alias, or written as `DisplayCopy`."""
    found: list[str] = []
    for mod in modules.values():
        if mod.name == "decoy.safe_url":
            continue
        for site in mod.sites:
            call = site.node
            if not isinstance(call, ast.Call):
                continue
            name = mod.resolve(call, site) or ast.unparse(call.func)
            if _leaf(name) == "DisplayCopy":
                found.append(f"{mod.name}:{site.lineno} builds DisplayCopy")
    return found


RULES = {"R1": _r1, "R2": _r2, "R3": _r3, "R4": _r4}


def scan(sources: dict[str, str]) -> dict[str, list[str]]:
    modules = {name: _Module(name, text) for name, text in sources.items()}
    return {rule: check(modules) for rule, check in RULES.items()}


def test_the_tree_passes_every_rule() -> None:
    assert scan(_sources()) == {rule: [] for rule in RULES}


def test_every_scanned_function_exists() -> None:
    modules = {name: _Module(name, text) for name, text in _sources().items()}
    for module, func, _ in (*_DOCUMENTS, *_PUBLIC):
        assert func in modules[module].defs, f"{module}.{func}"
    for module, func in _FORWARDERS:
        assert func in modules[module].defs, f"{module}.{func}"


# (rule, module, old text, new text): each seed is applied alone to the current tree.
SEEDS = {
    "show reads row_counts from the raw manifest": (
        "R1",
        "decoy.cli.report._show",
        "    shown = evidence.display_manifest(manifest)\n",
        '    shown = evidence.display_manifest(manifest)\n    _counts = manifest.get("row_counts")\n',
    ),
    "render passes an aliased loader call inline": (
        "R1",
        "decoy.cli.report._render",
        '    manifest = _load_manifest(evidence_file, state, "report render")\n',
        "    from decoy.cli.report._shared import _load_manifest as lm\n\n"
        '    render_html(lm(evidence_file, state, "report render"))\n'
        '    manifest = _load_manifest(evidence_file, state, "report render")\n',
    ),
    "report diff drops display_safe around compare_data": (
        "R2",
        "decoy.cli.report._diff",
        "        data_result = display_safe(\n            compare_data(",
        "        data_result = (\n            compare_data(",
    ),
    "library diff calls diff_payloads through a module alias": (
        "R2",
        "decoy.cli.library._read",
        "    from decoy.cli.library import diff_payloads\n",
        "    from decoy.cli import library as lib\n"
        "    from decoy.cli.library import diff_payloads\n\n"
        "    lib.diff_payloads(None, {}, {})\n",
    ),
    "a second unwrapped compare_manifests in library diff": (
        "R2",
        "decoy.cli.library._diff",
        "def _pair(old: Any, new: Any) -> dict:\n",
        "def _second(old: Any, new: Any) -> dict:\n"
        "    from decoy.cli.report import compare_manifests\n\n"
        "    return compare_manifests(dict(old), dict(new))\n\n\n"
        "def _pair(old: Any, new: Any) -> dict:\n",
    ),
    "html document takes a plain dict": (
        "R3",
        "decoy.cli.report._html",
        "def _html_document(manifest: DisplayCopy) -> str:",
        "def _html_document(manifest: dict[str, Any]) -> str:",
    ),
    "render_markdown skips display_manifest": (
        "R3",
        "decoy.cli.report._markdown",
        "    return _markdown_document(shown)\n",
        "    return _markdown_document(manifest)\n",
    ),
    "show builds its own DisplayCopy": (
        "R4",
        "decoy.cli.report._show",
        "    shown = evidence.display_manifest(manifest)\n",
        "    shown = evidence.display_manifest(manifest)\n    _empty = DisplayCopy({})\n",
    ),
    "show builds DisplayCopy through an import alias": (
        "R4",
        "decoy.cli.report._show",
        "    shown = evidence.display_manifest(manifest)\n",
        "    shown = evidence.display_manifest(manifest)\n"
        "    from decoy.safe_url import DisplayCopy as Shown\n\n"
        "    _empty = Shown({})\n",
    ),
}


@pytest.mark.parametrize("seed", sorted(SEEDS))
def test_each_seed_fails_only_its_own_rule(seed: str) -> None:
    rule, module, old, new = SEEDS[seed]
    sources = _sources()
    assert sources[module].count(old) == 1, f"seed {seed!r} no longer matches {module}"
    sources[module] = sources[module].replace(old, new)
    failing = {r for r, found in scan(sources).items() if found}
    assert failing == {rule}, scan(sources)
