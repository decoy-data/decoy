"""The one builder of the run result document of a `decoy run` (RESULT C-DOC1).

The run's facts live on `RunContext`: the engine's `ExecutionResult`, the progress collector, the
publication ledger and the config. This module turns them into the document, and into the exit
integer the document carries, in one place. `_errors` and `_render` call it with the category and
the reason; neither builds a document, a delivery fact or a status of its own.

A build that raises is a defect in the document, never in the run: the run keeps its exit code
(read from the same `RUN_EXIT_MAP` through the engine's `derive_outcome`), the `--json` envelope
loses its `result` member and `result_status` says why. Only value-free facts go in: table names
pass the engine's name check, outputs are run-relative, no message and no path of the caller.

Named limit: a `--chunked` run emits no progress events, so its tables carry no row counts.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from decoy._version import __version__ as _cli_version
from decoy.cli import exit_codes
from decoy.cli.exit_codes import run_exit_code
from decoy.cli.run._context import RunContext
from decoy.ui.output import OutputMode
from decoy.ui.theme import warn

_FORMATS = ("csv", "parquet", "fixed_width")
_BUILT = {"document": "built", "file": "not_requested", "code": None}
_FAILED = {"document": "failed", "file": "not_requested", "code": "run_result_build_failed"}


@dataclass(frozen=True)
class Document:
    """What the builder hands back: the `result` payload (None when the build failed), the
    `result_status` member and the run's exit integer."""

    payload: dict | None
    status: dict
    exit_code: int


def collect(ctx: RunContext) -> Callable[[Any], None]:
    """Start the run's collector and return the consumer to put on the progress sink."""
    from decoy_engine.run_result import RunResultCollector

    ctx._collector = RunResultCollector()
    return ctx._collector.on_event


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _output(ctx: RunContext, path: Path) -> str | None:
    """The file as the run folder (or `--out-dir`) names it, else its file name."""
    resolved = Path(path).resolve()
    folder = ctx.layout.output_dir() if ctx.layout is not None else None
    if folder is not None and folder in resolved.parents:
        return resolved.relative_to(folder).as_posix()
    return resolved.name


def _entry(ctx: RunContext, name: str, targets: dict) -> Any:
    from decoy_engine.run_result import TableDelivery

    published = ctx._published.get(name)
    if published is None:
        return TableDelivery(
            state="none", format=None, output=None, reason=None, dropped_because=None
        )
    spec = targets.get(name)
    fmt = spec.get("format") if isinstance(spec, dict) else None
    fmt = fmt if fmt in _FORMATS else None
    try:
        return TableDelivery(
            state="delivered",
            format=fmt,
            output=_output(ctx, published),
            reason=None,
            dropped_because=None,
        )
    except ValueError:
        # An output name the document may not carry: delivered, with no file shown.
        return TableDelivery(
            state="delivered", format=fmt, output=None, reason=None, dropped_because=None
        )


def delivery_facts(ctx: RunContext, config: dict, *, vault_failed: bool) -> Any:
    """The one provider of delivery facts. Before DELIV a table is delivered when the publication
    ledger holds its file, and not otherwise; a preview and a config with no target say nothing."""
    from decoy_engine.config import classify_table_kinds
    from decoy_engine.run_result import DeliveryFacts

    targets = config.get("targets")
    targets = targets if isinstance(targets, dict) else {}
    declared = classify_table_kinds(config)
    names = [name for name in targets if name in declared]
    if ctx.rows is not None or not names:
        return DeliveryFacts.not_applicable()
    writer = getattr(ctx, "vault_writer", None)
    if writer is None:
        vault = "not_used"
    elif vault_failed:
        vault = "failed"
    else:
        vault = "committed" if Path(ctx.vault).exists() else "not_used"
    return DeliveryFacts(
        "in_place",
        vault,
        {name: _entry(ctx, name, targets) for name in names},  # type: ignore[arg-type]
    )


