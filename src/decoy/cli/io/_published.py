"""What a run records as published: one closed value type and the ledger that holds it.

The ledger is the only evidence that a file exists, so it takes `PublishedOutput` values and
nothing else. A bare `Path` (a staged slot path, a declared path) is refused, so a path that was
never delivered cannot reach `--json` `outputs`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocalOutput:
    """A file this run published in the local file system."""

    path: Path

    def __fspath__(self) -> str:
        return os.fspath(self.path)

    def __str__(self) -> str:
        return str(self.path)


PublishedOutput = LocalOutput  # the closed set of published kinds; cloud kinds join in 1.x


class Ledger(dict[str, PublishedOutput]):
    """Table name to what was published for it. Writes go through `__setitem__` only."""

    def __setitem__(self, key: str, value: PublishedOutput) -> None:
        if not isinstance(value, PublishedOutput):
            raise TypeError("the publication ledger holds PublishedOutput values only")
        super().__setitem__(key, value)

    def update(self, *args: object, **kwargs: object) -> None:  # type: ignore[override]
        raise TypeError("fill the publication ledger one entry at a time")

    def setdefault(self, key: str, default: PublishedOutput | None = None) -> PublishedOutput:  # type: ignore[override]
        raise TypeError("fill the publication ledger one entry at a time")


__all__ = ["Ledger", "LocalOutput", "PublishedOutput"]
