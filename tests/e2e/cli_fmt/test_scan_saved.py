"""Saved-scan readers (`scan fields`, `show`, `diff`) go through `load_scan_set`, which reads
only the `scan-set/v1` core, from a path or from stdin. An untagged saved scan (the bare
`profile.to_dict()` written before `scan-set/v1`) is refused with a coded error (AT-D6)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from decoy.__main__ import app

runner = CliRunner()
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "scan" / "legacy_profile.json"
CANARY = "ZQCANARY"


@pytest.fixture
def legacy() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def legacy_file(tmp_path: Path, legacy: dict) -> Path:
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")
    return path


def _people_csv(path: Path) -> Path:
    pd.DataFrame(
        {
            "customer_id": ["C1", "C2", "C3", "C4", "C5"],
            "first_name": [f"{CANARY}{n}" for n in range(5)],
            "email": [f"zqcanary{n}@example.com" for n in range(5)],
            "ssn": ["111-22-3333", "222-33-4444", "333-44-5555", "444-55-6666", "555-66-7777"],
        }
    ).to_csv(path, index=False)
    return path


@pytest.fixture
def core_file(tmp_path: Path) -> Path:
    out = tmp_path / "core.json"
    src = _people_csv(tmp_path / "people.csv")
    assert runner.invoke(app, ["scan", str(src), "--has-header", "-o", str(out)]).exit_code == 0
    return out


@pytest.fixture
def load_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every `load_scan_set` call the commands make."""
    import decoy.cli.scan as scan_mod

    calls: list[str] = []
    real = scan_mod.load_scan_set

    def spy(path: str) -> dict:
        calls.append(path)
        return real(path)

    monkeypatch.setattr(scan_mod, "load_scan_set", spy)
    return calls


# -- T2-load-bare -----------------------------------------------------------------------


def test_fields_show_and_diff_all_use_load_scan_set(core_file: Path, load_calls: list[str]) -> None:
    assert runner.invoke(app, ["scan", "fields", str(core_file)]).exit_code == 0
    assert runner.invoke(app, ["scan", "show", str(core_file), "ssn"]).exit_code == 0
    assert runner.invoke(app, ["scan", "diff", str(core_file), str(core_file)]).exit_code == 0
    assert load_calls == [str(core_file)] * 4


def test_a_core_file_lists_the_same_fields_as_the_scan(core_file: Path) -> None:
    result = runner.invoke(app, ["scan", "fields", str(core_file), "--json"])
    assert [f["name"] for f in json.loads(result.stdout)["fields"]] == [
        "customer_id",
        "first_name",
        "email",
        "ssn",
    ]


def test_a_multi_table_scan_needs_table(tmp_path: Path) -> None:
    a = _people_csv(tmp_path / "a.csv")
    b = _people_csv(tmp_path / "b.csv")
    out = tmp_path / "two.json"
    assert (
        runner.invoke(app, ["scan", str(a), str(b), "--has-header", "-o", str(out)]).exit_code == 0
    )
    bare = runner.invoke(app, ["scan", "fields", str(out)])
    assert bare.exit_code == 1 and "--table" in bare.output
    picked = runner.invoke(app, ["scan", "fields", str(out), "--table", "b"])
    assert picked.exit_code == 0
    missing = runner.invoke(app, ["scan", "fields", str(out), "--table", "zzz"])
    assert missing.exit_code == 1


# -- T2-schema-reject -------------------------------------------------------------------


def test_an_unknown_scan_schema_major_exits_1(core_file: Path, tmp_path: Path) -> None:
    doc = json.loads(core_file.read_text())
    doc["scan_schema"] = "scan-set/v2"
    bad = tmp_path / "v2.json"
    bad.write_text(json.dumps(doc))
    result = runner.invoke(app, ["scan", "fields", str(bad)])
    assert result.exit_code == 1
    assert "scan-set/v2" in result.output


def test_a_tag_that_could_hold_data_is_not_echoed(core_file: Path, tmp_path: Path) -> None:
    doc = json.loads(core_file.read_text())
    doc["scan_schema"] = f"{CANARY} secret value with spaces"
    bad = tmp_path / "odd.json"
    bad.write_text(json.dumps(doc))
    result = runner.invoke(app, ["scan", "fields", str(bad)])
    assert result.exit_code == 1 and CANARY not in result.output


