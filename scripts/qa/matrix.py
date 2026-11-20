"""Turn `docs/qa/matrix.toml` into the pairwise L4 run list (plan 5.4).

    python -m scripts.qa.matrix [--name mask|generate] [--matrix PATH] [--out PATH]

Every pair of parameter values appears in at least one run, except a pair that the refusal
constraints make impossible. Each such pair is listed with its constraint kinds and doc lines, so
it turns into a refusal check, an ignored-flag equality check or a documented n/a (failure mode
F6). `allpairspy` does the bulk of the covering. A filter can leave a feasible pair uncovered, so
a completion pass adds one run per leftover pair that still has a valid completion; a pair with
none is removed and listed. The run list is written per QA pass and not committed.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from allpairspy import AllPairs
from scripts.qa.io import publish_private_once

SCHEMA_VERSION = 1
KINDS = ("refused", "refused_after_run", "ignored")
BLOCKING = ("refused", "refused_after_run")
DEFAULT_MATRIX = Path(__file__).resolve().parents[2] / "docs/qa/matrix.toml"
_DOC = re.compile(r"docs/cli-reference\.md:[0-9]+")
Pair = tuple[tuple[str, str], tuple[str, str]]


class MatrixError(ValueError):
    """The matrix file is malformed. Messages name ids and parameters, not data."""


@dataclass(frozen=True)
class Constraint:
    id: str
    kind: str
    when: dict[str, tuple[str, ...]]
    doc: str
    cites: tuple[str, ...]
    expect: str

    def matches(self, assignment: dict[str, str]) -> bool:
        """True when every parameter this constraint names is set to one of its values."""
        return all(assignment.get(p) in vals for p, vals in self.when.items())


@dataclass(frozen=True)
class Standalone:
    id: str
    kind: str
    flags: tuple[str, ...]
    doc: str
    cites: tuple[str, ...]
    expect: str


@dataclass(frozen=True)
class Matrix:
    name: str
    parameters: dict[str, tuple[str, ...]]
    constraints: tuple[Constraint, ...]
    standalone: tuple[Standalone, ...]


@dataclass
class Plan:
    runs: list[dict[str, str]]
    ignored: list[list[str]]  # per run: ids of the `ignored` constraints that apply
    removed: list[dict[str, object]]
    standalone: list[Standalone]


def _strs(value: object, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(type(v) is str and v for v in value):
        raise MatrixError(f"{where} must be a non-empty list of non-empty strings")
    return tuple(value)


def _common(raw: dict[str, object], where: str) -> tuple[str, str, str, tuple[str, ...], str]:
    ident, kind, doc, expect = (raw.get(k) for k in ("id", "kind", "doc", "expect"))
    if type(ident) is not str or not ident:
        raise MatrixError(f"{where}: id must be a non-empty string")
    if kind not in KINDS:
        raise MatrixError(f"{ident}: kind must be one of {KINDS}")
    if type(doc) is not str or _DOC.fullmatch(doc) is None:
        raise MatrixError(f"{ident}: doc must look like docs/cli-reference.md:<line>")
    if type(expect) is not str or not expect:
        raise MatrixError(f"{ident}: expect must be a non-empty string")
    return ident, kind, doc, _strs(raw.get("cites"), f"{ident}: cites"), expect


def _constraint(raw: dict[str, object], params: dict[str, tuple[str, ...]]) -> Constraint:
    ident, kind, doc, cites, expect = _common(raw, "constraint")
    when_raw = raw.get("when")
    if not isinstance(when_raw, dict) or not when_raw:
        raise MatrixError(f"{ident}: when must be a non-empty table")
    when: dict[str, tuple[str, ...]] = {}
    for param, value in when_raw.items():
        values = (value,) if type(value) is str else _strs(value, f"{ident}: when.{param}")
        if param not in params or not set(values) <= set(params[param]):
            raise MatrixError(f"{ident}: when.{param} names an unknown parameter or value")
        when[param] = tuple(values)
    return Constraint(ident, kind, when, doc, cites, expect)


def parse(text: str) -> list[Matrix]:
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        raise MatrixError("matrix.toml is not valid TOML") from None
    if type(doc.get("schema_version")) is not int or doc["schema_version"] != SCHEMA_VERSION:
        raise MatrixError(f"schema_version must be the integer {SCHEMA_VERSION}")
    out, seen = [], set()
    for raw in doc.get("matrix", []):
        params = {k: _strs(v, f"parameter {k}") for k, v in raw.get("parameters", {}).items()}
        if len(params) < 2:
            raise MatrixError(f"matrix {raw.get('name')!r} needs at least two parameters")
        cons = tuple(_constraint(c, params) for c in raw.get("constraints", []))
        alone = []
        for s in raw.get("standalone", []):
            ident, kind, sdoc, cites, expect = _common(s, "standalone")
            alone.append(Standalone(ident, kind, _strs(s.get("flags"), ident), sdoc, cites, expect))
        ids = [c.id for c in cons] + [s.id for s in alone]
        if len(ids) != len(set(ids)) or seen & set(ids):
            raise MatrixError("a constraint id appears twice")
        seen |= set(ids)
        out.append(Matrix(str(raw.get("name")), params, cons, tuple(alone)))
    if not out:
        raise MatrixError("no [[matrix]] tables")
    return out


def load(path: Path = DEFAULT_MATRIX) -> list[Matrix]:
    return parse(Path(path).read_text(encoding="utf-8"))


def _violates(matrix: Matrix, assignment: dict[str, str]) -> bool:
    return any(c.kind in BLOCKING and c.matches(assignment) for c in matrix.constraints)


def _complete(matrix: Matrix, fixed: dict[str, str]) -> dict[str, str] | None:
    """Depth-first search for a full valid run that contains `fixed`; None if there is none."""
    names = [n for n in matrix.parameters if n not in fixed]

    def go(i: int, cur: dict[str, str]) -> dict[str, str] | None:
        if i == len(names):
            return {n: cur[n] for n in matrix.parameters}  # parameter order keeps pairs canonical
        for value in matrix.parameters[names[i]]:
            nxt = {**cur, names[i]: value}
            if not _violates(matrix, nxt) and (done := go(i + 1, nxt)) is not None:
                return done
        return None

    return None if _violates(matrix, fixed) else go(0, dict(fixed))


def _all_pairs(matrix: Matrix) -> list[Pair]:
    items = [[(n, v) for v in vals] for n, vals in matrix.parameters.items()]
    return [(a, b) for left, right in itertools.combinations(items, 2) for a in left for b in right]


def _pairs_of(run: dict[str, str]) -> set[Pair]:
    items = list(run.items())
    return {(a, b) for a, b in itertools.combinations(items, 2)}


def _blame(matrix: Matrix, pair: Pair) -> list[Constraint]:
    """The blocking constraints that explain why `pair` has no valid run."""
    held = dict(pair)
    direct = [c for c in matrix.constraints if c.kind in BLOCKING and set(c.when) <= set(held)]
    direct = [c for c in direct if c.matches(held)]
    if direct:
        return direct
    return [
        c
        for c in matrix.constraints
        if c.kind in BLOCKING and any(held.get(p) in v for p, v in c.when.items())
    ]


def plan(matrix: Matrix) -> Plan:
    names = list(matrix.parameters)
    runs = [
        dict(zip(names, row))
        for row in AllPairs(
            [list(v) for v in matrix.parameters.values()],
            filter_func=lambda row: not _violates(matrix, dict(zip(names, row))),
        )
    ]
    covered: set[Pair] = set().union(*(_pairs_of(r) for r in runs)) if runs else set()
    removed = []
    for pair in _all_pairs(matrix):
        if pair in covered:
            continue
        full = _complete(matrix, dict(pair))
        if full is not None:
            runs.append(full)
            covered |= _pairs_of(full)
            continue
        why = _blame(matrix, pair)
        removed.append(
            {
                "pair": [list(pair[0]), list(pair[1])],
                "constraints": [c.id for c in why],
                "kinds": sorted({c.kind for c in why}),
                "docs": sorted({c.doc for c in why}),
            }
        )
    ignored = [
        [c.id for c in matrix.constraints if c.kind == "ignored" and c.matches(r)] for r in runs
    ]
    return Plan(runs, ignored, removed, list(matrix.standalone))


def to_json(matrix: Matrix, result: Plan) -> str:
    doc = {
        "matrix": matrix.name,
        "runs": [
            {"index": i, "values": r, "ignored_flag_checks": ig}
            for i, (r, ig) in enumerate(zip(result.runs, result.ignored))
        ],
        "removed_pairs": result.removed,
        "standalone_refusals": [
            {"id": s.id, "flags": list(s.flags), "doc": s.doc, "expect": s.expect}
            for s in result.standalone
        ],
    }
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    ap.add_argument("--name", choices=("mask", "generate"), default="mask")
    ap.add_argument("--out", type=Path, help="write the run list here (0600, create once)")
    args = ap.parse_args(argv)
    matrix = next(m for m in load(args.matrix) if m.name == args.name)
    text = to_json(matrix, plan(matrix))
    if args.out:
        publish_private_once(args.out, text.encode("utf-8"))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
