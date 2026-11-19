"""Source text to syntax tree.

Parsing uses Lark's LALR parser with its contextual lexer, the same library the engine uses for
its expression grammar. The Lark tree is rebuilt into the frozen nodes of `_ast`, each carrying
its source span, so later stages never see Lark types.
"""

from __future__ import annotations

import ast as python_ast
from functools import lru_cache
from typing import Any

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedInput, UnexpectedToken

from decoy.lang import _ast as nodes
from decoy.lang._errors import LangError, Span, fail
from decoy.lang._grammar import DISPLAY, GRAMMAR, KEYWORD_TERMINALS

SUPPORTED_VERSIONS = (1,)


@lru_cache(maxsize=1)
def _parser() -> Lark:
    return Lark(GRAMMAR, parser="lalr", propagate_positions=True, maybe_placeholders=True)


def parse(text: str) -> nodes.Program:
    try:
        tree = _parser().parse(text)
    except UnexpectedInput as error:
        failure = _syntax_error(error, text)
    else:
        return _program(tree)
    raise failure


def _syntax_error(error: UnexpectedInput, text: str) -> Exception:
    if isinstance(error, UnexpectedEOF):
        last = text.count("\n") + 1
        span = Span(last, 1, last, 1)
        found = "end of file"
    else:
        width = len(error.token) if isinstance(error, UnexpectedToken) else 1
        span = Span(error.line, error.column, error.line, error.column + max(1, width))
        if isinstance(error, UnexpectedToken):
            found = _found(error.token)
        else:
            found = f"`{text[error.pos_in_stream]}`"
    expected: set[str] = set()
    if isinstance(error, UnexpectedToken):
        expected = set(error.accepts or error.expected)
    elif isinstance(error, UnexpectedCharacters):
        expected = set(error.allowed or ())
    shown = sorted({DISPLAY.get(name, name) for name in expected})
    message = f"unexpected {found}"
    hint = f"expected {_one_of(shown)}" if shown else None
    # A language word where a column name was meant: either the word itself is refused where a
    # name fits, or it was read as a statement and the name's punctuation is refused after it.
    keyword = None
    if isinstance(error, UnexpectedToken):
        before = (error.token_history or [None])[-1]
        if error.token.type in KEYWORD_TERMINALS and "NAME" in expected:
            keyword = error.token
        elif error.token.type in ("COLON", "COMMA", "EQUAL") and before is not None:
            keyword = before if before.type in KEYWORD_TERMINALS else None
    if keyword is not None:
        word = str(keyword)
        quoted = f"`{word}` is a word of the language; for a column of that name write '{word}'"
        hint = f"{hint}. {quoted}" if hint else quoted
    return fail("lang.syntax", message, span, hint)


def _found(token: Token) -> str:
    """How an unexpected token is named. A number or quoted text is named by kind, not shown:
    it may be a seed or a path, and an error never quotes a config value."""
    if token.type == "$END":
        return "end of file"
    if token.type in ("NUMBER", "DQ_STRING", "SQ_STRING"):
        return DISPLAY[token.type]
    return f"`{token}`"


