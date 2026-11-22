"""AT-S2, AT-C7 and AT-C8: the retired product name appears in no tracked file outside the history list.

The owner decided that a V1 user never meets the retired name in the CLI. The one choke point is
a scan of the real artifact: every path and every text file that `git` tracks (plus untracked,
not-ignored files, so uncommitted work is seen too). A file is clean when neither its path nor any
line of its content matches, unless it is under `HISTORY` (dated records nobody edits).

The sentry is absolute: there is no pending list. A new exception needs a `HISTORY_ROOTS` change,
which is a stop line, and every `HISTORY_ROOTS` entry is also kept out of the sdist (`pyproject.toml`).

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

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

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


# The old public engine names from the detection taxonomy split. The engine contract (section 1) and
# the engine changelog own the table that maps each one to its new name; the CLI keeps this list
# only to prove no CLI source uses one. They are built from RETIRED_NAME like the name itself.
RETIRED_SYMBOLS = (
    f"run_{RETIRED_NAME}",
    f"{RETIRED_NAME.capitalize()}Profile",
    f"run_{RETIRED_NAME}_post_mask",
    f"{RETIRED_NAME.capitalize()}PostMaskReport",
    f"{RETIRED_NAME}_profiles_to_snapshot",
    f"_run_{RETIRED_NAME}_inner",
    f"decoy_engine.{RETIRED_NAME}",
)


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


def violations(files: Mapping[str, bytes]) -> list[str]:
    out: list[str] = []
    for path, data in sorted(files.items()):
        if is_history(path):
            continue
        path_hit = bool(RETIRED_PATTERN.search(path))
        lines = hit_lines(data, split_exempt=path == THIS_FILE)
        if lines == "undecodable":
            out.append(f"{path}: undecodable")
            continue
        assert isinstance(lines, int)
        if path_hit or lines:
            out.append(f"{path}: {lines} line(s)" + (", path" if path_hit else ""))
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


def test_no_retired_name_outside_history() -> None:
    found = violations(tracked_files())
    assert not found, "the retired name is still present:\n" + "\n".join(found)


def _old_name_pattern() -> re.Pattern[str]:
    return re.compile("|".join(rf"\b{re.escape(n)}\b" for n in RETIRED_SYMBOLS))


def test_no_cli_source_uses_an_old_public_engine_name() -> None:
    pattern = _old_name_pattern()
    offenders = [
        str(p.relative_to(ROOT))
        for p in sorted((ROOT / "src" / "decoy").rglob("*.py"))
        if pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_the_old_name_list_has_seven_names_and_finds_a_use() -> None:
    assert len(set(RETIRED_SYMBOLS)) == 7
    assert all(RETIRED_PATTERN.search(n) for n in RETIRED_SYMBOLS)
    for name in RETIRED_SYMBOLS:
        assert _old_name_pattern().search(f"x = {name}(1)"), name


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
    assert violations({path: data}), surface


def test_seed_under_history_is_allowed() -> None:
    data = f"The {_CAP} plan.\n".encode()
    assert violations({"docs/plans/2026-11-16-x.md": data}) == []


def test_undated_handoff_is_not_history() -> None:
    data = f"The {_CAP} note.\n".encode()
    assert violations({"docs/handoffs/notes.md": data})


def test_binary_file_gets_only_the_path_check() -> None:
    assert violations({"docs/a.png": b"\0" + _CAP.encode()}) == []
    assert violations({"docs/" + _NAME + ".png": b"\0"})


def test_a_prose_split_without_a_quote_is_not_a_split_hit() -> None:
    assert hit_lines(b"s t o r m\n") == 0


def test_this_file_is_exempt_from_the_split_pattern_only() -> None:
    assert violations({THIS_FILE: b'RETIRED_NAME = "st" + "orm"\n'}) == []
    assert violations({THIS_FILE: f"{_NAME}\n".encode()})


def test_roots_check_rejects_a_glob_outside_the_roots() -> None:
    assert root_violations((Allowed("src/decoy/*", "x"),), HISTORY_ROOTS) == ["src/decoy/*"]


# AT-C8: the sdist keeps every history root out, so no dated record ships. The list is derived from
# HISTORY_ROOTS one to one (trailing slash dropped), and the test suite stays excluded.
def test_sdist_excludes_every_history_root() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    exclude = set(data["tool"]["hatch"]["build"]["targets"]["sdist"]["exclude"])
    assert {r.rstrip("/") for r in HISTORY_ROOTS} <= exclude
    assert "tests" in exclude
