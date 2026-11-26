"""Walk and check for G-CONFIG-READER (see ``test_config_field_readers.py``).

Pure functions over a pydantic model and a manifest dict, so a test can feed a fixture model, a
fixture manifest or a fixture source tree. Findings carry config paths, symbol names and file
names only, never a value.

Source pattern: dbt flags configuration paths that apply to no resource; this applies the same
idea at build time with the model as the source of truth.
"""

from __future__ import annotations

import ast
import functools
import importlib
import importlib.util
import itertools
import json
import textwrap
import types
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from tests.sentry._ratchet import parse_registry

SENTRY_ID = "config-field-readers"
ROOT = Path(__file__).resolve().parents[3]
# A key this short, or one of these words, proves nothing by appearing in a source: it needs a
# `via` helper and the sentry checks the call to the helper instead.
SHORT_KEY = 6
COMMON_WORDS = frozenset({"enabled", "output", "format", "detectors", "strategy"})
# The engine's own config models define every key; a model class never counts as a reader, and a
# package-scope search skips the config package for the same reason.
CONFIG_PACKAGE = "config"
# `label` is for a field the model validates and the run carries without branching on it. Only
# these paths may use it, so it cannot hide an unread field.
LABEL_PATHS = frozenset({"name"})
MAX_SAME_NAME = 3


def load_manifest(unread: dict[str, Any]) -> dict[str, Any]:
    """``{"unread": ..., "readers": ...}``: ``unread`` is the registered baseline's entries, which
    the sentry itself loads with ``load_allowlist``; the readers sit beside them in that file."""
    registered, _ = parse_registry((ROOT / "scripts/dev/sentry_registry.toml").read_text("utf-8"))
    doc = json.loads((ROOT / registered[SENTRY_ID]).read_text(encoding="utf-8"))
    return {"unread": dict(unread), "readers": dict(doc["readers"])}


def _models_of(annotation: object) -> list[type[BaseModel]]:
    """Pydantic models an annotation names directly: through ``Optional``, unions and
    ``Annotated``, and not through ``list`` or ``dict`` items."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is typing.Annotated:
        return _models_of(args[0])
    if origin is typing.Union or origin is types.UnionType:
        return [m for a in args for m in _models_of(a)]
    return []


def walk(model: type[BaseModel]) -> list[str]:
    """Every top-level field and the fields of each directly nested model, sorted, unique."""
    paths: set[str] = set()
    for name, field in model.model_fields.items():
        paths.add(name)
        for nested in _models_of(field.annotation):
            paths.update(f"{name}.{inner}" for inner in nested.model_fields)
    return sorted(paths)


def _key(path: str) -> str:
    return path.rpartition(".")[2]


def _needs_via(path: str) -> bool:
    key = _key(path)
    return len(key) < SHORT_KEY or key in COMMON_WORDS


def _mentions(tree: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
    return out


def _calls(tree: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                out.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                out.add(fn.attr)
    return out


def _own_body_calls(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Names called in the function's own body; nested defs and lambdas are not run by it."""
    out: set[str] = set()
    stack: list[ast.AST] = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
        stack.extend(ast.iter_child_nodes(node))
    return out


def _public_symbol(spec: str, path: str) -> tuple[object, str | None, str | None]:
    """``(object, module, finding)`` for ``module:name``; a symbol must be public and listed."""
    module, sep, name = spec.partition(":")
    if not sep or not module or not name:
        return None, None, f"{path}: {spec!r} is not module:name"
    if any(part.startswith("_") for part in module.split(".")) or name.startswith("_"):
        return None, None, f"{path}: {module}:{name} is private; name a public engine symbol"
    try:
        mod = importlib.import_module(module)
    except (ImportError, AttributeError, RuntimeError, OSError) as exc:  # type name only
        return None, None, f"{path}: {module} does not import ({type(exc).__name__})"
    if name not in getattr(mod, "__all__", ()):
        return None, None, f"{path}: {name} is not in {module}.__all__"
    obj = getattr(mod, name, None)
    if obj is None:
        return None, None, f"{path}: {module} has no {name}"
    return obj, module, None


