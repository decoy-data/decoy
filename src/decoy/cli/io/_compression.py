"""Compression by file name, for CSV targets the CLI writes.

pandas picks a CSV codec from the path's suffix. A staged write goes to a temp name that
ends in `.tmp`, so the codec has to be named from the real target instead. This module is
the one table of suffixes (the same set pandas infers, `.tgz` is not one of them), the one
place that builds the `compression=` option of the DataFrame writer, and the one place that
opens the byte stream an Arrow CSV writer writes into (`open_csv_sink`). It holds no table
write call.

Every stream codec is opened with fixed settings and no clock, file name or host field, so
the complete file bytes depend only on the CSV payload and the pinned library versions.

Source pattern: `pandas.io.common.extension_to_compression` for the suffix set, the
`compression` dict of `DataFrame.to_csv` (`method`, `archive_name`, `mode`), RFC 1952 for the
gzip header, and the stdlib `gzip`, `bz2`, `lzma`, `zipfile` and `tarfile` stream classes.
"""

from __future__ import annotations

import bz2
import contextlib
import gzip
import lzma
import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO, cast

# Longest suffix first, so `.tar.gz` is matched before `.gz`. Same set pandas infers.
COMPRESSION = (
    (".tar.bz2", "tar"),
    (".tar.gz", "tar"),
    (".tar.xz", "tar"),
    (".bz2", "bz2"),
    (".tar", "tar"),
    (".zip", "zip"),
    (".zst", "zstd"),
    (".gz", "gzip"),
    (".xz", "xz"),
)
ARCHIVES = ("zip", "tar")


def split_compression(path: Path) -> tuple[str, str | None]:
    """Return the file name without one recognised compression suffix, and its method."""
    name = path.name.lower()
    for suffix, method in COMPRESSION:
        if name.endswith(suffix):
            return name[: -len(suffix)], method
    return name, None


def is_archive_csv(fmt: str, path: Path) -> bool:
    return fmt == "csv" and split_compression(path)[1] in ARCHIVES


def csv_compression(path: Path) -> str | dict[str, str] | None:
    """The `to_csv(compression=...)` option the real target name implies, else None.

    A stream codec is a method string. An archive (zip, tar) also names its one member after
    the real file with the archive suffix cut (`out.csv.zip` holds `out.csv`), never after the
    staging name. A compressed tar says its tar mode, because pandas reads that from the
    written file's own suffix and the staging file has none.
    """
    name = path.name
    for suffix, method in COMPRESSION:
        if not name.lower().endswith(suffix):
            continue
        if method not in ARCHIVES:
            return method
        option = {"method": method, "archive_name": name[: -len(suffix)]}
        if method == "tar":
            option["mode"] = "w:" + suffix.rsplit(".", 1)[1] if suffix != ".tar" else "w"
        return option
    return None


def _archive_name(path: Path) -> str:
    """The member name inside an archive target: the real file name with the suffix cut."""
    name = path.name
    for suffix, method in COMPRESSION:
        if method in ARCHIVES and name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return name


def _stream_codec(stack: contextlib.ExitStack, method: str | None, raw: IO[bytes]) -> IO[bytes]:
    """`raw` wrapped in the frozen stream codec for `method`, closed with `stack`."""
    if method == "gzip":
        # `filename=""` and `mtime=0` leave FNAME and MTIME empty; level 6 gives XFL 0.
        return cast(
            "IO[bytes]",
            stack.enter_context(
                gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, filename="", mtime=0)
            ),
        )
    if method == "bz2":
        return cast("IO[bytes]", stack.enter_context(bz2.BZ2File(raw, "wb", compresslevel=9)))
    if method == "xz":
        return cast(
            "IO[bytes]",
            stack.enter_context(
                lzma.LZMAFile(raw, "wb", format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=6)
            ),
        )
    if method == "zstd":
        import pyarrow as pa

        return cast("IO[bytes]", stack.enter_context(pa.CompressedOutputStream(raw, "zstd")))
    return raw


def _tar_member(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = 0o644
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    return info


def _zip_member(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED  # level: zlib's default, which is 6
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


@contextlib.contextmanager
def open_csv_sink(tmp: Path, out_path: Path) -> Iterator[IO[bytes]]:
    """A writable byte stream into the staged `tmp` for the codec `out_path`'s suffix names.

    The caller writes the CSV bytes and leaves the block; the codec trailer, zip central
    directory or tar blocks are written on the way out. A tar archive needs the member size
    first, so its CSV goes to an anonymous spool file and the archive is built on exit.
    """
    method = split_compression(out_path)[1]
    with contextlib.ExitStack() as stack:
        raw = stack.enter_context(tmp.open("wb"))
        if method == "zip":
            archive = stack.enter_context(zipfile.ZipFile(raw, "w"))
            yield stack.enter_context(archive.open(_zip_member(_archive_name(out_path)), "w"))
        elif method == "tar":
            spool = stack.enter_context(tempfile.TemporaryFile(dir=tmp.parent))
            yield spool
            size = spool.seek(0, 2)
            spool.seek(0)
            outer = _suffix_codec(out_path)
            with contextlib.ExitStack() as inner:
                wrapped = _stream_codec(inner, outer, raw)
                with tarfile.open(fileobj=wrapped, mode="w", format=tarfile.USTAR_FORMAT) as tf:
                    tf.addfile(_tar_member(_archive_name(out_path), size), spool)
        else:
            yield _stream_codec(stack, method, raw)


def _suffix_codec(path: Path) -> str | None:
    """The outer stream codec of a tar suffix (`.tar.gz` gives gzip), else None."""
    name = path.name.lower()
    methods = dict(COMPRESSION)
    for suffix, method in COMPRESSION:
        if method == "tar" and name.endswith(suffix):
            return methods.get("." + suffix.rsplit(".", 1)[1]) if suffix != ".tar" else None
    return None
