"""The catch-all error arm of `decoy run`: exception to exit code, text and output."""

from datetime import datetime, timezone
from typing import Any, NoReturn

import typer

from decoy import _mask_secret_guidance, _native_gate
from decoy._atomic import AtomicWriteError, describe
from decoy.cli import exit_codes as _exit_codes
from decoy.cli import gen
from decoy.cli.extras import (
    MissingExtraError,
    translate_missing_extra,
    translate_ner_unavailable,
)
from decoy.cli.gate import PreRunCheckError, cap_error_text, capacity_codes
from decoy.cli.io import OUTPUT_DIR_UNUSABLE, LayoutError, blocked_run
from decoy.cli.run import _result
from decoy.cli.run._context import (
    EvidenceWriteRefusal,
    IntegrityWriteRefusal,
    RunContext,
    RunRefusal,
)
from decoy.cli.run._notify import _dispatch_run_notifications
from decoy.cli.run._value_free import is_out_of_memory
from decoy.cli.run._vault import VAULT_COMMIT_FAILED_HINT, _VaultWriteError
from decoy.ui.output import OutputMode, is_reason_code, print_traceback

# The engine's capacity-refusal codes come from its registry (`capacity_codes()`); see
# docs/plans/2026-07-24-oom-checker-cli-v1.md R8 for why the match is narrow.

# The engine's code for a `unique` generate column or pair that the data cannot satisfy.
UNIQUENESS_IMPOSSIBLE_CODE = "uniqueness_impossible"


def config_caused_generation_codes() -> frozenset[str]:
    """Run-time generation failures the config causes, so they exit 1 like the validate-time checks.

    Other GenerationError codes (dtype_unsafe, timezone_naive_datetime) stay runtime errors. The
    engine import is lazy to keep it off the help path.
    """
    from decoy_engine import reasons

    return frozenset(
        {UNIQUENESS_IMPOSSIBLE_CODE, str(reasons.runtime.GENERATE_FORMULA_EVALUATION_FAILED)}
    )


_OUT_OF_MEMORY_TEXT = "the run ran out of memory."
_CAPACITY_HINT = (
    "this job needs more memory than this host has; use a larger tier or reduce the job."
)
_VERBOSE_HINT = "rerun with --verbose for the full traceback."


class OutDirUsageError(LayoutError):
    """`--out-dir` names something that cannot be a run's output directory.

    Always the registry's fixed `layout.output_dir_unusable` text: the caller's wording and
    the path are dropped, so nothing about the directory reaches the message.
    """

    def __init__(self, _detail: str = "") -> None:
        super().__init__(OUTPUT_DIR_UNUSABLE.code, OUTPUT_DIR_UNUSABLE.message())


def _engine_family(exc_type: type) -> bool:
    """Whether the engine's reason adapter trusts this exception class."""
    from decoy_engine.reason_adapter import registered_families

    return issubclass(exc_type, tuple(registered_families()))


def _cli_refusal_types() -> tuple[type, ...]:
    """Refusals the CLI raises itself, so the engine has no reason for them.

    The exit-1 types that are not engine families, plus the vault write failure (exit 3) and
    the gate refusal (exit 1 or 5) and the evidence write refusal (exit 3).
    """
    owned = tuple(t for t in _exit_codes.usage_error_types() if not _engine_family(t))
    return (*owned, _VaultWriteError, PreRunCheckError, EvidenceWriteRefusal, IntegrityWriteRefusal)


def _failure_reason(exc: Exception, engine_exc: Exception) -> Any:
    """The engine's `ReasonRecord` for the failure, or None when the CLI owns the refusal.

    `engine_exc` is the exception as the engine raised it, before the missing-extra and NER
    rewrites, so a rewrite keeps the engine's record. The answer is computed here only; any
    error in it drops the reason and never changes the exit.
    """
    try:
        from decoy_engine import reason_adapter

        if not _engine_family(type(engine_exc)) and isinstance(exc, _cli_refusal_types()):
            return None
        return reason_adapter.reason_from_exception(engine_exc)
    except Exception:
        return None


