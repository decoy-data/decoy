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
from decoy.lang._errors import Span, fail
from decoy.lang._grammar import DISPLAY, GRAMMAR

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
            found = "end of file" if error.token.type == "$END" else f"`{error.token}`"
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
    return fail("lang.syntax", message, span, hint)


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
    text = str(token)
    return nodes.Name(text[1:-1] if token.type == "QUOTED_NAME" else text, _span(token))


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
        return nodes.Value(_name(node.children[0]).text, span)
    return nodes.Value(tuple(_value(child) for child in node.children if child is not None), span)


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
    call, namespace, deterministic, vaulted = tree.children
    return nodes.Treatment(
        _call(call),
        _name(namespace.children[1]) if namespace is not None else None,
        deterministic is not None,
        vaulted is not None,
        _span(tree),
    )


def _names(tree: Tree[Any]) -> tuple[nodes.Name, ...]:
    return tuple(_name(child) for child in tree.children)


def _table(tree: Tree[Any]) -> nodes.Table:
    _, name, _, source, _, target, *statements = tree.children
    built: list[nodes.Mask | nodes.Keep] = []
    for statement in statements:
        if statement.data == "mask":
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
    tables: list[nodes.Table] = []
    for item in items:
        span = _span(item)
        if item.data == "seed":
            settings.append(nodes.Setting("seed", _token_value(item.children[1]), span))
        elif item.data == "secret":
            settings.append(nodes.Setting("secret", _token_value(item.children[2]), span))
        elif item.data == "unconfigured":
            word = _name(item.children[2])
            settings.append(nodes.Setting("unconfigured", nodes.Value(word.text, word.span), span))
        elif item.data == "let":
            lets.append(nodes.Let(_name(item.children[1]), _treatment(item.children[2]), span))
        else:
            tables.append(_table(item))
    return nodes.Program(
        int(version),
        _name(name) if name is not None else None,
        tuple(settings),
        tuple(lets),
        tuple(tables),
        _span(pipeline),
    )


def _token_value(token: Token) -> nodes.Value:
    if token.type == "STRING":
        return nodes.Value(python_ast.literal_eval(str(token)), _span(token), quoted=True)
    return nodes.Value(_number(token), _span(token))
