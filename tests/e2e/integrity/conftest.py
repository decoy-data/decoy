"""The real-model venv for the C2a tests that need spaCy and its model.

`ner_python` is a fresh venv holding the dev lock, this checkout and the `ner` closure installed
from the wheelhouse `DECOY_TEST_NER_WHEELHOUSE` names (the wheelhouse the C1 install tests use).
Without it, every test that asks for the fixture skips.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.e2e.models._venvs import child_env, make_full_venv, wheelhouse


@pytest.fixture(scope="session")
def ner_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A fresh venv with the dev lock, this checkout and the `ner` closure from the wheelhouse."""
    house = wheelhouse()
    if house is None:
        pytest.skip("set DECOY_TEST_NER_WHEELHOUSE to a prepared ner wheelhouse")
    python = make_full_venv(tmp_path_factory.mktemp("ner-venv") / "venv", with_pip=False)
    uv = shutil.which("uv")
    assert uv is not None
    install = [uv, "pip", "install", "-q", "--python", str(python), "--no-index"]
    subprocess.run(
        [*install, "--find-links", str(house), "spacy", "en_core_web_sm"],
        check=True,
        capture_output=True,
        env=child_env(),
    )
    return python
