"""The import surface the CLI-SPLIT packages keep (S2: `decoy.cli.preflight`)."""

from __future__ import annotations

import importlib

import pytest

import decoy.cli.preflight as package
from decoy.cli import validate
from decoy.cli.preflight import _command, _result, readiness

PUBLIC = ("CAPACITY_CHECK", "PLAN_UNCOMPILABLE_CHECK", "PREFLIGHT_EPILOG", "preflight")
OWNERS = {
    "CAPACITY_CHECK": _result,
    "PLAN_UNCOMPILABLE_CHECK": _result,
    "PREFLIGHT_EPILOG": _command,
    "preflight": _command,
}
# Every non-underscore name the single module bound at `origin/main`, imported names included
# (`{n for n in vars(module) if not n.startswith("_")}`), frozen from the plan.
FROZEN = frozenset(
    {
        "CAPACITY_CHECK",
        "ConfigFileError",
        "EXIT_CAPACITY",
        "EXIT_USAGE",
        "EXIT_WARNINGS",
        "OutputMode",
        "PLAN_UNCOMPILABLE_CHECK",
        "PREFLIGHT_EPILOG",
        "Path",
        "Any",
        "Text",
        "annotations",
        "capacity_codes",
        "code",
        "config_refusal",
        "dataclass",
        "emit_json",
        "error",
        "exit_code_for",
        "field",
        "hint",
        "load_config_mapping",
        "pipeline_argument",
        "preflight",
        "resolve_pipeline",
        "setup_output",
        "success",
        "typer",
        "warn",
    }
)
# Imported names and the module the old file took each from.
IMPORTED_FROM = {
    "Path": ("pathlib", "Path"),
    "Any": ("typing", "Any"),
    "typer": ("typer", None),
    "Text": ("rich.text", "Text"),
    "dataclass": ("dataclasses", "dataclass"),
    "field": ("dataclasses", "field"),
    "ConfigFileError": ("decoy._config_file", "ConfigFileError"),
    "config_refusal": ("decoy._config_file", "config_refusal"),
    "load_config_mapping": ("decoy._config_file", "load_config_mapping"),
    "EXIT_CAPACITY": ("decoy.cli.exit_codes", "EXIT_CAPACITY"),
    "EXIT_USAGE": ("decoy.cli.exit_codes", "EXIT_USAGE"),
    "EXIT_WARNINGS": ("decoy.cli.exit_codes", "EXIT_WARNINGS"),
    "exit_code_for": ("decoy.cli.exit_codes", "exit_code_for"),
    "capacity_codes": ("decoy.cli.gate", "capacity_codes"),
    "pipeline_argument": ("decoy.cli.io", "pipeline_argument"),
    "resolve_pipeline": ("decoy.cli.io", "resolve_pipeline"),
    "OutputMode": ("decoy.ui.output", "OutputMode"),
    "emit_json": ("decoy.ui.output", "emit_json"),
    "setup_output": ("decoy.ui.output", "setup_output"),
    "code": ("decoy.ui.theme", "code"),
    "error": ("decoy.ui.theme", "error"),
    "hint": ("decoy.ui.theme", "hint"),
    "success": ("decoy.ui.theme", "success"),
    "warn": ("decoy.ui.theme", "warn"),
}


def test_all_is_exactly_the_frozen_names() -> None:
    assert sorted(package.__all__) == sorted(FROZEN)


def test_package_names_are_the_frozen_names_plus_readiness() -> None:
    names = {n for n in vars(package) if not n.startswith("_")}
    assert names == FROZEN | {"readiness"}


@pytest.mark.parametrize("name", sorted(IMPORTED_FROM))
def test_each_imported_name_is_the_object_at_its_original_source(name: str) -> None:
    module, attr = IMPORTED_FROM[name]
    source = importlib.import_module(module)
    assert getattr(package, name) is (source if attr is None else getattr(source, attr))


@pytest.mark.parametrize("name", PUBLIC)
def test_each_public_name_is_the_object_its_owner_defines(name: str) -> None:
    assert getattr(package, name) is getattr(OWNERS[name], name)


def test_validate_uses_the_same_command_object() -> None:
    assert validate._preflight_command is _command.preflight


def test_private_names_are_not_bound_on_the_package() -> None:
    # A patch on the package would do nothing: the moved code reads `readiness`.
    for name in (
        "_check_capacity",
        "_check_native",
        "_check_source_files",
        "_PreflightAccumulator",
    ):
        assert not hasattr(package, name), name


def test_wildcard_import_binds_exactly_the_frozen_names() -> None:
    scope: dict[str, object] = {}
    exec("from decoy.cli.preflight import *", scope)
    assert {n for n in scope if not n.startswith("__")} == FROZEN


def test_readiness_binds_the_defining_objects() -> None:
    from decoy.cli.preflight import _capacity, _checks

    assert readiness._check_capacity is _capacity._check_capacity
    assert readiness._check_native is _checks._check_native
    assert readiness._check_source_files is _checks._check_source_files
    assert readiness._check_target_overwrite is _checks._check_target_overwrite
    assert readiness._PreflightAccumulator is _result._PreflightAccumulator


def test_result_module_imports_alone() -> None:
    importlib.import_module("decoy.cli.preflight._result")
