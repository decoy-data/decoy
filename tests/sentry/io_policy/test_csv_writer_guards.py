"""CSV-WRITE-FAST structure guards on the syntax tree.

1. `write_targets` runs `_preflight_csv_targets` before its target loop, so no directory is
   made and no file is staged before every resident CSV schema passed `check_csv_types`.
2. In the chunked coordinator, the four calls that build a source-to-masked stream sit in the one
   factory `_masked_chunks`, which `_run_chunked_mask` calls once per table, and every target is
   staged on one `ExitStack` (`write_chunked_output(..., defer=...)`), so none is published
   before all are staged. A direct engine call, a `next(stream)` check, a second mask pass or a
   write without `defer` fails here.
3. `_write_csv` feeds `write_batch` only through `table.to_batches(max_chunksize=...)`.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"
TARGETS = SRC / "cli" / "io" / "_targets.py"
EXECUTE = SRC / "cli" / "run" / "_execute.py"
FACTORY_CALLS = {
    "iter_source_chunks",
    "source_schema_and_chunks",
    "resolved_source_config",
    "run_mask_pipeline_chunked",
}


def _func(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"no function {name}")


def _calls(node: ast.AST) -> list[tuple[str, int]]:
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            out.append((f.id if isinstance(f, ast.Name) else getattr(f, "attr", ""), n.lineno))
    return out


def preflight_before_loop(source: str) -> bool:
    """True when `write_targets` calls the preflight before its first `for` statement."""
    func = _func(ast.parse(source), "write_targets")
    pre = [
        n.lineno
        for n in ast.walk(func)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_preflight_csv_targets"
    ]
    loops = [n.lineno for n in ast.walk(func) if isinstance(n, ast.For)]
    return bool(pre) and bool(loops) and min(pre) < min(loops)


def test_the_resident_preflight_runs_before_the_target_loop() -> None:
    assert preflight_before_loop(TARGETS.read_text(encoding="utf-8"))


def test_moving_the_preflight_below_the_loop_is_red() -> None:
    seeded = (
        "def write_targets(c, o):\n"
        "    for t in c:\n        pass\n"
        "    _preflight_csv_targets(c, o)\n"
    )
    assert not preflight_before_loop(seeded)
    assert not preflight_before_loop("def write_targets(c, o):\n    for t in c:\n        pass\n")


def chunked_findings(source: str) -> list[str]:
    tree = ast.parse(source)
    found: list[str] = []
    outside = [
        (name, line)
        for func in ast.walk(tree)
        if isinstance(func, ast.FunctionDef) and func.name == "_run_chunked_mask"
        for name, line in _calls(func)
        if name in FACTORY_CALLS
    ]
    for name, line in sorted(set(outside)):
        found.append(f"{name} outside _masked_chunks at line {line}")
    factory = {n for n, _l in _calls(_func(tree, "_masked_chunks"))}
    for name in sorted(FACTORY_CALLS - factory):
        found.append(f"_masked_chunks lacks {name}")
    run = _func(tree, "_run_chunked_mask")
    names = [n for n, _l in _calls(run)]
    for needed in ("_masked_chunks", "write_chunked_output", "ExitStack"):
        if needed not in names:
            found.append(f"_run_chunked_mask lacks {needed}")
    if "next" in names:
        found.append("_run_chunked_mask reads a stream with next()")
    # every target is staged on the one stack: write_chunked_output is called with `defer=`
    for node in ast.walk(run):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "write_chunked_output":
            if "defer" not in {k.arg for k in node.keywords}:
                found.append("write_chunked_output called without defer")
    # a second mask pass (a validation drain) is a second factory use
    if names.count("_masked_chunks") != 1:
        found.append("_run_chunked_mask builds a stream more than once")
    return found


def test_the_chunked_coordinator_has_one_factory_and_stages_every_target() -> None:
    assert chunked_findings(EXECUTE.read_text(encoding="utf-8")) == []


def test_chunked_seeds_are_red() -> None:
    live = EXECUTE.read_text(encoding="utf-8")
    direct = live.replace(
        "            src_path = _resolve_path(",
        "            run_mask_pipeline_chunked(1)\n            src_path = _resolve_path(",
        1,
    )
    assert any("outside _masked_chunks" in f for f in chunked_findings(direct))
    nexted = live.replace(
        "            src_path = _resolve_path(",
        "            next(stream)\n            src_path = _resolve_path(",
        1,
    )
    assert "_run_chunked_mask reads a stream with next()" in chunked_findings(nexted)
    no_defer = live.replace("                defer=staged,\n", "", 1)
    assert "write_chunked_output called without defer" in chunked_findings(no_defer)
    twice = live.replace(
        "            src_path = _resolve_path(",
        "            _masked_chunks(name, src_spec, config_dict, base_dir, chunk_size, key_provider)\n            src_path = _resolve_path(",
        1,
    )
    assert "_run_chunked_mask builds a stream more than once" in chunked_findings(twice)


def _write_csv_uses_bounded_batches(source: str) -> bool:
    func = _func(ast.parse(source), "_write_csv")
    for n in ast.walk(func):
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "to_batches":
            return any(k.arg == "max_chunksize" for k in n.keywords)
    return False


def test_write_csv_bounds_every_batch_and_never_writes_a_whole_table() -> None:
    source = TARGETS.read_text(encoding="utf-8")
    assert _write_csv_uses_bounded_batches(source)
    func = _func(ast.parse(source), "_write_csv")
    assert "write_table" not in {n for n, _l in _calls(func)}
    assert not _write_csv_uses_bounded_batches(
        "def _write_csv(t, w):\n    for b in t.to_batches():\n        w.write_batch(b)\n"
    )