def _symbol_tree(obj: object) -> ast.AST | None:
    import inspect

    try:
        return ast.parse(textwrap.dedent(inspect.getsource(obj)))
    except (OSError, TypeError, SyntaxError):
        return None


@functools.lru_cache(maxsize=None)
def _package_trees(module: str) -> tuple[ast.AST, ...]:
    """Parsed source of every file in the module's package, minus the config package.

    Read as files and never imported, so a private module stays unimported by the sentry. This
    scope serves a key the engine reads in a private helper of the public package named by the
    entry.
    """
    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin is None:
        return ()
    base = Path(spec.origin).parent
    out: list[ast.AST] = []
    for file in sorted(base.rglob("*.py")):
        if CONFIG_PACKAGE in file.relative_to(base).parts[:-1]:
            continue
        try:
            out.append(ast.parse(file.read_text(encoding="utf-8")))
        except (OSError, SyntaxError):
            continue
    return tuple(out)


def engine_findings(path: str, entry: dict[str, Any]) -> list[str]:
    """Why an ``engine`` entry fails: private or unlisted symbol, a model class, a symbol (or
    package) that does not name the key, a short key with no ``via``, a ``via`` never called."""
    obj, module, bad = _public_symbol(str(entry.get("engine", "")), path)
    if bad:
        return [bad]
    assert module is not None
    if isinstance(obj, type) and issubclass(obj, BaseModel):
        return [
            f"{path}: {entry['engine']} is a config model; a model defines a key, it reads none"
        ]
    scope = entry.get("scope", "symbol")
    if scope not in ("symbol", "package"):
        return [f"{path}: scope {scope!r} is not symbol or package"]
    # The named symbol is always the reader: it names the key itself, or it calls (directly or
    # through helpers of its own package) a function that does. Scope `package` follows those
    # calls; scope `symbol` reads the symbol's own source only. A different function of the
    # package never stands in for the symbol.
    via = entry.get("via")
    if _needs_via(path) and not via:
        return [f"{path}: key {_key(path)!r} is short or common; the entry needs a via helper"]
    reach = _reach if scope == "package" else _own
    seen = reach(obj, module)
    if not via:
        if _key(path) not in seen.mentions:
            return [f"{path}: {entry['engine']} does not name the key {_key(path)!r}"]
        return []
    return _via_findings(path, entry, str(via), scope, module, seen)


def _via_findings(
    path: str, entry: dict[str, Any], via: str, scope: str, module: str, seen: "_Seen"
) -> list[str]:
    """Why the ``via`` helper of an ``engine`` entry fails: unresolvable, never called, or it
    does not name the key."""
    name = via.partition(":")[2]
    helper_reach, bad_via = _via_reach(path, via, scope, module)
    if helper_reach is None:
        return [bad_via] if bad_via else []
    if name not in seen.calls:
        return [f"{path}: {entry['engine']} does not call the via helper {name}"]
    if _key(path) not in helper_reach.mentions:
        return [f"{path}: the via helper {name} does not name the key {_key(path)!r}"]
    return []


def _via_reach(path: str, via: str, scope: str, module: str) -> tuple["_Seen | None", str | None]:
    """What the ``via`` helper reaches, resolved by its exact module and symbol.

    A public helper is imported. Under scope ``package`` a private one is read from the source
    of the module the spec names, so a spec naming another module fails even when the bare
    function name exists elsewhere in the engine.
    """
    helper, helper_module, bad_via = _public_symbol(via, path)
    if not bad_via:
        assert helper_module is not None
        return (_reach if scope == "package" else _own)(helper, helper_module), None
    helper_module, _, name = via.partition(":")
    nodes = _module_defs(helper_module, name) if scope == "package" and name else ()
    if not nodes:
        return None, bad_via
    return _closure(*_node_names(nodes), module), None


