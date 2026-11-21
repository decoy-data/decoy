"""AT-Q1 to AT-Q8: the CLI QA checklist keeps its shape and names an exit code for each command.

`docs/qa/cli-v1-checklist.md` lists 205 checks in 16 groups. This sentry fails on a table row with
the wrong number of cells, an unknown or miscounted exit code, a broken id sequence, a wrong count,
a row-index entry that names no check, a fixture value in a check cell, a DOC-05 that does not point
at the journey, and a run template without the `Exit observed` column.

Seeded mutations (each makes the named test red): drop the Exit cell of one row, or delete a
group's table header (AT-Q1); set an Exit to `7`, or `tbd` on GATE-01 (AT-Q2); add a check row and change the document total to 206 in
the same edit, or duplicate RUN-05 (AT-Q3); remove DOC-05 from row 75's index line (AT-Q4); paste a
fixture address in RUN-01 (AT-Q5); restore DOC-05's old text (AT-Q6); remove the template column
(AT-Q7); give a row two `decoy` spans and one code, or `none` on a row with a `decoy` span (AT-Q8).

The counts are pinned here, apart from the document, so a row and the total that counts it cannot
move together unseen. Moving them is a decision for this file's owner, not a side effect of an edit.

Named limit: a command written outside a backtick span is not counted, so it needs no code; the
grammar of `tests/cli_journey.py` decides what a command span is.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pytest
from tests.cli_journey import allowed_exit_codes, parse_commands

ROOT = Path(__file__).resolve().parents[3]
CHECKLIST = ROOT / "docs" / "qa" / "cli-v1-checklist.md"
RUN_TEMPLATE = ROOT / "docs" / "qa" / "cli-v1-run-template.md"

EXPECTED_CHECKS = 205
EXPECTED_GROUPS = 16
CHECK_HEADER = ("Id", "Command", "Exit", "Expected", "Rows", "Pass/fail")
TEMPLATE_HEADER = ("Id", "Platform", "Exit observed", "Result", "Notes (value-free)")
NUMBER_WORDS = {
    10: "Ten",
    11: "Eleven",
    12: "Twelve",
    13: "Thirteen",
    14: "Fourteen",
    15: "Fifteen",
    16: "Sixteen",
    17: "Seventeen",
    18: "Eighteen",
    19: "Nineteen",
    20: "Twenty",
}

_GROUP_HEADING = re.compile(r"## (\d+)\. ")
_CHECK_ID = re.compile(r"([A-Z]+)-(\d{2})")
_ID_REF = re.compile(r"([A-Z]+-\d{2})(?: to ([A-Z]+-\d{2}))?")
_EXIT_GRAMMAR = re.compile(r"none|tbd|\d+(?:, \d+)*")
_ROW_ID = re.compile(r"\d+[a-z]*")
_NOT_BUILT = "**Not built.**"
_TOTALS = re.compile(r"(\w+) groups, (\d+) checks\.")
# Fixture values the checklist keeps out of its check cells (the fixture table may name them).
_VALUE_PATTERNS = (
    re.compile(r"qamark\d"),
    re.compile(r"@example\.invalid"),
    re.compile(r"QA_SECRET="),
)


@dataclass(frozen=True)
class Check:
    group: int
    id: str
    cells: tuple[str, ...]

    @property
    def command(self) -> str:
        return self.cells[1]

    @property
    def exit(self) -> str:
        return self.cells[2]

    @property
    def expected(self) -> str:
        return self.cells[3]

    @property
    def rows(self) -> str:
        return self.cells[4]


def _cells(line: str) -> tuple[str, ...]:
    return tuple(cell.strip() for cell in line.strip()[1:-1].split(" | "))


def parse_checks(text: str) -> tuple[list[Check], list[tuple[int, str]]]:
    """Every table row under the numbered group headings (so a malformed row is seen), and each table's group and header line.

    Rows are kept whole, so a wrong cell count is a test failure, not a parse error.
    """
    checks: list[Check] = []
    headers: list[tuple[int, str]] = []
    group = 0
    for line in text.splitlines():
        if line.startswith("## "):
            heading = _GROUP_HEADING.match(line)
            group = int(heading.group(1)) if heading else 0
            continue
        if not group or not line.startswith("| "):
            continue
        if line.startswith("| Id |"):
            headers.append((group, line))
        elif not line.startswith("|---"):
            cells = _cells(line)
            checks.append(Check(group, cells[0], cells))
    return checks, headers


def parse_groups_table(text: str) -> dict[int, tuple[str, str]]:
    """Group number to the first and last id its `Ids` cell names."""
    groups: dict[int, tuple[str, str]] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"\| (\d+) \| \[[^\]]+\]\(#[^)]+\) \| (\S+) to (\S+) \| .*\|", line)
        if match:
            groups[int(match.group(1))] = (match.group(2), match.group(3))
    return groups


def parse_row_index(text: str) -> dict[str, set[str]]:
    """Roadmap row to the check ids its row-index line names, ranges expanded."""
    start = text.index("## Row index")
    end = text.index("Rows no check covers", start)
    index: dict[str, set[str]] = {}
    for line in text[start:end].splitlines():
        match = re.fullmatch(r"\| (\d+[a-z]*) \| [^|]+ \| ([^|]+) \|", line)
        if match:
            index[match.group(1)] = set(expand_refs(match.group(2)))
    return index


def expand_refs(cell: str) -> list[str]:
    """Ids named in `cell`, with `A-01 to A-05` expanded to every id between them."""
    found: list[str] = []
    for first, last in _ID_REF.findall(cell):
        if not last:
            found.append(first)
            continue
        prefix, low = first.rsplit("-", 1)
        last_prefix, high = last.rsplit("-", 1)
        assert prefix == last_prefix, f"range {first} to {last} crosses a prefix"
        found += [f"{prefix}-{n:02d}" for n in range(int(low), int(high) + 1)]
    return found


def exit_problems(check: Check) -> list[str]:
    """Why `check`'s Exit cell does not fit its Command and Expected cells; empty when it fits."""
    code = check.exit
    if not _EXIT_GRAMMAR.fullmatch(code):
        return [f"{check.id}: Exit must be `none`, `tbd` or integers separated by ', '"]
    spans = parse_commands(check.command, installer=True)
    if code == "tbd":
        if not check.expected.startswith(_NOT_BUILT):
            return [f"{check.id}: `tbd` is only for a check marked Not built"]
        return []
    if code == "none":
        return [f"{check.id}: Exit `none` with {len(spans)} command span(s)"] if spans else []
    codes = code.split(", ")
    unknown = [c for c in codes if int(c) not in allowed_exit_codes()]
    problems = [f"{check.id}: exit {c} is not in decoy.cli.exit_codes" for c in unknown]
    if len(codes) != len(spans):
        problems.append(f"{check.id}: {len(codes)} exit code(s) for {len(spans)} command span(s)")
    return problems


