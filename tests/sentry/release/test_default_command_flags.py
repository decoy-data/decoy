"""The hidden default commands behind `decoy scan SOURCES` and `decoy validate CONFIG` are frozen.

`scan _scan` and `validate _gate` are hidden only so the group can dispatch to them. A user types
`decoy scan` and `decoy validate`, so their flags and `--json` documents are in the contract.
This sentry fails when a flag of either command is removed or renamed without
`docs/cli-reference.md` (generated, so it moves with the source help) showing it, and when the
allow-list in `tests/command_tree.py` stops matching the live tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.command_tree import PUBLIC_DEFAULT_COMMANDS, commands, json_leaf_commands, options

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "docs" / "cli-reference.md"
SNAPSHOT = ROOT / "tests" / "fixtures" / "release_freeze" / "json-shapes.json"


def _section(text: str, name: str) -> str:
    """The generated reference text of `decoy <name>`, up to its first subcommand heading."""
    start = text.index(f"\n## `decoy {name}`\n")
    end = text.find("\n### ", start)
    return text[start : end if end != -1 else len(text)]


def _flags(path: tuple[str, ...]) -> list[str]:
    """Every long and short spelling of every visible option of the command at `path`."""
    return sorted(
        {
            s
            for o in options()
            if o.cmd.path == path and not o.hidden
            for s in o.spellings
            if s.startswith("-") and s not in ("--help",)
        }
    )


def test_the_allow_list_names_live_hidden_commands() -> None:
    live = {c.path: c.hidden for c in commands()}
    for path, public in PUBLIC_DEFAULT_COMMANDS.items():
        assert live.get(path) is True, f"{path} is not a live hidden command"
        assert live.get(public) is not None, f"{public} is not a live command"


@pytest.mark.parametrize("path", sorted(PUBLIC_DEFAULT_COMMANDS))
def test_every_flag_is_shown_in_the_reference(path: tuple[str, ...]) -> None:
    text = _section(REFERENCE.read_text(encoding="utf-8"), PUBLIC_DEFAULT_COMMANDS[path][0])
    flags = _flags(path)
    assert flags, path
    missing = [f for f in flags if f not in text]
    assert missing == [], f"{' '.join(path)}: flags missing from docs/cli-reference.md: {missing}"


def test_the_named_flags_still_exist() -> None:
    scan = set(_flags(("scan", "_scan")))
    assert {
        "--has-header",
        "--no-header",
        "--column-names",
        "--rows",
        "--strategy",
        "--format",
        "--layout",
        "--detectors",
        "--ner-model",
        "--show-fields",
    } <= scan
    assert "--fail-on-warning" in _flags(("validate", "_gate"))


def test_the_snapshot_holds_both_json_documents_and_no_other_hidden_command() -> None:
    entries = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert {"scan", "validate"} <= set(entries)
    assert set(entries) == json_leaf_commands()
    hidden_json = {
        " ".join(o.cmd.path)
        for o in options()
        if o.cmd.hidden and not o.cmd.is_group and "--json" in o.spellings
    }
    assert {"scan _scan", "validate _gate"} <= hidden_json  # the raw names stay out of the snapshot
    assert not any(name in entries for name in hidden_json)
