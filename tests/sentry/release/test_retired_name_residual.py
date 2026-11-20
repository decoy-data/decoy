"""AT-S2 and AT-C7: the retired product name appears in no tracked file outside the history list.

The owner decided that a V1 user never meets the retired name in the CLI. The one choke point is
a scan of the real artifact: every path and every text file that `git` tracks (plus untracked,
not-ignored files, so uncommitted work is seen too). A file is clean when neither its path nor any
line of its content matches, unless it is under `HISTORY` (dated records nobody edits) or listed
in `PENDING` (files not yet migrated, with their live hit-line count).

`PENDING` lives in `tests/sentry/baselines/retired-name-pending.json`, a registered baseline, and
`scripts/dev/ratchet_check.py` blocks any added key. Slices C1b and C2 lower it; slice C3 deletes the
file and its registry row, and this sentry becomes absolute.

`PENDING` is a shrink-only ratchet: a file with hits that is in neither list fails, and a count
that differs from the live count in either direction fails, so every slice lowers it. The last
slice deletes it and the sentry becomes absolute. Adding a key or raising a count is a stop line.

The name is spelled in two pieces so this file does not hold it. Other tests import
`RETIRED_NAME` and `RETIRED_PATTERN` from here, so there is one place that knows the spelling.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from tests.sentry._ratchet import load_allowlist

ROOT = Path(__file__).resolve().parents[3]
THIS_FILE = "tests/sentry/release/test_retired_name_residual.py"

RETIRED_NAME = "st" + "orm"
RETIRED_PATTERN = re.compile(RETIRED_NAME, re.IGNORECASE)
# The name rebuilt from quoted pieces ("St" + "orm", 's' 'torm'). A hit needs a quote in the span,
# so ordinary prose with the letters in a row is the plain pattern's job.
SPLIT_PATTERN = re.compile(r"[\s'\"+]*".join(RETIRED_NAME), re.IGNORECASE)


@dataclass(frozen=True)
class Allowed:
    glob: str
    purpose: str


HISTORY_ROOTS = (
    "docs/plans/",
    "docs/records/",
    "docs/archive/",
    "docs/superpowers/plans/",
    "docs/overnight-dev/findings/",
    "docs/handoffs/",
    "docs/roadmap/decisions.md",
    "docs/RECENTLY-SHIPPED.md",
)

HISTORY = (
    Allowed("docs/plans/*", "dated plans"),
    Allowed("docs/records/*", "dated QA, health and census records"),
    Allowed("docs/archive/*", "archived shipped logs"),
    Allowed("docs/superpowers/plans/*", "a dated plan in the old plan folder"),
    Allowed("docs/overnight-dev/findings/*", "a dated review finding"),
    Allowed(
        "docs/handoffs/[0-9][0-9][0-9][0-9]-*", "dated handoffs; a new undated file is not history"
    ),
    Allowed("docs/roadmap/decisions.md", "the dated owner decision log"),
    Allowed("docs/RECENTLY-SHIPPED.md", "the dated shipped log"),
)


# The one tracked file outside history that may spell the old public names: the table that maps
# each retired symbol to its new one. `test_public_renames.py` checks the table row by row and
# that no other line in the file holds the word. RETIRED_SYMBOLS is the residual list of old names.
RENAMES_DOC = "docs/release/public-renames.md"
RETIRED_SYMBOLS = (
    f"run_{RETIRED_NAME}",
    f"{RETIRED_NAME.capitalize()}Profile",
    f"run_{RETIRED_NAME}_post_mask",
    f"{RETIRED_NAME.capitalize()}PostMaskReport",
    f"{RETIRED_NAME}_profiles_to_snapshot",
    f"_run_{RETIRED_NAME}_inner",
    f"decoy_engine.{RETIRED_NAME}",
)


# {path: lines that still carry the name}, kept in a registered baseline so the ratchet check
# lets it only shrink. A path that holds the name is written with `{n}` in the file.
def _pending() -> dict[str, int]:
    entries = load_allowlist("retired-name-pending")
    return {path.format(n=RETIRED_NAME): int(e["max"]) for path, e in entries.items()}


def is_history(path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, a.glob) for a in HISTORY)


def _is_binary(data: bytes) -> bool:
    return b"\0" in data[:8000]


def hit_lines(data: bytes, *, split_exempt: bool = False) -> int | str:
    """Content lines with a hit, or `'undecodable'` for a text file that is not UTF-8."""
    if _is_binary(data):
        return 0
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "undecodable"
    count = 0
    for line in text.splitlines():
        if RETIRED_PATTERN.search(line):
            count += 1
        elif not split_exempt and any(
            "'" in m.group(0) or '"' in m.group(0) for m in SPLIT_PATTERN.finditer(line)
        ):
            count += 1
    return count


def violations(files: Mapping[str, bytes], pending: Mapping[str, int]) -> list[str]:
    out: list[str] = []
    seen_pending: set[str] = set()
    for path, data in sorted(files.items()):
        if is_history(path) or path == RENAMES_DOC:
            continue
        path_hit = bool(RETIRED_PATTERN.search(path))
        lines = hit_lines(data, split_exempt=path == THIS_FILE)
        if lines == "undecodable":
            out.append(f"{path}: undecodable")
            continue
        assert isinstance(lines, int)
        if not path_hit and lines == 0:
            continue
        if path not in pending:
            out.append(f"{path}: {lines} line(s)" + (", path" if path_hit else ""))
            continue
        seen_pending.add(path)
        if pending[path] != lines:
            out.append(f"{path}: PENDING says {pending[path]}, live count is {lines}")
    out.extend(
        f"{path}: in PENDING but clean or missing" for path in sorted(set(pending) - seen_pending)
    )
    return out


def root_violations(history: tuple[Allowed, ...], roots: tuple[str, ...]) -> list[str]:
    return [a.glob for a in history if not a.glob.startswith(roots)]


def tracked_files() -> dict[str, bytes]:
    names = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    files: dict[str, bytes] = {}
    for raw in names:
        if not raw:
            continue
        path = raw.decode()
        full = ROOT / path
        if full.is_file():  # a file deleted or renamed in the working tree is skipped
            files[path] = full.read_bytes()
    return files


def test_no_retired_name_outside_history_and_pending() -> None:
    found = violations(tracked_files(), _pending())
    assert not found, "the retired name is still present:\n" + "\n".join(found)


def test_history_globs_sit_under_the_fixed_roots() -> None:
    assert root_violations(HISTORY, HISTORY_ROOTS) == []


def test_history_roots_are_all_docs() -> None:
    assert [r for r in HISTORY_ROOTS if not r.startswith("docs/")] == []


# AT-C7: the engine keeps the old identity pair of a decoded unknown reason in its context. No CLI
# source may name that field, so no output can render the old pair. A source-text proxy: it does
# not prove every rendering path drops the field (a record can pass through the engine and
# re-emit it). A future renderer must delete or narrow this test in review.
def test_no_cli_source_renders_original_identity() -> None:
    offenders = [
        str(p.relative_to(ROOT))
        for p in sorted((ROOT / "src" / "decoy").rglob("*.py"))
        if "original_identity" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


# Seeds: one violation per surface. Each must be reported, or the sentry misses that surface.
_NAME = RETIRED_NAME
_CAP = RETIRED_NAME.capitalize()
SEEDS = {
    "a path under src": ("src/decoy/ui/" + _NAME + "_cloud.py", b"x = 1\n"),
    "a python identifier": ("src/decoy/cli/scan.py", f"{_NAME}_value = 1\n".encode()),
    "a help string": ("src/decoy/cli/scan.py", f'help="Path to a {_CAP} scan"\n'.encode()),
    "a yaml comment": (
        "src/decoy/templates/x.yaml",
        f"# {_NAME.upper()} detected email\n".encode(),
    ),
    "a json schema description": (
        "docs/schemas/x.schema.json",
        f'{{"description": "{_CAP} scan"}}\n'.encode(),
    ),
    "a test file name": ("tests/e2e/test_" + _NAME + "_x.py", b"def test_x(): pass\n"),
    "a doc page": ("docs/guide.md", f"The {_CAP} page.\n".encode()),
    "a changelog line": ("CHANGELOG.md", f"## [Unreleased]\n- {_CAP} output\n".encode()),
    "a quote-split literal": ("src/decoy/cli/scan.py", b'x = "St" + "orm"\n'),
    "a single-quote split literal": ("src/decoy/cli/scan.py", b"x = 's' 'torm'\n"),
    "a latin-1 file": ("docs/guide.md", f"caf\xe9 {_CAP}\n".encode("latin-1")),
}


@pytest.mark.parametrize("surface", sorted(SEEDS))
def test_seed_is_reported(surface: str) -> None:
    path, data = SEEDS[surface]
    assert violations({path: data}, {}), surface


def test_seed_under_history_is_allowed() -> None:
    data = f"The {_CAP} plan.\n".encode()
    assert violations({"docs/plans/2026-11-16-x.md": data}, {}) == []


def test_undated_handoff_is_not_history() -> None:
    data = f"The {_CAP} note.\n".encode()
    assert violations({"docs/handoffs/notes.md": data}, {})


def test_binary_file_gets_only_the_path_check() -> None:
    assert violations({"docs/a.png": b"\0" + _CAP.encode()}, {}) == []
    assert violations({"docs/" + _NAME + ".png": b"\0"}, {})


def test_pending_count_must_match_in_both_directions() -> None:
    data = f"one {_NAME}\ntwo {_NAME}\n".encode()
    assert violations({"a.md": data}, {"a.md": 2}) == []
    assert violations({"a.md": data}, {"a.md": 3})
    assert violations({"a.md": data}, {"a.md": 1})
    assert violations({"a.md": b"clean\n"}, {"a.md": 1})


def test_a_prose_split_without_a_quote_is_not_a_split_hit() -> None:
    assert hit_lines(b"s t o r m\n") == 0


def test_this_file_is_exempt_from_the_split_pattern_only() -> None:
    assert violations({THIS_FILE: b'RETIRED_NAME = "st" + "orm"\n'}, {}) == []
    assert violations({THIS_FILE: f"{_NAME}\n".encode()}, {})


def test_roots_check_rejects_a_glob_outside_the_roots() -> None:
    assert root_violations((Allowed("src/decoy/*", "x"),), HISTORY_ROOTS) == ["src/decoy/*"]
