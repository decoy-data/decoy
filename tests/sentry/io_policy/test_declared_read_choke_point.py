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

from tests.sentry.io_policy._calls import bindings, qualified, sites
from tests.sentry.io_policy._calls import leaf as _leaf

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"

OWNERS = ("cli/_sources.py", "cli/_duckdb_source.py")
# What a read primitive does at the bottom: it opens a data file or a database. The readers are
# derived from the owner modules, not listed (r12.4): a function there that reaches one of these,
# directly or through another owner function, is a reader, so a new primitive is watched at once.
RAW_READS = frozenset(
    {"read_csv_source", "read_fixed_width", "read_table", "read_parquet", "ParquetFile", "connect"}
)
# Readers that are not owner functions: the engine's subset entries and the in-memory stager.
EXTRA_READERS = frozenset({"run_subset", "plan_subset", "_stage_source_entry"})


def derive_readers(source: str) -> frozenset[str]:
    """Public top-level functions of an owner module that reach a raw read, transitively."""
    tree = ast.parse(source)
    module_bound = bindings(tree)
    calls: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound = {**module_bound, **bindings(node)}
            calls[node.name] = {
                str(_leaf(c, bound)) for c in ast.walk(node) if isinstance(c, ast.Call)
            }
    readers = {fn for fn, names in calls.items() if names & RAW_READS}
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
    for name in ("prepared_sources", "gate_report_source", "check_declared_before_acquire")
)
LOCAL_GATES = frozenset({("api.py", "_gate_in_memory_data")})
ENGINE_ENTRIES = frozenset({"run_pipeline", "run_mask_pipeline_chunked", "profile_source"})

# Callers that read a file the caller named, not a declared source. Exact (module, function)
# pairs, each with its reason; any other call of a reader must follow a gate.
CALLER_NAMED: dict[tuple[str, str], str] = {
    ("cli/init.py", "_load_dataframe"): "`decoy init` reads the one input file the caller named",
    (
        "cli/scan.py",
        "_load_parquet_with_sampling",
    ): "`decoy scan` reads the Parquet the caller named",
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


def _top(scope: str) -> str:
    return scope.split(".")[0]


def _calls(source: str) -> list[tuple[str, str, int, ast.Call]]:
    found = []
    for s in sites(ast.parse(source)):
        if isinstance(s.node, ast.Call):
            found.append((_top(s.scope), str(_leaf(s.node, s.bound)), s.lineno, s.node))
    return found


def _gate_lines(source: str, rel: str) -> dict[str, int]:
    """The first line of each function's gate call, matched on the resolved qualified name."""
    first: dict[str, int] = {}
    for s in sites(ast.parse(source)):
        if not isinstance(s.node, ast.Call):
            continue
        resolved = qualified(s.node, s.bound)
        local = resolved is None and (rel, _name_of(s.node)) in LOCAL_GATES
        if resolved in GATES or local:
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
    new_reader = "def cmd(cfg):\n    return read_new_thing(cfg['p'])\n"
    assert ordering_violations(new_reader, readers=derive_readers(owner)) == ["cmd"]
    # Aliased imports resolve to the real name.
    aliased = (
        "from decoy.cli._sources import read_source as rs\ndef f(c):\n    return rs('t', c, b)\n"
    )
    assert ordering_violations(aliased) == ["f"]
