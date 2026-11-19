"""Compiler diagnostics for the Decoy language.

A diagnostic carries a public code, a message and a source position. Rendering is separate, so a
caller that must not echo config text can print the position alone.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    """A 1-based source position: where a construct starts and ends."""

    line: int
    column: int
    end_line: int
    end_column: int


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


def fail(code: str, message: str, span: Span | None = None, hint: str | None = None) -> LangError:
    return LangError([Diagnostic(code, message, span, hint)])


def render(diagnostic: Diagnostic, source: str | None = None, filename: str = "<input>") -> str:
    """One diagnostic as text. With `source`, the offending line is shown with a caret under it."""
    where = filename
    if diagnostic.span is not None:
        where = f"{filename}:{diagnostic.span.line}:{diagnostic.span.column}"
    lines = [f"{where}: error[{diagnostic.code}]: {diagnostic.message}"]
    if source is not None and diagnostic.span is not None:
        text = source.splitlines()
        if 0 < diagnostic.span.line <= len(text):
            span = diagnostic.span
            shown = text[span.line - 1]
            end = span.end_column if span.end_line == span.line else len(shown) + 1
            width = max(1, end - span.column)
            lines += [f"  {shown}", "  " + " " * (span.column - 1) + "^" * width]
    if diagnostic.hint:
        lines.append(f"  hint: {diagnostic.hint}")
    return "\n".join(lines)
