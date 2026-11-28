"""Shared pytest configuration for the decoy CLI test suite.

Force plain (non-ANSI) CLI output for the whole test session. Several e2e tests
assert plain option/help substrings (e.g. ``"--explain" in result.stdout``).
Rich emits ANSI color under a color-capable or CI terminal (``FORCE_COLOR``),
which interleaves escape codes into those strings and breaks the substring
match, so the tests pass locally (no color) but fail in CI (color). Neutralizing
color here makes the assertions terminal-agnostic (local == CI).

Set at import time, before pytest collects any test and before any Typer/Rich
Console is constructed: ``NO_COLOR`` alone does not win against ``FORCE_COLOR``
in Rich, so drop ``FORCE_COLOR`` and mark the terminal dumb as well.

It also sets ``DECOY_DEBUG=1`` so a crash in a command under test re-raises with its
traceback instead of becoming the guard's one-line exit.
"""

import atexit
import os
import re
import tempfile
from pathlib import Path

os.environ.pop("FORCE_COLOR", None)
os.environ["NO_COLOR"] = "1"
os.environ["TERM"] = "dumb"
# The root crash guard (`decoy.__main__._GuardedGroup`) turns an unexpected exception into a
# one-line "internal error" exit. Tests want the real traceback, so the guard re-raises under
# DECOY_DEBUG=1. The guard's own tests clear it to see the production default.
os.environ["DECOY_DEBUG"] = "1"

# ---------------------------------------------------------------------------------------------
# Release-pin fixture (UPGRADE-KEY R2-H3). One fixture creates ephemeral Ed25519 keys K1, K2, K3
# and backup B, then patches the MODULE-LEVEL pin paths, never an environment variable, so a test
# keeps working after the real main and backup public keys are committed. Every rotation test
# uses it. The committed-statement path is patched once `decoy.distribution.key_rotation` exists
# (it lands after this fixture, in the next slice of the plan); until then there is nothing to patch.
import importlib.util
from dataclasses import dataclass

import hypothesis.configuration
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from hypothesis import settings as hypothesis_settings
from hypothesis.database import DirectoryBasedExampleDatabase

# Registers the xdist-worker report scrubber (a lone surrogate in a captured log would otherwise
# abort a parallel run with an INTERNALERROR). Inert outside an xdist worker.
from tests._xdist_safe_reports import pytest_report_to_serializable  # noqa: F401

# The shared keyed-strategy secret fixture (`mask_secret`); see tests/keyed_secret.py.
from tests.keyed_secret import mask_secret  # noqa: F401


def _redirect_hypothesis_storage() -> "tempfile.TemporaryDirectory[str]":
    """Give this pytest process its own Hypothesis storage root, outside the checkout.

    Hypothesis keeps its example database and its constants cache under `.hypothesis/` in the
    current folder. A second worker, a nested pytest run or a test that lists the untracked files
    of the checkout would then meet files that appear and vanish between the listing and the
    read. Every process (the controller, each xdist worker, each nested child) allocates a fresh
    directory, under the gates temp root when there is one, and removes it when it exits. Runs
    before the first Hypothesis storage lookup: conftest import precedes collection.
    """
    parent = os.environ.get("PYTEST_DEBUG_TEMPROOT")
    if parent:
        Path(parent).mkdir(parents=True, exist_ok=True)
    who = re.sub(r"\W", "", os.environ.get("PYTEST_XDIST_WORKER", "main")) or "main"
    tmp = tempfile.TemporaryDirectory(prefix=f"decoy-hyp-{who}-", dir=parent or None)
    root = Path(tmp.name).resolve()
    os.environ["HYPOTHESIS_STORAGE_DIRECTORY"] = str(root)
    hypothesis.configuration.set_hypothesis_home_dir(root)
    # A test that passes its own `database=` still wins: the profile only sets the default.
    hypothesis_settings.register_profile(
        "decoy", database=DirectoryBasedExampleDatabase(root / "examples")
    )
    hypothesis_settings.load_profile("decoy")
    atexit.register(tmp.cleanup)  # an xdist worker can end without running pytest_unconfigure
    return tmp


_HYPOTHESIS_STORAGE = _redirect_hypothesis_storage()


def pytest_unconfigure(config: pytest.Config) -> None:
    _HYPOTHESIS_STORAGE.cleanup()


# Directories whose every test is `serial`. pytest ignores a `pytestmark` set in a conftest, so
# the mark is added to collected items below. Repo-relative, posix separators. The CLI has no such
# folder today; the hook stays so a later folder only adds its path here.
SERIAL_DIRS: tuple[str, ...] = ()

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _rel_posix(item: pytest.Item) -> str:
    try:
        return Path(str(item.path)).resolve().relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return Path(str(item.path)).as_posix()


def _in_dir(rel: str, directory: str) -> bool:
    return rel == directory or rel.startswith(directory + "/")


@pytest.hookimpl(tryfirst=True)  # before the `-m` deselection, which reads the serial mark
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark SERIAL_DIRS items `serial`, and refuse ids that differ between processes."""
    for item in items:
        rel = _rel_posix(item)
        if any(_in_dir(rel, d) for d in SERIAL_DIRS):
            item.add_marker(pytest.mark.serial)
    _refuse_unstable_ids(items)


# An object repr carries its memory address, which differs per process; xdist workers then
# collect different test ids and the parallel run aborts before running anything.
_UNSTABLE_ID = re.compile(r" at 0x[0-9a-fA-F]+>")  # how every default object repr ends


def _refuse_unstable_ids(items: list[pytest.Item]) -> None:
    bad = [item.nodeid for item in items if _UNSTABLE_ID.search(item.nodeid)]
    if bad:
        raise pytest.UsageError(
            "test ids must not contain a memory address; give these params an explicit id:\n"
            + "\n".join(bad)
        )


def public_pem(key: Ed25519PrivateKey) -> str:
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode("ascii")
    )


@dataclass(frozen=True)
class ReleasePins:
    k1: Ed25519PrivateKey
    k2: Ed25519PrivateKey
    k3: Ed25519PrivateKey
    b: Ed25519PrivateKey
    main_file: Path
    backup_file: Path
    statement_file: Path

    def pem(self, key: Ed25519PrivateKey) -> str:
        return public_pem(key)


@pytest.fixture
def release_pins(tmp_path, monkeypatch) -> ReleasePins:
    """Pin K1 as the main key and B as the backup key through the module-level paths."""
    from decoy.distribution import release_key

    keys = [Ed25519PrivateKey.generate() for _ in range(4)]
    k1, _k2, _k3, b = keys
    pins = tmp_path / "_pins"
    pins.mkdir()
    main_file, backup_file = pins / "release_key.pub.pem", pins / "release_backup_key.pub.pem"
    main_file.write_text(public_pem(k1), encoding="utf-8")
    backup_file.write_text(public_pem(b), encoding="utf-8")
    statement_file = pins / "key_rotation.json"
    for seam in ("DECOY_RELEASE_PUBKEY_FILE", "DECOY_RELEASE_BACKUP_PUBKEY_FILE"):
        monkeypatch.delenv(seam, raising=False)
    monkeypatch.setattr(release_key, "_KEY_FILE", main_file)
    monkeypatch.setattr(release_key, "_BACKUP_KEY_FILE", backup_file)
    if importlib.util.find_spec("decoy.distribution.key_rotation") is not None:
        from decoy.distribution import key_rotation

        monkeypatch.setattr(key_rotation, "_STATEMENT_FILE", statement_file)
    return ReleasePins(*keys, main_file, backup_file, statement_file)
