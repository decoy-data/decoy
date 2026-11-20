"""AT-1: the corpus generator is seeded and byte-deterministic, marks every text cell and joins
every foreign key. Planted cases prove the checks can fail."""

from __future__ import annotations

import csv
import datetime as dt
import io
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from scripts.qa.corpus import generate, shapes
from scripts.qa.corpus.manifest import Item, load_manifest

MANIFEST = Path(__file__).resolve().parents[3] / "docs/qa/corpus/manifest.toml"
ITEMS = [i for i in load_manifest(MANIFEST) if i.generated and i.tier == "S"]
BY_ID = {i.id: i for i in ITEMS}
SEED = 7


def marker_gaps(built: shapes.Built) -> list[str]:
    """`table.column[row]` for every non-null text cell without a marker."""
    return [
        f"{t.name}.{c.name}[{r}]"
        for t in built.tables
        for c in t.columns
        if c.kind == "text"
        for r, v in enumerate(c.values)
        if v is not None and shapes.MARKER not in v
    ]


def fk_orphans(built: shapes.Built) -> list[str]:
    """Child key tuples with no parent row; an all-null tuple is not an orphan."""
    by_name = {t.name: t for t in built.tables}
    orphans = []
    for fk in built.fks:
        parent, child = by_name[fk.parent], by_name[fk.child]
        keys = set(zip(*(parent.column(c).values for c in fk.parent_cols)))
        for row in zip(*(child.column(c).values for c in fk.child_cols)):
            if any(v is not None for v in row) and row not in keys:
                orphans.append(f"{fk.child}->{fk.parent}")
    return orphans


def duckdb_tables(data: bytes, path: Path) -> dict[str, list]:
    import duckdb

    path.write_bytes(data)
    con = duckdb.connect(str(path), read_only=True)
    try:
        names = sorted(r[0] for r in con.execute("SHOW TABLES").fetchall())
        return {n: con.execute(f'SELECT * FROM "{n}" ORDER BY ALL').fetchall() for n in names}
    finally:
        con.close()


def test_the_manifest_has_generated_items_in_every_tier() -> None:
    gen = [i for i in load_manifest(MANIFEST) if i.generated]
    assert {i.tier for i in gen} == {"S", "M", "L"}
    assert {i.shapes[0] for i in gen} == set(shapes.BUILDERS)
    assert {i.format for i in gen} == set(generate.formats.FORMATS)
    mods = {m for i in gen for m in i.shapes[1:]}
    assert mods == shapes.MODIFIERS


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i.id)
def test_same_seed_gives_identical_bytes(item: Item, tmp_path: Path) -> None:
    first, second = generate.render_item(item, SEED), generate.render_item(item, SEED)
    assert first.keys() == second.keys()
    # A DuckDB file has build-time identifiers in it: its tables repeat, its bytes do not.
    tables_only = item.format == "duckdb" and not {"empty_file", "malformed"} & set(item.shapes)
    if not tables_only:
        assert first == second
        return
    for name in first:
        one_db = duckdb_tables(first[name], tmp_path / "one.duckdb")
        assert one_db == duckdb_tables(second[name], tmp_path / "two.duckdb")


def test_a_different_seed_changes_the_data() -> None:
    item = BY_ID["single-csv-s"]
    assert generate.render_item(item, 1) != generate.render_item(item, 2)


def test_written_files_are_identical_and_a_rerun_is_a_no_op(tmp_path: Path) -> None:
    item = BY_ID["parent-child-csv-s"]
    a = generate.generate_item(item, tmp_path / "a", SEED)
    b = generate.generate_item(item, tmp_path / "b", SEED)
    assert [p.read_bytes() for p in a] == [p.read_bytes() for p in b]
    assert oct(a[0].stat().st_mode & 0o777) == "0o600"
    generate.generate_item(item, tmp_path / "a", SEED)  # same bytes: allowed
    with pytest.raises(generate.RegenerationDiffers):
        generate.generate_item(item, tmp_path / "a", SEED + 1)


def test_a_duckdb_rerun_compares_tables_and_refuses_a_mismatch(tmp_path: Path) -> None:
    item = BY_ID["parent-child-duckdb-s"]
    first = generate.generate_item(item, tmp_path, SEED)
    generate.generate_item(item, tmp_path, SEED)  # same tables, different bytes: allowed
    with pytest.raises(generate.RegenerationDiffers):
        generate.generate_item(item, tmp_path, SEED + 1)
    import duckdb

    con = duckdb.connect(str(first[0]))
    con.execute("DELETE FROM children WHERE id = 1")
    con.close()
    with pytest.raises(generate.RegenerationDiffers):
        generate.generate_item(item, tmp_path, SEED)
    first[0].write_bytes(b"not a database")
    with pytest.raises(generate.RegenerationDiffers):
        generate.generate_item(item, tmp_path, SEED)


