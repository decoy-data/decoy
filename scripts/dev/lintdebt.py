"""Lint-debt ratchet: ruff rules the CI `ruff check` does not select, counted per file and rule.

Usage: lintdebt.py [--root DIR] [--ruff PATH] [--init | --shrink] [PATH ...]
  PATH      what ruff scans, relative to --root (default: src tests)
  --init    write the baseline from the current tree; refused when the baseline exists
  --shrink  lower baseline counts to the current ones and drop keys that reached 0; never raises
            a count and never adds a key
The rules are added with `--extend-select` on this run only, so the `ruff check` that CI runs is
unchanged. Each hit is counted under the key `<file>::<rule>` in the baseline registered as
`lint-debt` (``tests/sentry/baselines/lint-debt.json``, entry field ``count``). The comparison
is per key: a count above the baseline, or a key the baseline lacks, fails. A count below the
baseline passes and says to run --shrink. The shared ratchet (`ratchet_check.py`) then holds the
baseline file itself shrink-only against the merge base. Output names files, rules and counts,
never source text.
Exit 0 clean, 1 on new debt, 2 when ruff or the baseline cannot be read.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

SENTRY_ID = "lint-debt"
CREATED_IN = "LINTDEBT-A1"
BASELINE_REL = f"tests/sentry/baselines/{SENTRY_ID}.json"
REASON = "hit present when the lint-debt ratchet was recorded (2026-11-22); may only shrink"
# S110 and S112 are engine-only: the CLI keeps them ignored.
EXTRA_RULES = (
    "BLE001",
    "PGH003",
    "ANN401",
    "PTH",
    "PLW1514",
    "ERA001",
    "C901",
    "PLR0912",
    "PLR0915",
    "T20",
)
# The one module that may print: it is the output layer.
PRINT_OK = "src/decoy/ui/output.py"
DEFAULT_PATHS = ("src", "tests")


def _load_ratchet(root: Path):
    # Loaded by path, like ratchet_check.py: tests/sentry is not a package.
    path = root / "tests" / "sentry" / "_ratchet.py"
    spec = importlib.util.spec_from_file_location("_ratchet_for_lintdebt", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def find_ruff(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    sibling = Path(sys.executable).parent / "ruff"
    return str(sibling) if sibling.exists() else shutil.which("ruff")


def count_hits(root: Path, ruff: str, paths: list[str]) -> Counter[str]:
    """``{"<file>::<rule>": hits}`` for the extra rules, from one ruff run in report mode."""
    cmd = [
        ruff,
        "check",
        "--no-cache",
        "--exit-zero",
        "--output-format",
        "json",
        "--extend-select",
        ",".join(EXTRA_RULES),
        *paths,
    ]
    res = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ruff exited {res.returncode}")
    counts: Counter[str] = Counter()
    for item in json.loads(res.stdout or "[]"):
        code = item.get("code") or ""
        if not any(code.startswith(r) for r in EXTRA_RULES):
            continue  # a rule CI already selects is the normal ruff step's job
        rel = Path(item["filename"]).resolve().relative_to(root.resolve()).as_posix()
        if code.startswith("T20") and rel == PRINT_OK:
            continue
        counts[f"{rel}::{code}"] += 1
    return counts


def compare(counts: Counter[str], base: dict[str, int]) -> tuple[list[str], list[str]]:
    """``(new_debt, shrinkable)`` lines; ids and counts only."""
    new, shrink = [], []
    for key in sorted(set(counts) | set(base)):
        now, was = counts.get(key, 0), base.get(key)
        file, rule = key.split("::")
        if was is None:
            new.append(f"{file} {rule}: {now} hit(s), not in the baseline")
        elif now > was:
            new.append(f"{file} {rule}: {now} hit(s), baseline allows {was}")
        elif now < was:
            shrink.append(f"{file} {rule}: {now} hit(s), baseline holds {was}")
    return new, shrink


def _dump(entries: dict[str, int]) -> str:
    doc = {
        "sentry_id": SENTRY_ID,
        "created_in": CREATED_IN,
        "entries": {k: {"reason": REASON, "count": v} for k, v in sorted(entries.items())},
    }
    return json.dumps(doc, indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--ruff")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--init", action="store_true")
    mode.add_argument("--shrink", action="store_true")
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    ruff = find_ruff(args.ruff)
    if ruff is None:
        print("lintdebt: no ruff found; pass --ruff or install the dev lock", file=sys.stderr)
        return 2
    try:
        counts = count_hits(root, ruff, args.paths or list(DEFAULT_PATHS))
    except (RuntimeError, ValueError, KeyError) as err:
        print(f"lintdebt: could not read the ruff report: {type(err).__name__}", file=sys.stderr)
        return 2
    target = root / BASELINE_REL
    if args.init:
        if target.exists():
            print(f"lintdebt: {BASELINE_REL} exists; use --shrink to lower it", file=sys.stderr)
            return 2
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_dump(dict(counts)), encoding="utf-8")
        print(f"lintdebt: wrote {len(counts)} key(s), {sum(counts.values())} hit(s)")
        return 0
    try:
        entries = _load_ratchet(root).load_allowlist(SENTRY_ID, root)
        base = {k: int(v["count"]) for k, v in entries.items()}
    except (OSError, KeyError, ValueError, TypeError) as err:
        print(f"lintdebt: could not read {BASELINE_REL}: {type(err).__name__}", file=sys.stderr)
        return 2
    new, shrinkable = compare(counts, base)
    for line in new:
        print(f"lintdebt: FAIL {line}", file=sys.stderr)
    if new:
        print("lintdebt: fix the hit; the baseline never grows", file=sys.stderr)
        return 1
    if args.shrink:
        kept = {k: counts[k] for k in base if counts.get(k, 0) > 0}
        target.write_text(_dump(kept), encoding="utf-8")
        print(f"lintdebt: shrank {len(shrinkable)} key(s); {len(kept)} remain")
    elif shrinkable:
        for line in shrinkable:
            print(f"lintdebt: below baseline: {line}")
        print("lintdebt: run `python scripts/dev/lintdebt.py --shrink` and commit the baseline")
    else:
        print(f"lintdebt: ok, {len(counts)} key(s), {sum(counts.values())} hit(s) at baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
