"""The one reader and writer of ``<DECOY_HOME>/trust_state.json``.

The file records what this install has accepted from the update channel: the highest
``serial`` seen in the current key epoch, the ``latest`` version it carried, the key epoch,
the main key of that epoch (only once a rotation raised it above 1) and the revoked key
fingerprints. ``install.sh`` reads ``serial`` with a ``grep`` over the first ``"serial":``
token, so ``serial`` stays a top-level integer and no other field may nest one in front of it.

The file is local state, not a secret: an attacker who can write it can already replace the
runtime. Refusals here are value-free: no path, no file text, no exception text.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeGuard

from decoy._atomic import AtomicWriteError, WriteMode, write_atomic
from decoy.distribution import signing
from decoy.distribution.errors import InstallError

TRUST_STATE_FILE = "trust_state.json"
_UNREADABLE = "trust state unreadable"
_FINGERPRINT = re.compile(r"[0-9a-f]{64}")
# install.sh reads the serial with this pattern (`json_top_number`) and takes the first match.
_SHELL_SERIAL = re.compile(r'"serial"[ \t\r\n]*:[ \t\r\n]*[0-9]+')


@dataclass(frozen=True)
class Decision:
    """What the writer records from one trust decision: the main key PEM of its epoch (None for
    the pinned key), the epoch, and the cumulative revoked fingerprints. Any object with these
    three attributes works, so the resolver's richer decision type needs no conversion."""

    main_pem: str | None
    epoch: int
    revoked: frozenset[str]


NO_ROTATION = Decision(None, 1, frozenset())


@dataclass(frozen=True)
class TrustState:
    serial: int = 0
    epoch: int = 1
    main_key: str | None = None
    revoked: frozenset[str] = frozenset()
    latest: Any = None
    extras: dict[str, Any] = field(default_factory=dict)


_KNOWN = frozenset({"serial", "latest", "key_epoch", "main_key", "revoked_keys"})


def _unreadable() -> InstallError:
    return InstallError(f"refusing ({_UNREADABLE})")


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _fingerprint_or_none(pem: object) -> str | None:
    """The key's fingerprint, or None when ``pem`` is not a loadable Ed25519 public key."""
    if not isinstance(pem, str):
        return None
    try:
        return signing.fingerprint(pem)
    except ValueError:
        return None


def _valid(data: object) -> bool:
    """The state shape the reader accepts. Every refusal below is one fixed result."""
    if not isinstance(data, dict):
        return False
    serial, epoch = data.get("serial"), data.get("key_epoch", 1)
    if not _is_int(serial) or serial < 0 or not _is_int(epoch) or epoch < 1:
        return False
    revoked = data.get("revoked_keys", [])
    if not isinstance(revoked, list) or not all(
        isinstance(f, str) and _FINGERPRINT.fullmatch(f) for f in revoked
    ):
        return False
    if epoch == 1:
        return not revoked
    fp = _fingerprint_or_none(data.get("main_key"))
    return fp is not None and fp not in revoked


def _parse(data: object) -> TrustState | None:
    """The state, or None when ``data`` is not a valid state."""
    if not _valid(data) or not isinstance(data, dict):
        return None
    epoch = data.get("key_epoch", 1)
    extras = {k: v for k, v in data.items() if k not in _KNOWN}
    return TrustState(
        data["serial"],
        epoch,
        data["main_key"] if epoch > 1 else None,
        frozenset(data.get("revoked_keys", [])),
        data.get("latest"),
        extras,
    )


_ABSENT, _BAD = object(), object()


def _load_file(path: Path) -> object:
    """The parsed JSON, ``_ABSENT`` for a missing file, ``_BAD`` for anything unreadable."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _ABSENT
    except (OSError, ValueError):
        return _BAD
    try:
        return json.loads(raw)
    except (ValueError, RecursionError):
        return _BAD


def read_trust_state(home: Path) -> TrustState:
    """Absent state is a first run; a present but unreadable or invalid one is refused, never
    treated as "nothing seen", or corrupting the file would reset rollback protection."""
    data = _load_file(home / TRUST_STATE_FILE)
    if data is _ABSENT:
        return TrustState()
    state = None if data is _BAD else _parse(data)
    if state is None:
        raise _unreadable()
    return state


def _shell_reads_serial(text: str, serial: int) -> bool:
    """True when the first match of install.sh's serial pattern in ``text`` is ``serial``."""
    match = _SHELL_SERIAL.search(text)
    return match is not None and match.group().rsplit(":", 1)[1].strip() == str(serial)


def _state_text(state: TrustState) -> str:
    """Compact JSON with ``serial`` as the FIRST key, so the shell's first match is the real
    one whatever unknown fields are kept; every other key is sorted."""
    rest: dict[str, Any] = dict(state.extras)
    rest.update({"latest": state.latest, "key_epoch": state.epoch})
    rest["revoked_keys"] = sorted(state.revoked)
    if state.epoch > 1:
        rest["main_key"] = state.main_key
    body = json.dumps(rest, sort_keys=True, separators=(",", ":"))
    text = f'{{"serial":{state.serial},{body[1:]}\n'
    # Never write a file this reader would refuse, or one the shell would misread.
    if not _shell_reads_serial(text, state.serial) or _parse(json.loads(text)) is None:
        raise InstallError("could not record the trust state -- refusing to continue")
    return text


def _next_state(
    old: TrustState, decision: Decision, latest: object, document_serial: int | None
) -> TrustState:
    epoch = max(old.epoch, decision.epoch)
    raised = epoch > old.epoch
    if raised:
        serial = document_serial if document_serial is not None else 0
    else:
        serial = old.serial if document_serial is None else max(old.serial, document_serial)
    main_key = decision.main_pem if raised else old.main_key
    return TrustState(
        serial=serial,
        epoch=epoch,
        main_key=main_key if epoch > 1 else None,
        revoked=old.revoked | frozenset(decision.revoked),
        latest=old.latest if document_serial is None and latest is None else latest,
        extras=old.extras,
    )


def write_trust_state(
    home: Path, decision: Decision, *, latest: object, document_serial: int | None
) -> None:
    """Record one accepted decision atomically. The epoch only rises, the revoked set only grows
    (union), an epoch rise sets ``serial`` to the new document's serial (0 with no document) so
    the old epoch's floor never carries over, and unknown top-level fields are kept as read.
    Raises InstallError and writes nothing if the result would not read back safely."""
    new = _next_state(read_trust_state(home), decision, latest, document_serial)
    text = _state_text(new)
    home.mkdir(parents=True, exist_ok=True)
    try:
        write_atomic(home, TRUST_STATE_FILE, text.encode("utf-8"), WriteMode.REPLACE)
    except AtomicWriteError as exc:
        code = exc.code
    else:
        return
    raise InstallError(f"could not record the trust state ({code}) -- refusing to continue")
