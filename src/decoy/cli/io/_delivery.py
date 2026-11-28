"""The one place a `decoy run` output reaches its destination: stage, then deliver.

Pattern: Git's commit then ref update. In a project the engine's `DeliveryStage` holds every
table in a stage, binds the run folder and moves `LATEST` with a compare-and-swap, so the run is
current whole or not at all. The CLI adds no publication mechanism: it reserves a member per
table, writes into the reserved slot, completes it, and hands the engine a decision.

Two stages sit behind one `SinkStage` protocol, so the sink never branches on kind after open:
the engine's strict stage (kind R, the project run folder) and `PassThroughStage` (kind A, one
fixed folder, and a project run on a host without the engine's lock). The pass-through calls
today's writers, has no strict guarantee and says so: its `mode` is `in_place`. C2b replaces it
with the journalled batch for kind A.

`cli/io` never imports `cli/run`: the CLI-side work (evidence, warnings) arrives as one
`DeliveryHooks` value of callables.
"""

from __future__ import annotations

import contextlib
import enum
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from decoy.cli.io import _pointer
from decoy.cli.io._layout import RunLayout, quarantine_enabled
from decoy.cli.io._layout_errors import (
    DELIVERY_ROOT_SPLIT,
    LATEST_COMMIT_UNCERTAIN,
    LayoutWarning,
)
from decoy.cli.io._placement import (
    Fixed,
    NoLocalOutput,
    Relative,
    Split,
    delivery_root,
    strict_route,
)
from decoy.cli.io._published import Ledger, LocalOutput
from decoy.cli.io._run_outputs import not_delivered_report_name
from decoy.cli.io._side_lock import SideFile, hold_side_files
from decoy.cli.io._targets import (
    check_target_formats,
    file_targets,
    preflight_csv_targets,
    write_target,
    write_targets,
)

if TYPE_CHECKING:
    from decoy_engine.delivery import DeliveryDecision
    from decoy_engine.publication import (
        DeliveryReceipt,
        DeliveryStage,
        StageDecision,
        StagedMember,
    )


def _nothing() -> None:
    return None


class SideFileBusy(Exception):
    """Another run holds the lock on a vault or evidence file this run would publish.

    Raised before the stage is entered, so nothing is delivered and the caller turns it into
    one fixed refusal. The text carries no path.
    """


class RootKind(enum.Enum):
    """Where a run is delivered: the project run folder, or one fixed folder."""

    run_folder = "run_folder"
    fixed_folder = "fixed_folder"


class SinkStage(Protocol):
    """What the sink needs of a stage; `DeliveryStage` fits `abort` and `deliver` as it is."""

    mode: Literal["strict", "in_place"]

    def abort(self) -> None: ...

    def deliver(
        self,
        decision: StageDecision,
        before_visible: Callable[[], None],
        reconcile: Callable[[DeliveryReceipt], None] | None = None,
    ) -> DeliveryReceipt: ...


@dataclass(frozen=True)
class DeliveryHooks:
    """The CLI-side work the sink calls, injected so `cli/io` stays below `cli/run`.

    Every hook is value-free by construction: it raises a typed refusal or warns with a fixed
    code, and never carries a path or a value.
    """

    write_attempts: Callable[[Callable[[str], Path]], None]  # evidence and `--integrity-out`
    publish_attempts: Callable[[], None]  # attempt files become the live files
    discard_attempts: Callable[[], None]
    show_warning: Callable[[LayoutWarning], None]
    side_files: tuple[SideFile, ...] = ()  # the vault and evidence files other runs may share
    integrity_out: Path | None = None  # an explicit `--integrity-out`


class PreVisible:
    """The work before the visibility point, and its undo.

    `write_attempts` writes the evidence manifest and an explicit `--integrity-out` beside their
    final names, under an attempt name. Nothing live changes until `publish`, which runs only
    after a delivered receipt. `restore` and `discard` remove attempt files only.
    """

    def __init__(self, hooks: DeliveryHooks, staged_file: Callable[[str], Path]) -> None:
        self._hooks = hooks
        self._staged_file = staged_file

    def write_attempts(self) -> None:
        self._hooks.write_attempts(self._staged_file)

    def publish(self) -> None:
        self._hooks.publish_attempts()

    def restore(self) -> None:
        self._hooks.discard_attempts()

    def discard(self) -> None:
        self._hooks.discard_attempts()


