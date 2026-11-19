"""Expression trees and generator arguments.

The grammar reads `name = ...` and `when ...` with one loose expression rule: it finds where an
expression starts and ends, and gives it no meaning. This module turns such a tree into what the
config holds: one line of canonical text for the engine's own grammars to judge, or, for the
arguments of a generator call, plain values.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedInput

from decoy.lang import _ast as nodes
from decoy.lang._errors import fail
from decoy.lang._grammar import GRAMMAR
from decoy.lang._tokens import number_of, span_of, unquote


def expression_text(node: Tree[Any] | Token) -> str:
    """One line of canonical text for an expression: the engine's `when` grammar admits spaces
    and tabs only, and equal programs must compile to equal configs whatever their layout."""
    if isinstance(node, Token):
        return str(node).replace("_", "") if node.type == "NUMBER" else str(node)
    parts = [child for child in node.children if child is not None]
    if node.data == "expression":
        return " ".join(expression_text(part) for part in parts)
    if node.data == "operator":
        return " ".join(str(part) for part in parts)
    if node.data == "operand":
        return "".join(expression_text(part) for part in parts)
    if node.data == "prefix":
        return "not " if parts[0].type == "NOT" else "-"
    if node.data == "e_map":
        raise fail("lang.syntax", "an expression cannot hold a `{...}` map", span_of(node))
    if node.data == "e_option":
        raise fail(
            "lang.generator_in_masked_table",
            "a masked table can only define a column from an expression",
            span_of(node),
            "generators such as `sequence(start: 1)` belong in a `generate` table",
        )
    inner = ", ".join(expression_text(part) for part in parts if not isinstance(part, Token))
    if node.data == "e_call":
        return f"{parts[0]}({inner})"
    return f"({inner})" if node.data == "e_group" else f"[{inner}]"


_LEADING_WORD = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(\(|\Z)")


def leading_call(text: str) -> str | None:
    """The word an expression starts with when it is `word(...)` or the word alone, else None.
    That is where a generator name would stand if a generator were written by mistake."""
    found = _LEADING_WORD.match(text)
    return found[1] if found else None


def _single(tree: Tree[Any], kind: str) -> Tree[Any] | Token | None:
    """The one child of an `expression` or `operand` that is nothing but that child."""
    parts = [child for child in tree.children if child is not None]
    return parts[0] if tree.data == kind and len(parts) == 1 else None


def plain_value(tree: Tree[Any]) -> nodes.Value:
    """A generator argument as a value: a number, text, a bare word, a list or a map.

    Generator calls are read by the expression grammar, since `name = ...` may hold either, so
    their arguments arrive as expression trees and anything computed is refused here."""
    span = span_of(tree)
    operand = _single(tree, "expression")
    parts = [c for c in operand.children if c is not None] if isinstance(operand, Tree) else []
    negative = (
        len(parts) == 2 and isinstance(parts[0], Tree) and parts[0].children[0].type == "MINUS"
    )
    primary = parts[-1] if parts and (len(parts) == 1 or negative) else None
    if isinstance(primary, Token):
        if primary.type == "NUMBER":
            return nodes.Value(-number_of(primary) if negative else number_of(primary), span)
        if not negative and primary.type == "NAME":
            word = str(primary)
            return nodes.Value(word == "true" if word in ("true", "false") else word, span)
        if not negative:
            return nodes.Value(unquote(primary), span)
    elif isinstance(primary, Tree) and not negative and primary.data == "e_list":
        return nodes.Value(tuple(plain_value(c) for c in primary.children if c is not None), span)
    elif isinstance(primary, Tree) and not negative and primary.data == "e_map":
        pairs: dict[str, nodes.Value] = {}
        for pair in (c for c in primary.children if c is not None):
            token, value = pair.children
            key = str(token) if token.type == "NAME" else unquote(token)
            if key in pairs:
                raise fail(
                    "lang.option_repeated", "a key is given twice in this map", span_of(token)
                )
            pairs[key] = plain_value(value)
        return nodes.Value(pairs, span)
    raise fail(
        "lang.generator_argument",
        "a generator takes plain values: numbers, text, words, lists and maps",
        span,
        "for a computed column write the expression on its own: `total = price * quantity`",
    )


def generator_call(expression: Tree[Any]) -> nodes.Call | None:
    """The call `name(...)` when the whole right-hand side is one call, else None."""
    operand = _single(expression, "expression")
    call = _single(operand, "operand") if isinstance(operand, Tree) else None
    if not isinstance(call, Tree) or call.data != "e_call":
        return None
    head = call.children[0]
    positional: list[nodes.Value] = []
    options: list[nodes.Option] = []
    for argument in (c for c in call.children[1:] if isinstance(c, Tree)):
        if argument.data == "e_option":
            token, value = argument.children
            key = nodes.Name(str(token) if token.type == "NAME" else unquote(token), span_of(token))
            if any(o.key.text == key.text for o in options):
                raise fail("lang.option_repeated", f"option `{key.text}` is given twice", key.span)
            options.append(nodes.Option(key, plain_value(value)))
        elif options:
            raise fail(
                "lang.positional_after_option",
                "a plain value cannot follow a `key: value` option",
                span_of(argument),
                "put plain values first",
            )
        else:
            positional.append(plain_value(argument))
    name = nodes.Name(str(head), span_of(head))
    return nodes.Call(name, tuple(positional), tuple(options), True, span_of(call))


@lru_cache(maxsize=1)
def _expression_parser() -> Lark:
    return Lark(GRAMMAR, parser="lalr", start="expression", maybe_placeholders=True)


def canonical_expression(text: str) -> str:
    """An expression from a config as the compiler would write it: one space between tokens.

    Raises `LangError` when the text is not something the language can hold as an expression."""
    try:
        tree = _expression_parser().parse(text)
    except UnexpectedInput:
        failure = fail("lang.expression", "this expression cannot be written in the language")
    else:
        return expression_text(tree)
    raise failure
