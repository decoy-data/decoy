"""Value-free replacement of source-read failures, and the out-of-memory test, for `decoy run`.

A pandas conversion error and a csv decode error quote the offending cell. The chunked run
passes every such failure through here so the text and the `--verbose` cause chain carry no
source value. `is_out_of_memory` lives here because the read boundary and the run error exit
need the same answer, and `decoy.cli.exit_codes` reads it lazily (it cannot import the run
package at module level).
"""

import lzma
import zlib
from collections.abc import Iterator
from typing import Any


def is_out_of_memory(exc: BaseException) -> bool:
    """True when `exc` is the host or Arrow running out of memory (the capacity exit).

    `ArrowMemoryError` is a `MemoryError`; `ArrowCapacityError` is not, so it is named.
    """
    import pyarrow as pa

    return isinstance(exc, (MemoryError, pa.ArrowCapacityError))


def _no_close() -> None:
    """The close of a stream that has none (a plain iterator)."""


_UNCONVERTIBLE_MESSAGE = (
    "a source value cannot be converted by the pandas route. The text names no column or value, "
    "because the library error quotes the cell. Drop --no-native, or fix the source value."
)
_UNREADABLE_MESSAGE = (
    "a source value cannot be read. The text names no column or value, because the library "
    "error quotes the cell. Fix the source value."
)


def _value_free_failure(exc: Exception, *, reading: bool = False) -> Exception | None:
    """A value-free replacement for a failure that can quote a source cell, or None.

    The pandas conversion error and the csv decode error quote the cell, and a coded engine
    error chains that error as its cause, which `--verbose` prints. All are replaced by a fresh
    error with no cause. Only conversion and parse errors qualify: an out-of-memory failure
    (`MemoryError`, `ArrowMemoryError`, `ArrowCapacityError`) returns None, so it reaches the
    capacity exit. `reading` is a failure of the source reader, which has a narrower set of
    types so that a usage error of the reader (an unknown format) is not renamed.
    """
    import pandas as pd
    import pyarrow as pa
    from decoy_engine import ExecutionError, reasons

    code = reasons.runtime.CHUNKED_PASSTHROUGH_VALUE_UNREPRESENTABLE
    if is_out_of_memory(exc):
        return None
    if isinstance(exc, ExecutionError):
        if exc.code != code:
            return None
        return ExecutionError(code=code, message=exc.message)
    if getattr(exc, "code", None) is not None:
        return None
    if reading:
        read_types: tuple[type[Exception], ...] = (
            UnicodeError,
            pd.errors.ParserError,
            pa.ArrowInvalid,
            pa.ArrowTypeError,
            pa.ArrowNotImplementedError,
            EOFError,
            zlib.error,
            lzma.LZMAError,
        )
        # A decoder failure (a corrupt gzip member or Snappy page) is an OSError with no errno
        # and its text can quote source bytes. A missing or unreadable file has an errno.
        decoder_oserror = isinstance(exc, OSError) and exc.errno is None
        if decoder_oserror or isinstance(exc, read_types):
            return ExecutionError(code=code, message=_UNREADABLE_MESSAGE)
        return None
    if isinstance(exc, (ValueError, ArithmeticError, pa.ArrowException)):
        return ExecutionError(code=code, message=_UNCONVERTIBLE_MESSAGE)
    return None


def _value_free(stream: Iterator[Any], *, reading: bool = False) -> Iterator[Any]:
    """The stream with its cell-quoting failures replaced by `_value_free_failure`.

    The replacement is raised after the `except` block, so it carries no `__cause__` or
    `__context__`. The inner stream is closed with this one.
    """
    inner = iter(stream)
    try:
        while True:
            failure: Exception | None = None
            try:
                chunk = next(inner)
            except StopIteration:
                return
            except Exception as exc:
                failure = _value_free_failure(exc, reading=reading)
                if failure is None:
                    raise
            else:
                yield chunk
                continue
            raise failure
    finally:
        getattr(inner, "close", _no_close)()