def _module_defs(module: str, name: str) -> tuple[ast.AST, ...]:
    """The functions named ``name`` in the one source file of ``module``; never imports it."""
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, AttributeError, ValueError):  # a parent that is missing or not a package
        return ()
    if spec is None or spec.origin is None or not spec.origin.endswith(".py"):
        return ()
    try:
        tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return ()
    return tuple(
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
    )


def _node_names(nodes: tuple[ast.AST, ...]) -> tuple[set[str], set[str]]:
    mentions: set[str] = set()
    calls: set[str] = set()
    for node in nodes:
        mentions |= _mentions(node)
        calls |= _calls(node)
    return mentions, calls


@dataclass(frozen=True)
class _Seen:
    mentions: set[str]
    calls: set[str]


def _own(obj: object, module: str) -> _Seen:
    tree = _symbol_tree(obj)
    return _Seen(_mentions(tree), _calls(tree)) if tree is not None else _Seen(set(), set())


@functools.lru_cache(maxsize=None)
def _defs_by_name(module: str) -> dict[str, tuple[ast.AST, ...]]:
    """Every function or method defined in the engine, by name, minus the config package.

    The index is engine-wide because a public reader often calls a helper in a sibling package.
    A name defined more than ``MAX_SAME_NAME`` times (``get``, ``run``) is left out: following it
    would credit a symbol with half the engine.
    """
    out: dict[str, list[ast.AST]] = {}
    for tree in _package_trees(module.partition(".")[0]):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.setdefault(node.name, []).append(node)
    return {k: tuple(v) for k, v in out.items() if len(v) <= MAX_SAME_NAME}


def _reach(obj: object, module: str) -> _Seen:
    """The symbol's own source plus every package function its calls reach, by call name.

    A call resolves by name to each same-named function of the package, so a name shared by two
    functions reaches both (a named limit: it can only widen what a symbol is credited with).
    """
    start = _own(obj, module)
    return _closure(set(start.mentions), set(start.calls), module)


def _closure(mentions: set[str], calls: set[str], module: str) -> _Seen:
    defs = _defs_by_name(module)
    queue, done = sorted(calls), set()
    while queue:
        name = queue.pop()
        if name in done or (name.startswith("__") and name.endswith("__")):
            continue  # a dunder name is shared by every class and would reach the whole package
        done.add(name)
        for node in defs.get(name, ()):
            mentions |= _mentions(node)
            fresh = _calls(node)
            calls |= fresh
            queue.extend(sorted(fresh - done))
    return _Seen(mentions, calls)


def _function(root: Path, spec: str, path: str) -> tuple[ast.FunctionDef | None, str | None]:
    rel, sep, name = spec.partition("::")
    if not sep or not rel or not name:
        return None, f"{path}: {spec!r} is not file::function"
    file = root / rel
    if not file.is_file():
        return None, f"{path}: {rel} does not exist"
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"))
    except SyntaxError:
        return None, f"{path}: {rel} does not parse"
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node, None
    return None, f"{path}: {rel} has no function {name}"


def cli_findings(path: str, entry: dict[str, Any], root: Path) -> list[str]:
    """Why a ``cli`` entry fails: a missing function, a body that neither names the key nor
    calls its ``via`` helper, a short key with no ``via``, a chain whose link is not a direct
    call in the previous function's own body, or no chain at all."""
    fn, bad = _function(root, str(entry.get("cli", "")), path)
    if bad:
        return [bad]
    assert fn is not None
    out: list[str] = []
    via = entry.get("via")
    if _needs_via(path) and not via:
        out.append(f"{path}: key {_key(path)!r} is short or common; the entry needs a via helper")
    elif via:
        if str(via) not in _calls(fn):
            out.append(f"{path}: {entry['cli']} does not call the via helper {via}")
    elif _key(path) not in _mentions(fn):
        out.append(f"{path}: {entry['cli']} does not name the key {_key(path)!r}")
    chains = entry.get("chains")
    if not isinstance(chains, dict) or not chains:
        return [*out, f"{path}: a cli entry lists at least one route chain"]
    for route, links in sorted(chains.items()):
        out += _chain_findings(path, route, links, root)
    return out


