"""Compiler diagnostics for the Decoy language.

A diagnostic carries a public code, a message and a source position. Messages name words of the
language, strategies, tables and columns, never a value the config holds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from decoy.lang._codes import Code


@dataclass(frozen=True)
class Span:
    """A 1-based source position: where a construct starts and ends."""

    line: int
    column: int
    end_line: int
    end_column: int


# Config path to the source span that produced it, built during lowering.
SourceMap = dict[tuple[Any, ...], "Span"]


@dataclass(frozen=True)
class Diagnostic:
    code: str  # public, `lang.*`
    message: str
    span: Span | None = None
    hint: str | None = None


class LangError(Exception):
    """A `.decoy` program that does not compile. Holds every problem found, in source order."""

    def __init__(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__("; ".join(d.message for d in diagnostics))


def diagnostic(
    code: Code, span: Span | None = None, hint: str | None = None, **fields: object
) -> Diagnostic:
    """The one place a `Diagnostic` is built. `fields` fill the `{name}` slots of the message."""
    return Diagnostic(code.code, code.message.format(**fields), span, hint)


def fail(
    code: Code, span: Span | None = None, hint: str | None = None, **fields: object
) -> LangError:
    return LangError([diagnostic(code, span, hint, **fields)])


def render(diagnostic: Diagnostic, filename: str = "<input>") -> str:
    """One diagnostic as text: `file:line:column: error[code]: message`, then its hint.

    The source line is never shown: the CLI's rule is that an error does not quote the config."""
    where = filename
    if diagnostic.span is not None:
        where = f"{filename}:{diagnostic.span.line}:{diagnostic.span.column}"
    lines = [f"{where}: error[{diagnostic.code}]: {diagnostic.message}"]
    if diagnostic.hint:
        lines.append(f"  hint: {diagnostic.hint}")
    return "\n".join(lines)
