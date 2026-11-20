"""AT-10 (setup script): static checks only. The script creates OS users, so tests never run it."""

from __future__ import annotations

import shutil
import subprocess

import pytest
from tests.unit.qa._paths import QA_SCRIPTS

SCRIPT = QA_SCRIPTS / "setup-testers.sh"


def test_the_script_exists_and_parses() -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("no bash")
    done = subprocess.run([bash, "-n", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr


def test_the_script_guards_itself_and_names_both_platforms() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "--apply" in text, "default must be a dry run"
    assert "id -u" in text, "must check for root before changing users"
    assert "useradd" in text and "sysadminctl" in text
    assert "qatester-" in text
    assert "—" not in text
