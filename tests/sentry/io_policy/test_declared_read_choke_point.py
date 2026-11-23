"""G-ONE-DECLARED-READ: no declared source is read, staged or acquired before its columns are checked.

The engine owns the rule (`prepare_declared_sources`); the CLI reaches it through
`cli/_sources.py::prepared_sources` (and the three wrappers built on it, `GATES`). The scan walks
every module under `src/decoy/` and applies three checks:

1. A function that calls a row reader, a stager or `acquire_relation` (`READERS`) must call a
   gate no later than its first such call. `CALLER_NAMED` lists the exact (module, function) pairs that read a file the caller named.
   `READERS` is derived from the owner modules (`derive_readers`), not listed by hand.
2. `REQUIRED` names the config-backed commands and loaders that must hold a gate call, so
   deleting a gate from one of them fails even when no reader sits in the same function.
3. An engine entry that reads sources (`ENGINE_ENTRIES`) receives the reader-side copy
   (`resolved_source_config(...)`) as its first argument, never the dump as written, and no
   module builds a `CsvDialect(...)` of its own.

Caller-named files (`decoy scan`, `decoy init`'s input, the tokenized file of `decoy detokenize`,
which opens no declared source) are not declared sources; each is an exact exemption with its
reason. The csv and parquet read primitives themselves are owned by
`test_csv_read_choke_point.py`; this sentry is about the order of the check.

Named limits of a syntax walk: a call through a runtime-bound name, an alias by assignment, and a
gate that sits in the function but runs on another branch.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.sentry.io_policy._calls import bindings, is_raw_reader, qualified, sites
from tests.sentry.io_policy._calls import leaf as _leaf

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"

OWNERS = ("cli/_sources.py", "cli/_duckdb_source.py")
# What a read primitive does at the bottom: it opens a data file (the shared qualified predicate
# `is_raw_reader`, the one G-ONE-CSV-READ also uses) or a database. The readers are derived from
# the owner modules, not listed (r12.4): a public function there that reaches a raw read, directly
# or through another owner function, is a reader, so a new primitive is watched at once.
# Explicit entries are only for readers that are not file reads: the DuckDB connection, the engine's
# subset entries and the in-memory stager.
NON_FILE_RAW = frozenset({"duckdb.connect"})
EXTRA_READERS = frozenset({"run_subset", "plan_subset", "_stage_source_entry"})


def _is_raw(call: ast.Call, bound: dict[str, str]) -> bool:
    name = qualified(call, bound)
    if name is None:
        return False
    package, _dot, member = name.rpartition(".")
    return name in NON_FILE_RAW or is_raw_reader(package, member)


def derive_readers(source: str) -> frozenset[str]:
    """Public top-level functions of an owner module that reach a raw read, transitively."""
    tree = ast.parse(source)
    module_bound = bindings(tree)
    calls: dict[str, set[str]] = {}
    raw: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound = {**module_bound, **bindings(node)}
            found = [c for c in ast.walk(node) if isinstance(c, ast.Call)]
            calls[node.name] = {str(_leaf(c, bound)) for c in found}
            if any(_is_raw(c, bound) for c in found):
                raw.add(node.name)
    readers = set(raw)
    while True:
        more = {fn for fn, names in calls.items() if names & readers} - readers
        if not more:
            break
        readers |= more
    return frozenset(r for r in readers if not r.startswith("_"))


def _owner_readers() -> frozenset[str]:
    found: set[str] = set()
    for rel in OWNERS:
        found |= derive_readers((SRC / rel).read_text(encoding="utf-8"))
    return frozenset(found)


READERS = _owner_readers() | EXTRA_READERS
# A gate counts by the name its import resolves to, never by its spelling: a local function that
# happens to be called `prepared_sources` is not the gate. `decoy.cli.io` re-exports the same
# functions for `cli/run/`. `api.py` owns its in-memory gate, a function defined in that module.
GATES = frozenset(
    f"{module}.{name}"
    for module in ("decoy.cli._sources", "decoy.cli.io")
    for name in (
        "prepared_sources",
        "gate_report_source",
        "check_declared_before_acquire",
    )
)
# The only gates whose capability `scan_descriptors` accepts (a `for_scan` request). They are not
# in `GATES`: a scan checks no declared columns (it finds them), so a run or config path that
# swapped one in for `prepared_sources` would lose the column check and must fail the sentry.
SCAN_GATES = frozenset(
    f"{module}.scan_prepared_sources" for module in ("decoy.cli._sources", "decoy.cli.io")
)
SCAN_CALL = frozenset(
    {"decoy.cli.scanning.scan_descriptors", "decoy.cli.scanning._engine_call.scan_descriptors"}
)
SCAN_OWNER = "cli/scanning/_engine_call.py"
LOCAL_GATES = frozenset({("api.py", "_gate_in_memory_data")})
ENGINE_ENTRIES = frozenset({"run_pipeline", "run_mask_pipeline_chunked", "profile_source"})

# Callers that read a file the caller named, not a declared source. Exact (module, function)
# pairs, each with its reason; any other call of a reader must follow a gate.
CALLER_NAMED: dict[tuple[str, str], str] = {
    ("cli/init.py", "_load_dataframe"): "`decoy init` reads the one input file the caller named",
    (
        "api.py",
        "scan",
    ): "`decoy.scan()` stages the caller's own DataFrame before the scan gate; the stager reads no declared source",
    ("cli/unmask.py", "unmask"): "reads the masked file the caller named, reversed from the vault",
    (
        "cli/tokenize.py",
        "detokenize",
    ): "reads the tokenized file the caller named; no declared source",
    ("cli/report.py", "compare_data"): "reads the output files two evidence manifests recorded",
}

REQUIRED: tuple[tuple[str, str], ...] = (
    ("cli/run/_execute.py", "_load_sources_from_config"),
    ("cli/run/_execute.py", "_run_chunked_mask"),
    ("cli/run/_prepare.py", "prepare"),
    ("cli/demo.py", "_run_v2_mask"),
    ("cli/subset.py", "subset"),
    ("cli/report.py", "_fidelity"),
    ("cli/report.py", "_integrity"),
    ("api.py", "_stage_data_sources"),
    ("api.py", "_gate_in_memory_data"),
)


# Where a scan runs: each must hold a scan gate call (and no other gate stands in for it).
REQUIRED_SCAN: tuple[tuple[str, str], ...] = (
    ("cli/demo.py", "_run_single_demo"),
    ("cli/scanning/_multi.py", "run_scan"),
    ("api.py", "scan"),
)


def _top(scope: str) -> str:
    return scope.split(".")[0]


def _calls(source: str) -> list[tuple[str, str, int, ast.Call]]:
    found = []
    for s in sites(ast.parse(source)):
        if isinstance(s.node, ast.Call):
            found.append((_top(s.scope), str(_leaf(s.node, s.bound)), s.lineno, s.node))
    return found


def _gate_lines(source: str, rel: str, gates: frozenset[str] = GATES) -> dict[str, int]:
    """The first line of each function's gate call, matched on the resolved qualified name.

    `LOCAL_GATES` are ordinary gates, so they count only when the caller asks for the ordinary
    set; a scan requirement is met by a scan gate alone.
    """
    first: dict[str, int] = {}
    for s in sites(ast.parse(source)):
        if not isinstance(s.node, ast.Call):
            continue
        resolved = qualified(s.node, s.bound)
        local = gates is GATES and resolved is None and (rel, _name_of(s.node)) in LOCAL_GATES
        if resolved in gates or local:
            fn = _top(s.scope)
            first[fn] = min(s.lineno, first.get(fn, s.lineno))
    return first


def ordering_violations(
    source: str, rel: str = "", readers: frozenset[str] | None = None
) -> list[str]:
    """Functions whose first reader call has no gate call on or before its line."""
    readers = READERS if readers is None else readers
    first_read: dict[str, int] = {}
    first_gate = _gate_lines(source, rel)
    for fn, name, line, _node in _calls(source):
        if name in readers:
            first_read[fn] = min(line, first_read.get(fn, line))
    return sorted(fn for fn, line in first_read.items() if first_gate.get(fn, 10**9) > line)


def unresolved_engine_calls(source: str) -> list[int]:
    """Lines of an engine entry whose first argument is not `resolved_source_config(...)`."""
    bad = []
    for _fn, name, line, node in _calls(source):
        if name not in ENGINE_ENTRIES:
            continue
        first = node.args[0] if node.args else None
        ok = isinstance(first, ast.Call) and _name_of(first) == "resolved_source_config"
        if not ok:
            bad.append(line)
    return bad


def _name_of(call: ast.Call) -> str | None:
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id
    return fn.attr if isinstance(fn, ast.Attribute) else None


def dialect_constructions(source: str) -> list[int]:
    return [line for _fn, name, line, _n in _calls(source) if name == "CsvDialect"]


def _modules() -> list[tuple[str, str]]:
    return [
        (str(p.relative_to(SRC)), p.read_text(encoding="utf-8")) for p in sorted(SRC.rglob("*.py"))
    ]


def test_every_reader_is_gated_first() -> None:
    found = {
        (rel, fn)
        for rel, text in _modules()
        if rel not in OWNERS
        for fn in ordering_violations(text, rel)
        if (rel, fn) not in CALLER_NAMED
    }
    assert found == set(), sorted(found)


def test_required_commands_hold_a_gate() -> None:
    modules = dict(_modules())
    missing = []
    for rel, fn in REQUIRED:
        if fn not in _gate_lines(modules[rel], rel):
            missing.append((rel, fn))
    assert missing == []


def missing_scan_gates(modules: dict[str, str]) -> list[tuple[str, str]]:
    """Scan commands whose source holds no scan gate call."""
    return [
        (rel, fn)
        for rel, fn in REQUIRED_SCAN
        if fn not in _gate_lines(modules[rel], rel, SCAN_GATES)
    ]


def test_scan_commands_hold_a_scan_gate() -> None:
    assert missing_scan_gates(dict(_modules())) == []


def test_engine_entries_get_the_reader_side_copy() -> None:
    bad = [f"{rel}:{line}" for rel, text in _modules() for line in unresolved_engine_calls(text)]
    assert bad == []


def test_no_module_builds_its_own_csv_dialect() -> None:
    assert [rel for rel, text in _modules() if dialect_constructions(text)] == []


def test_seeded_bypasses_are_detected() -> None:
    reader = "def cmd(cfg, base):\n    return read_source('t', cfg, base)\n"
    imp = "from decoy.cli._sources import prepared_sources\n"
    gated = (
        imp
        + "def cmd(cfg, base):\n    prepared_sources(cfg, base_dir=base)\n    return read_source('t', cfg, base)\n"
    )
    late = (
        imp
        + "def cmd(cfg, base):\n    x = read_source('t', cfg, base)\n    prepared_sources(cfg, base_dir=base)\n"
    )
    # A same-named local function is not the gate.
    local = "def prepared_sources(c, base_dir):\n    return c\ndef cmd(cfg, base):\n    prepared_sources(cfg, base_dir=base)\n    return read_source('t', cfg, base)\n"
    planned = "def cmd(s):\n    return plan_subset(s)\n"
    duck = "def cmd(db, rel, d):\n    return acquire_relation(db, rel, d)\n"
    assert ordering_violations(reader) == ["cmd"]
    assert ordering_violations(gated) == []
    assert ordering_violations(late) == ["cmd"]
    assert ordering_violations(local) == ["cmd"]
    assert ordering_violations(planned) == ["cmd"]
    assert ordering_violations(duck) == ["cmd"]
    assert unresolved_engine_calls("def f(c):\n    run_pipeline(c, {})\n") == [2]
    assert (
        unresolved_engine_calls("def f(c):\n    run_pipeline(resolved_source_config(c, d), {})\n")
        == []
    )
    assert dialect_constructions("def f():\n    return CsvDialect(names=None)\n") == [2]
    # A config-backed `read_file` (a reader the old hand list missed) and a brand-new primitive.
    assert "read_file" in READERS
    cfg_read = "def cmd(cfg, base):\n    return read_file(cfg['p'], 'csv', None, table='t')\n"
    assert ordering_violations(cfg_read) == ["cmd"]
    owner = (
        "import pyarrow.parquet as pq\n"
        "def read_new_thing(p):\n    return pq.read_table(p)\n"
        "def wrapper(p):\n    return read_new_thing(p)\n"
        "def _private(p):\n    return pq.read_table(p)\n"
    )
    assert derive_readers(owner) == {"read_new_thing", "wrapper"}
    # A reader family nobody listed (`pandas.read_feather`) is derived through the shared predicate.
    feather = "import pandas as pd\ndef read_feather_thing(p):\n    return pd.read_feather(p)\n"
    assert derive_readers(feather) == {"read_feather_thing"}
    new_reader = "def cmd(cfg):\n    return read_new_thing(cfg['p'])\n"
    assert ordering_violations(new_reader, readers=derive_readers(owner)) == ["cmd"]
    # Aliased imports resolve to the real name.
    aliased = (
        "from decoy.cli._sources import read_source as rs\ndef f(c):\n    return rs('t', c, b)\n"
    )
    assert ordering_violations(aliased) == ["f"]


# ---------------------------------------------------------------------------
# AT-C8 (S1c.2a): `scan_descriptors` takes a scan capability and every caller gets it from a gate
# ---------------------------------------------------------------------------

_SCAN_KEYWORDS = ("tables", "relationships", "relationship_positions")
_Scope = ast.Module | ast.FunctionDef | ast.AsyncFunctionDef


def _own_nodes(scope: _Scope) -> list[ast.AST]:
    """Every node of a function body (or module body) outside nested functions and classes."""
    found: list[ast.AST] = []
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        found.append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))
    return found


def _bound_names(target: ast.AST) -> list[str]:
    """Names a binding target introduces (`a`, `(a, b)`, `*rest`)."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List, ast.Starred)):
        return [n for inner in ast.iter_child_nodes(target) for n in _bound_names(inner)]
    return []


