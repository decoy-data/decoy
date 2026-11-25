"""The out-of-core FK capacity check."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from decoy.cli.gate import capacity_codes
from decoy.cli.gate._capacity_text import format_gib as _format_gib
from decoy.cli.gate._capacity_text import insufficient_text as _insufficient_text
from decoy.cli.preflight._result import (
    CAPACITY_CHECK,
    PLAN_UNCOMPILABLE_CHECK,
    _PreflightAccumulator,
)


def _file_sources_missing_on_disk(raw: dict[str, Any], base_dir: Path) -> bool:
    """True if any declared FILE-type source does not resolve to a readable
    regular file, resolved the SAME way `estimate_job_capacity`,
    `_check_source_files`, and `decoy run` resolve them (relative to
    `base_dir`, the pipeline YAML's directory -- R2). All three now agree on
    resolution, so a source missing where the runner would look is reported
    by Step 4 as a `fail` AND skipped here, never silently passed.

    Root-cause guard: a source already reported missing by Step 4 would still reach
    `estimate_job_capacity`, which raises on an unreadable source and would crash the whole
    command before `_emit_preflight_result` prints any finding. Skipping a check whose
    precondition is already known false is not swallowing a defect; it matches the
    non-file-source skip below.
    """
    sources = raw.get("sources") or {}
    if not isinstance(sources, dict):
        return False
    for src in sources.values():
        if not isinstance(src, dict) or (src.get("type") or "file") != "file":
            continue
        path_str = src.get("path")
        if not path_str:
            return True
        path = Path(path_str)
        if not path.is_absolute():
            path = base_dir / path
        if not path.is_file():
            return True
        # Present but UN-OPENABLE counts too (Codex re-gate MEDIUM): a
        # permission-denied file opens-then-fails, and `estimate_job_capacity`
        # -> `profile_source` opens the source, so with the broad catch removed
        # (R3) it would crash the command. Skip the estimate; Step 4's
        # readability check already reported the `fail`. This tests filesystem
        # ACCESSIBILITY only (open + zero-byte read) -- a file that opens but is
        # truncated/corrupt/wrong-format is NOT caught here (parsing would be
        # required); that case is handled downstream by the estimator's typed
        # `capacity_source_unprofilable` error, rendered as a capacity fail.
        try:
            with path.open("rb") as fh:
                fh.read(0)
        except OSError:
            return True
    return False


def _check_capacity(raw: dict[str, Any], config_path: Path, acc: _PreflightAccumulator) -> None:
    """Predict the out-of-core-FK memory-capacity gate before a run starts.

    R4 honest framing: this covers the out-of-core-FK route's memory check,
    which has two branches -- an ADVISORY build-floor prediction (an over-cap
    floor WARNS with a recommended size, it does not refuse) and a hard fan-in
    impossibility guard (the only branch that exits EXIT_CAPACITY). `decoy run`
    fully loads every source into memory BEFORE it ever calls the engine, so an
    ingestion `MemoryError` or OS OOM-kill happens before this gate runs; a
    "capacity: OK" here says nothing about that. See the module docstring's
    "OOM checker v1" note.

    R3 (Codex P1-2): `estimate_job_capacity` returns a typed verdict
    (`UNKNOWN` for expected indeterminacy) or raises. A plan the engine
    rejects (`PlanCompileError`) becomes a `capacity.plan_uncompilable` FAIL;
    any other exception is a real defect and propagates, since folding it
    into a WARN would report a false pass. Only the TWO guarded
    early-returns below (non-file sources, a source already known
    missing/unreadable from disk) skip the estimator. The second
    exists because a missing source is also one of the estimator's documented
    propagating cases: without it, a source Step 4 (`_check_source_files`)
    already flagged would crash the command before any finding is printed.

    Scope + posture: this section reads FILE-source metadata (parquet footer /
    a bounded local sample) to size the job. To keep preflight local and
    no-network, it runs only when every source is a file; if any source is
    non-file (database/API), capacity is "not checked" here rather than opening
    a remote connection during a "local" preflight.
    """
    import decoy_engine.execution as _engine_execution

    # Preserve preflight's local, no-network posture: the engine estimate reads
    # each source, which for a non-file source means opening a DB/remote
    # connection. A "local" preflight must not do that, so skip capacity when
    # any source is non-file (matches _check_source_files' file-only scope).
    sources = raw.get("sources") or {}
    if isinstance(sources, dict) and any(
        isinstance(s, dict) and (s.get("type") or "file") != "file" for s in sources.values()
    ):
        acc.add_pass(
            name=CAPACITY_CHECK,
            message="not checked -- capacity is estimated only for file sources in local preflight.",
        )
        return

    # A source already known missing/unreadable (Step 4 already reported this
    # as a `fail`) cannot be estimated -- see `_file_sources_missing_on_disk`'s
    # docstring for why this guard exists (a real regression it fixes).
    if _file_sources_missing_on_disk(raw, config_path.parent):
        acc.add_pass(
            name=CAPACITY_CHECK,
            message="not checked -- one or more declared source files are missing or "
            "unreadable; see the source-file findings above.",
        )
        return

    from decoy_engine import (
        CapacityVerdict,
        ExecutionError,
        PipelineValidationError,
        parse_pipeline_config,
    )
    from decoy_engine.plan import PlanCompileError

    # Narrow catches only (R3): the estimator is the first read that parses a source, so a
    # corrupt file (`capacity_source_unprofilable`) or a column the config and file disagree on
    # (`source_file.*`) surfaces here as a FAIL, not a traceback. Any other exception is an
    # estimator defect and propagates, never degraded into a WARN or a false pass.
    config_dump = parse_pipeline_config(raw).model_dump()
    try:
        estimate = _engine_execution.estimate_job_capacity(config_dump, base_dir=config_path.parent)
    except ExecutionError as exc:
        if exc.code in capacity_codes():
            # The build-floor gate is advisory, so the estimator no longer returns
            # INSUFFICIENT for it, but a capacity refusal found while resolving the
            # memory budget still propagates as this ExecutionError. The set is the
            # engine's own, so `decoy run` agrees on every code. Render it like the
            # INSUFFICIENT verdict below: a FAIL that trips EXIT_CAPACITY.
            acc.capacity_insufficient = True
            acc.add_fail(
                name=CAPACITY_CHECK,
                message=f"INSUFFICIENT -- {exc.message}",
                code=exc.code,
            )
            return
        if exc.code != "capacity_source_unprofilable":
            raise
        acc.add_fail(
            name="capacity.source_unreadable",
            message=f"Cannot estimate capacity -- source not parsed ({type(exc.__cause__).__name__})",
            code=exc.code,
        )
        return
    except PipelineValidationError as exc:
        # The engine's one declared-column check, with the code `decoy run` gives.
        if not str(exc.code).startswith("source_file."):
            raise
        acc.add_fail(name="source.declared_columns", message=str(exc), code=exc.code)
        return
    except PlanCompileError as exc:
        # Own check name so CHUNKED's CAPACITY_CHECK downgrade cannot make it a warning.
        # Only the structured code and path are shown, never the engine's message text.
        from decoy_engine.relationships import NamespaceConfigError

        hint = (
            "Run `decoy explain pipeline` for how namespaces are resolved."
            if isinstance(exc, NamespaceConfigError)
            else "Run `decoy validate compile` for the compile error."
        )
        acc.add_fail(
            name=PLAN_UNCOMPILABLE_CHECK,
            message=f"Cannot estimate capacity -- the plan does not compile ({exc.code}). {hint}",
            location=exc.path,
            code=exc.code,
        )
        return

    needed = _format_gib(estimate.needed_bytes)
    available = _format_gib(estimate.available_bytes)

    if estimate.verdict is CapacityVerdict.FIT and estimate.warned:
        # Round-4: FIT no longer means "clears the build-floor budget" -- it
        # means "no hard impossibility detected". `warned=True` marks an
        # adverse build-floor prediction (relation-build only; excludes
        # resident inputs, accumulated outputs, and ingestion peak); render
        # it as a WARNING, not a green PASS, so `--fail-on-warning` can act
        # on it, but the job is not refused either way.
        # Relay the engine's own wording verbatim: it distinguishes a floor that
        # NEARS its cap (the warn band, floor still under cap) from one that
        # EXCEEDS it, so a hardcoded "exceeds" here would misreport a warn-band
        # floor that still sits under its cap as over it.
        acc.add_warn(
            name=CAPACITY_CHECK,
            message=(
                f"ADVISORY -- {estimate.message} Recommends {needed} (budget {available}); "
                "the job is not refused, this is a recommendation."
            ),
        )
    elif estimate.verdict is CapacityVerdict.FIT:
        acc.add_pass(
            name=CAPACITY_CHECK,
            message=(
                "OK -- OOC-FK estimated resident floor is within budget (does not "
                f"include ingestion peak). Needs {needed}, budget {available}."
            ),
        )
    elif estimate.verdict is CapacityVerdict.INSUFFICIENT:
        acc.capacity_insufficient = True
        acc.add_fail(name=CAPACITY_CHECK, message=_insufficient_text(estimate), code=estimate.code)
    elif estimate.verdict is CapacityVerdict.UNKNOWN:
        # An uncertain route (a byte-estimate-promoted OOC job) forces UNKNOWN,
        # but a build-floor advisory can still ride along on the estimate. Surface
        # it as a warning so the recommendation is not lost and --fail-on-warning
        # can act on it, exactly as it does on the confirmed FIT+warned path.
        if estimate.warned:
            acc.add_warn(
                name=CAPACITY_CHECK,
                message=f"ADVISORY (route unconfirmed) -- {estimate.message}",
            )
        else:
            acc.add_pass(name=CAPACITY_CHECK, message=f"not checked -- {estimate.message}")
    else:  # NOT_APPLICABLE
        acc.add_pass(name=CAPACITY_CHECK, message=f"not applicable -- {estimate.message}")
