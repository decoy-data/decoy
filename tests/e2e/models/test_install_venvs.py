"""AT-C1b, AT-C1i, AT-C1j and the `NER_MODEL_WHEELS` range check, in fresh venvs.

Each test runs the real `decoy models install ner` in a child process whose interpreter is a
fresh venv (see `_venvs.py`). The fake-installer tests need nothing else. The rest need a prepared
wheelhouse: a directory holding the `ner` closure wheels and the pinned model wheel, named by
`DECOY_TEST_NER_WHEELHOUSE`; without it they skip. AT-C1b runs only on the owner's Mac mini
(`DECOY_TEST_OWNER_MACMINI=1`).

Mutations: M-C1i (inherit installer stderr) and M-C1i2 (accept a lone model wheel into a fresh
environment); M-C1j (name `decoy-engine[ner]` to pip) and M-C1j2 (drop `--constraint`); M-C1b
(drop `--no-index`).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from decoy_engine.detection.ner import NER_MODEL_WHEELS

from tests.e2e.models._venvs import (
    CANARY,
    CANARY_URL,
    MODEL_WHEEL,
    UNREACHABLE_INDEX,
    child_env,
    fake_sdist,
    fake_wheel,
    installed,
    make_full_venv,
    make_venv,
    ner_available,
    run_cli,
    serve_index,
    site_packages,
    wheelhouse,
)

pytestmark = [
    pytest.mark.timeout(1200),
    pytest.mark.skipif(sys.platform == "win32", reason="POSIX venv layout"),
]
needs_wheelhouse = pytest.mark.skipif(
    wheelhouse() is None, reason="set DECOY_TEST_NER_WHEELHOUSE to a prepared ner wheelhouse"
)

_FAKE_PIP = f"""\
import sys
text = "Looking in indexes: {CANARY_URL}"
print(text)
print(text, file=sys.stderr)
sys.exit(0 if "--version" in sys.argv else 1)
"""


def _doc(proc) -> dict:
    lines = proc.stdout.strip().splitlines()
    assert len(lines) == 1, (proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:])
    return json.loads(lines[0])


def _no_canary(proc, cwd: Path) -> None:
    assert CANARY not in proc.stdout
    assert CANARY not in proc.stderr
    for log in cwd.rglob("*.log"):
        assert CANARY not in log.read_text(encoding="utf-8", errors="replace")


@pytest.mark.parametrize("route", ["pip", "uv"])
def test_installer_output_and_index_url_never_leak(route: str, tmp_path: Path) -> None:
    python = make_venv(tmp_path / "venv", with_pip=False)
    env = child_env(PIP_INDEX_URL=CANARY_URL, UV_INDEX_URL=CANARY_URL, UV_DEFAULT_INDEX=CANARY_URL)
    if route == "pip":
        pkg = site_packages(python) / "pip"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "__main__.py").write_text(_FAKE_PIP)
    else:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        uv = bin_dir / "uv"
        uv.write_text(f"#!{sys.executable}\n{_FAKE_PIP}")
        uv.chmod(0o755)
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    work = tmp_path / "work"
    work.mkdir()
    proc = run_cli(python, ["models", "install", "ner", "--yes", "--json"], work, env)
    assert proc.returncode == 3, (proc.stdout, proc.stderr)
    assert _doc(proc)["code"] == "models.install_failed"
    _no_canary(proc, work)
    human = run_cli(python, ["models", "install", "ner", "--yes"], work, env)
    assert human.returncode == 3
    _no_canary(human, work)


@needs_wheelhouse
def test_a_lone_model_wheel_needs_the_closure_already_installed(tmp_path: Path) -> None:
    wh = wheelhouse()
    assert wh is not None
    env = child_env(PIP_INDEX_URL=UNREACHABLE_INDEX, UV_DEFAULT_INDEX=UNREACHABLE_INDEX)
    work = tmp_path / "work"
    work.mkdir()

    bare = make_full_venv(tmp_path / "bare", with_pip=True)
    before = installed(bare)
    proc = run_cli(
        bare,
        ["models", "install", "ner", "--from", str(wh / MODEL_WHEEL), "--yes", "--json"],
        work,
        env,
    )
    assert proc.returncode == 1, proc.stdout
    assert _doc(proc)["code"] == "models.source_invalid"
    assert installed(bare) == before

    ready = make_full_venv(tmp_path / "ready", with_pip=True)
    closure = [str(p) for p in wh.glob("*.whl") if p.name != MODEL_WHEEL]
    subprocess.run(
        [
            str(ready),
            "-m",
            "pip",
            "install",
            "-q",
            "--no-index",
            "--find-links",
            str(wh),
            "spacy",
            "click",
        ],
        check=True,
        env=env,
        capture_output=True,
    )
    assert closure
    proc = run_cli(
        ready,
        ["models", "install", "ner", "--from", str(wh / MODEL_WHEEL), "--yes", "--json"],
        work,
        env,
    )
    assert proc.returncode == 0, (proc.stdout[-2000:], proc.stderr[-2000:])
    assert ner_available(ready)


@needs_wheelhouse
@pytest.mark.parametrize("route", ["pip", "uv"])
def test_a_wheelhouse_installs_closure_and_model_with_no_network(
    route: str, tmp_path: Path
) -> None:
    wh = wheelhouse()
    assert wh is not None
    python = make_full_venv(tmp_path / "venv", with_pip=route == "pip")
    env = child_env(PIP_INDEX_URL=UNREACHABLE_INDEX, UV_DEFAULT_INDEX=UNREACHABLE_INDEX)
    work = tmp_path / "work"
    work.mkdir()
    before = installed(python)
    proc = run_cli(
        python, ["models", "install", "ner", "--from", str(wh), "--yes", "--json"], work, env
    )
    assert proc.returncode == 0, (proc.stdout[-2000:], proc.stderr[-2000:])
    assert ner_available(python)
    after = installed(python)
    assert {k: v for k, v in after.items() if k in before} == before


@needs_wheelhouse
def test_each_pinned_model_range_matches_its_wheel_meta(tmp_path: Path) -> None:
    wh = wheelhouse()
    assert wh is not None
    for (model, version), pin in NER_MODEL_WHEELS.items():
        path = wh / f"{model}-{version}-py3-none-any.whl"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == pin.sha256
        with zipfile.ZipFile(path) as zf:
            meta = json.loads(zf.read(f"{model}/meta.json"))
        assert meta["spacy_version"] == pin.spacy_range


_PIN_PRELUDE = """\
import sys
from types import MappingProxyType
from decoy_engine.detection import ner
key = (ner.DEFAULT_NER_MODEL, ner.DEFAULT_NER_MODEL_VERSION)
ner.NER_MODEL_WHEELS = MappingProxyType({key: ner.NER_MODEL_WHEELS[key]._replace(url=sys.argv.pop(1))})
"""


@needs_wheelhouse
@pytest.mark.parametrize("route", ["pip", "uv"])
def test_online_install_never_asks_for_decoy_engine_and_moves_nothing(
    route: str, tmp_path: Path
) -> None:
    wh = wheelhouse()
    assert wh is not None
    extra = tmp_path / "extra"
    extra.mkdir()
    marker = tmp_path / "sdist-built"
    files = [p for p in wh.glob("*.whl")]
    files += [
        fake_sdist(extra, "decoy-engine", "99.0.0", marker),
        fake_wheel(extra, "decoy-engine", "99.0.0"),
        fake_wheel(extra, "numpy", "99.0.0"),
        fake_wheel(extra, "pandas", "99.0.0"),
    ]
    python = make_full_venv(tmp_path / "venv", with_pip=route == "pip")
    before = installed(python)
    work = tmp_path / "work"
    work.mkdir()
    with serve_index(files, tmp_path / "index") as (base, requests):
        env = child_env(
            PIP_INDEX_URL=f"{base}/simple/",
            UV_DEFAULT_INDEX=f"{base}/simple/",
            UV_INDEX_URL=f"{base}/simple/",
        )
        args = [f"{base}/files/{MODEL_WHEEL}", "models", "install", "ner", "--yes", "--json"]
        proc = run_cli(python, args, work, env, prelude=_PIN_PRELUDE)
    assert proc.returncode == 0, (proc.stdout[-2000:], proc.stderr[-2000:])
    assert not any("decoy-engine" in r or "decoy_engine" in r for r in requests), requests
    assert not marker.exists()
    after = installed(python)
    for name in ("numpy", "pandas", "decoy-engine", "decoy-cli"):
        assert after[name] == before[name]
    closure = {str(p.name.split("-")[0]).lower().replace("_", "-") for p in wh.glob("*.whl")}
    assert set(after) - set(before) <= closure
    assert ner_available(python)


@needs_wheelhouse
def test_online_install_never_moves_an_installed_closure_member(tmp_path: Path) -> None:
    wh = wheelhouse()
    assert wh is not None
    old = fake_wheel(tmp_path, "catalogue", "2.0.0")  # spaCy needs >=2.0.6
    python = make_full_venv(tmp_path / "venv", with_pip=True)
    subprocess.run(
        [str(python), "-m", "pip", "install", "-q", "--no-index", str(old)],
        check=True,
        capture_output=True,
    )
    work = tmp_path / "work"
    work.mkdir()
    with serve_index(list(wh.glob("*.whl")), tmp_path / "index") as (base, _):
        env = child_env(PIP_INDEX_URL=f"{base}/simple/")
        args = [f"{base}/files/{MODEL_WHEEL}", "models", "install", "ner", "--yes", "--json"]
        proc = run_cli(python, args, work, env, prelude=_PIN_PRELUDE)
    assert proc.returncode == 3, (proc.stdout[-2000:], proc.stderr[-2000:])
    assert installed(python)["catalogue"] == "2.0.0"


@pytest.mark.skipif(
    sys.platform != "darwin" or os.environ.get("DECOY_TEST_OWNER_MACMINI") != "1",
    reason="AT-C1b runs on the owner's Mac mini with no network",
)
@needs_wheelhouse
def test_mac_mini_offline_wheelhouse_install(tmp_path: Path) -> None:
    wh = wheelhouse()
    assert wh is not None
    python = make_full_venv(tmp_path / "venv", with_pip=True)
    env = child_env(PIP_INDEX_URL=UNREACHABLE_INDEX, UV_DEFAULT_INDEX=UNREACHABLE_INDEX)
    work = tmp_path / "work"
    work.mkdir()
    proc = run_cli(
        python, ["models", "install", "ner", "--from", str(wh), "--yes", "--json"], work, env
    )
    assert proc.returncode == 0, (proc.stdout[-2000:], proc.stderr[-2000:])
    names = installed(python)
    assert {"spacy", "click", "en-core-web-sm"} <= set(names)
    assert ner_available(python)