def _fixed_text_types() -> tuple[type, ...]:
    """Exceptions whose text the CLI or its registries author, so it holds no data value.

    The CLI's own refusals (`_cli_refusal_types`), the config file error and the
    missing-extra install line. An engine exception is not here: it earns its text through a
    registered code (see `_safe_error_text`).
    """
    from decoy._config_file import ConfigFileError

    return (*_cli_refusal_types(), ConfigFileError, MissingExtraError)


def _capacity_text(code: str) -> str:
    """The fixed text of a coded capacity refusal. The engine's own message is dropped: it
    quotes sizes and host figures."""
    return f"the job needs more memory than this host has ({code})."


def _safe_error_text(exc: Exception, *, capacity_code: str | None, out_of_memory: bool) -> str:
    """The run error text for `exc`: fixed words, codes and the exception type name only.

    `str(exc)` of an arbitrary exception can quote a source cell (pandas, pyarrow, a formula), and
    this text reaches the terminal in every mode, the `--json` document and the first-finding
    summary. A specific message is kept only when its producer supplies fixed text: a CLI
    refusal, a file-write description, a layout refusal, or an engine error that carries a
    registered reason code. Everything else reads `run failed (<ExceptionType>).`.
    """
    from decoy_engine import DecoyError

    if out_of_memory:
        return _OUT_OF_MEMORY_TEXT
    if capacity_code is not None:
        return _capacity_text(capacity_code)
    if isinstance(exc, AtomicWriteError):
        return describe(exc)
    if isinstance(exc, LayoutError):
        return f"{exc.code}: {exc.message}"
    if isinstance(exc, _fixed_text_types()) or (
        isinstance(exc, DecoyError) and is_reason_code(getattr(exc, "code", None))
    ):
        return cap_error_text(str(exc))
    return f"run failed ({type(exc).__name__})."