# -- untagged saved scans (AT-D6) --------------------------------------------------------

CODE = "scan.saved_scan_schema_unsupported"


@pytest.mark.parametrize("cmd", [["fields"], ["show"], ["diff"]])
def test_an_untagged_saved_scan_is_refused_with_its_code(legacy_file: Path, cmd: list[str]) -> None:
    extra = ["first_name"] if cmd == ["show"] else [str(legacy_file)] if cmd == ["diff"] else []
    result = runner.invoke(app, ["scan", *cmd, str(legacy_file), *extra])
    assert result.exit_code == 1
    assert CODE in result.output
    assert CANARY not in result.output


def test_an_untagged_saved_scan_is_refused_in_json_with_its_code(legacy_file: Path) -> None:
    result = runner.invoke(app, ["scan", "fields", str(legacy_file), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "error" and CODE in payload["error"]
    assert CANARY not in result.output


@pytest.mark.parametrize(
    "doc",
    [
        {"row_count": 5},
        {"row_count": 5, "fields": "name"},
        {"row_count": 5, "fields": [{"name": "x", "pii_score": 0.1}]},
        {"command": "scan", "status": "ok", "profile": {"row_count": 1, "fields": []}},
        {"unrelated": "value " + CANARY},
    ],
)
def test_a_dict_without_the_tag_exits_1_with_the_code(tmp_path: Path, doc: object) -> None:
    path = tmp_path / "x.json"
    path.write_text(json.dumps(doc))
    result = runner.invoke(app, ["scan", "fields", str(path)])
    assert result.exit_code == 1
    assert CODE in result.output
    assert CANARY not in result.output


# -- stdin ------------------------------------------------------------------------------


def test_stdin_untagged_is_refused_with_the_code(legacy_file: Path) -> None:
    result = runner.invoke(app, ["scan", "fields", "-"], input=legacy_file.read_text())
    assert result.exit_code == 1 and CODE in result.output and CANARY not in result.output


def test_stdin_core_matches_the_file(core_file: Path) -> None:
    text = core_file.read_text()
    piped = runner.invoke(app, ["scan", "fields", "-", "--json"], input=text)
    direct = runner.invoke(app, ["scan", "fields", str(core_file), "--json"])
    assert json.loads(piped.stdout)["fields"] == json.loads(direct.stdout)["fields"]
    for args in (["-", str(core_file)], [str(core_file), "-"]):
        r = runner.invoke(app, ["scan", "diff", *args, "--json"], input=text)
        assert r.exit_code == 0 and json.loads(r.stdout)["drift"] is False


def test_diff_with_both_operands_on_stdin_is_refused_before_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_read(_: str) -> dict:
        raise AssertionError("stdin was read")

    import decoy.cli.scan as scan_mod

    monkeypatch.setattr(scan_mod, "load_scan_set", no_read)
    result = runner.invoke(app, ["scan", "diff", "-", "-"], input="{}")
    assert result.exit_code == 1
    assert "only one of OLD or NEW" in result.output


def test_a_json_list_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[1, 2]")
    assert runner.invoke(app, ["scan", "fields", str(path)]).exit_code == 1


# -- non-finite numbers ---------------------------------------------------------------


def _core_with(core: dict, literal: str) -> str:
    core["tables"][0]["fields"][0]["pii_score"] = "@@"
    return json.dumps(core).replace('"@@"', literal)


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
@pytest.mark.parametrize("cmd", [["fields"], ["show"]])
def test_a_non_finite_number_in_a_saved_scan_is_refused(
    tmp_path: Path, core_file: Path, literal: str, cmd: list[str]
) -> None:
    path = tmp_path / "bad.json"
    path.write_text(_core_with(json.loads(core_file.read_text()), literal), encoding="utf-8")
    args = ["scan", *cmd, str(path)] + (["ssn", "--json"] if cmd == ["show"] else ["--json"])
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert "not a saved scan Decoy can read" in result.output
    assert "NaN" not in result.output and "Infinity" not in result.output


def test_a_normal_float_in_a_saved_scan_is_still_accepted(tmp_path: Path, core_file: Path) -> None:
    path = tmp_path / "ok.json"
    path.write_text(_core_with(json.loads(core_file.read_text()), "0.25"), encoding="utf-8")
    assert runner.invoke(app, ["scan", "fields", str(path), "--json"]).exit_code == 0
