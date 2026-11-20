"""The corpus manifest and its strict reader."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.qa.corpus import manifest as mf

PATH = Path(__file__).resolve().parents[3] / "docs/qa/corpus/manifest.toml"
GOOD = {
    "id": "x-csv-s",
    "origin": "generated",
    "license": "generated",
    "sha256": "",
    "tier": "S",
    "format": "csv",
    "shapes": ["single"],
    "marker_columns": ["people.name"],
}
PUBLIC = {
    **GOOD,
    "id": "pub",
    "origin": "https://example.com/a.zip",
    "license": "MIT",
    "sha256": "a" * 64,
}


def test_the_checked_in_manifest_loads_and_has_the_public_items() -> None:
    items = mf.load_manifest(PATH)
    public = {i.id: i for i in items if not i.generated}
    assert set(public) == {"synthea-csv-apr2020", "chinook-sqlite"}
    assert {i.license for i in public.values()} <= mf.ALLOWED_LICENSES
    assert all(i.sha256 and i.origin.startswith("https://") for i in public.values())
    assert all(i.sha256 == "" for i in items if i.generated)


def test_the_good_rows_parse() -> None:
    assert mf.parse_item(GOOD).generated
    assert not mf.parse_item(PUBLIC).generated


@pytest.mark.parametrize(
    "change",
    [
        {"id": "Bad_Id"},
        {"tier": "XL"},
        {"origin": "http://example.com/a.zip"},
        {"origin": "ftp://example.com/a"},
        {"sha256": "abc"},
        {"sha256": "A" * 64},
        {"shapes": []},
        {"shapes": "single"},
        {"marker_columns": [1]},
        {"extra": "field"},
    ],
)
def test_bad_rows_are_refused(change: dict) -> None:
    base = PUBLIC if "sha256" in change or change.get("origin", "").startswith("http") else GOOD
    with pytest.raises(mf.ManifestError):
        mf.parse_item({**base, **change})


def test_a_generated_item_with_a_hash_and_a_public_one_without_are_refused() -> None:
    with pytest.raises(mf.ManifestError):
        mf.parse_item({**GOOD, "sha256": "a" * 64})
    with pytest.raises(mf.ManifestError):
        mf.parse_item({**PUBLIC, "sha256": ""})


def test_a_missing_field_is_refused() -> None:
    bad = dict(GOOD)
    del bad["format"]
    with pytest.raises(mf.ManifestError):
        mf.parse_item(bad)


@pytest.mark.parametrize(
    "text",
    [
        "items = []\n",
        "schema_version = 1\n",
        "schema_version = true\nitems=[{}]\n",
        "schema_version = '1'\n",
        "schema_version = 2\n[[items]]\nid='a'\n",
        "not toml [",
    ],
)
def test_bad_documents_are_refused(text: str) -> None:
    with pytest.raises(mf.ManifestError):
        mf.parse_manifest(text)


def test_a_repeated_id_is_refused() -> None:
    row = "[[items]]\n" + "\n".join(
        f"{k} = {v!r}".replace("'", '"')
        for k, v in GOOD.items()
        if k not in {"shapes", "marker_columns"}
    )
    row += '\nshapes = ["single"]\nmarker_columns = []\n'
    with pytest.raises(mf.ManifestError, match="twice"):
        mf.parse_manifest("schema_version = 1\n" + row + row)


def test_an_unlicensed_item_still_parses_so_the_fetcher_can_refuse_it() -> None:
    assert mf.parse_item({**PUBLIC, "license": ""}).license == ""
