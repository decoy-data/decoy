"""Foreign keys: `child <- parent_table.key` to the engine's `relationships` block.

The child columns are declared `from_parent` and the relationship does the work: the engine masks
the parent first and gives each child key the value its parent key received, so the join survives
(the dbt `ref` idea, a link stated once where it is used). Links to the same parent key with the
same namespace and orphan policy share one relationship entry, as the engine's shape has one
parent and a list of children.

The engine wants a namespace on every relationship that touches a masked table. A link takes it
from its own `in <namespace>`, else from the first parent key column, following a chain of links
upward when that column is itself a foreign key.
"""

from __future__ import annotations

import difflib
from typing import Any

from decoy.lang import _ast as nodes
from decoy.lang._errors import Diagnostic, SourceMap

CHILD_STRATEGY = "from_parent"
# A link whose parent link already failed adds no second report.
_ALREADY_REPORTED = ""
ORPHAN_HINT = (
    "add `orphans preserve` (keep the unmatched key), `orphans remap` (mask it anyway), "
    "`orphans warn` (keep it and report the count) or `orphans fail` (stop the run)"
)


def relationships(
    links: list[tuple[str, nodes.Link]],
    tables: list[dict[str, Any]],
    spans: SourceMap,
    problems: list[Diagnostic],
) -> list[dict[str, Any]]:
    columns = {t["name"]: {c["name"]: c for c in t["columns"]} for t in tables}
    parent_of = {
        (child, column.text): (link, position)
        for child, link in links
        for position, column in enumerate(link.columns)
    }

    def namespace_of(table: str, column: str, visited: frozenset[tuple[str, str]]) -> str | None:
        declared = columns.get(table, {}).get(column, {}).get("namespace")
        if declared is not None or (table, column) not in parent_of or (table, column) in visited:
            return declared
        link, position = parent_of[(table, column)]
        if id(link) in failed:
            return _ALREADY_REPORTED
        if link.namespace is not None:
            return link.namespace.text
        if position >= len(link.parent_columns):
            return None
        upward = link.parent_columns[0].text
        return namespace_of(link.parent_table.text, upward, visited | {(table, column)})

    entries: dict[tuple[Any, ...], dict[str, Any]] = {}
    failed: set[int] = set()
    for child, link in links:
        parent = link.parent_table.text
        before = len(problems)
        if parent not in columns:
            close = difflib.get_close_matches(parent, sorted(columns), n=1)
            hint = f"did you mean `{close[0]}`?" if close else None
            problems.append(
                Diagnostic(
                    "lang.link_unknown_table",
                    f"`{parent}` is not a table of this pipeline",
                    link.parent_table.span,
                    hint,
                )
            )
        elif len(link.columns) != len(link.parent_columns):
            problems.append(
                Diagnostic(
                    "lang.link_arity",
                    f"{len(link.columns)} column(s) cannot follow a key of "
                    f"{len(link.parent_columns)} column(s)",
                    link.span,
                )
            )
        else:
            problems.extend(
                Diagnostic(
                    "lang.link_unknown_column",
                    f"table `{parent}` has no rule for column `{key.text}`",
                    key.span,
                )
                for key in link.parent_columns
                if key.text not in columns[parent]
            )
        if link.orphans is None:
            problems.append(
                Diagnostic(
                    "lang.orphans_missing",
                    "this link does not say what happens to rows with no matching parent",
                    link.span,
                    ORPHAN_HINT,
                )
            )
        if len(problems) > before:
            failed.add(id(link))
            continue
        key_names = [key.text for key in link.parent_columns]
        namespace = (
            link.namespace.text
            if link.namespace is not None
            else namespace_of(parent, key_names[0], frozenset())
        )
        if namespace == _ALREADY_REPORTED:
            failed.add(id(link))
            continue
        if namespace is None:
            failed.add(id(link))
            problems.append(
                Diagnostic(
                    "lang.link_needs_namespace",
                    f"the parent key `{parent}.{key_names[0]}` has no namespace",
                    link.parent_columns[0].span,
                    "add `in <namespace>` to that column's rule, or to this link",
                )
            )
            continue
        assert link.orphans is not None
        identity = (parent, tuple(key_names), namespace, link.orphans.text)
        if identity not in entries:
            index = len(entries)
            entries[identity] = {
                "parent": {"table": parent, "columns": key_names},
                "children": [],
                "orphan_policy": link.orphans.text,
                "namespace": namespace,
            }
            spans[("relationships", index)] = link.span
            spans[("relationships", index, "orphan_policy")] = link.orphans.span
            if link.namespace is not None:
                spans[("relationships", index, "namespace")] = link.namespace.span
        entry = entries[identity]
        index = list(entries).index(identity)
        spans[("relationships", index, "children", len(entry["children"]))] = link.span
        entry["children"].append({"table": child, "columns": [c.text for c in link.columns]})
    return list(entries.values())
