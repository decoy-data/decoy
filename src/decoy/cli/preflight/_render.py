"""Rendering of a preflight result: card, --json payload and warnings."""

from __future__ import annotations

from typing import Any

from rich.text import Text

from decoy.cli.preflight._result import CAPACITY_CHECK, _PreflightAccumulator
from decoy.ui.output import OutputMode, emit_json
from decoy.ui.theme import code, error, hint, success, warn


def _emit_preflight_result(
    state: Any,
    acc: _PreflightAccumulator,
    config_str: str,
    fail_on_warning: bool,
) -> None:
    """Render the accumulated preflight result."""
    capacity_checks = [c for c in acc.checks if c.name == CAPACITY_CHECK]
    native_checks = [c for c in acc.checks if c.name in ("native.companion", "native.eligibility")]

    if state.mode is OutputMode.json:
        status = "ok" if not acc.has_failures else "fail"
        if status == "ok" and fail_on_warning and acc.has_warnings:
            status = "warn"
        payload: dict[str, Any] = {
            "command": "validate preflight",
            "status": status,
            "config": config_str,
            "checks": acc.to_dicts(),
            "fail_count": sum(1 for c in acc.checks if c.status == "fail"),
            "warn_count": sum(1 for c in acc.checks if c.status == "warn"),
            "pass_count": sum(1 for c in acc.checks if c.status == "pass"),
        }
        # A structured top-level `capacity` block, in addition to its entry
        # in `checks` -- R9: assertable without parsing display text.
        if capacity_checks:
            cap = capacity_checks[0]
            payload["capacity"] = {
                "status": cap.status,
                "message": cap.message,
                "code": cap.code,
            }
        # Same structured-block treatment as `capacity` (R9): a --json
        # caller asserts on `native.companion` / `native.eligibility`
        # directly instead of parsing `checks` by name.
        for chk in native_checks:
            payload[chk.name.replace(".", "_")] = {
                "status": chk.status,
                "message": chk.message,
                "code": chk.code,
            }
        emit_json(state, payload)
        return

    if state.mode is OutputMode.quiet:
        return

    # Human-readable: print warnings then failures, then overall result.
    for chk in acc.checks:
        if chk.name in (CAPACITY_CHECK, "native.companion", "native.eligibility"):
            continue  # rendered separately below, at every status (not just warn/fail)
        # markup=False on every message print in this function: a check
        # message is not authored markup. It can carry an install hint like
        # `pip install decoy-cli[ner]` (Rich would parse `[ner]` as an
        # unknown tag and drop it), a user path, or engine text relayed
        # verbatim. The styled labels are Text objects and keep their style.
        if chk.status == "warn":
            loc_hint = f" ({chk.location})" if chk.location else ""
            state.err_console.print(warn("warning:"), chk.message + loc_hint, markup=False)
        elif chk.status == "fail":
            loc_hint = f" ({chk.location})" if chk.location else ""
            state.err_console.print(error("fail:"), chk.message + loc_hint, markup=False)

    # The capacity line always prints, regardless of pass/warn/fail: OK, not
    # checked, and not applicable are all informative outcomes an operator
    # should see, not just the failure case.
    for cap in capacity_checks:
        if cap.status == "fail":
            label = error("capacity:")
        elif cap.status == "warn":
            label = warn("capacity:")
        else:
            label = hint("capacity:")
        state.err_console.print(label, cap.message, markup=False)

    # Same always-print treatment for the native companion + eligibility
    # lines: both are informative even at "pass" (companion absent, or
    # config not eligible, are normal outcomes an operator should still see).
    # Text(): the message can carry an untrusted `abi_actual` value (see
    # sanitize_abi) that Rich's default string markup would otherwise
    # reinterpret.
    for nat in native_checks:
        if nat.status == "warn":
            label = warn("native:")
        else:
            label = hint("native:")
        state.err_console.print(label, Text(nat.message))

    if acc.has_failures:
        state.err_console.print(
            error("FAIL"),
            code(config_str),
            hint("- fix the errors above, then rerun."),
        )
        return

    state.console.print(success("OK"), code(config_str))

    if acc.has_warnings and fail_on_warning:
        state.err_console.print(
            warn("warning:"),
            "warnings present and --fail-on-warning is set.",
        )
