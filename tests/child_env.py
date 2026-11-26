"""The environment of a nested pytest or gates run, with the outer run's state removed.

An outer `-n` worker sets PYTEST_XDIST_* and every running test sets PYTEST_CURRENT_TEST. A child
that inherited them would think it is a worker (the xdist report scrubber hook) or loop on the id.
This is the one place that rule is written; `tests/sentry/test_nested_env_single_copy.py` fails
when another file spells it.
"""

from __future__ import annotations

import os


def child_env(
    base: dict[str, str] | None = None, drop_prefixes: tuple[str, ...] = ()
) -> dict[str, str]:
    """`base` (default: this process's environment) without the outer run state.

    `drop_prefixes` removes more, for a child that must start from a clean pytest and gates slate."""
    src = os.environ if base is None else base
    drop = ("PYTEST_XDIST_", *drop_prefixes)
    return {k: v for k, v in src.items() if not k.startswith(drop) and k != "PYTEST_CURRENT_TEST"}
