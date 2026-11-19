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

import os

os.environ.pop("FORCE_COLOR", None)
os.environ["NO_COLOR"] = "1"
os.environ["TERM"] = "dumb"
# The root crash guard (`decoy.__main__._GuardedGroup`) turns an unexpected exception into a
# one-line "internal error" exit. Tests want the real traceback, so the guard re-raises under
# DECOY_DEBUG=1. The guard's own tests clear it to see the production default.
os.environ["DECOY_DEBUG"] = "1"

# The shared keyed-strategy secret fixture (`mask_secret`); see tests/keyed_secret.py.
# ---------------------------------------------------------------------------------------------
# Release-pin fixture (UPGRADE-KEY R2-H3). One fixture creates ephemeral Ed25519 keys K1, K2, K3
# and backup B, then patches the MODULE-LEVEL pin paths, never an environment variable, so a test
# keeps working after the real main and backup public keys are committed. Every rotation test
# uses it. The committed-statement path is patched once `decoy.distribution.key_rotation` exists
# (it lands after this fixture, in the next slice of the plan); until then there is nothing to patch.
import importlib.util
from dataclasses import dataclass
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tests.keyed_secret import mask_secret  # noqa: F401


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
