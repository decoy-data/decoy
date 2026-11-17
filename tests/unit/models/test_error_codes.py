"""The `models.*` code list is the module's constants, and every raise site names one of them."""

from __future__ import annotations

import ast
from pathlib import Path

from decoy.cli.models import CODES, _errors

_SRC = Path(__file__).resolve().parents[3] / "src" / "decoy" / "cli"


def _constants() -> dict[str, str]:
    return {
        name: value
        for name, value in vars(_errors).items()
        if name.isupper() and isinstance(value, str) and value.startswith("models.")
    }


def test_codes_holds_every_models_constant() -> None:
    assert set(CODES) == set(_constants().values())
    assert len(CODES) == len(set(CODES))


def test_every_raise_site_names_a_registered_code() -> None:
    known = _constants()
    sites = 0
    for path in (*(_SRC / "models").glob("*.py"), *(_SRC / "setup").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "ModelsError"
                and node.args
            ):
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and first.value is None:
                continue  # a refused prompt: no code
            if isinstance(first, ast.Name) and first.id in known:
                sites += 1
                continue
            if isinstance(first, ast.Call):
                continue  # a reason code from the engine's registry (`str(reasons...)`)
            raise AssertionError(
                f"{path.name}:{node.lineno} raises ModelsError with an unlisted code"
            )
    assert sites >= len(known)
