"""Source text to syntax tree.

Parsing uses Lark's LALR parser with its contextual lexer, the same library the engine uses for
its expression grammar. The Lark tree is rebuilt into the frozen nodes of `_ast`, each carrying
its source span, so later stages never see Lark types.
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Any

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedCharacters, UnexpectedInput, UnexpectedToken

from decoy.lang import _ast as nodes
from decoy.lang._errors import LangError, Span, fail
from decoy.lang._expressions import expression_text, generator_call
from decoy.lang._grammar import DISPLAY, GRAMMAR, KEYWORD_TERMINALS
from decoy.lang._tokens import number_of, span_of, unquote

SUPPORTED_VERSIONS = ("1",)


@lru_cache(maxsize=1)
def _parser() -> Lark:
    return Lark(GRAMMAR, parser="lalr", propagate_positions=True, maybe_placeholders=True)


def parse(text: str) -> nodes.Program:
    return _program(_tree(_parser(), text))


def _tree(parser: Lark, text: str) -> Tree[Any]:
    try:
        return parser.parse(text)
    except UnexpectedInput as error:
        failure = _syntax_error(error, text)
    raise failure


# Lark takes a lexer callback when the parser is built, not per call, so the comments of the
# parse in progress are kept per thread.
_collecting = threading.local()


def _keep_comment(token: Token) -> Token:
    _collecting.comments.append(token)
    return token


@lru_cache(maxsize=1)
def _commenting_parser() -> Lark:
    return Lark(
        GRAMMAR,
        parser="lalr",
        propagate_positions=True,
        maybe_placeholders=True,
        lexer_callbacks={"COMMENT": _keep_comment},
    )


def parse_with_comments(text: str) -> tuple[nodes.Program, list[tuple[int, int, str]]]:
    """The program, and each comment as `(line, column, text)` in source order. The formatter is
    the one caller: compiling has no use for comments."""
    _collecting.comments = []
    try:
        program = _program(_tree(_commenting_parser(), text))
        return program, [(t.line or 1, t.column or 1, str(t)) for t in _collecting.comments]
    finally:
        del _collecting.comments


def _syntax_error(error: UnexpectedInput, text: str) -> Exception:
    width = len(error.token) if isinstance(error, UnexpectedToken) else 1
    span = Span(error.line, error.column, error.line, error.column + max(1, width))
    found = _found(error.token) if isinstance(error, UnexpectedToken) else "a character"
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


# "unexpected <noun>": DISPLAY holds phrases with an article, which read wrongly after "unexpected".
_KIND_NOUN = {
    "NAME": "word",
    "NUMBER": "number",
    "DQ_STRING": "quoted text",
    "SQ_STRING": "quoted name",
}


def _found(token: Token) -> str:
    """How an unexpected token is named. Only a word of the language or punctuation is shown.
    A number, quoted text or a bare word is named by kind: it may be a seed, a path or a secret
    name, and an error never quotes a config value."""
    if token.type == "$END":
        return "end of file"
    if token.type in _KIND_NOUN:
        return _KIND_NOUN[token.type]
    return f"`{token}`"


def _one_of(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return "one of: " + ", ".join(items)


def _name(tree: Tree[Any]) -> nodes.Name:
    token = tree.children[0]
    if token.type == "NAME":
        return nodes.Name(str(token), span_of(token))
    text = unquote(token)
    if not text:
        raise fail("lang.name_empty", "a name cannot be empty", span_of(token))
    return nodes.Name(text, span_of(token))


def _value(node: Tree[Any]) -> nodes.Value:
    span = span_of(node)
    kind = node.data
    if kind == "string":
        return nodes.Value(unquote(node.children[0]), span)
    if kind == "number":
        return nodes.Value(number_of(node.children[0]), span)
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
            key = str(token) if token.type == "NAME" else unquote(token)
            if key in pairs:
                raise fail(
                    "lang.option_repeated", "a key is given twice in this map", span_of(token)
                )
            pairs[key] = _value(value)
        return nodes.Value(pairs, span)
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
                span_of(argument),
                "put plain values first",
            )
        else:
            positional.append(_value(argument))
    return nodes.Call(
        _name(name_tree), tuple(positional), tuple(options), arguments is not None, span_of(tree)
    )


def _treatment(tree: Tree[Any]) -> nodes.Treatment:
    call, namespace, deterministic, vaulted, condition = tree.children
    when = None
    if condition is not None:
        expression = condition.children[1]
        when = nodes.Expression(expression_text(expression), span_of(expression))
    return nodes.Treatment(
        _call(call),
        _name(namespace.children[1]) if namespace is not None else None,
        deterministic is not None,
        vaulted is not None,
        when,
        span_of(tree),
    )


def _names(tree: Tree[Any]) -> tuple[nodes.Name, ...]:
    return tuple(_name(child) for child in tree.children)


def _expression(tree: Tree[Any]) -> nodes.Expression:
    return nodes.Expression(expression_text(tree), span_of(tree))


def _where(tree: Tree[Any]) -> nodes.Where:
    return nodes.Where(_expression(tree.children[1]), span_of(tree))


def _define(tree: Tree[Any]) -> nodes.Define:
    return nodes.Define(_name(tree.children[0]), _expression(tree.children[1]), span_of(tree))


def _sort(tree: Tree[Any]) -> nodes.Sort:
    keys = tuple(
        nodes.SortKey(
            _name(key.children[0]), key.children[1] is None or key.children[1].type == "ASC"
        )
        for key in tree.children[2:]
    )
    return nodes.Sort(keys, span_of(tree))


def _limit(tree: Tree[Any]) -> nodes.Limit:
    return nodes.Limit(_token_value(tree.children[1]), span_of(tree))


def _dedupe(tree: Tree[Any]) -> nodes.Dedupe:
    names = tree.children[2]
    return nodes.Dedupe(_names(names) if names is not None else (), span_of(tree))


def _drop(tree: Tree[Any]) -> nodes.Drop:
    return nodes.Drop(_names(tree.children[1]), span_of(tree))


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
        span_of(tree),
    )


def _table(tree: Tree[Any]) -> nodes.Table:
    _, name, _, source, _, target, *statements = tree.children
    built: list[nodes.Mask | nodes.Keep | nodes.Link | nodes.Shaping] = []
    for statement in statements:
        if statement.data in _TRANSFORMS:
            built.append(_TRANSFORMS[statement.data](statement))
        elif statement.data == "link":
            built.append(_link(statement))
        elif statement.data == "group":
            names, treatment, mark = statement.children
            built.append(
                nodes.Mask(
                    _names(names),
                    _treatment(treatment),
                    span_of(statement),
                    coherent=True,
                    unreviewed=mark is not None,
                )
            )
        elif statement.data == "mask":
            built.append(
                nodes.Mask(
                    _names(statement.children[0]),
                    _treatment(statement.children[1]),
                    span_of(statement),
                    unreviewed=statement.children[2] is not None,
                )
            )
        else:
            marked = statement.children[2] is not None
            built.append(nodes.Keep(_names(statement.children[1]), span_of(statement), marked))
    return nodes.Table(_name(name), _call(source), _call(target), tuple(built), span_of(tree))


def _generate(tree: Tree[Any]) -> nodes.Generate:
    _, name, _, rows, _, target, *statements = tree.children
    built: list[nodes.GenColumn | nodes.GenLink | nodes.Unique] = []
    for statement in statements:
        span = span_of(statement)
        if statement.data == "gen_link":
            column, _, table, parent = statement.children
            built.append(nodes.GenLink(_name(column), _name(table), _name(parent), span))
        elif statement.data == "unique":
            built.append(nodes.Unique(_names(statement.children[1]), span))
        else:
            built.append(_gen_column(statement))
    return nodes.Generate(
        _name(name), _token_value(rows), _call(target), tuple(built), span_of(tree)
    )


def _gen_column(statement: Tree[Any]) -> nodes.GenColumn:
    """`name = ...` in a generated table, kept in both readings where both are possible.

    `faker(first_name)` and `concat(first, last)` look alike; lowering knows the engine's
    generator names and picks. `key: value` options and maps only occur in a generator call, so
    with those there is no expression reading, and a call that cannot be read is an error."""
    body = statement.children[1]
    only_a_call = any(True for _ in body.find_pred(lambda t: t.data in ("e_option", "e_map")))
    call = None
    try:
        call = generator_call(body)
    except LangError:
        if only_a_call:
            raise
    if only_a_call and call is None:
        raise fail(
            "lang.generator_argument",
            "`key: value` options and `{...}` maps belong to a generator call",
            span_of(body),
            "write one call: `id = sequence(start: 1)`",
        )
    expression = None if only_a_call else nodes.Expression(expression_text(body), span_of(body))
    return nodes.GenColumn(_name(statement.children[0]), call, expression, span_of(statement))


def _edge_end(tree: Tree[Any]) -> tuple[nodes.Name, tuple[nodes.Name, ...]]:
    table, key = tree.children
    target = key.children[0]
    return _name(table), _names(target) if target.data == "names" else (_name(target),)


def _seed(tree: Tree[Any]) -> nodes.Seed:
    _, table, how = tree.children
    span = span_of(tree)
    if how.data == "sample":
        _, amount, unit, _, columns = how.children
        unit_text = "%" if unit.type == "PERCENT_SIGN" else "rows"
        return nodes.Seed(
            _name(table), "sample", _names(columns), _token_value(amount), unit_text, (), None, span
        )
    if how.data == "keys":
        _, columns, _, values = how.children
        return nodes.Seed(
            _name(table), "keys", _names(columns), None, None, (), _value(values), span
        )
    conditions = []
    for condition in how.children[1:]:
        column = _name(condition.children[0])
        if condition.data == "compare":
            operator, value = str(condition.children[1]), _value(condition.children[2])
        elif condition.data == "member":
            operator, value = "in", _value(condition.children[2])
        else:
            operator, value = condition.data.replace("_", " "), None
        conditions.append(nodes.Condition(column, operator, value, span_of(condition)))
    return nodes.Seed(_name(table), "filter", (), None, None, tuple(conditions), None, span)


def _subset(tree: Tree[Any]) -> nodes.Subset:
    seeds: list[nodes.Seed] = []
    follows: list[nodes.Follow] = []
    budget: list[nodes.Option] = []
    dangling = False
    for statement in tree.children[1:]:
        if statement.data == "subset_seed":
            seeds.append(_seed(statement))
        elif statement.data == "follow":
            _, parent, _, child, direction = statement.children
            follows.append(
                nodes.Follow(
                    *_edge_end(parent), *_edge_end(child), _name(direction), span_of(statement)
                )
            )
        elif statement.data == "budget":
            block = _block(statement)
            if block.positional or block.refs:
                raise fail(
                    "lang.block_arguments",
                    "`budget` takes `key: value` options only",
                    block.span,
                    "write `budget(max_total_rows: 1_000_000)`",
                )
            if budget:
                raise fail("lang.block_repeated", "`budget` is written twice", block.span)
            budget.extend(block.options)
        else:
            dangling = True
    return nodes.Subset(tuple(seeds), tuple(follows), tuple(budget), dangling, span_of(tree))


_BLOCKS = ("scan", "expect", "block", "declare")


def _ref(tree: Tree[Any]) -> nodes.Ref:
    return nodes.Ref(_name(tree.children[0]), _name(tree.children[1]), span_of(tree))


def _block(tree: Tree[Any]) -> nodes.Block:
    """A check or safety statement, with its arguments sorted into values, refs and options."""
    head, second, *rest = tree.children
    if tree.data == "declare":
        refs = tuple(_ref(child) for child in rest[1:])
        return nodes.Block("namespace", _name(second), (), refs, (), span_of(tree))
    if tree.data == "scan":
        kind, name, arguments = f"scan {second}", None, rest[0]
    elif tree.data == "expect":
        kind, name, arguments = "expect", _name(second), rest[0]
    else:
        kind, name, arguments = str(head), None, second
    positional: list[nodes.Value] = []
    refs: list[nodes.Ref] = []
    options: list[nodes.Option] = []
    for argument in arguments.children if arguments is not None else ():
        if argument is None:
            continue
        if argument.data == "ref":
            refs.append(_ref(argument))
        elif argument.data == "option":
            key = _name(argument.children[0])
            if any(o.key.text == key.text for o in options):
                raise fail("lang.option_repeated", f"option `{key.text}` is given twice", key.span)
            options.append(nodes.Option(key, _value(argument.children[1])))
        else:
            positional.append(_value(argument))
    return nodes.Block(kind, name, tuple(positional), tuple(refs), tuple(options), span_of(tree))


def _pairs(pairs: list[Tree[Any]]) -> list[nodes.Option]:
    built = []
    for pair in pairs:
        token, value = pair.children
        key = str(token) if token.type == "NAME" else unquote(token)
        built.append(nodes.Option(nodes.Name(key, span_of(token)), _value(value)))
    return built


def _program(tree: Tree[Any]) -> nodes.Program:
    _, version_token, pipeline = tree.children
    if str(version_token) not in SUPPORTED_VERSIONS:
        raise fail(
            "lang.version",
            "this language version is not supported",
            span_of(version_token),
            "this compiler reads `decoy 1`",
        )
    _, name, *items = pipeline.children
    settings: list[nodes.Setting] = []
    lets: list[nodes.Let] = []
    tables: list[nodes.Table | nodes.Generate] = []
    extra: list[nodes.Option] = []
    block_spans: dict[str, Span] = {}
    subsets: list[nodes.Subset] = []
    blocks: list[nodes.Block] = []
    options: list[nodes.Option] = []
    for item in items:
        span = span_of(item)
        if item.data == "seed":
            settings.append(nodes.Setting("seed", _token_value(item.children[1]), span))
        elif item.data == "secret":
            settings.append(nodes.Setting("secret", _token_value(item.children[2]), span))
        elif item.data == "unconfigured":
            word = _name(item.children[2])
            settings.append(nodes.Setting("unconfigured", nodes.Value(word.text, word.span), span))
        elif item.data == "subset":
            subsets.append(_subset(item))
        elif item.data in _BLOCKS:
            blocks.append(_block(item))
        elif item.data == "settings":
            extra.extend(_pairs(item.children[1:]))
            block_spans["settings_span"] = span
        elif item.data == "options":
            options.extend(_pairs(item.children[1:]))
            block_spans["options_span"] = span
        elif item.data == "let":
            lets.append(nodes.Let(_name(item.children[1]), _treatment(item.children[2]), span))
        elif item.data == "generate":
            tables.append(_generate(item))
        else:
            tables.append(_table(item))
    return nodes.Program(
        _name(name) if name is not None else None,
        tuple(settings),
        tuple(lets),
        tuple(tables),
        span_of(pipeline),
        tuple(extra),
        tuple(options),
        tuple(blocks),
        tuple(subsets),
        **block_spans,
    )


def _token_value(token: Token) -> nodes.Value:
    if token.type in ("DQ_STRING", "SQ_STRING"):
        return nodes.Value(unquote(token), span_of(token))
    return nodes.Value(number_of(token), span_of(token))
