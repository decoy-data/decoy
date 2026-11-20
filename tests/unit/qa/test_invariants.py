"""AT-3, AT-4, AT-5 and AT-12: planted defects for I2 to I7 (I1 is in test_sweep.py)."""

from __future__ import annotations

import json

import pytest
from scripts.qa import sweep
from scripts.qa.invariants import i2_foreign_keys as i2
from scripts.qa.invariants import i3_repeat, i4_rows, i5_schema, i6_exit, i7_errors

from decoy.cli import exit_codes

P = ["a", "n"]  # parent key columns
C = ["pa", "pn"]  # child key columns


def parents(*keys: tuple[str, int]) -> list[dict]:
    return [{"a": a, "n": n} for a, n in keys]


def children(*keys: tuple[str, int]) -> list[dict]:
    return [{"pa": a, "pn": n} for a, n in keys]


def run_fk(policy, sp, sc, op, oc, **kw):
    return i2.check_fk(policy, "t", sp, sc, op, oc, P, C, **kw)


# AT-3 ---------------------------------------------------------------------------------------
PARENTS = parents(("A", 1), ("B", 2))


def test_the_composite_tuple_orphan_is_caught_though_each_part_exists() -> None:
    bad = children(("A", 2))  # A exists, 2 exists, (A,2) does not
    found = run_fk("remap", PARENTS, children(("A", 1)), PARENTS, bad)
    assert [(v.invariant, v.kind) for v in found] == [("I2", "orphan")]


def test_remap_passes_when_every_tuple_joins() -> None:
    assert run_fk("remap", PARENTS, children(("A", 2)), PARENTS, children(("B", 2))) == []


def test_fail_policy_needs_a_refusal_for_a_source_orphan() -> None:
    src = children(("A", 2))
    assert [v.kind for v in run_fk("fail", PARENTS, src, PARENTS, [])] == ["not-refused"]
    assert run_fk("fail", PARENTS, src, [], [], refused=True) == []


def test_fail_policy_refusing_a_clean_source_is_wrong() -> None:
    clean = children(("A", 1))
    assert [v.kind for v in run_fk("fail", PARENTS, clean, [], [], refused=True)] == ["refused"]


def test_fail_policy_refusing_a_clean_source_is_wrong_for_remap() -> None:
    assert [v.kind for v in run_fk("remap", PARENTS, children(("A", 1)), [], [], refused=True)] == [
        "refused"
    ]


def test_preserve_keeps_the_orphan_relation_and_flags_a_changed_one() -> None:
    src = children(("A", 1), ("A", 2))  # second is an orphan
    assert run_fk("preserve", PARENTS, src, PARENTS, children(("B", 2), ("B", 1))) == []
    healed = run_fk("preserve", PARENTS, src, PARENTS, children(("B", 2), ("A", 1)))
    assert [v.kind for v in healed] == ["orphan"]
    broken = run_fk("preserve", PARENTS, src, PARENTS, children(("Z", 9), ("A", 2)))
    assert len(broken) == 1  # row 0 became an orphan; row 1 stayed one


@pytest.mark.parametrize("shape", ["single", "chain", "self"])
def test_single_chain_and_self_reference_keys(shape: str) -> None:
    keys = {"single": ["id"], "chain": ["id"], "self": ["id"]}[shape]
    parent = [{"id": 1}, {"id": 2}]
    ok = [{"pid": 1}, {"pid": 2}, {"pid": None}]  # a null key is not an orphan
    assert i2.check_fk("remap", shape, parent, ok, parent, ok, keys, ["pid"]) == []
    bad = [{"pid": 1}, {"pid": 7}]
    found = i2.check_fk("remap", shape, parent, ok, parent, bad, keys, ["pid"])
    assert [v.coordinate for v in found] == [f"{shape}/pid/1"]


# AT-4 ---------------------------------------------------------------------------------------
def test_one_changed_data_byte_is_flagged() -> None:
    a, b = {"out.csv": b"id,name\n1,x\n"}, {"out.csv": b"id,name\n1,y\n"}
    assert [v.kind for v in i3_repeat.compare(a, b)] == ["differs"]


def test_identical_runs_pass_and_a_missing_file_is_flagged() -> None:
    a = {"out.csv": b"1"}
    assert i3_repeat.compare(a, dict(a)) == []
    assert [v.kind for v in i3_repeat.compare(a, {})] == ["missing"]


def test_run_ids_and_timestamps_in_result_files_are_ignored() -> None:
    def result(run_id: str, at: str, rows: int) -> bytes:
        doc = {"run_id": run_id, "meta": {"started_at": at}, "rows": rows}
        return json.dumps(doc).encode()

    one, two = {"r.json": result("a", "t1", 5)}, {"r.json": result("b", "t2", 5)}
    assert i3_repeat.compare(one, two, result_files={"r.json"}) == []
    other = {"r.json": result("b", "t2", 6)}
    assert i3_repeat.compare(one, other, result_files={"r.json"})
    assert i3_repeat.compare(one, two)  # as plain data they differ


