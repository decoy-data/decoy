"""AT-J1 to AT-J5, AT-J10, AT-J11 and AT-J13: the CLI journey document and its citations agree.

`docs/qa/cli-v1-journey.md` defines steps CJ-01 to CJ-NN. This sentry fails when the document
breaks its format, when a step is not cited by exactly one journey test, when a cited id does not
exist, when an exit code is not in `decoy.cli.exit_codes`, when a step that is not on main is not a
strict expected failure, or when a step lists a different number of commands and exit codes.

Seeded mutations (each makes the named test red): delete the pre-scan step (AT-J1); add a stray
token after an Exit value (AT-J1); remove `@journey_step("CJ-04")` (AT-J2); cite `CJ-99` in
`tests/e2e/test_release_smoke.py` (AT-J3); set CJ-05's Exit to `7`, or hard-code the exit set in
`tests/cli_journey.py` (AT-J4); drop `strict=True` in the decorator (AT-J5); write
`assert r.returncode == 0` in the journey module (AT-J10); remove a decorator from the release
smoke (AT-J11); give CJ-10 two commands and Exit `0`, or count a `decoyx run` span (AT-J13).

Named limit: an id built at run time is not read; the scanner reads literal ids only and flags a
call whose id is not a string literal.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest
from tests import cli_journey
from tests.cli_journey import (
    BASELINE_STAGES,
    JourneyDocError,
    JourneyStep,
    allowed_exit_codes,
    parse_commands,
    parse_journey,
    read_journey,
)

from decoy.cli import exit_codes

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / "tests"
JOURNEY_TESTS = TESTS / "e2e" / "first_user" / "journey"
RELEASE_SMOKE = TESTS / "e2e" / "test_release_smoke.py"
HELPER = TESTS / "cli_journey.py"
NOT_A_LITERAL = "<not a string literal>"


def _step_block(extra: str = "", exit_value: str = "0") -> str:
    return (
        "### CJ-01: One\n\n**Stage:** install\n\n**Command:** `decoy --version`\n\n"
        f"**Exit:** {exit_value}\n\n**Expected:** Prints a version.\n\n**Lands with:** main\n{extra}"
    )


# ---- AST scanner for journey_step citations ----------------------------------------------------


def cited_ids(source: str) -> list[str]:
    """Ids passed to `journey_step`, including an import alias and the attribute form."""
    tree = ast.parse(source)
    names = {"journey_step"}
    modules = {"cli_journey"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names |= {a.asname for a in node.names if a.name == "journey_step" and a.asname}
            modules |= {a.asname for a in node.names if a.name == "cli_journey" and a.asname}
        elif isinstance(node, ast.Import):
            modules |= {a.asname for a in node.names if a.asname}
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_call = (isinstance(func, ast.Name) and func.id in names) or (
            isinstance(func, ast.Attribute)
            and func.attr == "journey_step"
            and isinstance(func.value, ast.Name)
            and func.value.id in modules
        )
        if not is_call:
            continue
        arg = node.args[0] if node.args else None
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            found.append(arg.value)
        else:
            found.append(NOT_A_LITERAL)
    return found


def _cited_in(paths: list[Path]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for path in paths:
        counts.update(cited_ids(path.read_text(encoding="utf-8")))
    return counts


def _all_test_files() -> list[Path]:
    return sorted(p for p in TESTS.rglob("*.py") if p != HELPER and "__pycache__" not in p.parts)


# ---- AT-J1: the document shape -----------------------------------------------------------------


def test_journey_doc_shape() -> None:
    steps = read_journey()
    expected_ids = [f"CJ-{n:02d}" for n in range(1, len(steps) + 1)]
    assert [s.id for s in steps] == expected_ids, "ids must be CJ-01.. contiguous and unique"
    stages = {s.stage for s in steps}
    assert set(BASELINE_STAGES) <= stages, (
        f"baseline stages without a step: {set(BASELINE_STAGES) - stages}"
    )


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        (_step_block("\n**Owner:** me\n"), "unknown label"),
        (_step_block(exit_value="0 extra"), "Exit must be"),
        (_step_block(exit_value="0,1"), "Exit must be"),
        (_step_block("\n**Stage:** mask\n"), "appears twice"),
        (_step_block().replace("**Expected:** Prints a version.\n\n", ""), "missing or empty"),
        (_step_block().replace("**Stage:** install", "**Stage:** nowhere"), "stage is not"),
        (_step_block().replace("main", "later"), "Lands with"),
        (_step_block().replace("`decoy --version`", "`decoyx --version`"), "no `decoy"),
        (_step_block("\nfree prose\n"), "labelled lines"),
    ],
)
def test_parser_refuses_a_malformed_document(text: str, fragment: str) -> None:
    with pytest.raises(JourneyDocError, match=fragment):
        parse_journey(text)


def test_parser_reads_a_well_formed_step() -> None:
    (step,) = parse_journey(_step_block(exit_value="0"))
    assert step == JourneyStep(
        "CJ-01", "One", "install", ("decoy --version",), (0,), "Prints a version.", "main"
    )


# ---- AT-J2, AT-J3: citations in both directions ------------------------------------------------


def test_every_journey_id_is_cited() -> None:
    files = sorted(JOURNEY_TESTS.glob("*.py"))
    assert files, "tests/e2e/first_user/journey/ holds no test module"
    counts = _cited_in(files)
    ids = {s.id for s in read_journey()}
    assert {i: counts[i] for i in sorted(ids) if counts[i] != 1} == {}, (
        "each id is cited exactly once"
    )


def test_every_cited_id_exists() -> None:
    ids = {s.id for s in read_journey()}
    unknown = {i for i in _cited_in(_all_test_files()) if i not in ids}
    assert unknown == set(), "journey_step names an id the document does not define"


def test_scanner_reads_every_citation_form() -> None:
    source = (
        "from tests.cli_journey import journey_step as js\n"
        "from tests import cli_journey\n"
        "from tests.cli_journey import journey_step\n"
        "@js('CJ-01')\ndef a(): pass\n"
        "@cli_journey.journey_step('CJ-02')\ndef b(): pass\n"
        "@journey_step('CJ-03')\ndef c(): pass\n"
        "@journey_step(name)\ndef d(): pass\n"
    )
    assert sorted(cited_ids(source)) == sorted(["CJ-01", "CJ-02", "CJ-03", NOT_A_LITERAL])
    assert NOT_A_LITERAL not in {s.id for s in read_journey()}


# ---- AT-J4: exits are registered ---------------------------------------------------------------


def test_exit_tokens_are_registered() -> None:
    allowed = allowed_exit_codes()
    bad = {(s.id, code) for s in read_journey() for code in s.exits if code not in allowed}
    assert bad == set()


def test_allowed_exit_set_is_what_the_registry_gives() -> None:
    named = {getattr(exit_codes, n) for n in exit_codes.__all__ if n.startswith("EXIT_")}
    assert allowed_exit_codes() == frozenset(named | set(exit_codes.RUN_EXIT_MAP.values()))
    assert all(isinstance(code, int) for code in allowed_exit_codes())


def test_helper_copies_no_exit_integer() -> None:
    tree = ast.parse(HELPER.read_text(encoding="utf-8"))
    literals = {
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, int)
        and not isinstance(n.value, bool)
    }
    assert literals <= {0, 1}, "tests/cli_journey.py holds an integer other than an index"


# ---- AT-J5: a step that is not on main is a strict expected failure ----------------------------


def _fake_steps(lands_with: str) -> tuple[JourneyStep, ...]:
    return (JourneyStep("CJ-01", "t", "install", ("decoy x",), (0,), "e", lands_with),)


def _marks(test: object) -> list[pytest.Mark]:
    return list(getattr(test, "pytestmark", []))


def test_unbuilt_steps_are_strict_xfail(monkeypatch: pytest.MonkeyPatch) -> None:
    def probe() -> None:  # pragma: no cover - never run
        pass

    monkeypatch.setattr(cli_journey, "read_journey", lambda: _fake_steps("row 61"))
    (mark,) = [m for m in _marks(cli_journey.journey_step("CJ-01")(probe)) if m.name == "xfail"]
    assert mark.kwargs["strict"] is True

    def probe_main() -> None:  # pragma: no cover - never run
        pass

    monkeypatch.setattr(cli_journey, "read_journey", lambda: _fake_steps("main"))
    assert [
        m for m in _marks(cli_journey.journey_step("CJ-01")(probe_main)) if m.name == "xfail"
    ] == []


def test_the_document_marks_unbuilt_steps_with_a_row() -> None:
    for step in read_journey():
        assert step.on_main or step.lands_with.startswith("row "), step.id


# ---- AT-J10: the journey module reads its exits from the document ------------------------------


def returncode_literal_comparisons(source: str) -> list[int]:
    """Line numbers where an exit status is compared with an integer literal."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        names = {
            o.attr if isinstance(o, ast.Attribute) else o.id
            for o in operands
            if isinstance(o, ast.Attribute | ast.Name)
        }
        has_int = any(
            isinstance(o, ast.Constant)
            and isinstance(o.value, int)
            and not isinstance(o.value, bool)
            for o in operands
        )
        if has_int and names & {"returncode", "exit_code", "exit_codes", "codes"}:
            found.append(node.lineno)
    return found


