"""``decoy report integrity``: post-mask checks of a masked file against its source."""

from __future__ import annotations

import json as _json
from pathlib import Path

import typer

from decoy._config_file import ConfigFileError, config_refusal
from decoy._yaml_errors import sanitize_yaml_error
from decoy.cli._sources import (
    ReportSourceError,
    gate_report_source,
    read_report_source,
)
from decoy.cli.exit_codes import EXIT_FINDINGS, EXIT_RUNTIME, EXIT_USAGE, exit_code_for
from decoy.cli.io import pipeline_option, report_dest, resolve_pipeline
from decoy.cli.report._shared import _write_out
from decoy.ui.output import (
    OutputMode,
    emit_error,
    emit_json,
    print_traceback,
    setup_output,
)
from decoy.ui.summary import (
    render_residual_pii,
)
from decoy.ui.theme import error, hint, risk_high, success

_INTEGRITY_EPILOG = """\
Examples:

  decoy report integrity masked.csv --source source.csv
    Run all three post-mask checks (residual_pii + fk_preservation +
    policy_validation) against a masked file with its pre-mask
    baseline as ground truth. Render a Rich findings table.

  decoy report integrity masked.csv --source source.csv --config pipeline.yaml
    Same, but load the pipeline YAML so policy_validation can
    compare against the configured masks. Without --config the
    runner still produces residual_pii findings; policy_validation
    is reduced to "no config provided" notes.

  decoy report integrity masked.csv --source source.csv --json > report.json
    Pipe the full integrity report JSON for downstream tooling.

  decoy report integrity masked.csv --source source.csv --output report.json
    Write JSON to file + render a Rich summary on stderr.

Exit codes: 0 clean (no fail/error findings); 4 EXIT_FINDINGS (one
or more fail-severity findings); 1 EXIT_USAGE for missing files;
3 EXIT_RUNTIME for unexpected exceptions.

See also: decoy report verify, decoy report fidelity, decoy explain exit-codes.
"""


