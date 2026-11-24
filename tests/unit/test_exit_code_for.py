"""`exit_code_for`: the one exception-to-exit map, and its parity with the three older copies.

AT-CL3-7. Until CL4 the `decoy run` classifier (`cli/run/_errors.py`), `decoy demo`'s three-type
map and `decoy fit`'s differential-privacy arms still decide for themselves. This file runs the
same exception through each and through `exit_code_for`, so the owner cannot drift from them
before they are deleted. The categories come from the run classifier's own type list, so a type
added there without a matching rule here fails the parity test.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from decoy import _native_gate
from decoy._config_file import ConfigFileError
from decoy.cli import exit_codes
from decoy.cli.exit_codes import (
    EXIT_CAPACITY,
    EXIT_RUNTIME,
    EXIT_USAGE,
    exit_code_for,
)
from decoy.cli.gate import PreRunCheckError, capacity_codes
from decoy.cli.run import _errors
from decoy.ui.output import setup_output


def _classifier_exit(exc: Exception) -> int:
    """The exit the `decoy run` error arm gives `exc`, through its real `fail`."""
    ctx = SimpleNamespace(
        state=setup_output(False, True, False),  # quiet: the arm prints one stderr line
        notify_channels=[],
        notify_on=SimpleNamespace(value="failure"),
        config_str="pipeline.yaml",
        yaml_mode="mask",
        rows=None,
        no_library=True,
        layout=None,
        result=None,
        _run_started_at=datetime.now(timezone.utc),
    )
    with pytest.raises(typer.Exit) as info:
        _errors.fail(ctx, exc)  # type: ignore[arg-type]
    return info.value.exit_code


def _bare(cls: type[BaseException]) -> BaseException:
    """An instance built without its constructor: only the type matters for the exit.

    The run classifier reads `.code` and `.message` for a few types, so a stand-in is set on each."""
    exc = cls.__new__(cls)
    for name in ("code", "message"):
        if not hasattr(exc, name):
            setattr(exc, name, "stand_in")
    return exc


def _pre_run(exit_code: int) -> PreRunCheckError:
    kind = "capacity" if exit_code == EXIT_CAPACITY else "validation"
    return PreRunCheckError(
        "refused", exit_code=exit_code, error_kind=kind, code=None, extra=None, messages=[]
    )


def _run_categories() -> dict[str, Any]:
    from decoy_engine import GenerationError
    from decoy_engine.errors import DecoyError
    from decoy_engine.execution import ExecutionError

    capacity = sorted(capacity_codes())[0]
    cases: dict[str, Any] = {
        "pre-run usage": _pre_run(EXIT_USAGE),
        "pre-run capacity": _pre_run(EXIT_CAPACITY),
        "execution capacity code": ExecutionError(code=capacity, message="x"),
        "engine capacity code": DecoyError.__new__(DecoyError),
        "memory error": MemoryError(),
        "uniqueness impossible": GenerationError(
            code=_errors.UNIQUENESS_IMPOSSIBLE_CODE, message="x"
        ),
        "other generation error": GenerationError(code="dtype_unsafe", message="x"),
        "native gate": _bare(_native_gate.NativeGateError),
        "runtime error": RuntimeError("boom"),
        "os error": OSError("disk"),
        "value error": ValueError("bad"),
    }
    cases["engine capacity code"].code = capacity
    for t in exit_codes.usage_error_types():
        cases[f"usage type {t.__name__}"] = _bare(t)
    return cases


# AT-1: the exit and category the old `decoy run` classifier gave each case on main before CL4,
# typed out as literals (recorded at base `00ed97b2`). Nothing here is computed from `exit_code_for`.
_BASE_TABLE: dict[str, tuple[str, int]] = {
    "engine capacity code": ("capacity", 5),
    "execution capacity code": ("capacity", 5),
    "memory error": ("capacity", 5),
    "native gate": ("usage", 1),
    "os error": ("runtime", 3),
    "other generation error": ("runtime", 3),
    "pre-run capacity": ("capacity", 5),
    "pre-run usage": ("usage", 1),
    "runtime error": ("runtime", 3),
    "uniqueness impossible": ("usage", 1),
    "value error": ("runtime", 3),
    "usage type ConfigError": ("usage", 1),
    "usage type DuckDBSourceError": ("usage", 1),
    "usage type LayoutError": ("usage", 1),
    "usage type MaskSecretError": ("usage", 1),
    "usage type MissingExtraError": ("usage", 1),
    "usage type ModelUnavailableError": ("usage", 1),
    "usage type NativeGateError": ("usage", 1),
    "usage type NerUnavailableError": ("usage", 1),
    "usage type OutDirUsageError": ("usage", 1),
    "usage type PipelineValidationError": ("usage", 1),
    "usage type PlanCompileError": ("usage", 1),
    "usage type PostScanRouteError": ("usage", 1),
    "usage type ResourceError": ("usage", 1),
    "usage type TargetFormatError": ("usage", 1),
    "usage type UnsupportedCloudEndpointError": ("usage", 1),
    "usage type UsageRefusal": ("usage", 1),
    "usage type _ChunkedFixedWidthError": ("usage", 1),
    "usage type _ChunkedGenerateError": ("usage", 1),
    "usage type _ChunkedIntegrityError": ("usage", 1),
    "usage type _ChunkedQuarantineError": ("usage", 1),
    "usage type _ChunkedReportFlagError": ("usage", 1),
    "usage type _ChunkedVaultError": ("usage", 1),
    "usage type _MaskSecretUsageError": ("usage", 1),
    "usage type _OtelSettingsUsageError": ("usage", 1),
    "usage type _VaultUsageError": ("usage", 1),
}


@pytest.mark.parametrize("name", sorted(_BASE_TABLE))
def test_exit_code_for_equals_the_recorded_base_table(name: str) -> None:
    assert name in _run_categories()
    assert exit_code_for(_run_categories()[name]) == _BASE_TABLE[name][1]


def test_the_base_table_covers_every_case() -> None:
    assert sorted(_BASE_TABLE) == sorted(_run_categories())


@pytest.mark.parametrize("name", sorted(_run_categories()))
def test_every_run_category_matches_the_classifier(name: str) -> None:
    exc = _run_categories()[name]

    assert exit_code_for(exc) == _classifier_exit(exc)


def test_the_documented_exits() -> None:
    assert exit_code_for(ConfigFileError("yaml.empty", "x")) == EXIT_USAGE
    assert exit_code_for(MemoryError()) == EXIT_CAPACITY
    assert exit_code_for(OSError("read failed")) == EXIT_RUNTIME
    assert exit_code_for(RuntimeError("x")) == EXIT_RUNTIME


def test_an_engine_env_flag_error_is_a_usage_exit() -> None:
    # The class ships with the engine's env-flag slice; the pinned engine may predate it.
    errors = pytest.importorskip("decoy_engine.errors")
    cls = getattr(errors, "EnvFlagError", None)
    if cls is None:
        pytest.skip("the pinned engine has no EnvFlagError yet")

    assert exit_code_for(cls.__new__(cls)) == EXIT_USAGE


def test_the_demo_map_is_the_owner_map() -> None:
    from decoy_engine import ConfigError, PipelineValidationError
    from decoy_engine.plan import PlanCompileError

    for exc in (
        PlanCompileError("c", None, "m"),
        PipelineValidationError("m"),
        ConfigError("m"),
    ):
        assert exit_code_for(exc) == EXIT_USAGE
    assert exit_code_for(RuntimeError("m")) == EXIT_RUNTIME


@pytest.mark.parametrize(
    ("module", "name", "code", "expected"),
    [
        ("dp_provenance", "ProvenanceError", "dp_provenance_refused", EXIT_RUNTIME),
        ("dp_budget", "DpBudgetError", "dp_schedule_mismatch", EXIT_RUNTIME),
        ("dp_budget", "DpBudgetError", "dp_budget_exceeded", EXIT_USAGE),
        ("dp", "DpError", "dp_bad_request", EXIT_USAGE),
        ("carriers", "CarrierError", "carrier_bad", EXIT_USAGE),
    ],
)
def test_the_fit_dp_arms_are_the_owner_map(
    module: str, name: str, code: str, expected: int
) -> None:
    import importlib

    cls = getattr(importlib.import_module(f"decoy_engine.quality.{module}"), name)

    assert exit_code_for(cls(code=code, message="m")) == expected


def test_a_blocking_post_scan_is_findings_and_an_existing_vault_is_usage() -> None:
    """Every command agrees with `decoy run`'s repin cases (engine 0.24.0 behaviour)."""
    from decoy_engine import VaultError
    from decoy_engine.verification.postmask import PostScanBlockedError

    from decoy.cli.exit_codes import EXIT_FINDINGS

    assert exit_code_for(PostScanBlockedError({})) == EXIT_FINDINGS
    assert exit_code_for(VaultError(code="vault_exists", message="m")) == EXIT_USAGE
    assert exit_code_for(VaultError(code="vault_other", message="m")) == EXIT_RUNTIME


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("vault_tampered", EXIT_RUNTIME),
        ("vault_key_mismatch", EXIT_USAGE),
        ("vault_crypto_not_installed", EXIT_USAGE),
        ("vault_unreadable", EXIT_USAGE),
        ("vault_format_unsupported", EXIT_USAGE),
        ("vault_protocol_version_mismatch", EXIT_USAGE),
    ],
)
def test_a_vault_that_fails_authentication_is_runtime_and_a_wrong_input_is_usage(
    code: str, expected: int
) -> None:
    """F09: a damaged vault is exit 3; the wrong secret, file or format is the caller's (exit 1).

    `decoy unmask` meets the engine's vault failure re-raised as an `ExecutionError` with the same
    code, so the tampered match holds for that type too."""
    from decoy_engine import VaultError
    from decoy_engine.execution import ExecutionError

    assert exit_code_for(VaultError(code=code, message="m")) == expected
    if code == "vault_tampered":
        assert exit_code_for(ExecutionError(code=code, message="m")) == EXIT_RUNTIME