def _one_of(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return "one of: " + ", ".join(items)


def _span(node: Tree[Any] | Token) -> Span:
    if isinstance(node, Token):
        return Span(node.line or 1, node.column or 1, node.end_line or 1, node.end_column or 1)
    meta = node.meta
    return Span(meta.line, meta.column, meta.end_line, meta.end_column)


def _number(token: Token) -> int | float:
    digits = str(token).replace("_", "")
    return float(digits) if "." in digits else int(digits)


def _name(tree: Tree[Any]) -> nodes.Name:
    token = tree.children[0]
    if token.type == "NAME":
        return nodes.Name(str(token), _span(token))
    text = python_ast.literal_eval(str(token))
    if not text:
        raise fail("lang.name_empty", "a name cannot be empty", _span(token))
    return nodes.Name(text, _span(token))


def _value(node: Tree[Any]) -> nodes.Value:
    span = _span(node)
    kind = node.data
    if kind == "string":
        return nodes.Value(python_ast.literal_eval(str(node.children[0])), span, quoted=True)
    if kind == "number":
        return nodes.Value(_number(node.children[0]), span)
    if kind in ("true", "false"):
        return nodes.Value(kind == "true", span)
    if kind == "word":
        return nodes.Value(str(node.children[0]), span)
    if kind == "map":
        pairs: dict[str, nodes.Value] = {}
        for pair in node.children:
            if pair is None:
                continue
            token, value = pair.children
            key = str(token) if token.type == "NAME" else python_ast.literal_eval(str(token))
            if key in pairs:
                raise fail("lang.option_repeated", f"key `{key}` is given twice", _span(token))
            pairs[key] = _value(value)
        return nodes.Value(pairs, span)
    return nodes.Value(tuple(_value(child) for child in node.children if child is not None), span)


def _expression_text(node: Tree[Any] | Token) -> str:
    """One line of canonical text for an expression: the engine's `when` grammar admits spaces
    and tabs only, and equal programs must compile to equal configs whatever their layout."""
    if isinstance(node, Token):
        return str(node).replace("_", "") if node.type == "NUMBER" else str(node)
    parts = [child for child in node.children if child is not None]
    if node.data == "expression":
        return " ".join(_expression_text(part) for part in parts)
    if node.data == "operator":
        return " ".join(str(part) for part in parts)
    if node.data == "operand":
        return "".join(_expression_text(part) for part in parts)
    if node.data == "prefix":
        return "not " if parts[0].type == "NOT" else "-"
    if node.data == "e_map":
        raise fail("lang.syntax", "an expression cannot hold a `{...}` map", _span(node))
    if node.data == "e_option":
        raise fail(
            "lang.generator_in_masked_table",
            "a masked table can only define a column from an expression",
            _span(node),
            "generators such as `sequence(start: 1)` belong in a `generate` table",
        )
    inner = ", ".join(_expression_text(part) for part in parts if not isinstance(part, Token))
    if node.data == "e_call":
        return f"{parts[0]}({inner})"
    return f"({inner})" if node.data == "e_group" else f"[{inner}]"


def _call(tree: Tree[Any]) -> nodes.Call:
    name_tree, arguments = tree.children
    positional: list[nodes.Value] = []
    options: list[nodes.Option] = []
    for argument in arguments.children if arguments is not None else ():
        if argument is None:
            continue
        if argument.data == "option":
            if any(o.key.text == _name(argument.children[0]).text for o in options):
                key = _name(argument.children[0])
                raise fail("lang.option_repeated", f"option `{key.text}` is given twice", key.span)
            options.append(nodes.Option(_name(argument.children[0]), _value(argument.children[1])))
        elif options:
            raise fail(
                "lang.positional_after_option",
                "a plain value cannot follow a `key: value` option",
                _span(argument),
                "put plain values first",
            )
        else:
            positional.append(_value(argument))
    return nodes.Call(
        _name(name_tree), tuple(positional), tuple(options), arguments is not None, _span(tree)
    )


def _treatment(tree: Tree[Any]) -> nodes.Treatment:
    call, namespace, deterministic, vaulted, condition = tree.children
    when = None
    if condition is not None:
        expression = condition.children[1]
        when = nodes.Expression(_expression_text(expression), _span(expression))
    return nodes.Treatment(
        _call(call),
        _name(namespace.children[1]) if namespace is not None else None,
        deterministic is not None,
        vaulted is not None,
        when,
        _span(tree),
    )


def _names(tree: Tree[Any]) -> tuple[nodes.Name, ...]:
    return tuple(_name(child) for child in tree.children)


def _expression(tree: Tree[Any]) -> tuple[str, Span]:
    return _expression_text(tree), _span(tree)


def _where(tree: Tree[Any]) -> nodes.Transform:
    text, span = _expression(tree.children[1])
    return nodes.Transform("filter", (("expression", text, span),), _span(tree))


def _define(tree: Tree[Any]) -> nodes.Transform:
    name = _name(tree.children[0])
    text, span = _expression(tree.children[1])
    fields = (("column", name.text, name.span), ("expression", text, span))
    return nodes.Transform("derive", fields, _span(tree))


def _sort(tree: Tree[Any]) -> nodes.Transform:
    keys = tree.children[2:]
    by = [_name(key.children[0]).text for key in keys]
    ascending = [key.children[1] is None or key.children[1].type == "ASC" for key in keys]
    fields: list[tuple[str, Any, Span]] = [("by", by, _span(tree))]
    if not all(ascending):
        fields.append(("ascending", ascending, _span(tree)))
    return nodes.Transform("sort", tuple(fields), _span(tree))


def _limit(tree: Tree[Any]) -> nodes.Transform:
    token = tree.children[1]
    return nodes.Transform("limit", (("n", _number(token), _span(token)),), _span(tree))


def _dedupe(tree: Tree[Any]) -> nodes.Transform:
    names = tree.children[2]
    if names is None:
        return nodes.Transform("dedupe", (), _span(tree))
    columns = [name.text for name in _names(names)]
    return nodes.Transform("dedupe", (("columns", columns, _span(names)),), _span(tree))


def _drop(tree: Tree[Any]) -> nodes.Transform:
    names = tree.children[1]
    columns = [name.text for name in _names(names)]
    return nodes.Transform("drop_column", (("columns", columns, _span(names)),), _span(tree))


_TRANSFORMS = {
    "where": _where,
    "define": _define,
    "sort": _sort,
    "limit": _limit,
    "dedupe": _dedupe,
    "drop": _drop,
}


def _link(tree: Tree[Any]) -> nodes.Link:
    columns, _, table, key, namespace, orphans = tree.children
    target = key.children[0]
    parent_columns = _names(target) if target.data == "names" else (_name(target),)
    return nodes.Link(
        _names(columns),
        _name(table),
        parent_columns,
        _name(namespace.children[1]) if namespace is not None else None,
        _name(orphans.children[1]) if orphans is not None else None,
        _span(tree),
    )


def _table(tree: Tree[Any]) -> nodes.Table:
    _, name, _, source, _, target, *statements = tree.children
    built: list[nodes.Mask | nodes.Keep | nodes.Link | nodes.Transform] = []
    for statement in statements:
        if statement.data in _TRANSFORMS:
            built.append(_TRANSFORMS[statement.data](statement))
        elif statement.data == "link":
            built.append(_link(statement))
        elif statement.data == "group":
            names, treatment = statement.children
            built.append(
                nodes.Mask(_names(names), _treatment(treatment), _span(statement), coherent=True)
            )
        elif statement.data == "mask":
            built.append(
                nodes.Mask(
                    _names(statement.children[0]),
                    _treatment(statement.children[1]),
                    _span(statement),
                )
            )
        else:
            built.append(nodes.Keep(_names(statement.children[1]), _span(statement)))
    return nodes.Table(_name(name), _call(source), _call(target), tuple(built), _span(tree))


def _single(tree: Tree[Any], kind: str) -> Tree[Any] | Token | None:
    """The one child of an `expression` or `operand` that is nothing but that child."""
    parts = [child for child in tree.children if child is not None]
    return parts[0] if tree.data == kind and len(parts) == 1 else None


def _plain_value(tree: Tree[Any]) -> nodes.Value:
    """A generator argument as a value: a number, text, a bare word, a list or a map.

    Generator calls are read by the expression grammar, since `name = ...` may hold either, so
    their arguments arrive as expression trees and anything computed is refused here."""
    span = _span(tree)
    operand = _single(tree, "expression")
    parts = [c for c in operand.children if c is not None] if isinstance(operand, Tree) else []
    negative = (
        len(parts) == 2 and isinstance(parts[0], Tree) and parts[0].children[0].type == "MINUS"
    )
    primary = parts[-1] if parts and (len(parts) == 1 or negative) else None
    if isinstance(primary, Token):
        if primary.type == "NUMBER":
            return nodes.Value(-_number(primary) if negative else _number(primary), span)
        if not negative and primary.type == "NAME":
            word = str(primary)
            return nodes.Value(word == "true" if word in ("true", "false") else word, span)
        if not negative:
            return nodes.Value(python_ast.literal_eval(str(primary)), span, quoted=True)
    elif isinstance(primary, Tree) and not negative and primary.data == "e_list":
        return nodes.Value(tuple(_plain_value(c) for c in primary.children if c is not None), span)
    elif isinstance(primary, Tree) and not negative and primary.data == "e_map":
        pairs: dict[str, nodes.Value] = {}
        for pair in (c for c in primary.children if c is not None):
            token, value = pair.children
            key = str(token) if token.type == "NAME" else python_ast.literal_eval(str(token))
            if key in pairs:
                raise fail("lang.option_repeated", f"key `{key}` is given twice", _span(token))
            pairs[key] = _plain_value(value)
        return nodes.Value(pairs, span)
    raise fail(
        "lang.generator_argument",
        "a generator takes plain values: numbers, text, words, lists and maps",
        span,
        "for a computed column write the expression on its own: `total = price * quantity`",
    )


def _generator_call(expression: Tree[Any]) -> nodes.Call | None:
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
            key = nodes.Name(str(token), _span(token))
            if any(o.key.text == key.text for o in options):
                raise fail("lang.option_repeated", f"option `{key.text}` is given twice", key.span)
            options.append(nodes.Option(key, _plain_value(value)))
        elif options:
            raise fail(
                "lang.positional_after_option",
                "a plain value cannot follow a `key: value` option",
                _span(argument),
                "put plain values first",
            )
        else:
            positional.append(_plain_value(argument))
    name = nodes.Name(str(head), _span(head))
    return nodes.Call(name, tuple(positional), tuple(options), True, _span(call))


def _generate(tree: Tree[Any]) -> nodes.Generate:
    _, name, _, rows, _, target, *statements = tree.children
    built: list[nodes.GenColumn | nodes.GenLink | nodes.Unique] = []
    for statement in statements:
        span = _span(statement)
        if statement.data == "gen_link":
            column, _, table, parent = statement.children
            built.append(nodes.GenLink(_name(column), _name(table), _name(parent), span))
        elif statement.data == "unique":
            built.append(nodes.Unique(_names(statement.children[1]), span))
        else:
            built.append(_gen_column(statement))
    return nodes.Generate(_name(name), _token_value(rows), _call(target), tuple(built), _span(tree))


def _gen_column(statement: Tree[Any]) -> nodes.GenColumn:
    """`name = ...` in a generated table, kept in both readings where both are possible.

    `faker(first_name)` and `concat(first, last)` look alike; lowering knows the engine's
    generator names and picks. `key: value` options and maps only occur in a generator call, so
    with those there is no expression reading, and a call that cannot be read is an error."""
    body = statement.children[1]
    only_a_call = any(True for _ in body.find_pred(lambda t: t.data in ("e_option", "e_map")))
    call = None
    try:
        call = _generator_call(body)
    except LangError:
        if only_a_call:
            raise
    if only_a_call and call is None:
        raise fail(
            "lang.generator_argument",
            "`key: value` options and `{...}` maps belong to a generator call",
            _span(body),
            "write one call: `id = sequence(start: 1)`",
        )
    expression = None if only_a_call else nodes.Expression(_expression_text(body), _span(body))
    return nodes.GenColumn(_name(statement.children[0]), call, expression, _span(statement))


def _pairs(pairs: list[Tree[Any]]) -> list[nodes.Option]:
    built = []
    for pair in pairs:
        token, value = pair.children
        key = str(token) if token.type == "NAME" else python_ast.literal_eval(str(token))
        built.append(nodes.Option(nodes.Name(key, _span(token)), _value(value)))
    return built


def _program(tree: Tree[Any]) -> nodes.Program:
    _, version_token, pipeline = tree.children
    version = _number(version_token)
    if version not in SUPPORTED_VERSIONS:
        raise fail(
            "lang.version",
            f"language version {version_token} is not supported",
            _span(version_token),
            "this compiler reads `decoy 1`",
        )
    _, name, *items = pipeline.children
    settings: list[nodes.Setting] = []
    lets: list[nodes.Let] = []
    tables: list[nodes.Table | nodes.Generate] = []
    extra: list[nodes.Option] = []
    options: list[nodes.Option] = []
    for item in items:
        span = _span(item)
        if item.data == "seed":
            settings.append(nodes.Setting("seed", _token_value(item.children[1]), span))
        elif item.data == "secret":
            settings.append(nodes.Setting("secret", _token_value(item.children[2]), span))
        elif item.data == "unconfigured":
            word = _name(item.children[2])
            settings.append(nodes.Setting("unconfigured", nodes.Value(word.text, word.span), span))
        elif item.data in ("settings", "options"):
            (extra if item.data == "settings" else options).extend(_pairs(item.children[1:]))
        elif item.data == "let":
            lets.append(nodes.Let(_name(item.children[1]), _treatment(item.children[2]), span))
        elif item.data == "generate":
            tables.append(_generate(item))
        else:
            tables.append(_table(item))
    return nodes.Program(
        int(version),
        _name(name) if name is not None else None,
        tuple(settings),
        tuple(lets),
        tuple(tables),
        _span(pipeline),
        tuple(extra),
        tuple(options),
    )


def _token_value(token: Token) -> nodes.Value:
    if token.type in ("DQ_STRING", "SQ_STRING"):
        return nodes.Value(python_ast.literal_eval(str(token)), _span(token), quoted=True)
    return nodes.Value(_number(token), _span(token))
