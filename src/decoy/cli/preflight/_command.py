"""The `decoy validate preflight` command: step order and exits."""

from __future__ import annotations

import typer

from decoy._config_file import ConfigFileError, config_refusal, load_config_mapping
from decoy.cli.exit_codes import EXIT_CAPACITY, EXIT_USAGE, EXIT_WARNINGS, exit_code_for
from decoy.cli.io import pipeline_argument, resolve_pipeline
from decoy.cli.preflight import readiness
from decoy.cli.preflight._render import _emit_preflight_result
from decoy.cli.preflight._result import _PreflightAccumulator
from decoy.ui.output import setup_output

_PREFLIGHT_EPILOG = """\
Examples:

  decoy validate preflight pipeline.yaml
    Run local readiness checks: YAML validity, schema, and source file existence.

  decoy validate preflight pipeline.yaml --local
    Same as above (--local is the explicit form; all checks are local by default).

  decoy validate preflight pipeline.yaml --json
    Emit a structured JSON result with per-check findings.

  decoy validate preflight pipeline.yaml --fail-on-warning
    Exit non-zero when advisory warnings fire (e.g. output already exists).

What preflight checks:
  - YAML syntax and schema (same as `decoy validate`)
  - Source file existence and readability
  - Target overwrite risk (advisory warning)
  - Out-of-core-FK memory capacity (v1; build-floor is advisory, a fan-in
    impossibility exits EXIT_CAPACITY -- see: decoy explain exit-codes)
  - Generated tables whose output cannot fit memory (exit EXIT_CAPACITY)
  - Native companion health, plus a STATIC (config-shape-only) native
    eligibility possibility -- see: decoy explain native

What preflight does NOT check:
  - Platform server-side conditions (secrets, RBAC, schedules, network targets)
  - Engine run-time constraints beyond out-of-core-FK capacity (row counts,
    provider limits)
  - The ingestion peak `decoy run` pays before the engine's capacity gate runs
    (out of the v1 capacity check's scope)
  - Data validity or masking quality
  - Vault or secrets accessibility

See also: decoy validate, decoy run, decoy report verify, decoy explain exit-codes.
"""


