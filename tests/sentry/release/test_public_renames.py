"""AT-S7d: the public renames table lists every pair of the detection taxonomy map.

The engine split its prototype package into `detection`, `profiling` and `verification` and renamed
six symbols (engine CHANGELOG, "taxonomy rename: engine half"). A migrator who still has the old
spelling needs one place that maps it to the new one: `docs/release/public-renames.md`. This sentry
holds the pairs (the taxonomy map), checks that the table lists each one, and checks that each old
name is in the retired-name residual list, the only list that lets the old spelling sit in a
tracked file. The old names hold the retired word, so they are built from `RETIRED_NAME`.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.sentry.release.test_retired_name_residual import (
    RENAMES_DOC,
    RETIRED_NAME,
    RETIRED_SYMBOLS,
    ROOT,
    violations,
)

_W = RETIRED_NAME
_C = RETIRED_NAME.capitalize()
# old -> new, from the engine taxonomy rename. The module row names the three new packages.
TAXONOMY_MAP: dict[str, str] = {
    f"run_{_W}": "profile_columns",
    f"{_C}Profile": "ColumnProfile",
    f"run_{_W}_post_mask": "run_post_mask",
    f"{_C}PostMaskReport": "PostMaskReport",
    f"{_W}_profiles_to_snapshot": "profiles_to_snapshot",
    f"_run_{_W}_inner": "_profile_columns_inner",
    f"decoy_engine.{_W}": "decoy_engine.detection, decoy_engine.profiling, decoy_engine.verification",
}
DOC = ROOT / RENAMES_DOC
ROW = re.compile(r"^\| `([^`]+)` \| ([^|]+?) \|", re.MULTILINE)


def table_pairs(text: str) -> dict[str, str]:
    """Old name -> new cell of every `| `old` | new |` row."""
    return {m.group(1): m.group(2).replace("`", "") for m in ROW.finditer(text)}


def table_findings(text: str, taxonomy: dict[str, str], residual: tuple[str, ...]) -> list[str]:
    pairs = table_pairs(text)
    found = [f"table lacks {old}" for old in taxonomy if old not in pairs]
    found += [
        f"table maps {old} to {pairs[old]!r}, not {new!r}"
        for old, new in taxonomy.items()
        if old in pairs and pairs[old] != new
    ]
    found += [f"table has an extra row {old}" for old in pairs if old not in taxonomy]
    found += [f"{old} is not in the residual list" for old in taxonomy if old not in residual]
    return found


def test_the_real_table_is_clean() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert table_findings(text, TAXONOMY_MAP, RETIRED_SYMBOLS) == []


def test_the_residual_list_is_exactly_the_old_names() -> None:
    assert set(RETIRED_SYMBOLS) == set(TAXONOMY_MAP)


def test_the_doc_is_the_only_allowed_file_and_holds_only_table_rows() -> None:
    lines = DOC.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if _W in line.lower():
            assert ROW.match(line), f"the retired word outside a table row: {line[:60]}"


def test_the_doc_is_allowed_by_the_residual_sentry() -> None:
    data = DOC.read_bytes()
    assert violations({RENAMES_DOC: data}, {}) == []
    assert violations({"docs/release/other.md": data}, {}) != []


def test_seed_a_dropped_pair_is_found() -> None:
    text = DOC.read_text(encoding="utf-8")
    kept = "\n".join(ln for ln in text.splitlines() if not ln.startswith(f"| `run_{_W}` |"))
    assert f"table lacks run_{_W}" in table_findings(kept, TAXONOMY_MAP, RETIRED_SYMBOLS)


def test_seed_a_wrong_new_name_is_found() -> None:
    text = DOC.read_text(encoding="utf-8").replace("`profile_columns`", "`profile_rows`", 1)
    assert table_findings(text, TAXONOMY_MAP, RETIRED_SYMBOLS)


def test_seed_an_old_name_missing_from_the_residual_list_is_found() -> None:
    text = DOC.read_text(encoding="utf-8")
    residual = tuple(s for s in RETIRED_SYMBOLS if s != f"run_{_W}")
    assert table_findings(text, TAXONOMY_MAP, residual) == [f"run_{_W} is not in the residual list"]


def test_doc_path_is_under_the_repo() -> None:
    assert isinstance(DOC, Path) and DOC.parent.is_dir()
