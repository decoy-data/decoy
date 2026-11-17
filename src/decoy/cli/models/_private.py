"""Every file `decoy models install` writes: a private work folder and the files inside it.

The constraints file, the pinned-model requirements file and the `--from` wheel copies all go
through `write_private`, and both folders through `make_private_dir`, so each is created
owner-only by the CLI's one private-file module before any byte is written (G-ONE-PRIVATE-FILE).
"""

from __future__ import annotations

import secrets
import tempfile
from pathlib import Path

from decoy._private_file import create_private_directory, open_private


def make_private_dir(path: Path) -> Path:
    create_private_directory(path)
    return path


def private_workdir() -> Path:
    """A new 0700 folder in the system temp folder; the caller removes it."""
    return make_private_dir(Path(tempfile.gettempdir()) / f"decoy-models-{secrets.token_hex(8)}")


def write_private(path: Path, data: bytes) -> None:
    open_private(path, new_parent=False)
    path.write_bytes(data)
