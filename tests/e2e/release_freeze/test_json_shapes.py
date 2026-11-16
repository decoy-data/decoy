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


def test_merge_keeps_object_paths_whatever_the_order() -> None:
    with_object, without = {"x": {"a": 1}}, {"x": None}
    first = ws.shape_of([with_object, without])
    second = ws.shape_of([without, with_object])
    assert first == second
    expected = {"/x": "null|object", "/x/a": "integer"}
    assert ws.flatten(first[0]) == expected and ws.flatten(second[0]) == expected
    assert ws._merge("null", {"a": "integer"}) == ws._merge({"a": "integer"}, "null")


def test_merge_of_equal_kinds_is_unchanged() -> None:
    assert ws._merge({"a": "integer"}, {"b": "string"}) == {"a": "integer", "b": "string"}
    assert ws._merge("integer", "null") == "integer|null"
    assert ws._merge(["integer"], []) == ["integer"]


def test_an_opaque_key_keeps_its_type_and_cannot_change_kind() -> None:
    shape = ws.shape_of({"w": [1, "x"]}, opaque={"/w": "array"})
    assert shape == {"w": "array"}
    with pytest.raises(ValueError, match="declared array"):
        ws.shape_of({"w": None}, opaque={"/w": "array"})


def test_an_undeclared_map_would_leak_its_keys() -> None:
    """The negative control: without the declaration the marker column name reaches the shape."""
    shape = ws.shape_of({"by_column": {ws.MARKER_COL: 1}})
    assert ws.MARKER_COL in json.dumps(shape)


@pytest.fixture(scope="module")
def captured_docs(tmp_path_factory: pytest.TempPathFactory) -> dict:
    return ws.capture(tmp_path_factory.mktemp("shapes"))


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


def test_the_exemption_set_is_exactly_the_five_known_commands() -> None:
    assert set(ws.EXEMPT) == {"doctor", "models install", "schema", "setup", "upgrade"}


def test_run_and_info_always_present_keys_are_pinned_not_optional() -> None:
    entries = json.loads(ws.SNAPSHOT.read_text(encoding="utf-8"))
    run, info = entries["run"], entries["info"]
    assert run["paths"]["/warnings"] == "array"
    assert info["paths"]["/native_companion"] == "null|object"
    assert run["optional_keys"] == ["/native_route", "/notify", "/report", "/subset"]
    assert "optional_keys" not in info


def test_removing_a_pinned_key_changes_the_flattened_shape(captured_docs: dict) -> None:
    """The negative control: a run document that lost "warnings" no longer matches its snapshot."""
    run = captured_docs["run"]
    pinned = ws.flatten(ws.shape_of(run, opaque=ws.OPAQUE["run"], optional=ws.OPTIONAL["run"]))
    assert "/warnings" in pinned
    trimmed = {k: v for k, v in run.items() if k != "warnings"}
    after = ws.flatten(ws.shape_of(trimmed, opaque=ws.OPAQUE["run"], optional=ws.OPTIONAL["run"]))
    assert after != pinned and "/warnings" not in after


def test_the_snapshot_names_every_json_command_once() -> None:
    entries = json.loads(ws.SNAPSHOT.read_text(encoding="utf-8"))
    assert set(entries) == json_leaf_commands()
    assert set(ws.EXEMPT) <= set(entries)
    assert all("exempt" in entries[name] for name in ws.EXEMPT)
