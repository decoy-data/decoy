"""Fresh virtual environments and a local package index for the `decoy models install` tests.

A fresh venv gets the test interpreter's packages through one `.pth` overlay line, so it runs
this checkout of the CLI and the pinned engine without reinstalling them, while every package
the install adds lands in the fresh venv's own site-packages. The index is a PEP 503 simple
index served from a temporary directory on 127.0.0.1; it records every request path.
"""

from __future__ import annotations

import hashlib
import http.server
import io
import os
import subprocess
import sys
import sysconfig
import tarfile
import threading
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from packaging.utils import canonicalize_name, parse_wheel_filename

CANARY = "CANARY-PASSWORD"
CANARY_URL = f"https://user:{CANARY}@host.invalid/simple"
WHEELHOUSE_ENV = "DECOY_TEST_NER_WHEELHOUSE"
MODEL_WHEEL = "en_core_web_sm-3.8.0-py3-none-any.whl"
# Port 9 (discard) on loopback refuses at once: an index pip and uv can never reach.
UNREACHABLE_INDEX = "http://127.0.0.1:9/simple"


def wheelhouse() -> Path | None:
    """The prepared directory of `ner` closure wheels plus the model wheel, if one is set."""
    value = os.environ.get(WHEELHOUSE_ENV)
    return Path(value) if value and (Path(value) / MODEL_WHEEL).is_file() else None


def make_venv(root: Path, *, with_pip: bool) -> Path:
    """A fresh venv at `root` that sees this interpreter's packages; returns its python."""
    args = [sys.executable, "-m", "venv", str(root)]
    if not with_pip:
        args.insert(3, "--without-pip")
    subprocess.run(args, check=True, capture_output=True)
    python = root / "bin" / "python"
    purelib = subprocess.run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    overlay = sysconfig.get_paths()["purelib"]
    Path(purelib, "zz_test_overlay.pth").write_text(
        f"import site; site.addsitedir({overlay!r})\n", encoding="utf-8"
    )
    return python


def site_packages(python: Path) -> Path:
    out = subprocess.run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(out.stdout.strip())


def child_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PIP_", "UV_", "DECOY_"))}
    env.update({"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200", "PYTHONUTF8": "1"})
    env.update(extra)
    return env


def run_cli(
    python: Path, args: list[str], cwd: Path, env: dict[str, str], *, prelude: str = ""
) -> subprocess.CompletedProcess[str]:
    """`decoy ARGS` under `python`; `prelude` runs first in the same process (a test seam)."""
    code = f"{prelude}\nimport sys\nfrom decoy.__main__ import app\nsys.argv[0] = 'decoy'\napp()\n"
    return subprocess.run(
        [str(python), "-c", code, *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )


def installed(python: Path) -> dict[str, str]:
    """Canonical name to version of every distribution `python` sees."""
    code = (
        "import json, importlib.metadata as m\n"
        "print(json.dumps({d.metadata['Name']: d.version for d in m.distributions()}))"
    )
    out = subprocess.run([str(python), "-c", code], check=True, capture_output=True, text=True)
    import json

    return {str(canonicalize_name(k)): v for k, v in json.loads(out.stdout).items()}


def ner_available(python: Path) -> bool:
    code = "from decoy_engine import ner_status; print(ner_status().available)"
    out = subprocess.run([str(python), "-c", code], capture_output=True, text=True, check=False)
    return out.stdout.strip() == "True"


def fake_wheel(directory: Path, name: str, version: str, requires: tuple[str, ...] = ()) -> Path:
    """A minimal pure wheel with no code: only its metadata."""
    dist = f"{name.replace('-', '_')}-{version}"
    meta = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    meta += "".join(f"Requires-Dist: {r}\n" for r in requires)
    files = {
        f"{dist}.dist-info/METADATA": meta,
        f"{dist}.dist-info/WHEEL": "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
    }
    record = "".join(f"{p},,\n" for p in files) + f"{dist}.dist-info/RECORD,,\n"
    files[f"{dist}.dist-info/RECORD"] = record
    path = directory / f"{dist}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as zf:
        for member, text in files.items():
            zf.writestr(member, text)
    return path


def fake_sdist(directory: Path, name: str, version: str, marker: Path) -> Path:
    """An sdist whose setup.py writes `marker`: proof that something built it."""
    base = f"{name}-{version}"
    setup = f"open({str(marker)!r}, 'w').write('built')\nfrom setuptools import setup\nsetup()\n"
    path = directory / f"{base}.tar.gz"
    with tarfile.open(path, "w:gz") as tf:
        for member, text in {
            f"{base}/setup.py": setup,
            f"{base}/PKG-INFO": f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
        }.items():
            data = text.encode()
            info = tarfile.TarInfo(member)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return path


def _project(filename: str) -> str:
    if filename.endswith(".whl"):
        return str(parse_wheel_filename(filename)[0])
    return str(canonicalize_name(filename.rsplit("-", 1)[0]))


class _Index(http.server.SimpleHTTPRequestHandler):
    requests: list[str]

    def log_message(self, *args: object) -> None:
        return

    def do_GET(self) -> None:
        self.requests.append(self.path)
        super().do_GET()


@contextmanager
def serve_index(files: list[Path], root: Path) -> Iterator[tuple[str, list[str]]]:
    """Serve `files` as a simple index under `root`; yields (base URL, request log)."""
    projects: dict[str, list[Path]] = {}
    (root / "files").mkdir(parents=True)
    for f in files:
        (root / "files" / f.name).write_bytes(f.read_bytes())
        projects.setdefault(_project(f.name), []).append(f)
    for project, members in projects.items():
        page = root / "simple" / project
        page.mkdir(parents=True)
        links = "".join(
            f'<a href="../../files/{f.name}#sha256={hashlib.sha256(f.read_bytes()).hexdigest()}">'
            f"{f.name}</a>\n"
            for f in members
        )
        (page / "index.html").write_text(f"<html><body>\n{links}</body></html>\n")
    log: list[str] = []
    handler = type("Handler", (_Index,), {"requests": log})

    def factory(*args: object, **kwargs: object) -> _Index:
        return handler(*args, directory=str(root), **kwargs)  # type: ignore[arg-type]

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), factory)  # type: ignore[arg-type]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", log
    finally:
        server.shutdown()
        server.server_close()