class _Strict:
    """The engine's `DeliveryStage` as a `SinkStage`: only `mode` is added."""

    mode: Literal["strict", "in_place"] = "strict"

    def __init__(self, stage: DeliveryStage) -> None:
        self.stage = stage

    def abort(self) -> None:
        self.stage.abort()

    def deliver(
        self,
        decision: StageDecision,
        before_visible: Callable[[], None],
        reconcile: Callable[[DeliveryReceipt], None] | None = None,
    ) -> DeliveryReceipt:
        return self.stage.deliver(decision, before_visible, reconcile)


class PassThroughStage:
    """Today's writers, named as such: no stage, no strict claim, `mode` `in_place`.

    The outputs are already in place when `deliver` runs, so the decision cannot withhold them,
    and `before_visible` has nothing to stage: the run's own tail still writes the report and the
    evidence after the outputs and moves `LATEST` last (a project run on a host without the
    engine's lock), exactly as before the sink.
    """

    mode: Literal["strict", "in_place"] = "in_place"

    def abort(self) -> None:
        return None

    def deliver(
        self,
        decision: StageDecision,
        before_visible: Callable[[], None],
        reconcile: Callable[[DeliveryReceipt], None] | None = None,
    ) -> DeliveryReceipt:
        from decoy_engine.publication import DeliveryReceipt

        receipt = DeliveryReceipt("delivered")
        if reconcile is not None:
            reconcile(receipt)
        return receipt


class _Placer(Protocol):
    """How one kind turns a declared table into a path the writer fills."""

    def place(self, table: str, raw: str) -> Path: ...
    def done(self, table: str, *, ok: bool) -> None: ...
    def staged(self, raw: str) -> Path: ...
    def report(self, final: Path, write: Callable[[Path], str | None]) -> str | None: ...
    def quarantine(self, config_dict: dict) -> str | None: ...
    def settle_quarantine(self, rows: int) -> None: ...


class _VaultProbe:
    """Records what the vault writer's one publish did, by wrapping that call on the writer.

    The engine's receipt does not say whether rule V ran, and the file system cannot say whose
    file it is, so the sink keeps the writer's own outcome. The engine insists on a real
    `VaultWriter`, so the writer stays the writer: only its `publish` is wrapped.
    """

    def __init__(self, writer: object) -> None:
        self.writer = writer
        self.outcome: Literal["pending", "published", "raised"] = "pending"
        self.exists = False  # the publish found a vault there (the engine then adopts or refuses)
        real = writer.publish  # type: ignore[attr-defined]

        def publish(out: object) -> object:
            from decoy_engine import reasons

            done = False
            try:
                result = real(out)
                done = True
                return result
            except Exception as exc:
                self.exists = getattr(exc, "code", None) == reasons.runtime.VAULT_EXISTS
                raise
            finally:
                self.outcome = "published" if done else "raised"

        writer.publish = publish  # type: ignore[attr-defined]


class _Direct:
    """Kind A pass-through: writers go straight to the placed path, as before."""

    def __init__(self, layout: RunLayout) -> None:
        self._layout = layout

    def place(self, table: str, raw: str) -> Path:
        return self._layout.place_target(raw)

    def done(self, table: str, *, ok: bool) -> None:
        return None

    def staged(self, raw: str) -> Path:
        return self._layout.place_target(raw)

    def report(self, final: Path, write: Callable[[Path], str | None]) -> str | None:
        return write(final)

    def quarantine(self, config_dict: dict) -> str | None:
        return self._layout.place_quarantine(config_dict)

    def settle_quarantine(self, rows: int) -> None:
        return None


class _Reserved:
    """Kind R: every file is a reserved member of the engine stage."""

    def __init__(self, layout: RunLayout, stage: DeliveryStage) -> None:
        assert layout.run is not None
        self._layout = layout
        self._stage = stage
        self._root = layout.run.path
        self._members: dict[str, StagedMember] = {}  # by declared path, so a re-ask is the same
        self._tables: dict[str, str] = {}  # declared path to table
        self._by_table: dict[str, StagedMember] = {}
        self._quarantine: StagedMember | None = None

    def _relative(self, raw: str) -> str:
        return self._layout.place_target(raw).relative_to(self._root).as_posix()

    def place(self, table: str, raw: str) -> Path:
        member = self._members.get(raw)
        if member is None:
            member = self._stage.reserve(table, self._relative(raw), "table")
            self._members[raw] = member
            self._tables[raw] = table
            self._by_table[table] = member
        return member.path

    def done(self, table: str, *, ok: bool) -> None:
        member = self._by_table[table]
        if ok:
            member.complete()
        else:
            member.fail()

    def staged(self, raw: str) -> Path:
        """Where the claimed file sits in the unit stage: the bytes the bind publishes unchanged."""
        table = self._tables.get(raw)
        return self._stage.staged_path(table) if table else self._layout.place_target(raw)

    def report(self, final: Path, write: Callable[[Path], str | None]) -> str | None:
        member = self._stage.reserve(None, final.relative_to(self._root).as_posix(), "report")
        failed = write(member.path)
        if failed is None:
            member.complete()
        else:
            member.fail()
        return failed

    def quarantine(self, config_dict: dict) -> str | None:
        raw = self._layout.place_quarantine(config_dict)
        if raw is None:
            return None
        relpath = Path(raw).relative_to(self._root).as_posix()
        self._quarantine = self._stage.reserve(None, relpath, "quarantine")
        return str(self._quarantine.path)

    def settle_quarantine(self, rows: int) -> None:
        if self._quarantine is None:
            return
        if rows > 0:
            self._quarantine.complete()
        else:
            self._quarantine.omit()