def _config(ctx: RunContext) -> dict:
    config = getattr(ctx, "config_dict", None)
    if isinstance(config, dict):
        return config
    return ctx.raw_cfg if ctx.raw_cfg is not None else {}


def _config_ref(ctx: RunContext, config: dict) -> Any:
    from decoy_engine import pipeline_config_hash
    from decoy_engine.reasons import approve_name
    from decoy_engine.run_result import ConfigRef

    from decoy.cli.evidence import hash_file

    def attempt(read: Callable[[], Any]) -> Any:
        try:
            return read()
        except Exception:
            return None

    return ConfigRef(
        name=approve_name(ctx.config.name),
        file_sha256=attempt(lambda: hash_file(ctx.config)),
        semantic_hash=attempt(lambda: pipeline_config_hash(config)),
    )


def _native(ctx: RunContext) -> Any:
    from decoy_engine.run_result import NativeRoute

    route = ctx._native_route
    if route is None:
        return None
    state = route.state if route.state in ("pandas", "native", "unified_slice") else None
    return NativeRoute(applicable=route.applicable, state=state)


def _build(
    ctx: RunContext,
    category: str | None,
    reason: Any,
    error_class: str | None,
    blocking_failed: bool,
    vault_failed: bool,
) -> tuple[dict, int]:
    from decoy_engine import route_summary
    from decoy_engine.run_result import (
        FailureInput,
        Links,
        build_run_result,
        project_tables,
    )

    config = _config(ctx)
    failed = category is not None
    facts = None if ctx._collector is None else ctx._collector.snapshot()
    execution = ctx._execution
    delivery = delivery_facts(ctx, config, vault_failed=vault_failed)
    tables = project_tables(
        config=config,
        execution_result=execution,
        facts=facts,
        delivery=delivery,
        run_failed=failed,
    )
    now = datetime.now(timezone.utc)
    elapsed = getattr(ctx, "elapsed", None)
    elapsed = time.perf_counter() - ctx.started if elapsed is None else elapsed
    document = build_run_result(
        tables=tables,
        execution_result=execution,
        failure=FailureInput(category, reason, error_class) if failed else None,  # type: ignore[arg-type]
        config_ref=_config_ref(ctx, config),
        producer=_cli_version,
        invocation_id=ctx.invocation_id,
        exit_map=exit_codes.RUN_EXIT_MAP,
        blocking_failed=blocking_failed,
        native=_native(ctx),
        chunked=ctx.chunked,
        route=None if execution is None else route_summary(execution.quality_metrics),
        links=Links(log=None, evidence=None, baseline=None),
        started_at=_stamp(ctx._run_started_at),
        finished_at=_stamp(now),
        elapsed_s=max(0.0, float(elapsed)),
        phases=() if facts is None else facts.phases,
    )
    return document.to_payload(), document.exit_code


def build(
    ctx: RunContext,
    *,
    category: str | None = None,
    reason: Any = None,
    error_class: str | None = None,
    blocking_failed: bool = False,
    vault_failed: bool = False,
) -> Document:
    """The document of this run and its exit integer. `reason` is the engine's `ReasonRecord`.

    Never raises for a document defect: the exit then comes straight from `derive_outcome` with
    the same inputs, and the one stderr line names the exception class and the code only.
    """
    try:
        payload, code = _build(ctx, category, reason, error_class, blocking_failed, vault_failed)
    except Exception as exc:
        if ctx.state.mode is not OutputMode.quiet:
            ctx.state.err_console.print(
                warn("warning:"), f"run_result_build_failed ({type(exc).__name__})", markup=False
            )
        return Document(
            None, dict(_FAILED), run_exit_code(category, blocking_failed=blocking_failed)
        )
    return Document(payload, dict(_BUILT), code)


def members(document: Document) -> dict:
    """The `--json` members the document adds to an envelope: `result` (when built) and
    `result_status`."""
    added: dict = {} if document.payload is None else {"result": document.payload}
    added["result_status"] = document.status
    return added
