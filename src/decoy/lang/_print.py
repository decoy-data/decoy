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
from decimal import Decimal
from typing import Any

from decoy.lang import _ast as nodes
from decoy.lang._ast import plain
from decoy.lang._errors import fail
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
    if "'" in text or "\n" in text or not text:
        raise fail("lang.unprintable_name", "a name with a quote or a line break cannot be written")
    return f"'{text}'"


def number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise fail("lang.unprintable_number", "a number that is not finite cannot be written")
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


def _table(table: nodes.Table) -> list[str]:
    rows: list[tuple[str, str, str] | str] = []
    for statement in table.statements:
        if isinstance(statement, nodes.Shaping):
            rows.append(_shaping(statement))
        elif isinstance(statement, nodes.Keep):
            rows.append(f"keep {_names(statement.columns)}")
        elif isinstance(statement, nodes.Link):
            line = (
                f"{_names(statement.columns)} <- {name(statement.parent_table.text)}."
                f"{_key_columns(statement.parent_columns)}"
            )
            if statement.namespace is not None:
                line += f" in {name(statement.namespace.text)}"
            if statement.orphans is not None:
                line += f" orphans {name(statement.orphans.text)}"
            rows.append(line)
        elif statement.coherent:
            rows.append(f"{{{_names(statement.columns)}}} : {_treatment(statement.treatment)}")
        else:
            rows.append((_names(statement.columns), ":", _treatment(statement.treatment)))
    head = f"mask {name(table.name.text)} from {_call(table.source)} to {_call(table.target)} {{"
    return [head, *(INDENT + line for line in _aligned(rows)), "}"]


def _generate(table: nodes.Generate) -> list[str]:
    rows: list[tuple[str, str, str] | str] = []
    for statement in table.statements:
        if isinstance(statement, nodes.Unique):
            rows.append(f"unique ({_names(statement.columns)})")
        elif isinstance(statement, nodes.GenLink):
            target = f"{name(statement.parent_table.text)}.{name(statement.parent_column.text)}"
            rows.append((name(statement.name.text), "<-", target))
        elif statement.expression is not None:
            # The parser keeps both readings of `name = f(x)`; the expression text is the source.
            rows.append((name(statement.name.text), "=", statement.expression.text))
        else:
            assert statement.call is not None
            rows.append((name(statement.name.text), "=", _call(statement.call)))
    head = (
        f"generate {name(table.name.text)} rows {number(table.rows.value)} "  # type: ignore[arg-type]
        f"to {_call(table.target)} {{"
    )
    return [head, *(INDENT + line for line in _aligned(rows)), "}"]


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


def _subset(subset: nodes.Subset) -> list[str]:
    lines = []
    for seed in subset.seeds:
        head = f"start {name(seed.table.text)}"
        if seed.mode == "sample":
            assert seed.amount is not None
            amount = number(seed.amount.value)  # type: ignore[arg-type]
            unit = "%" if seed.unit == "%" else " rows"
            lines.append(f"{head} sample {amount}{unit} by {_names(seed.key_columns)}")
        elif seed.mode == "filter":
            lines.append(f"{head} where " + ", ".join(_condition(c) for c in seed.conditions))
        else:
            assert seed.keys is not None
            lines.append(f"{head} keys {_names(seed.key_columns)} in {value(plain(seed.keys))}")
    for follow in subset.follows:
        lines.append(
            f"follow {name(follow.parent_table.text)}.{_key_columns(follow.parent_columns)} -> "
            f"{name(follow.child_table.text)}.{_key_columns(follow.child_columns)} "
            f"{name(follow.direction.text)}"
        )
    if subset.budget:
        lines.append(f"budget({_arguments((), subset.budget)})")
    if subset.allow_dangling:
        lines.append("allow dangling")
    return ["subset {", *(INDENT + line for line in lines), "}"]


def _pairs(word: str, options: tuple[nodes.Option, ...]) -> list[str]:
    lines = [f"{_key(option.key.text)}: {value(plain(option.value))}" for option in options]
    return [f"{word} {{", *(INDENT + line for line in lines), "}"]


_SETTINGS = {
    "seed": lambda item: f"seed {number(item)}",
    "secret": lambda item: f"secret ref({text_literal(item)})",
    "unconfigured": lambda item: f"unconfigured columns {name(item)}",
}


def print_program(program: nodes.Program) -> str:
    """The program as text. Sections come in a set order, one blank line apart."""
    sections: list[list[str]] = [
        [_SETTINGS[setting.kind](setting.value.value) for setting in program.settings]
    ]
    if program.extra_settings:
        sections.append(_pairs("settings", program.extra_settings))
    sections.append(
        [f"let {name(let.name.text)} = {_treatment(let.treatment)}" for let in program.lets]
    )
    sections.extend(_subset(subset) for subset in program.subsets)
    sections.append([_block(block) for block in program.blocks])
    for table in program.tables:
        sections.append(_generate(table) if isinstance(table, nodes.Generate) else _table(table))
    if program.options:
        sections.append(_pairs("options", program.options))
    head = f"pipeline {name(program.name.text)} {{" if program.name is not None else "pipeline {"
    body = "\n\n".join(
        "\n".join(INDENT + line for line in section) for section in sections if section
    )
    return f"decoy 1\n\n{head}\n{body}\n}}\n"
