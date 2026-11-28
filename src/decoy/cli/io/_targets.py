"""Write every table the CLI produces, by the format its target declares.

A target is written by its declared `format`, never inferred from the path. The one
exception is a vault-reversal output (`decoy unmask -o`, `decoy detokenize -o`), which
has no declaration and takes its format from the suffix through `format_for_path`.
A declared format that contradicts the path suffix is refused before any source is read.

This module holds every CLI table write, whole (`write_table`) and chunked
(`write_chunked_output`), so one sentry can keep it that way. It also decides which format a
CLI-written file is read back in (`input_format`, `entry_format`); the read calls themselves
stay in `cli/_sources.py`.

Source patterns: `cli/_sources.py` for the shape, and the platform's
`api/jobs/fixed_width_output.py` for the fixed-width frame conversion.
"""

from __future__ import annotations

import contextlib
import itertools
import math
import numbers
import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv

from decoy._atomic import (
    ATOMIC_SYNC_FAILED,
    AtomicWriteError,
    staged_local_target,
    staged_private_target,
)
from decoy.cli._sources import resolve_path
from decoy.cli.io._compression import (
    PRIVATE_MEMBER_MODE,
    PUBLIC_MEMBER_MODE,
    is_archive_csv,
    open_csv_sink,
    split_compression,
)
from decoy.cli.io._layout import RunLayout, owning_run, placed_path, same_path

if TYPE_CHECKING:
    import pandas as pd

SUFFIX_MISMATCH = "target_format_suffix_mismatch"
STREAMING_UNSUPPORTED = "target_format_streaming_unsupported"
FORMAT_UNKNOWN = "target_format_unknown"
UNREADABLE = "target_format_unreadable"
UNRECORDED = "target_format_unrecorded"
CSV_UNSUPPORTED_TYPE = "target.csv_unsupported_type"
CSV_SCHEMA_DRIFT = "target.csv_schema_drift"

# The supported target formats and the file suffix a sample gives each: the one registry.
TARGET_SUFFIX = {"csv": ".csv", "parquet": ".parquet", "fixed_width": ".txt"}
_SUFFIX_FORMAT = {".csv": "csv", ".parquet": "parquet", ".pq": "parquet"}
# The most rows one `CSVWriter.write_batch` call gets, so write-phase memory does not grow with
# the table or the chunk.
_CSV_WRITE_BATCH_ROWS = 65_536
_CSV_WRITE_OPTIONS = pacsv.WriteOptions(include_header=True, delimiter=",", quoting_style="needed")
# The same, for every chunk after the first of one chunked file: its header is already written.
_CSV_BODY_OPTIONS = pacsv.WriteOptions(include_header=False, delimiter=",", quoting_style="needed")
_EXHAUSTED = object()  # a yielded chunk is never mistaken for the end
_INT64_MIN, _INT64_MAX = -(2**63), 2**63 - 1
_CANONICAL_INT = re.compile(r"0|-?[1-9][0-9]*")
_STREAMING_REFUSAL = (
    "--chunked cannot write a fixed_width target or a CSV inside a zip or tar archive; "
    "run without --chunked"
)


