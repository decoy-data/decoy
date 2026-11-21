"""AT-S2b: every hidden command and option has a tier row in `docs/release/frozen-surfaces.md`.

The sentry walks the real Click tree with `tests.command_tree.walk()` and reads the one map row whose
surface is "Hidden commands and options". Its "Completeness source" cell lists `name: tier` spans.
A command's name is its space-joined path (`scan _scan`); an option's name is the command path then
the flag (`ci check --unsafe-debug-log`). A hidden name with no span fails, a span naming something that
no longer exists fails, and the tier must match the rule: a hidden command whose last segment starts
with `_` is `internal`, every other hidden command or option is `frozen-hidden`.

Seeded mutations (each makes the named test red): add `hidden=True` to any option of `run`
(`test_the_real_map_is_clean`); delete a span from the row (`test_a_dropped_span_is_found`);
rename `_gate` in the map (`test_a_stale_span_is_found`); change a tier (`test_a_wrong_tier_is_found`);
mark every command visible (`test_the_walk_finds_the_known_names`).
"""

from __future__ import annotations

import re
from pathlib import Path

import typer.main
from tests.command_tree import walk

from decoy.__main__ import app

ROOT = Path(__file__).resolve().parents[3]
MAP = ROOT / "docs" / "release" / "frozen-surfaces.md"
ROW_SURFACE = "Hidden commands and options"
TIERS = ("internal", "frozen-hidden")
SPAN = re.compile(r"`([^`]+): (internal|frozen-hidden)`")
# The names the plan lists. The walk is the source of truth; this only proves the walk sees them.
KNOWN = {"scan _scan", "validate _gate", "upgrade --url", "ci check --unsafe-debug-log"}


def tier_of(name: str, is_option: bool) -> str:
    last = name.split()[-1]
    return "internal" if not is_option and last.startswith("_") else "frozen-hidden"


def hidden_names() -> dict[str, str]:
    """Every hidden command path and hidden option in the live tree, with its rule tier."""
    root = typer.main.get_command(app)
    found: dict[str, str] = {}
    for node in walk():
        cmd = root
        for part in node.path:
            cmd = cmd.commands[part]  # type: ignore[attr-defined]
        name = " ".join(node.path)
        if node.hidden:
            found[name] = tier_of(name, False)
        for param in cmd.params:
            if getattr(param, "hidden", False) and getattr(param, "opts", None):
                flag = max(param.opts, key=len)
                key = f"{name} {flag}"
                found[key] = tier_of(key, True)
    return found


def map_row(text: str) -> str:
    rows = [ln for ln in text.splitlines() if ln.startswith(f"| {ROW_SURFACE} |")]
    assert len(rows) == 1, f"the map needs exactly one '{ROW_SURFACE}' row, found {len(rows)}"
    return rows[0]


def mapped(text: str) -> dict[str, str]:
    cell = map_row(text).strip().strip("|").split("|")[1]
    return {name: tier for name, tier in SPAN.findall(cell)}


def findings(text: str, live: dict[str, str] | None = None) -> list[str]:
    """Why the map's hidden-names row is not true for the live tree; empty when it is."""
    live = hidden_names() if live is None else live
    listed = mapped(text)
    found = [f"hidden name with no tier row: {n}" for n in sorted(live.keys() - listed.keys())]
    found += [f"tier row for a name that is gone: {n}" for n in sorted(listed.keys() - live.keys())]
    found += [
        f"wrong tier for {n}: map says {listed[n]}, rule says {live[n]}"
        for n in sorted(live.keys() & listed.keys())
        if listed[n] != live[n]
    ]
    return found


def test_the_walk_finds_the_known_names() -> None:
    assert KNOWN <= hidden_names().keys()


def test_internal_names_start_with_an_underscore() -> None:
    for name, tier in hidden_names().items():
        assert (tier == "internal") == (name.split()[-1].startswith("_")), name


def test_the_real_map_is_clean() -> None:
    assert findings(MAP.read_text(encoding="utf-8")) == []


def test_the_row_uses_only_known_tiers() -> None:
    cell = map_row(MAP.read_text(encoding="utf-8")).strip().strip("|").split("|")[1]
    assert len(SPAN.findall(cell)) == cell.count("`") // 2


def test_a_dropped_span_is_found() -> None:
    text = MAP.read_text(encoding="utf-8")
    for name in hidden_names():
        seeded = re.sub(rf"`{re.escape(name)}: [a-z-]+`;? ?", "", text, count=1)
        assert any(f.endswith(name) for f in findings(seeded)), name


def test_a_stale_span_is_found() -> None:
    text = MAP.read_text(encoding="utf-8").replace("`validate _gate:", "`validate _gone:", 1)
    got = findings(text)
    assert "tier row for a name that is gone: validate _gone" in got
    assert "hidden name with no tier row: validate _gate" in got


def test_a_wrong_tier_is_found() -> None:
    text = MAP.read_text(encoding="utf-8").replace(
        "`upgrade --url: frozen-hidden`", "`upgrade --url: internal`", 1
    )
    assert any(f.startswith("wrong tier for upgrade --url") for f in findings(text))


def test_a_new_hidden_name_is_found() -> None:
    live = {**hidden_names(), "run --new-secret": "frozen-hidden"}
    assert "hidden name with no tier row: run --new-secret" in findings(
        MAP.read_text(encoding="utf-8"), live
    )
