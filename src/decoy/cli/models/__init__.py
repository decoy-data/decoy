"""`decoy models`: list the detector models and install the NER model (SCAN-ML C1).

`decoy setup`, `decoy doctor` and the gate import the names exported here, never a `_` module.
`models_app` is registered in `decoy.__main__`. The names in `_LAZY` import the engine, so they
load on first use (PEP 562), as `decoy`'s own `_LAZY_API` does: importing this package for the
command tree must not import the engine.
"""

from __future__ import annotations

import importlib
from typing import Any

import typer

from decoy.cli.models._commands import (
    INSTALL_EPILOG,
    LIST_EPILOG,
    confirmer,
    fail,
    install_command,
    list_command,
    plan_lines,
    progress,
    result_doc,
)
from decoy.cli.models._errors import CODES, DP_NOTE, ModelsError

_LAZY = {
    "InstallPlan": "_install",
    "InstallResult": "_install",
    "install_ner": "_install",
    "doctor_rows": "_status",
    "hint": "_status",
    "install_command_text": "_status",
    "model_rows": "_status",
}


def __getattr__(name: str) -> Any:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(name)
    return getattr(importlib.import_module(f"{__name__}.{module}"), name)


models_app = typer.Typer(
    name="models",
    help="Detector models: see which can run here, and install NER.",
    no_args_is_help=True,
    add_completion=False,
)
models_app.command(name="list", epilog=LIST_EPILOG)(list_command)
models_app.command(name="install", epilog=INSTALL_EPILOG)(install_command)

__all__ = [
    "CODES",
    "DP_NOTE",
    "InstallPlan",
    "InstallResult",
    "ModelsError",
    "confirmer",
    "doctor_rows",
    "fail",
    "hint",
    "install_command_text",
    "install_ner",
    "model_rows",
    "models_app",
    "plan_lines",
    "progress",
    "result_doc",
]