def structured(item: Item) -> bool:
    return "empty_file" not in item.shapes


@pytest.mark.parametrize("item", [i for i in ITEMS if structured(i)], ids=lambda i: i.id)
def test_every_text_cell_holds_a_marker_and_the_manifest_lists_it(item: Item) -> None:
    built = generate.build_item(item, SEED)
    assert marker_gaps(built) == []
    listed = tuple(
        f"{t.name}.{c.name}" for t in built.tables for c in t.columns if c.kind == "text"
    )
    assert item.marker_columns == listed


@pytest.mark.parametrize("item", [i for i in ITEMS if structured(i)], ids=lambda i: i.id)
def test_every_foreign_key_joins(item: Item) -> None:
    assert fk_orphans(generate.build_item(item, SEED)) == []


def test_markers_are_unique_inside_an_item() -> None:
    built = generate.build_item(BY_ID["fk-chain3-csv-s"], SEED)
    cells = [v for t in built.tables for c in t.columns if c.kind == "text" for v in c.values]
    marks = [v.split()[0].split(".")[0] for v in cells]
    assert len(marks) == len(set(marks))


def test_a_cell_without_a_marker_is_caught() -> None:
    built = generate.build_item(BY_ID["single-csv-s"], SEED)
    built.tables[0].column("email").values[3] = "plain@example.invalid"
    assert marker_gaps(built) == ["people.email[3]"]


def test_an_orphan_child_is_caught() -> None:
    built = generate.build_item(BY_ID["parent-child-csv-s"], SEED)
    built.tables[1].column("parent_id").values[0] = 10**9
    assert fk_orphans(built) == ["children->parents"]


def test_a_broken_composite_tuple_is_caught() -> None:
    # Each half of the key exists in the parent; only the pair does not.
    built = generate.build_item(BY_ID["composite-key-csv-s"], SEED)
    sales = built.tables[1]
    parents = built.tables[0]
    sales.column("region").values[0] = parents.column("region").values[0]
    sales.column("store_no").values[0] = max(parents.column("store_no").values) + 1
    assert fk_orphans(built) == ["sales->stores"]


def test_largest_table_has_the_tier_row_count() -> None:
    for item in ITEMS:
        if not structured(item) or "header_only" in item.shapes or item.shapes[0] == "wide":
            continue
        built = generate.build_item(item, SEED)
        assert max(t.rows for t in built.tables) == shapes.TIER_ROWS["S"], item.id
    for item in ITEMS:
        if "header_only" in item.shapes:
            assert all(t.rows == 0 for t in generate.build_item(item, SEED).tables)


# Shapes -------------------------------------------------------------------------------------


def test_the_shapes_are_what_the_plan_lists() -> None:
    def table(shape: str) -> shapes.Table:
        return shapes.build(shape, 1000, 3).tables[0]

    assert len(table("wide").columns) == 200
    sparse = table("heavy_nulls")
    nulls = sum(v is None for v in sparse.column("a").values) / sparse.rows
    assert 0.85 < nulls < 0.95
    flat = table("null_constant")
    assert set(flat.column("all_null_text").values) == {None}
    assert len(set(flat.column("const_text").values)) == 1
    keys = table("dup_keys").column("id").values
    assert len(set(keys)) < len(keys)
    assert any(
        "@example.invalid" in v and " " in v for v in table("free_text").column("body").values
    )
    staff = table("self_ref")
    assert None in staff.column("manager_id").values
    cycle = shapes.build("fk_cycle", 200, 3)
    assert {(f.child, f.parent) for f in cycle.fks} == {
        ("departments", "employees"),
        ("employees", "departments"),
    }


def test_dates_come_in_five_formats_and_some_are_bad() -> None:
    events = shapes.build("dates", 700, 3).tables[0]
    formats = {
        "d_iso": "%Y-%m-%d",
        "d_dmy": "%d/%m/%Y",
        "d_mdy": "%m-%d-%Y",
        "d_long": "%d %b %Y",
        "d_compact": "%Y%m%d",
    }
    for name, fmt in formats.items():
        for v in events.column(name).values:
            dt.datetime.strptime(v, fmt)
    bad = 0
    for v in events.column("d_bad").values:
        try:
            dt.datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            bad += 1
    assert bad > 50


