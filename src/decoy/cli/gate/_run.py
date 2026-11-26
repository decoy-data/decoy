"""Run policy beside the gate: turn a `GateResult` into what `decoy run` needs.

`check_before_run` is the one place `decoy run` consults the gate. It returns the validated
config dict or raises `PreRunCheckError`, which `run`'s single error handler maps to an exit
code and a `--json` envelope. Messages here are the gate's own (names and locations, never
data values); this module only caps their length for the run envelope.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from decoy.cli.exit_codes import EXIT_CAPACITY
from decoy.cli.gate._layers import (
    GateFinding,
    GateResult,
    GateRoute,
    finding_message,
    gate_exit_code,
    run_gate_on_config,
    run_static_gate,
)

if TYPE_CHECKING:
    from decoy.cli.io import OutputPlacement

# `decoy run` caps every error text it emits (CLI QA F8): an engine exception can quote
# source-row content verbatim, so the cap bounds what reaches a log aggregator.
ERROR_TEXT_CAP = 500


def capacity_codes() -> frozenset[str]:
    """The engine's capacity-refusal codes, from its one public registry.

    Imported on call so the engine stays off the `--help` path.
    """
    from decoy_engine.errors import CAPACITY_REASON_CODES

    return CAPACITY_REASON_CODES


def cap_error_text(text: str) -> str:
    """Cut `text` to `ERROR_TEXT_CAP` characters plus `...`."""
    return text[:ERROR_TEXT_CAP] + "..." if len(text) > ERROR_TEXT_CAP else text


class PreRunCheckError(Exception):
    """The gate refused the run. Carries the exit code and the members `--json` adds.

    Build it with `from_result`; raise it outside any `except` block so it has no cause
    or context to leak.
    """

    def __init__(
        self,
        summary: str,
        *,
        exit_code: int,
        error_kind: str,
        code: str | None,
        extra: str | None,
        messages: list[dict[str, Any]],
    ) -> None:
        super().__init__(summary)
        self.exit_code = exit_code
        self.error_kind = error_kind
        self.code = code
        self.extra = extra
        self.messages = messages

    @classmethod
    def from_findings(cls, findings: list[GateFinding]) -> PreRunCheckError:
        """A refusal from config-layer findings alone (a YAML syntax error saved at parse)."""
        return cls.from_result(GateResult(findings, frozenset({"config"}), False))

    @classmethod
    def from_result(cls, result: GateResult) -> PreRunCheckError:
        """The one run-envelope error builder for a refused `GateResult`."""
        errors = [f for f in result.findings if f.severity == "error"]
        exit_code = gate_exit_code(result, fail_on_warning=False)
        code: str | None = None
        extra: str | None = None
        error_kind = "validation"
        first = errors[0]
        if exit_code == EXIT_CAPACITY:
            error_kind = "capacity"
            capacity = next((f for f in errors if f.code in capacity_codes()), None)
            if capacity is not None:
                code, first = capacity.code, capacity
        else:
            extra = next((f.extra for f in errors if f.extra is not None), None)
            if extra is not None:
                error_kind = "missing_extra"
        where = f" (at {first.location})" if first.location else ""
        if first.layer == "preflight" and first.code.startswith("source_file."):
            # The engine's own refusal text, "code: reason", as `decoy run` printed it before
            # the gate carried this check; the findings still hold every error.
            return cls(
                first.message,
                exit_code=exit_code,
                error_kind=error_kind,
                code=first.code,
                extra=extra,
                messages=[_message(f) for f in result.findings],
            )
        summary = (
            f"{len(errors)} error(s) found before the run; first: "
            f"{cap_error_text(first.message)}{where}. "
            "Run `decoy validate CONFIG` for the full report."
        )
        return cls(
            summary,
            exit_code=exit_code,
            error_kind=error_kind,
            code=code,
            extra=extra,
            messages=[_message(f) for f in result.findings],
        )

    def context_members(self) -> dict[str, Any]:
        """The members a refusal adds to a command's `--json` error object, beside the code.

        The code is not among them: `emit_error` owns it as a fixed member, and a caller passes
        `self.code` as `code=`.
        """
        members: dict[str, Any] = {"error_kind": self.error_kind}
        if self.extra is not None:
            members["extra"] = self.extra
        members["messages"] = self.messages
        return members


def _message(f: GateFinding) -> dict[str, Any]:
    """One `messages[]` entry: the shared `finding_message` shape, message capped."""
    return {**finding_message(f), "message": cap_error_text(f.message)}


def check_before_run(
    raw: Any,
    config_path: Path,
    route: GateRoute,
    state: Any,
    placement: OutputPlacement | None = None,
    *,
    skip_subset: bool = False,
) -> dict[str, Any]:
    """Run the gate on the parsed YAML; return the validated config or raise.

    Warnings never stop a run. In human mode one stderr line gives their count and the
    command that lists them; `--quiet` and `--json` print nothing extra. `skip_subset` is
    `--no-subset`: the capacity estimate then prices the full sources.
    """
    result = run_gate_on_config(raw, config_path, route, placement, skip_subset=skip_subset)
    if gate_exit_code(result, fail_on_warning=False) != 0:
        raise PreRunCheckError.from_result(result)
    warnings = sum(1 for f in result.findings if f.severity == "warning")
    if warnings and _is_human(state):
        from decoy.ui.theme import warn

        state.err_console.print(
            warn("warning:"),
            f"{warnings} pre-run warning(s); run `decoy validate CONFIG` to list them.",
            markup=False,
        )
    if result.config is None:  # a passing gate always carries its config; kept under -O
        raise RuntimeError("pre-run gate passed without a parsed config")
    return result.config


def check_static_before_acquire(
    raw: Any, config_path: Path, placement: OutputPlacement | None = None
) -> dict[str, Any]:
    """Refuse a config the config and compile layers reject, before any source is acquired.

    Raises `PreRunCheckError` exactly as `check_before_run` does for those layers and returns the
    validated config otherwise. Preflight (source readiness, capacity) is source-dependent and
    stays with `check_before_run`."""
    static = run_static_gate(raw, config_path, placement)
    result = GateResult(
        static.config_findings + static.compile_findings,
        static.layers,
        False,
        static.checks_run,
        static.config,
    )
    if gate_exit_code(result, fail_on_warning=False) != 0:
        raise PreRunCheckError.from_result(result)
    if static.config is None:  # a passing static gate carries its config; kept under -O
        raise RuntimeError("static gate passed without a parsed config")
    return static.config


def _is_human(state: Any) -> bool:
    from decoy.ui.output import OutputMode

    return state.mode is OutputMode.default
