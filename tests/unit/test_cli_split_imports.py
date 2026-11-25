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
# Public-looking names the single module held only because it imported them. The old module
# had no `__all__`, so `import *` leaked them; nothing in the repo reads them from here.
INCIDENTAL_BASE_NAMES = frozenset(
    {
        "Any",
        "ConfigFileError",
        "EXIT_CAPACITY",
        "EXIT_USAGE",
        "EXIT_WARNINGS",
        "OutputMode",
        "Path",
        "Text",
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
        "resolve_pipeline",
        "setup_output",
        "success",
        "typer",
        "warn",
    }
)
BASE_WILDCARD = frozenset(PUBLIC) | INCIDENTAL_BASE_NAMES


def test_all_is_exactly_the_public_names() -> None:
    assert sorted(package.__all__) == sorted(PUBLIC)


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


def test_wildcard_import_keeps_the_public_names_and_drops_only_incidental_ones() -> None:
    scope: dict[str, object] = {}
    exec("from decoy.cli.preflight import *", scope)
    got = {n for n in scope if not n.startswith("__")}
    assert got == set(PUBLIC)
    assert BASE_WILDCARD - got == INCIDENTAL_BASE_NAMES


def test_readiness_binds_the_defining_objects() -> None:
    from decoy.cli.preflight import _capacity, _checks

    assert readiness._check_capacity is _capacity._check_capacity
    assert readiness._check_native is _checks._check_native
    assert readiness._check_source_files is _checks._check_source_files
    assert readiness._check_target_overwrite is _checks._check_target_overwrite
    assert readiness._PreflightAccumulator is _result._PreflightAccumulator


def test_result_module_imports_alone() -> None:
    importlib.import_module("decoy.cli.preflight._result")
