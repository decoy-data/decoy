"""CLI-SPLIT: a command that became a package keeps the names its old module exported."""

from __future__ import annotations

import importlib

import pytest

# Every non-underscore name the single-file `decoy/cli/fit.py` bound at d6b9e4c7 (it had no
# `__all__`, so a wildcard import yielded all of them).
_FIT_BASE_NAMES = frozenset(
    {
        "AtomicWriteError",
        "Any",
        "EXIT_RUNTIME",
        "EXIT_USAGE",
        "FIT_EPILOG",
        "FIT_SAMPLE_SEED",
        "FitSourceError",
        "OutputMode",
        "Path",
        "ResourceError",
        "WriteMode",
        "annotations",
        "code",
        "describe",
        "emit_error",
        "emit_json",
        "exit_code_for",
        "fit",
        "fit_exact_snapshot",
        "hint",
        "json",
        "math",
        "read_fit_csv",
        "read_fit_max_rows",
        "setup_output",
        "side_file_default",
        "strict_csv",
        "success",
        "typer",
        "warn",
        "write_local_target",
    }
)


def _fit_package() -> object:
    return importlib.import_module("decoy.cli.fit")


def test_fit_wildcard_import_yields_the_names_of_the_old_module() -> None:
    namespace: dict[str, object] = {}
    exec("from decoy.cli.fit import *", namespace)
    assert {n for n in namespace if not n.startswith("_") and n != "__builtins__"} == (
        _FIT_BASE_NAMES
    )


@pytest.mark.parametrize("name", sorted(_FIT_BASE_NAMES))
def test_fit_named_import_still_works(name: str) -> None:
    assert hasattr(_fit_package(), name)


def test_fit_package_defines_no_all() -> None:
    assert not hasattr(_fit_package(), "__all__")


def test_fit_command_names_are_the_objects_the_command_module_defines() -> None:
    package = _fit_package()
    command = importlib.import_module("decoy.cli.fit._command")
    for name in ("fit", "FIT_EPILOG"):
        assert getattr(package, name) is getattr(command, name)
    main = importlib.import_module("decoy.__main__")
    assert main.fit_command is command.fit  # type: ignore[attr-defined]


def test_fit_private_names_are_not_reexported() -> None:
    package = _fit_package()
    # A re-exported private name invites a patch on the package that the moved code never reads.
    assert not hasattr(package, "_FitUsageError")
    assert not hasattr(package, "_build_typed_frame")