# AT-1: the category of every base case, from the recorded literal table.
@pytest.mark.parametrize("name", sorted(_BASE_TABLE))
def test_run_category_for_equals_the_recorded_base_table(name: str) -> None:
    from decoy.cli.exit_codes import run_category_for

    assert run_category_for(_run_categories()[name]) == _BASE_TABLE[name][0]


# AT-1 + 7.2: the exits CL4 changes on purpose. Each row names the 7.2 line that allows it.
def test_a_config_file_error_is_usage_for_run_too() -> None:
    # 7.2 "decoy run exits that change": ConfigFileError 3 to 1.
    from decoy.cli.exit_codes import run_category_for

    exc = ConfigFileError("yaml.empty", "x")
    assert run_category_for(exc) == "usage"
    assert _classifier_exit(exc) == EXIT_USAGE


@pytest.mark.parametrize(
    ("module", "name", "code"),
    [
        ("dp_provenance", "ProvenanceError", "dp_provenance_refused"),
        ("dp_budget", "DpBudgetError", "dp_schedule_mismatch"),
    ],
)
def test_the_fit_runtime_dp_arms_stay_runtime_in_run(module: str, name: str, code: str) -> None:
    import importlib

    from decoy.cli.exit_codes import run_category_for

    cls = getattr(importlib.import_module(f"decoy_engine.quality.{module}"), name)
    assert run_category_for(cls(code=code, message="m")) == "runtime"