def fail(ctx: RunContext, exc: Exception) -> NoReturn:
    """Map `exc` to an exit code, notify, print the error and exit. Called inside the
    `except` block so the exit keeps the exception as its context.

    The exit is `exit_code_for(exc)` (through `run_category_for`) and the output is the one
    error emitter, `_result.finish_error`.
    """
    # The reason comes from the exception as raised, before the rewrites below.
    engine_exc = exc
    # Imported lazily to keep the engine import off the help path.
    from decoy_engine import GenerationError, VaultError, reasons
    from decoy_engine.verification.postmask import PostScanBlockedError

    # CLI install DX (2026-09-25): a pipeline step that lazily imports an
    # optional dependency (boto3/google-cloud-storage for a cloud
    # source/target, spacy for NER, etc.) raises ImportError when the
    # matching decoy-cli extra isn't installed. Translate that into the
    # exact install line instead of a raw traceback. An ImportError for
    # anything NOT a known optional extra is left as-is (stays classified
    # EXIT_RUNTIME below -- that is a real defect, not a missing extra).
    if isinstance(exc, ImportError):
        _missing_extra = translate_missing_extra(exc)
        if _missing_extra is not None:
            exc = _missing_extra

    # CLI install DX (2026-09-25): the engine's own NerUnavailableError
    # (text_mask/text_redact `ner`) already fails closed for a missing
    # spaCy install; rewrite it to point at decoy-cli's own `[ner]`
    # extra instead of `decoy-engine[ner]` (see translate_ner_unavailable
    # docstring for why only the "spaCy absent" case is rewritten).
    _translated_ner = translate_ner_unavailable(exc)
    if _translated_ner is not None:
        exc = _translated_ner

    # DE-02: MaskSecretError lives in the engine's `keyprovider` module,
    # which a pre-DE-02 engine lacks. Import defensively so a missing
    # module never crashes the error handler itself (it would mask the
    # real exception). `()` makes the isinstance check below a harmless
    # no-op when the class is unavailable.
    try:
        from decoy_engine.keyprovider import MaskSecretError as _MaskSecretError

        _mask_secret_error_types: tuple = (_MaskSecretError,)
    except ImportError:
        _mask_secret_error_types = ()

    # The category names the failure; the exit integer comes from `RUN_EXIT_MAP`, through the
    # one exception-to-exit owner. A blocking post-scan finding has no category (exit 4).
    category = _exit_codes.run_category_for(exc)
    pre_run = isinstance(exc, PreRunCheckError)
    is_capacity = category == "capacity"
    # A coded capacity refusal (an engine error or a generate budget) keeps its code. A bare
    # `MemoryError` has no code and often no text: fixed text instead of an empty `error: `.
    capacity_code: str | None = None
    if is_capacity and not pre_run:
        candidate = getattr(exc, "code", None)
        if isinstance(candidate, str) and candidate in capacity_codes():
            capacity_code = candidate
    out_of_memory = is_capacity and not pre_run and is_out_of_memory(exc)

    # One document and one exit integer for the run, from the one builder.
    record = _failure_reason(exc, engine_exc)
    document = _result.build(
        ctx,
        category=category,
        reason=record,
        error_class=type(exc).__name__,
        blocking_failed=isinstance(exc, PostScanBlockedError),
        vault_failed=isinstance(exc, _VaultWriteError),
    )
    # CLI QA fix (2026-06-02, F8): engine exceptions can quote source-row content verbatim
    # (pandas / pyarrow). `_safe_error_text` keeps only text the producer fixes.
    error_text = _safe_error_text(exc, capacity_code=capacity_code, out_of_memory=out_of_memory)
    blocked: dict[str, Any] = {}
    if isinstance(exc, PostScanBlockedError):  # writes the report; the text is the fixed summary
        error_text, blocked = blocked_run(ctx.state, exc, ctx._post_scan_file, ctx.config_sha256)
    keyed_refusal = _mask_secret_guidance.is_keyed_secret_refusal(exc)
    if isinstance(exc, _mask_secret_error_types):
        # Constant text by code; the engine message never reaches the terminal or --json.
        error_text = _mask_secret_guidance.secret_error_text(exc, _mask_secret_guidance.RUN)

    # PII egress guard (dennis sprint-5 BLOCKER): the raw engine error
    # can quote source-row cell values verbatim (see the comment above),
    # so it MUST NOT ride into an outbound notification, which is POSTed
    # to a third-party webhook / Slack / email. Only the exception TYPE
    # name goes on the wire. Redaction by construction, mirroring the
    # platform's facts-only alert rule (dispatcher.py:137-142).
    ctx.notify_results = _dispatch_run_notifications(
        ctx.notify_channels,
        notify_on=ctx.notify_on.value,
        status="failure",
        config_path=ctx.config_str,
        row_count=None,
        started_at=ctx._run_started_at,
        finished_at=datetime.now(timezone.utc),
        error_summary=type(exc).__name__,
        state=ctx.state,
    )

    # A preview shrinks the tables; a bound it can no longer meet is fixed by a larger --rows.
    raise_rows_hint = (
        ctx.rows is not None
        and isinstance(exc, GenerationError)
        and exc.code == UNIQUENESS_IMPOSSIBLE_CODE
    )
    remove_vault_hint = (
        isinstance(engine_exc, VaultError)
        and engine_exc.code == reasons.runtime.VAULT_COMMIT_FAILED
    )

    # One hint per error: the specific one wins over "rerun with --verbose".
    hint: str | None
    if raise_rows_hint:
        hint = gen.RAISE_ROWS_HINT
    elif remove_vault_hint:
        hint = VAULT_COMMIT_FAILED_HINT
    elif capacity_code is not None or out_of_memory:
        hint = _CAPACITY_HINT
    elif pre_run or keyed_refusal or isinstance(exc, PostScanBlockedError):
        hint = None  # the refusal or verdict says it all; a verdict is not a crash
    else:
        hint = _VERBOSE_HINT

    # The one code of the envelope: the refusal's, the post-scan reason, the capacity code or
    # the native gate's. Only a valid reason code is promoted; `emit_error` would refuse the rest.
    code: str | None = None
    if pre_run:
        code = exc.code
    elif isinstance(exc, PostScanBlockedError):
        code = blocked.pop("code", None)
    elif capacity_code is not None:
        code = capacity_code
    elif isinstance(exc, _native_gate.NativeGateError):
        code = exc.code
    if not is_reason_code(code):
        code = None

    context: dict[str, Any] = {"config": ctx.config_str, "mode": ctx.yaml_mode}
    if ctx.state.mode is OutputMode.json:
        # Only what the publication ledger holds: files a writer finished, and their folder.
        if ctx.layout is not None:
            ctx.layout.abandon()
        context.update(ctx.published_members())
        context.update(blocked)
        if pre_run:
            context.update(exc.context_members())
        elif is_capacity:
            context["error_kind"] = "capacity"
        elif isinstance(exc, _native_gate.NativeGateError):
            context["error_kind"] = "native"
        elif isinstance(exc, MissingExtraError):
            # A machine-detectable field, not just the `[missing_extra]`-prefixed message text.
            context["error_kind"] = "missing_extra"
            context["extra"] = exc.extra
        if record is not None:
            context["reason"] = record.to_payload()
        if ctx.notify_channels:
            context["notify"] = ctx.notify_results
    # The terminal reads `error: capacity: <text>`; the JSON `error` has no label. A refusal or a
    # blocked run keeps its plain `error: <text>` line: its code is a machine member.
    human_line: _result.HumanLine | None = None
    if is_capacity:
        human_line = _result.HumanLine(f"capacity: {error_text}")
    elif pre_run or isinstance(exc, PostScanBlockedError):
        human_line = _result.HumanLine(error_text)
    _result.finish_error(
        ctx,
        document,
        error_text,
        code=code,
        hint=hint,
        context=context,
        human_line=human_line,
        then=(lambda: print_traceback(ctx.state)) if ctx.state.verbose else None,
    )
    raise AssertionError("a failed run has a non-zero exit code")  # pragma: no cover


