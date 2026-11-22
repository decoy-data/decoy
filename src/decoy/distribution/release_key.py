"""The pinned release public key the shipped CLI trusts for `decoy upgrade`.

Single source of truth: ``release_key.pub.pem`` beside this module (committed +
shipped in the wheel). The release-publish step fills it with the real release key's
public half and injects the SAME key into `install.sh`'s inline pin; until then the
committed file holds the ``__DECOY_RELEASE_PUBLIC_KEY__`` placeholder, and this loader
treats a build that still carries the placeholder as "no key pinned" -- a hard refusal
for `decoy upgrade`, never a silent accept. Tests and the local smoke inject a real
ephemeral key via ``DECOY_RELEASE_PUBKEY_FILE`` rather than committing one whose
private half would have to live somewhere.

That override is a DEV/TEST seam only: it is honored solely while the committed key is
still the placeholder (a dev checkout), and warns loudly when used. Once a release build
has injected the real key, an environment variable must never be able to replace the
trust anchor, so the override is ignored (with a warning). Same rule in `install.sh`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from decoy._env_flags import env_str

PLACEHOLDER_MARKER = "__DECOY_RELEASE_PUBLIC_KEY__"
BACKUP_PLACEHOLDER_MARKER = "__DECOY_RELEASE_BACKUP_PUBLIC_KEY__"
_KEY_FILE = Path(__file__).resolve().parent / "release_key.pub.pem"
_BACKUP_KEY_FILE = Path(__file__).resolve().parent / "release_backup_key.pub.pem"


class NoPinnedKeyError(RuntimeError):
    """Raised when this build carries no real pinned release key (still the placeholder)
    and no override is set (``DECOY_RELEASE_PUBKEY_FILE``, or for the backup key
    ``DECOY_RELEASE_BACKUP_PUBKEY_FILE``)."""


def _warn(msg: str) -> None:
    sys.stderr.write(f"decoy: WARNING: {msg}\n")


@dataclass(frozen=True)
class _Pin:
    """One pinned trust anchor: its file, its placeholder marker, its dev override variable and
    the name used in messages. The only thing that differs between the main and the backup key."""

    key_file: Path
    marker: str
    env_name: str
    label: str


def _is_placeholder(key_file: Path, marker: str) -> bool:
    return marker in key_file.read_text(encoding="utf-8")


def _load_pin(pin: _Pin, *, dev_override_ok: bool = True) -> str:
    """The one loader behind every pinned key: file read, override handling, warnings, placeholder
    detection and refusal. A filled-in committed key always wins. The override is honored only
    while the pin is a placeholder (a dev checkout) AND ``dev_override_ok`` (the caller's extra
    condition), with a loud fixed warning; otherwise it is ignored with a fixed warning. A
    placeholder pin with no usable override raises NoPinnedKeyError, never a silent accept.
    Messages carry no path and no key text."""
    text = pin.key_file.read_text(encoding="utf-8")
    override = env_str(pin.env_name, "")
    placeholder = pin.marker in text
    if placeholder and dev_override_ok and override:
        _warn(
            f"trusting the {pin.label} key from {pin.env_name} instead of a pinned key. "
            "This is a dev/test build; never do this with a real install."
        )
        return Path(override).read_text(encoding="utf-8")
    if override:
        _warn(
            f"{pin.env_name} is set but IGNORED: this build pins its release keys "
            "and an environment variable cannot add or replace a trust anchor."
        )
    if placeholder:
        raise NoPinnedKeyError(
            f"this decoy build has no pinned {pin.label} key (placeholder present); "
            f"a release build commits it. Dev/test builds may set {pin.env_name}."
        )
    return text


def pinned_public_pem() -> str:
    """Return the pinned release public key PEM (``release_key.pub.pem``). The override
    ``DECOY_RELEASE_PUBKEY_FILE`` works only while this pin is a placeholder."""
    return _load_pin(_Pin(_KEY_FILE, PLACEHOLDER_MARKER, "DECOY_RELEASE_PUBKEY_FILE", "release"))


def pinned_backup_pem() -> str:
    """Return the pinned offline backup public key PEM (``release_backup_key.pub.pem``).

    Same loader, one stricter policy: ``DECOY_RELEASE_BACKUP_PUBKEY_FILE`` is honored only while
    BOTH the backup pin and the main pin are placeholders, so no environment variable can add a
    backup key to a build that pins a real main key. A placeholder backup pin with no usable
    override raises NoPinnedKeyError; that matters only when a rotation needs the backup key."""
    return _load_pin(
        _Pin(
            _BACKUP_KEY_FILE,
            BACKUP_PLACEHOLDER_MARKER,
            "DECOY_RELEASE_BACKUP_PUBKEY_FILE",
            "backup",
        ),
        dev_override_ok=_is_placeholder(_KEY_FILE, PLACEHOLDER_MARKER),
    )