@pytest.fixture(scope="module")
def text() -> str:
    return CHECKLIST.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def checks(text: str) -> list[Check]:
    return parse_checks(text)[0]


# ---- AT-Q1 ----------------------------------------------------------------------------------


def test_check_tables_have_six_cells(text: str, checks: list[Check]) -> None:
    _, headers = parse_checks(text)
    assert [group for group, _ in headers] == list(range(1, EXPECTED_GROUPS + 1)), (
        "each group needs exactly one check table"
    )
    for _, header in headers:
        assert _cells(header) == CHECK_HEADER, header
    short = [c.id for c in checks if len(c.cells) != len(CHECK_HEADER)]
    assert not short, f"rows without six cells: {short}"
    assert all(c.cells[5] == "" for c in checks), "Pass/fail stays blank in the checklist"
    bad = [c.id for c in checks if not _CHECK_ID.fullmatch(c.id)]
    assert not bad, f"rows whose first cell is not a check id: {bad}"


def test_separator_rows_match_the_header(text: str) -> None:
    lines = text.splitlines()
    heads = [n for n, line in enumerate(lines) if line.startswith("| Id | Command |")]
    assert len(heads) == EXPECTED_GROUPS
    for number in heads:
        assert lines[number + 1] == "|" + "---|" * len(CHECK_HEADER), number + 1


