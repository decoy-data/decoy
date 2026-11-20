"""AT-6: the pairwise generator covers every value pair that no constraint removes, and lists each
removed pair with its kind and doc line. The property test uses random parameter sets and checks
the answer against an independent brute-force walk of the whole product."""

from __future__ import annotations

import itertools
import random
from pathlib import Path

import pytest
from scripts.qa import matrix as mx

ROOT = Path(__file__).resolve().parents[3]
REF = (ROOT / "docs/cli-reference.md").read_text(encoding="utf-8").splitlines()
MATRICES = {m.name: m for m in mx.load(ROOT / "docs/qa/matrix.toml")}


def product(matrix: mx.Matrix, free: set[str] | None = None):
    """Every full assignment; parameters outside `free` are pinned to their first value."""
    names = list(matrix.parameters)
    pools = [v if free is None or n in free else v[:1] for n, v in matrix.parameters.items()]
    for combo in itertools.product(*pools):
        yield dict(zip(names, combo))


def valid(matrix: mx.Matrix, run: dict[str, str]) -> bool:
    return not any(c.kind in mx.BLOCKING and c.matches(run) for c in matrix.constraints)


def feasible_pairs(matrix: mx.Matrix, free: set[str] | None = None) -> set[mx.Pair]:
    pairs: set[mx.Pair] = set()
    for run in product(matrix, free):
        if valid(matrix, run):
            pairs |= {(a, b) for a, b in itertools.combinations(run.items(), 2)}
    return pairs


def check_plan(matrix: mx.Matrix, result: mx.Plan, feasible: set[mx.Pair]) -> list[str]:
    """Why the plan is wrong; empty when it covers every feasible pair and removes the rest."""
    problems = []
    covered = {p for run in result.runs for p in mx._pairs_of(run)}
    all_pairs = set(mx._all_pairs(matrix))
    removed = {(tuple(r["pair"][0]), tuple(r["pair"][1])) for r in result.removed}
    problems += [f"uncovered feasible pair {p}" for p in sorted(feasible - covered)]
    problems += [f"removed but feasible {p}" for p in sorted(removed & feasible)]
    problems += [f"neither covered nor removed {p}" for p in sorted(all_pairs - covered - removed)]
    problems += [f"run breaks a refusal: {r}" for r in result.runs if not valid(matrix, r)]
    problems += [
        f"removed pair without kind or doc: {r['pair']}"
        for r in result.removed
        if not (r["kinds"] and r["docs"] and r["constraints"])
    ]
    return problems


def random_matrix(rng: random.Random) -> mx.Matrix:
    params = {
        f"p{i}": tuple(f"v{i}{j}" for j in range(rng.randint(2, 4)))
        for i in range(rng.randint(2, 5))
    }
    names = list(params)
    cons = []
    for n in range(rng.randint(0, 4)):
        chosen = rng.sample(names, rng.randint(1, min(3, len(names))))
        when = {
            p: tuple(rng.sample(params[p], rng.randint(1, len(params[p]) - 1 or 1))) for p in chosen
        }
        cons.append(
            mx.Constraint(
                f"c{n}", rng.choice(mx.KINDS), when, "docs/cli-reference.md:1", ("x",), "e"
            )
        )
    return mx.Matrix("rand", params, tuple(cons), ())


def test_random_parameter_sets_are_covered_or_removed_exactly() -> None:
    rng = random.Random(20261120)
    for case in range(150):
        matrix = random_matrix(rng)
        problems = check_plan(matrix, mx.plan(matrix), feasible_pairs(matrix))
        assert problems == [], (case, matrix, problems[:3])


def test_a_dropped_run_is_caught_by_the_checker() -> None:
    matrix = MATRICES["generate"]
    result = mx.plan(matrix)
    feasible = feasible_pairs(matrix)
    assert check_plan(matrix, result, feasible) == []
    result.runs.pop()
    assert any("uncovered" in p for p in check_plan(matrix, result, feasible))


def test_a_run_that_breaks_a_refusal_is_caught_by_the_checker() -> None:
    matrix = MATRICES["generate"]
    result = mx.plan(matrix)
    bad = dict(result.runs[0], rows="--rows 100", evidence="--evidence-out")
    result.runs.append(bad)
    assert any("breaks a refusal" in p for p in check_plan(matrix, result, feasible_pairs(matrix)))


@pytest.mark.parametrize("name", ["mask", "generate"])
def test_the_real_matrices_are_covered_or_removed_exactly(name: str) -> None:
    matrix = MATRICES[name]
    mentioned = {p for c in matrix.constraints if c.kind in mx.BLOCKING for p in c.when}
    # Parameters no refusal mentions are free: pinning them keeps the walk small and exact.
    result = mx.plan(matrix)
    feasible = feasible_pairs(matrix, mentioned)
    in_scope = {p for p in mx._all_pairs(matrix) if p[0][0] in mentioned and p[1][0] in mentioned}
    covered = {p for run in result.runs for p in mx._pairs_of(run)}
    removed = {(tuple(r["pair"][0]), tuple(r["pair"][1])) for r in result.removed}
    assert in_scope - covered == removed & in_scope
    assert (in_scope & feasible) <= covered
    assert not (removed & feasible)
    assert check_plan(matrix, result, set()) == []
    # Every pair is covered or removed, including the ones outside the pinned walk.
    assert set(mx._all_pairs(matrix)) == covered | removed