# Formats ------------------------------------------------------------------------------------


def one(item_id: str) -> dict[str, bytes]:
    return generate.render_item(BY_ID[item_id], SEED)


def test_csv_variants_have_their_marks() -> None:
    assert one("single-csv-bom-s")["people.csv"].startswith(b"\xef\xbb\xbf")
    assert one("single-csv-utf16-s")["people.csv"][:2] in {b"\xff\xfe", b"\xfe\xff"}
    latin = one("single-csv-latin1-s")["people.csv"]
    assert any(b >= 0x80 for b in latin) and latin.decode("latin-1")
    with pytest.raises(UnicodeDecodeError):
        latin.decode("utf-8")
    crlf = one("single-csv-crlf-s")["people.csv"]
    assert crlf.count(b"\r\n") == 1001
    semi = one("single-csv-semicolon-s")["people.csv"].decode()
    assert semi.splitlines()[0] == "id;name;email;note;age;balance;signup"
    assert one("single-tsv-s")["people.tsv"].decode().splitlines()[0].count("\t") == 6


def test_quoted_newlines_survive_a_csv_read() -> None:
    text = one("single-csv-quoted-newlines-s")["people.csv"].decode()
    rows = list(csv.reader(io.StringIO(text, newline="")))
    assert len(rows) == 1001
    assert all("\n" in r[1] and shapes.MARKER in r[1] for r in rows[1:])


def test_parquet_plain_and_dictionary_differ_in_encoding() -> None:
    def encodings(data: bytes) -> set[str]:
        meta = pq.ParquetFile(io.BytesIO(data)).metadata
        return {e for i in range(meta.num_columns) for e in meta.row_group(0).column(i).encodings}

    plain = encodings(one("single-parquet-s")["people.parquet"])
    dictionary = encodings(one("single-parquet-dict-s")["people.parquet"])
    assert not any("DICTIONARY" in e for e in plain)
    assert any("DICTIONARY" in e for e in dictionary)
    table = pq.read_table(io.BytesIO(one("single-parquet-s")["people.parquet"]))
    assert table.num_rows == 1000 and table.column_names[:2] == ["id", "name"]


def test_fixed_width_comes_with_a_layout_file() -> None:
    files = one("single-fixed-width-s")
    assert set(files) == {"people.fwf", "people.layout.toml"}
    lines = files["people.fwf"].decode().splitlines()
    layout = files["people.layout.toml"].decode()
    assert len(lines) == 1001 and len({len(ln) for ln in lines}) == 1
    assert 'name = "email"' in layout and "start = " in layout


def test_a_duckdb_item_holds_its_tables(tmp_path: Path) -> None:
    files = one("parent-child-duckdb-s")
    ((name, data),) = files.items()
    assert name == "parent-child-duckdb-s.duckdb"
    tables = duckdb_tables(data, tmp_path / "x.duckdb")
    assert {k: len(v) for k, v in tables.items()} == {"children": 1000, "parents": 100}


# Edge files ---------------------------------------------------------------------------------


def test_header_only_and_empty_files() -> None:
    assert (
        one("single-csv-header-only-s")["people.csv"] == b"id,name,email,note,age,balance,signup\n"
    )
    assert (
        pq.read_table(io.BytesIO(one("single-parquet-header-only-s")["people.parquet"])).num_rows
        == 0
    )
    assert one("single-csv-empty-file-s") == {"people.csv": b""}
    assert one("single-parquet-empty-file-s") == {"people.parquet": b""}


def test_malformed_files_do_not_parse(tmp_path: Path) -> None:
    rows = list(csv.reader(io.StringIO(one("single-csv-malformed-s")["people.csv"].decode())))
    assert len({len(r) for r in rows}) > 1 or rows[-1][0] != "2"
    import pyarrow

    with pytest.raises(pyarrow.ArrowInvalid):
        pq.read_table(io.BytesIO(one("single-parquet-malformed-s")["people.parquet"]))
    import duckdb

    bad = tmp_path / "bad.duckdb"
    bad.write_bytes(one("single-duckdb-malformed-s")["single-duckdb-malformed-s.duckdb"])
    with pytest.raises(duckdb.Error):
        duckdb.connect(str(bad), read_only=True)
    fixed = one("single-fixed-width-malformed-s")["people.fwf"].decode().splitlines()
    assert len({len(ln) for ln in fixed}) > 1
