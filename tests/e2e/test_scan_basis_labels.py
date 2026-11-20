"""Sampled scan numbers say they are a sample (PROFILE-SAMPLE-LABELS C1).

The default scan profiles the first 10,000 rows. The card, `--show-fields`, `--json` and
`decoy scan show` name the basis, and a sampled scan claims no key (a key needs every row).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from decoy.__main__ import app
from tests.scan_docs import scan_set_doc

runner = CliRunner()
_WIDE = {"COLUMNS": "10000"}

_BIG = 25_000
_SMALL = 4_812


def _big_csv(path: Path) -> Path:
    """25,000 rows: `id` repeats after 10,000 rows, `u` is unique throughout."""
    pd.DataFrame({"id": list(range(10_000)) + [i % 100 for i in range(_BIG - 10_000)]}).assign(
        u=range(_BIG)
    ).to_csv(path, index=False)
    return path


def _small_csv(path: Path) -> Path:
    pd.DataFrame({"id": range(_SMALL), "v": ["x"] * _SMALL}).to_csv(path, index=False)
    return path


def _scan_json(*paths: Path, extra: tuple[str, ...] = ()) -> dict:
    result = runner.invoke(app, ["scan", *map(str, paths), "--has-header", "--json", *extra])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


@pytest.fixture
def big(tmp_path: Path) -> Path:
    return _big_csv(tmp_path / "big.csv")


@pytest.fixture
def small(tmp_path: Path) -> Path:
    return _small_csv(tmp_path / "small.csv")


# AT-C1


def test_card_labels_a_sample_and_claims_no_key(big: Path) -> None:
    result = runner.invoke(app, ["scan", str(big), "--has-header"], env=_WIDE)
    assert result.exit_code == 0, result.output
    assert "(sample, head)" in result.stdout
    assert "10,000 of" in result.stdout
    assert "not checked (sampled scan; --rows 0 reads every row)" in result.stdout


def test_card_labels_a_whole_read_and_keeps_the_key(small: Path) -> None:
    result = runner.invoke(app, ["scan", str(small), "--has-header"])
    assert result.exit_code == 0, result.output
    assert f"{_SMALL:,} (whole file)" in result.stdout
    assert "not checked" not in result.stdout


# AT-C2


def test_flat_json_carries_the_basis_and_the_source_row_count(big: Path, small: Path) -> None:
    sample = _scan_json(big)
    assert sample["basis"] == "sample"
    assert sample["scanned_rows"] == 10_000
    assert sample["row_count"] > sample["scanned_rows"]
    assert sample["row_count"] >= _BIG
    assert isinstance(sample["row_count_exact"], bool)
    whole = _scan_json(small)
    assert whole["basis"] == "whole"
    assert whole["scanned_rows"] == whole["row_count"] == _SMALL
    assert whole["row_count_exact"] is True


def test_rows_zero_reads_the_whole_file(big: Path) -> None:
    payload = _scan_json(big, extra=("--rows", "0"))
    assert payload["basis"] == "whole"
    assert payload["scanned_rows"] == payload["row_count"] == _BIG


# AT-C3 and AT-C8


def test_multi_json_gives_every_table_the_same_members(big: Path, small: Path) -> None:
    payload = _scan_json(big, small)
    assert [t["basis"] for t in payload["tables"]] == ["sample", "whole"]
    # `row_count` is the source count, `scanned_rows` the rows read (the Breaking change).
    sampled = payload["tables"][0]
    assert sampled["row_count"] > sampled["scanned_rows"] == 10_000
    assert sampled["row_count"] >= _BIG
    for t in payload["tables"]:
        assert {"basis", "scanned_rows", "row_count", "row_count_exact"} <= set(t)


def test_multi_card_sums_scanned_rows_not_source_rows(big: Path, small: Path) -> None:
    result = runner.invoke(app, ["scan", str(big), str(small), "--has-header"], env=_WIDE)
    assert result.exit_code == 0, result.output
    assert f"{10_000 + _SMALL:,}" in result.stdout
    assert "(sample, head)" in result.stdout
    assert "(whole file)" in result.stdout


# AT-C5


def test_show_fields_headers_say_sample_only_on_a_sample(big: Path, small: Path) -> None:
    sampled = runner.invoke(app, ["scan", str(big), "--has-header", "--show-fields"], env=_WIDE)
    assert "Null rate (sample)" in sampled.stdout
    assert "Distinct (sample)" in sampled.stdout
    whole = runner.invoke(app, ["scan", str(small), "--has-header", "--show-fields"], env=_WIDE)
    assert "(sample)" not in whole.stdout


# AT-C4 and AT-C6


def _saved(tmp_path: Path, doc: dict) -> Path:
    path = tmp_path / "scan.json"
    path.write_text(json.dumps(doc))
    return path


def test_show_labels_counts_of_a_sampled_saved_scan(tmp_path: Path) -> None:
    doc = scan_set_doc([{"name": "id"}], basis="sample", scanned_rows=10_000, row_count=28_058)
    saved = _saved(tmp_path, doc)
    card = runner.invoke(app, ["scan", "show", str(saved), "id"], env=_WIDE)
    assert card.exit_code == 0, card.output
    assert "in 10,000 scanned rows" in card.stdout
    payload = json.loads(runner.invoke(app, ["scan", "show", str(saved), "id", "--json"]).stdout)
    assert payload["basis"] == "sample"
    assert payload["scanned_rows"] == 10_000


def test_show_on_a_whole_saved_scan_has_no_suffix(tmp_path: Path) -> None:
    doc = scan_set_doc([{"name": "id"}], basis="whole", scanned_rows=5, row_count=5)
    card = runner.invoke(app, ["scan", "show", str(_saved(tmp_path, doc)), "id"])
    assert card.exit_code == 0, card.output
    assert "scanned rows" not in card.stdout


def test_show_on_a_scan_saved_before_the_labels_says_so(tmp_path: Path) -> None:
    saved = _saved(tmp_path, scan_set_doc([{"name": "id"}]))
    card = runner.invoke(app, ["scan", "show", str(saved), "id"], env=_WIDE)
    assert card.exit_code == 0, card.output
    assert "basis not recorded; read as a sample" in card.stdout
    payload = json.loads(runner.invoke(app, ["scan", "show", str(saved), "id", "--json"]).stdout)
    assert payload["basis"] == "sample"
    assert payload["scanned_rows"] is None


@pytest.mark.parametrize(
    ("basis", "scanned", "count"),
    [("whole", None, 5), ("sample", 9, 5), ("whole", 4, 5)],
    ids=["whole-without-count", "scanned-over-total", "whole-short-of-total"],
)
def test_show_refuses_a_corrupt_basis_relation(
    tmp_path: Path, basis: str, scanned: int | None, count: int
) -> None:
    doc = scan_set_doc([{"name": "id"}], basis=basis, scanned_rows=scanned, row_count=count)
    saved = _saved(tmp_path, doc)
    from_path = runner.invoke(app, ["scan", "show", str(saved), "id"])
    from_stdin = runner.invoke(app, ["scan", "show", "-", "id"], input=json.dumps(doc))
    for result in (from_path, from_stdin):
        assert result.exit_code == 1, result.output
        assert "not a saved scan Decoy can read" in result.output


def test_a_basis_the_cli_does_not_know_reads_as_a_sample(tmp_path: Path) -> None:
    doc = scan_set_doc([{"name": "id"}], basis="future", scanned_rows=7, row_count=9)
    card = runner.invoke(app, ["scan", "show", str(_saved(tmp_path, doc)), "id"], env=_WIDE)
    assert card.exit_code == 0, card.output
    assert "in 7 scanned rows" in card.stdout
