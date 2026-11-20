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


def test_a_domain_strategy_may_reuse_a_domain_value() -> None:
    assert check_cells("t", {"c": Rule("categorical")}, SRC, SRC[::-1]) == []


def test_an_unknown_strategy_is_refused_not_passed() -> None:
    with pytest.raises(i1_leaks.UnknownStrategy):
        check_cells("t", {"c": Rule("made_up")}, SRC, SRC)


def test_the_marker_kept_by_a_replacing_strategy_on_stdout_is_a_leak() -> None:
    leaks = sweep.sweep({"o": ("stdout", b"qamark0042")}, NEEDLES, REGISTRY)
    assert leaks == [sweep.Leak("stdout", "o", "n0")]


def test_a_hex_secret_also_matches_as_raw_bytes() -> None:
    needles = sweep.read_needles("00ff10ab\n")
    assert sweep.hits(bytes.fromhex("00ff10ab"), needles) == [1]


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