def _chain_findings(path: str, route: str, links: object, root: Path) -> list[str]:
    if not isinstance(links, list) or len(links) < 2:
        return [f"{path}: route {route} needs a chain of two or more links"]
    funcs: list[ast.FunctionDef] = []
    for link in links:
        node, bad = _function(root, str(link), path)
        if bad:
            return [f"{bad} (route {route})"]
        assert node is not None
        funcs.append(node)
    return [
        f"{path}: route {route}: {a.name} has no direct call to {b.name}"
        for a, b in itertools.pairwise(funcs)
        if b.name not in _own_body_calls(a)
    ]


def _children_of(parent: str, unread: dict[str, Any]) -> set[str] | None:
    """The recorded children of an unread block, or None when the entry is not a block."""
    entry = unread.get(parent)
    kids = entry.get("children") if isinstance(entry, dict) else None
    return {str(k) for k in kids} if isinstance(kids, list) else None


def _coverage_findings(
    walked: list[str], unread: dict[str, Any], readers: dict[str, Any]
) -> list[str]:
    """A path needs exactly one entry. An unread block lists its known children, so a child the
    block gains later is a finding like any other new field."""
    out: list[str] = []
    for path in walked:
        out += _path_coverage(path, unread, readers)
    for path in sorted((set(unread) | set(readers)) - set(walked)):
        out.append(f"{path}: manifest entry for a path the model does not have")
    for parent in sorted(unread):
        kids = _children_of(parent, unread)
        if kids is None:
            continue
        for child in sorted(
            kids - {w.partition(".")[2] for w in walked if w.startswith(parent + ".")}
        ):
            out.append(f"{parent}.{child}: listed as a child of an unread block that lacks it")
    return out


def _path_coverage(path: str, unread: dict[str, Any], readers: dict[str, Any]) -> list[str]:
    """The coverage findings of one walked path."""
    parent, _, child = path.partition(".")
    kinds = [path in unread, path in readers]
    if child and parent in unread:
        kids = _children_of(parent, unread)
        if kids is None or child not in kids:
            return [
                f"{path}: new field under the unread block {parent}; classify it as engine,"
                f" cli or other_command, or add it to the block's children"
            ]
        if any(kinds):
            return [f"{path}: its block {parent} is unread; list the block once"]
        return []
    if sum(kinds) == 0:
        return [f"{path}: no manifest entry; classify it as engine, cli, other_command or unread"]
    if sum(kinds) == 2:
        return [f"{path}: listed as both unread and read"]
    return []


def _entry_findings(path: str, entry: dict[str, Any], root: Path) -> list[str]:
    kinds = [k for k in ("engine", "cli", "other_command", "label") if k in entry]
    if len(kinds) != 1:
        return [f"{path}: an entry has exactly one of engine, cli, other_command, label"]
    kind = kinds[0]
    if kind == "engine":
        return engine_findings(path, entry)
    if kind == "cli":
        return cli_findings(path, entry, root)
    if kind == "label" and (path not in LABEL_PATHS or not str(entry["label"]).strip()):
        return [f"{path}: a label entry is allowed only for {sorted(LABEL_PATHS)}"]
    if kind == "other_command" and not entry.get("row"):
        return [f"{path}: an other_command entry names its roadmap row"]
    return []


def findings(model: type[BaseModel], manifest: dict[str, Any], root: Path) -> list[str]:
    """Every finding for ``model`` against ``manifest``: coverage first, then each entry."""
    unread: dict[str, Any] = manifest["unread"]
    readers: dict[str, Any] = manifest["readers"]
    walked = walk(model)
    out = _coverage_findings(walked, unread, readers)
    for path, entry in sorted(readers.items()):
        if path in walked:
            out += _entry_findings(path, entry, root)
    for path, entry in sorted(unread.items()):
        if not isinstance(entry, dict) or not entry.get("row"):
            out.append(f"{path}: an unread entry names its roadmap row")
    return out