def test_run_counts_are_in_the_planned_range() -> None:
    assert 40 <= len(mx.plan(MATRICES["mask"]).runs) <= 80
    assert 8 <= len(mx.plan(MATRICES["generate"]).runs) <= 20


def test_the_plan_is_deterministic_and_prints_json(tmp_path: Path) -> None:
    matrix = MATRICES["mask"]
    first, second = mx.to_json(matrix, mx.plan(matrix)), mx.to_json(matrix, mx.plan(matrix))
    assert first == second
    out = tmp_path / "runs.json"
    assert mx.main(["--name", "mask", "--out", str(out)]) == 0
    assert out.read_text() == first
    assert oct(out.stat().st_mode & 0o777) == "0o600"


# The file itself ----------------------------------------------------------------------------


def test_the_three_constraint_kinds_are_all_used() -> None:
    kinds = {c.kind for m in MATRICES.values() for c in m.constraints}
    assert kinds == set(mx.KINDS)


def test_every_constraint_cites_a_doc_line_that_says_what_it_claims() -> None:
    every = [*(c for m in MATRICES.values() for c in m.constraints)]
    every += [s for m in MATRICES.values() for s in m.standalone]
    for c in every:
        line = int(c.doc.rsplit(":", 1)[1])
        assert 1 <= line <= len(REF), c.id
        for needle in c.cites:
            assert needle in REF[line - 1], f"{c.id}: {needle!r} not on {c.doc}"


def test_the_matrix_parameters_are_the_planned_ones() -> None:
    assert list(MATRICES["mask"].parameters) == [
        "strategy_mix", "source", "size_tier", "mask_secret", "chunked", "native", "threads",
        "memory_budget", "subset", "post_scan", "evidence", "vault", "output", "json",
    ]  # fmt: skip
    assert list(MATRICES["generate"].parameters) == [
        "key", "rows", "tables", "output_format", "native", "evidence", "json",
    ]  # fmt: skip
    assert MATRICES["mask"].parameters["source"] == (
        "csv",
        "tsv",
        "parquet",
        "fixed-width",
        "duckdb",
    )
    assert MATRICES["generate"].standalone[0].flags == ("--native",)


def test_every_planned_refusal_example_is_a_constraint() -> None:
    ids = {c.id for c in MATRICES["mask"].constraints}
    assert {
        "mask-chunked-vault",
        "mask-chunked-subset",
        "mask-chunked-fixed-width",
        "mask-chunked-post-validate",
        "mask-chunked-not-value-keyed",
        "mask-duckdb-evidence",
        "mask-unkeyed-date-shift",
        "mask-chunked-ignores-max-memory",
        "mask-chunked-ignores-threads",
        "mask-native-no-kernel-evidence",
    } <= ids
    subset = next(c for c in MATRICES["mask"].constraints if c.id == "mask-chunked-subset")
    assert "--no-subset" in subset.when["subset"]  # refused even with --no-subset


def test_ignored_constraints_tag_runs_and_never_remove_pairs() -> None:
    matrix = MATRICES["mask"]
    result = mx.plan(matrix)
    tagged = [ig for ig in result.ignored if ig]
    assert tagged, "some run pairs --chunked with --threads or --max-memory"
    removed_ids = {i for r in result.removed for i in r["constraints"]}
    assert not removed_ids & {c.id for c in matrix.constraints if c.kind == "ignored"}


@pytest.mark.parametrize(
    "text",
    [
        "schema_version = 2\n",
        "schema_version = 1\n",
        'schema_version = 1\n[[matrix]]\nname="m"\n[matrix.parameters]\na=["1"]\n',
        'schema_version = 1\n[[matrix]]\nname="m"\n[matrix.parameters]\na=["1","2"]\nb=["x","y"]\n'
        '[[matrix.constraints]]\nid="c"\nkind="bogus"\nwhen={a="1"}\ndoc="docs/cli-reference.md:1"\n'
        'cites=["x"]\nexpect="e"\n',
        'schema_version = 1\n[[matrix]]\nname="m"\n[matrix.parameters]\na=["1","2"]\nb=["x","y"]\n'
        '[[matrix.constraints]]\nid="c"\nkind="refused"\nwhen={a="9"}\ndoc="docs/cli-reference.md:1"\n'
        'cites=["x"]\nexpect="e"\n',
        'schema_version = 1\n[[matrix]]\nname="m"\n[matrix.parameters]\na=["1","2"]\nb=["x","y"]\n'
        '[[matrix.constraints]]\nid="c"\nkind="refused"\nwhen={a="1"}\ndoc="README.md:3"\n'
        'cites=["x"]\nexpect="e"\n',
    ],
)
def test_a_malformed_matrix_file_is_refused(text: str) -> None:
    with pytest.raises(mx.MatrixError):
        mx.parse(text)
