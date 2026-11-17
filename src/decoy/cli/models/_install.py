"""Install spaCy and one NER model into the running interpreter (`decoy models install ner`).

Pattern: pip's documented safety controls (plan 4.6, section 2): `--only-binary :all:` on every
call so no build step runs; `--constraint` with one `name==version` line per installed
distribution (`installed_distribution_set()`, the DP gate's own set) so nothing installed can
move; the model as one wheel pinned by URL and SHA-256 under `--require-hashes --no-deps`
(Presidio and spaCy install models as pip packages); `--no-index --find-links` over a private
copy for offline installs. uv's `uv pip install --python` takes the same flags, for venvs without
pip. `decoy-engine` is never named to pip: it is not on PyPI, and a public package of that name
could resolve.

Installer output is captured and discarded, never replayed: a configured index URL can carry a
credential. Errors carry fixed text, names, versions and the integer exit code only, and are
raised outside any `except` block.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from decoy_engine import ModelStatus, ner_status, reasons
from decoy_engine.detection import ner as engine_ner
from decoy_engine.detection.types import validate_ner_model_name
from decoy_engine.quality.dp_provenance import installed_distribution_set
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from decoy.cli.models._errors import (
    ENV_CHANGED,
    INSTALL_FAILED,
    MANAGED_RUNTIME,
    MODEL_UNPINNED,
    PIP_MISSING,
    SOURCE_INVALID,
    ModelsError,
)
from decoy.cli.models._private import private_workdir, write_private
from decoy.cli.models._source import StagedSource, stage_source
from decoy.distribution.layout import managed_home

_ENGINE = "decoy-engine"
# Exit status a shell gives a command it could not start.
_NOT_STARTED = 127


@dataclass(frozen=True)
class InstallPlan:
    model: str
    version: str
    packages: tuple[str, ...]  # requirement names the closure step installs, then the model
    offline: bool
    installer: str  # "pip" or "uv"
    interpreter: str


@dataclass(frozen=True)
class InstallResult:
    model: str
    version: str
    runtime_version: str | None
    installed: tuple[str, ...]  # canonical names new to the environment
    installer: str | None  # None when the model was already available
    already_installed: bool


def _run_captured(argv: list[str]) -> int:
    """Run one installer call with its output captured and dropped; return its exit status."""
    try:
        done = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        return _NOT_STARTED
    return done.returncode


run_installer: Callable[[list[str]], int] = _run_captured


def pip_available() -> bool:
    return _run_captured([sys.executable, "-m", "pip", "--version"]) == 0


def _pin(model: str, version: str | None) -> engine_ner.NerModelWheel | None:
    rows = {v: w for (m, v), w in engine_ner.NER_MODEL_WHEELS.items() if m == model}
    if version is not None:
        return rows.get(version)
    return rows[max(rows, key=Version)] if rows else None


def _pinned_version(model: str) -> str | None:
    versions = [v for (m, v) in engine_ner.NER_MODEL_WHEELS if m == model]
    return max(versions, key=Version) if versions else None


def _uv_route() -> str:
    pin = _pin(engine_ner.DEFAULT_NER_MODEL, None)
    url = pin.url if pin is not None else "<model wheel>"
    return f"install Decoy with: uv tool install 'decoy-cli[ner]' --with {url}"


def installer_prefix() -> tuple[list[str], str]:
    if pip_available():
        return [sys.executable, "-m", "pip", "install"], "pip"
    uv = shutil.which("uv")
    if uv is not None:
        return [uv, "pip", "install", "--python", sys.executable], "uv"
    raise ModelsError(
        PIP_MISSING,
        "this interpreter has no pip, and uv is not on PATH.",
        hint=_uv_route(),
    )


def ner_requirements() -> list[str]:
    """The engine's `ner` extra, read from its installed metadata (never asked of pip)."""
    out = []
    for text in importlib.metadata.requires(_ENGINE) or ():
        req = Requirement(text)
        if req.marker is None or not req.marker.evaluate({"extra": "ner"}):
            continue
        if req.marker.evaluate({"extra": ""}):
            continue  # a base dependency, already installed with the engine
        extras = f"[{','.join(sorted(req.extras))}]" if req.extras else ""
        out.append(f"{req.name}{extras}{req.specifier}")
    return sorted(out)


def _satisfied(text: str, have: dict[str, str]) -> bool:
    req = Requirement(text)
    version = have.get(str(canonicalize_name(req.name)))
    return version is not None and req.specifier.contains(version, prereleases=True)


def constraint_lines(before: tuple[tuple[str, str], ...]) -> list[str]:
    # The engine is left out so pip is never told its name, not even as a constraint.
    return [f"{name}=={version}" for name, version in before if name != _ENGINE]


def _names(requirements: list[str]) -> tuple[str, ...]:
    return tuple(Requirement(r).name for r in requirements)


def _step(prefix: list[str], constraints: Path, *args: str) -> list[str]:
    return [*prefix, "--only-binary", ":all:", "--constraint", str(constraints), *args]