class TargetFormatError(ValueError):
    """A target the CLI refuses to write. The message never holds a path or a value."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TargetFormatIssue:
    """The non-raising form of `TargetFormatError`, for the config gate."""

    table: str
    code: str
    message: str


def _uncompressed_only_message(label: str, fmt: str, path: Path) -> str | None:
    """Message for a Parquet or fixed-width file under a compression suffix, else None.

    Those writers never compress, so a `.gz` name would hold an uncompressed file.
    """
    if fmt == "csv":
        return None
    name = path.name.lower()
    stem, method = split_compression(path)
    if method is None:
        return None
    return (
        f"{label}: declared format '{fmt}' cannot be written under the compression "
        f"suffix '{name[len(stem) :]}'; rename the file or change the format"
    )


def check_output_path(path: Path) -> None:
    """Refuse a vault-reversal output (`-o`) whose suffix the writer cannot honour."""
    message = _uncompressed_only_message("output", format_for_path(path), path)
    if message is not None:
        raise TargetFormatError(SUFFIX_MISMATCH, message)


def is_target_format(fmt: object) -> bool:
    """True when `fmt` is a format the CLI writes: csv, parquet or fixed_width."""
    return isinstance(fmt, str) and fmt in TARGET_SUFFIX


def declared_format(entry: object) -> str | None:
    """The supported format a target entry declares, else None. Reads nothing else."""
    fmt = entry.get("format") if isinstance(entry, Mapping) else None
    return fmt if is_target_format(fmt) else None


def sample_target_format(table: str, entry: object) -> str:
    """The format a sample writes for one declared target.

    A file target keeps its declared format. A database or cloud target becomes Parquet.
    A file target with an unsupported format raises `TargetFormatError` (`FORMAT_UNKNOWN`),
    as the gate does.
    """
    declared = entry if isinstance(entry, Mapping) else {}
    if declared.get("type", "file") != "file":
        return "parquet"
    fmt = declared_format(declared)
    if fmt is None:
        raise TargetFormatError(
            FORMAT_UNKNOWN,
            f"targets.{table}: unsupported target format; expected csv, parquet or fixed_width",
        )
    return fmt


def _format_suffix(path: Path) -> str:
    return Path(split_compression(path)[0]).suffix


def claimed_format(path: Path) -> str | None:
    """The format the suffix before any compression suffix claims: csv, parquet or None."""
    return _SUFFIX_FORMAT.get(_format_suffix(path))


def format_for_path(path: Path) -> str:
    """The format of a file with no declaration: parquet for `.parquet`/`.pq`, else csv."""
    return claimed_format(path) or "csv"


def _entry_issue(
    table: str, entry: Mapping[str, Any], *, chunked: bool
) -> TargetFormatIssue | None:
    fmt = entry.get("format")
    if not is_target_format(fmt):
        return TargetFormatIssue(
            table,
            FORMAT_UNKNOWN,
            f"targets.{table}: unsupported target format; expected csv, parquet or fixed_width",
        )
    path = Path(entry["path"])
    claimed = claimed_format(path)
    if claimed is not None and claimed != fmt:
        return TargetFormatIssue(
            table,
            SUFFIX_MISMATCH,
            f"targets.{table}: declared format '{fmt}' does not match the path suffix "
            f"'{_format_suffix(path)}'; rename the file or change the format",
        )
    message = _uncompressed_only_message(f"targets.{table}", fmt, path)
    if message is not None:
        return TargetFormatIssue(table, SUFFIX_MISMATCH, message)
    if chunked and (fmt == "fixed_width" or is_archive_csv(fmt, path)):
        return TargetFormatIssue(
            table,
            STREAMING_UNSUPPORTED,
            f"targets.{table}: --chunked cannot stream declared format '{fmt}' to this "
            "path (fixed_width, or CSV in a zip or tar archive); run without --chunked",
        )
    return None


def target_format_issues(config_dict: dict, *, chunked: bool) -> list[TargetFormatIssue]:
    """Every contradiction in the file targets, in sorted table order. Raises nothing.

    Cloud targets and entries without a path are skipped: `_require_local_io_endpoints`
    owns the first, and the writers skip the second.
    """
    targets = config_dict.get("targets") or {}
    if not isinstance(targets, dict):
        return []
    issues = []
    for name, entry in sorted(targets.items(), key=lambda item: str(item[0])):
        table = str(name)
        if not isinstance(entry, dict) or entry.get("type", "file") != "file":
            continue
        if not isinstance(entry.get("path"), str):
            continue
        issue = _entry_issue(table, entry, chunked=chunked)
        if issue is not None:
            issues.append(issue)
    return issues


def check_target_formats(config_dict: dict, *, chunked: bool) -> None:
    """Raise `TargetFormatError` for the first issue, before any table is read or written."""
    issues = target_format_issues(config_dict, chunked=chunked)
    if not issues:
        return
    first = issues[0]
    message = first.message
    if first.code == STREAMING_UNSUPPORTED:
        message = "; ".join(i.message for i in issues if i.code == STREAMING_UNSUPPORTED)
    raise TargetFormatError(first.code, message)


def resolve_target_format(table: str, entry: Mapping[str, Any]) -> str:
    """The declared format of one target to write, after the suffix contradiction check.

    The only function that reads a target's `format` for a write.
    """
    issue = _entry_issue(table, entry, chunked=False)
    if issue is not None:
        raise TargetFormatError(issue.code, issue.message)
    return str(entry["format"])


def _unreadable(fmt: object, layout: object) -> TargetFormatError | None:
    if not is_target_format(fmt):
        return TargetFormatError(UNREADABLE, "the file's format cannot be determined")
    if fmt == "fixed_width" and (not isinstance(layout, Mapping) or not layout):
        return TargetFormatError(UNREADABLE, "the file's format cannot be determined")
    return None


def _is_declared_target(
    path: Path, raw: str, base_dir: Path, pipeline: tuple[Path, str] | None
) -> bool:
    """True when `path` is the target declared as `raw`, at the old place or in a run folder."""
    if same_path(path, resolve_path(raw, base_dir)):
        return True
    if pipeline is None:
        return False
    run = owning_run(path, *pipeline)
    placed = placed_path(run, raw) if run is not None else None
    return placed is not None and same_path(path, placed)


def input_format(
    config_dict: Mapping[str, Any],
    table: str,
    path: Path,
    base_dir: Path,
    pipeline: tuple[Path, str] | None = None,
) -> tuple[str, Mapping[str, Any] | None]:
    """The format and layout to read a CLI-written file in, for `detokenize` and `unmask`.

    When `path` is the table's file target (both sides fully resolved), the target's declared
    format and layout apply, and an undeclared or unknown format is refused before any read.
    The target is the file at the old place (declared path against `base_dir`) or, when
    `pipeline` (project root, pipeline name) is given, the same declared path inside a run
    folder of that pipeline.
    Any other path has no declaration and takes the suffix rule.
    """
    targets = config_dict.get("targets")
    entry = targets.get(table) if isinstance(targets, Mapping) else None
    if (
        isinstance(entry, Mapping)
        and entry.get("type", "file") == "file"
        and isinstance(entry.get("path"), str)
        and _is_declared_target(path, entry["path"], base_dir, pipeline)
    ):
        layout = entry.get("layout")
        error = _unreadable(entry.get("format"), layout)
        if error is not None:
            raise error
        fmt = str(entry["format"])
        return fmt, layout if fmt == "fixed_width" else None
    return format_for_path(path), None


def entry_format(recorded: Mapping[str, Any]) -> tuple[str, Mapping[str, Any] | None]:
    """The format and layout to read one evidence-manifest output in.

    `recorded` holds the entry's `format` and `layout` keys, without its path. An entry with no
    `format` was written before format recording and is refused (`UNRECORDED`), as is an unknown
    format or fixed_width without a layout.
    """
    if "format" not in recorded:
        raise TargetFormatError(
            UNRECORDED,
            "the evidence manifest entry records no format (written before format recording); "
            "re-run the pipeline to write a new manifest",
        )
    layout = recorded.get("layout")
    error = _unreadable(recorded["format"], layout)
    if error is not None:
        raise error
    fmt = str(recorded["format"])
    return fmt, layout if fmt == "fixed_width" else None


def _coerce_canonical_int_strings(series: pd.Series) -> pd.Series | None:
    """Strings that are canonical int64 digits become Int64; anything else stays as is.

    A CSV source reads every cell as text. No value changes: a leading zero, `-0`, a
    sign, spaces, a trailing newline or an out-of-range number leaves the column alone,
    so the writer refuses it.
    """
    import pandas as pd

    present = series.dropna()
    for value in present:
        if not isinstance(value, str) or _CANONICAL_INT.fullmatch(value) is None:
            return None
        if not _INT64_MIN <= int(value) <= _INT64_MAX:
            return None
    return pd.Series(
        [pd.NA if pd.isna(v) else int(v) for v in series],
        index=series.index,
        dtype="Int64",
        name=series.name,
    )


def _is_integral_in_range(value: float) -> bool:
    return math.isfinite(value) and value == math.floor(value) and _INT64_MIN <= value <= _INT64_MAX


def _coerce_object_series(series: pd.Series) -> pd.Series | None:
    """Python ints and integral floats only; bool, Decimal and str stay untouched."""
    import numpy as np
    import pandas as pd

    for value in series.dropna():
        if isinstance(value, (bool, np.bool_)):
            return None
        if isinstance(value, numbers.Integral):
            if not _INT64_MIN <= int(value) <= _INT64_MAX:
                return None
        elif isinstance(value, float):
            if not _is_integral_in_range(value):
                return None
        else:
            return None
    return pd.Series(
        [pd.NA if pd.isna(v) else int(v) for v in series],
        index=series.index,
        dtype="Int64",
        name=series.name,
    )


def _coerce_int_columns(frame: pd.DataFrame, layout: Mapping[str, Any]) -> pd.DataFrame:
    """Coerce float and object columns the layout types `int` to Int64, losslessly.

    Ported from the platform's `coerce_int_columns`: a column is touched only when every
    non-null value is finite, integral and in int64 range. Anything else is left for the
    engine writer to refuse. Object columns of strings also take the CLI-only canonical
    digit rule, because a CSV source arrives as text.
    """
    import pandas as pd

    out = frame.copy()
    for column in layout.get("columns") or []:
        if not isinstance(column, Mapping) or column.get("type") != "int":
            continue
        name = column.get("name")
        if name not in out.columns:
            continue
        series = out[name]
        dtype = series.dtype
        coerced: pd.Series | None = None
        if pd.api.types.is_bool_dtype(dtype):
            continue
        if pd.api.types.is_float_dtype(dtype):
            present = series.dropna()
            if all(_is_integral_in_range(float(v)) for v in present):
                coerced = series.astype("Int64")
        elif pd.api.types.is_object_dtype(dtype):
            coerced = _coerce_object_series(series)
            if coerced is None:
                coerced = _coerce_canonical_int_strings(series)
        if coerced is not None:
            out[name] = coerced
    return out


def _csv_type_allowed(arrow_type: pa.DataType) -> bool:
    """True for an Arrow type the CSV writer has a frozen text form for (plan section 4).

    Named predicates only: a family check (`is_floating`) would admit float16, and a new Arrow type must be refused until it is added here with a row.
    """
    types = pa.types
    if types.is_dictionary(arrow_type):
        return types.is_string(arrow_type.value_type) or types.is_large_string(
            arrow_type.value_type
        )
    return bool(
        types.is_string(arrow_type)
        or types.is_large_string(arrow_type)
        or types.is_integer(arrow_type)
        or types.is_float32(arrow_type)
        or types.is_float64(arrow_type)
        or types.is_boolean(arrow_type)
        or types.is_date32(arrow_type)
        or types.is_date64(arrow_type)
        or types.is_timestamp(arrow_type)
        or types.is_decimal128(arrow_type)
        or types.is_decimal256(arrow_type)
        or types.is_null(arrow_type)
        or types.is_time32(arrow_type)
        or types.is_time64(arrow_type)
    )


def check_csv_types(
    table_name: str, schema: pa.Schema, *, expected_schema: pa.Schema | None = None
) -> None:
    """Refuse an Arrow schema a CSV target cannot write, and a chunk whose columns changed.

    The one rule for every Arrow CSV write: each column type must be in the allowlist. CSV
    carries no types, so a column may change type between chunks (the engine's adapter makes a
    nullable int64 chunk float64 and reports an all-null chunk as `null`). When
    `expected_schema` is given (the first chunk's schema) only the column names and their order
    must equal it. Both refusals are `TargetFormatError` and name only the table, columns and
    Arrow type names, never a value. `write_chunked_output` calls this on every chunk, before
    the chunk reaches the writer.
    """
    for field in schema:
        if not _csv_type_allowed(field.type):
            raise TargetFormatError(
                CSV_UNSUPPORTED_TYPE,
                f"table {table_name!r} column {field.name!r} has Arrow type {field.type}, "
                "which a CSV target cannot write; write a Parquet target instead",
            )
    if expected_schema is not None and schema.names != expected_schema.names:
        raise TargetFormatError(
            CSV_SCHEMA_DRIFT,
            f"table {table_name!r} changed its columns between chunks: "
            f"{expected_schema.names} became {schema.names}",
        )


def _utc(arrow_type: pa.DataType) -> pa.DataType:
    """The type a zoned timestamp is written as: the same unit in UTC. Others are unchanged.

    Arrow writes a zoned timestamp as local wall clock plus offset. Recasting changes only the
    zone metadata, so the instant and the unit are kept, and the text is the UTC instant with a
    `Z` suffix whatever the source zone. Naive timestamps are left alone.
    """
    if pa.types.is_timestamp(arrow_type) and arrow_type.tz not in (None, "UTC"):
        return pa.timestamp(arrow_type.unit, tz="UTC")
    return arrow_type


def _is_text(arrow_type: pa.DataType) -> bool:
    return pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type)


def _csv_type(arrow_type: pa.DataType, single: bool) -> pa.DataType:
    """The type a CSV writer column has: zoned timestamps in UTC; in a one-column table, text.

    A CSV row with one empty field is a blank line, which readers skip, so a one-column table
    writes every null as `""` and needs a text column to hold that.
    """
    arrow_type = _utc(arrow_type)
    if not single or _is_text(arrow_type):
        return arrow_type
    if pa.types.is_dictionary(arrow_type):
        return arrow_type.value_type
    return pa.string()


def _csv_schema(schema: pa.Schema) -> pa.Schema:
    """The schema a CSV writer is built with for a table of `schema`."""
    single = len(schema) == 1
    return pa.schema([pa.field(f.name, _csv_type(f.type, single), f.nullable) for f in schema])


def _csv_column(column: pa.Array, field: pa.Field, single: bool) -> pa.Array:
    """`column` as the writer's `field`: dictionary decoded, zoned timestamps in UTC."""
    if column.type != field.type:
        if pa.types.is_dictionary(column.type):
            column = column.dictionary_decode()
        # Text of a zoned timestamp must be the UTC one, so recast the zone before the text cast.
        column = column.cast(_utc(column.type))
        column = column.cast(field.type) if column.type != field.type else column
    return pc.fill_null(column, pa.scalar("", field.type)) if single else column


def _csv_batch(batch: pa.RecordBatch) -> pa.RecordBatch:
    """`batch` converted to the writer's schema (`_csv_schema`)."""
    single = batch.num_columns == 1
    target = _csv_schema(batch.schema)
    columns = [
        _csv_column(column, field, single)
        for column, field in zip(batch.columns, target, strict=True)
    ]
    return pa.RecordBatch.from_arrays(columns, schema=target)


def _write_csv(table: pa.Table, writer: pacsv.CSVWriter) -> None:
    """Feed `table` to `writer` in batches of at most `_CSV_WRITE_BATCH_ROWS` rows.

    The writer must have been built with `_csv_schema` of the table's schema.
    """
    for batch in table.to_batches(max_chunksize=_CSV_WRITE_BATCH_ROWS):
        writer.write_batch(_csv_batch(batch))


def _preflight_csv_targets(config_dict: dict, outputs: Mapping[str, pa.Table]) -> None:
    """Refuse an unsupported CSV column type in any resident target before any is written."""
    for table_name, entry, _raw_path, table in _file_targets(config_dict, outputs):
        if isinstance(table, pa.Table) and resolve_target_format(str(table_name), entry) == "csv":
            check_csv_types(str(table_name), table.schema)


def _write_fixed_width(table: pa.Table, layout: Mapping[str, Any] | None, path: Path) -> None:
    from decoy_engine import write_fixed_width

    if layout is None:
        raise TargetFormatError(FORMAT_UNKNOWN, "a fixed_width target needs a layout")
    frame = _coerce_int_columns(table.to_pandas(), layout)
    write_fixed_width(frame, dict(layout), path)


@dataclass(frozen=True)
class _TargetPrivacy:
    """The stager and archive member mode of one whole-table writer, kept as a single fact."""

    stage: Callable[[Path], AbstractContextManager[Path]]
    member_mode: int


PUBLIC_TARGET = _TargetPrivacy(staged_local_target, PUBLIC_MEMBER_MODE)
PRIVATE_TARGET = _TargetPrivacy(staged_private_target, PRIVATE_MEMBER_MODE)


def _write_table(
    data: pa.Table | pd.DataFrame,
    fmt: str,
    path: Path,
    layout: Mapping[str, Any] | None,
    target: _TargetPrivacy,
) -> None:
    import pandas as pd
    import pyarrow.parquet as pq
    from decoy_engine import output_table

    message = _uncompressed_only_message("output", fmt, path)
    if message is not None:
        raise TargetFormatError(SUFFIX_MISMATCH, message)
    frame = isinstance(data, pd.DataFrame)
    if fmt == "fixed_width":
        if frame:
            raise TypeError("write_table: fixed_width needs a pyarrow Table")
        _write_fixed_width(data, layout, path)
        return
    if fmt not in ("csv", "parquet"):
        raise TargetFormatError(FORMAT_UNKNOWN, "unsupported target format")
    if fmt == "csv" and not isinstance(data, pd.DataFrame):
        check_csv_types("output", data.schema)
    with target.stage(path) as tmp:
        if isinstance(data, pd.DataFrame) and fmt == "csv":
            with open_csv_sink(tmp, path, member_mode=target.member_mode) as sink:
                data.to_csv(sink, index=False)
        elif fmt == "csv":
            with (
                open_csv_sink(tmp, path, member_mode=target.member_mode) as sink,
                pacsv.CSVWriter(
                    sink, _csv_schema(data.schema), write_options=_CSV_WRITE_OPTIONS
                ) as writer,
            ):
                _write_csv(data, writer)
        else:
            # One rule for every Parquet target: only the engine's allow-listed metadata is
            # written, never the source's. A DataFrame goes through Arrow first so pandas does
            # not write its own `attrs` key.
            table = pa.Table.from_pandas(data, preserve_index=False) if frame else data
            pq.write_table(output_table(table), str(tmp))


def write_table(
    data: pa.Table | pd.DataFrame,
    fmt: str,
    path: Path,
    layout: Mapping[str, Any] | None = None,
) -> None:
    """Write one whole table. The only whole-table writer in the CLI.

    CSV and Parquet are staged beside `path` and published only when the write finishes, so a
    failure keeps the old file. An existing file keeps its mode bits. Fixed width goes straight
    to the engine writer, which stages and publishes by itself.
    """
    _write_table(data, fmt, path, layout, PUBLIC_TARGET)


def write_private_table(
    data: pa.Table | pd.DataFrame,
    fmt: str,
    path: Path,
    layout: Mapping[str, Any] | None = None,
) -> None:
    """`write_table` for restored original values (`unmask`, `detokenize`): owner-only (0600).

    Fixed width is refused: the engine writer stages by itself and would not apply 0600.
    """
    if fmt == "fixed_width":
        raise TargetFormatError(FORMAT_UNKNOWN, "a private output cannot be fixed_width")
    _write_table(data, fmt, path, layout, PRIVATE_TARGET)


@contextlib.contextmanager
def _publication(ledger: dict[str, Path] | None, key: str, path: Path) -> Iterator[None]:
    """Enter `path` in the publication ledger once its write has published the file.

    The atomic writer replaces the file and then syncs the directory, so a write that fails
    with `ATOMIC_SYNC_FAILED` has already published (the code is raised only after the
    replace). Every other failure published nothing. This is the one place the ledger is
    filled by a table writer; `ledger` is None for a caller that keeps none.
    """
    try:
        yield
    except AtomicWriteError as exc:
        if exc.code == ATOMIC_SYNC_FAILED and ledger is not None:
            ledger[key] = path
        raise
    if ledger is not None:
        ledger[key] = path


def _file_targets(
    config_dict: dict, outputs: Mapping[str, pa.Table]
) -> Iterator[tuple[Any, dict, str, pa.Table]]:
    """Each declared file target that has an output: (name, entry, declared path, table)."""
    targets = config_dict.get("targets") or {}
    if not isinstance(targets, dict):
        return
    for table_name, entry in targets.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("type", "file") not in ("file", None):
            continue
        raw_path = entry.get("path")
        if not isinstance(raw_path, str):
            continue
        table = outputs.get(table_name)
        if table is not None:
            yield table_name, entry, raw_path, table


def write_targets(
    config_dict: dict,
    outputs: Mapping[str, pa.Table],
    layout: RunLayout,
    published: dict[str, Path] | None = None,
) -> dict[str, Path]:
    """Write each declared file target from `outputs`, by its declared format.

    Callers run `check_target_formats` first so a contradiction is refused before the
    first table is written; `layout` places each entry as it iterates. Returns table name to
    path for the files actually published: `_publication` adds a path once its file is in place.
    `published` is the caller's publication ledger; it is filled as each file is published, so
    a later failure keeps the earlier entries, and it is the mapping that comes back.
    """
    published = {} if published is None else published
    _preflight_csv_targets(config_dict, outputs)
    for table_name, entry, raw_path, table in _file_targets(config_dict, outputs):
        fmt = resolve_target_format(str(table_name), entry)
        path = layout.place_target(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _publication(published, str(table_name), path):
            write_table(table, fmt, path, entry.get("layout"))
    return published


@contextlib.contextmanager
def _staged_chunked(
    out_path: Path, ledger: dict[str, Path] | None, name: str, defer: contextlib.ExitStack | None
) -> Iterator[Path]:
    """The staged temp of one chunked target, published when `defer` (or this block) exits.

    Without `defer` the block's own exit publishes, as `staged_local_target` does. With `defer`
    the staged file and its ledger entry go onto the caller's stack and stay open past this
    block, so the caller publishes every target together, or none when it unwinds on an error.
    """
    with contextlib.ExitStack() as own:
        stack = own if defer is None else defer
        stack.enter_context(_publication(ledger, name, out_path))
        yield stack.enter_context(staged_local_target(out_path))


def write_chunked_output(
    masked_iter: Iterable[pa.Table],
    fmt: str,
    raw_path: str,
    layout: RunLayout,
    *,
    empty_schema: Callable[[], pa.Schema] | None,
    ledger: dict[str, Path] | None = None,
    name: str = "",
    defer: contextlib.ExitStack | None = None,
) -> Path | None:
    """Stream masked chunks to the placed `raw_path` in `fmt`. The only chunked writer in the CLI.

    `layout` places the declared path (a run folder for a relative one).

    The chunks go to a staged temp beside `out_path`, published only after the last one, so
    a failure after chunk one keeps the old output. The first chunk is read before staging:
    an empty source that writes nothing leaves the old output alone and makes no temp.
    Returns `out_path` once the file is published, or None when nothing was published.
    `ledger` (the caller's publication ledger) gets `out_path` under `name` as the file is
    published, including a publication that then failed at the directory sync.

    With `defer` (an `ExitStack` the caller owns) the staged file is written but not published:
    publication happens when the caller's stack exits cleanly, and an error anywhere before that
    discards every staged file on the stack. The caller stages all its targets this way, so no
    target is published when any chunk of any target fails. The returned path is then the one
    that stack will publish.
    """
    import pyarrow.parquet as pq
    from decoy_engine import output_schema, output_table

    out_path = layout.place_target(raw_path)
    if fmt not in ("csv", "parquet") or is_archive_csv(fmt, out_path):
        raise TargetFormatError(STREAMING_UNSUPPORTED, _STREAMING_REFUSAL)
    chunks = iter(masked_iter)
    first = next(chunks, _EXHAUSTED)
    schema = None
    if first is _EXHAUSTED:
        if fmt == "csv" or empty_schema is None:
            return None
        # Empty parquet source: emit a valid zero-row file with the source schema, matching
        # what a plain run writes. Read before staging so a schema error leaves no temp.
        schema = empty_schema()
    elif fmt == "parquet":
        schema = cast("pa.Table", first).schema
    else:
        check_csv_types(name or "output", cast("pa.Table", first).schema)
    if schema is not None:
        schema = output_schema(schema)
    with _staged_chunked(out_path, ledger, name, defer) as tmp:
        if fmt == "parquet":
            with pq.ParquetWriter(str(tmp), schema) as writer:
                for masked in () if first is _EXHAUSTED else itertools.chain((first,), chunks):
                    writer.write_table(output_table(masked))
        else:
            first_schema = cast("pa.Table", first).schema
            with open_csv_sink(tmp, out_path, member_mode=PUBLIC_MEMBER_MODE) as sink:
                # One sink and one header. Each chunk gets a writer on its own types, because
                # CSV carries none and the adapter may change a column's type between chunks.
                for index, masked in enumerate(itertools.chain((first,), chunks)):
                    check_csv_types(name or "output", masked.schema, expected_schema=first_schema)
                    options = _CSV_WRITE_OPTIONS if index == 0 else _CSV_BODY_OPTIONS
                    with pacsv.CSVWriter(
                        sink, _csv_schema(masked.schema), write_options=options
                    ) as writer:
                        _write_csv(masked, writer)
    # Reached only after the staging context published the file (or, with `defer`, is staged).
    return out_path


def table_records(
    rows: Mapping[str, int | None], paths: Mapping[str, Path | None]
) -> list[dict[str, Any]]:
    """One `{name, rows, path}` record per table for the run summary.

    `rows` is None when the writer streamed and never counted; `path` is None when no file
    was published. Neither is ever inferred from the config.
    """
    return [
        {"name": name, "rows": count, "path": str(path) if path is not None else None}
        for name, count in rows.items()
        for path in (paths.get(name),)
    ]
