"""AT-2: the I1 sweep is driven by the surface registry; plus the shared sweep's exit meanings.

Each registered surface gets a planted marker, a planted secret and a planted indexed scalar. The
exception cases come from the same registry, and a consistency test fails if the dispatch, these
parameters and the I1 rules do not name the same entries.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from scripts.qa import sweep
from scripts.qa.invariants import i1_leaks
from scripts.qa.invariants.i1_leaks import Rule, check_cells

REGISTRY = sweep.load_registry()
NEEDLES = sweep.read_needles("qamark0042\nS3cretValueXYZ\n")
REFUSAL = sweep.RefusalSet.build(["Zelda Quinn", 90210, datetime.date(2020, 1, 2), 3.5])
SURFACES = sorted(REGISTRY.surfaces)


NEEDLE_PLANTS = ["row qamark0042 here", "token=S3cretValueXYZ"]
SCALAR_PLANTS = ["who: Zelda Quinn.", "on 2020-01-02"]
NUMERIC_PLANTS = ["zip 90210", "ratio 3.5 here"]


def _text_surfaces() -> list[str]:
    return [s for s in SURFACES if REGISTRY.surfaces[s].check == "needles"]


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("planted", NEEDLE_PLANTS)
def test_each_surface_catches_each_planted_needle(surface: str, planted: str) -> None:
    leaks = sweep.sweep({"cap": (surface, planted.encode())}, NEEDLES, REGISTRY, REFUSAL)
    assert [lk.surface for lk in leaks] == [surface]
    assert planted.split()[-1] not in repr(leaks[0])  # a leak never carries the matched text


@pytest.mark.parametrize("surface", _text_surfaces())
@pytest.mark.parametrize("planted", [*SCALAR_PLANTS, *NUMERIC_PLANTS])
def test_text_surfaces_catch_indexed_scalars(surface: str, planted: str) -> None:
    leaks = sweep.sweep({"cap": (surface, planted.encode())}, NEEDLES, REGISTRY, REFUSAL)
    numeric_only = planted in NUMERIC_PLANTS
    if numeric_only and not REGISTRY.surfaces[surface].numeric_matches:
        assert leaks == []  # the run summary prints its own counts
    else:
        assert [lk.surface for lk in leaks] == [surface]


@pytest.mark.parametrize("planted", [*SCALAR_PLANTS, *NUMERIC_PLANTS])
def test_cells_and_encrypted_surfaces_do_not_read_the_refusal_set(planted: str) -> None:
    # Cell values are the point of an output file (I1 owns them); ciphertext is noise.
    for surface in (s for s in SURFACES if REGISTRY.surfaces[s].check != "needles"):
        captures = {"cap": (surface, planted.encode())}
        assert sweep.sweep(captures, NEEDLES, REGISTRY, REFUSAL) == []


def test_only_the_run_summary_skips_numeric_only_matches() -> None:
    skipped = {s for s, v in REGISTRY.surfaces.items() if not v.numeric_matches}
    assert skipped == {"stdout"}
    both = sweep.RefusalSet.build([90210, "Main 90210"])
    # a number next to words is not numeric-only, so it still counts on stdout
    text = b"lives at Main 90210"
    assert sweep.sweep({"c": ("stdout", text)}, NEEDLES, REGISTRY, both)
    assert sweep.sweep({"c": ("stderr", b"zip 90210")}, NEEDLES, REGISTRY, both)
    assert not sweep.sweep({"c": ("stdout", b"zip 90210")}, NEEDLES, REGISTRY, both)


@pytest.mark.parametrize("surface", SURFACES)
def test_each_surface_passes_clean_text(surface: str) -> None:
    clean = {"cap": (surface, b"exit 3 after 12 rows, nothing to see")}
    assert sweep.sweep(clean, NEEDLES, REGISTRY, REFUSAL) == []


def test_registry_dispatch_params_and_exceptions_share_entries() -> None:
    assert set(i1_leaks.EXCEPTION_RULES) == set(REGISTRY.exceptions)
    assert set(EXCEPTION_PASS_CASES) == set(REGISTRY.exceptions)
    assert {s.check for s in REGISTRY.surfaces.values()} <= set(sweep.CHECKS)
    assert set(sweep.CHECK_RULES) == set(sweep.CHECKS)  # every registry check has its own rule
    with pytest.raises(sweep.RegistryError):
        sweep.sweep({"cap": ("not-a-surface", b"x")}, NEEDLES, REGISTRY)


# Each documented exception has a pass case: behaviour that must not be flagged.
SRC = [{"c": "Zelda Quinn"}, {"c": "Omar Fry"}]
EXCEPTION_PASS_CASES = {
    "passthrough": (Rule("passthrough"), SRC, SRC, False),
    "truncate-prefix": (Rule("truncate", prefix=3), SRC, [{"c": "Zel"}, {"c": "Oma"}], False),
    "text-redact-context": (
        Rule("text_redact", entities=(("Zelda",), ("Omar",))),
        [{"c": "hi Zelda ok"}, {"c": "hi Omar ok"}],
        [{"c": "hi [NAME] ok"}, {"c": "hi [NAME] ok"}],
        False,
    ),
    "unmask-output": (Rule("hash"), SRC, SRC, True),
}


@pytest.mark.parametrize("name", sorted(EXCEPTION_PASS_CASES))
def test_each_exception_passes(name: str) -> None:
    rule, before, after, unmask = EXCEPTION_PASS_CASES[name]
    assert check_cells("t", {"c": rule}, before, after, unmask_run=unmask) == []


@pytest.mark.parametrize(
    ("rule", "after", "kind"),
    [
        (Rule("hash"), [{"c": "Zelda Quinn"}, {"c": "x1"}], "same-row"),
        (Rule("hash"), [{"c": "Omar Fry"}, {"c": "Zelda Quinn"}], "exact-cell"),
        (Rule("fpe"), [{"c": "Zelda Quinn"}, {"c": "x1"}], "same-row"),
        (Rule("truncate", prefix=3), [{"c": "Zelda"}, {"c": "Oma"}], "truncate-extra"),
        (Rule("text_redact", entities=(("Zelda",), ())), [{"c": "hi Zelda"}, {"c": "x"}], "entity"),
    ],
)
def test_planted_cell_defects_are_flagged(rule: Rule, after: list[dict], kind: str) -> None:
    src = [{"c": "Zelda Quinn"}, {"c": "Omar Fry"}]
    if rule.strategy == "text_redact":
        src = [{"c": "hi Zelda"}, {"c": "x"}]
    found = check_cells("t", {"c": rule}, src, after)
    assert [v.kind for v in found][:1] == [kind]
    assert found[0].coordinate.startswith("t/c/")


@pytest.mark.parametrize("strategy", ["hash", "tokenize", "redact"])
def test_swapping_values_between_rows_fails_the_exact_cell_strategies(strategy: str) -> None:
    found = check_cells("t", {"c": Rule(strategy)}, SRC, SRC[::-1])
    assert [v.kind for v in found] == ["exact-cell", "exact-cell"]


def test_faker_gets_the_exact_cell_check_over_marker_inputs_only() -> None:
    marked = [{"c": "qamark1"}, {"c": "qamark2"}]
    assert [v.kind for v in check_cells("t", {"c": Rule("faker")}, marked, marked[::-1])] == [
        "exact-cell",
        "exact-cell",
    ]
    # Public data has no markers: a faker value may legitimately equal another row's input.
    assert check_cells("t", {"c": Rule("faker")}, SRC, SRC[::-1]) == []
    assert [v.kind for v in check_cells("t", {"c": Rule("faker")}, SRC, SRC)] == ["same-row"] * 2


def _dates(shifts: list[int]) -> tuple[list[dict], list[dict]]:
    base = datetime.date(2020, 1, 1)
    src = [{"c": base + datetime.timedelta(days=i)} for i in range(len(shifts))]
    return src, [{"c": r["c"] + datetime.timedelta(days=d)} for r, d in zip(src, shifts)]


def test_date_shift_passes_a_thousand_real_shifts_and_checks_range_and_same_row() -> None:
    import random

    rng = random.Random(7)
    shifts = [rng.choice([d for d in range(-30, 31) if d]) for _ in range(1000)]
    src, out = _dates(shifts)
    assert check_cells("t", {"c": Rule("date_shift", range=30)}, src, out) == []
    src, out = _dates([0, 31, -31, 5])
    kinds = [v.kind for v in check_cells("t", {"c": Rule("date_shift", range=30)}, src, out)]
    assert kinds == ["same-row", "shift-range", "shift-range"]
    iso = [{"c": "2020-01-01"}], [{"c": "2020-01-09"}]
    assert check_cells("t", {"c": Rule("date_shift", range=30)}, *iso) == []


def test_date_shift_needs_its_range() -> None:
    src, out = _dates([3])
    with pytest.raises(i1_leaks.UnknownStrategy):
        check_cells("t", {"c": Rule("date_shift")}, src, out)


def _codes() -> tuple[list[dict], list[dict], list[dict]]:
    import random

    sample = random.Random(1).sample(range(10000), 1000)
    src = [{"c": f"{x:04d}"} for x in sample]
    permuted = [{"c": f"{(x * 7919 + 13) % 10000:04d}"} for x in sample]  # a bijection of 0..9999
    return src, permuted, src[1:] + src[:1]  # last: a row permutation of the same values


@pytest.mark.parametrize("strategy", ["fpe", "faker"])
def test_a_true_permutation_of_the_domain_passes_and_a_row_swap_fails(strategy: str) -> None:
    src, permuted, swapped = _codes()
    rule = Rule(strategy, pool=True)
    assert check_cells("t", {"c": rule}, src, permuted) == []
    found = check_cells("t", {"c": rule}, src, swapped)
    assert [(v.kind, v.coordinate) for v in found] == [("permutation", "t/c/-")]


def test_the_swap_check_needs_twenty_rows() -> None:
    src, _, _ = _codes()
    assert check_cells("t", {"c": Rule("fpe")}, src[:10], src[1:10] + src[:1]) == []


@pytest.mark.parametrize("after", ["", "Ze", "Zeld", "Omar"])
def test_truncate_keeps_exactly_the_documented_prefix(after: str) -> None:
    out = [{"c": after}, {"c": "Oma"}]
    found = check_cells("t", {"c": Rule("truncate", prefix=3)}, SRC, out)
    assert [v.coordinate for v in found] == ["t/c/0"]


def test_truncate_must_set_its_prefix() -> None:
    with pytest.raises(i1_leaks.UnknownStrategy):
        check_cells("t", {"c": Rule("truncate")}, SRC, SRC)


def test_text_redact_entities_match_case_insensitively() -> None:
    rule = Rule("text_redact", entities=(("Zelda",), ()))
    found = check_cells(
        "t", {"c": rule}, [{"c": "hi zelda"}, {"c": "x"}], [{"c": "hi ZELDA"}, {"c": "x"}]
    )
    assert [v.kind for v in found] == ["entity"]


def test_an_unknown_strategy_is_refused_not_passed() -> None:
    with pytest.raises(i1_leaks.UnknownStrategy):
        check_cells("t", {"c": Rule("made_up")}, SRC, SRC)


def test_the_marker_kept_by_a_replacing_strategy_on_stdout_is_a_leak() -> None:
    leaks = sweep.sweep({"o": ("stdout", b"qamark0042")}, NEEDLES, REGISTRY)
    assert leaks == [sweep.Leak("stdout", "o", "n0")]


def test_a_long_hex_secret_also_matches_as_raw_bytes() -> None:
    secret = "00ff10ab" * 6  # 48 hex characters
    needles = sweep.read_needles(secret + "\n")
    assert sweep.hits(bytes.fromhex(secret), needles) == [1]


def test_a_short_hex_looking_marker_is_not_decoded() -> None:
    assert len(sweep.read_needles("00ff10ab\ndeadbeef\n")) == 2


def test_a_sweep_that_read_nothing_is_not_a_pass() -> None:
    with pytest.raises(sweep.NothingRead):
        sweep.sweep({}, NEEDLES, REGISTRY)
    with pytest.raises(sweep.NothingRead):
        sweep.sweep({"cap": ("stdout", b"")}, NEEDLES, REGISTRY)


def test_the_refusal_set_keeps_no_values_and_round_trips() -> None:
    text = REFUSAL.dumps()
    assert "Zelda" not in text and "90210" not in text
    again = sweep.RefusalSet.loads(text)
    assert again.found_in("name Zelda Quinn") and not again.found_in("name Zelda")


def test_scalar_forms_agree_across_types() -> None:
    assert sweep.canonical(7.0) == sweep.canonical(7) == sweep.canonical("7")
    assert sweep.canonical("a   b") == "a b"


def test_cli_exit_meanings(tmp_path: Path) -> None:
    needles, hit, clean = tmp_path / "n.txt", tmp_path / "hit.txt", tmp_path / "clean.txt"
    needles.write_text("qamark0042\n")
    hit.write_text("a qamark0042 b")
    clean.write_text("nothing")
    assert sweep.main(["--needles", str(needles), str(clean)]) == 1  # no match: pass
    assert sweep.main(["--needles", str(needles), str(hit)]) == 0  # match: finding
    assert sweep.main(["--needles", str(needles), str(tmp_path / "gone")]) == 2  # did not run
    empty = tmp_path / "empty.txt"
    empty.write_text("")
    assert sweep.main(["--needles", str(needles), str(empty)]) == 2  # read nothing
    none = tmp_path / "none.txt"
    none.write_text("")
    assert sweep.main(["--needles", str(none), str(hit)]) == 2  # no needles can never pass


PUNCTUATED = [
    ("O'Brien", "customer O'Brien refused", "customer o'brien refused"),
    ("Smith, John", "who: Smith, John.", "who: Smith John"),
    ("(555) 123-4567", "call (555) 123-4567 now", "call 555-123-4567"),
    ("Acme Inc.", "vendor Acme Inc. failed", "vendor Acme Inc failed"),
    ("$1,234.50", "total $1,234.50 bad", "total 1234.50 bad"),
    ("Zelda Quinn", "name zelda quinn", "NAME ZELDA QUINN"),
    (datetime.datetime(2020, 1, 2, 10), "at 2020-01-02T10:00:00", "at 2020-01-02 10:00:00"),
]


@pytest.mark.parametrize(("scalar", "text", "variant"), PUNCTUATED)
def test_the_refusal_set_sees_a_scalar_through_punctuation_case_and_separators(
    scalar: object, text: str, variant: str
) -> None:
    refusal = sweep.RefusalSet.build([scalar])
    assert refusal.found_in(text), text
    assert sweep.sweep({"c": ("stderr", text.encode())}, NEEDLES, REGISTRY, refusal)
    if not isinstance(scalar, datetime.datetime) and scalar != "$1,234.50":
        assert refusal.found_in(variant), variant
    assert not refusal.found_in("nothing here, 12 rows")


def test_a_datetime_matches_with_either_separator() -> None:
    refusal = sweep.RefusalSet.build([datetime.datetime(2020, 1, 2, 10)])
    assert refusal.found_in("2020-01-02 10:00:00") and refusal.found_in("2020-01-02T10:00:00")


def test_domain_and_replace_compare_canonical_forms() -> None:
    src = [{"c": 1234}, {"c": "x"}]
    assert [
        v.kind for v in check_cells("t", {"c": Rule("hash")}, src, [{"c": "1234"}, {"c": "y"}])
    ] == ["same-row"]
    other = [{"c": 5678}, {"c": 1234}]
    found = check_cells("t", {"c": Rule("hash")}, other, [{"c": "9"}, {"c": "5678"}])
    assert [v.kind for v in found] == ["exact-cell"]
    assert check_cells("t", {"c": Rule("fpe")}, [{"c": 7.0}], [{"c": "7"}])


SHORT = ["Bob", "Ann", "O'Neil", 123, "Zoë"]  # the last is NFC; the text below is NFD


@pytest.mark.parametrize(
    ("scalar", "text"),
    [
        ("Bob", "who is bob here"),
        ("Ann", "Ann."),
        ("O'Neil", "customer o'neil refused"),
        (123, "id 123 refused"),
        ("Zoë", "name Zoë refused"),
    ],
)
def test_short_scalars_of_three_characters_are_indexed_as_whole_tokens(
    scalar: object, text: str
) -> None:
    refusal = sweep.RefusalSet.build(SHORT)
    nfd = text.replace("Zoë", "Zoe\u0308")
    assert refusal.found_in(nfd), nfd
    assert sweep.sweep({"c": ("stderr", nfd.encode())}, NEEDLES, REGISTRY, refusal)


def test_tokens_are_whole() -> None:
    refusal = sweep.RefusalSet.build(["Bob"])
    assert not refusal.found_in("Bobby and Bobcat")  # a longer token is not a match


def test_a_text_redact_rule_without_matching_entities_is_refused() -> None:
    src = [{"c": "hi Zelda"}, {"c": "hi Omar"}]
    for rule in (Rule("text_redact"), Rule("text_redact", entities=(("Zelda",),))):
        with pytest.raises(i1_leaks.UnknownStrategy):
            check_cells("t", {"c": rule}, src, src)


CATS = ("Zelda Quinn", "Omar Fry", "Other")


def test_categorical_may_map_a_value_to_itself_or_onto_another_input_category() -> None:
    rule = Rule("categorical", allowed=CATS)
    assert check_cells("t", {"c": rule}, SRC, SRC) == []  # no same-row check
    assert check_cells("t", {"c": rule}, SRC, [{"c": "Omar Fry"}, {"c": "Zelda Quinn"}]) == []
    assert check_cells("t", {"c": rule}, SRC, [{"c": "Other"}, {"c": "Other"}]) == []


def test_categorical_output_outside_the_categories_fails() -> None:
    rule = Rule("categorical", allowed=CATS)
    found = check_cells("t", {"c": rule}, SRC, [{"c": "Zelda Quinn"}, {"c": "invented"}])
    assert [(v.kind, v.coordinate) for v in found] == [("not-allowed", "t/c/1")]


def test_a_non_deterministic_categorical_mapping_fails() -> None:
    rule = Rule("categorical", allowed=CATS)
    src = [{"c": "Omar Fry"}, {"c": "Omar Fry"}, {"c": 7}, {"c": "7"}]
    out = [{"c": "Other"}, {"c": "Zelda Quinn"}, {"c": "Other"}, {"c": "Zelda Quinn"}]
    found = check_cells("t", {"c": rule}, src, out)
    assert [(v.kind, v.coordinate) for v in found] == [
        ("nondeterministic", "t/c/1"),
        ("nondeterministic", "t/c/3"),
    ]


def test_bucketize_checks_the_label_or_bound_form_and_determinism() -> None:
    rule = Rule("bucketize", allowed=("0-9", "10-19", "20"))
    src = [{"c": 3}, {"c": 14}]
    assert check_cells("t", {"c": rule}, src, [{"c": "10-19"}, {"c": "0-9"}]) == []
    assert [v.kind for v in check_cells("t", {"c": rule}, src, [{"c": 3}, {"c": "0-9"}])] == [
        "not-allowed"
    ]
    twice = check_cells("t", {"c": rule}, [{"c": 3}, {"c": 3}], [{"c": "0-9"}, {"c": "20"}])
    assert [v.kind for v in twice] == ["nondeterministic"]


@pytest.mark.parametrize("strategy", ["categorical", "bucketize"])
def test_these_two_need_their_allowed_values(strategy: str) -> None:
    with pytest.raises(i1_leaks.UnknownStrategy):
        check_cells("t", {"c": Rule(strategy)}, SRC, SRC[::-1])


def test_an_empty_refusal_set_reports_empty() -> None:
    assert sweep.RefusalSet.build([]).is_empty()
    assert sweep.RefusalSet.build(["", "...", None]).is_empty()  # no token to index
    assert not sweep.RefusalSet.build(["1", "ab"]).is_empty()  # short values are indexed
    assert not REFUSAL.is_empty()


@pytest.mark.parametrize("refusal", [None, "empty"])
def test_no_needles_and_no_usable_refusal_set_means_not_run(refusal: str | None) -> None:
    ref = sweep.RefusalSet.build([]) if refusal else None
    with pytest.raises(sweep.NothingRead):
        sweep.require_input([b""], ref)
    with pytest.raises(sweep.NothingRead):
        sweep.sweep({"c": ("stdout", b"data")}, (), REGISTRY, ref)
    assert sweep.require_input([b"x"], ref) is None  # one real needle is enough
    assert sweep.require_input([], REFUSAL) is None


def _rotation_with(change: int | None) -> tuple[list[dict], list[dict]]:
    src, _, rotated = _codes()
    out = [dict(r) for r in rotated]
    if change is not None:
        out[change] = {"c": "new"} if change % 2 else {"c": None}
    return src, out


@pytest.mark.parametrize("strategy", ["fpe", "faker"])
@pytest.mark.parametrize("change", [None, 3, 4])
def test_a_near_permutation_with_a_new_value_or_a_null_still_fails(
    strategy: str, change: int | None
) -> None:
    src, out = _rotation_with(change)
    found = check_cells("t", {"c": Rule(strategy, pool=True)}, src, out)
    assert "permutation" in [v.kind for v in found]


def test_a_pooled_faker_returning_other_rows_names_fails() -> None:
    names = [f"Person Number{i}" for i in range(40)]
    src = [{"c": n} for n in names]
    out = [{"c": names[(i * 7 + 1) % 40]} for i in range(40)]  # a shuffle of the same names
    found = check_cells("t", {"c": Rule("faker", pool=True)}, src, out)
    assert [v.kind for v in found if v.kind == "permutation"] == ["permutation"]


def test_an_unpooled_faker_gets_no_swap_check_but_keeps_marker_exact_cell() -> None:
    marked = [{"c": f"qamark{i}"} for i in range(30)]
    found = check_cells("t", {"c": Rule("faker")}, marked, marked[1:] + marked[:1])
    assert {v.kind for v in found} == {"exact-cell"}
    plain = [{"c": f"Person{i}"} for i in range(30)]
    assert check_cells("t", {"c": Rule("faker")}, plain, plain[1:] + plain[:1]) == []


# V1-1: short scalars. A number is one token with its sign and decimal point.
@pytest.mark.parametrize(
    ("scalar", "text"),
    [
        (3.5, "ratio 3.5 here"),
        (-7.25, "delta -7.25 here"),
        ("3.5", "ratio 3.5 here"),
        ("O'Neil", "customer O'Neil refused"),
        ("Zoë", "name Zoe\u0308 refused"),
        ("日本語", "客 日本語 です"),
        (123, "id 123 refused"),
    ],
)
def test_decimals_signed_numbers_and_unicode_are_indexed_and_found(
    scalar: object, text: str
) -> None:
    refusal = sweep.RefusalSet.build([scalar])
    assert not refusal.is_empty()
    assert refusal.found_in(text), text
    assert refusal.contains(scalar)
    assert sweep.sweep({"c": ("stderr", text.encode())}, NEEDLES, REGISTRY, refusal)


@pytest.mark.parametrize(
    ("scalar", "text"),
    [("F", "sex F here"), ("CA", "state: CA."), (0, "count 0 rows"), (-1, "delta -1 now"),
     ("é", "lettre é ici"), ("日本", "a 日本 b")],
)  # fmt: skip
def test_one_and_two_character_values_are_refused_as_whole_tokens(
    scalar: object, text: str
) -> None:
    refusal = sweep.RefusalSet.build([scalar])
    assert not refusal.is_empty()
    assert refusal.found_in(text), text
    assert sweep.sweep({"c": ("stderr", text.encode())}, NEEDLES, REGISTRY, refusal)


@pytest.mark.parametrize(
    ("scalar", "text"),
    [("F", "Fred left"), ("CA", "the CAT sat"), (0, "10 and 100 and 0.5"), ("CA", "ABCA CAB"),
     (-1, "item-1 and 1")],
)  # fmt: skip
def test_the_same_characters_inside_a_longer_word_or_number_are_not_refused(
    scalar: object, text: str
) -> None:
    assert not sweep.RefusalSet.build([scalar]).found_in(text), text


def test_indexing_and_lookup_share_one_tokenizer() -> None:
    assert sweep.words("-7.25 and 3.5, O'Neil 123-4567") == [
        "-7.25", "and", "3.5", "o", "neil", "123", "4567"
    ]  # fmt: skip
    for scalar in (3.5, -7.25, "O'Neil", "(555) 123-4567"):
        refusal = sweep.RefusalSet.build([scalar])
        assert refusal.found_in(sweep.canonical(scalar)), scalar


def test_numeric_only_windows_are_skipped_only_when_asked() -> None:
    refusal = sweep.RefusalSet.build([90210, "Main 90210"])
    assert refusal.found_in("zip 90210") and not refusal.found_in("zip 90210", numeric=False)
    assert refusal.found_in("at Main 90210", numeric=False)


# V1-3: the stored refusal set is versioned and strictly read.
def _stored(**changes: object) -> str:
    import json

    doc = json.loads(REFUSAL.dumps())
    for key, value in changes.items():
        if value is None:
            doc.pop(key, None)
        else:
            doc[key] = value
    return json.dumps(doc)


def test_the_stored_set_is_versioned_and_round_trips() -> None:
    import json

    assert json.loads(REFUSAL.dumps())["schema_version"] == sweep.REFUSAL_VERSION
    again = sweep.RefusalSet.loads(REFUSAL.dumps())
    assert again.dumps() == REFUSAL.dumps()
    assert sweep.RefusalSet.loads(sweep.RefusalSet.build([]).dumps()).is_empty()


GOOD = "ab" * 32


_MALFORMED_STORED = [
    "not json",
    "[]",
    '{"salt": "00", "digests": ["x"], "lengths": []}',  # the old unversioned form
    _stored(schema_version=None),
    _stored(schema_version=2),
    _stored(schema_version=True),
    _stored(schema_version="1"),
    _stored(salt="zz" * 16),
    _stored(salt="ab" * 8),
    _stored(salt=7),
    _stored(groups=[GOOD]),
    _stored(groups={"2": []}),  # a group with no digests: lengths and digests disagree
    _stored(groups={"0": [GOOD]}),
    _stored(groups={"-1": [GOOD]}),
    _stored(groups={"x": [GOOD]}),
    _stored(groups={"2": "oops"}),
    _stored(groups={"2": [GOOD, GOOD]}),
    _stored(groups={"2": ["short"]}),
    _stored(groups={"2": [GOOD.upper()]}),
    _stored(groups={"2": [5]}),
    _stored(extra=1),
]


# The stored texts embed the per-process salt, so the ids are by index. Salted ids differ between
# xdist workers and abort collection.
@pytest.mark.parametrize(
    "text", _MALFORMED_STORED, ids=[f"malformed-{i}" for i in range(len(_MALFORMED_STORED))]
)
def test_a_malformed_stored_set_is_refused_never_read_as_clean(text: str) -> None:
    with pytest.raises(sweep.RefusalSetError) as err:
        sweep.RefusalSet.loads(text)
    assert err.value.__cause__ is None and err.value.__context__ is None
    assert "ab" * 8 not in str(err.value)


def test_the_cli_refuses_a_malformed_stored_set(tmp_path: Path) -> None:
    from scripts.qa import findings

    needles, refusal = tmp_path / "n.txt", tmp_path / "r.json"
    needles.write_text("qamark0042\n")
    refusal.write_text(_stored(groups={"2": []}))
    code = findings.main(
        ["publish", "--root", str(tmp_path), "--pass", "p1", "--needles", str(needles),
         "--refusal", str(refusal), "--no-slack"]
    )  # fmt: skip
    assert code == 1


# V1-9: the output domain is checked even when the source cell is null -------------------------
def _with_null(strategy: str, **kw: object) -> tuple[Rule, list[dict], list[dict]]:
    before = [{"c": "alpha"}, {"c": None}, {"c": "gamma"}]
    return Rule(strategy, **kw), before, [{"c": "x1"}, {"c": "SECRET"}, {"c": "x3"}]  # type: ignore[arg-type]


@pytest.mark.parametrize("strategy", ["categorical", "bucketize"])
def test_a_closed_domain_strategy_refuses_a_value_outside_it_in_a_null_row(strategy: str) -> None:
    rule, before, after = _with_null(strategy, allowed=("x1", "x3", "x9"))
    got = check_cells("t", {"c": rule}, before, after)
    assert [(v.coordinate, v.kind) for v in got] == [("t/c/1", "not-allowed")]
    after[1] = {"c": "x9"}
    assert check_cells("t", {"c": rule}, before, after) == []
    after[1] = {"c": None}  # a null stays null: fine
    assert check_cells("t", {"c": rule}, before, after) == []


def test_a_null_row_must_stay_null_for_hash_even_with_a_fresh_value() -> None:
    rule = Rule("hash")
    before = [{"c": "alpha"}, {"c": None}, {"c": "gamma"}]
    got = check_cells("t", {"c": rule}, before, [{"c": "h1"}, {"c": "gamma"}, {"c": "h3"}])
    assert [(v.coordinate, v.kind) for v in got] == [("t/c/1", "null-row")]
    got = check_cells("t", {"c": rule}, before, [{"c": "h1"}, {"c": "h2"}, {"c": "h3"}])
    assert [(v.coordinate, v.kind) for v in got] == [("t/c/1", "null-row")]
    assert check_cells("t", {"c": rule}, before, [{"c": "h1"}, {"c": None}, {"c": "h3"}]) == []


@pytest.mark.parametrize(
    ("rule", "invented"),
    [
        (Rule("date_shift", range=30), datetime.date(2020, 1, 2)),
        (Rule("fpe"), "1234"),
        (Rule("faker", pool=True), "Alice"),
        (Rule("faker"), "Alice"),
        (Rule("tokenize"), "tok-1"),
        (Rule("redact"), "[REDACTED]"),
        (Rule("truncate", prefix=2), "SE"),
        (Rule("text_redact", entities=(("x",), (), ("y",))), "invented"),
    ],
)
def test_every_other_strategy_keeps_a_null_row_null(rule: Rule, invented: object) -> None:
    before: list[dict] = [{"c": _src(rule, 0)}, {"c": None}, {"c": _src(rule, 2)}]
    ok = [{"c": "z0"}, {"c": None}, {"c": "z2"}]
    if rule.strategy == "date_shift":
        ok = [{"c": datetime.date(2020, 1, 11)}, {"c": None}, {"c": datetime.date(2020, 1, 13)}]
    if rule.strategy == "truncate":
        ok = [{"c": "al"}, {"c": None}, {"c": "ga"}]
    assert check_cells("t", {"c": rule}, before, ok) == [], rule.strategy
    bad = [dict(r) for r in ok]
    bad[1] = {"c": invented}
    got = check_cells("t", {"c": rule}, before, bad)
    assert [(v.coordinate, v.kind) for v in got] == [("t/c/1", "null-row")], rule.strategy


def _src(rule: Rule, row: int) -> object:
    if rule.strategy == "date_shift":
        return datetime.date(2020, 1, 1 + row)
    return ["alpha", "", "gamma"][row]


def test_the_null_row_contract_names_every_strategy_once() -> None:
    assert set(i1_leaks.NULL_ROW) == i1_leaks.KNOWN | {"passthrough"}
    assert {s for s, v in i1_leaks.NULL_ROW.items() if v == "domain"} == i1_leaks.CLOSED
    assert set(i1_leaks.NULL_ROW.values()) == {"null", "domain"}
