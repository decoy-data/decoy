"""The `decoy fit` command flow: read, fit, refuse, write, report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from decoy._atomic import AtomicWriteError, WriteMode, describe, write_local_target
from decoy._resources import ResourceError, read_fit_max_rows
from decoy.cli.exit_codes import EXIT_RUNTIME, EXIT_USAGE, exit_code_for
from decoy.cli.fit._args import (
    _build_column_schema,
    _build_typed_frame,
    _FitUsageError,
    _parse_rows,
)
from decoy.cli.gen import (
    FIT_SAMPLE_SEED,
    FitSourceError,
    fit_exact_snapshot,
    read_fit_csv,
    strict_csv,
)
from decoy.cli.io import side_file_default
from decoy.ui.output import OutputMode, emit_error, emit_json, setup_output
from decoy.ui.theme import code, hint, success, warn

_DP_REFUSED_LINE = (
    "DP fit is not available on this install: it runs only on a certified platform and package set."
)
_DP_REFUSED_HINT = (
    "run decoy fit without --epsilon for an exact snapshot (add --include-values to "
    "sample sensitive columns as categories; the file then holds real data). A DP "
    "release needs a certified install; see decoy explain differential-privacy."
)

_FIT_EPILOG = """\
Examples:

  decoy fit customers.csv
    Write customers.snapshot.json next to the source.

  decoy fit customers.csv --output snapshot.json --parse-dates signup_date
    Treat signup_date as a datetime column.

  decoy fit customers.csv --joint state,tier
    Capture the (state, tier) contingency table so a statistical column
    can use `condition_on`.

  decoy fit customers.csv --joint state,tier --joint-max-cells 100
    Keep up to 100 (state, tier) combinations instead of 25. When the
    cap drops combinations, fit warns on stderr and in --json. Without
    --include-values a raised cap needs both columns to be plain
    categories.

  decoy fit customers.csv --rows 100000
    Fit on a seeded random sample of 100,000 rows spread across the whole
    file (never the first 100,000). Without --rows the limit is the
    `fit.max_rows` setting in settings.json, default 1,000,000. A file at
    or under the limit uses every row. The summary and --json say how many
    rows were used out of how many.

  decoy fit visits.csv --fanout patient_id
    Record how many visits each patient_id has (counts only). A reference
    column with `distribution: fitted` and this snapshot then gives each
    generated patient a visit count drawn from that shape. Not supported
    with --epsilon.

  decoy fit customers.csv --epsilon 1.0 --delta 1e-6 \\
      --dp-number amount:0:500 --dp-text state --dp-flag is_active
    Differentially private release (dps-marginal/v3), certified installs
    only (see decoy explain differential-privacy): every declared
    column is released under one (epsilon, delta) budget through OpenDP.
    Every column MUST be declared with a carrier (--dp-number for a
    numeric column plus its data-independent domain, --dp-text for a
    categorical column, --dp-flag for a boolean column); an undeclared
    source column is a usage error unless --dp-allow-omit is passed.
    --epsilon requires --delta and is incompatible with --joint and
    --parse-dates. A DP fit never samples: it uses every row, ignores the
    `fit.max_rows` setting, and refuses --rows.

