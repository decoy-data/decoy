"""A `.decoy` finding is reported on the line of the construct that caused it.

The gate fills `GateFinding.position` from `PipelineFile.locate` for loader, schema, compile and
preflight findings. Direct `--json` shows it for loader findings only; `decoy ci` uses it for
every finding. A rule still marked `?` is held back and listed after every schema finding.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy._config_file import load_pipeline
from decoy._source_positions import Position
from decoy.cli.gate import parse_pipeline_yaml, run_config_gate, run_gate

runner = CliRunner()
ENV = {"COLUMNS": "10000"}
MARKER = "SECRET_MARKER_91be"

THREE_PROBLEMS = """decoy 1

pipeline {
  seed 1
  generate g rows 5 to csv("g.csv") { id = sequence(1) }
  mask t from csv("a.csv", header: true) to csv("b.csv") {
    gid <- g.id orphans preserve
    x : nostrategy
    y : redact ?
  }
}
"""

# Lowers cleanly; the engine refuses the extra top-level key, and two rules are marked.
SCHEMA_AND_MARKS = f"""decoy 1

pipeline {{
  seed 42
  options {{ bogus_key: 1 }}

  mask people from csv("./{MARKER}.csv", header: true) to csv("./output.csv") {{
    first_name : faker(person_first_name) ?
    ssn        : redact ?
    keep account_status
  }}
}}
"""

ONLY_MARKS = SCHEMA_AND_MARKS.replace("  options { bogus_key: 1 }\n", "")


def _line_of(text: str, needle: str) -> int:
    """The 1-based line of the first line holding `needle`, found by plain search."""
    return next(i for i, line in enumerate(text.splitlines(), start=1) if needle in line)


def _write(tmp_path: Path, text: str, name: str = "pipeline.decoy") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _validate_json(path: Path, *args: str) -> tuple[int, dict]:
    result = runner.invoke(app, ["validate", *args, str(path), "--json"], env=ENV)
    return result.exit_code, json.loads(result.stdout)


# -- the three loader problems, in source order -----------------------------------------------


def test_three_problems_come_in_source_order_each_on_its_own_line(tmp_path: Path) -> None:
    path = _write(tmp_path, THREE_PROBLEMS)

    code, document = _validate_json(path)

    assert code == 1
    messages = document["messages"]
    assert [m["code"] for m in messages] == [
        "lang.link_needs_namespace",
        "lang.unknown_strategy",
        "lang.unreviewed",
    ]
    assert [m["position"]["line"] for m in messages] == [
        _line_of(THREE_PROBLEMS, "gid <-"),
        _line_of(THREE_PROBLEMS, "nostrategy"),
        _line_of(THREE_PROBLEMS, "redact ?"),
    ]
    assert all(m["position"]["column"] >= 1 for m in messages)


def test_the_config_command_gives_the_same_three(tmp_path: Path) -> None:
    path = _write(tmp_path, THREE_PROBLEMS)

    code, document = _validate_json(path, "config")

    assert code == 1
    assert [m["code"] for m in document["messages"]] == [
        "lang.link_needs_namespace",
        "lang.unknown_strategy",
        "lang.unreviewed",
    ]
    assert all(m["position"]["line"] for m in document["messages"])


def test_the_gate_findings_carry_the_loader_position(tmp_path: Path) -> None:
    path = _write(tmp_path, THREE_PROBLEMS)

    result = run_gate(path)

    assert [f.position.line for f in result.findings] == [
        _line_of(THREE_PROBLEMS, "gid <-"),
        _line_of(THREE_PROBLEMS, "nostrategy"),
        _line_of(THREE_PROBLEMS, "redact ?"),
    ]
    assert all(isinstance(f.position, Position) for f in result.findings)


# -- an engine schema problem beside two marks -------------------------------------------------


def _schema_findings(document: dict) -> list[dict]:
    return [m for m in document["messages"] if m["code"] != "lang.unreviewed"]


def test_a_schema_finding_matches_the_yaml_twin_and_marks_follow(tmp_path: Path) -> None:
    decoy = _write(tmp_path, SCHEMA_AND_MARKS)
    twin_config = load_pipeline(decoy).config
    twin = _write(tmp_path, yaml.safe_dump(twin_config, sort_keys=False), name="twin.yaml")

    decoy_code, decoy_doc = _validate_json(decoy)
    twin_code, twin_doc = _validate_json(twin)

    assert decoy_code == twin_code == 1
    decoy_schema, twin_schema = _schema_findings(decoy_doc), _schema_findings(twin_doc)
    assert decoy_schema and twin_schema
    keep = ("code", "message", "location")
    assert [{k: m.get(k) for k in keep} for m in decoy_schema] == [
        {k: m.get(k) for k in keep} for m in twin_schema
    ]
    codes = [m["code"] for m in decoy_doc["messages"]]
    assert codes[-2:] == ["lang.unreviewed", "lang.unreviewed"]
    assert codes.count("lang.unreviewed") == 2


def test_a_schema_finding_has_a_position_in_the_gate_but_not_in_direct_json(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, SCHEMA_AND_MARKS)

    result = run_gate(path)
    _, document = _validate_json(path)

    schema = [f for f in result.findings if f.code != "lang.unreviewed"]
    assert schema[0].position is not None
    assert schema[0].position.line == _line_of(SCHEMA_AND_MARKS, "bogus_key")
    assert [f.code for f in result.findings][-2:] == ["lang.unreviewed"] * 2
    # Direct JSON keeps the dotted location for an engine finding.
    assert all("position" not in m for m in _schema_findings(document))
    marks = [m for m in document["messages"] if m["code"] == "lang.unreviewed"]
    assert [m["position"]["line"] for m in marks] == [
        _line_of(SCHEMA_AND_MARKS, "person_first_name"),
        _line_of(SCHEMA_AND_MARKS, "redact ?"),
    ]


def test_marks_stop_the_gate_after_the_config_layer(tmp_path: Path) -> None:
    path = _write(tmp_path, ONLY_MARKS)

    for gate in (run_gate, run_config_gate):
        result = gate(path)
        assert result.ran_layers == frozenset({"config"})
        assert result.config is None
        assert [f.code for f in result.findings] == ["lang.unreviewed"] * 2


def test_yaml_findings_keep_their_dotted_location_and_get_no_direct_position(
    tmp_path: Path,
) -> None:
    twin = _write(tmp_path, yaml.safe_dump({"bogus_key": 1, "tables": []}), name="p.yaml")

    _, document = _validate_json(twin)

    assert document["status"] == "error"
    assert all("position" not in m for m in document["messages"])


# -- a file that only has marks ----------------------------------------------------------------


def test_validate_reports_two_marks_and_nothing_else(tmp_path: Path) -> None:
    path = _write(tmp_path, ONLY_MARKS)

    code, document = _validate_json(path)

    assert code == 1
    assert [m["code"] for m in document["messages"]] == ["lang.unreviewed"] * 2


def test_run_refuses_two_marks_before_it_opens_a_source(tmp_path: Path) -> None:
    path = _write(tmp_path, ONLY_MARKS)
    assert not (tmp_path / f"{MARKER}.csv").exists()

    result = runner.invoke(app, ["run", str(path), "--json"], env=ENV)

    assert result.exit_code == 1, result.output
    assert result.output.count("lang.unreviewed") == 2
    # The source path names the marker, so a read of it would show up as a missing-file error.
    assert MARKER not in result.output


def test_tokenize_refuses_a_marked_file_and_names_the_count(tmp_path: Path) -> None:
    path = _write(tmp_path, ONLY_MARKS)

    result = runner.invoke(
        app, ["tokenize", str(path), "--vault", str(tmp_path / "v.db"), "--json"], env=ENV
    )

    assert result.exit_code != 0
    assert "lang.unreviewed" in result.output
    assert "1 more" in result.output
    assert MARKER not in result.output


# -- the parser hands back the file, not a bare mapping ----------------------------------------


def test_parse_pipeline_yaml_returns_the_pipeline_file_and_the_marks(tmp_path: Path) -> None:
    path = _write(tmp_path, ONLY_MARKS)

    pipeline, findings = parse_pipeline_yaml(path)

    assert pipeline is not None
    assert pipeline.config["tables"][0]["name"] == "people"
    assert [f.code for f in findings] == ["lang.unreviewed"] * 2
    assert pipeline.locate("tables[0]").line == _line_of(ONLY_MARKS, "mask people")


def test_parse_pipeline_yaml_returns_none_for_a_file_that_cannot_load(tmp_path: Path) -> None:
    path = _write(tmp_path, THREE_PROBLEMS)

    pipeline, findings = parse_pipeline_yaml(path)

    assert pipeline is None
    assert [f.code for f in findings][:2] == ["lang.link_needs_namespace", "lang.unknown_strategy"]
    assert findings[-1].code == "lang.unreviewed"
