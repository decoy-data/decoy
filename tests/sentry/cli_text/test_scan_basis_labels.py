"""A count taken from a sample says so: every `--json` object that holds a scan count has a `basis`.

`null_rate`, `null_count` and `distinct_count` come from the rows a scan read, which is a sample
unless the basis is `whole`. In the committed `--json` shapes, each such leaf needs a `basis`
member on its own object or on an ancestor (the table object), so no payload shows a sample
number with no label beside it.
"""

from __future__ import annotations

import json
from pathlib import Path

SHAPES = Path(__file__).resolve().parents[2] / "fixtures" / "release_freeze" / "json-shapes.json"
COUNT_LEAVES = ("null_rate", "null_count", "distinct_count")


def _unlabelled(paths: dict[str, str]) -> list[str]:
    found = []
    for path in paths:
        parent, _, leaf = path.rpartition("/")
        if leaf not in COUNT_LEAVES:
            continue
        # The object that holds the leaf, then each ancestor object up to the root.
        owners = [parent]
        while owners[-1]:
            owners.append(owners[-1].rpartition("/")[0])
        if not any(f"{owner}/basis" in paths for owner in owners):
            found.append(path)
    return found


def test_every_count_in_the_json_shapes_sits_under_a_basis() -> None:
    shapes = json.loads(SHAPES.read_text(encoding="utf-8"))
    missing = {
        command: bad
        for command, entry in shapes.items()
        if (bad := _unlabelled(entry.get("paths", {})))
    }
    assert missing == {}


def test_an_unlabelled_count_is_found() -> None:
    assert _unlabelled({"/field/null_rate": "number"}) == ["/field/null_rate"]
    assert _unlabelled({"/field/null_rate": "number", "/basis": "string"}) == []
    assert _unlabelled({"/tables[]/fields[]/distinct_count": "integer"}) != []
    labelled = {"/tables[]/fields[]/distinct_count": "integer", "/tables[]/basis": "string"}
    assert _unlabelled(labelled) == []
