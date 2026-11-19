"""Syntax tree of a `.decoy` program: frozen nodes, each with the span it was read from."""

from __future__ import annotations

from dataclasses import dataclass

from decoy.lang._errors import Span

Scalar = str | int | float | bool


@dataclass(frozen=True)
class Value:
    """An option value. `quoted` separates the string `"zip"` from the bare word `zip`; both
    compile to the same string, the difference is kept for the formatter."""

    value: Scalar | tuple["Value", ...]
    span: Span
    quoted: bool = False


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
class Treatment:
    """A strategy call and the settings written after it."""

    call: Call
    namespace: Name | None
    deterministic: bool
    vaulted: bool
    span: Span


@dataclass(frozen=True)
class Mask:
    columns: tuple[Name, ...]
    treatment: Treatment
    span: Span


@dataclass(frozen=True)
class Keep:
    columns: tuple[Name, ...]
    span: Span


@dataclass(frozen=True)
class Table:
    name: Name
    source: Call
    target: Call
    statements: tuple[Mask | Keep, ...]
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
    language_version: int
    name: Name | None
    settings: tuple[Setting, ...]
    lets: tuple[Let, ...]
    tables: tuple[Table, ...]
    span: Span
