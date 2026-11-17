"""fsck codes have one registry (review round 1 on #210, DESIGN 8).

`decoy.cli.library._fsck_codes` holds every finding, warning and note fsck prints and every
repair action, each with its level and the one repair it allows; check and repair derive their
dispatch from it. No other library module spells a code as a string literal, and the newer
layout reuses the library's own `library_layout_newer`.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest
from tests.unit.library._helpers import ROOT, envelope, object_path

from decoy.cli.io import DECOY_DIR
from decoy.cli.library import _fsck, _fsck_codes, open_library
from decoy.cli.library._errors import LIBRARY_LAYOUT_NEWER

PACKAGE = ROOT / "src" / "decoy" / "cli" / "library"
REGISTRY_FILE = "_fsck_codes.py"


def _local(_p: Path) -> None:
    return None


def _all_codes() -> set[str]:
    return {d.code for d in _fsck_codes.FINDINGS} | {a.code for a in _fsck_codes.ACTIONS}


def literals_outside(sources: dict[str, str], codes: set[str]) -> dict[str, list[str]]:
    """String constants equal to a registered code, per module other than the registry."""
    hits: dict[str, list[str]] = {}
    for name, text in sources.items():
        if name == REGISTRY_FILE:
            continue
        found = [
            node.value
            for node in ast.walk(ast.parse(text))
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in codes
        ]
        if found:
            hits[name] = sorted(found)
    return hits


def test_no_module_spells_a_registered_code_outside_the_registry() -> None:
    sources = {p.name: p.read_text(encoding="utf-8") for p in PACKAGE.glob("*.py")}
    assert REGISTRY_FILE in sources and "_fsck.py" in sources  # non-vacuous
    codes = _all_codes() - {LIBRARY_LAYOUT_NEWER}  # an error code first, owned by _errors
    assert literals_outside(sources, codes) == {}


def test_the_guard_fires_on_a_seeded_literal() -> None:
    seeded = {"_seeded.py": 'def f(add):\n    add("finding", "temp_stale", "x")\n'}
    assert literals_outside(seeded, _all_codes()) == {"_seeded.py": ["temp_stale"]}


def test_each_descriptor_is_unique_and_its_repair_is_known() -> None:
    keys = [(d.code, d.level) for d in _fsck_codes.FINDINGS]
    assert len(keys) == len(set(keys))
    assert {d.repair for d in _fsck_codes.FINDINGS} <= {None, *_fsck_codes.REPAIRS}
    assert len({a.code for a in _fsck_codes.ACTIONS}) == len(_fsck_codes.ACTIONS)


def test_a_newer_layout_is_the_library_error_code(tmp_path: Path) -> None:
    root = tmp_path / DECOY_DIR
    open_library(root, probe=_local).put(envelope(0))
    (root / "library" / "LAYOUT").write_text(json.dumps({"layout": 99}), encoding="utf-8")
    codes = {f.code for f in _fsck.check(root).items}
    assert LIBRARY_LAYOUT_NEWER in codes and "layout_newer" not in codes


def test_every_code_a_damaged_library_prints_is_registered(tmp_path: Path) -> None:
    root = tmp_path / DECOY_DIR
    library = open_library(root, probe=_local)
    ids = [library.put(envelope(n)).id for n in range(3)]
    object_path(root, ids[0]).write_bytes(b"{broken")
    (root / "library" / "objects" / "zz").write_bytes(b"stray")
    refs = root / "library" / "refs" / "sample-run"
    refs.mkdir(parents=True)
    (refs / "gone").write_text(envelope(9).id + "\n", encoding="utf-8")
    (refs / "junk").write_text("not an id\n", encoding="utf-8")
    stale = root / "library" / "tmp" / ".x.decoy-1.tmp"
    stale.write_bytes(b"partial")
    os.utime(stale, (1, 1))
    registered = {(d.code, d.level) for d in _fsck_codes.FINDINGS}
    report = _fsck.check(root)
    assert len(report.items) >= 5  # non-vacuous
    assert {(f.code, f.level) for f in report.items} <= registered
    actions, _after = _fsck.repair(root, probe=_local)
    assert {a.code for a in actions} <= {a.code for a in _fsck_codes.ACTIONS}
    assert actions


@pytest.mark.parametrize("repair", ["quarantine", "delete_temp", "remove_ref"])
def test_each_repair_is_reached_only_through_its_descriptors(repair: str) -> None:
    owners = {d.code for d in _fsck_codes.FINDINGS if d.repair == repair}
    assert owners  # every repair kind has at least one finding that allows it
