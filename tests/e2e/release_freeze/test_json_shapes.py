"""AT-F2b and AT-F2c: one value-free shape per `--json` command, held byte for byte.

The snapshot `tests/fixtures/release_freeze/json-shapes.json` records key paths and JSON types of
one success document per leaf command. A change to any of them shows up as a snapshot diff in review;
a person regenerates it with `python -m tests.e2e.release_freeze.write_shapes`.
"""

from __future__ import annotations

import json

import pytest

from tests.command_tree import json_leaf_commands
from tests.e2e.release_freeze import write_shapes as ws


def test_shape_writer_emits_types_never_values() -> None:
    doc = {
        "name": ws.MARKER_VAL,
        "count": 3,
        "ratio": 0.5,
        "ok": True,
        "none": None,
        "rows": [{"id": 1, "tag": ws.MARKER_VAL}, {"id": 2, "extra": [1]}],
        "by_column": {ws.MARKER_COL: {"n": 1}, "other": {"n": 2, "m": "x"}},
        "host_only": {"a": 1},
    }
    shape = ws.shape_of(doc, ["/by_column"], ["/host_only"])
    text = json.dumps(shape)
    assert ws.MARKER_VAL not in text and ws.MARKER_COL not in text
    assert shape == {
        "by_column": {"*": {"m": "string", "n": "integer"}},
        "count": "integer",
        "name": "string",
        "none": "null",
        "ok": "boolean",
        "ratio": "number",
        "rows": [{"extra": ["integer"], "id": "integer", "tag": "string"}],
    }


def test_flatten_names_one_path_per_line() -> None:
    shape = ws.shape_of(
        {"a": {"b": 1}, "rows": [{"id": 1}], "none": [], "empty": {}, "tags": ["x"]}
    )
    assert ws.flatten(shape) == {
        "/a/b": "integer",
        "/empty": "{}",
        "/none": "[]",
        "/rows[]/id": "integer",
        "/tags[]": "string",
    }


def test_an_undeclared_map_would_leak_its_keys() -> None:
    """The negative control: without the declaration the marker column name reaches the shape."""
    shape = ws.shape_of({"by_column": {ws.MARKER_COL: 1}})
    assert ws.MARKER_COL in json.dumps(shape)


@pytest.fixture(scope="module")
def captured() -> dict:
    return ws.snapshot()


def test_the_snapshot_holds_no_marker(captured: dict) -> None:
    """The workspace plants the marker as a column name and a cell value in every table it can."""
    assert ws.MARKER_COL not in ws.render(captured)
    assert ws.MARKER_VAL not in ws.render(captured)


def test_every_json_command_matches_its_snapshot(captured: dict) -> None:
    committed = ws.SNAPSHOT.read_text(encoding="utf-8")
    assert ws.render(captured) == committed, (
        "a `--json` document changed shape: regenerate with "
        "`python -m tests.e2e.release_freeze.write_shapes`, review the diff, and note it in CHANGELOG.md"
    )


def test_the_snapshot_names_every_json_command_once() -> None:
    entries = json.loads(ws.SNAPSHOT.read_text(encoding="utf-8"))
    assert set(entries) == json_leaf_commands()
    assert set(ws.EXEMPT) <= set(entries)
    assert all("exempt" in entries[name] for name in ws.EXEMPT)