def _node_bindings(node: ast.AST) -> list[tuple[str, ast.AST | None]]:
    """(name, assigned value or None) for what one node binds; None means not a plain assignment."""
    if isinstance(node, ast.Assign):
        return [
            (n, node.value if isinstance(t, ast.Name) else None)
            for t in node.targets
            for n in _bound_names(t)
        ]
    if isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
        return [(n, None) for n in _bound_names(node.target)]
    if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
        return [(n, None) for n in _bound_names(node.target)]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [
            (n, None)
            for item in node.items
            if item.optional_vars is not None
            for n in _bound_names(item.optional_vars)
        ]
    if isinstance(node, ast.ExceptHandler) and node.name:
        return [(node.name, None)]
    return []


def _binders(scope: _Scope) -> dict[str, list[ast.AST | None]]:
    """Each local name to what binds it: the assigned value, or None for any other binding."""
    bound: dict[str, list[ast.AST | None]] = {}
    if not isinstance(scope, ast.Module):
        a = scope.args
        for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg):
            if arg is not None:
                bound.setdefault(arg.arg, []).append(None)
    for node in _own_nodes(scope):
        for name, value in _node_bindings(node):
            bound.setdefault(name, []).append(value)
    return bound


def _scopes(tree: ast.Module) -> list[tuple[str, _Scope, dict[str, str]]]:
    """(qualified name, scope node, import bindings in force) for the module and every function."""
    out: list[tuple[str, _Scope, dict[str, str]]] = []

    def visit(node: ast.AST, prefix: str, bound: dict[str, str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = child.name if not prefix else f"{prefix}.{child.name}"
                merged = {**bound, **bindings(child)}
                out.append((name, child, merged))
                visit(child, name, merged)
            elif isinstance(child, ast.ClassDef):
                name = child.name if not prefix else f"{prefix}.{child.name}"
                visit(child, name, {**bound, **bindings(child)})
            else:
                visit(child, prefix, bound)

    module_bound = bindings(tree)
    out.append(("<module>", tree, module_bound))
    visit(tree, "", module_bound)
    return out


def _chain_root(node: ast.AST | None) -> str | None:
    """The root name of an attribute chain with at least one attribute (`d.relationships`)."""
    if not isinstance(node, ast.Attribute):
        return None
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _is_declaration_of(value: ast.AST | None, param: str) -> bool:
    return (
        isinstance(value, ast.Attribute)
        and value.attr == "scan_declaration"
        and isinstance(value.value, ast.Name)
        and value.value.id == param
    )


def scan_call_violations(source: str) -> list[str]:
    """Check A: the one `scan_sources` call in the module sits in `scan_descriptors`, fed only by
    its capability. Call discovery and scope names come from the shared `sites()` scanner."""
    tree = ast.parse(source)
    calls = [
        s
        for s in sites(tree)
        if isinstance(s.node, ast.Call) and s.name == "decoy_engine.scan_sources"
    ]
    if len(calls) != 1:
        return [f"expected one scan_sources call in the module, found {len(calls)}"]
    if calls[0].scope != "scan_descriptors":
        return [f"the scan_sources call is in {calls[0].scope}, not scan_descriptors"]
    found = [fn for name, fn, _bound in _scopes(tree) if name == "scan_descriptors"]
    if len(found) != 1 or isinstance(found[0], ast.Module) or not found[0].args.args:
        return ["scan_descriptors takes no capability parameter"]
    fn = found[0]
    param = fn.args.args[0].arg
    binders = _binders(fn)
    problems = []
    if len(binders.get(param, [])) != 1:
        problems.append("the capability parameter is reassigned")
    allowed = {param} | {
        name
        for name, values in binders.items()
        if name != param and values and all(_is_declaration_of(v, param) for v in values)
    }
    call = calls[0].node
    assert isinstance(call, ast.Call)
    given = {kw.arg: kw.value for kw in call.keywords if kw.arg}
    given["<first>"] = call.args[0] if call.args else None  # type: ignore[assignment]
    for slot in ("<first>", *_SCAN_KEYWORDS):
        if _chain_root(given.get(slot)) not in allowed:
            problems.append(f"{slot} is not read from the capability")
    return problems


def _resolves_to(node: ast.AST, bound: dict[str, str], names: frozenset[str]) -> bool:
    return isinstance(node, (ast.Name, ast.Attribute, ast.Call)) and qualified(node, bound) in names  # type: ignore[arg-type]


def _gate_result(arg: ast.AST | None, scope: _Scope, bound: dict[str, str]) -> bool:
    """True for an inline scan gate call, or a local whose every binding is one."""
    if isinstance(arg, ast.Call):
        return _resolves_to(arg, bound, SCAN_GATES)
    if not isinstance(arg, ast.Name):
        return False
    values = _binders(scope).get(arg.id, [])
    return bool(values) and all(
        isinstance(v, ast.Call) and _resolves_to(v, bound, SCAN_GATES) for v in values
    )


def scan_caller_violations(source: str) -> list[str]:
    """Check B: every call of `scan_descriptors` passes a scan gate result bound in the same
    function. Calls come from the shared `sites()` scanner, so a call inside a lambda or a nested
    function is seen; a scope that is not a plain function has no gate and is red."""
    tree = ast.parse(source)
    scopes = {name: scope for name, scope, _bound in _scopes(tree)}
    problems = []
    for s in sites(tree):
        node = s.node
        if not (isinstance(node, ast.Call) and s.name in SCAN_CALL):
            continue
        by_keyword = next((k.value for k in node.keywords if k.arg == "prepared"), None)
        arg = node.args[0] if node.args else by_keyword
        scope = scopes.get(s.scope)
        if scope is None or not _gate_result(arg, scope, s.bound):
            problems.append(f"{s.scope}:{node.lineno}")
    return problems


def scan_value_references(source: str) -> list[int]:
    """Check C: lines where `scan_descriptors` is named without being called."""
    tree = ast.parse(source)
    called = {id(s.node.func) for s in sites(tree) if isinstance(s.node, ast.Call)}
    return [
        s.lineno
        for s in sites(tree)
        if isinstance(s.node, (ast.Name, ast.Attribute))
        and id(s.node) not in called
        and qualified(s.node, s.bound) in SCAN_CALL
    ]


def test_scan_call_is_fed_only_from_the_capability() -> None:
    source = (SRC / SCAN_OWNER).read_text(encoding="utf-8")
    assert scan_call_violations(source) == []


def test_every_scan_caller_passes_a_scan_gate_result() -> None:
    bad = [
        f"{rel}:{p}"
        for rel, text in _modules()
        if rel != SCAN_OWNER
        for p in scan_caller_violations(text)
    ]
    assert bad == []


def test_scan_descriptors_is_never_passed_as_a_value() -> None:
    bad = [
        f"{rel}:{line}"
        for rel, text in _modules()
        if rel != SCAN_OWNER
        for line in scan_value_references(text)
    ]
    assert bad == []


_OWNER_OK = (
    "def scan_descriptors(prepared, *, rows):\n"
    "    from decoy_engine import scan_sources\n"
    "    declaration = prepared.scan_declaration\n"
    "    return scan_sources(declaration.descriptors, tables=declaration.tables,\n"
    "        relationships=declaration.relationships,\n"
    "        relationship_positions=declaration.relationship_positions)\n"
)
_CALLER_IMPORT = (
    "from decoy.cli._sources import scan_prepared_sources\n"
    "from decoy.cli.scanning import scan_descriptors\n"
)


def _caller(body: str, imports: str = _CALLER_IMPORT) -> str:
    return imports + "def run(cfg, base):\n" + body


def test_seeded_scan_bypasses_are_detected() -> None:
    assert scan_call_violations(_OWNER_OK) == []
    good = _caller(
        "    prepared = scan_prepared_sources(cfg, base_dir=base)\n"
        "    return scan_descriptors(prepared, rows=1)\n"
    )
    inline = _caller(
        "    return scan_descriptors(scan_prepared_sources(cfg, base_dir=base), rows=1)\n"
    )
    keyword = _caller(
        "    prepared = scan_prepared_sources(cfg, base_dir=base)\n"
        "    return scan_descriptors(prepared=prepared, rows=1)\n"
    )
    for ok in (good, inline, keyword):
        assert scan_caller_violations(ok) == []
    # (1) the raw mapping
    assert scan_caller_violations(
        _caller("    return scan_descriptors({'sources': cfg}, rows=1)\n")
    )
    # (2) the wrong gate: a `for_descriptors` capability
    wrong = _caller(
        "    prepared = prepared_sources(cfg, base_dir=base)\n"
        "    return scan_descriptors(prepared, rows=1)\n",
        _CALLER_IMPORT + "from decoy.cli._sources import prepared_sources\n",
    )
    assert scan_caller_violations(wrong)
    # (2b) a local function that only shares the gate's name
    local = (
        "from decoy.cli.scanning import scan_descriptors\n"
        "def scan_prepared_sources(c, base_dir):\n    return c\n"
        "def run(cfg, base):\n"
        "    prepared = scan_prepared_sources(cfg, base_dir=base)\n"
        "    return scan_descriptors(prepared, rows=1)\n"
    )
    assert scan_caller_violations(local)
    # (3) the gate call deleted: `prepared` becomes a parameter
    assert scan_caller_violations(
        _CALLER_IMPORT + "def run(prepared):\n    return scan_descriptors(prepared, rows=1)\n"
    )
    # (4) reassigned from a dict after the gate
    assert scan_caller_violations(
        _caller(
            "    prepared = scan_prepared_sources(cfg, base_dir=base)\n"
            "    prepared = {'sources': cfg}\n"
            "    return scan_descriptors(prepared, rows=1)\n"
        )
    )
    # a gate result from another function is not accepted
    assert scan_caller_violations(
        _CALLER_IMPORT
        + "def helper(c):\n    return scan_prepared_sources(c, base_dir=None)\n"
        + "def run(cfg):\n    prepared = helper(cfg)\n    return scan_descriptors(prepared, rows=1)\n"
    )
    # a name bound by a loop
    assert scan_caller_violations(
        _caller("    for prepared in cfg:\n        scan_descriptors(prepared, rows=1)\n")
    )


def test_seeded_import_spellings_are_detected() -> None:
    # (5) the aliased import
    assert scan_caller_violations(
        _caller(
            "    return sd(cfg, rows=1)\n",
            "from decoy.cli.scanning import scan_descriptors as sd\n",
        )
    )
    # the private module spelling
    assert scan_caller_violations(
        _caller(
            "    return scan_descriptors(cfg, rows=1)\n",
            "from decoy.cli.scanning._engine_call import scan_descriptors\n",
        )
    )
    # (6) the attribute forms
    assert scan_caller_violations(
        _caller(
            "    return scanning.scan_descriptors(cfg, rows=1)\n",
            "from decoy.cli import scanning\n",
        )
    )
    assert scan_caller_violations(
        _caller(
            "    return decoy.cli.scanning.scan_descriptors(cfg, rows=1)\n",
            "import decoy.cli.scanning\n",
        )
    )


def test_seeded_value_references_are_detected() -> None:
    good = _caller(
        "    prepared = scan_prepared_sources(cfg, base_dir=base)\n"
        "    return scan_descriptors(prepared, rows=1)\n"
    )
    # (7) passed as a value, or stored
    assert scan_value_references(_caller("    return pool.submit(scan_descriptors, cfg)\n"))
    assert scan_value_references(_caller("    f = scan_descriptors\n    return f(cfg)\n"))
    assert scan_value_references(good) == []


def test_seeded_owner_bypasses_are_detected() -> None:
    assert scan_call_violations(_OWNER_OK) == []
    # (8) fed from a copied mapping, not the capability
    assert scan_call_violations(
        _OWNER_OK.replace(
            "    declaration = prepared.scan_declaration\n",
            "    declaration = prepared.scan_declaration\n    descriptors = dict(declaration.descriptors)\n",
        ).replace("scan_sources(declaration.descriptors", "scan_sources(descriptors")
    )
    # (9) relationships from a literal
    assert scan_call_violations(
        _OWNER_OK.replace("relationships=declaration.relationships", "relationships=()")
    )
    # the parameter reassigned, a keyword missing, a second call, no call
    assert scan_call_violations(
        _OWNER_OK.replace("    declaration =", "    prepared = {}\n    declaration =")
    )
    assert scan_call_violations(
        _OWNER_OK.replace(
            ",\n        relationship_positions=declaration.relationship_positions", ""
        )
    )
    assert scan_call_violations(
        _OWNER_OK.replace(
            "    return scan_sources",
            "    scan_sources(declaration.descriptors)\n    return scan_sources",
        )
    )
    assert scan_call_violations("def scan_descriptors(prepared):\n    return 1\n")


def test_seeded_ordinary_gate_does_not_satisfy_the_scan_requirement() -> None:
    # The reverse substitution: an ordinary gate on a scan command leaves it without a scan gate.
    modules = {rel: "" for rel, _fn in REQUIRED_SCAN}
    modules["api.py"] = "def scan(raw, items):\n    _gate_in_memory_data(raw, items)\n"
    modules["cli/demo.py"] = (
        "from decoy.cli._sources import prepared_sources\n"
        "def _run_single_demo(c, b):\n    prepared_sources(c, base_dir=b)\n"
    )
    assert ("api.py", "scan") in missing_scan_gates(modules)
    assert ("cli/demo.py", "_run_single_demo") in missing_scan_gates(modules)


def test_seeded_scan_gate_substitution_and_hidden_calls_are_detected() -> None:
    # The scan gate is not a declared-column gate: swapping it into a run path is red.
    swapped = (
        "from decoy.cli._sources import scan_prepared_sources\n"
        "def cmd(cfg, base):\n"
        "    scan_prepared_sources(cfg, base_dir=base)\n"
        "    return read_source('t', cfg, base)\n"
    )
    assert ordering_violations(swapped) == ["cmd"]
    assert "cmd" not in _gate_lines(swapped, "cli/run/_execute.py")
    assert "cmd" in _gate_lines(swapped, "cli/scanning/_multi.py", SCAN_GATES)
    # A scan call inside a lambda or a nested function is seen by check B.
    lam = _caller(
        "    prepared = scan_prepared_sources(cfg, base_dir=base)\n"
        "    return (lambda: scan_descriptors(prepared, rows=1))()\n"
    )
    assert scan_caller_violations(lam)
    nested = _caller(
        "    prepared = scan_prepared_sources(cfg, base_dir=base)\n"
        "    def inner():\n        return scan_descriptors(prepared, rows=1)\n"
        "    return inner()\n"
    )
    assert scan_caller_violations(nested)
    # A second function in the owner module that calls scan_sources is red for check A alone.
    second = _OWNER_OK + (
        "def other(d):\n    from decoy_engine import scan_sources\n    return scan_sources(d)\n"
    )
    assert scan_call_violations(second)


def test_a_scan_caller_in_api_py_is_not_exempt() -> None:
    # (10) `("api.py", "scan")` is in CALLER_NAMED for check 1 only; checks A to C never read it.
    raw = (
        "from decoy.cli.scanning import scan_descriptors\n"
        "def scan(data):\n    return scan_descriptors({'t': data}, rows=1)\n"
    )
    assert ("api.py", "scan") in CALLER_NAMED
    assert scan_caller_violations(raw)
