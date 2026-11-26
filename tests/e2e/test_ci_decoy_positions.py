"""`decoy ci check` puts a `.decoy` finding on the `.decoy` line, in JSON and in SARIF.

The CI adapter does not read the pipeline file or build an index: the gate loads it once and each
finding carries the position the loader gave it.
"""

from __future__ import annotations

from pathlib import Path

from tests.ci_support import (
    MANIFEST_NAME,
    assert_valid_sarif,
    ci_check,
    ci_manifest,
    make_repo,
    parse_stdout,
    write,
)

PROGRAM = """decoy 1

pipeline {
  seed 42
  options { bogus_key: 1 }

  mask people from csv("data/in.csv", header: true) to csv("out/out.csv") {
    email : faker(person_email) ?
    ssn   : redact ?
  }
}
"""
MANIFEST = ci_manifest(pipelines="  - id: primary\n    path: pipeline.decoy\n")


def _repo(tmp_path: Path) -> Path:
    repo = make_repo(tmp_path / "repo")
    write(repo, MANIFEST_NAME, MANIFEST)
    write(repo, "pipeline.decoy", PROGRAM)
    return repo


def _line(needle: str) -> int:
    return next(i for i, text in enumerate(PROGRAM.splitlines(), start=1) if needle in text)


def test_json_findings_sit_on_the_decoy_lines(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    report = parse_stdout(ci_check(repo, "--format", "json"))

    found = {f["rule_id"]: f for f in report["findings"] if f["rule_id"].startswith("validate.")}
    marks = [f for f in report["findings"] if f["rule_id"] == "validate.lang.unreviewed"]
    assert [m["location"]["start_line"] for m in marks] == [_line("person_email"), _line("redact")]
    assert all(m["location"]["uri"] == "pipeline.decoy" for m in marks)
    schema = [f for rule, f in found.items() if rule != "validate.lang.unreviewed"]
    assert schema, "the engine schema finding is reported"
    assert schema[0]["location"]["start_line"] == _line("bogus_key")


def test_sarif_regions_are_on_the_decoy_lines_and_valid(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    proc = ci_check(repo, "--format", "sarif")

    sarif = parse_stdout(proc)
    assert_valid_sarif(sarif)
    results = sarif["runs"][0]["results"]
    marks = [r for r in results if r["ruleId"] == "validate.lang.unreviewed"]
    assert len(marks) == 2
    starts = [r["locations"][0]["physicalLocation"]["region"]["startLine"] for r in marks]
    assert starts == [_line("person_email"), _line("redact")]
    for r in results:
        physical = r["locations"][0]["physicalLocation"]
        assert physical["artifactLocation"]["uri"] == "pipeline.decoy"


def test_a_decoy_syntax_error_is_one_finding_with_its_own_rule_not_the_unknown_one(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "repo")
    write(repo, MANIFEST_NAME, MANIFEST)
    write(repo, "pipeline.decoy", PROGRAM.replace("pipeline {", "pipeline { ("))

    report = parse_stdout(ci_check(repo, "--format", "json"))

    rules = [f["rule_id"] for f in report["findings"]]
    assert "validate.lang.syntax" in rules
    assert not any(rule.endswith("unknown") for rule in rules)
