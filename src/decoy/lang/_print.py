"""Syntax tree to `.decoy` text, in the one canonical layout.

The layout is a fixed function of the tree, in the manner of gofmt and Black: two-space indent,
one statement per line, pipeline-level sections in a set order, and `:` or `=` aligned within a
run of single-line rules. The converter prints the tree it built from a config and the formatter
prints the tree it parsed, so both give the same text for the same program.

Names and words are written bare when the grammar reads them back as the same name, and quoted
otherwise (a word of the language, a space, a leading digit).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from decoy.lang import _ast as nodes
from decoy.lang._ast import plain
from decoy.lang._codes import UNPRINTABLE_NAME_CHARS, UNPRINTABLE_NAME_EMPTY, UNPRINTABLE_NUMBER
from decoy.lang._errors import Span, fail
from decoy.lang._grammar import KEYWORD_TERMINALS, NAME_PATTERN

_WORD = re.compile(NAME_PATTERN)
# Words that begin a value or an expression, so cannot stand bare before the `:` of an option.
OPTION_KEYS_QUOTED = frozenset({"true", "false", "not", "if"})
INDENT = "  "
ALIGN_LIMIT = 24


def _bare(text: str) -> bool:
    return _WORD.fullmatch(text) is not None and text.upper() not in KEYWORD_TERMINALS


def text_literal(text: str) -> str:
    """A double-quoted string the grammar reads back as `text`."""
    return json.dumps(text, ensure_ascii=False)


def name(text: str) -> str:
    """A table, column, namespace or `let` name: bare, or in single quotes."""
    return text if _bare(text) else _single_quoted(text)


def _single_quoted(text: str) -> str:
    if not text:
        raise fail(UNPRINTABLE_NAME_EMPTY)
    if "'" in text or "\n" in text:
        raise fail(UNPRINTABLE_NAME_CHARS)
    return f"'{text}'"


def number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise fail(UNPRINTABLE_NUMBER)
    digits = format(Decimal(repr(value)), "f")
    return digits if "." in digits else f"{digits}.0"


def value(item: Any) -> str:
    """A plain Python value as the language writes it."""
    if isinstance(item, bool):
        return "true" if item else "false"
    if isinstance(item, (int, float)):
        return number(item)
    if isinstance(item, str):
        return item if _bare(item) else text_literal(item)
    if isinstance(item, dict):
        return "{" + ", ".join(f"{_key(key)}: {value(inner)}" for key, inner in item.items()) + "}"
    return "[" + ", ".join(value(inner) for inner in item) + "]"


def _key(text: str) -> str:
    """A key in a map or in `settings { }` and `options { }`: bare, or in double quotes."""
    return text if _bare(text) else text_literal(text)


def option_key(text: str) -> str:
    """The name of a `key: value` option in a call. The grammar reads a word of the language as
    a plain name there, except the few that can begin a value; those, and anything that is not
    a word, are written in single quotes."""
    if _WORD.fullmatch(text) is not None and text not in OPTION_KEYS_QUOTED:
        return text
    return name(text) if _bare(text) else _single_quoted(text)


def _names(items: tuple[nodes.Name, ...]) -> str:
    return ", ".join(name(item.text) for item in items)


def _arguments(
    positional: tuple[nodes.Value, ...],
    options: tuple[nodes.Option, ...],
    refs: tuple[nodes.Ref, ...] = (),
) -> str:
    parts = [f"{name(ref.table.text)}.{name(ref.column.text)}" for ref in refs]
    parts += [value(plain(item)) for item in positional]
    parts += [f"{option_key(option.key.text)}: {value(plain(option.value))}" for option in options]
    return ", ".join(parts)


def _call(call: nodes.Call) -> str:
    if not call.has_parens:
        return name(call.name.text)
    return f"{name(call.name.text)}({_arguments(call.positional, call.options)})"


def _treatment(treatment: nodes.Treatment) -> str:
    parts = [_call(treatment.call)]
    if treatment.namespace is not None:
        parts.append(f"in {name(treatment.namespace.text)}")
    if treatment.deterministic:
        parts.append("deterministic")
    if treatment.vaulted:
        parts.append("vaulted")
    if treatment.when is not None:
        parts.append(f"when {treatment.when.text}")
    return " ".join(parts)


def _key_columns(columns: tuple[nodes.Name, ...]) -> str:
    return name(columns[0].text) if len(columns) == 1 else f"({_names(columns)})"


def _shaping(statement: nodes.Shaping) -> str | tuple[str, str, str]:
    if isinstance(statement, nodes.Where):
        return f"where {statement.expression.text}"
    if isinstance(statement, nodes.Define):
        return (name(statement.name.text), "=", statement.expression.text)
    if isinstance(statement, nodes.Limit):
        return f"limit {number(statement.count.value)}"  # type: ignore[arg-type]
    if isinstance(statement, nodes.Drop):
        return f"drop {_names(statement.columns)}"
    if isinstance(statement, nodes.Dedupe):
        return f"dedupe on {_names(statement.columns)}" if statement.columns else "dedupe"
    keys = [
        name(key.column.text) if key.ascending else f"{name(key.column.text)} desc"
        for key in statement.keys
    ]
    return "sort by " + ", ".join(keys)


def _aligned(rows: list[tuple[str, str, str] | str]) -> list[str]:
    """Lines for a block: a `(left, symbol, right)` row is padded so that the symbols of each
    unbroken run of such rows line up; a plain string is a line of its own and ends the run."""
    lines: list[str] = []
    run: list[tuple[str, str, str]] = []

    def flush() -> None:
        # A long left side (a list of columns) is left alone rather than pushing every symbol out.
        width = max((len(left) for left, _, _ in run if len(left) <= ALIGN_LIMIT), default=0)
        lines.extend(f"{left.ljust(width)} {symbol} {right}" for left, symbol, right in run)
        run.clear()

    for row in rows:
        if isinstance(row, str):
            flush()
            lines.append(row)
        else:
            run.append(row)
    flush()
    return lines


Row = tuple[str, str, str] | str


def _indented(line: str) -> str:
    return INDENT + line if line else ""


@dataclass(frozen=True)
class Notes:
    """The comments of a program, by where they belong. A key is the source line and column at
    which a statement starts; a node built by the converter has no position and so no comments."""

    before: dict[tuple[int, int], tuple[str, ...]] = field(default_factory=dict)
    after: dict[tuple[int, int], str] = field(default_factory=dict)
    closing: dict[tuple[int, int], tuple[str, ...]] = field(default_factory=dict)
    spaced: frozenset[tuple[int, int]] = frozenset()  # statements with a blank line above them
    head: tuple[str, ...] = ()
    tail: tuple[str, ...] = ()

    def around(self, span: Span, row: Row) -> list[Row]:
        """The row with the comments written above it, and the one written beside it."""
        key = (span.line, span.column)
        beside = self.after.get(key)
        if beside is not None and isinstance(row, str):
            row = f"{row}  {beside}"
        elif beside is not None:
            row = (row[0], row[1], f"{row[2]}  {beside}")
        gap: list[Row] = [""] if key in self.spaced else []
        return [*gap, *self.before.get(key, ()), row]

    def block(self, span: Span, head: str, rows: list[Row]) -> list[str]:
        """A braced block: its head, its aligned rows, the comments left before its `}`."""
        key = (span.line, span.column)
        opening = self.around(span, head)
        inner = _aligned([*rows, *self.closing.get(key, ())])
        return [*(str(line) for line in opening), *(_indented(line) for line in inner), "}"]


def _table_row(statement: nodes.Mask | nodes.Keep | nodes.Link | nodes.Shaping) -> Row:
    if isinstance(statement, nodes.Shaping):
        return _shaping(statement)
    mark = " ?" if getattr(statement, "unreviewed", False) else ""
    if isinstance(statement, nodes.Keep):
        return f"keep {_names(statement.columns)}{mark}"
    if isinstance(statement, nodes.Link):
        line = (
            f"{_names(statement.columns)} <- {name(statement.parent_table.text)}."
            f"{_key_columns(statement.parent_columns)}"
        )
        if statement.namespace is not None:
            line += f" in {name(statement.namespace.text)}"
        if statement.orphans is not None:
            line += f" orphans {name(statement.orphans.text)}"
        return line
    if statement.coherent:
        return f"{{{_names(statement.columns)}}} : {_treatment(statement.treatment)}{mark}"
    return (_names(statement.columns), ":", _treatment(statement.treatment) + mark)


def _table(table: nodes.Table, notes: Notes) -> list[str]:
    rows = [
        row
        for statement in table.statements
        for row in notes.around(statement.span, _table_row(statement))
    ]
    head = f"mask {name(table.name.text)} from {_call(table.source)} to {_call(table.target)} {{"
    return notes.block(table.span, head, rows)


def _generate_row(statement: nodes.GenColumn | nodes.GenLink | nodes.Unique) -> Row:
    if isinstance(statement, nodes.Unique):
        return f"unique ({_names(statement.columns)})"
    if isinstance(statement, nodes.GenLink):
        target = f"{name(statement.parent_table.text)}.{name(statement.parent_column.text)}"
        return (name(statement.name.text), "<-", target)
    if statement.expression is not None:
        # The parser keeps both readings of `name = f(x)`; the expression text is the source.
        return (name(statement.name.text), "=", statement.expression.text)
    assert statement.call is not None
    return (name(statement.name.text), "=", _call(statement.call))


def _generate(table: nodes.Generate, notes: Notes) -> list[str]:
    rows = [
        row
        for statement in table.statements
        for row in notes.around(statement.span, _generate_row(statement))
    ]
    head = (
        f"generate {name(table.name.text)} rows {number(table.rows.value)} "  # type: ignore[arg-type]
        f"to {_call(table.target)} {{"
    )
    return notes.block(table.span, head, rows)


def _block(block: nodes.Block) -> str:
    if block.kind == "namespace":
        assert block.name is not None
        refs = ", ".join(f"{name(r.table.text)}.{name(r.column.text)}" for r in block.refs)
        return f"namespace {name(block.name.text)} for {refs}"
    head = f"expect {name(block.name.text)}" if block.name is not None else block.kind
    arguments = _arguments(block.positional, block.options, block.refs)
    bare = block.kind.startswith("scan") or block.kind == "expect"
    return head if bare and not arguments else f"{head}({arguments})"


def _condition(condition: nodes.Condition) -> str:
    column = name(condition.column.text)
    if condition.value is None:
        return f"{column} {condition.operator}"
    return f"{column} {condition.operator} {value(plain(condition.value))}"


def _seed(seed: nodes.Seed) -> str:
    head = f"start {name(seed.table.text)}"
    if seed.mode == "sample":
        assert seed.amount is not None
        amount = number(seed.amount.value)  # type: ignore[arg-type]
        unit = "%" if seed.unit == "%" else " rows"
        return f"{head} sample {amount}{unit} by {_names(seed.key_columns)}"
    if seed.mode == "filter":
        return f"{head} where " + ", ".join(_condition(c) for c in seed.conditions)
    assert seed.keys is not None
    return f"{head} keys {_names(seed.key_columns)} in {value(plain(seed.keys))}"


def _follow(follow: nodes.Follow) -> str:
    return (
        f"follow {name(follow.parent_table.text)}.{_key_columns(follow.parent_columns)} -> "
        f"{name(follow.child_table.text)}.{_key_columns(follow.child_columns)} "
        f"{name(follow.direction.text)}"
    )


def _subset(subset: nodes.Subset, notes: Notes) -> list[str]:
    rows: list[Row] = []
    for seed in subset.seeds:
        rows += notes.around(seed.span, _seed(seed))
    for follow in subset.follows:
        rows += notes.around(follow.span, _follow(follow))
    if subset.budget:
        rows += notes.around(subset.budget[0].key.span, f"budget({_arguments((), subset.budget)})")
    if subset.allow_dangling:
        rows.append("allow dangling")
    return notes.block(subset.span, "subset {", rows)


def _pairs(
    word: str, options: tuple[nodes.Option, ...], span: Span | None, notes: Notes
) -> list[str]:
    rows: list[Row] = []
    for option in options:
        rows += notes.around(
            option.key.span, f"{_key(option.key.text)}: {value(plain(option.value))}"
        )
    if span is None:
        return [f"{word} {{", *(_indented(str(row)) for row in rows), "}"]
    return notes.block(span, f"{word} {{", rows)


_SETTINGS = {
    "seed": lambda item: f"seed {number(item)}",
    "secret": lambda item: f"secret ref({text_literal(item)})",
    "unconfigured": lambda item: f"unconfigured columns {name(item)}",
}


def print_program(program: nodes.Program, notes: Notes | None = None) -> str:
    """The program as text. Sections come in a set order, one blank line apart; `notes` are the
    comments to write with the statements they belong to."""
    notes = notes or Notes()

    def lines(items: Any, render: Any) -> list[str]:
        return [str(row) for item in items for row in notes.around(item.span, render(item))]

    sections: list[list[str]] = [
        lines(program.settings, lambda s: _SETTINGS[s.kind](s.value.value))
    ]
    if program.extra_settings:
        sections.append(_pairs("settings", program.extra_settings, program.settings_span, notes))
    sections.append(
        lines(program.lets, lambda let: f"let {name(let.name.text)} = {_treatment(let.treatment)}")
    )
    sections.extend(_subset(subset, notes) for subset in program.subsets)
    sections.append(lines(program.blocks, _block))
    for table in program.tables:
        printed = _generate if isinstance(table, nodes.Generate) else _table
        sections.append(printed(table, notes))  # type: ignore[arg-type]
    if program.options:
        sections.append(_pairs("options", program.options, program.options_span, notes))
    sections.append(list(notes.closing.get((program.span.line, program.span.column), ())))
    head = f"pipeline {name(program.name.text)} {{" if program.name is not None else "pipeline {"
    body = "\n\n".join(
        "\n".join(_indented(line) for line in section).strip("\n")
        for section in sections
        if section
    )
    top = "".join(f"{comment}\n" for comment in notes.head)
    bottom = "".join(f"{comment}\n" for comment in notes.tail)
    return f"{top}decoy 1\n\n{head}\n{body}\n}}\n{bottom}"
