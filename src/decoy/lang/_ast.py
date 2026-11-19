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
class Transform:
    """A table-shaping statement, already in the engine's transform shape: the `op` and its
    fields, each with the span it was written at."""

    op: str
    fields: tuple[tuple[str, Any, Span], ...]
    span: Span


@dataclass(frozen=True)
class Table:
    name: Name
    source: Call
    target: Call
    statements: tuple[Mask | Keep | Link | Transform, ...]
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
