"""An archive member name does not depend on the process locale (FREEZE-OUTPUT O2)."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

# 51 two-byte characters: over 100 UTF-8 bytes, so the tar header takes the PAX path too.
_NAME = "é" * 51 + ".csv"

_CHILD = """
import hashlib, os, sys
from pathlib import Path
import pandas as pd
from decoy.cli.io import write_private_table
out = Path(sys.argv[1]) / os.fsdecode(bytes.fromhex(sys.argv[2]) + sys.argv[3].encode())
write_private_table(pd.DataFrame({"a": [1]}), "csv", out)
print(hashlib.sha256(out.read_bytes()).hexdigest())
"""


def _run(tmp: Path, suffix: str, *, utf8_mode: str) -> tuple[str, Path]:
    env = {
        **os.environ,
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONUTF8": utf8_mode,
        "PYTHONCOERCECLOCALE": "0",
    }
    out = tmp / f"mode{utf8_mode}{suffix}"
    out.mkdir()
    # The name travels as hex so the child, not this process, decodes it under its own locale.
    args = [sys.executable, "-c", _CHILD, str(out), _NAME.encode().hex(), suffix]
    done = subprocess.run(args, env=env, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr[-400:]
    return done.stdout.strip(), out / (_NAME + suffix)


@pytest.mark.parametrize("suffix", [".tar", ".zip"])
def test_the_member_name_and_bytes_match_in_c_and_utf8_modes(tmp_path: Path, suffix: str) -> None:
    c_digest, c_file = _run(tmp_path, suffix, utf8_mode="0")
    utf8_digest, utf8_file = _run(tmp_path, suffix, utf8_mode="1")
    assert c_digest == utf8_digest
    assert c_file.read_bytes() == utf8_file.read_bytes()
    assert hashlib.sha256(c_file.read_bytes()).hexdigest() == c_digest
    if suffix == ".zip":
        assert zipfile.ZipFile(c_file).namelist() == [_NAME]
        assert zipfile.ZipFile(c_file).infolist()[0].flag_bits & 0x800
    else:
        assert tarfile.open(c_file, encoding="utf-8").getnames() == [_NAME]


def test_a_raw_byte_in_a_zip_member_name_becomes_the_replacement_character(
    tmp_path: Path,
) -> None:
    from decoy.cli.io._compression import PUBLIC_MEMBER_MODE, open_csv_sink

    target = Path(os.fsdecode(b"x\xff") + ".csv.zip")
    with open_csv_sink(tmp_path / "staged", target, member_mode=PUBLIC_MEMBER_MODE) as sink:
        sink.write(b"a\n1\n")
    assert zipfile.ZipFile(tmp_path / "staged").namelist() == ["x�.csv"]
