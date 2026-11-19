"""Reading single tokens: positions, numbers and quoted text.

Text in double quotes takes the JSON escapes (`\\"`, `\\\\`, `\\n`, `\\t`, `\\uXXXX` and the rest of
that set) and nothing else. Text in single quotes is taken as written, with no escapes, so a
Windows path or a regular expression needs no doubling; it cannot contain a single quote.

That is for values. Inside an expression (`when`, `where`, `name = ...`) quoted text is not
read here at all: the expression goes to the engine exactly as written, and the engine's own
rules for text apply.
"""

from __future__ import annotations

import math
import re
from typing import Any

from lark import Token, Tree

from decoy.lang._codes import NUMBER_TOO_LARGE, STRING_ESCAPE, STRING_ESCAPE_HALF
from decoy.lang._errors import Span, fail

_ESCAPE = re.compile(r"\\(u[0-9a-fA-F]{4}|.)", re.DOTALL)
_SIMPLE = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


def span_of(node: Tree[Any] | Token) -> Span:
    if isinstance(node, Token):
        return Span(node.line or 1, node.column or 1, node.end_line or 1, node.end_column or 1)
    meta = node.meta
    return Span(meta.line, meta.column, meta.end_line, meta.end_column)


def number_of(token: Token) -> int | float:
    digits = str(token).replace("_", "")
    if not any(mark in digits for mark in ".eE"):
        return int(digits)
    value = float(digits)
    if not math.isfinite(value):
        raise fail(NUMBER_TOO_LARGE, span_of(token))
    return value


def unquote(token: Token) -> str:
    """The text a quoted token holds."""
    text = str(token)
    if text[0] == "'":
        return text[1:-1]

    def replace(match: re.Match[str]) -> str:
        escape = match.group(1)
        if len(escape) == 5:
            return chr(int(escape[1:], 16))
        if escape in _SIMPLE:
            return _SIMPLE[escape]
        raise fail(
            STRING_ESCAPE,
            span_of(token),
            "write a backslash as two, or use single quotes, where a backslash is just a backslash",
        )

    decoded = _ESCAPE.sub(replace, text[1:-1])
    try:
        # Two `\\u` escapes for one character (a surrogate pair) become that character.
        return decoded.encode("utf-16", "surrogatepass").decode("utf-16")
    except UnicodeDecodeError:
        failure = fail(STRING_ESCAPE_HALF, span_of(token))
    raise failure
