"""The one reader of gates.sh's shell arrays and of the `-m` expression in `PYTEST_ARGS`.

The sentry manifest, the serial-resource guard and the CI lane rule M5 all need the same two
facts from gates.sh: an array's tokens and the marker expression the gate filters on. They read
them here so a format change in gates.sh breaks one reader, not three half-copies.

An empty `PYTEST_ARGS=()` means the gate filters no marker (`marker_expr` returns None); the
parallel and serial passes then run `not serial` and `serial` (see `pass_expressions`).
"""

from __future__ import annotations

import re
import shlex


def shell_array(name: str, text: str) -> list[str] | None:
    """The tokens of the `NAME=( ... )` array in `text`, or None when there is no such array.

    The array may span lines and carry `#` comments; a quoted token stays one element."""
    m = re.search(rf"^{name}=\(([^)]*)\)", text, re.MULTILINE)
    return shlex.split(m.group(1), comments=True) if m else None


def marker_expr(gates_text: str) -> str | None:
    """The `-m` expression in `PYTEST_ARGS`, or None when the gate filters no marker.

    Raises ValueError for a missing array or a `-m` with no expression, so a malformed line fails
    loudly instead of reading as "no filter"."""
    args = shell_array("PYTEST_ARGS", gates_text)
    if args is None:
        raise ValueError("gates.sh has no PYTEST_ARGS array")
    if "-m" not in args:
        return None
    i = args.index("-m")
    if i + 1 >= len(args) or not args[i + 1].strip():
        raise ValueError("PYTEST_ARGS has -m with no expression")
    return args[i + 1]


def pass_expressions(gates_text: str) -> tuple[str, str]:
    """`(parallel, serial)` `-m` expressions gates.sh builds for a parallel run.

    With no marker filter they are exactly `not serial` and `serial`: never an empty
    parenthesis and never a leading `and`."""
    expr = marker_expr(gates_text)
    if expr is None:
        return "not serial", "serial"
    return f"({expr}) and not serial", f"({expr}) and serial"
