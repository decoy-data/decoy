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
from typing import Any, Protocol

from decoy._atomic import AtomicWriteError, WriteMode, write_atomic
from decoy.distribution import signing
from decoy.distribution.errors import InstallError

TRUST_STATE_FILE = "trust_state.json"
_UNREADABLE = "trust state unreadable"
_FINGERPRINT = re.compile(r"[0-9a-f]{64}")
_SERIAL_TOKEN = '"serial":'


class Decision(Protocol):
    """What a trust decision must expose for the writer: the main key PEM of its epoch (None
    for the pinned key), the epoch, and the cumulative revoked fingerprints."""

    @property
    def main_pem(self) -> str | None: ...
    @property
    def epoch(self) -> int: ...
    @property
    def revoked(self) -> frozenset[str]: ...


@dataclass(frozen=True)
class TrustState:
    serial: int = 0
    epoch: int = 1
    main_key: str | None = None
    revoked: frozenset[str] = frozenset()
    latest: Any = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _NoRotation:
    """The decision of an install that has seen no rotation: the pinned key, epoch 1, nothing revoked."""

    main_pem: str | None = None
    epoch: int = 1
    revoked: frozenset[str] = frozenset()


NO_ROTATION = _NoRotation()
_KNOWN = frozenset({"serial", "latest", "key_epoch", "main_key", "revoked_keys"})


def _unreadable() -> InstallError:
    return InstallError(f"refusing ({_UNREADABLE})")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse(data: object) -> TrustState:
    if not isinstance(data, dict):
        raise _unreadable()
    serial = data.get("serial")
    if not _is_int(serial) or serial < 0:
        raise _unreadable()
    epoch = data.get("key_epoch", 1)
    if not _is_int(epoch) or epoch < 1:
        raise _unreadable()
    raw_revoked = data.get("revoked_keys", [])
    if not isinstance(raw_revoked, list) or not all(
        isinstance(f, str) and _FINGERPRINT.fullmatch(f) for f in raw_revoked
    ):
        raise _unreadable()
    revoked = frozenset(raw_revoked)
    main_key = data.get("main_key") if epoch > 1 else None
    if epoch == 1 and revoked:
        raise _unreadable()
    if epoch > 1:
        try:
            if not isinstance(main_key, str) or signing.fingerprint(main_key) in revoked:
                raise _unreadable()
        except ValueError:
            raise _unreadable() from None
    extras = {k: v for k, v in data.items() if k not in _KNOWN}
    return TrustState(serial, epoch, main_key, revoked, data.get("latest"), extras)


def read_trust_state(home: Path) -> TrustState:
    """Absent state is a first run; a present but unreadable or invalid one is refused, never
    treated as "nothing seen", or corrupting the file would reset rollback protection."""
    try:
        raw = (home / TRUST_STATE_FILE).read_text(encoding="utf-8")
    except FileNotFoundError:
        return TrustState()
    except (OSError, ValueError):
        raise _unreadable() from None
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):
        raise _unreadable() from None
    return _parse(data)


def _first_serial_is_top_level(text: str) -> bool:
    """True when the first ``"serial":`` token in ``text`` sits at object depth 1, the way
    ``install.sh`` reads it. Walks the text once, skipping string contents."""
    depth, i, in_string = 0, 0, False
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 1
            elif ch == '"':
                in_string = False
        elif text.startswith(_SERIAL_TOKEN, i):
            return depth == 1
        elif ch == '"':
            in_string = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        i += 1
    return False


def _state_text(state: TrustState) -> str:
    out: dict[str, Any] = dict(state.extras)
    out.update({"latest": state.latest, "serial": state.serial, "key_epoch": state.epoch})
    out["revoked_keys"] = sorted(state.revoked)
    if state.epoch > 1:
        out["main_key"] = state.main_key
    text = json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n"
    if not _first_serial_is_top_level(text):
        raise InstallError("could not record the trust state -- refusing to continue")
    try:
        _parse(json.loads(text))  # never write a file this reader would refuse
    except InstallError:
        raise InstallError("could not record the trust state -- refusing to continue") from None
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
        raise InstallError(
            f"could not record the trust state ({exc.code}) -- refusing to continue"
        ) from None
