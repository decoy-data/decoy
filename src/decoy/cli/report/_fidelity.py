"""``decoy report fidelity``: distribution fidelity between a source and an output."""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any

import typer

from decoy._config_file import ConfigFileError, config_refusal, load_config_mapping
from decoy._yaml_errors import sanitize_yaml_error
from decoy.cli._sources import (
    ReportSourceError,
    gate_report_source,
    read_report_source,
)
from decoy.cli.exit_codes import EXIT_FINDINGS, EXIT_USAGE, exit_code_for
from decoy.cli.io import pipeline_option, report_dest, resolve_pipeline
from decoy.cli.report._shared import _write_out
from decoy.ui.output import (
    OutputMode,
    emit_error,
    emit_json,
    setup_output,
)
from decoy.ui.summary import (
    null_rate_pairs,
    render_fidelity_report,
)

# Grade -> minimum overall_score, mirroring the engine's own grade thresholds
# (decoy_engine.quality.report._GRADE_THRESHOLDS: A >= 0.95, B >= 0.85,
# C >= 0.70, D >= 0.50). Moved verbatim with the `fidelity` body from
# validate.py (S4b): the engine maps score -> grade but exposes no reverse
# (grade -> score) helper, so `--min-grade` needs its own copy of the table.
_GRADE_MIN_SCORE: dict[str, float] = {"A": 0.95, "B": 0.85, "C": 0.70, "D": 0.50}


_FIDELITY_EPILOG = """\
Examples:

  decoy report fidelity source.csv output.csv
    Recompute distribution fidelity between a pre-mask source and its
    masked output. Report mode (record only): always exits 0.

  decoy report fidelity source.csv output.csv --config pipeline.yaml
    Pass the pipeline config so intentional loss (hash, bucketize, ...)
    is not flagged as accidental drift.

  decoy report fidelity source.csv synthetic.csv --generate
    Row counts are expected to differ (synthetic generation, not masking).

  decoy report fidelity source.csv output.csv --mode fail --min-grade B
    Exit non-zero (EXIT_FINDINGS) when the overall grade falls below B.

  decoy report fidelity source.csv output.csv --joint state,tier --json
    Include a (state, tier) joint fidelity score; emit the full
    quality-report/v1 + policy JSON.

  decoy report fidelity source.csv output.csv --report-out report.json
    Also write the full report + policy verdict to disk.

Exit codes: 0 pass (or warn without --fail-on-warning); 4 EXIT_FINDINGS
when the policy verdict is fail, or warn with --fail-on-warning set;
1 EXIT_USAGE for bad input (missing columns, unreadable CSV, bad flags).

See also: decoy report integrity, decoy fit, decoy run.
"""


def _build_strategy_map(config_dict: dict[str, Any]) -> dict[str, str]:
    """Flatten column -> strategy across every declared table.

    Mirrors the evidence manifest's strategy-summary loop
    (`decoy.cli.evidence.build_manifest`). `report fidelity` checks a single
    source/output CSV pair, not a specific table, so this assumes column names
    are unique across the pipeline's declared tables; a multi-table config
    with a repeated column name lets the last table's strategy win. Acceptable
    for the v1 single source/output scope (D4).
    """
    strategy_map: dict[str, str] = {}
    for table in config_dict.get("tables") or []:
        if not isinstance(table, dict):
            continue
        for col in table.get("columns") or []:
            if isinstance(col, dict) and col.get("name"):
                strategy_map[col["name"]] = col.get("strategy", "")
        for gen_col in table.get("generate_columns") or []:
            if isinstance(gen_col, dict) and gen_col.get("name"):
                strategy_map[gen_col["name"]] = "generate"
    return strategy_map


