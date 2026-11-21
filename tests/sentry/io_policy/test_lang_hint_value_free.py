"""A `.decoy` hint never repeats an identifier the user wrote.

Hints reach `decoy validate` text, `validate --json` and `run --json`, and from there logs. A hint
may name a language word, a strategy, a generator or a connector, never a table, a `let` or a
column of the user's. Two checks hold that: a run of each command on a program whose near-miss
target is a distinctive user identifier, and a scan that every hint the language can build comes
from a registry. A new dynamic hint site fails the scan until it is added here on purpose.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app

LANG = Path(__file__).resolve().parents[3] / "src" / "decoy" / "lang"
PROGRAM = (
    Path(__file__).resolve().parents[2] / "unit" / "lang" / "twins" / "minimal.decoy"
).read_text(encoding="utf-8")

TABLE_MARK = "ZQtablemark"
LET_MARK = "ZQletmark"

# Each case declares a user identifier and then misspells it by one character.
CASES = {
    "table": PROGRAM.replace("mask people", f"mask {TABLE_MARK}").replace(
        "  }\n}",
        "  }\n"
        '  mask other from csv("./o.csv", header: true) to csv("./p.csv") {\n'
        f"    other_id <- {TABLE_MARK[:-1]}x.id orphans preserve\n    keep a\n  }}\n}}",
    ),
    "let": PROGRAM.replace("seed 42", f"seed 42\n  let {LET_MARK} = hash").replace(
        "ssn        : redact", f"ssn        : {LET_MARK[:-1]}x"
    ),
}
MARKS = {"table": TABLE_MARK, "let": LET_MARK}

# Hint expressions built from more than a fixed string, each from a registry or language word.
DYNAMIC_HINTS = {
    "'use one of: ' + ', '.join(sorted(CONNECTORS))",
    "f'write `{word}(...)`' if bare else 'for a computed column do not start with a generator'",
    "f'did you mean `{close[0]}`?'",
    "f'did you mean `{close[0]}`?' if close else None",
    "f'use {COLUMN_SYNTAX[key]}'",
    "f'use {SETTING_SYNTAX[key]}'",
    "f'use {BLOCK_SYNTAX[key]}'",
    "hint",  # a hint built elsewhere: _errors.diagnostic passes it, _parse and _validate build it
    "ORPHAN_HINT",
}
# The candidates a "did you mean" may pick from. Never user declarations.
SUGGESTION_POOLS = {"sorted(generators())", "sorted(_strategies())"}

runner = CliRunner()


def _outputs(path: Path) -> list[str]:
    env = {"COLUMNS": "10000"}
    argvs = [
        ["validate", "config", str(path)],
        ["validate", "config", str(path), "--json"],
        ["validate", str(path)],
        ["validate", str(path), "--json"],
        ["run", str(path), "--json"],
    ]
    return [runner.invoke(app, argv, env=env).output for argv in argvs]


@pytest.mark.parametrize("kind", sorted(CASES))
def test_no_command_prints_a_declared_identifier_as_a_suggestion(kind: str, tmp_path: Path) -> None:
    path = tmp_path / "pipeline.decoy"
    path.write_text(CASES[kind], encoding="utf-8")

    outputs = _outputs(path)

    assert any("lang." in out for out in outputs), outputs  # the misspelling was refused
    for out in outputs:
        assert MARKS[kind] not in out
    for out in outputs[1::2][:2]:
        for message in json.loads(out).get("messages", []):
            assert MARKS[kind] not in message.get("hint", "")


def _hint_args() -> list[tuple[str, int, str]]:
    found = []
    for source in sorted(LANG.glob("*.py")):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in {"fail", "diagnostic"}:
                if len(node.args) >= 3 and not isinstance(node.args[2], ast.Constant):
                    found.append((source.name, node.lineno, ast.unparse(node.args[2])))
    return found


def test_every_dynamic_hint_is_a_known_registry_site() -> None:
    unknown = [site for site in _hint_args() if site[2] not in DYNAMIC_HINTS]

    assert unknown == []


def test_every_suggestion_is_picked_from_a_registry() -> None:
    pools = []
    for source in sorted(LANG.glob("*.py")):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and "get_close_matches" in ast.unparse(node.func):
                pools.append(ast.unparse(node.args[1]))

    assert pools and set(pools) <= SUGGESTION_POOLS
