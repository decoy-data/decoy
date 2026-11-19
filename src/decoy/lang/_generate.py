"""`generate` blocks to the engine's generate tables.

A column is `name = generator(...)`. The generator's plain values fill its required options in the
order the engine's catalog lists them, so `sequence(1000)` is `start: 1000` and
`reference(patients, patient_id)` names the table and the column; every `key: value` option rides
flat on the column, as the engine reads it. The catalog (`generate_option_catalog()`) is the only
list of generator names and options.

Three shorter forms: `name <- table.column` is a `reference` column (the same arrow a masked table
uses for a foreign key); `name = expression` is a `derived` column; and `categorical` takes a
`{value: weight}` map, which keeps each weight beside its category instead of in a second list.
"""

from __future__ import annotations

import difflib
from functools import lru_cache
from typing import Any

from decoy_engine.config import generate_option_catalog

from decoy.lang import _ast as nodes
from decoy.lang._connectors import SourceMap, lower_connector, plain
from decoy.lang._errors import Diagnostic, LangError, fail


@lru_cache(maxsize=1)
def generators() -> dict[str, tuple[str, ...]]:
    """Each generator type with the options its plain values fill, in order."""
    return {name: tuple(spec.required) for name, spec in generate_option_catalog().items()}


def lower_generate(table: nodes.Generate, config: dict[str, Any], spans: SourceMap) -> None:
    name = table.name.text
    index = len(config["tables"])
    target = lower_connector(table.target, is_source=False, path=("targets", name), spans=spans)
    columns: list[dict[str, Any]] = []
    unique_together: list[list[str]] = []
    seen: dict[str, nodes.Name] = {}
    problems: list[Diagnostic] = []
    for statement in table.statements:
        if isinstance(statement, nodes.Unique):
            spans[("tables", index, "unique_together", len(unique_together))] = statement.span
            unique_together.append([column.text for column in statement.columns])
            continue
        column = statement.name
        if column.text in seen:
            first = seen[column.text].span
            problems.append(
                Diagnostic(
                    "lang.column_repeated",
                    f"column `{column.text}` is already defined on line {first.line}",
                    column.span,
                )
            )
            continue
        seen[column.text] = column
        path = ("tables", index, "generate_columns", len(columns))
        spans[path] = statement.span
        spans[(*path, "name")] = column.span
        try:
            columns.append({"name": column.text, **_column(statement, path, spans)})
        except LangError as error:
            problems.extend(error.diagnostics)
    if problems:
        raise LangError(problems)
    spans[("tables", index)] = table.span
    spans[("tables", index, "name")] = table.name.span
    spans[("tables", index, "row_count")] = table.rows.span
    entry: dict[str, Any] = {
        "name": name,
        "row_count": plain(table.rows),
        "generate_columns": columns,
    }
    if unique_together:
        entry["unique_together"] = unique_together
    config["tables"].append(entry)
    config["targets"][name] = target


def _column(
    statement: nodes.GenColumn | nodes.GenLink, path: tuple[Any, ...], spans: SourceMap
) -> dict[str, Any]:
    if isinstance(statement, nodes.GenLink):
        spans[(*path, "reference_table")] = statement.parent_table.span
        spans[(*path, "reference_column")] = statement.parent_column.span
        return {
            "type": "reference",
            "reference_table": statement.parent_table.text,
            "reference_column": statement.parent_column.text,
        }
    call = statement.call
    if call is None or call.name.text not in generators():
        if statement.expression is None:
            assert call is not None
            close = difflib.get_close_matches(call.name.text, sorted(generators()), n=1)
            raise fail(
                "lang.unknown_generator",
                f"`{call.name.text}` is not a generator",
                call.name.span,
                f"did you mean `{close[0]}`?" if close else None,
            )
        spans[(*path, "expression")] = statement.expression.span
        return {"type": "derived", "expression": statement.expression.text}
    kind = call.name.text
    spans[(*path, "type")] = call.name.span
    out: dict[str, Any] = {"type": kind}
    fills = generators()[kind]
    if len(call.positional) > len(fills):
        takes = ", ".join(fills) if fills else "none"
        raise fail(
            "lang.generator_arguments",
            f"`{kind}` takes at most {len(fills)} plain value(s): {takes}",
            call.positional[len(fills)].span,
            "write the other values as `key: value` options",
        )
    for key, value in zip(fills, call.positional, strict=False):
        if kind == "categorical" and isinstance(value.value, dict):
            out["categories"] = list(value.value)
            out["weights"] = [plain(weight) for weight in value.value.values()]
            spans[(*path, "categories")] = spans[(*path, "weights")] = value.span
            continue
        out[key] = plain(value)
        spans[(*path, key)] = value.span
    for option in call.options:
        key = option.key.text
        if key in ("name", "type"):
            raise fail("lang.option_not_allowed", f"`{key}` is not an option", option.key.span)
        if key in out:
            raise fail("lang.option_repeated", f"`{key}` is given twice", option.key.span)
        out[key] = plain(option.value)
        spans[(*path, key)] = option.value.span
    return out
