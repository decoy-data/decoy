"""Checks and safety statements to their config blocks.

    scan before(regex, ner)                      pre_scan
    scan after(regex, integrity: true)           post_scan
    expect leak_check(orders.email, min_rows: 50)   one `validators` entry
    quarantine("out/bad.jsonl", triggers: [...]) quarantine, enabled
    baseline("scans/base.json", on_drift: fail)  scan_baseline
    delivery(best_effort)                        delivery
    namespace ids for members.id, orders.id      one `namespaces` entry

Each statement is a word and call-style arguments, the shape strategies and generators already
have. One `Shape` per block says where its plain values go; every `key: value` option is passed to
the engine under the same key, and the engine's validation decides whether it is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from decoy.lang import _ast as nodes
from decoy.lang._ast import plain
from decoy.lang._codes import (
    BLOCK_ARGUMENTS,
    BLOCK_REPEATED,
    BLOCK_REPEATED_NAMESPACE,
    EXPECT_ARGUMENT,
    OPTION_SET_BY_STATEMENT,
    REFERENCE_NOT_ALLOWED,
)
from decoy.lang._errors import Diagnostic, SourceMap, diagnostic


@dataclass(frozen=True)
class Shape:
    key: str  # the config block
    written: str  # how the block is written, for the refusal in `options { }`
    variadic: str | None = None  # the list option all plain values fill
    positional: tuple[str, ...] = ()  # or the options they fill, in order
    fixed: dict[str, Any] = field(default_factory=dict)


SHAPES = {
    "scan before": Shape("pre_scan", "`scan before(...)`", variadic="detectors"),
    "scan after": Shape("post_scan", "`scan after(...)`", variadic="detectors"),
    # Writing the statement turns quarantine on; a pipeline without it has none.
    "quarantine": Shape(
        "quarantine",
        '`quarantine("path", ...)`',
        positional=("output_path",),
        fixed={"enabled": True},
    ),
    # The engine accepts one baseline format, so the statement does not ask for it.
    "baseline": Shape(
        "scan_baseline",
        '`baseline("path", ...)`',
        positional=("path",),
        fixed={"schema": "scan-set/v1"},
    ),
    "delivery": Shape(
        "delivery", "`delivery(strict)` or `delivery(best_effort)`", positional=("mode",)
    ),
}
# Config blocks this module writes, with the syntax that writes each.
SAFETY_SYNTAX = {
    **{shape.key: shape.written for shape in SHAPES.values()},
    "validators": "`expect <check>(...)`",
    "namespaces": "`namespace <name> for table.column, ...`",
}


def lower_blocks(
    blocks: tuple[nodes.Block, ...],
    config: dict[str, Any],
    spans: SourceMap,
    problems: list[Diagnostic],
) -> None:
    for block in blocks:
        if block.kind == "expect":
            _expect(block, config, spans, problems)
        elif block.kind == "namespace":
            _namespace(block, config, spans, problems)
        else:
            _shaped(block, SHAPES[block.kind], config, spans, problems)


def _options(
    block: nodes.Block, out: dict[str, Any], path: tuple[Any, ...], spans: SourceMap
) -> Diagnostic | None:
    for option in block.options:
        key = option.key.text
        if key in out:
            return diagnostic(OPTION_SET_BY_STATEMENT, option.key.span, key=key)
        out[key] = plain(option.value)
        spans[(*path, key)] = option.value.span
    return None


def _shaped(
    block: nodes.Block,
    shape: Shape,
    config: dict[str, Any],
    spans: SourceMap,
    problems: list[Diagnostic],
) -> None:
    if shape.key in config:
        problems.append(diagnostic(BLOCK_REPEATED, block.span, kind=block.kind))
        return
    if block.refs:
        problems.append(diagnostic(REFERENCE_NOT_ALLOWED, block.refs[0].span, kind=block.kind))
        return
    out: dict[str, Any] = dict(shape.fixed)
    if shape.variadic is not None:
        if block.positional:
            out[shape.variadic] = [plain(value) for value in block.positional]
            spans[(shape.key, shape.variadic)] = block.positional[0].span
    elif len(block.positional) > len(shape.positional):
        takes = ", ".join(shape.positional)
        problems.append(
            diagnostic(
                BLOCK_ARGUMENTS,
                block.positional[len(shape.positional)].span,
                "write the other values as `key: value` options",
                kind=block.kind,
                count=len(shape.positional),
                takes=takes,
            )
        )
        return
    else:
        for key, value in zip(shape.positional, block.positional, strict=False):
            out[key] = plain(value)
            spans[(shape.key, key)] = value.span
    problem = _options(block, out, (shape.key,), spans)
    if problem is not None:
        problems.append(problem)
        return
    spans[(shape.key,)] = block.span
    config[shape.key] = out


def _expect(
    block: nodes.Block, config: dict[str, Any], spans: SourceMap, problems: list[Diagnostic]
) -> None:
    assert block.name is not None
    if block.positional:
        problems.append(
            diagnostic(
                EXPECT_ARGUMENT,
                block.positional[0].span,
                "write a column as `table.column` and a setting as `key: value`",
            )
        )
        return
    entries = config.setdefault("validators", [])
    path = ("validators", len(entries))
    entry: dict[str, Any] = {"name": block.name.text}
    columns: dict[str, list[str]] = {}
    for ref in block.refs:
        columns.setdefault(ref.table.text, []).append(ref.column.text)
    if columns:
        entry["columns"] = columns
    params: dict[str, Any] = {}
    problem = _options(block, params, (*path, "params"), spans)
    if problem is not None:
        problems.append(problem)
        return
    if params:
        entry["params"] = params
    spans[path] = block.span
    spans[(*path, "name")] = block.name.span
    entries.append(entry)


def _namespace(
    block: nodes.Block, config: dict[str, Any], spans: SourceMap, problems: list[Diagnostic]
) -> None:
    assert block.name is not None
    declared = config.setdefault("namespaces", {})
    if block.name.text in declared:
        problems.append(diagnostic(BLOCK_REPEATED_NAMESPACE, block.name.span, name=block.name.text))
        return
    spans[("namespaces", block.name.text)] = block.span
    declared[block.name.text] = {
        "declared_by": [f"{ref.table.text}.{ref.column.text}" for ref in block.refs]
    }