def test_journey_module_reads_exits_from_doc() -> None:
    files = sorted(JOURNEY_TESTS.glob("*.py"))
    assert files
    for path in files:
        assert returncode_literal_comparisons(path.read_text(encoding="utf-8")) == [], path.name


def test_exit_literal_scanner_sees_a_literal() -> None:
    assert returncode_literal_comparisons("assert r.returncode == 0\n")
    assert returncode_literal_comparisons("assert 3 == result.exit_code\n")
    assert not returncode_literal_comparisons("assert r.returncode == step.exits[0]\n")


# ---- AT-J11: the release smoke cites the journey -----------------------------------------------


def test_release_smoke_cites_journey() -> None:
    cited = set(cited_ids(RELEASE_SMOKE.read_text(encoding="utf-8")))
    assert {"CJ-01", "CJ-08"} <= cited


# ---- AT-J13: one exit code per command ---------------------------------------------------------


def test_one_exit_per_command() -> None:
    off = {
        s.id: (len(s.commands), len(s.exits))
        for s in read_journey()
        if len(s.commands) != len(s.exits)
    }
    assert off == {}


def test_command_parser_is_anchored() -> None:
    text = "`decoy run a` then `decoyx run b`, `--json`, `pipelines/x.yaml`, and `decoy`"
    assert parse_commands(text) == ["decoy run a", "decoy"]
    installer = "`NAME=v sh install.sh --yes` and `install.ps1` and `sh install.sh.bak`"
    assert parse_commands(installer) == []
    assert parse_commands(installer, installer=True) == [
        "NAME=v sh install.sh --yes",
        "install.ps1",
    ]
