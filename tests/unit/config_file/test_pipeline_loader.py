"""The pipeline loader reads a `.yaml`, `.yml` or `.decoy` file into one `PipelineFile`.

Plan: docs/plans/2026-11-19-decoy-language-commands.md, slice S1. The YAML codes and texts are
pinned in `test_config_file.py`; this file covers the `.decoy` kind, the kind rule, the review
marks, and that no problem quotes the file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy._config_file import (
    PIPELINE_SUFFIXES,
    ConfigFileError,
    config_refusal,
    is_decoy_path,
    load_config_mapping,
    load_pipeline,
    read_config_text,
    read_decoy_text,
)
from decoy.cli.completers import _config_paths
from decoy.cli.io._pipelines import looks_like_path

MARKER = "SECRET_MARKER_5d1c"
TWIN = Path(__file__).parent.parent / "lang" / "twins" / "minimal.decoy"
PROGRAM = TWIN.read_text(encoding="utf-8")
# The marker rides in a path value: a message may name a strategy or a table, never a value.
WITH_VALUE = PROGRAM.replace("./input.csv", f"./{MARKER}.csv")
BAD_STRATEGY = WITH_VALUE.replace("ssn        : redact", "ssn        : redcat")
SYNTAX = WITH_VALUE.replace("pipeline {", "pipeline { (")
MARKED = WITH_VALUE.replace("ssn        : redact", "ssn        : redact ?").replace(
    "email      : faker(person_email)", "email      : faker(person_email) ?"
)


def _decoy(tmp_path: Path, text: str | bytes, name: str = "pipeline.decoy") -> Path:
    path = tmp_path / name
    path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    return path


def _refusal(path: Path) -> ConfigFileError:
    with pytest.raises(ConfigFileError) as info:
        load_pipeline(path)
    return info.value


def test_a_decoy_file_loads_to_the_same_value_as_its_yaml_twin(tmp_path: Path) -> None:
    pipeline = load_pipeline(_decoy(tmp_path, PROGRAM))

    assert pipeline.config["tables"][0]["name"] == "people"
    assert pipeline.unreviewed == ()
    assert pipeline.locate("tables.0").line == 6  # the `mask people` statement


def test_yaml_loads_through_the_same_function(tmp_path: Path) -> None:
    path = tmp_path / "pipeline.yaml"
    path.write_text("version: 2\nname: x\n", encoding="utf-8")

    pipeline = load_pipeline(path)

    assert pipeline.config == {"version": 2, "name": "x"}
    assert pipeline.unreviewed == ()
    assert pipeline.locate("name").line == 2  # the YAML index is built on first use


def test_not_utf8_is_one_decoy_code(tmp_path: Path) -> None:
    exc = _refusal(_decoy(tmp_path, b"decoy 1\n\xff\xfe" + MARKER.encode()))

    assert (exc.code, exc.message) == ("lang.not_utf8", "Pipeline file is not UTF-8 text.")
    assert len(exc.problems) == 1


@pytest.mark.parametrize("text", ["", "   \n\t\n"], ids=["empty", "whitespace"])
def test_empty_text_is_lang_empty(tmp_path: Path, text: str) -> None:
    exc = _refusal(_decoy(tmp_path, text))

    assert (exc.code, exc.message) == ("lang.empty", "Pipeline file is empty.")


def test_a_syntax_error_has_its_line_and_column(tmp_path: Path) -> None:
    exc = _refusal(_decoy(tmp_path, SYNTAX))

    assert exc.code == "lang.syntax"
    place = exc.problems[0].position
    assert place is not None and place.line == 3
    assert exc.problems[0].text.startswith("line 3, column ")
    assert MARKER not in repr(exc) + exc.message  # the marker is on line 6, past the error


def test_a_lowering_error_is_one_problem_per_diagnostic(tmp_path: Path) -> None:
    exc = _refusal(_decoy(tmp_path, BAD_STRATEGY))

    assert [p.code for p in exc.problems] == ["lang.unknown_strategy"]
    assert exc.problems[0].position is not None


def test_a_lowering_hint_reaches_the_problem_and_both_outputs(tmp_path: Path) -> None:
    path = _decoy(tmp_path, BAD_STRATEGY)

    assert _refusal(path).problems[0].hint == "did you mean `redact`?"
    text = runner.invoke(app, ["validate", "config", str(path)], env={"COLUMNS": "10000"})
    assert "hint: did you mean `redact`?" in text.output
    as_json = runner.invoke(
        app, ["validate", "config", str(path), "--json"], env={"COLUMNS": "10000"}
    )
    assert json.loads(as_json.stdout)["messages"][0]["hint"] == "did you mean `redact`?"
    gate = runner.invoke(app, ["validate", str(path), "--json"], env={"COLUMNS": "10000"})
    assert json.loads(gate.stdout)["messages"][0]["hint"] == "did you mean `redact`?"
    gate_text = runner.invoke(app, ["validate", str(path)], env={"COLUMNS": "10000"})
    assert "hint: did you mean `redact`?" in gate_text.output
    assert MARKER not in text.output + as_json.output + gate.output + gate_text.output


def test_the_review_mark_hint_reaches_both_outputs(tmp_path: Path) -> None:
    path = _decoy(tmp_path, MARKED)
    hint = "check the rule, then remove the `?`"

    text = runner.invoke(app, ["validate", "config", str(path)], env={"COLUMNS": "10000"})
    as_json = runner.invoke(
        app, ["validate", "config", str(path), "--json"], env={"COLUMNS": "10000"}
    )
    gate = runner.invoke(app, ["validate", str(path), "--json"], env={"COLUMNS": "10000"})

    assert f"hint: {hint}" in text.output
    assert [m["hint"] for m in json.loads(as_json.stdout)["messages"]] == [hint, hint]
    assert [m["hint"] for m in json.loads(gate.stdout)["messages"]] == [hint, hint]


def test_a_lowering_error_is_followed_by_the_marks(tmp_path: Path) -> None:
    text = BAD_STRATEGY.replace("email      : faker(person_email)", "email : faker(x) ?")
    text = text.replace("last_name  : faker(person_last_name)", "last_name : redact ?")

    exc = _refusal(_decoy(tmp_path, text))

    assert [p.code for p in exc.problems] == [
        "lang.unknown_strategy",
        "lang.unreviewed",
        "lang.unreviewed",
    ]
    assert exc.code == "lang.unknown_strategy"
    assert "(2 more; `decoy validate FILE` lists them)" in exc.message


def test_a_clean_file_with_marks_loads_and_holds_them(tmp_path: Path) -> None:
    pipeline = load_pipeline(_decoy(tmp_path, MARKED))

    assert [p.code for p in pipeline.unreviewed] == ["lang.unreviewed", "lang.unreviewed"]
    assert [p.position.line for p in pipeline.unreviewed] == [9, 10]
    assert pipeline.config["tables"][0]["name"] == "people"


def test_the_mapping_reader_refuses_a_marked_file(tmp_path: Path) -> None:
    path = _decoy(tmp_path, MARKED)

    with pytest.raises(ConfigFileError) as info:
        load_config_mapping(path)

    assert [p.code for p in info.value.problems] == ["lang.unreviewed", "lang.unreviewed"]
    assert load_config_mapping(_decoy(tmp_path, PROGRAM, "ok.decoy"))["tables"]


def test_the_suffix_decides_the_kind(tmp_path: Path) -> None:
    upper = _decoy(tmp_path, PROGRAM, "P.DECOY")
    assert is_decoy_path(upper) and load_pipeline(upper).config["tables"]

    # `p.decoy.yaml` is a YAML file whose name has `decoy` inside it.
    yaml_path = tmp_path / "p.decoy.yaml"
    yaml_path.write_text("a: 1\n", encoding="utf-8")
    assert not is_decoy_path(yaml_path)
    assert load_pipeline(yaml_path).config == {"a": 1}
    assert PIPELINE_SUFFIXES == (".yaml", ".yml", ".decoy")


@pytest.mark.parametrize("name", ["a.YML", "a.YAML", "a.DECOY", "a.decoy", "a.yml"])
def test_every_suffix_spelling_is_a_pipeline_path(name: str) -> None:
    assert looks_like_path(name)
    assert not looks_like_path("a.txt")


def test_completion_offers_every_pipeline_suffix(tmp_path: Path, monkeypatch) -> None:
    for name in ("a.yaml", "b.YML", "c.decoy", "d.DECOY", "e.csv"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert sorted(_config_paths("")) == ["a.yaml", "b.YML", "c.decoy", "d.DECOY"]


# --- the conversion cells (M6): a LangError leaves no trace in the ConfigFileError ----------


@pytest.mark.parametrize("text", [SYNTAX, BAD_STRATEGY, MARKED], ids=["syntax", "lower", "marks"])
def test_a_converted_error_has_no_cause_context_or_marker(tmp_path: Path, text: str) -> None:
    path = _decoy(tmp_path, text)
    try:
        load_config_mapping(path)
    except ConfigFileError as exc:
        error = exc
    else:
        raise AssertionError("expected a ConfigFileError")

    assert error.__cause__ is None
    assert error.__context__ is None
    everything = repr((str(error), error.args, error.problems))
    assert MARKER not in everything


def test_config_refusal_has_two_keys_and_names_the_count(tmp_path: Path) -> None:
    text = BAD_STRATEGY.replace("email      : faker(person_email)", "email : faker(x) ?")
    text = text.replace("last_name  : faker(person_last_name)", "last_name : redact ?")
    exc = _refusal(_decoy(tmp_path, text))

    refusal = config_refusal(exc)

    assert set(refusal) == {"message", "code"}
    assert refusal["code"] == "lang.unknown_strategy"
    assert refusal["message"].startswith("line 10, column ")
    assert "(2 more;" in refusal["message"]


def test_config_refusal_for_yaml_has_no_line_prefix(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text("- a\n", encoding="utf-8")

    refusal = config_refusal(_refusal(path))

    assert refusal["message"].startswith("Pipeline YAML must be")


# --- one decoder behind both readers ---------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "reader", "code", "text"),
    [
        ("p.yaml", read_config_text, "yaml.not_utf8", "Pipeline YAML is not UTF-8 text."),
        ("p.decoy", read_decoy_text, "lang.not_utf8", "Pipeline file is not UTF-8 text."),
    ],
)
def test_both_readers_share_one_decoder(tmp_path: Path, name, reader, code, text) -> None:
    good = tmp_path / name
    good.write_bytes(b"\xef\xbb\xbfdecoy 1\n")
    assert reader(good) == "decoy 1\n"  # the BOM is dropped

    bad = tmp_path / ("bad_" + name)
    bad.write_bytes(b"a\xff" + MARKER.encode())
    with pytest.raises(ConfigFileError) as info:
        reader(bad)

    assert (info.value.code, info.value.message) == (code, text)
    assert info.value.__context__ is None and info.value.__cause__ is None
    assert MARKER not in repr(info.value)


def test_bytes_given_to_the_loader_use_the_kind_decoder(tmp_path: Path) -> None:
    decoy = tmp_path / "p.decoy"
    yaml_path = tmp_path / "p.yaml"

    with pytest.raises(ConfigFileError) as one:
        load_pipeline(decoy, text=b"\xff")
    with pytest.raises(ConfigFileError) as two:
        load_pipeline(yaml_path, text=b"\xff")

    assert (one.value.code, two.value.code) == ("lang.not_utf8", "yaml.not_utf8")


# --- hostile text -----------------------------------------------------------------------------


def test_a_deeply_nested_list_the_grammar_accepts_is_a_nesting_problem(tmp_path: Path) -> None:
    # Each bracket is valid on its own, so the parser accepts the text and only the depth limit
    # can refuse it.
    deep = PROGRAM.replace(
        "faker(person_email)", "faker(person_email, k: " + "[" * 3000 + "]" * 3000 + ")"
    )

    exc = _refusal(_decoy(tmp_path, deep))

    assert exc.code == "lang.nesting"


def test_a_lone_surrogate_escape_is_a_string_escape_problem(tmp_path: Path) -> None:
    text = PROGRAM.replace("faker(person_email)", 'faker(person_email, k: "\\ud800")')

    exc = _refusal(_decoy(tmp_path, text))

    assert exc.code == "lang.string_escape"


def test_a_large_file_and_odd_bytes_are_refused_cleanly(tmp_path: Path) -> None:
    for data in (b"x" * 5_000_000, b"decoy 1\n\x00\x00", b"decoy 1\r\n\r\nseed 1\r\n"):
        exc = _refusal(_decoy(tmp_path, data))
        assert exc.code.startswith("lang.")


# --- imports ---------------------------------------------------------------------------------


def test_importing_the_loader_does_not_load_the_engine_or_the_compiler(tmp_path: Path) -> None:
    yaml_path = tmp_path / "p.yaml"
    yaml_path.write_text("a: 1\n", encoding="utf-8")
    code = (
        "import sys, pathlib\n"
        "import decoy._config_file as c\n"
        f"c.load_pipeline(pathlib.Path({str(yaml_path)!r}))\n"
        "print(json.dumps(sorted(m for m in ('decoy_engine', 'lark', 'decoy.lang')"
        " if m in sys.modules)))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", "import json\n" + code], capture_output=True, text=True, check=True
    )

    assert json.loads(out.stdout) == []


# --- through the commands --------------------------------------------------------------------

runner = CliRunner()


def test_validate_accepts_a_decoy_twin(tmp_path: Path) -> None:
    (tmp_path / "input.csv").write_text("first_name,last_name,email,ssn,account_status\n")
    path = _decoy(tmp_path, PROGRAM)

    result = runner.invoke(app, ["validate", "config", str(path)], catch_exceptions=False)

    assert result.exit_code == 0, result.output


def test_validate_reports_a_syntax_error_with_its_line(tmp_path: Path) -> None:
    path = _decoy(tmp_path, SYNTAX)

    result = runner.invoke(
        app, ["validate", "config", str(path), "--json"], env={"COLUMNS": "10000"}
    )

    assert result.exit_code == 1, result.output
    assert MARKER not in result.output
    document = json.loads(result.stdout)
    finding = document["messages"][0]
    assert finding["code"] == "lang.syntax"
    assert finding["message"].startswith("line 3, column ")


def test_preflight_says_pipeline_syntax_for_a_decoy_file(tmp_path: Path) -> None:
    path = _decoy(tmp_path, PROGRAM)
    (tmp_path / "input.csv").write_text("first_name,last_name,email,ssn,account_status\n")

    result = runner.invoke(
        app, ["validate", "preflight", str(path), "--json"], env={"COLUMNS": "10000"}
    )

    checks = {c["name"]: c["message"] for c in json.loads(result.stdout)["checks"]}
    assert checks["yaml.syntax"] == "Pipeline syntax is valid."
