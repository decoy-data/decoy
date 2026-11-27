"""AT-50b: every step the sink takes after the visibility point sits in `except Exception`.

The sink catches with `contextlib.suppress(Exception)`, because the lint-debt ratchet takes no
new `except Exception`. The real writers raise more than `OSError`: `AtomicWriteError` and `EvidenceWriteRefusal` are
`Exception` subclasses and not `OSError`. A narrower handler would let one escape `deliver`
after `LATEST` moved and turn a delivered run into a failed exit. Scanned shapes: a handler that
names `OSError` (alone or in a tuple), a bare `except`, and a `try` that has no handler.
"""

from __future__ import annotations

import ast
from pathlib import Path

SINK = Path(__file__).resolve().parents[3] / "src" / "decoy" / "cli" / "io" / "_delivery.py"


def _is_exception(kind: ast.expr | None) -> bool:
    return isinstance(kind, ast.Name) and kind.id in {"Exception", "BaseException"}


def _bad_handlers(source: str) -> list[int]:
    found: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.With):
            for item in node.items:
                call = item.context_expr
                name = getattr(getattr(call, "func", None), "attr", getattr(call.func, "id", ""))
                if name == "suppress" and not all(_is_exception(a) for a in call.args):
                    found.append(node.lineno)
        if not isinstance(node, ast.Try):
            continue
        if not node.handlers and not node.finalbody:
            found.append(node.lineno)
        for handler in node.handlers:
            if not _is_exception(handler.type):
                found.append(handler.lineno)
    return found


def test_every_handler_in_the_sink_is_except_exception() -> None:
    assert _bad_handlers(SINK.read_text(encoding="utf-8")) == []


def test_the_scan_sees_a_narrow_handler_and_a_bare_except() -> None:
    narrow = "try:\n    pass\nexcept OSError:\n    pass\n"
    bare = "try:\n    pass\nexcept:\n    pass\n"
    assert _bad_handlers(narrow) == [3]
    assert _bad_handlers(bare) == [3]


def test_the_scan_sees_a_narrow_suppress() -> None:
    narrow = "import contextlib\nwith contextlib.suppress(OSError):\n    pass\n"
    wide = "import contextlib\nwith contextlib.suppress(Exception):\n    pass\n"
    assert _bad_handlers(narrow) == [2]
    assert _bad_handlers(wide) == []
