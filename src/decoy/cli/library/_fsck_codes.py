"""Every code `decoy library fsck` prints, with its level and the one repair it allows (plan 4.10).

The shape of `cli/io/_layout_errors.py`: one descriptor per code, and the walk and the repair
take their levels and dispatch from here, so a new code is one line here and nowhere else holds
a code as a literal (`tests/unit/library/test_fsck_codes.py`). `mode_open` has two descriptors:
a finding for the private folders, a note for records and refs that git checks out 0644.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from decoy.cli.library._errors import LIBRARY_LAYOUT_NEWER

__all__ = [
    "ACTIONS",
    "FINDINGS",
    "REPAIRS",
    "ActionCode",
    "FsckCode",
    "Level",
    "Repair",
    "descriptor",
]

Level = Literal["finding", "warning", "note"]
Repair = Literal["quarantine", "delete_temp", "remove_ref"]
REPAIRS: tuple[Repair, ...] = ("quarantine", "delete_temp", "remove_ref")


@dataclass(frozen=True)
class FsckCode:
    """One thing fsck reports. `repair` is what `--repair` may do about it (None: nothing);
    `blocks_repair` stops the whole walk and every repair."""

    code: str
    level: Level
    repair: Repair | None = None
    blocks_repair: bool = False


@dataclass(frozen=True)
class ActionCode:
    """One thing `--repair` printed it did, or could not do, to one entry."""

    code: str


LAYOUT_NEWER = FsckCode(LIBRARY_LAYOUT_NEWER, "finding", blocks_repair=True)
LAYOUT_UNREADABLE = FsckCode("layout_unreadable", "finding", blocks_repair=True)
PATH_LINKED = FsckCode("path_linked", "finding")
OBJECT_CORRUPT = FsckCode("object_corrupt", "finding", repair="quarantine")
OBJECT_NAME_INVALID = FsckCode("object_name_invalid", "finding", repair="quarantine")
OBJECT_UNREADABLE = FsckCode("object_unreadable", "finding")
PAYLOAD_INVALID = FsckCode("payload_invalid", "finding")
NEEDS_NEWER = FsckCode("needs_newer", "warning")
LINK_DANGLING = FsckCode("link_dangling", "warning")
REF_CORRUPT = FsckCode("ref_corrupt", "finding")
REF_DANGLING = FsckCode("ref_dangling", "finding", repair="remove_ref")
REF_UNREADABLE = FsckCode("ref_unreadable", "finding")
INDEX_MISSING = FsckCode("index_missing", "finding")
INDEX_NOT_FILE = FsckCode("index_not_file", "finding")
INDEX_CORRUPT = FsckCode("index_corrupt", "finding")
INDEX_STALE = FsckCode("index_stale", "finding")
TEMP_STALE = FsckCode("temp_stale", "finding", repair="delete_temp")
MODE_OPEN = FsckCode("mode_open", "finding")
MODE_OPEN_ADVISORY = FsckCode("mode_open", "note")
LOG_HEADER_INVALID = FsckCode("log_header_invalid", "finding")
LOG_BAD_LINE = FsckCode("log_bad_line", "finding")
LOG_TRUNCATED = FsckCode("log_truncated", "warning")
LOG_UNREADABLE = FsckCode("log_unreadable", "finding")

FINDINGS: tuple[FsckCode, ...] = (
    LAYOUT_NEWER,
    LAYOUT_UNREADABLE,
    PATH_LINKED,
    OBJECT_CORRUPT,
    OBJECT_NAME_INVALID,
    OBJECT_UNREADABLE,
    PAYLOAD_INVALID,
    NEEDS_NEWER,
    LINK_DANGLING,
    REF_CORRUPT,
    REF_DANGLING,
    REF_UNREADABLE,
    INDEX_MISSING,
    INDEX_NOT_FILE,
    INDEX_CORRUPT,
    INDEX_STALE,
    TEMP_STALE,
    MODE_OPEN,
    MODE_OPEN_ADVISORY,
    LOG_HEADER_INVALID,
    LOG_BAD_LINE,
    LOG_TRUNCATED,
    LOG_UNREADABLE,
)

OBJECT_QUARANTINED = ActionCode("object_quarantined")
QUARANTINE_FAILED = ActionCode("quarantine_failed")
TEMP_DELETED = ActionCode("temp_deleted")
TEMP_DELETE_FAILED = ActionCode("temp_delete_failed")
REF_REMOVED = ActionCode("ref_removed")
INDEX_REBUILT = ActionCode("index_rebuilt")

ACTIONS: tuple[ActionCode, ...] = (
    OBJECT_QUARANTINED,
    QUARANTINE_FAILED,
    TEMP_DELETED,
    TEMP_DELETE_FAILED,
    REF_REMOVED,
    INDEX_REBUILT,
)


_BY_KEY = {(d.code, d.level): d for d in FINDINGS}


class _Reported(Protocol):  # what `descriptor` needs from a finding, without `_fsck`
    @property
    def code(self) -> str: ...

    @property
    def level(self) -> Level: ...


def descriptor(finding: _Reported) -> FsckCode:
    """The descriptor a reported finding came from."""
    return _BY_KEY[(finding.code, finding.level)]