def preflight(
    config: str = pipeline_argument(help="Pipeline file (.yaml or .decoy), or its name, to check."),
    local: bool = typer.Option(
        False,
        "--local",
        help=(
            "Explicit local mode (all checks are local by default; "
            "this flag makes the intent explicit in scripts)."
        ),
    ),
    json_: bool = typer.Option(
        False,
        "--json",
        help="Emit a structured JSON result on stdout.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress stdout. Errors still go to stderr; exit code carries the result.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug-level CLI logs on stderr.",
    ),
    fail_on_warning: bool = typer.Option(
        False,
        "--fail-on-warning",
        help="Exit non-zero when any advisory warning fires.",
    ),
) -> None:
    """Local pre-run readiness checks for a pipeline config.

    Checks file existence, file readability, YAML syntax, schema validity,
    and (v1) the engine's out-of-core-FK memory feasibility. The build-floor
    estimate is advisory: an over-budget prediction reports a WARNING with a
    recommended size, not a refusal (`--fail-on-warning` makes it exit
    nonzero). A fan-in impossibility, and generated tables whose output
    cannot fit the machine's memory, exit EXIT_CAPACITY (see `decoy explain
    exit-codes`), distinct from a config problem (EXIT_USAGE). Reports
    findings as pass/warn/fail with structured output available via --json.

    This is a LOCAL check only. It does NOT check platform server-side
    conditions, most engine run-time constraints, data quality, vault
    access, secrets availability, or network connectivity. The capacity
    check does not cover the ingestion peak `decoy run` pays before the
    engine's gate runs. Use `decoy validate` for pure schema-only checks; use
    this command when you want to confirm source files are present and check
    the job's capacity feasibility before starting a run.
    """
    state = setup_output(json_, quiet, verbose)
    config_path = resolve_pipeline(config, state, "validate preflight").yaml
    config_str = str(config)
    acc = _PreflightAccumulator()

    from decoy_engine import (
        ConfigError,
        PipelineValidationError,
        parse_pipeline_config,
        run_config_only_checks,
    )
    from decoy_engine.config import PipelineConfigError
    from decoy_engine.plan import PlanCompileError

    # -- Step 1: YAML parse ---------------------------------------------------
    try:
        raw = load_config_mapping(config_path)
    except (ConfigFileError, OSError) as exc:
        message, reason = config_refusal(exc).values()  # reason is None for an OSError
        acc.add_fail(name=reason or "config.unreadable", message=str(message))
        _emit_preflight_result(state, acc, config_str, fail_on_warning)
        raise typer.Exit(code=exit_code_for(exc))

    acc.add_pass(name="yaml.syntax", message="Pipeline syntax is valid.")

    # -- Step 2: Schema validation --------------------------------------------
    try:
        parse_pipeline_config(raw)
        acc.add_pass(name="schema.valid", message="Pipeline schema is valid.")
    except PipelineConfigError as exc:
        for problem in exc.problems:
            acc.add_fail(
                name="schema.field",
                message=problem.text,
                location=problem.location or None,
            )
        _emit_preflight_result(state, acc, config_str, fail_on_warning)
        raise typer.Exit(code=EXIT_USAGE)
    except (PipelineValidationError, ConfigError) as exc:
        acc.add_fail(name="schema.validation_error", message=str(exc))
        _emit_preflight_result(state, acc, config_str, fail_on_warning)
        raise typer.Exit(code=EXIT_USAGE)

    # -- Step 3: Profile-free plan-compile checks ----------------------------
    try:
        run_config_only_checks(raw, base_dir=config_path.parent)
        acc.add_pass(name="config.plan_checks", message="Profile-free plan-compile checks passed.")
    except PlanCompileError as exc:
        # Rewrite ner_spacy_not_installed to decoy-cli's own [ner] extra;
        # see plan_compile_error_fields's docstring for why every
        # PlanCompileError display site goes through it.
        from decoy.cli.extras import plan_compile_error_fields

        code, message = plan_compile_error_fields(exc)
        acc.add_fail(name=f"config.{code}", message=message)
        _emit_preflight_result(state, acc, config_str, fail_on_warning)
        raise typer.Exit(code=EXIT_USAGE)

    # -- Step 3b: Project-layout checks --------------------------------------
    from decoy.cli.io import layout_failures

    for code, message, location in layout_failures(config_path, raw):
        acc.add_fail(name=code, message=message, location=location, code=code)
    if acc.has_failures:
        _emit_preflight_result(state, acc, config_str, fail_on_warning)
        raise typer.Exit(code=EXIT_USAGE)

    # -- Step 4: Source file checks ------------------------------------------
    readiness._check_source_files(raw, config_path.parent, acc)

    # -- Step 5: Target overwrite advisory -----------------------------------
    readiness._check_target_overwrite(raw, acc, config_path.parent)

    # -- Step 6: Capacity check (OOM checker v1) -----------------------------
    readiness._check_capacity(raw, config_path, acc)

    # -- Step 7: Native companion health + static eligibility (Phase 3.1) ----
    readiness._check_native(raw, acc)

    # -- Emit and exit --------------------------------------------------------
    _emit_preflight_result(state, acc, config_str, fail_on_warning)

    # T7: INSUFFICIENT capacity exits EXIT_CAPACITY, checked BEFORE the
    # generic has_failures path so it is never masked as a plain EXIT_USAGE
    # config problem -- a distinct, machine-detectable "needs more memory"
    # result up front, before a run starts.
    if acc.capacity_insufficient:
        raise typer.Exit(code=EXIT_CAPACITY)
    if acc.has_failures:
        raise typer.Exit(code=EXIT_USAGE)
    if fail_on_warning and acc.has_warnings:
        raise typer.Exit(code=EXIT_WARNINGS)


PREFLIGHT_EPILOG = _PREFLIGHT_EPILOG