See also: decoy run, decoy validate, decoy explain differential-privacy.
"""


def fit(
    source: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="Source CSV to fit the distribution snapshot from.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Where to write the snapshot JSON. Default: <source>.snapshot.json.",
    ),
    parse_dates: list[str] = typer.Option(
        [],
        "--parse-dates",
        help="Column(s) to parse as datetimes (repeatable). CSV carries no dtype, so date columns must be named explicitly. Not supported with --epsilon.",
    ),
    joint: list[str] = typer.Option(
        [],
        "--joint",
        help="Column pair 'a,b' whose contingency table to capture (repeatable). Needed for `condition_on`. Not supported with --epsilon.",
    ),
    joint_max_cells: str | None = typer.Option(
        None,
        "--joint-max-cells",
        metavar="N",
        help=(
            "Keep up to N combinations per --joint pair (default 25, at most 1000); the "
            "rest fall into one count. Rare combinations can point at one person, so "
            "without --include-values a raised cap works only on pairs of plain "
            "categorical columns. Needs --joint."
        ),
    ),
    rows: str | None = typer.Option(
        None,
        "--rows",
        metavar="N",
        help=(
            "Fit on at most N rows. A larger file is cut to a random sample of N rows "
            f"spread across the whole file, never the first N (fixed seed {FIT_SAMPLE_SEED}: "
            "the same file gives the same sample). Sensitive-column detection and the "
            "snapshot use the same sampled rows. Default: the fit.max_rows setting in "
            "settings.json, else 1000000. A whole number of 1 or more. Not supported "
            "with --epsilon (a DP fit uses every row and ignores the setting)."
        ),
    ),
    epsilon: float = typer.Option(
        None,
        "--epsilon",
        help=(
            "Select DP mode: fit a dps-marginal/v3 artifact via the engine's "
            "fit_dp_snapshot instead of the exact snapshot. Requires --delta and "
            "at least one carrier declaration (--dp-number/--dp-flag/--dp-text). "
            "This is the ONLY DP-mode selector -- every DP-only option is a usage "
            "error without it, so a forgotten --epsilon never silently falls back "
            "to the exact release. Runs only on a certified DP install; see "
            "decoy explain differential-privacy."
        ),
    ),
    delta: float = typer.Option(
        None,
        "--delta",
        help="DP failure probability, required with --epsilon (no default: a silent delta would set an unchosen privacy level). Finite, in (0, 1).",
    ),
    dp_number: list[str] = typer.Option(
        [],
        "--dp-number",
        help="'COL:LO:HI' -- declare COL as a DP numeric carrier with a data-independent domain (repeatable). Requires --epsilon.",
    ),
    dp_flag: list[str] = typer.Option(
        [],
        "--dp-flag",
        help="Declare COL as a DP boolean/flag carrier (repeatable). Requires --epsilon.",
    ),
    dp_text: list[str] = typer.Option(
        [],
        "--dp-text",
        help="Declare COL as a DP categorical text carrier (repeatable). Requires --epsilon.",
    ),
    numeric_bins: int = typer.Option(
        None,
        "--numeric-bins",
        help="Bins per number column, 2 to 1000 (engine default if omitted). A plain fit uses N as the finest bin width it may use and keeps every bin at 0 or 10 or more rows, so it can write fewer bins; a column that keeps stored values or a quantile grid gets one bin.",
    ),
    dp_allow_omit: bool = typer.Option(
        False,
        "--dp-allow-omit",
        help=(
            "Allow the DP release to omit source columns nobody declared with "
            "--dp-number/--dp-flag/--dp-text (default: omission is a usage error "
            "listing the columns). Requires --epsilon."
        ),
    ),
    fanout: list[str] = typer.Option(
        [],
        "--fanout",
        metavar="COLUMN",
        help=(
            "Record how many rows each key of COLUMN has (repeatable): the child-side "
            "key of a foreign key. A generate reference column with `distribution: "
            "fitted` then gives each generated parent about as many children as the "
            "source parents had. Counts only, never a key value. Not supported with "
            "--epsilon."
        ),
    ),
    include_values: bool = typer.Option(
        False,
        "--include-values",
        help=(
            "Keep real values of sensitive columns in the snapshot. The file then "
            "holds real data. Not supported with --epsilon."
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
) -> None:
    """Fit a distribution-snapshot/v2 artifact for statistical generation.

    Without --epsilon: reads the source CSV, captures per-column
    distribution shape (numeric histograms + quantiles, categorical top-k,
    datetime year bins) plus any requested pairwise contingency tables, and
    writes the JSON artifact `type: statistical` generate columns reference
    via `snapshot_file`.

    A file over the row limit (--rows, else the fit.max_rows setting, default
    1,000,000) is fitted on a seeded random sample spread across the whole file.

    With --epsilon: fits a `dps-marginal/v3` artifact instead, releasing
    ONLY the columns declared via --dp-number/--dp-flag/--dp-text under one
    (epsilon, delta) budget. DP runs only on a certified install. Exits 0 on success, 1 on bad input, 3 if the
    engine's DP fit refuses at run time (an uncertified proof stack, or an
    internal schedule invariant).
    """
    state = setup_output(json_, quiet, verbose)

    def _emit_error(
        message: str, *, err_code: str | None = None, hint_text: str | None = None
    ) -> None:
        emit_error(
            state,
            "fit",
            message,
            code=err_code,
            hint=hint_text,
            context={"source": str(source)},
        )

    def _emit_dp_refused(refusal: Any) -> None:
        # The engine text carries the platform and a package fingerprint: JSON
        # and --verbose keep it, the default human line stays plain.
        if state.mode is OutputMode.json:
            _emit_error(refusal.message, err_code=refusal.code, hint_text=_DP_REFUSED_HINT)
        else:
            emit_error(state, "fit", _DP_REFUSED_LINE, hint=_DP_REFUSED_HINT)
            if verbose:
                state.err_console.print(" ", f"{refusal.code}: {refusal.message}")

    joint_pairs: list[tuple[str, str]] = []
    for spec in joint:
        parts = [p.strip() for p in spec.split(",") if p.strip()]
        if len(parts) != 2:
            _emit_error(
                f"--joint expects 'colA,colB'; got {spec!r}.",
                err_code="dp_usage_joint_spec_invalid",
            )
            raise typer.Exit(code=EXIT_USAGE)
        joint_pairs.append((parts[0], parts[1]))
    if joint_max_cells is not None and not joint_pairs:
        _emit_error(
            "--joint-max-cells sets the cell cap of a --joint pair; pass --joint 'a,b' with it.",
            err_code="fit_joint_max_cells_needs_joint",
        )
        raise typer.Exit(code=EXIT_USAGE)

    # --- D0: DP mode is explicit and fail-closed, decided BEFORE the CSV is
    # read and before any carrier declaration is parsed for content. ---------
    row_limit: int | None = None
    try:
        if rows is not None:
            row_limit = _parse_rows(rows)
    except _FitUsageError as exc:
        _emit_error(exc.message, err_code=exc.code)
        raise typer.Exit(code=EXIT_USAGE)

    fanout_names = list(dict.fromkeys(fanout))
    has_carrier_decls = bool(dp_number or dp_flag or dp_text)
    delta_given = delta is not None

    try:
        if epsilon is None:
            dp_only_given = []
            if delta_given:
                dp_only_given.append("--delta")
            if has_carrier_decls:
                dp_only_given.append("--dp-number/--dp-flag/--dp-text")
            if dp_allow_omit:
                dp_only_given.append("--dp-allow-omit")
            if dp_only_given:
                raise _FitUsageError(
                    f"{', '.join(dp_only_given)} require --epsilon (DP mode is not "
                    "selected). Pass --epsilon to run the DP fit, or drop them to run "
                    "the exact (non-DP) fit.",
                    code="dp_mode_not_selected",
                )
        else:
            if row_limit is not None:
                raise _FitUsageError(
                    "--rows with --epsilon is not supported: a DP fit uses every row "
                    "under its own budget rules and never samples. Drop --rows or omit "
                    "--epsilon.",
                    code="dp_mode_rows_unsupported",
                )
            if fanout_names:
                raise _FitUsageError(
                    "--fanout with --epsilon is not supported: a DP release carries no "
                    "per-key counts. Drop --fanout or omit --epsilon.",
                    code="dp_mode_fanout_unsupported",
                )
            if include_values:
                raise _FitUsageError(
                    "--include-values with --epsilon is not supported: a DP release "
                    "never holds real cell values. Drop --include-values or omit "
                    "--epsilon.",
                    code="dp_usage_include_values",
                )
            if joint_pairs:
                raise _FitUsageError(
                    "--epsilon with --joint is not supported: releasing marginals "
                    "plus joint tables under one epsilon needs composition accounting "
                    "not implemented here. Drop --joint or omit --epsilon.",
                    code="dp_mode_joint_unsupported",
                )
            if parse_dates:
                raise _FitUsageError(
                    "--epsilon with --parse-dates is not supported: datetime handling "
                    "for a DP fit is decided at the option level, never by inspecting "
                    "data. Declare a date-like column with --dp-text (ordinary "
                    "categorical text) if that is acceptable, or omit --epsilon.",
                    code="dp_mode_parse_dates_unsupported",
                )
            if not delta_given:
                raise _FitUsageError(
                    "--epsilon requires --delta: the (epsilon, delta) budget must be "
                    "fully specified, and there is no default delta (a silent default "
                    "would set a privacy level you did not choose).",
                    code="dp_mode_delta_required",
                )
            if not has_carrier_decls:
                raise _FitUsageError(
                    "--epsilon requires at least one carrier declaration "
                    "(--dp-number/--dp-flag/--dp-text): an epsilon with nothing "
                    "declared would release nothing.",
                    code="dp_mode_no_carriers",
                )

        column_schema = _build_column_schema(dp_number, dp_flag, dp_text)
        if epsilon is None and row_limit is None:
            setting_error: str | None = None
            try:
                row_limit = read_fit_max_rows()
            except ResourceError as exc:
                setting_error = str(exc)
            if setting_error is not None:
                # Raised after the except block closes: no __context__ to carry the cause.
                raise _FitUsageError(setting_error, code="fit_rows_setting_invalid")
    except _FitUsageError as exc:
        _emit_error(exc.message, err_code=exc.code)
        raise typer.Exit(code=EXIT_USAGE)

    from decoy_engine import snapshot_joint_warnings
    from decoy_engine.quality.snapshot import (
        DEFAULT_CONTINGENCY_TOP_K,
        MAX_CONTINGENCY_TOP_K,
        DistributionSnapshotError,
        check_contingency_top_k,
    )

    from decoy.ui.summary import warning_record

    # The engine owns the bound; the CLI only turns the text into a number for it.
    cell_cap = DEFAULT_CONTINGENCY_TOP_K
    if joint_max_cells is not None:
        # ASCII digits only: int() also takes "1_000", "+30" and non-ASCII digits.
        text = joint_max_cells.strip()
        parsed: object = int(text) if text.isascii() and text.isdigit() else joint_max_cells
        try:
            check_contingency_top_k(parsed)
        except DistributionSnapshotError as exc:
            # Named override: the engine type is a flag validator here, and the owner map's 3
            # for it is right for a snapshot that fails at run time (24ze G-C1 carries it).
            _emit_error(
                f"--joint-max-cells must be a whole number from 1 to {MAX_CONTINGENCY_TOP_K}.",
                err_code=exc.code,
            )
            raise typer.Exit(code=EXIT_USAGE)
        cell_cap = int(text)

    def _unreadable() -> None:
        # No str(exc): a pandas parse error can quote a source cell.
        _emit_error(f"could not read {source} as a CSV.")
        raise typer.Exit(code=EXIT_USAGE)

    # DP mode ingests every cell as its literal CSV lexeme: dtype=str disables
    # column-wide dtype inference (so one row cannot change how another is
    # boxed), and keep_default_na=False disables pandas' NA grammar (so
    # "NA"/"null"/"" stay the exact lexemes the engine's per-cell text/number
    # codecs see). Both are required for D6 boxing invariance and stability-1.
    # _build_typed_frame below converts only flags; number and text columns
    # reach the engine as raw strings.
    dp_read_kwargs: dict[str, Any] = {"dtype": str, "keep_default_na": False, "index_col": False}
    omitted_columns: list[str] = []
    dp_header: list[str] = []
    dp_kwargs: dict[str, Any] = {}

    if epsilon is not None:
        from decoy_engine.quality import check_dp_fit_request
        from decoy_engine.quality.carriers import CarrierError
        from decoy_engine.quality.dp import DpError, fit_dp_snapshot
        from decoy_engine.quality.dp_budget import DpBudgetError
        from decoy_engine.quality.dp_provenance import ProvenanceError

        # Header only: the name checks and the engine's request check below
        # decide from column names and options, so no data row is read when the
        # request is invalid or this install cannot run a DP fit.
        header_failed = False
        try:
            dp_header = list(read_fit_csv(source, nrows=0, **dp_read_kwargs).columns)
        except Exception:
            header_failed = True
        if header_failed:
            _unreadable()

        # D3: only declared columns are ever released; an undeclared
        # source column is a usage error by default (the foot-gun of silently
        # dropping a column the operator expected to see), unless the
        # operator explicitly opts in with --dp-allow-omit.
        omitted_columns = sorted(set(dp_header) - set(column_schema))
        if omitted_columns and not dp_allow_omit:
            _emit_error(
                f"source column(s) not declared for the DP release: {', '.join(omitted_columns)}.",
                err_code="dp_columns_omitted",
                hint_text=(
                    "declare each with --dp-number/--dp-flag/--dp-text, or pass "
                    "--dp-allow-omit to release only the declared columns."
                ),
            )
            raise typer.Exit(code=EXIT_USAGE)
        if omitted_columns:
            omission_notice = (
                f"omitting {len(omitted_columns)} undeclared source column(s) from "
                f"the DP release: {', '.join(omitted_columns)}."
            )
            if state.mode is not OutputMode.quiet:
                state.err_console.print(warn("notice:"), omission_notice)

        # A declared column absent from the CSV is a usage error, surfaced by
        # name before the engine steps. Otherwise a phantom --dp-flag column
        # crashes _build_typed_frame with a raw KeyError (breaking the --json
        # error contract), and a phantom --dp-number/text column gets
        # misattributed to an uncertified host. Names only, so this stays
        # data-independent (D6).
        missing_declared = sorted(set(column_schema) - set(dp_header))
        if missing_declared:
            _emit_error(
                f"declared DP column(s) not in the CSV: {', '.join(missing_declared)}.",
                err_code="dp_schema_column_missing",
                hint_text="each --dp-number/--dp-flag/--dp-text column must name a column in the source CSV.",
            )
            raise typer.Exit(code=EXIT_USAGE)

        if numeric_bins is not None:
            dp_kwargs["numeric_bins"] = numeric_bins

        # The engine's own request check: typed request errors first, then the
        # certified-install gate, all before any data row is read.
        try:
            check_dp_fit_request(column_schema, epsilon=epsilon, delta=delta, **dp_kwargs)
        except ProvenanceError as exc:
            _emit_dp_refused(exc)
            raise typer.Exit(code=exit_code_for(exc))
        except (DpBudgetError, DpError, CarrierError) as exc:
            _emit_error(exc.message, err_code=exc.code)
            raise typer.Exit(code=exit_code_for(exc))

    rows_total: int
    fit_warnings: list[dict[str, Any]] = []
    if epsilon is None:
        assert row_limit is not None
        source_error: FitSourceError | None = None
        try:
            fitted = fit_exact_snapshot(
                source,
                row_limit=row_limit,
                parse_dates=parse_dates,
                joint_pairs=joint_pairs,
                include_values=include_values,
                contingency_top_k=cell_cap,
                fanout_columns=fanout_names,
                numeric_bins=numeric_bins,
            )
        except FitSourceError as exc:
            source_error = exc
        if source_error is not None:  # raised outside the except block: no exception context
            _emit_error(source_error.message, err_code=source_error.code)
            raise typer.Exit(code=exit_code_for(source_error))
        snapshot, rows_used, rows_total = fitted.snapshot, fitted.rows_used, fitted.rows_total
        fit_warnings = [
            warning_record(w.code, column=w.column, detail=w.detail)
            for w in snapshot_joint_warnings(snapshot, contingency_top_k=cell_cap)
        ]
    else:
        # DP mode reads the literal lexemes (see dp_read_kwargs above).
        read_failed = False
        try:
            with strict_csv():
                df = read_fit_csv(source, **dp_read_kwargs)
        except Exception:
            read_failed = True
        if read_failed:
            _unreadable()
        rows_used = rows_total = len(df)
        # The name checks ran on the header. A file replaced between the two
        # reads would reach the typed frame with names nobody checked.
        if list(df.columns) != dp_header:
            _emit_error(
                "the CSV changed while it was being read; run the command again.",
                err_code="dp_source_changed",
            )
            raise typer.Exit(code=EXIT_USAGE)

        typed_df = _build_typed_frame(df, column_schema)
        try:
            snapshot = fit_dp_snapshot(
                typed_df, column_schema, epsilon=epsilon, delta=delta, **dp_kwargs
            )
        except ProvenanceError as exc:
            _emit_dp_refused(exc)
            raise typer.Exit(code=exit_code_for(exc))
        except (DpBudgetError, DpError, CarrierError) as exc:
            _emit_error(exc.message, err_code=exc.code)
            raise typer.Exit(code=exit_code_for(exc))

    withheld: list[str] = list(snapshot.get("redacted_columns") or []) if epsilon is None else []
    # Only reached on success: a failed fit creates or overwrites nothing.
    out_path = output if output is not None else side_file_default("snapshot", source)
    try:
        write_local_target(
            out_path, json.dumps(snapshot, indent=1).encode("utf-8"), WriteMode.REPLACE
        )
    except AtomicWriteError as exc:
        _emit_error(f"could not write the snapshot: {describe(exc)}", err_code=exc.code)
        raise typer.Exit(code=EXIT_RUNTIME)

    if withheld and snapshot.get("value_policy") == "raw" and state.mode is not OutputMode.quiet:
        state.err_console.print(
            warn("warning:"),
            f"{out_path} holds real values of {len(withheld)} sensitive "
            f"column(s): {', '.join(withheld)}. Do not share or commit it.",
        )
    if state.mode is OutputMode.default:
        for record in fit_warnings:
            # The line quotes column names from the CSV header: print it as plain text.
            state.err_console.print(warn("warning:"), record["message"], markup=False)

    from decoy_engine.quality import snapshot_null_fraction

    # The engine's one null-rate rule (zero-row and corrupt counts give None, left out here).
    null_rates = {
        name: rate
        for name, entry in snapshot["columns"].items()
        if (rate := snapshot_null_fraction(entry)) is not None
    }

    if state.mode is OutputMode.json:
        payload: dict[str, Any] = {
            "command": "fit",
            "status": "ok",
            "source": str(source),
            "output": str(out_path),
            "row_count": snapshot["row_count"],
            "rows_used": rows_used,
            "rows_total": rows_total,
            "columns": {name: entry["kind"] for name, entry in snapshot["columns"].items()},
            "joints": [j["columns"] for j in snapshot["joints"]],
            "fanout_columns": fanout_names,
            "null_rates": null_rates,
            "warnings": [{k: r[k] for k in ("code", "message", "detail")} for r in fit_warnings],
        }
        if epsilon is None:
            payload["value_policy"] = snapshot.get("value_policy")
            payload["redacted_columns"] = withheld
        if epsilon is not None:
            payload["dp"] = {"schema": snapshot["dp"]["schema"]}
            payload["omitted_columns"] = omitted_columns
        emit_json(state, payload)
        return
    if state.mode is OutputMode.quiet:
        return

    state.console.print(success("OK"), code(str(out_path)))
    kinds = ", ".join(
        f"{n} ({e['kind']}{f', {null_rates[n]:.1%} null' if null_rates.get(n) else ''})"
        for n, e in snapshot["columns"].items()
    )
    state.console.print(f"  fitted on {rows_used:,} of {rows_total:,} rows; columns: {kinds}")
    for name in fanout_names:
        block = snapshot["columns"][name]["fanout"]
        top = max((degree for degree, _ in block["degrees"]), default=0)
        state.console.print(
            f"  fan-out kept for {name}: {block['keys']} keys, up to {top} rows per key",
            markup=False,
        )
    if fanout_names:
        state.console.print(
            " ",
            hint("hint:"),
            "use `distribution: fitted` on the reference column that points at the parent.",
        )
    if snapshot["joints"]:
        pairs = ", ".join("x".join(j["columns"]) for j in snapshot["joints"])
        state.console.print(f"  joints captured: {pairs}")
    if withheld:
        names = ", ".join(withheld)
        if snapshot.get("value_policy") != "raw":
            state.console.print(
                f"  {len(withheld)} sensitive column(s) withheld: {names} (no cell "
                "values kept; numbers reduced to one range, dates to years)"
            )
            state.console.print(
                " ",
                hint("hint:"),
                "to sample these as categories, re-run with --include-values (the "
                "file then holds real data). A DP release (--epsilon) needs a "
                "certified DP install; see decoy explain differential-privacy.",
            )
    if epsilon is not None:
        state.console.print(
            f"  DP release: {snapshot['dp']['schema']}, epsilon={epsilon}, delta={delta}"
        )


FIT_EPILOG = _FIT_EPILOG
