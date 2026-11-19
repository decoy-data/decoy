"""`subset { }` to the engine's `subset` block.

    subset {
      start customers sample 2% by customer_id
      start orders where total > 1000, status == 'open'
      start vips keys customer_id in [101, 102]
      follow customers.customer_id -> orders.customer_id downward
      budget(max_total_rows: 2_000_000)
      allow dangling
    }

`start` is a seed: a sample, a filter or a list of keys. The engine closes the slice over the
pipeline's foreign keys; `follow` sets the direction for one of them, named as the engine names
an edge, parent first. The conditions of a filter are the engine's predicates, one per
comparison, all of which must hold.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from decoy.lang import _ast as nodes
from decoy.lang._ast import plain
from decoy.lang._errors import Diagnostic, LangError, SourceMap, fail

SUBSET_SYNTAX = {"subset": "`subset { ... }`"}
# How a comparison is written, and the engine's name for it.
PREDICATES = {
    "==": "eq",
    "!=": "ne",
    "<": "lt",
    "<=": "le",
    ">": "gt",
    ">=": "ge",
    "in": "in",
    "is null": "is_null",
    "is not null": "is_not_null",
}


# The seed modes, as the engine names them.
SEED_MODES = ("sample", "filter", "keys")


def lower_subsets(
    subsets: tuple[nodes.Subset, ...],
    config: dict[str, Any],
    spans: SourceMap,
    problems: list[Diagnostic],
) -> None:
    if not subsets:
        return
    if len(subsets) > 1:
        problems.append(
            Diagnostic("lang.block_repeated", "`subset` is written twice", subsets[1].span)
        )
        return
    subset = subsets[0]
    spans[("subset",)] = subset.span
    out: dict[str, Any] = {"seeds": []}
    for index, seed in enumerate(subset.seeds):
        spans[("subset", "seeds", index)] = seed.span
        try:
            out["seeds"].append(_seed(seed))
        except LangError as error:
            problems.extend(error.diagnostics)
    if subset.budget:
        out["budget"] = {}
        for option in subset.budget:
            out["budget"][option.key.text] = plain(option.value)
            spans[("subset", "budget", option.key.text)] = option.value.span
    if subset.follows:
        out["edge_directions"] = {}
        for follow in subset.follows:
            edge = (
                f"{follow.parent_table.text}.{_joined(follow.parent_columns)} -> "
                f"{follow.child_table.text}.{_joined(follow.child_columns)}"
            )
            if edge in out["edge_directions"]:
                problems.append(
                    Diagnostic(
                        "lang.block_repeated", "this link already has a direction", follow.span
                    )
                )
            out["edge_directions"][edge] = follow.direction.text
            spans[("subset", "edge_directions", edge)] = follow.span
    if subset.allow_dangling:
        out["allow_dangling"] = True
    config["subset"] = out


def _joined(columns: tuple[nodes.Name, ...]) -> str:
    return ",".join(column.text for column in columns)


def _seed(seed: nodes.Seed) -> dict[str, Any]:
    out: dict[str, Any] = {"table": seed.table.text, "mode": seed.mode}
    if seed.key_columns:
        out["key_columns"] = [column.text for column in seed.key_columns]
    if seed.mode == "sample":
        assert seed.amount is not None
        amount = seed.amount.value
        if seed.unit == "%":
            # Decimal, so `33.3%` is 0.333 and not the nearest binary fraction of 33.3 / 100.
            out["fraction"] = float(Decimal(str(amount)) / 100)
        elif isinstance(amount, int):
            out["count"] = amount
        else:
            raise fail(
                "lang.sample_rows",
                "a row count is a whole number",
                seed.amount.span,
                "write `sample 500 rows`, or `sample 2.5%` for a share of the table",
            )
    elif seed.mode == "filter":
        out["predicates"] = []
        for condition in seed.conditions:
            if condition.operator not in PREDICATES:
                raise fail(
                    "lang.subset_condition",
                    f"`{condition.operator}` is not a comparison a subset can filter on",
                    condition.span,
                    "use ==, !=, <, <=, >, >=, `in [...]`, `is null` or `is not null`",
                )
            predicate: dict[str, Any] = {
                "column": condition.column.text,
                "op": PREDICATES[condition.operator],
            }
            if condition.value is not None:
                predicate["value"] = plain(condition.value)
            out["predicates"].append(predicate)
    else:
        assert seed.keys is not None
        rows = plain(seed.keys)
        # With one key column, `in [101, 102]` means the keys 101 and 102.
        single = len(seed.key_columns) == 1
        out["keys"] = [[row] if single and not isinstance(row, list) else row for row in rows]
    return out
