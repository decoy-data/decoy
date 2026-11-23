"""`decoy demo` -- 30-second end-to-end walkthrough on bundled sample data.

Default flow: a small single-table CSV, scanned -> masked via the V2
PipelineConfig spine. All artifacts land in `./decoy_demo/`. The legacy
FORECAST recommender step was removed in the V1 scan rework; do not
re-introduce.
"""

from __future__ import annotations

from pathlib import Path

import typer

from decoy.cli._sources import (
    csv_file_source,
    read_source,
    refusal_message,
    resolved_source_config,
)
from decoy.cli.exit_codes import EXIT_RUNTIME, EXIT_USAGE
from decoy.cli.io import RunLayout, prepared_sources
from decoy.cli.io._targets import check_target_formats, write_targets
from decoy.ui.card import render_card
from decoy.ui.output import (
    OutputMode,
    OutputState,
    emit_error,
    emit_json,
    print_traceback,
    setup_output,
)
from decoy.ui.theme import accent, error, hint, success

_DEMO_EPILOG = """\
Examples:

  decoy demo
    Run the simple scan -> mask walkthrough in ./decoy_demo/.

  decoy demo --json
    Same flow, but emit a JSON summary instead of cards.

See also: decoy scan, decoy run.
"""


# ---------------------------------------------------------------------------
# Single-table demo (default)
# ---------------------------------------------------------------------------


def _write_sample_csv(path: Path) -> None:
    rows = [
        ("customer_id", "first_name", "last_name", "email", "ssn", "dob", "zip", "gender"),
        (
            "C001",
            "Alice",
            "Anderson",
            "alice@example.com",
            "111-22-3333",
            "1990-01-15",
            "10001",
            "F",
        ),
        ("C002", "Bob", "Brown", "bob@example.com", "222-33-4444", "1985-05-20", "90210", "M"),
        ("C003", "Carol", "Carter", "carol@example.com", "333-44-5555", "1992-08-30", "60601", "F"),
        ("C004", "David", "Davis", "david@example.com", "444-55-6666", "1988-11-04", "77001", "M"),
        ("C005", "Eve", "Evans", "eve@example.com", "555-66-7777", "2000-02-14", "94016", "F"),
        ("C006", "Frank", "Foster", "frank@example.com", "666-77-8888", "1979-09-09", "30301", "M"),
        ("C007", "Grace", "Green", "grace@example.com", "777-88-9999", "1995-12-25", "10001", "F"),
        ("C008", "Henry", "Harris", "henry@example.com", "888-99-0000", "1983-06-18", "20001", "M"),
        ("C009", "Iris", "Ingram", "iris@example.com", "999-00-1111", "1997-03-22", "33101", "F"),
        ("C010", "Jack", "Johnson", "jack@example.com", "000-11-2222", "1991-07-11", "75201", "M"),
    ]
    path.write_text("\n".join(",".join(r) for r in rows) + "\n", encoding="utf-8")


def _build_pipeline_yaml(input_path: Path, output_path: Path) -> str:
    """V2 PipelineConfig shape per decoy-engine `decoy_engine.config._pipeline`.

    Provider names come from the engine's default registry. customer_id
    rides the deterministic envelope (deterministic + namespace) so a
    future multi-table demo can re-join on it; deterministic faker
    output is the V2-equivalent of the V1 'hash for FK join' trick the
    original demo used.

    CLI QA fix (2026-06-02, F6): build a dict and serialize via
    yaml.safe_dump rather than f-string templating. Pre-fix a single
    quote in a path (e.g. --dir "O'Hare_demo") produced un-escaped YAML
    that yaml.safe_load then rejected with a ScannerError, surfacing as
    a confusing crash. safe_dump quotes path strings correctly.
    """
    import yaml as _yaml

    cfg = {
        "version": 2,
        "global_settings": {"seed": 42},
        "sources": {
            "customers": csv_file_source(input_path),
        },
        "tables": [
            {
                "name": "customers",
                "columns": [
                    {"name": "customer_id", "strategy": "redact"},
                    {"name": "first_name", "strategy": "faker", "provider": "person_first_name"},
                    {"name": "last_name", "strategy": "faker", "provider": "person_last_name"},
                    {"name": "email", "strategy": "faker", "provider": "person_email"},
                    {"name": "ssn", "strategy": "redact"},
                    {"name": "dob", "strategy": "redact"},
                    {"name": "zip", "strategy": "redact"},
                    {"name": "gender", "strategy": "passthrough"},
                ],
            },
        ],
        "targets": {
            "customers": {
                "type": "file",
                "format": "csv",
                "path": str(output_path),
            },
        },
    }
    return _yaml.safe_dump(cfg, default_flow_style=False, sort_keys=False)


