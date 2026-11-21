"""A rig for `decoy models install` in-process: the one installer seam replaced by a recorder.

The rig never lets a real pip or uv run: `run_installer` (the one subprocess call) is replaced,
and `pip_available`, `ner_status`, `installed_distribution_set` and `managed_home` are faked on
the install module. Temporary directories go under a per-test base so a test can prove none is
left behind.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from decoy_engine import ModelStatus
from typer.testing import CliRunner

from decoy.__main__ import app

BEFORE = (
    ("decoy-cli", "0.1.0"),
    ("decoy-engine", "0.27.0"),
    ("numpy", "2.2.6"),
    ("pandas", "2.3.3"),
)
NEW = (("en-core-web-sm", "3.8.0"), ("spacy", "3.8.18"))
UNAVAILABLE = ModelStatus(
    "ner", "en_core_web_sm", False, None, None, "provider.ner_spacy_not_installed"
)
AVAILABLE = ModelStatus("ner", "en_core_web_sm", True, "3.8.0", "3.8.18", None)


def install_module() -> ModuleType:
    return importlib.import_module("decoy.cli.models._install")


@dataclass
class Call:
    argv: list[str]
    files: dict[str, Any] = field(default_factory=dict)


def _value_after(argv: list[str], flag: str) -> str | None:
    return argv[argv.index(flag) + 1] if flag in argv else None


def _snapshot(argv: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for flag in ("--constraint", "-r"):
        path = _value_after(argv, flag)
        if path is not None:
            out[flag] = Path(path).read_text(encoding="utf-8")
    links = _value_after(argv, "--find-links")
    if links is not None:
        out["--find-links"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(links).iterdir()
        }
    return out


@dataclass
class Rig:
    mod: ModuleType
    tmpbase: Path
    calls: list[Call] = field(default_factory=list)
    rc: int = 0
    installs: bool = True  # a successful call makes the model available
    changed: bool = False  # a successful call also moves numpy
    hook: Any = None  # run inside the installer call, before it returns
    real_set: bool = False
    available: bool = False

    def run_installer(self, argv: list[str]) -> int:
        self.calls.append(Call(list(argv), _snapshot(argv)))
        if self.hook is not None:
            self.hook(argv)
        if self.rc == 0 and self.installs:
            self.available = True
        return self.rc

    def ner_status(self, model: str = "en_core_web_sm") -> ModelStatus:
        return AVAILABLE if self.available else UNAVAILABLE

    def installed_set(self) -> tuple[tuple[str, str], ...]:
        if not self.available:
            return BEFORE
        moved = tuple(
            ("numpy", "2.3.0") if n == "numpy" and self.changed else (n, v) for n, v in BEFORE
        )
        return tuple(sorted(moved + NEW))

    def leftovers(self) -> list[str]:
        return sorted(p.name for p in self.tmpbase.iterdir())

    def invoke(self, *args: str) -> Any:
        return CliRunner().invoke(app, ["models", "install", "ner", *args])

    def json(self, *args: str) -> tuple[int, dict[str, Any]]:
        result = self.invoke(*args, "--json")
        lines = result.stdout.strip().splitlines()
        assert len(lines) == 1, (result.exit_code, result.stdout, result.stderr)
        return result.exit_code, json.loads(lines[0])


def make_rig(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, real_set: bool = False) -> Rig:
    mod = install_module()
    base = tmp_path / "tmpbase"
    base.mkdir(parents=True)
    monkeypatch.setattr(tempfile, "tempdir", str(base))
    rig = Rig(mod, base, real_set=real_set)
    monkeypatch.setattr(mod, "run_installer", rig.run_installer)
    monkeypatch.setattr(mod, "pip_available", lambda: True)
    monkeypatch.setattr(mod, "ner_status", rig.ner_status)
    monkeypatch.setattr(mod, "managed_home", lambda: None)
    if not real_set:
        monkeypatch.setattr(mod, "installed_distribution_set", rig.installed_set)
    return rig


def wheel(directory: Path, name: str, data: bytes = b"wheel") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(data)
    return path