def _run(argv: list[str]) -> None:
    code = run_installer(argv)
    if code != 0:
        raise ModelsError(
            INSTALL_FAILED,
            f"the installer exited with code {code}; nothing was rolled back.",
            hint="check the network or pass --from with a wheel directory; reinstall Decoy to "
            "restore the environment.",
            context={"installer_exit_code": code},
        )


def _verify(model: str, before: tuple[tuple[str, str], ...]) -> tuple[ModelStatus, tuple[str, ...]]:
    importlib.invalidate_caches()  # pip wrote new packages into a path this process already scanned
    status = ner_status(model)
    if not status.available:
        raise ModelsError(
            INSTALL_FAILED,
            f"the packages installed but {model} does not load here ({status.reason}).",
            hint="install the model wheel pinned for this spaCy; reinstall Decoy to restore the "
            "environment.",
        )
    after = dict(installed_distribution_set())
    moved = [f"{n} {v} -> {after.get(n, 'removed')}" for n, v in before if after.get(n) != v]
    if moved:
        raise ModelsError(
            ENV_CHANGED,
            "the install changed installed packages: " + ", ".join(moved) + ".",
            hint="reinstall Decoy to restore the environment.",
        )
    old = {n for n, _ in before}
    return status, tuple(sorted(n for n in after if n not in old))


def _execute(
    model: str,
    staged: StagedSource | None,
    workdir: Path,
    confirm: Callable[[InstallPlan], bool],
    progress: Callable[[str], None],
) -> InstallResult:
    version = staged.model_version if staged is not None else _pinned_version(model)
    pin = _pin(model, version) if version is not None else None
    if version is None:
        raise ModelsError(
            MODEL_UNPINNED,
            f"{model} has no pinned wheel, so it cannot install from the network.",
            hint="download its wheel and pass it with --from.",
        )
    before = installed_distribution_set()
    have = dict(before)
    wanted = ner_requirements() + ([f"spacy{pin.spacy_range}"] if pin is not None else [])
    missing = [r for r in wanted if not _satisfied(r, have)]
    if staged is not None and staged.single and missing:
        raise ModelsError(
            SOURCE_INVALID,
            "a single model wheel installs only where spaCy and the ner packages are already "
            "installed.",
            hint="pass a directory holding the ner closure wheels and the model wheel.",
        )
    prefix, installer = installer_prefix()
    plan = InstallPlan(
        model, version, (*_names(missing), model), staged is not None, installer, sys.executable
    )
    if not confirm(plan):
        raise ModelsError(None, "nothing was installed.")
    constraints = workdir / "constraints.txt"
    write_private(constraints, "".join(f"{ln}\n" for ln in constraint_lines(before)).encode())
    offline = ["--no-index", "--find-links", str(staged.directory)] if staged is not None else []
    if missing:
        progress(f"Installing {', '.join(_names(missing))} ({installer})")
        _run(_step(prefix, constraints, *offline, *missing))
    progress(f"Installing {model} {version} ({installer})")
    if staged is not None or pin is None:
        _run(_step(prefix, constraints, *offline, "--no-deps", f"{model}=={version}"))
    else:
        pinned = workdir / "model.txt"
        write_private(pinned, f"{model} @ {pin.url} --hash=sha256:{pin.sha256}\n".encode())
        _run(_step(prefix, constraints, "--require-hashes", "--no-deps", "-r", str(pinned)))
    progress(f"Checking that {model} loads")
    status, new = _verify(model, before)
    return InstallResult(
        model, status.version or version, status.runtime_version, new, installer, False
    )


def model_name_error(model: str) -> ModelsError | None:
    """The refusal for a model name that is not a plain spaCy package name, else None.

    The engine's one name rule (`validate_ner_model_name`); the name is never echoed.
    """
    try:
        validate_ner_model_name(model)
    except engine_ner.NerModelNameError:
        return ModelsError(
            str(reasons.config.NER_MODEL_INVALID),
            "--model must be a plain package name (lowercase letters, digits, _).",
        )
    return None


def install_ner(
    *,
    model: str,
    source: Path | None,
    confirm: Callable[[InstallPlan], bool],
    progress: Callable[[str], None] = lambda text: None,
) -> InstallResult:
    """Install spaCy and `model`, from the index or from `source`; raise `ModelsError`."""
    bad_name = model_name_error(model)
    if bad_name is not None:
        raise bad_name
    if managed_home() is not None:
        raise ModelsError(
            MANAGED_RUNTIME,
            "the managed runtime is a signed bundle; models are not installed into it.",
            hint=_uv_route(),
        )
    workdir = private_workdir()
    try:
        staged = stage_source(source, workdir, model) if source is not None else None
        current = ner_status(model)
        if current.available:
            version = current.version or ""
            return InstallResult(model, version, current.runtime_version, (), None, True)
        return _execute(model, staged, workdir, confirm, progress)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