def _early(ctx: RunContext) -> bool:
    """Whether the run stopped before the engine phase began (no collector yet)."""
    return ctx._collector is None


def _inside_run(ctx: RunContext) -> dict[str, Any]:
    """The legacy members of a run that ends after the engine phase began, outside the error
    arm: the same base as `fail`, with the files the run had already published."""
    return {"config": ctx.config_str, "mode": ctx.yaml_mode, **ctx.published_members()}


def refused(ctx: RunContext, refusal: RunRefusal) -> NoReturn:
    """End the run for a typed CLI refusal: print it, write the envelope and exit.

    The exit is the document's: 1 for a usage refusal, 3 for the evidence write. A refusal
    names flags and codes only, so its text goes to the terminal and the envelope as is.
    """
    document = _result.build(
        ctx, category=refusal.category, error_class=type(refusal).__name__, early=_early(ctx)
    )
    if isinstance(refusal, (EvidenceWriteRefusal, IntegrityWriteRefusal)):
        # The outputs are already written, so the error shows in every mode, `--quiet` included.
        _result.finish_error(
            ctx,
            document,
            refusal.text,
            code=refusal.code,
            context=_inside_run(ctx),
            stderr_line=True,
        )
    # A refusal with no code was silent under `--quiet`; one with a code was not.
    silent = ctx.state.mode is OutputMode.quiet and refusal.code is None
    _result.finish_error(
        ctx,
        document,
        refusal.text,
        code=refusal.code,
        context={"config": ctx.config_str},
        human=not silent,
    )
    raise AssertionError("a refusal has a non-zero exit code")  # pragma: no cover


def bad_parameter(ctx: RunContext, exc: typer.BadParameter) -> None:
    """Write the envelope for a `--master-key` or `--key-label` refusal (exit 2).

    Returns, and the caller re-raises the Typer error, so Typer prints its own message and
    exits 2 as before; the document carries the same 2.
    """
    document = _result.build(ctx, category="parameter", error_class=type(exc).__name__, early=True)
    _result.report_error(
        ctx, document, exc.message, context={"config": ctx.config_str}, human=False
    )


def interrupted(ctx: RunContext) -> None:
    """Write the envelope for Ctrl-C. Returns, and the caller re-raises the interrupt, so the
    process ends as it did before; the document carries the same exit (`run_cancelled`)."""
    record = _failure_reason(KeyboardInterrupt(), KeyboardInterrupt())
    early = _early(ctx)
    document = _result.build(
        ctx, category="cancelled", reason=record, error_class="KeyboardInterrupt", early=early
    )
    context: dict[str, Any] = {"config": ctx.config_str}
    if record is not None:
        context["reason"] = record.to_payload()
    _result.report_error(ctx, document, "interrupted", context=context, human=False)
