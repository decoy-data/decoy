"""The fixed-width layout rules live in `scanning/_layout.py`, free of `decoy.cli.scan` (T2-layout-move)."""

from __future__ import annotations

import subprocess
import sys


def test_layout_module_does_not_import_the_scan_command() -> None:
    code = (
        "import sys, decoy.cli.scanning._layout as m\n"
        "assert 'decoy.cli.scan' not in sys.modules, 'layout pulled in decoy.cli.scan'\n"
        "assert m._parse_layout and m._check_layout_columns\n"
    )
    done = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
