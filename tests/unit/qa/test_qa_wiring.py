"""AT-11 and the AT-13 sentries: one sweep, and the publication and Slack paths stay in findings.py.

The scans are syntax-tree walks over string constants and imports, so a moved path or an aliased
import is still seen. Planted snippets prove each scan finds what it claims to.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
QA = ROOT / "scripts" / "qa"
JOURNEY = ROOT / "tests/e2e/first_user/journey/test_cli_journey.py"
CHECKLIST = ROOT / "docs/qa/cli-v1-checklist.md"


def _modules() -> list[Path]:
    return sorted(p for p in QA.rglob("*.py") if "__pycache__" not in p.parts)


def records_or_slack(source: str) -> list[str]:
    """Where code names `docs/records` or Slack, other than in a docstring."""
    tree = ast.parse(source)
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Module | ast.FunctionDef | ast.ClassDef)
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    found = []
    for node in ast.walk(tree):
        text = ""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = "" if id(node) in docstrings else node.value
        elif isinstance(node, ast.Name | ast.Attribute | ast.alias | ast.arg):
            text = getattr(node, "id", getattr(node, "attr", getattr(node, "name", "")))
        low = text.lower()
        if "slack" in low or "docs/records" in low or low == "records":
            found.append(f"{getattr(node, 'lineno', 0)}")
    return found


@pytest.mark.parametrize(
    "snippet",
    [
        "p = 'docs/records/x.md'",
        "p = root / 'docs' / 'records'",
        "run(['slack-notify.sh'])",
        "import slack_sdk",
        "from x import post_to_slack",
        "SLACK = 1",
    ],
)
def test_the_scan_sees_each_spelling(snippet: str) -> None:
    assert records_or_slack(snippet), snippet


def test_the_scan_ignores_docstrings_and_other_text() -> None:
    assert (
        records_or_slack('"""Notes on Slack."""\ndef f():\n    """docs/records"""\nx = "ok"') == []
    )


def test_only_findings_publish_writes_records_or_calls_slack() -> None:
    offenders = {
        p.relative_to(ROOT).as_posix(): lines
        for p in _modules()
        if p != QA / "findings.py" and (lines := records_or_slack(p.read_text(encoding="utf-8")))
    }
    assert offenders == {}, "route this through scripts/qa/findings.py publish"
    assert records_or_slack((QA / "findings.py").read_text(encoding="utf-8"))  # the scan sees it


def test_the_journey_calls_the_one_sweep_and_has_no_second_implementation() -> None:
    source = JOURNEY.read_text(encoding="utf-8")
    assert "from scripts.qa import sweep as qa_sweep" in source
    assert "qa_sweep.sweep(" in source
    tree = ast.parse(source)
    sweeper = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_sweep"
    )
    loops = [
        n
        for n in ast.walk(sweeper)
        if isinstance(n, ast.Compare) and any(isinstance(o, ast.In) for o in n.ops)
    ]
    assert loops == [], "the journey must not match needles itself"


def test_the_checklist_sweep_step_calls_the_one_sweep() -> None:
    text = CHECKLIST.read_text(encoding="utf-8")
    assert "python -m scripts.qa.sweep --needles data/markers.txt" in text
    assert "grep -rFf" not in text


COLLECTION = ("set", "frozenset", "dict", "Mapping", "Collection", "Sequence", "list", "tuple")
COLLECTION_CALLS = {"set", "frozenset", "dict", "list", "tuple", "Counter", "defaultdict"}
TEXT_CALLS = {"casefold", "lower", "upper", "decode", "encode", "str"}


def _collection_names(tree: ast.AST) -> set[str]:
    """Names that hold a collection of values, so `x in names` is set membership, not text search."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.arg | ast.AnnAssign):
            note = node.annotation
            target = node.arg if isinstance(node, ast.arg) else getattr(node.target, "id", "")
            if note is not None and ast.unparse(note).startswith(COLLECTION):
                names.add(target)
        elif isinstance(node, ast.Assign):
            value = node.value
            kind = isinstance(
                value, ast.Set | ast.SetComp | ast.Dict | ast.DictComp | ast.List | ast.Tuple
            )
            kind = kind or (isinstance(value, ast.BinOp) and isinstance(value.op, ast.BitOr))
            fn = value.func if isinstance(value, ast.Call) else None
            kind = kind or (isinstance(fn, ast.Name) and fn.id in COLLECTION_CALLS)
            if kind:
                names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


REGEX_MODULES = {"re", "regex"}
REGEX_MATCHERS = {"search", "match", "fullmatch", "findall", "finditer"}


