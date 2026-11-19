"""The formatter: a `.decoy` file rewritten in the canonical layout, comments kept.

`format_text` parses the text, decides which statement each comment belongs to, prints the tree
with those comments, and checks the result before returning it: the formatted text must parse to
the same syntax tree and hold every comment. It follows gofmt in the two things users notice: one
layout with no options, and a single blank line between statements kept where the author left one.

A comment belongs, in this order, to the statement it is written inside or beside; to the block
whose closing brace it follows; to the next statement in the same block; else it stays at the end
of that block. Sections are printed in a set order, so a comment travels with its statement.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from dataclasses import dataclass
from typing import Any

from decoy.lang import _ast as nodes
from decoy.lang._errors import Span, fail
from decoy.lang._parse import parse_with_comments
from decoy.lang._print import Notes, print_program

Position = tuple[int, int]


@dataclass(frozen=True)
class _Anchor:
    """A statement, or a block's opening line, that a comment can belong to."""

    start: Position
    end: Position
    block: Position  # the start of the block that holds it


def _key(span: Span) -> Position:
    return (span.line, span.column)


def _end(span: Span) -> Position:
    return (span.end_line, span.end_column)


def _anchors(program: nodes.Program) -> tuple[list[_Anchor], dict[Position, Position]]:
    """Every anchor, and each block's end by its start."""
    top = _key(program.span)
    anchors: list[_Anchor] = []
    blocks = {top: _end(program.span)}

    def add(span: Span, block: Position, end: Span | None = None) -> None:
        anchors.append(_Anchor(_key(span), _end(end or span), block))

    def open_block(span: Span) -> Position:
        add(span, top)
        blocks[_key(span)] = _end(span)
        return _key(span)

    for item in (*program.settings, *program.lets, *program.blocks):
        add(item.span, top)
    for options, span in (
        (program.extra_settings, program.settings_span),
        (program.options, program.options_span),
    ):
        inside = open_block(span) if span is not None else top
        for option in options:
            add(option.key.span, inside, option.value.span)
    for subset in program.subsets:
        inside = open_block(subset.span)
        for inner in (*subset.seeds, *subset.follows):
            add(inner.span, inside)
        if subset.budget:
            add(subset.budget[0].key.span, inside, subset.budget[-1].value.span)
    for table in program.tables:
        inside = open_block(table.span)
        for statement in table.statements:
            add(statement.span, inside)
    return sorted(anchors, key=lambda anchor: anchor.start), blocks


def _notes(
    program: nodes.Program, comments: list[tuple[int, int, str]], source: list[str]
) -> Notes:
    anchors, blocks = _anchors(program)
    top = _key(program.span)
    before: dict[Position, list[str]] = {}
    after: dict[Position, str] = {}
    closing: dict[Position, list[str]] = {}
    head: list[str] = []
    tail: list[str] = []
    first_line: dict[Position, int] = {anchor.start: anchor.start[0] for anchor in anchors}

    def attach(start: Position, text: str, line: int) -> None:
        """Beside the statement if nothing is there yet, else above it."""
        if start not in after:
            after[start] = text
        else:
            before.setdefault(start, []).append(text)
            first_line[start] = min(first_line[start], line)

    for line, column, text in comments:
        at = (line, column)
        if at < top:
            head.append(text)
            continue
        if at > blocks[top]:
            tail.append(text)
            continue
        # The innermost block the comment sits in: the last one to open before it and still open.
        block = max(start for start, end in blocks.items() if start < at < end)
        inside = [anchor for anchor in anchors if anchor.block == block]
        within = [a for a in inside if a.start < at < a.end and a.start not in blocks]
        beside = [a for a in inside if a.end[0] == line and a.end <= at]
        opening = block[0] == line and block != top and not any(a.start < at for a in inside)
        later = [anchor for anchor in inside if anchor.start > at]
        if within:
            attach(within[-1].start, text, line)
        elif beside:
            attach(beside[-1].start, text, line)
        elif opening:
            attach(block, text, line)
        elif later:
            before.setdefault(later[0].start, []).append(text)
            first_line[later[0].start] = min(first_line[later[0].start], line)
        else:
            closing.setdefault(block, []).append(text)
    # A statement keeps one blank line above it when the source had one above it or its comments.
    spaced = {
        start
        for start, line in first_line.items()
        if line >= 2 and not source[line - 2].strip() and _not_first(start, anchors)
    }
    return Notes(
        {key: tuple(lines) for key, lines in before.items()},
        after,
        {key: tuple(lines) for key, lines in closing.items()},
        frozenset(spaced),
        tuple(head),
        tuple(tail),
    )


def _not_first(start: Position, anchors: list[_Anchor]) -> bool:
    """Whether the anchor has an earlier statement in its block; the first needs no gap."""
    block = next(anchor.block for anchor in anchors if anchor.start == start)
    return any(anchor.block == block and anchor.start < start for anchor in anchors)


def _shape(node: Any) -> Any:
    """A syntax tree with its positions removed and every scalar paired with its type, so two
    parses of the same program compare equal and nothing else does."""
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        return {
            f.name: _shape(getattr(node, f.name))
            for f in dataclasses.fields(node)
            if not isinstance(getattr(node, f.name), Span) and not f.name.endswith("_span")
        }
    if isinstance(node, dict):
        return {key: _shape(item) for key, item in node.items()}
    if isinstance(node, (list, tuple)):
        return [_shape(item) for item in node]
    return (type(node).__name__, repr(node))


def format_text(text: str) -> str:
    """`text` in the canonical layout. Raises `LangError` when the text does not parse, or if
    the formatted result would not be the same program with the same comments."""
    try:
        program, comments = parse_with_comments(text)
        # Lark counts lines by "\\n" alone, so the source is split the same way.
        formatted = print_program(program, _notes(program, comments, text.split("\n")))
        again, kept = parse_with_comments(formatted)
        same_program = _shape(again) == _shape(program)
    except RecursionError:
        failure = fail("lang.nesting", "the program is nested too deeply")
    else:
        same_comments = Counter(c for _, _, c in kept) == Counter(c for _, _, c in comments)
        if same_program and same_comments:
            return formatted
        failure = fail(
            "lang.format", "formatting would change this program; the file is left as it is"
        )
    raise failure
