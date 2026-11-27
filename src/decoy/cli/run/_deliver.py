"""The delivery step of `decoy run`: open the sink, decide, deliver, and project the receipt.

The sink lives in `cli/io`, which never imports `cli/run`; this module builds the one
`DeliveryHooks` value that carries the run-side work (evidence, warnings) across.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text

from decoy.cli.io import (
    INTEGRITY_WRITE_FAILED,
    DeliveryHooks,
    DeliverySink,
    LayoutWarning,
    SideFileBusy,
    write_run_report,
)
from decoy.cli.run import _evidence
from decoy.cli.run._context import DeliveryRefusal, IntegrityWriteRefusal, RunContext
from decoy.ui.output import OutputMode
from decoy.ui.theme import warn

_BUSY_TEXT = (
    "another run holds the vault or evidence file this run would publish; nothing was delivered."
)
_REPORT_CODE = "post_scan_report_write_failed"
_REPORT_TEXT = "the post-scan report of a run that delivered nothing could not be written."
_CLEANUP_CODE = "delivery_cleanup_incomplete"
_CLEANUP_TEXT = (
    "delivery finished, but cleaning up after it did not: a temporary file may remain beside "
    "the outputs."
)


def _show(ctx: RunContext, item: LayoutWarning) -> None:
    if ctx.state.mode is not OutputMode.quiet:
        ctx.state.err_console.print(warn("warning:"), Text(f"{item.code}: {item.message}"))


def open_sink(ctx: RunContext) -> DeliverySink:
    """Open the sink after the layout exists and before the first write."""
    assert ctx.layout is not None
    hooks = DeliveryHooks(
        write_attempts=lambda staged: _evidence.write_attempts(ctx, staged),
        publish_attempts=lambda: _evidence.publish_attempts(ctx),
        discard_attempts=lambda: _evidence.discard_attempts(ctx),
        show_warning=lambda item: _show(ctx, item),
        integrity_out=ctx.integrity_out,
        side_files=tuple(p for p in (ctx.evidence_out, vault_leaf(ctx)) if p is not None),
    )
    return DeliverySink.open(ctx.layout, ctx.config_dict, hooks, ctx.invocation_id)


def vault_leaf(ctx: RunContext) -> Path | None:
    """The `--vault` file this run publishes, or None when it keeps no vault."""
    return ctx.vault if ctx.vault_writer is not None else None


def blocking_failed(ctx: RunContext) -> bool:
    """Whether the run exits 4: `--post-validate-enforce` with failed checks, or a delivery the
    sink withheld for the post-scan rule. The one place the decision is made."""
    enforced = bool(
        ctx.post_validate_enforce and (ctx._report_quality_metrics or {}).get("failed_checks")
    )
    return enforced or _withheld(ctx)


def _withheld(ctx: RunContext) -> bool:
    sink = ctx._sink
    return sink is not None and sink.mode == "strict" and sink.withheld


def note_cleanup(ctx: RunContext) -> None:
    """Record the one `delivery_cleanup_incomplete` warning, however many steps failed."""
    if not any(w["code"] == _CLEANUP_CODE for w in ctx._cli_warnings):
        ctx.add_cli_warning(_CLEANUP_CODE, _CLEANUP_TEXT)


def _gate_withholds(ctx: RunContext) -> bool:
    """W2: an applicable post-scan with no report, or an enforced failure, delivers nothing."""
    from decoy_engine.config import post_scan_integrity_requested

    missing = post_scan_integrity_requested(ctx.config_dict) and ctx._post_scan is None
    enforced = bool(
        ctx.post_validate_enforce and (ctx._report_quality_metrics or {}).get("failed_checks")
    )
    return missing or enforced


# The target types `plan_delivery` gives a state to (the engine keeps the set private).
_DELIVERABLE_TYPES = frozenset({"file", "s3", "gcs"})


def _deliverable(config: dict) -> dict[str, None]:
    """The tables `plan_delivery` expects an outcome for, each one a success."""
    names = {t["name"] for t in config.get("tables") or []}
    targets = config.get("targets") or {}
    return {
        n: None for n, t in targets.items() if n in names and t.get("type") in _DELIVERABLE_TYPES
    }


def _stage_report(ctx: RunContext, sink: DeliverySink) -> None:
    """The implicit post-scan report: a member of the run folder, or the placed file."""
    if ctx._post_scan is None or ctx._post_scan_file is None:
        return

    def write(path: Path) -> str | None:
        return write_run_report(ctx._post_scan, path, ctx.config_sha256)

    if ctx.integrity_out is not None:
        sink.keep_report(write)  # the attempt file carries it when the run delivers
        return

    failed = sink.stage_report(ctx._post_scan_file, write)
    if failed is not None:
        raise IntegrityWriteRefusal(failed, code=INTEGRITY_WRITE_FAILED)


def deliver(ctx: RunContext) -> None:
    """End of the plain branch: decide, deliver and project what the receipt says."""
    from decoy_engine.delivery import plan_delivery
    from decoy_engine.publication import StageDecision

    sink = ctx._sink
    assert sink is not None
    if sink.mode == "strict":
        _stage_report(ctx, sink)
    plan = plan_delivery(ctx.config_dict, _deliverable(ctx.config_dict))
    sink.decision = plan
    withhold = _gate_withholds(ctx)
    sink.withheld = withhold
    delivered = frozenset(n for n, t in plan.tables.items() if t.state == "delivered")
    written = frozenset(sink.final_paths())
    decision = StageDecision(
        plan.deliver and not withhold, frozenset() if withhold else delivered | written
    )
    busy = False
    try:
        receipt = sink.deliver(decision, ctx._published)
    except SideFileBusy:
        busy = True
    if busy:
        # Raised outside the handler, so the refusal carries no context.
        raise DeliveryRefusal(_BUSY_TEXT, code="delivery_side_file_busy")
    if sink.report_failed:
        ctx.add_cli_warning(_REPORT_CODE, _REPORT_TEXT)
    if sink.cleanup_failed:
        note_cleanup(ctx)
    if sink.mode == "strict":
        # One projection for both renderers: a path only for a confirmed delivery of the table.
        confirmed = receipt.state == "delivered"
        ctx._table_records = [
            {
                **r,
                "path": str(ctx._published[r["name"]])
                if confirmed and r["name"] in ctx._published
                else None,
            }
            for r in ctx._table_records
        ]
    if receipt.state == "nothing" and decision.deliver:
        cause = None if receipt.cause is None else str(receipt.cause)
        raise DeliveryRefusal(
            f"nothing was delivered ({cause or 'no cause reported'}); the previous run stays current.",
            code=cause,
        )
