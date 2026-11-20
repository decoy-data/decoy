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


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize(
    "planted",
    [
        "row qamark0042 here",
        "token=S3cretValueXYZ",
        "who: Zelda Quinn.",
        "zip 90210",
        "on 2020-01-02",
    ],
)
def test_each_surface_catches_each_planted_value(surface: str, planted: str) -> None:
    blob = planted.encode()
    leaks = sweep.sweep({"cap": (surface, blob)}, NEEDLES, REGISTRY, REFUSAL)
    assert [lk.surface for lk in leaks] == [surface]
    assert planted.split()[-1] not in repr(leaks[0])  # a leak never carries the matched text


@pytest.mark.parametrize("surface", SURFACES)
def test_each_surface_passes_clean_text(surface: str) -> None:
    clean = {"cap": (surface, b"exit 3 after 12 rows, nothing to see")}
    assert sweep.sweep(clean, NEEDLES, REGISTRY, REFUSAL) == []


def test_registry_dispatch_params_and_exceptions_share_entries() -> None:
    assert set(i1_leaks.EXCEPTION_RULES) == set(REGISTRY.exceptions)
    assert set(EXCEPTION_PASS_CASES) == set(REGISTRY.exceptions)
    assert {s.check for s in REGISTRY.surfaces.values()} <= set(sweep.CHECKS)
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


def test_one_and_two_character_scalars_are_exempt_and_tokens_are_whole() -> None:
    refusal = sweep.RefusalSet.build(["Bob", 7, "ab"])
    assert not refusal.found_in("exit 7 and ab")
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
    assert sweep.RefusalSet.build(["1", "ab"]).is_empty()  # nothing long enough was indexed
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
