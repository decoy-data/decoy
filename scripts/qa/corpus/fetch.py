"""Download the public corpus items listed in `docs/qa/corpus/manifest.toml`.

    python -m scripts.qa.corpus.fetch [--out DIR] [--item ID]

Order matters here: the bytes go to a private temporary file, the SHA-256 is computed from that
file on disk, and only then is it renamed into place. The file that was checked is the file that
is used, and a bad download never has a final name. An item needs a recorded license from the
allow-list. Downloaded data is read as data only: this tool never unpacks or runs it, and later
code that reads it runs under `python -I` from another folder.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import urllib.parse
import urllib.request
from collections.abc import Sequence
from pathlib import Path

from scripts.qa.corpus.manifest import ALLOWED_LICENSES, Item, load_manifest
from scripts.qa.io import StagedFile, staged_private

DEFAULT_OUT = Path.home() / "decoy-qa-corpus"
DEFAULT_MANIFEST = Path(__file__).resolve().parents[3] / "docs/qa/corpus/manifest.toml"
SCHEMES = ("https",)
_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_CHUNK = 1 << 20


class FetchRefused(RuntimeError):
    """The fetcher refused an item. Messages hold the item id and the reason only."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def check_item(item: Item, schemes: Sequence[str]) -> str:
    """Refuse an item that may not be fetched; return the file name to store it under."""
    if item.generated:
        raise FetchRefused(f"{item.id}: a generated item has no download")
    if not item.license:
        raise FetchRefused(f"{item.id}: no license recorded")
    if item.license not in ALLOWED_LICENSES:
        raise FetchRefused(f"{item.id}: license {item.license!r} is not on the allow-list")
    parts = urllib.parse.urlparse(item.origin)
    if parts.scheme not in schemes:
        raise FetchRefused(f"{item.id}: scheme {parts.scheme!r} is not allowed")
    name = Path(urllib.parse.unquote(parts.path)).name
    if _FILENAME.fullmatch(name) is None:
        raise FetchRefused(f"{item.id}: the URL does not end in a plain file name")
    return name


def _download(url: str, staged: StagedFile) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:
        while chunk := response.read(_CHUNK):
            staged.write(chunk)


def fetch_item(item: Item, out: Path, schemes: Sequence[str] = SCHEMES) -> Path:
    name = check_item(item, schemes)
    target = out / item.id / name
    if target.exists():
        if sha256_file(target) != item.sha256:
            raise FetchRefused(f"{item.id}: the stored file does not match the manifest hash")
        return target
    with staged_private(target) as staged:
        _download(item.origin, staged)
        staged.close()
        if sha256_file(staged.path) != item.sha256:
            raise FetchRefused(f"{item.id}: SHA-256 differs from the manifest; nothing stored")
        staged.publish()
    return target


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--item", action="append", help="fetch only these ids")
    args = ap.parse_args(argv)
    items = [
        i
        for i in load_manifest(args.manifest)
        if not i.generated and (not args.item or i.id in args.item)
    ]
    for item in items:
        print(f"fetched {fetch_item(item, args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
