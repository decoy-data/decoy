"""Fixed-width layout file rules for `decoy scan` (the readers live in the engine).

A layout is a list of `{name, start, width}` columns, given as a YAML or JSON file or as a parsed
list. This module imports nothing from `decoy.cli.scan`, so the scan report code can use it
without a cycle.
"""

from __future__ import annotations

from pathlib import Path


def _check_layout_columns(columns: list) -> list[dict]:
    """Check each layout column; one rule set for a layout file and for a parsed list."""
    for i, col in enumerate(columns):
        if not isinstance(col, dict):
            raise ValueError(
                f"layout column {i}: expected a dict, got {type(col).__name__} - "
                "each column needs a string 'name' and integer 'start'/'width'."
            )
        name = col.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"layout column {i} ({name!r}): missing or empty 'name' - "
                "each column needs a string 'name' and integer 'start'/'width'."
            )
        for key in ("start", "width"):
            val = col.get(key)
            if val is None:
                raise ValueError(
                    f"layout column {i} ({name!r}): missing '{key}' - "
                    "each column needs a string 'name' and integer 'start'/'width'."
                )
            try:
                int_val = int(val)
            except (TypeError, ValueError):
                raise ValueError(
                    f"layout column {i} ({name!r}): '{key}' must be an integer, got {val!r} - "
                    "each column needs a string 'name' and integer 'start'/'width'."
                )
            if key == "start" and int_val < 0:
                raise ValueError(
                    f"layout column {i} ({name!r}): 'start' must be >= 0, got {int_val} - "
                    "each column needs a string 'name' and integer 'start'/'width'."
                )
            if key == "width" and int_val <= 0:
                raise ValueError(
                    f"layout column {i} ({name!r}): 'width' must be > 0, got {int_val} - "
                    "each column needs a string 'name' and integer 'start'/'width'."
                )

    return list(columns)


def _parse_layout(layout_path: Path) -> list[dict]:
    """Load a layout spec from a YAML or JSON file.

    Expected shape (YAML or JSON):
        columns:
          - name: field_name
            start: 0      # 0-indexed start position (inclusive)
            width: 10     # column width in characters

    Returns the `columns` list.
    """
    import json as _json_mod

    import yaml as _yaml

    text = layout_path.read_text(encoding="utf-8")
    try:
        data = _yaml.safe_load(text)
    except _yaml.YAMLError:
        data = _json_mod.loads(text)

    if not isinstance(data, dict) or "columns" not in data:
        raise ValueError(
            f"Layout file {layout_path.name} must be a mapping with a 'columns' key. "
            "Each column must have 'name', 'start', and 'width'."
        )

    columns = data["columns"]
    if not isinstance(columns, list):
        raise ValueError(
            f"Layout file {layout_path.name}: 'columns' must be a list of column dicts, "
            f"got {type(columns).__name__}. Each column needs a string 'name' and integer 'start'/'width'."
        )

    return _check_layout_columns(columns)