def test_a_dp_request_error_is_usage_in_run() -> None:
    # 7.2: DpError, CarrierError and a non-schedule DpBudgetError 3 to 1.
    from decoy_engine.quality.dp import DpError

    from decoy.cli.exit_codes import run_category_for

    assert _classifier_exit(DpError(code="dp_bad_request", message="m")) == EXIT_USAGE
    assert run_category_for(DpError(code="dp_bad_request", message="m")) == "usage"


def test_a_post_scan_block_has_no_run_category() -> None:
    from decoy_engine.verification.postmask import PostScanBlockedError

    from decoy.cli.exit_codes import run_category_for

    assert run_category_for(PostScanBlockedError({})) is None


# AT-4
def test_run_category_for_refuses_an_exit_with_no_row(monkeypatch: pytest.MonkeyPatch) -> None:
    from decoy.cli.exit_codes import run_category_for

    monkeypatch.setattr(exit_codes, "exit_code_for", lambda exc: 7)

    with pytest.raises(RuntimeError):
        run_category_for(RuntimeError("x"))


def test_fit_source_error_is_a_usage_type() -> None:
    from decoy.cli.gen._fit import FitSourceError

    assert FitSourceError in exit_codes.usage_error_types()
    assert exit_code_for(FitSourceError("bad", code="fit_x")) == EXIT_USAGE
