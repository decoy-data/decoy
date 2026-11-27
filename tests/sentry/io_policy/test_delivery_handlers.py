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
    # Not `BaseException`: Ctrl-C must still propagate out of the cleanup (AT-50).
    return isinstance(kind, ast.Name) and kind.id == "Exception"


def _cleans_up_and_reraises(handler: ast.ExceptHandler) -> bool:
    """`except BaseException:` that ends in a bare `raise`: cleanup that lets Ctrl-C through."""
    base = isinstance(handler.type, ast.Name) and handler.type.id == "BaseException"
    return base and bool(handler.body) and isinstance(handler.body[-1], ast.Raise)


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
            if not _is_exception(handler.type) and not _cleans_up_and_reraises(handler):
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


def test_the_scan_sees_suppress_base_exception() -> None:
    seeded = "import contextlib\nwith contextlib.suppress(BaseException):\n    pass\n"
    assert _bad_handlers(seeded) == [2]
    assert _bad_handlers("try:\n    pass\nexcept BaseException:\n    pass\n") == [3]


# The calls that may stand outside `_step` in the two post-visibility entry points: the step
# runner itself and plain state reads.
_PLAIN = {"self._step", "isinstance", "any"}


def _calls_outside_lambdas(node: ast.AST) -> list[ast.Call]:
    """Calls under `node`, not looking inside a lambda: a lambda is a step handed to `_step`."""
    found: list[ast.Call] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Lambda):
            continue
        if isinstance(child, ast.Call):
            found.append(child)
        found.extend(_calls_outside_lambdas(child))
    return found


def _unguarded_calls(source: str, methods: set[str]) -> list[str]:
    """Calls in the named methods that are not `self._step(...)` or a plain read."""
    found: list[str] = []
    tree = ast.parse(source)
    sinks = [
        n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name in {"DeliverySink", "S"}
    ]
    for node in (m for c in sinks for m in ast.walk(c)):
        if isinstance(node, ast.FunctionDef) and node.name in methods:
            found.extend(
                f"{node.name}:{ast.unparse(c.func)}"
                for c in _calls_outside_lambdas(node)
                if ast.unparse(c.func) not in _PLAIN
            )
    return found


def test_the_real_reconcile_and_abort_call_only_through_step() -> None:
    """AT-50b: a direct `self._pre.restore()` in `_reconcile` or `abort` could raise past the
    visibility point, so every action there is handed to `_step` as a reference."""
    source = SINK.read_text(encoding="utf-8")
    assert _unguarded_calls(source, {"_reconcile", "abort"}) == []


def test_the_guard_sees_a_seeded_unguarded_call() -> None:
    seeded = (
        "class S:\n"
        "    def abort(self):\n"
        "        self._step(self._stage.abort)\n"
        "        self._pre.restore()\n"
    )
    assert _unguarded_calls(seeded, {"abort"}) == ["abort:self._pre.restore"]
