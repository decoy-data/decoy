"""Build the generated corpus items listed in `docs/qa/corpus/manifest.toml`.

    python -m scripts.qa.corpus.generate [--out DIR] [--seed N] [--tier S --tier M] [--item ID]

Same seed, same bytes (a DuckDB file keeps its tables but not its bytes). Each item goes to
`<out>/<id>/`, default `~/decoy-qa-corpus`. Data never enters git. Tier L (1M rows) is built only
when asked for, and only on the Dell or a GCP test node.
Files are published by `scripts/qa/io.py`; a re-run that would write identical bytes is a no-op
and one that would write different bytes stops.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from scripts.qa.corpus import formats, shapes
from scripts.qa.corpus.manifest import Item, load_manifest
from scripts.qa.io import AlreadyPublished, publish_or_same

DEFAULT_SEED = 20261120
DEFAULT_OUT = Path.home() / "decoy-qa-corpus"
DEFAULT_MANIFEST = Path(__file__).resolve().parents[3] / "docs/qa/corpus/manifest.toml"


class RegenerationDiffers(RuntimeError):
    """An existing file differs from what this seed would write."""


def build_item(item: Item, seed: int) -> shapes.Built:
    """The tables of a generated item, before any file format is applied."""
    structure, *mods = item.shapes
    unknown = (set(mods) - shapes.MODIFIERS) | ({structure} - set(shapes.BUILDERS))
    if unknown:
        raise ValueError(f"item {item.id!r} has unknown shapes {sorted(unknown)}")
    rows = 0 if "header_only" in mods else shapes.TIER_ROWS[item.tier]
    return shapes.build(structure, rows, shapes.seed_for(seed, item.id))


def render_item(item: Item, seed: int) -> dict[str, bytes]:
    """File name to bytes for one generated item."""
    mods = set(item.shapes[1:])
    files = formats.render(build_item(item, seed).tables, item.format, item.id)
    if "empty_file" in mods:
        return {name: b"" for name in files if not name.endswith(".layout.toml")}
    if "malformed" in mods:
        return {name: formats.malform(name, data, item.format) for name, data in files.items()}
    return files


def _publish(path: Path, data: bytes) -> None:
    """Publish once, or accept identical bytes already there (`io.publish_or_same`)."""
    different = False
    try:
        publish_or_same(path, data)
    except AlreadyPublished:
        different = True
    if different:  # raised outside the handler so the error carries no context
        raise RegenerationDiffers(f"{path.name} exists with different bytes")


def _check_existing_duckdb(item: Item, path: Path, seed: int) -> None:
    """A DuckDB file has build-time identifiers, so compare its tables, not its bytes."""
    expected = formats.duckdb_expected(build_item(item, seed).tables)
    try:
        same = formats.duckdb_snapshot(path) == expected
    except Exception:  # an unreadable or foreign file is a mismatch; keep its text out of the error
        same = False
    if not same:
        raise RegenerationDiffers(f"{path.name} exists with different tables")


def generate_item(item: Item, out: Path, seed: int = DEFAULT_SEED) -> list[Path]:
    if not item.generated:
        raise ValueError(f"item {item.id!r} is not generated; use fetch.py")
    tables_only = item.format == "duckdb" and not {"empty_file", "malformed"} & set(item.shapes)
    written = []
    for name, data in render_item(item, seed).items():
        target = out / item.id / name
        if tables_only and target.exists():
            _check_existing_duckdb(item, target, seed)
        else:
            _publish(target, data)
        written.append(target)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--tier", action="append", choices=("S", "M", "L"), help="default: S and M")
    ap.add_argument("--item", action="append", help="build only these ids")
    args = ap.parse_args(argv)
    tiers = set(args.tier or ("S", "M"))
    items = [
        i
        for i in load_manifest(args.manifest)
        if i.generated and i.tier in tiers and (not args.item or i.id in args.item)
    ]
    for item in items:
        generate_item(item, args.out, args.seed)
        print(f"generated {item.id}")
    print(f"{len(items)} items under {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