# ---- AT-Q2 and AT-Q8 ------------------------------------------------------------------------


def test_exit_cells_parse(checks: list[Check]) -> None:
    problems = [p for c in checks for p in exit_problems(c) if "span(s)" not in p]
    assert not problems, problems


def test_one_exit_per_command(checks: list[Check]) -> None:
    problems = [p for c in checks for p in exit_problems(c) if "span(s)" in p]
    assert not problems, problems


def test_exit_rules_catch_each_malformed_cell() -> None:
    def check(command: str, code: str, expected: str = "Fine") -> Check:
        return Check(1, "XX-01", ("XX-01", command, code, expected, "1", ""))

    assert not exit_problems(check("`decoy run a`", "0"))
    assert not exit_problems(check("`decoy run a`, then `decoy run b`", "0, 3"))
    assert not exit_problems(check("Read the file", "none"))
    assert not exit_problems(check("Read the file", "tbd", "**Not built.** Later"))
    assert exit_problems(check("`decoy run a`", "7"))
    assert exit_problems(check("`decoy run a`, then `decoy run b`", "0"))
    assert exit_problems(check("`decoy run a`", "none"))
    assert exit_problems(check("`decoy run a`", "tbd"))
    assert exit_problems(check("`decoyx run a`", "0"))
    assert exit_problems(check("Read the file", "0 and 1"))


# ---- AT-Q3 ----------------------------------------------------------------------------------


def test_ids_and_counts(text: str, checks: list[Check]) -> None:
    assert len(checks) == EXPECTED_CHECKS
    totals = _TOTALS.search(text)
    assert totals, "the document states no total"
    assert (totals.group(1), int(totals.group(2))) == (
        NUMBER_WORDS[EXPECTED_GROUPS],
        EXPECTED_CHECKS,
    )
    groups = parse_groups_table(text)
    assert sorted(groups) == list(range(1, EXPECTED_GROUPS + 1))
    assert sorted({c.group for c in checks}) == sorted(groups)

    ids = [c.id for c in checks]
    assert not [i for i, n in Counter(ids).items() if n > 1], "duplicate ids"
    for number, (first, last) in groups.items():
        own = [c.id for c in checks if c.group == number]
        prefix, low = first.rsplit("-", 1)
        _, high = last.rsplit("-", 1)
        want = [f"{prefix}-{n:02d}" for n in range(int(low), int(high) + 1)]
        assert own == want, f"group {number}: the Groups table says {first} to {last}"


# ---- AT-Q4 ----------------------------------------------------------------------------------


def test_row_index_names_real_checks(text: str, checks: list[Check]) -> None:
    index = parse_row_index(text)
    assert index, "no row-index lines parsed"
    known = {c.id for c in checks}
    for row, named in index.items():
        assert named <= known, f"row {row} names unknown checks {sorted(named - known)}"
    for check in checks:
        for row in (r.strip() for r in check.rows.split(",")):
            assert _ROW_ID.fullmatch(row), f"{check.id}: Rows cell holds {row!r}"
            assert row in index, f"{check.id} lists row {row}, which has no index line"
            assert check.id in index[row], f"row {row}'s index line does not name {check.id}"


# ---- AT-Q5 ----------------------------------------------------------------------------------


def test_check_cells_are_value_free(checks: list[Check]) -> None:
    hits = [
        f"{c.id}: {pattern.pattern}"
        for c in checks
        for cell in c.cells
        for pattern in _VALUE_PATTERNS
        if pattern.search(cell)
    ]
    assert not hits, hits


# ---- AT-Q6 and AT-Q7 ------------------------------------------------------------------------


def test_doc05_points_at_the_journey(checks: list[Check]) -> None:
    doc05 = next(c for c in checks if c.id == "DOC-05")
    assert "(cli-v1-journey.md)" in doc05.expected
    assert _NOT_BUILT not in doc05.expected
    assert doc05.exit != "tbd"


def test_run_template_has_exit_column() -> None:
    template = RUN_TEMPLATE.read_text(encoding="utf-8")
    results = template[template.index("## Results") :]
    header = next(line for line in results.splitlines() if line.startswith("| Id |"))
    assert _cells(header) == TEMPLATE_HEADER
