"""Readers for the CLI sentries whose allowlist is not the baseline JSON itself.

The registry (``scripts/dev/sentry_registry.toml``) gives each sentry a ``kind``. A ``json``
sentry reads its baseline through ``_ratchet.load_allowlist`` and needs nothing here. A
``from_scan`` or ``from_file`` sentry derives its keys from the source tree or a committed config
file, so ``READERS`` holds the one function that recomputes them for the registry test.
After the first inventory the ratchet (``scripts/dev/ratchet_check.py``) lets a baseline only
shrink.

Named limit: the ratchet sees ``file::symbol`` keys and the numeric ceilings ``max``, ``count``
and ``sites``; the sentry's exact-count check and review hold everything else.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[2]
SENTRY = ROOT / "tests" / "sentry"
REGISTRY = ROOT / "scripts" / "dev" / "sentry_registry.toml"
KINDS = frozenset({"json", "from_scan", "from_file"})
_LAYER_WHY = "back import measured when LAYOUT C3 declared the tiers; may only shrink"


def load_module(path: Path) -> Any:
    name = f"_bl_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses resolve string annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


@dataclass(frozen=True)
class FromFile:
    """Keys a sentry reads from a committed config file instead of a module constant.

    ``read`` maps the file's text to ``{key: reason}``.
    """

    path: str
    read: Callable[[str], dict[str, str]]

    def __call__(self) -> set[str]:
        return set(self.reasons())

    def reasons(self) -> dict[str, str]:
        return self.read((ROOT / self.path).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class FromScan:
    """Keys recomputed from the source tree by a scanner module's ``reasons()``.

    The scanner is the single definition of the inventory, so the baseline cannot drift from a
    second hand-kept list.
    """

    module: str

    def __call__(self) -> set[str]:
        return set(self.reasons())

    def reasons(self) -> dict[str, str]:
        mod = load_module(ROOT / self.module)
        return dict(mod.reasons())


def import_layer_reasons(text: str) -> dict[str, str]:
    """``layers::<importer> -> <imported>`` for each ignore line of ``.importlinter``.

    Layer membership is not keyed here: it is the exact snapshot in ``test_import_layers.py``.
    """
    layout = load_module(SENTRY / "layout" / "_layout.py")
    return {f"layers::{k}": _LAYER_WHY for k in layout.ignore_keys(text)}


def sink_row_reasons(text: str) -> dict[str, str]:
    """``{key: reason}`` of each ``file_sinks.toml`` row that carries an ``exit``."""
    return {
        f"{r['file']}::{r['function']}::{r['sink']}::{r['ordinal']}": r["reason"]
        for r in tomllib.loads(text).get("row", [])
        if r.get("exit")
    }


# Sentries whose keys are recomputed, by registry id. Every other sentry is kind ``json``.
READERS: dict[str, FromFile | FromScan] = {
    "one-error-emitter": FromScan("tests/sentry/cli_text/_error_sites.py"),
    "env-reads": FromScan("tests/sentry/io_policy/_env_read_sites.py"),
    "json-stdout-writes": FromScan("tests/sentry/cli_text/_stdout_sites.py"),
    "private-file-sinks": FromFile("tests/sentry/io_policy/file_sinks.toml", sink_row_reasons),
    "import-layers": FromFile(".importlinter", import_layer_reasons),
}

# Committed data files a sentry reads besides its baseline. The snapshot goes with C-G2.
DATA_FILES = frozenset(
    {
        "tests/sentry/io_policy/file_sinks.toml",
        "tests/sentry/allowlist-before.json",
        "tests/fixtures/release_freeze/json-shapes.json",
        # A grow-only list of tests that must carry the `serial` mark, not an allowlist (CLI-PAR S1).
        "tests/sentry/tooling/required_serial.toml",
    }
)

# Allowlist-shaped constants a sentry holds that are a closed contract, not a bypass list.
NOT_A_LIST_CONSTS: dict[tuple[str, str], str] = {
    ("tests/sentry/test_notify_redaction.py", "_ALLOWED_EVENT_FIELDS"): (
        "closed notification fact set, pinned by test_notify_redaction lane 1"
    ),
    ("tests/sentry/test_engine_import_surface.py", "_GUARD_EXCEPTIONS"): (
        "exception names the import guard recognises, not a bypass list"
    ),
}
