"""The table shapes of the generated QA corpus (plan 5.2).

NumPy and the standard library only, never Faker: the product masks with Faker, and data made by
the same library could hide a defect that depends on Faker's own patterns.

Every text cell holds `qamark` plus a number that is unique to the cell where it was made. A
copied key cell (a composite foreign key) and a constant column repeat the marker of their source
on purpose, so I1 relies on the marker being present, not on every number being distinct.
Date columns are not text for this rule: they exist to hold odd and bad date strings. Each builder returns tables as
column lists plus the foreign keys that must join.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

TIER_ROWS = {"S": 1_000, "M": 100_000, "L": 1_000_000}
MARKER = "qamark"
# Display names are Latin-1 safe so the Latin-1 and UTF-16 variants carry real accents.
_FIRST = ("Ana", "José", "Zoë", "Søren", "Núria", "Åsa", "Renée", "Tomás", "Léa", "Björn")
_FIRST_ASCII = ("ana", "jose", "zoe", "soren", "nuria", "asa", "renee", "tomas", "lea", "bjorn")
_LAST = ("García", "Müller", "Ñandú", "O'Brien", "Dupont", "Ferrão", "Smith", "Östberg")
_LAST_ASCII = ("garcia", "muller", "nandu", "obrien", "dupont", "ferrao", "smith", "ostberg")
_BASE_DAY = np.datetime64("2015-01-01")


@dataclass
class Column:
    name: str
    kind: str  # "int", "float", "text" or "date"
    values: list


@dataclass
class Table:
    name: str
    columns: list[Column]

    @property
    def rows(self) -> int:
        return len(self.columns[0].values) if self.columns else 0

    def column(self, name: str) -> Column:
        return next(c for c in self.columns if c.name == name)


@dataclass(frozen=True)
class ForeignKey:
    child: str
    child_cols: tuple[str, ...]
    parent: str
    parent_cols: tuple[str, ...]


@dataclass
class Built:
    tables: list[Table]
    fks: list[ForeignKey] = field(default_factory=list)


class Markers:
    """Hands out unique `qamark<number>` tokens for one item."""

    def __init__(self) -> None:
        self._next = 0

    def take(self, n: int) -> list[str]:
        start = self._next
        self._next += n
        return [f"{MARKER}{i:09d}" for i in range(start, start + n)]


def seed_for(seed: int, item_id: str) -> int:
    digest = hashlib.sha256(f"{seed}:{item_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


class _Ctx:
    def __init__(self, seed: int) -> None:
        self.rng = np.random.default_rng(seed)
        self.mk = Markers()

    def pick(self, n: int, pool: int) -> list[int]:
        return self.rng.integers(0, pool, size=n).tolist()

    def names(self, n: int) -> list[str]:
        f, ln = self.pick(n, len(_FIRST)), self.pick(n, len(_LAST))
        return [f"{m} {_FIRST[a]} {_LAST[b]}" for m, a, b in zip(self.mk.take(n), f, ln)]

    def emails(self, n: int) -> list[str]:
        f, ln = self.pick(n, len(_FIRST)), self.pick(n, len(_LAST))
        marks = self.mk.take(n)
        return [
            f"{m}.{_FIRST_ASCII[a]}.{_LAST_ASCII[b]}@example.invalid"
            for m, a, b in zip(marks, f, ln)
        ]

    def notes(self, n: int) -> list[str]:
        words = ("shipped", "refunded", "pending", "escalated", "closed", "reopened")
        w = self.pick(n, len(words))
        qty = self.rng.integers(1, 50, size=n).tolist()
        return [f"{m} order {words[a]} qty {q}" for m, a, q in zip(self.mk.take(n), w, qty)]

    def ints(self, n: int, lo: int, hi: int) -> list[int]:
        return self.rng.integers(lo, hi, size=n).tolist()

    def floats(self, n: int) -> list[float]:
        return np.round(self.rng.normal(250.0, 90.0, size=n), 2).tolist()

    def days(self, n: int) -> np.ndarray:
        return _BASE_DAY + self.rng.integers(0, 3650, size=n).astype("timedelta64[D]")


def _iso(days: np.ndarray) -> list[str]:
    return np.datetime_as_string(days, unit="D").tolist()


def _col(name: str, kind: str, values: list) -> Column:
    return Column(name, kind, values)


def _ids(n: int) -> list[int]:
    return list(range(1, n + 1))


def _sparse(values: list, rng: np.random.Generator, keep: float) -> list:
    mask = rng.random(len(values)) < keep
    return [v if k else None for v, k in zip(values, mask.tolist())]


def single(c: _Ctx, rows: int) -> Built:
    t = Table(
        "people",
        [
            _col("id", "int", _ids(rows)),
            _col("name", "text", c.names(rows)),
            _col("email", "text", c.emails(rows)),
            _col("note", "text", c.notes(rows)),
            _col("age", "int", c.ints(rows, 18, 91)),
            _col("balance", "float", c.floats(rows)),
            _col("signup", "date", _iso(c.days(rows))),
        ],
    )
    return Built([t])


def parent_child(c: _Ctx, rows: int) -> Built:
    n_parent = max(rows // 10, 10)
    parents = Table(
        "parents",
        [
            _col("id", "int", _ids(n_parent)),
            _col("name", "text", c.names(n_parent)),
            _col("email", "text", c.emails(n_parent)),
        ],
    )
    children = Table(
        "children",
        [
            _col("id", "int", _ids(rows)),
            _col("parent_id", "int", [1 + p for p in c.pick(rows, n_parent)]),
            _col("memo", "text", c.notes(rows)),
            _col("amount", "float", c.floats(rows)),
        ],
    )
    return Built([parents, children], [ForeignKey("children", ("parent_id",), "parents", ("id",))])


def fk_chain3(c: _Ctx, rows: int) -> Built:
    n_acc, n_ord = max(rows // 20, 5), max(rows // 5, 10)
    accounts = Table(
        "accounts", [_col("id", "int", _ids(n_acc)), _col("name", "text", c.names(n_acc))]
    )
    orders = Table(
        "orders",
        [
            _col("id", "int", _ids(n_ord)),
            _col("account_id", "int", [1 + p for p in c.pick(n_ord, n_acc)]),
            _col("ref", "text", c.notes(n_ord)),
        ],
    )
    items = Table(
        "items",
        [
            _col("id", "int", _ids(rows)),
            _col("order_id", "int", [1 + p for p in c.pick(rows, n_ord)]),
            _col("sku", "text", c.notes(rows)),
        ],
    )
    fks = [
        ForeignKey("orders", ("account_id",), "accounts", ("id",)),
        ForeignKey("items", ("order_id",), "orders", ("id",)),
    ]
    return Built([accounts, orders, items], fks)


def self_ref(c: _Ctx, rows: int) -> Built:
    # Row i points at an earlier row, so the graph is a forest; 5 percent are roots.
    roots = (c.rng.random(rows) < 0.05).tolist()
    boss = [None if (r or i == 0) else int(c.rng.integers(1, i + 1)) for i, r in enumerate(roots)]
    staff = Table(
        "staff",
        [
            _col("id", "int", _ids(rows)),
            _col("manager_id", "int", boss),
            _col("name", "text", c.names(rows)),
        ],
    )
    return Built([staff], [ForeignKey("staff", ("manager_id",), "staff", ("id",))])


def composite_key(c: _Ctx, rows: int) -> Built:
    n_store = max(rows // 10, 10)
    marks = c.mk.take(n_store)
    regions = [f"{m} {'ABC'[i % 3]}" for i, m in enumerate(marks)]
    nos = [1 + i // 3 for i in range(n_store)]
    stores = Table(
        "stores",
        [
            _col("region", "text", regions),
            _col("store_no", "int", nos),
            _col("name", "text", c.names(n_store)),
        ],
    )
    pick = c.pick(rows, n_store)
    orders = Table(
        "sales",
        [
            _col("id", "int", _ids(rows)),
            _col("region", "text", [regions[p] for p in pick]),
            _col("store_no", "int", [nos[p] for p in pick]),
            _col("memo", "text", c.notes(rows)),
        ],
    )
    fk = ForeignKey("sales", ("region", "store_no"), "stores", ("region", "store_no"))
    return Built([stores, orders], [fk])


def fk_cycle(c: _Ctx, rows: int) -> Built:
    # Two tables that point at each other. The docs refuse a cross-table cycle in V1.
    n_dept = max(rows // 50, 5)
    depts = Table(
        "departments",
        [
            _col("id", "int", _ids(n_dept)),
            _col("head_id", "int", [1 + p for p in c.pick(n_dept, rows)]),
            _col("name", "text", c.names(n_dept)),
        ],
    )
    staff = Table(
        "employees",
        [
            _col("id", "int", _ids(rows)),
            _col("dept_id", "int", [1 + p for p in c.pick(rows, n_dept)]),
            _col("name", "text", c.names(rows)),
        ],
    )
    fks = [
        ForeignKey("departments", ("head_id",), "employees", ("id",)),
        ForeignKey("employees", ("dept_id",), "departments", ("id",)),
    ]
    return Built([depts, staff], fks)


def wide(c: _Ctx, rows: int) -> Built:
    makers: list[tuple[str, Callable[[], list]]] = [
        ("int", lambda: c.ints(rows, 0, 10_000)),
        ("float", lambda: c.floats(rows)),
        ("text", lambda: c.notes(rows)),
        ("date", lambda: _iso(c.days(rows))),
    ]
    cols = [_col("id", "int", _ids(rows))]
    for i in range(199):
        kind, make = makers[i % 4]
        cols.append(_col(f"c{i:03d}_{kind}", kind, make()))
    return Built([Table("wide", cols)])


def free_text(c: _Ctx, rows: int) -> Built:
    f, ln = c.pick(rows, len(_FIRST)), c.pick(rows, len(_LAST))
    marks = c.mk.take(rows)
    body = [
        f"{m} Hi, this is {_FIRST[a]} {_LAST[b]}. Write to {_FIRST_ASCII[a]}.{_LAST_ASCII[b]}"
        f"@example.invalid or call 555-01{i % 100:02d}."
        for i, (m, a, b) in enumerate(zip(marks, f, ln))
    ]
    return Built([Table("messages", [_col("id", "int", _ids(rows)), _col("body", "text", body)])])


def dates(c: _Ctx, rows: int) -> Built:
    d = c.days(rows)
    py = d.astype("datetime64[D]").astype(object)
    bad_pool = ("2023-02-30", "31/13/2022", "yesterday", "0000-00-00", "13-13-2013", "")
    bad = [bad_pool[i % len(bad_pool)] if i % 7 == 0 else s.isoformat() for i, s in enumerate(py)]
    cols = [
        _col("id", "int", _ids(rows)),
        _col("d_iso", "date", [s.strftime("%Y-%m-%d") for s in py]),
        _col("d_dmy", "date", [s.strftime("%d/%m/%Y") for s in py]),
        _col("d_mdy", "date", [s.strftime("%m-%d-%Y") for s in py]),
        _col("d_long", "date", [s.strftime("%d %b %Y") for s in py]),
        _col("d_compact", "date", [s.strftime("%Y%m%d") for s in py]),
        _col("d_bad", "date", bad),
        _col("label", "text", c.notes(rows)),
    ]
    return Built([Table("events", cols)])


def heavy_nulls(c: _Ctx, rows: int) -> Built:
    keep = 0.10
    cols = [
        _col("id", "int", _ids(rows)),
        _col("a", "text", _sparse(c.notes(rows), c.rng, keep)),
        _col("b", "int", _sparse(c.ints(rows, 0, 1000), c.rng, keep)),
        _col("c", "float", _sparse(c.floats(rows), c.rng, keep)),
        _col("d", "date", _sparse(_iso(c.days(rows)), c.rng, keep)),
    ]
    return Built([Table("sparse", cols)])


def null_constant(c: _Ctx, rows: int) -> Built:
    fixed = c.mk.take(1)[0] + " fixed"
    cols = [
        _col("id", "int", _ids(rows)),
        _col("all_null_text", "text", [None] * rows),
        _col("all_null_int", "int", [None] * rows),
        _col("const_text", "text", [fixed] * rows),
        _col("const_int", "int", [7] * rows),
        _col("label", "text", c.notes(rows)),
    ]
    return Built([Table("flat", cols)])


def dup_keys(c: _Ctx, rows: int) -> Built:
    keys = c.ints(rows, 1, max(rows // 2, 2))
    cols = [_col("id", "int", keys), _col("name", "text", c.names(rows))]
    return Built([Table("dups", cols)])


BUILDERS: dict[str, Callable[[_Ctx, int], Built]] = {
    "single": single,
    "parent_child": parent_child,
    "fk_chain3": fk_chain3,
    "self_ref": self_ref,
    "composite_key": composite_key,
    "fk_cycle": fk_cycle,
    "wide": wide,
    "free_text": free_text,
    "dates": dates,
    "heavy_nulls": heavy_nulls,
    "null_constant": null_constant,
    "dup_keys": dup_keys,
}
MODIFIERS = frozenset({"header_only", "empty_file", "malformed"})


def build(shape: str, rows: int, seed: int) -> Built:
    """Build the tables of one structure shape. `rows` 0 gives the schema with no rows."""
    ctx = _Ctx(seed)
    built = BUILDERS[shape](ctx, max(rows, 1))
    if rows == 0:
        for table in built.tables:
            for column in table.columns:
                column.values = []
    return built


def marker_columns(shape: str) -> tuple[str, ...]:
    """`table.column` for every text column of the shape, from a tiny build."""
    built = build(shape, 5, 0)
    return tuple(f"{t.name}.{c.name}" for t in built.tables for c in t.columns if c.kind == "text")
