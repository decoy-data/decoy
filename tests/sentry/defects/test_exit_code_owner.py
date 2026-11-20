"""G-ONE-EXIT-MAP: an exception becomes an exit code in one place, `exit_code_for`.

`decoy.cli.exit_codes.exit_code_for` is the map. Three older copies still decide for themselves
until CL4 moves them: the `decoy run` classifier, `decoy demo`'s three-type map and `decoy fit`'s
differential-privacy arms. `ALLOWLIST` is exactly those three, read from the shrink-only baseline
`baselines/exit-code-owner.json`: the ratchet (`scripts/dev/ratchet_check.py`) rejects an added
key, this test requires every entry to match a real site, and CL4 empties it. Distinct from the
literal-exit-code sentry (`tests/unit/test_exit_codes.py`), which watches `typer.Exit(code=7)`.
The scan is `_exit_map_sites.py`.
"""

from __future__ import annotations

from typing import NamedTuple

from tests.sentry._ratchet import load_allowlist
from tests.sentry.defects import _exit_map_sites as sites


class Copy(NamedTuple):
    file: str
    function: str
    reason: str


ALLOWLIST: tuple[Copy, ...] = tuple(
    Copy(*key.split("::"), e["reason"]) for key, e in load_allowlist("exit-code-owner").items()
)


def _allowed() -> set[str]:
    return {f"{c.file}::{c.function}" for c in ALLOWLIST}


def test_the_allowlist_equals_the_source_inventory() -> None:
    live = sites.inventory()
    assert live - _allowed() == set(), "a new exception-to-exit map (call exit_code_for)"
    assert _allowed() - live == set(), "an entry no longer matches a real site (shrink it)"


def test_the_owner_exists_and_is_not_scanned() -> None:
    owner = (sites.SRC / sites.OWNER).read_text(encoding="utf-8")
    assert "def exit_code_for" in owner
    assert not any(k.startswith(f"{sites.OWNER}::") for k in sites.inventory())


# --- seeded spellings: each turns the scan red --------------------------------------------

_SEEDS = {
    "isinstance chain": (
        "def f(exc):\n"
        "    if isinstance(exc, ValueError):\n"
        "        return EXIT_USAGE\n"
        "    return EXIT_RUNTIME\n"
    ),
    "conditional": (
        "def f(exc):\n"
        "    return EXIT_USAGE if isinstance(exc, (KeyError, ValueError)) else EXIT_RUNTIME\n"
    ),
    "handler reads its exception": (
        "def f():\n"
        "    try:\n"
        "        g()\n"
        "    except OSError as caught:\n"
        "        code = EXIT_RUNTIME if caught.errno == 2 else EXIT_USAGE\n"
    ),
    "dict of types": "def f():\n    return {ValueError: EXIT_USAGE, OSError: EXIT_RUNTIME}\n",
    "dict of tuples": "def f():\n    return {(KeyError, ValueError): EXIT_USAGE}\n",
    "attribute names": (
        "import decoy.cli.exit_codes as ec\n"
        "def f(exc):\n"
        "    if isinstance(exc, ValueError):\n"
        "        return ec.EXIT_USAGE\n"
    ),
}


def test_each_seeded_spelling_is_seen() -> None:
    for name, source in _SEEDS.items():
        assert sites.sites_in_source(source, "x.py") == {"x.py::f"}, name


def test_a_method_is_keyed_by_its_qualified_name() -> None:
    source = (
        "class C:\n"
        "    def m(self, exc):\n"
        "        if isinstance(exc, ValueError):\n"
        "            return EXIT_USAGE\n"
    )
    assert sites.sites_in_source(source, "x.py") == {"x.py::C.m"}


def test_ordinary_exits_are_not_sites() -> None:
    source = (
        "def f(raw):\n"
        "    if not isinstance(raw, dict):\n"
        "        raise typer.Exit(code=EXIT_USAGE)\n"
        "    try:\n"
        "        g()\n"
        "    except OSError:\n"
        "        raise typer.Exit(code=EXIT_RUNTIME)\n"
        "    except ValueError:\n"
        "        raise typer.Exit(code=EXIT_USAGE)\n"
        "    return {'a': EXIT_USAGE}\n"
    )
    assert sites.sites_in_source(source, "x.py") == set()
