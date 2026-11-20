"""Render built tables to file bytes in each corpus format (plan 5.2).

Everything returns `{file name: bytes}` and writes nothing: `generate.py` publishes the bytes
through `scripts/qa/io.py`, the one QA writer. CSV and TSV use the standard library, Parquet uses
pyarrow, the DuckDB database uses duckdb (both are already product dependencies, so the corpus
adds none). The generator itself stays free of Faker.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from pathlib import Path

from scripts.qa.corpus.shapes import Table
from scripts.qa.io import private_scratch_dir

# format name: (delimiter, encoding, line terminator, embed newlines in text cells)
_DELIMITED: dict[str, tuple[str, str, str, bool]] = {
    "csv": (",", "utf-8", "\n", False),
    "csv-semicolon": (";", "utf-8", "\n", False),
    "csv-quoted-newlines": (",", "utf-8", "\n", True),
    "csv-bom": (",", "utf-8-sig", "\n", False),
    "csv-latin1": (",", "latin-1", "\n", False),
    "csv-utf16": (",", "utf-16", "\n", False),
    "csv-crlf": (",", "utf-8", "\r\n", False),
    "tsv": ("\t", "utf-8", "\n", False),
}
FORMATS = (*_DELIMITED, "parquet", "parquet-dict", "fixed-width", "duckdb")
_EXT = {"tsv": "tsv", "parquet": "parquet", "parquet-dict": "parquet", "fixed-width": "fwf"}


def _cell(value: object, kind: str, embed_newline: bool) -> str:
    if value is None:
        return ""
    if kind == "float":
        return f"{value:.2f}"
    text = str(value)
    if embed_newline and kind == "text":
        # The marker stays in the cell; the newline forces the reader to honour quoting.
        return text.replace(" ", "\n", 1)
    return text


def _strings(table: Table, embed_newline: bool = False) -> list[list[str]]:
    return [[_cell(v, c.kind, embed_newline) for v in c.values] for c in table.columns]


def delimited(table: Table, fmt: str) -> bytes:
    delim, encoding, eol, embed = _DELIMITED[fmt]
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, delimiter=delim, lineterminator=eol)
    writer.writerow([c.name for c in table.columns])
    writer.writerows(zip(*_strings(table, embed)))
    return buf.getvalue().encode(encoding)


def fixed_width(table: Table) -> tuple[bytes, bytes]:
    """Return the data bytes and the TOML layout file that says where each column sits."""
    cols = _strings(table)
    widths = [max([len(c.name), *map(len, vals)]) + 1 for c, vals in zip(table.columns, cols)]
    lines = ["".join(c.name.ljust(w) for c, w in zip(table.columns, widths))]
    for row in zip(*cols):
        lines.append("".join(v.ljust(w) for v, w in zip(row, widths)))
    layout = [f"# Fixed-width layout for the {table.name} table; the first line is the header."]
    start = 0
    for c, w in zip(table.columns, widths):
        layout.append(f'\n[[column]]\nname = "{c.name}"\nstart = {start}\nwidth = {w}')
        start += w
    return ("\n".join(lines) + "\n").encode("utf-8"), ("\n".join(layout) + "\n").encode("utf-8")


def _arrow(table: Table):  # type: ignore[no-untyped-def]
    import pyarrow as pa

    types = {"int": pa.int64(), "float": pa.float64(), "text": pa.string(), "date": pa.string()}
    return pa.table({c.name: pa.array(c.values, type=types[c.kind]) for c in table.columns})


def parquet(table: Table, dictionary: bool) -> bytes:
    import pyarrow.parquet as pq

    buf = io.BytesIO()
    # Uncompressed so the bytes do not depend on a codec build.
    pq.write_table(_arrow(table), buf, compression="NONE", use_dictionary=dictionary)
    return buf.getvalue()


def duckdb_file(tables: list[Table]) -> bytes:
    import duckdb

    with private_scratch_dir() as scratch:
        db = scratch / "corpus.duckdb"
        con = duckdb.connect(str(db))
        try:
            for t in tables:
                arrow = _arrow(t)  # noqa: F841  (duckdb reads the local name `arrow`)
                con.execute(f'CREATE TABLE "{t.name}" AS SELECT * FROM arrow')
        finally:
            con.close()
        return Path(db).read_bytes()


def render(tables: list[Table], fmt: str, item_id: str) -> dict[str, bytes]:
    """File name to bytes for one item. A multi-table item gets one file per table."""
    if fmt == "duckdb":
        return {f"{item_id}.duckdb": duckdb_file(tables)}
    files: dict[str, bytes] = {}
    for t in tables:
        if fmt in _DELIMITED:
            files[f"{t.name}.{_EXT.get(fmt, 'csv')}"] = delimited(t, fmt)
        elif fmt.startswith("parquet"):
            files[f"{t.name}.parquet"] = parquet(t, fmt == "parquet-dict")
        elif fmt == "fixed-width":
            data, layout = fixed_width(t)
            files[f"{t.name}.fwf"] = data
            files[f"{t.name}.layout.toml"] = layout
        else:
            raise ValueError(f"unknown format {fmt!r}")
    return files


def _damage_delimited(data: bytes, delim: bytes) -> bytes:
    head = b"\n".join(data.split(b"\n")[:20])
    return head + b"\n1" + delim + b'"never closed\n2' + delim + b"3\n"


def _damage_fixed(data: bytes, _delim: bytes) -> bytes:
    lines = data.split(b"\n")
    return b"\n".join(ln[: len(ln) // 2] if i % 3 == 2 else ln for i, ln in enumerate(lines))


_DAMAGE: dict[str, Callable[[bytes, bytes], bytes]] = {
    "csv": _damage_delimited,
    "tsv": _damage_delimited,
    "parquet": lambda d, _x: d[: len(d) * 6 // 10],
    "fixed-width": _damage_fixed,
    "duckdb": lambda d, _x: b"\x00" * 64 + b"not a database",
}


def malform(name: str, data: bytes, fmt: str) -> bytes:
    """Break one file the way a real bad file breaks: ragged rows, a cut, a wrong header."""
    if name.endswith(".layout.toml"):
        return data
    family = "csv" if fmt.startswith("csv") else "parquet" if fmt.startswith("parquet") else fmt
    return _DAMAGE[family](data, b"\t" if fmt == "tsv" else b",")