def _run_single_demo(state: OutputState, out_dir: Path) -> int:
    """V2 one-CSV walkthrough.

    CLI.3 commit 2 (2026-06-02): rewritten against the V2 spine.
    Pre-rewrite the demo called `recommend` (FORECAST, retired in
    the V1 scan rework) and `Masker(...).mask()` (V1 surface deleted with
    the V1 graph runner). The new walkthrough: write a sample CSV ->
    scan -> V2 PipelineConfig validate -> compile_plan ->
    select_execution_adapter().run(...) -> write masked output.
    The FORECAST step is dropped (no V2 successor); the scan
    still surfaces PII counts so the operator gets the same gut-check
    on what the engine saw in their data.
    """
    sample_csv = out_dir / "customers.csv"
    masked_csv = out_dir / "customers_masked.csv"
    pipeline_yaml = out_dir / "pipeline.yaml"
    scan_json = out_dir / "scan.json"

    if state.mode is OutputMode.default:
        state.console.print(accent("[1/3]"), "Writing sample dataset...")
    _write_sample_csv(sample_csv)

    if state.mode is OutputMode.default:
        state.console.print(accent("[2/3]"), "Scanning...")
    from decoy.cli._sources import csv_file_source, scan_prepared_sources
    from decoy.cli.scanning import core_bytes, scan_descriptors, table_name_from_path

    # The shape `decoy scan --output` saves: the value-free `scan-set/v1` core.
    descriptors = {
        table_name_from_path(sample_csv): csv_file_source(sample_csv.resolve(), has_header=True)
    }
    prepared = scan_prepared_sources({"sources": descriptors}, base_dir=out_dir)
    run = scan_descriptors(prepared, rows=None, strategy="full")
    core = run.core
    scan_json.write_text(core_bytes(core).decode("utf-8"))
    scanned = core["tables"][0]

    if state.mode is OutputMode.default:
        state.console.print(accent("[3/3]"), "Running V2 masking pipeline...")
    pipeline_yaml.write_text(_build_pipeline_yaml(sample_csv, masked_csv))
    _run_v2_mask(pipeline_yaml)

    pii_columns = sum(1 for f in scanned["fields"] if f["pii_candidate"])

    if state.mode is OutputMode.json:
        emit_json(
            state,
            {
                "command": "demo",
                "variant": "single",
                "status": "ok",
                "dir": str(out_dir),
                "scan": str(scan_json),
                "masked": str(masked_csv),
                "pii_columns": pii_columns,
            },
        )
        return 0

    if state.mode is OutputMode.quiet:
        return 0

    state.console.print()
    render_card(
        state,
        command="decoy demo",
        facts=[
            ("Sample dataset", str(sample_csv)),
            ("Rows scanned", str(run.result.tables[0].row_count)),
            ("PII columns", f"{pii_columns} of {len(scanned['fields'])}"),
            ("Masked output", str(masked_csv)),
        ],
        next_hint=f"head {masked_csv}",
        status="ok",
    )
    state.console.print(success("OK"), "demo complete.")
    return 0


def _run_v2_mask(pipeline_yaml: Path) -> None:
    """Execute a V2-shape mask pipeline end-to-end.

    Mirrors `decoy run`'s V2 dispatch (cli/run.py) inline: validate ->
    profile_source -> compile_plan -> build_namespace_registry ->
    check_orphan_fk_policy_completeness + build_relationship_graph (if
    relationships) -> select_execution_adapter().run(...) -> write the
    masked output to the declared target path. Per best-practices §3.3
    the demo composes the engine calls itself; extracting a shared
    helper would couple two callers prematurely.
    """
    import yaml as _yaml
    from decoy_engine import (
        __version__ as engine_version,
    )
    from decoy_engine import (
        compile_plan,
        get_default_registry,
        parse_pipeline_config,
        select_execution_adapter,
    )
    from decoy_engine.contracts.column_shape import NO_SOURCES
    from decoy_engine.profile import profile_source
    from decoy_engine.relationships import (
        RelationshipGraph,
        build_namespace_registry,
        build_relationship_graph,
        check_orphan_fk_policy_completeness,
    )

    text = pipeline_yaml.read_text(encoding="utf-8")
    raw = _yaml.safe_load(text)
    config_dict = parse_pipeline_config(raw).model_dump()

    # Before profiling, which is the first reader of a data row.
    prepared_sources(config_dict, base_dir=pipeline_yaml.parent)
    job_seed = (config_dict.get("global_settings") or {}).get("seed")
    profile = profile_source(
        resolved_source_config(config_dict, pipeline_yaml.parent),
        seed=job_seed if isinstance(job_seed, int) else None,
    )
    plan = compile_plan(
        config_dict,
        profile,
        decoy_engine_version=engine_version,
        base_dir=pipeline_yaml.parent,
        sources=NO_SOURCES,
    )
    ns_registry = build_namespace_registry(config_dict, profile)
    if profile.relationships:
        lookup = check_orphan_fk_policy_completeness(config_dict, profile.relationships)
        graph = build_relationship_graph(
            profile.relationships,
            namespace_registry=ns_registry,
            orphan_policy_lookup=lookup,
        )
    else:
        graph = RelationshipGraph(edges=(), ordering=())

    sources = _load_sources_from_config(config_dict, pipeline_yaml.parent)
    adapter = select_execution_adapter()
    result = adapter.run(
        plan,
        sources,
        registry=get_default_registry(),
        relationship_graph=graph,
        namespace_registry=ns_registry,
    )
    _write_mask_outputs(config_dict, result, RunLayout.fixed(pipeline_yaml.parent))