def _regex_names(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Local names bound to a regex module, and local names bound to one of its matchers.

    `import re as regex` gives `regex` as a module name, and `from re import search as s` gives
    `s` as a matcher name, so the spelling cannot hide a call.
    """
    modules: set[str] = set()
    matchers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {a.asname or a.name for a in node.names if a.name in REGEX_MODULES}
        elif isinstance(node, ast.ImportFrom) and node.module in REGEX_MODULES:
            matchers |= {a.asname or a.name for a in node.names if a.name in REGEX_MATCHERS}
    return modules, matchers


def _is_regex_call(node: ast.Call, modules: set[str], matchers: set[str]) -> bool:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id in matchers
    if not isinstance(fn, ast.Attribute) or fn.attr not in REGEX_MATCHERS:
        return False
    owner = fn.value
    if isinstance(owner, ast.Name):
        return owner.id in modules
    # `re.compile(p).search(text)`: the matcher hangs off a compile call.
    return (
        isinstance(owner, ast.Call)
        and isinstance(owner.func, ast.Attribute)
        and owner.func.attr == "compile"
        and isinstance(owner.func.value, ast.Name)
        and owner.func.value.id in modules
    )


def inline_text_matches(source: str) -> list[int]:
    """Lines where an invariant searches text for a value itself instead of calling the sweep.

    Covered shapes: `x in text.casefold()` (a text-method call on the right), `str(x) in y`,
    `x in <name>` for a name that is not known to hold a collection, `text.find(x)`,
    `re.search/match/fullmatch/findall(...)`, and `.__contains__(x)`. A constant on the left, such
    as `'\\n' in text`, is exempt. A set or dict held in a name (a parameter annotated `set[...]`,
    a set comprehension, `frozenset(...)`) is set membership and is exempt.

    Matching needles, cells or entities in text belongs to `scripts/qa/sweep.py`. A second matcher
    in an invariant is how `Bob` came to flag `Bobby`.
    """
    tree = ast.parse(source)
    known = _collection_names(tree)
    modules, matchers = _regex_names(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and any(
            isinstance(o, ast.In | ast.NotIn) for o in node.ops
        ):
            left, right = node.left, node.comparators[-1]
            if isinstance(left, ast.Constant):
                continue
            as_text = isinstance(right, ast.Call) and getattr(right.func, "attr", "") in TEXT_CALLS
            as_name = isinstance(right, ast.Name) and right.id not in known
            as_str = isinstance(left, ast.Call) and getattr(left.func, "id", "") == "str"
            if as_text or as_name or as_str:
                found.append(node.lineno)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"find", "__contains__"}:
                found.append(node.lineno)
            elif _is_regex_call(node, modules, matchers):
                found.append(node.lineno)
    return found


@pytest.mark.parametrize(
    "snippet",
    [
        "any(c in text.casefold() for c in cells)",
        "x = c in text",
        "ok = needle not in blob",
        "bad = e in str(after).lower()",
        "hit = n in data.decode()",
        "hit = str(n) in other",
        "hit = n in other",
        "pos = text.find(cell)",
        "import re\nhit = re.search(cell, text)",
        "import re\nhit = re.match(cell, text)",
        "hit = text.__contains__(cell)",
        "import re as regex\nhit = regex.search(cell, text)",
        "import re as r\nhit = r.findall(cell, text)",
        "from re import search\nhit = search(cell, text)",
        "from re import fullmatch as fm\nhit = fm(cell, text)",
        "import re\nhit = re.compile(cell).search(text)",
        "import regex\nhit = regex.match(cell, text)",
    ],
)
def test_the_inline_match_scan_sees_each_spelling(snippet: str) -> None:
    assert inline_text_matches(snippet), snippet


@pytest.mark.parametrize(
    "snippet",
    [
        "x = '\\n' in text",
        "def f(seen: set[str]):\n    return k in seen",
        "def f(cfg: Mapping[str, int]):\n    return k in cfg",
        "have = {k for k in rows}\nok = key not in have",
        "kinds = frozenset({'a'})\nok = kind in kinds",
        "ok = kind in {'a', 'b'}",
        "ok = kind in KNOWN | {'x'}",
        "import re as regex\nPAT = regex.compile('x')\nok = PAT.search(msg)",
        "from re import compile\nPAT = compile('x')",
    ],
)
def test_the_inline_match_scan_leaves_set_membership_alone(snippet: str) -> None:
    assert inline_text_matches(snippet) == [], snippet


def test_no_invariant_matches_needles_or_cells_in_text_itself() -> None:
    offenders = {
        p.relative_to(ROOT).as_posix(): lines
        for p in sorted((QA / "invariants").glob("*.py"))
        if (lines := inline_text_matches(p.read_text(encoding="utf-8")))
    }
    assert offenders == {}, "use scripts/qa/sweep.py"
    i7 = (QA / "invariants" / "i7_errors.py").read_text(encoding="utf-8")
    assert "from scripts.qa.sweep import" in i7 and "sweep(captures" in i7
