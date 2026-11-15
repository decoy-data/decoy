"""Refuse a change to the `--json` shape snapshot that leaves CHANGELOG.md untouched.

``check_shape_changelog.py --base <sha>`` lists the files changed between ``--base`` and ``HEAD``
(``git diff --name-only <base>...HEAD``). It exits 1 with ``shape_change_without_changelog`` when
``tests/fixtures/release_freeze/json-shapes.json`` is among them and ``CHANGELOG.md`` is not.
A sentry cannot do this: it sees one tree, not a diff. The CI job runs it on pull requests only.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

SHAPES = "tests/fixtures/release_freeze/json-shapes.json"
CHANGELOG = "CHANGELOG.md"
CODE = "shape_change_without_changelog"


def changed_files(base: str) -> set[str]:
    done = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        raise SystemExit(f"git diff against {base} failed: is the checkout deep enough?")
    return set(done.stdout.split())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, help="the commit the pull request branched from")
    files = changed_files(parser.parse_args(argv).base)
    if SHAPES in files and CHANGELOG not in files:
        print(
            f"{CODE}: {SHAPES} changed and {CHANGELOG} did not. A `--json` shape change is a "
            f"public-surface change: add a {CHANGELOG} entry.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
