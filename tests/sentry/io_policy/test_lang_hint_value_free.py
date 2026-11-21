"""A `.decoy` hint never repeats a table or `let` name the user declared.

Hints reach `decoy validate` text, `validate --json` and `run --json`, and from there logs. Two
programs each declare a distinctive identifier (a table, a `let`) and misspell it by one character.
Five outputs must refuse the program and none may print the declared identifier as a suggestion.
Suggestions come from the strategy registry or are fixed text.
"""

from __future__ import annotations

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