def _load_sources_from_config(config_dict: dict, base_dir: Path) -> dict:
    import pyarrow as pa

    prepared_sources(config_dict, base_dir=base_dir)
    out: dict[str, pa.Table] = {}
    sources = config_dict.get("sources") or {}
    if not isinstance(sources, dict):
        return out
    for table_name, src in sources.items():
        if not isinstance(src, dict) or not isinstance(src.get("path"), str):
            continue
        out[table_name] = read_source(table_name, src, base_dir)
    return out


def _write_mask_outputs(config_dict: dict, result, layout: RunLayout) -> None:
    """Write each declared target by its declared format, through the shared writer.
    The engine `ExecutionResult` carries masked tables on `outputs`
    (dict[table_name -> pa.Table]); not `tables`."""
    check_target_formats(config_dict, chunked=False)
    outputs = getattr(result, "outputs", None)
    if not isinstance(outputs, dict):
        return
    write_targets(config_dict, outputs, layout)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def _demo(
    out_dir: Path = typer.Option(
        Path("decoy_demo"),
        "--dir",
        help="Where to drop the demo artifacts.",
    ),
    json_: bool = typer.Option(False, "--json", help="Emit a JSON summary instead of cards."),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress stdout. Errors still go to stderr."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug-level CLI logs on stderr."
    ),
) -> None:
    """Walk through scan -> mask on a bundled sample dataset.

    Use this on a fresh install to see what Decoy can do end to end without
    needing your own data or pipeline. All output lands in `./decoy_demo/`
    (override with `--dir`).
    """
    state = setup_output(json_, quiet, verbose)

    out_dir.mkdir(parents=True, exist_ok=True)
    # Resolve to absolute up front. Pre-fix the relative `out_dir` (e.g.
    # `decoy_demo`) flowed into `_build_pipeline_yaml`, which wrote
    # `decoy_demo/customers.csv` into the pipeline YAML. Then
    # `_run_v2_mask` re-resolved that relative path against
    # `pipeline_yaml.parent` (which is `decoy_demo` again), producing
    # `decoy_demo/decoy_demo/customers.csv` and a FileNotFoundError.
    # Dennis launch-readiness audit (2026-06-02) BLOCKER finding.
    out_dir = out_dir.resolve()

    try:
        exit_code = _run_single_demo(state, out_dir)
    except typer.Exit:
        # CLI QA fix (2026-06-02, F7): preserve inner typer.Exit codes.
        raise
    except Exception as exc:
        # Audit H10 (2026-06-12): dispatch on exception type so scripts
        # can tell "your config is wrong" (EXIT_USAGE, per the
        # exit_codes.py contract) from "the run blew up" (EXIT_RUNTIME).
        from decoy_engine import ConfigError, PipelineValidationError
        from decoy_engine.plan import PlanCompileError

        if isinstance(exc, PipelineValidationError):
            # A declared-source refusal: the one emitter, code once (r12.3).
            emit_error(
                state,
                "demo",
                refusal_message(exc),
                code=exc.code,
                hint="rerun with --verbose for the full traceback.",
            )
            if state.verbose:
                print_traceback(state)
            raise typer.Exit(code=EXIT_USAGE)
        _exit_code = (
            EXIT_USAGE
            if isinstance(exc, (PlanCompileError, PipelineValidationError, ConfigError))
            else EXIT_RUNTIME
        )
        # CLI QA fix (2026-06-02, F8): truncate the error message at
        # 500 chars before emitting through --json.
        error_text = str(exc)
        if len(error_text) > 500:
            error_text = error_text[:500] + "..."
        if state.mode is OutputMode.json:
            emit_json(
                state,
                {"command": "demo", "status": "error", "error": error_text},
            )
        elif state.mode is not OutputMode.quiet:
            state.err_console.print(error("error:"), error_text)
            state.err_console.print(
                " ", hint("hint:"), "rerun with --verbose for the full traceback."
            )
        if state.verbose:
            print_traceback(state)
        raise typer.Exit(code=_exit_code)

    if exit_code != 0:
        raise typer.Exit(code=exit_code)


_demo.__doc__ = _demo.__doc__
DEMO_EPILOG = _DEMO_EPILOG