def test_each_promise_cites_a_docs_line() -> None:
    assert all(v.startswith("docs/cli-reference.md:") for v in i3_repeat.PROMISES.values())


# AT-5 ---------------------------------------------------------------------------------------
CRASH_ERR = "error: internal error (KeyError)\n"
CRASH_VERBOSE = "Traceback (most recent call last):\n  ...\nerror: internal error (KeyError)\n"


def kind(code: int, err: str = "", out: str = "", **kw) -> str:
    return i6_exit.classify(code, out, err, **kw).kind


@pytest.mark.parametrize("err", [CRASH_ERR, CRASH_VERBOSE, "", "Traceback (most recent call last)"])
def test_exit_1_crash_forms_are_always_findings(err: str) -> None:
    for expect in ("refusal", "success"):
        verdict = i6_exit.classify(exit_codes.EXIT_USAGE, "", err, expect=expect)
        assert (verdict.kind, verdict.finding) == ("crash", True)


def test_exit_1_documented_refusals() -> None:
    err = "error: --chunked cannot be combined with --vault\n"
    assert not i6_exit.classify(1, "", err, expect="refusal").finding
    assert i6_exit.classify(1, "", err, expect="success").finding


def test_exit_0_and_2() -> None:
    assert not i6_exit.classify(exit_codes.EXIT_OK, "", "").finding
    assert i6_exit.classify(0, "", "", expect="refusal").finding
    warned = "warning: output target exists\n"
    assert not i6_exit.classify(exit_codes.EXIT_WARNINGS, warned, "", expect="warnings").finding
    assert i6_exit.classify(2, warned, "", expect="success").finding


@pytest.mark.parametrize(
    ("out", "err"),
    [("", ""), ("done", ""), ("", "error: bad flag"), ("0 warnings", ""), ("no warnings", ""),
     ("", "error: warning: x"), ("", "Traceback (most recent call last):\nwarning: x"),
     ("the warning light is on", "")],
)  # fmt: skip
def test_exit_2_needs_a_documented_warning_form(out: str, err: str) -> None:
    verdict = i6_exit.classify(2, out, err, expect="warnings")
    assert verdict.finding and verdict.reason == "no-warning-form"


@pytest.mark.parametrize(
    ("out", "err"),
    [("warning: output target exists", ""), ("", "WARN  slow disk"), ("2 warnings", ""),
     ("", '{"severity": "warning"}'), ("check output_exists: warn", "")],
)  # fmt: skip
def test_each_documented_warning_form_passes(out: str, err: str) -> None:
    assert not i6_exit.classify(2, out, err, expect="warnings").finding


def test_exit_2_as_a_usage_error_needs_the_usage_form() -> None:
    assert not i6_exit.classify(
        2, "", "Usage: decoy run [OPTIONS]\nError: no", expect="usage"
    ).finding
    assert i6_exit.classify(2, "", "", expect="usage").reason == "no-usage-form"


@pytest.mark.parametrize("cell", ["readonly", "disk", "quota"])
def test_exit_3_passes_in_each_named_fault_cell(cell: str) -> None:
    ok = i6_exit.classify(exit_codes.EXIT_RUNTIME, "", "", cell=cell, atomic_ok=True)
    assert not ok.finding
    assert i6_exit.classify(3, "", "", cell=cell, atomic_ok=False).finding


def test_exit_3_passes_only_in_a_fault_cell_with_atomicity() -> None:
    assert i6_exit.classify(3, "", "", cell="disk", atomic_ok=False).finding
    assert i6_exit.classify(3, "", "", cell=None, atomic_ok=True).finding
    assert i6_exit.classify(3, "", "", cell="memory", atomic_ok=True).finding


def test_exit_5_passes_only_for_memory_and_exit_6_never() -> None:
    assert not i6_exit.classify(exit_codes.EXIT_CAPACITY, "", "", cell="memory").finding
    assert i6_exit.classify(5, "", "", cell="disk").finding
    assert i6_exit.classify(5, "", "").finding
    for expect in ("success", "findings", "refusal"):
        assert i6_exit.classify(exit_codes.EXIT_PARTIAL, "x", "x", expect=expect).finding