def _integrity(
    masked: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Path to the masked CSV to verify.",
    ),
    source: Path = typer.Option(
        ...,
        "--source",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Pre-mask source CSV (ground truth for the integrity check).",
    ),
    config: str | None = pipeline_option(
        None,
        "--config",
        help=(
            "Optional pipeline file (.yaml or .decoy), or a pipeline name. When passed, "
            "policy_validation can compare against the configured masks. Without it the runner "
            "still produces residual_pii + fk_preservation findings."
        ),
    ),
    out: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help=(
            "Write the integrity report JSON to this path. The Rich table still renders to stderr."
        ),
    ),
    allow_source_mismatch: bool = typer.Option(
        False,
        "--allow-source-mismatch",
        help=(
            "Suppress the stderr warning when --source does not match "
            "the pipeline's declared sources block."
        ),
    ),
    json_: bool = typer.Option(
        False,
        "--json",
        help="Emit the full integrity report JSON to stdout. No card.",
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress stdout. Errors still go to stderr."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug-level CLI logs on stderr."
    ),
) -> None:
    """Verify a masked file's integrity against its pre-mask source.

    Runs the three post-mask check buckets (residual_pii, fk_preservation,
    policy_validation) that `post_scan: {integrity: true}` runs inside a
    pipeline; this verb runs the same checks standalone.

    Distinct from `report verify` (manifest fingerprint-drift): integrity is
    post-mask residual-PII / FK / policy on a masked file plus --source.

    Exit codes: 0 clean; 4 EXIT_FINDINGS on any fail-severity finding;
    1 EXIT_USAGE for missing files; 3 EXIT_RUNTIME for unexpected
    exceptions.
    """
    from decoy.ui.table import make_table

    state = setup_output(json_, quiet, verbose)
    ref = resolve_pipeline(config, state, "report integrity")
    config_path = ref.yaml if ref else None
    masked_str = str(masked)
    source_str = str(source)
    members = {"masked": masked_str, "source": source_str}

    try:
        from decoy_engine.verification.postmask import run_post_mask

        from decoy.cli.io import bare_report_config, read_report_config, report_detectors

        table_name: str
        config_sha: str | None = None
        if config_path is not None:
            from decoy_engine import parse_pipeline_config

            try:
                raw, config_sha = read_report_config(config_path)
            except (ConfigFileError, OSError) as exc:
                emit_error(state, "report integrity", context=members, **config_refusal(exc))
                raise typer.Exit(code=exit_code_for(exc))
            except ValueError as exc:
                # A tag constructor (`!!int x`) raises ValueError, not YAMLError, and its
                # text quotes the scalar. sanitize_yaml_error reads only the error mark.
                emit_error(state, "report integrity", sanitize_yaml_error(exc), context=members)
                raise typer.Exit(code=EXIT_RUNTIME)
            config_dict = parse_pipeline_config(raw).model_dump()
            # One source/masked pair: anchor on the first declared table.
            tables = config_dict.get("tables") or []
            table_name = tables[0]["name"] if tables else masked.stem
            declared_sources = config_dict.get("sources") or {}
            declared_path = None
            if table_name in declared_sources:
                declared_path = declared_sources[table_name].get("path")
            if (
                declared_path
                and not allow_source_mismatch
                and Path(declared_path).resolve() != source.resolve()
            ):
                state.err_console.print(
                    hint("warning:"),
                    f"--source {source_str} does not match pipeline "
                    f"input.path {declared_path}; proceeding with --source "
                    "as ground truth (suppress with --allow-source-mismatch).",
                )
        else:
            # No config: a minimal dict; the runner's branches degrade when it is bare.
            table_name, config_dict = masked.stem, bare_report_config()

        source_dir = config_path.parent if config_path else Path.cwd()
        try:
            gated = gate_report_source(config_dict, source_dir, source, table_name)
        except ReportSourceError as exc:
            emit_error(state, "report integrity", exc.message, code=exc.code, context=members)
            raise typer.Exit(code=EXIT_USAGE)
        detectors = report_detectors(state, config_dict, members)  # before either CSV is read
        source_df = read_report_source(source, config_dict, source_dir, gated)
        masked_df = read_report_source(masked, {}, Path.cwd())

        report = run_post_mask(
            source_frames={table_name: source_df},
            output_frames={table_name: masked_df},
            config=config_dict,
            detectors=detectors,
        )
        report["config_sha256"] = config_sha

        target = report_dest("integrity", masked, ref, out)
        written = _write_out(state, target, _json.dumps(report, indent=2))

        # Decide exit code based on the report's severity counters.
        fail_count = int(report.get("fail_count") or 0)
        error_count = int(report.get("error_count") or 0)
        exit_code = EXIT_FINDINGS if (fail_count + error_count) > 0 else 0

        if state.mode is OutputMode.json:
            emit_json(
                state,
                {
                    "command": "report integrity",
                    "status": "ok" if exit_code == 0 else "findings",
                    "masked": masked_str,
                    "source": source_str,
                    "report": report,
                    **({"report_path": str(written)} if written else {}),
                },
            )
        elif state.mode is not OutputMode.quiet:
            # A 3-row summary, then the residual-PII rows. FK and policy findings
            # are other record types and stay in the JSON payload only.
            table = make_table("Bucket", "Findings", "Severities", title="Post-scan integrity")
            for bucket in ("residual_pii", "fk_preservation", "policy_validation"):
                findings = report.get(bucket) or []
                if not findings:
                    table.add_row(bucket, "0", success("clean"))
                    continue
                sevs: dict[str, int] = {}
                for f in findings:
                    sev = (f.get("severity") if isinstance(f, dict) else None) or "info"
                    sevs[sev] = sevs.get(sev, 0) + 1
                sev_text = ", ".join(f"{k}:{v}" for k, v in sorted(sevs.items()))
                table.add_row(bucket, str(len(findings)), sev_text)
            state.console.print(table)
            render_residual_pii(state, report.get("residual_pii") or [])
            counters = (
                f"pass={report.get('pass_count', 0)}  "
                f"warning={report.get('warning_count', 0)}  "
                f"fail={fail_count}  "
                f"error={error_count}"
            )
            state.console.print(counters)
            if exit_code == 0:
                state.console.print(success("OK"), "no fail or error findings.")
            else:
                state.console.print(
                    risk_high("FINDINGS"),
                    f"{fail_count + error_count} fail/error findings; review the report.",
                )

        if exit_code != 0:
            raise typer.Exit(code=exit_code)

    except typer.Exit:
        raise
    except FileNotFoundError as exc:
        if state.mode is OutputMode.json:
            emit_json(
                state,
                {
                    "command": "report integrity",
                    "status": "error",
                    "masked": masked_str,
                    "source": source_str,
                    "error": str(exc),
                },
            )
        elif state.mode is not OutputMode.quiet:
            state.err_console.print(error("error:"), str(exc))
        raise typer.Exit(code=EXIT_USAGE)
    except Exception as exc:
        error_text = str(exc)
        if len(error_text) > 500:
            error_text = error_text[:500] + "..."
        if state.mode is OutputMode.json:
            emit_json(
                state,
                {
                    "command": "report integrity",
                    "status": "error",
                    "masked": masked_str,
                    "source": source_str,
                    "error": error_text,
                },
            )
        elif state.mode is not OutputMode.quiet:
            state.err_console.print(error("error:"), error_text)
            state.err_console.print(
                " ",
                hint("hint:"),
                "rerun with --verbose for the full traceback.",
            )
        if state.verbose:
            print_traceback(state)
        raise typer.Exit(code=EXIT_RUNTIME)
