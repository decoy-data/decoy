"""Check `--from` and copy it into a private directory that pip alone reads.

`--from` is a single `.whl` file or a directory holding only regular `.whl` files: no symlinks, no
sub-directories, no source distributions (they run code at install time). Each file is read
through the CLI's one no-follow reader (`read_small_file`: `lstat`, then the descriptor must be
the same regular file) and written into an owner-only directory, so a file added to or swapped in
the user's directory afterwards is never installed (pip's `--no-index --find-links` offline
pattern, run over the copy).
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from packaging.utils import InvalidWheelFilename, canonicalize_name, parse_wheel_filename

from decoy.cli.io import UnsafeFileError, read_small_file
from decoy.cli.models._errors import SOURCE_INVALID, ModelsError
from decoy.cli.models._private import make_private_dir, write_private

# Larger than any spaCy, model or numpy wheel; a bigger file is refused, not truncated.
_MAX_WHEEL_BYTES = 1 << 30


@dataclass(frozen=True)
class StagedSource:
    directory: Path  # the private copy
    model_version: str
    single: bool  # `--from` named one file, not a directory


def _invalid(why: str) -> ModelsError:
    return ModelsError(
        SOURCE_INVALID,
        f"--from must be a .whl file or a directory of regular .whl files: {why}.",
        hint="pass the model wheel, or a directory holding the ner closure wheels and the model wheel.",
    )


def _members(source: Path) -> tuple[list[Path], bool] | str:
    """The files to copy and whether `source` is one file, else why it is refused."""
    try:
        mode = os.lstat(source).st_mode
    except OSError:
        return "it does not exist or cannot be read"
    if stat.S_ISLNK(mode):
        return "symlinks are not followed"
    if stat.S_ISREG(mode):
        return ([source], True) if source.name.endswith(".whl") else "it is not a .whl file"
    if not stat.S_ISDIR(mode):
        return "it is not a regular file or directory"
    try:
        entries = sorted(os.scandir(source), key=lambda e: e.name)
    except OSError:
        return "the directory cannot be listed"
    for entry in entries:
        if not entry.is_file(follow_symlinks=False) or not entry.name.endswith(".whl"):
            return "the directory holds something other than regular .whl files"
    if not entries:
        return "the directory is empty"
    return [Path(e.path) for e in entries], False


def _copy(src: Path, dest: Path) -> bool:
    """Copy one plain regular file; False when it is not one, changed, or is too large."""
    try:
        found = read_small_file(src, _MAX_WHEEL_BYTES)
    except UnsafeFileError:
        return False
    if found is None or len(found.data) != found.size:
        return False
    write_private(dest, found.data)
    return True


def _model_version(name: str, model: str) -> str | None:
    try:
        dist, version, _, _ = parse_wheel_filename(name)
    except InvalidWheelFilename:
        return None
    return str(version) if dist == canonicalize_name(model) else None


def stage_source(source: Path, workdir: Path, model: str) -> StagedSource:
    """Check `source`, copy it into `workdir/wheels` (0700) and find the `model` wheel."""
    found = _members(source)
    if isinstance(found, str):
        raise _invalid(found)
    files, single = found
    target = make_private_dir(workdir / "wheels")
    for path in files:
        if not _copy(path, target / path.name):
            raise _invalid("a file changed or is not a regular file")
    versions = [v for v in (_model_version(p.name, model) for p in files) if v is not None]
    if len(versions) != 1:
        raise _invalid(f"it must hold exactly one {model} wheel")
    return StagedSource(target, versions[0], single)