def test_exit_4_needs_findings_named_in_the_output() -> None:
    assert not i6_exit.classify(
        exit_codes.EXIT_FINDINGS, "3 findings", "", expect="findings"
    ).finding
    assert i6_exit.classify(4, "", "", expect="findings").finding
    for text in (
        "done, 12 rows written", "warning: slow disk", "all checks passed",
        "no findings", "0 findings", "No finding. 3 checks fail-safe ok",
        "Traceback (most recent call last):\n  KeyError: 'fail'",
        "changed", "failed", "error: failed to open configuration", "1 changed file name",
        "fingerprint ok, failed nothing",
    ):  # fmt: skip
        assert i6_exit.classify(4, text, "", expect="findings").finding, text
    for text in (
        "check fk_preservation: fail", "1 finding", "fingerprint changed: out.csv",
        "INTEGRITY CHECK FAILED: fingerprint mismatch", "fail=2  warn=0", '{"fail_count": 3}',
        "4 records checked: 2 findings, 0 warnings", "1 left behind",
    ):  # fmt: skip
        assert not i6_exit.classify(4, text, "", expect="findings").finding, text
    assert i6_exit.classify(4, "x", "", expect="success").finding


def test_interrupt_unknown_and_signal_exits() -> None:
    assert not i6_exit.classify(130, "", "", expect="interrupted").finding
    assert i6_exit.classify(130, "", "", expect="success").finding
    for code in (7, 99, -9, 137):
        assert (kind(code), i6_exit.classify(code, "", "").finding) == ("unknown", True)


def test_json_that_does_not_parse_or_fails_its_schema_is_a_finding() -> None:
    assert i6_exit.classify(0, "", "", json_text="{not json").reason == "invalid-json"
    assert i6_exit.classify(0, "", "", json_text="{}", validate=lambda d: False).finding
    assert not i6_exit.classify(0, "", "", json_text="{}", validate=lambda d: True).finding


# AT-12 --------------------------------------------------------------------------------------
def test_i4_row_loss_and_wrong_quarantine_counts() -> None:
    assert i4_rows.check_mask("t", 10, 8, 2, 2) == []
    assert [v.kind for v in i4_rows.check_mask("t", 10, 8, 1, 1)] == ["row-loss"]
    assert [v.kind for v in i4_rows.check_mask("t", 10, 8, 2, 3)] == ["quarantine-count"]
    assert [v.kind for v in i4_rows.check_subset("t", 5, 6)] == ["subset-grew"]
    assert i4_rows.check_subset("t", 5, 5) == []
    assert [v.kind for v in i4_rows.check_generate("t", 99, 100)] == ["generated-count"]
    assert i4_rows.check_generate("t", 50, 100, ratio=0.5) == []


def test_i5_names_order_and_types() -> None:
    want = [("id", "int"), ("name", "str")]
    assert i5_schema.check_schema("t", want, list(want)) == []
    assert [v.kind for v in i5_schema.check_schema("t", want, [("id", "int"), ("nom", "str")])] == [
        "names"
    ]
    assert [v.kind for v in i5_schema.check_schema("t", want, want[::-1])] == ["order"]
    found = i5_schema.check_schema("t", want, [("id", "str"), ("name", "str")])
    assert [(v.kind, v.coordinate) for v in found] == [("type", "t/id/-")]


def test_i7_flags_non_marker_input_and_output_scalars() -> None:
    refusal = sweep.RefusalSet.build(["Zelda Quinn", 90210])
    cells = ["Omar Fry", 4471]
    texts = {"stderr": "error: bad value Omar Fry in column name", "stdout": "ok"}
    found = i7_errors.check_text(texts, [], None, cells)
    assert [(v.surface, v.kind) for v in found] == [("stderr", "input-cell")]
    out = i7_errors.check_text({"logs": "customer Zelda Quinn rejected"}, [], refusal)
    assert [(v.surface, v.kind) for v in out] == [("logs", "scalar")]
    assert [v.kind for v in i7_errors.check_text({"stdout": "qamark9"}, [b"qamark9"])] == ["needle"]
    assert (
        i7_errors.check_text({"stderr": "error: bad column 'name'"}, [b"qamark9"], refusal, cells)
        == []
    )
    assert all("Omar" not in repr(v) for v in found)


def test_i7_matches_whole_tokens_not_substrings() -> None:
    assert (
        i7_errors.check_text({"stderr": "error: Bobby Tables failed"}, [b"qamark9"], None, ["Bob"])
        == []
    )
    assert [
        v.kind for v in i7_errors.check_text({"stderr": "who: bob."}, [b"qamark9"], None, ["Bob"])
    ] == ["input-cell"]


def test_i7_goes_through_the_sweep_and_empty_input_is_not_a_pass() -> None:
    with pytest.raises(sweep.NothingRead):
        i7_errors.check_text({"stderr": "error: x"}, [], None, [])  # nothing to look for
    with pytest.raises(sweep.NothingRead):
        i7_errors.check_text({"stdout": "", "stderr": ""}, [b"qamark9"])  # nothing to read
    refusal = sweep.RefusalSet.build(["Zelda Quinn"])
    found = i7_errors.check_text({"stderr": "Zelda Quinn and Omar Fry"}, [], refusal, ["Omar Fry"])
    assert sorted(v.kind for v in found) == ["input-cell", "scalar"]
    assert i7_errors.check_text({"stderr": "ok"}, [], None, ["Omar Fry"]) == []  # cells are input