class DeliverySink:
    """Stage every output of one run, then deliver them together or not at all.

    States: `open`, `delivering`, `delivered`, `aborted`. The state becomes `delivered` in the
    stage's `reconcile` call, which runs in the statement that passes the visibility point, so
    a Ctrl-C after it leaves the run delivered. `abort` after `delivered` is a no-op.
    """

    def __init__(
        self,
        kind: RootKind,
        stage: SinkStage,
        placer: _Placer,
        layout: RunLayout,
        hooks: DeliveryHooks,
    ) -> None:
        self.kind = kind
        self._stage = stage
        self._placer = placer
        self._layout = layout
        self._hooks = hooks
        self.state: Literal["open", "delivering", "delivered", "aborted"] = "open"
        self.receipt: DeliveryReceipt | None = None
        self.decision: DeliveryDecision | None = None
        self._vault_fact: Literal["not_used", "committed", "failed"] = "not_used"
        self._probe: _VaultProbe | None = None
        self.cleanup_failed = False
        self.report_failed = False  # the not-delivered report could not be written
        self.report_path: Path | None = None  # where that report was written, when it was
        self._report_writer: Callable[..., str | None] | None = None
        self._report_tried = False
        self.withheld = False  # the run's decision withheld every table
        self._finals: dict[str, Path] = {}
        self._pre = PreVisible(hooks, placer.staged)
        layout.on_abandon(self.abort)

    @property
    def mode(self) -> Literal["strict", "in_place"]:
        return self._stage.mode

    @classmethod
    def open(
        cls, layout: RunLayout, config_dict: dict, hooks: DeliveryHooks, operation_id: str
    ) -> DeliverySink:
        """Choose the stage from the delivery root, never from the route, and open it."""
        root = delivery_root(config_dict, layout.contained_base)
        if isinstance(root, Split):
            raise DELIVERY_ROOT_SPLIT.error(first=root.first, second=root.second)
        if isinstance(root, Fixed | NoLocalOutput):
            return cls(RootKind.fixed_folder, PassThroughStage(), _Direct(layout), layout, hooks)
        if not isinstance(root, Relative):  # a new DeliveryRoot variant needs its own stage
            raise TypeError(type(root).__name__)
        folder = layout.pipeline_dir
        if layout.run is None or folder is None:
            raise RuntimeError("a relative delivery root needs a run folder")
        if not strict_route(root):
            return cls(RootKind.run_folder, PassThroughStage(), _Direct(layout), layout, hooks)
        from decoy_engine.fileaccess import FileRequest, FileRole, current
        from decoy_engine.publication import DeliveryStage

        out = current().output_dir(
            FileRequest(FileRole.TARGET_OUTPUT, "write", str(layout.run.path), "layout.run")
        )
        stage = DeliveryStage.open(
            out,
            _pointer.latest_pointer(folder),
            layout.run.run_id,
            operation_id,
            lock_timeout_s=_pointer.LATEST_LOCK_TIMEOUT_S,
        )
        return cls(RootKind.run_folder, _Strict(stage), _Reserved(layout, stage), layout, hooks)

    # --- writers -------------------------------------------------------------------------

    def attach_vault(self, writer: object, vault: Path, commit: Callable[[], None]) -> None:
        """Kind R hands the vault to the stage (rule V publishes it create-only before the
        bind); kind A commits it now, before any output, as before."""
        if not isinstance(self._stage, _Strict):
            commit()
            self._vault_fact = "committed"
            return
        from decoy_engine.fileaccess import FileRequest, FileRole, current
        from decoy_engine.publication import VaultBinding

        self._probe = _VaultProbe(writer)
        request = FileRequest(FileRole.TARGET_OUTPUT, "write", str(vault), "vault")
        self._stage.stage.set_vault(VaultBinding(writer, current().output_dir(request)))  # type: ignore[arg-type]

    @property
    def vault(self) -> Literal["not_used", "committed", "failed"]:
        """What this run's own vault write did, as the writer recorded it (never a file check)."""
        probe = self._probe
        if probe is None:
            return self._vault_fact
        if probe.outcome == "published":
            return "committed"
        adopted = probe.exists and self.receipt is not None and self.receipt.state != "nothing"
        return "committed" if adopted else ("failed" if probe.outcome == "raised" else "not_used")

    def place_quarantine(self, config_dict: dict) -> str | None:
        """The `run_pipeline(quarantine_path=...)` value: a staged path on kind R."""
        if not quarantine_enabled(config_dict):
            return None
        return self._placer.quarantine(config_dict)

    def settle_quarantine(self, quality_metrics: dict) -> None:
        """Complete the quarantine member when the engine reports rows, omit it when not."""
        summary = quality_metrics.get("quarantine") or {}
        self._placer.settle_quarantine(int(summary.get("total_quarantined") or 0))

    def write_outputs(self, config_dict: dict, outputs: dict, ledger: Ledger) -> None:
        """Write each declared file target. The one table writer is `_targets.write_target`."""
        check_target_formats(config_dict, chunked=False)
        if isinstance(self._placer, _Direct):
            write_targets(config_dict, outputs, self._layout, ledger)
            return
        preflight_csv_targets(config_dict, outputs)
        scratch = Ledger()  # a slot path is never a published path
        for name, entry, raw, table in file_targets(config_dict, outputs):
            path = self._placer.place(str(name), raw)
            self._finals[str(name)] = self._layout.place_target(raw)
            try:
                write_target(name, entry, table, path, scratch)
            except BaseException:
                self._placer.done(str(name), ok=False)
                raise
            self._placer.done(str(name), ok=True)

    def stage_report(self, final: Path, write: Callable[..., str | None]) -> str | None:
        """Write the implicit post-scan report: a member of the run folder on kind R, the
        placed file as before on kind A. The failure text, or None."""
        if isinstance(self._stage, _Strict):
            self._report_writer = write  # kept for a run that delivers nothing (AT-59)
        return self._placer.report(final, write)

    def keep_report(self, write: Callable[..., str | None]) -> None:
        """Remember how to write the report when `--integrity-out` carries it (kind R only)."""
        if isinstance(self._stage, _Strict):
            self._report_writer = write

    def final_paths(self) -> dict[str, Path]:
        """Table to the path it will have once delivered (kind R); empty for the pass-through."""
        return dict(self._finals)

    # --- delivery ------------------------------------------------------------------------

    def deliver(self, decision: StageDecision, ledger: Ledger) -> DeliveryReceipt:
        """Hand the stage the decision; it runs `before_visible`, the bind and the swap."""
        self.state = "delivering"

        def reconcile(receipt: DeliveryReceipt) -> None:
            self._reconcile(receipt, decision, ledger)

        with contextlib.ExitStack() as held:
            # Before the pointer lock, in one order, so two runs sharing a file cannot deadlock.
            # The strict route only, and only a run that publishes: the pass-through behaves as
            # before the sink, and a withheld run touches no publication file but its report.
            strict_delivery = self.mode == "strict" and decision.deliver
            if strict_delivery and hold_side_files(held, self._hooks.side_files):
                raise SideFileBusy
            try:
                before = self._pre.write_attempts if self.mode == "strict" else _nothing
                receipt = self._stage.deliver(decision, before, reconcile)
            except BaseException:
                if not self._bound():
                    self._publish_side_report()  # a failure before the bind keeps the verdict
                raise
        if self.receipt is None:  # a withheld decision aborts without calling `reconcile`
            self.receipt = receipt
            self.state = "aborted" if receipt.state == "nothing" else "delivered"
        if not decision.deliver and receipt.state == "nothing":
            self._publish_side_report()
        return receipt

    def _bound(self) -> bool:
        """Whether the engine already bound the run folder (its descriptor is in it)."""
        from decoy_engine.fileaccess import DESCRIPTOR_NAME

        run = self._layout.run
        return run is not None and os.path.lexists(run.path / DESCRIPTOR_NAME)

    def _publish_side_report(self) -> None:
        """A strict run that delivered nothing before the bind keeps its post-scan verdict as
        `out/<name>/<run-id>.post-scan.json`, created once under that leaf's own lock (or in
        the explicit `--integrity-out`). It runs once; a failure is one warning and never
        changes the exit."""
        write, run, folder = self._report_writer, self._layout.run, self._layout.pipeline_dir
        if write is None or run is None or folder is None or self._report_tried:
            return
        self._report_tried = True
        explicit = self._hooks.integrity_out
        path = explicit or folder / not_delivered_report_name(run.run_id)
        failed = True
        with contextlib.suppress(Exception):
            with contextlib.ExitStack() as held:
                if explicit is None and _pointer.pointer_supported():
                    from decoy_engine.fileaccess import FileRequest, FileRole, current

                    request = FileRequest(
                        FileRole.TARGET_OUTPUT, "write", str(path), "not_delivered_report"
                    )
                    held.enter_context(
                        current().output_dir(request).lock(_pointer.LATEST_LOCK_TIMEOUT_S)
                    )
                failed = write(path, create_only=explicit is None) is not None
        self.report_failed = failed
        self.report_path = None if failed else path

    def publish_blocked_report(self, write: Callable[..., str | None]) -> Path | None:
        """The verdict of a run an engine finding blocked: kept beside the run folder like any
        other run that delivers nothing. Where it went, or None."""
        self._report_writer = write
        self._report_tried = False
        self._publish_side_report()
        return self.report_path

    def report_location(self, staged_for: Path | None) -> Path | None:
        """Where the post-scan report really is: the run folder when the run bound, the
        not-delivered file when it was written, otherwise nowhere. An uncertain receipt shows no
        path, and its attempt report was discarded."""
        if self.mode != "strict":
            return staged_for
        if self.confirmed:
            return staged_for
        return self.report_path

    def _reconcile(self, receipt: DeliveryReceipt, decision: StageDecision, ledger: Ledger) -> None:
        """Runs once under the pointer lock and must not raise. Each step is its own handler, so
        a failure in one never skips a later one, and the `current` re-point cannot be skipped."""
        self.receipt = receipt
        if receipt.state == "nothing":
            self.state = "aborted"
            self._step(self._pre.restore)
            return
        self.state = "delivered"
        if not isinstance(self._stage, _Strict):
            return  # the writers filled the ledger; the run's tail does the rest
        self._step(self._link_current)
        if receipt.state == "uncertain":
            self._step(self._warn_uncertain)
        else:
            self._step(self._pre.publish)
        self._step(self._pre.discard)
        self._step(lambda: self._fill(ledger, decision))

    def _warn_uncertain(self) -> None:
        self._hooks.show_warning(LATEST_COMMIT_UNCERTAIN.warning())

    def _link_current(self) -> None:
        run, folder = self._layout.run, self._layout.pipeline_dir
        if run is not None and folder is not None:
            for item in _pointer.link_current(folder, run.run_id):
                self._hooks.show_warning(item)
                self.cleanup_failed = True  # the helper returns the fault; it is a cleanup fault

    def _fill(self, ledger: Ledger, decision: StageDecision) -> None:
        for name, path in self._finals.items():
            if name in decision.delivered:
                ledger[name] = LocalOutput(path)

    def _step(self, work: Callable[[], None]) -> None:
        """Run one step after the visibility point. Any `Exception` only sets a flag; the one
        warning is added by the caller, after this handler closes, so no context rides on it."""
        with contextlib.suppress(Exception):
            work()
            return
        self.cleanup_failed = True

    def abort(self) -> None:
        """Remove the stages. Never raises: `abandon` calls it from a `finally`."""
        if self.state in ("delivered", "aborted"):
            return
        self.state = "aborted"
        self._step(self._stage.abort)
        self._step(self._pre.restore)
        if self.mode == "strict":
            self._step(self._side_report_if_unbound)

    def _side_report_if_unbound(self) -> None:
        if not self._bound():
            self._publish_side_report()

    @property
    def confirmed(self) -> bool:
        """True when the receipt is `delivered`. Only then may a renderer show a path."""
        return self.receipt is not None and self.receipt.state == "delivered"

    def settled(self) -> bool:
        """True once the visibility point has passed: a delivered or uncertain receipt."""
        return self.receipt is not None and self.receipt.state != "nothing"


__all__ = [
    "DeliveryHooks",
    "DeliverySink",
    "PassThroughStage",
    "PreVisible",
    "RootKind",
    "SinkStage",
]