def _fidelity(
    source: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Pre-mask / pre-generate source CSV (ground truth).",
    ),
    output: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Post-mask / post-generate output CSV to check.",
    ),
    joint: list[str] = typer.Option(
        [],
        "--joint",
        help="Column pair 'a,b' to also score jointly (repeatable).",
    ),
    generate: bool = typer.Option(
        False,
        "--generate",
        help=(
            "Output is synthetic generation, not masking: row counts may "
            "legitimately differ (sets expect_row_parity=False). Default "
            "assumes masking (row parity expected)."
        ),
    ),
    pipeline_config: str | None = pipeline_option(
        None,
        "--config",
        help=(
            "Pipeline file (.yaml or .decoy) naming each column's strategy, so intentional "
            "loss (hash, bucketize, faker, ...) is not flagged as accidental "
            "drift. Without it, per-column policy checks run on defaults only."
        ),
    ),
    policy: Path | None = typer.Option(
        None,
        "--policy",
        exists=True,
        dir_okay=False,
        readable=True,
        help=(
            "A quality-policy config (YAML or JSON: mode / thresholds / "
            "strategy_expectations) overriding --mode / --min-grade / --min-score."
        ),
    ),
    mode: str = typer.Option(
        "report",
        "--mode",
        help=(
            "report (record only, verdict always pass) | warn (violations "
            "promote verdict to warn) | fail (violations promote verdict to "
            "fail). Ignored when --policy sets its own mode."
        ),
    ),
    min_grade: str | None = typer.Option(
        None,
        "--min-grade",
        help=(
            "Shorthand: minimum letter grade (A/B/C/D) the overall score must reach. "
            "Intended columns count in the grade."
        ),
    ),
    min_score: float | None = typer.Option(
        None,
        "--min-score",
        help="Shorthand: minimum overall_score in [0, 1].",
    ),
    fail_on_warning: bool = typer.Option(
        False,
        "--fail-on-warning",
        help="Also exit non-zero (EXIT_FINDINGS) when the policy verdict is 'warn'.",
    ),
    report_out: Path | None = typer.Option(
        None,
        "--report-out",
        help="Write the full quality-report/v1 + policy JSON to this path.",
    ),
    json_: bool = typer.Option(
        False,
        "--json",
        help="Emit the full quality-report/v1 + policy result as JSON.",
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
) -> None:
    """Recompute distribution fidelity between a source and an output CSV.

    The engine owns every metric and the letter grade; this command
    computes no fidelity number itself. It reads both CSVs fresh on every
    run (pure, repeatable). The local evidence manifest records file
    fingerprints but not the raw frames, so recomputing from the two files
    is the only honest source for this number.

    Exit codes: 0 when the policy verdict is 'pass' (or 'warn' without
    --fail-on-warning); EXIT_FINDINGS (4) when the verdict is 'fail', or
    'warn' with --fail-on-warning set. This mirrors `report integrity`'s
    exit-code contract -- a data-audit verb that reports findings, not a run
    that crashed -- rather than EXIT_RUNTIME (reserved for the CLI/engine
    blowing up unexpectedly).
    """
    import yaml as _yaml

    state = setup_output(json_, quiet, verbose)
    ref = resolve_pipeline(pipeline_config, state, "report fidelity")
    pipeline_path = ref.yaml if ref else None
    source_str = str(source)
    output_str = str(output)

    def _emit_error(message: str, *, code: str | None = None) -> None:
        emit_error(
            state,
            "report fidelity",
            message,
            code=code,
            context={"source": source_str, "output": output_str},
        )

    joint_pairs: list[tuple[str, str]] = []
    for spec in joint:
        parts = [p.strip() for p in spec.split(",") if p.strip()]
        if len(parts) != 2:
            _emit_error(f"--joint expects 'colA,colB'; got {spec!r}.")
            raise typer.Exit(code=EXIT_USAGE)
        joint_pairs.append((parts[0], parts[1]))

    if min_grade is not None and min_score is not None:
        _emit_error("specify only one of --min-grade / --min-score, not both.")
        raise typer.Exit(code=EXIT_USAGE)

    if min_grade is not None and min_grade.upper() not in _GRADE_MIN_SCORE:
        _emit_error(f"--min-grade must be one of A, B, C, D; got {min_grade!r}.")
        raise typer.Exit(code=EXIT_USAGE)

    if mode not in ("report", "warn", "fail"):
        _emit_error(f"--mode must be one of report, warn, fail; got {mode!r}.")
        raise typer.Exit(code=EXIT_USAGE)

    config_dict: dict[str, Any] = {}
    if pipeline_path is not None:
        from decoy_engine import parse_pipeline_config

        try:
            raw_cfg = load_config_mapping(pipeline_path)
        except (ConfigFileError, OSError) as exc:
            _emit_error(**config_refusal(exc))
            raise typer.Exit(code=exit_code_for(exc))
        try:
            config_dict = parse_pipeline_config(raw_cfg).model_dump()
        except Exception as exc:
            _emit_error(f"could not parse --config {pipeline_config}: {exc}")
            raise typer.Exit(code=EXIT_USAGE)
    strategy_map = _build_strategy_map(config_dict)

    if policy is not None:
        try:
            policy_config = _yaml.safe_load(policy.read_text(encoding="utf-8")) or {}
        except _yaml.YAMLError as exc:
            _emit_error(sanitize_yaml_error(exc))
            raise typer.Exit(code=EXIT_USAGE)
        except Exception as exc:
            _emit_error(f"could not parse --policy {policy}: {exc}")
            raise typer.Exit(code=EXIT_USAGE)
        if not isinstance(policy_config, dict):
            _emit_error(f"--policy {policy} must be a YAML/JSON mapping.")
            raise typer.Exit(code=EXIT_USAGE)
    else:
        thresholds: dict[str, Any] = {}
        if min_score is not None:
            thresholds["overall"] = {"min": min_score}
        elif min_grade is not None:
            thresholds["overall"] = {"min": _GRADE_MIN_SCORE[min_grade.upper()]}
        policy_config = {"mode": mode, "thresholds": thresholds}

    from decoy_engine.quality import apply_quality_policy, compute_quality_report

    config_dir = pipeline_path.parent if pipeline_path is not None else Path.cwd()
    try:
        table = gate_report_source(config_dict, config_dir, source)
        src_df = read_report_source(source, config_dict, config_dir, table)
    except ReportSourceError as exc:
        _emit_error(exc.message, code=exc.code)
        raise typer.Exit(code=EXIT_USAGE)
    except Exception as exc:
        _emit_error(f"could not read {source}: {type(exc).__name__}.")
        raise typer.Exit(code=EXIT_USAGE)
    try:
        out_df = read_report_source(output, {}, config_dir)
    except Exception as exc:
        _emit_error(f"could not read {output}: {type(exc).__name__}.")
        raise typer.Exit(code=EXIT_USAGE)

    report = compute_quality_report(
        src_df,
        out_df,
        joint_columns=joint_pairs or None,
        expect_row_parity=not generate,
    )
    policy_result = apply_quality_policy(report, policy_config, strategy_map=strategy_map)

    text = _json.dumps({**report, "policy": policy_result}, indent=2)
    written = _write_out(state, report_dest("fidelity", output, ref, report_out), text)

    verdict = policy_result["verdict"]
    status = "ok" if verdict == "pass" else verdict

    if state.mode is OutputMode.json:
        envelope = dict(report)
        envelope["command"] = "report fidelity"
        envelope["status"] = status
        envelope.update(policy=policy_result, **({"report_path": str(written)} if written else {}))
        emit_json(state, envelope)
    elif state.mode is not OutputMode.quiet:
        render_fidelity_report(
            state, report, policy_result, null_rates=null_rate_pairs(report, src_df, out_df)
        )

    if verdict == "fail" or (verdict == "warn" and fail_on_warning):
        raise typer.Exit(code=EXIT_FINDINGS)
