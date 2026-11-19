"""Syntax tree of a `.decoy` program: frozen nodes, each with the span it was read from."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from decoy.lang._errors import Span

Scalar = str | int | float | bool


@dataclass(frozen=True)
class Value:
    """An option value: a scalar, a list or a map. A quoted string and a bare word are the same
    string."""

    value: Scalar | tuple["Value", ...] | dict[str, "Value"]
    span: Span


def plain(value: Value) -> Any:
    """A value node as the plain Python value the config holds."""
    if isinstance(value.value, tuple):
        return [plain(item) for item in value.value]
    if isinstance(value.value, dict):
        return {key: plain(item) for key, item in value.value.items()}
    return value.value


@dataclass(frozen=True)
class Name:
    text: str
    span: Span


@dataclass(frozen=True)
class Option:
    key: Name
    value: Value


@dataclass(frozen=True)
class Call:
    """`name`, or `name(positional, key: value)`."""

    name: Name
    positional: tuple[Value, ...]
    options: tuple[Option, ...]
    has_parens: bool
    span: Span


@dataclass(frozen=True)
class Expression:
    """An expression as one line of canonical text: single spaces, no line breaks or comments.

    The compiler only finds where an expression starts and ends. The text goes to the engine,
    whose closed grammars are the one place that decides what an expression may contain."""

    text: str
    span: Span


@dataclass(frozen=True)
class Treatment:
    """A strategy call and the settings written after it."""

    call: Call
    namespace: Name | None
    deterministic: bool
    vaulted: bool
    when: Expression | None
    span: Span


@dataclass(frozen=True)
class Mask:
    columns: tuple[Name, ...]
    treatment: Treatment
    span: Span
    coherent: bool = False  # written `{a, b} : rule`: one consistent group per row


@dataclass(frozen=True)
class Link:
    """`columns <- table.key`: a foreign key whose values follow the parent key's masking."""

    columns: tuple[Name, ...]
    parent_table: Name
    parent_columns: tuple[Name, ...]
    namespace: Name | None
    orphans: Name | None
    span: Span


@dataclass(frozen=True)
class Keep:
    columns: tuple[Name, ...]
    span: Span


@dataclass(frozen=True)
class Where:
    """`where <expression>`: keep the rows it holds for."""

    expression: Expression
    span: Span


@dataclass(frozen=True)
class Define:
    """`name = <expression>` in a masked table: a new column."""

    name: Name
    expression: Expression
    span: Span


@dataclass(frozen=True)
class SortKey:
    column: Name
    ascending: bool


@dataclass(frozen=True)
class Sort:
    keys: tuple[SortKey, ...]
    span: Span


@dataclass(frozen=True)
class Limit:
    count: Value
    span: Span


@dataclass(frozen=True)
class Dedupe:
    """`dedupe`, or `dedupe on a, b`."""

    columns: tuple[Name, ...]
    span: Span


@dataclass(frozen=True)
class Drop:
    columns: tuple[Name, ...]
    span: Span


Shaping = Where | Define | Sort | Limit | Dedupe | Drop


@dataclass(frozen=True)
class Table:
    name: Name
    source: Call
    target: Call
    statements: tuple[Mask | Keep | Link | Shaping, ...]
    span: Span


@dataclass(frozen=True)
class Ref:
    """`table.column`."""

    table: Name
    column: Name
    span: Span


@dataclass(frozen=True)
class Block:
    """A pipeline-level check or safety statement: `scan before(...)`, `expect name(...)`,
    `quarantine(...)`, `baseline(...)`, `delivery(...)`, `namespace name for ...`."""

    kind: str
    name: Name | None
    positional: tuple[Value, ...]
    refs: tuple[Ref, ...]
    options: tuple[Option, ...]
    span: Span


@dataclass(frozen=True)
class Condition:
    """One test in `start <table> where ...`: `column == value`, `column in [...]`,
    `column is null`, `column is not null`."""

    column: Name
    operator: str
    value: Value | None
    span: Span


@dataclass(frozen=True)
class Seed:
    """`start <table> ...`: where a subset begins. `mode` is the engine's seed mode."""

    table: Name
    mode: str  # sample | filter | keys
    key_columns: tuple[Name, ...]
    amount: Value | None  # sample: the number before `%` or `rows`
    unit: str | None  # sample: "%" or "rows"
    conditions: tuple[Condition, ...]
    keys: Value | None
    span: Span


@dataclass(frozen=True)
class Follow:
    """`follow parent.key -> child.key <direction>`."""

    parent_table: Name
    parent_columns: tuple[Name, ...]
    child_table: Name
    child_columns: tuple[Name, ...]
    direction: Name
    span: Span


@dataclass(frozen=True)
class Subset:
    seeds: tuple[Seed, ...]
    follows: tuple[Follow, ...]
    budget: tuple[Option, ...]
    allow_dangling: bool
    span: Span


@dataclass(frozen=True)
class GenColumn:
    """`name = generator(...)` or `name = expression` in a generated table. A generator call has
    `call`; anything else is an expression the engine's `derived` type evaluates."""

    name: Name
    call: Call | None
    expression: Expression | None
    span: Span


@dataclass(frozen=True)
class GenLink:
    """`name <- table.column` in a generated table: values drawn from that table's column."""

    name: Name
    parent_table: Name
    parent_column: Name
    span: Span


@dataclass(frozen=True)
class Unique:
    """`unique (a, b)`: the listed columns' value combinations do not repeat."""

    columns: tuple[Name, ...]
    span: Span


@dataclass(frozen=True)
class Generate:
    name: Name
    rows: Value
    target: Call
    statements: tuple[GenColumn | GenLink | Unique, ...]
    span: Span


@dataclass(frozen=True)
class Let:
    name: Name
    treatment: Treatment
    span: Span


@dataclass(frozen=True)
class Setting:
    """A pipeline setting: `seed 42`, `secret ref("x")`, `unconfigured columns error`."""

    kind: str
    value: Value
    span: Span


@dataclass(frozen=True)
class Program:
    name: Name | None
    settings: tuple[Setting, ...]
    lets: tuple[Let, ...]
    tables: tuple[Table | Generate, ...]
    span: Span
    extra_settings: tuple[Option, ...] = ()  # the `settings { }` block
    options: tuple[Option, ...] = ()  # the `options { }` block
    blocks: tuple[Block, ...] = ()
    subsets: tuple[Subset, ...] = ()
