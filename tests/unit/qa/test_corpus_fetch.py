"""AT-8: `fetch.py` refuses a wrong hash, no license and an unlisted license, and a good item lands
only after its hash checks. Fixtures are local `file://` URLs; nothing here touches the network."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path

import pytest
from scripts.qa.corpus import fetch
from scripts.qa.corpus.manifest import Item

PAYLOAD = b"id,name\n1,qamark-free public data\n" * 50
SCHEMES = ("file",)


def item_for(src: Path, **change: str) -> Item:
    base = {
        "id": "pub-item",
        "origin": src.as_uri(),
        "license": "MIT",
        "sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
        "tier": "S",
        "format": "csv",
        "shapes": ("single",),
        "marker_columns": (),
    }
    return Item(**{**base, **change})  # type: ignore[arg-type]


@pytest.fixture
def src(tmp_path: Path) -> Path:
    path = tmp_path / "remote" / "data.csv"
    path.parent.mkdir()
    path.write_bytes(PAYLOAD)
    return path


@pytest.fixture
def out(tmp_path: Path) -> Path:
    return tmp_path / "corpus"


def leftovers(out: Path) -> list[Path]:
    return [p for p in out.rglob("*") if p.is_file()] if out.exists() else []


def test_a_good_item_lands_private_with_the_checked_bytes(src: Path, out: Path) -> None:
    got = fetch.fetch_item(item_for(src), out, SCHEMES)
    assert got == out / "pub-item" / "data.csv"
    assert got.read_bytes() == PAYLOAD
    assert stat.S_IMODE(got.stat().st_mode) == 0o600
    assert leftovers(out) == [got]


def test_a_wrong_hash_refuses_and_stores_nothing(src: Path, out: Path) -> None:
    with pytest.raises(fetch.FetchRefused, match="SHA-256"):
        fetch.fetch_item(item_for(src, sha256="0" * 64), out, SCHEMES)
    assert leftovers(out) == []


def test_a_good_item_is_only_renamed_after_the_hash_is_checked(
    src: Path, out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = out / "pub-item" / "data.csv"
    seen: list[bool] = []
    real = fetch.sha256_file

    def spy(path: Path) -> str:
        seen.append(target.exists())
        assert path != target, "the hash must be taken from the temporary file"
        return real(path)

    monkeypatch.setattr(fetch, "sha256_file", spy)
    fetch.fetch_item(item_for(src), out, SCHEMES)
    assert seen == [False]


def test_an_item_with_no_license_is_refused_before_any_download(src: Path, out: Path) -> None:
    with pytest.raises(fetch.FetchRefused, match="no license"):
        fetch.fetch_item(item_for(src, license=""), out, SCHEMES)
    assert leftovers(out) == []


@pytest.mark.parametrize("license_id", ["GPL-3.0-only", "CC-BY-NC-4.0", "proprietary", "mit"])
def test_a_license_off_the_allow_list_is_refused(src: Path, out: Path, license_id: str) -> None:
    with pytest.raises(fetch.FetchRefused, match="allow-list"):
        fetch.fetch_item(item_for(src, license=license_id), out, SCHEMES)
    assert leftovers(out) == []


def test_a_generated_item_has_nothing_to_fetch(src: Path, out: Path) -> None:
    with pytest.raises(fetch.FetchRefused, match="generated"):
        fetch.fetch_item(item_for(src, origin="generated", license="generated"), out, SCHEMES)


def test_only_https_is_fetched_by_default(src: Path, out: Path) -> None:
    with pytest.raises(fetch.FetchRefused, match="scheme"):
        fetch.fetch_item(item_for(src), out)
    assert leftovers(out) == []


def test_a_stored_file_is_checked_again_and_kept(src: Path, out: Path) -> None:
    item = item_for(src)
    first = fetch.fetch_item(item, out, SCHEMES)
    assert fetch.fetch_item(item, out, SCHEMES) == first
    first.chmod(0o600)
    first.write_bytes(b"tampered")
    with pytest.raises(fetch.FetchRefused, match="stored file"):
        fetch.fetch_item(item, out, SCHEMES)


def test_a_url_without_a_plain_file_name_is_refused(tmp_path: Path, src: Path, out: Path) -> None:
    odd = tmp_path / "remote" / "a b;c.csv"
    odd.write_bytes(PAYLOAD)
    with pytest.raises(fetch.FetchRefused, match="file name"):
        fetch.fetch_item(item_for(src, origin=odd.as_uri()), out, SCHEMES)


def test_main_tries_the_public_items_and_leaves_nothing_after_a_failed_download(
    tmp_path: Path, out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "m.toml"
    manifest.write_text(
        "schema_version = 1\n[[items]]\n"
        'id = "pub-item"\norigin = "https://example.invalid/data.csv"\nlicense = "MIT"\n'
        f'sha256 = "{"a" * 64}"\ntier = "S"\nformat = "csv"\nshapes = ["x"]\nmarker_columns = []\n',
        encoding="utf-8",
    )
    asked: list[str] = []

    def refuse(url: str, timeout: int) -> None:
        asked.append(url)
        raise OSError("no network in tests")

    monkeypatch.setattr(fetch.urllib.request, "urlopen", refuse)
    with pytest.raises(OSError):
        fetch.main(["--manifest", str(manifest), "--out", str(out)])
    assert asked == ["https://example.invalid/data.csv"]
    assert leftovers(out) == []
