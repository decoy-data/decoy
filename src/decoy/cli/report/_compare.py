"""Manifest-level and data-level comparison of two runs, shared by ``report diff``."""

from __future__ import annotations

import json as _json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from decoy.cli._sources import (
    read_file,
)
from decoy.cli.evidence import (
    resolve_manifest_path,
)
from decoy.cli.io import TargetFormatError, entry_format
from decoy.safe_url import redacted_location


def _warning_key(w: Any) -> str:
    """Produce a stable string key for a warning entry (for set-diff comparison)."""
    if isinstance(w, dict):
        return _json.dumps(w, sort_keys=True)
    return str(w)


def compare_manifests(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Compare two evidence manifests and return a structured diff.

    EVIDENCE-SAFE: operates entirely on manifest dicts. Does NOT read any
    files from disk.

    Returns a dict with:
      pipeline_fingerprint_changed   bool
      old_pipeline_fingerprint       str | None
      new_pipeline_fingerprint       str | None
      input_fingerprint_changes      dict with "changed", "added", "removed" lists
      output_fingerprint_changes     dict with "changed", "added", "removed" lists
      row_count_deltas               list of {"table", "old", "new", "delta"}
      warnings_added                 list (warnings in new but not old)
      warnings_removed               list (warnings in old but not in new)
      any_change                     bool
    """
    old_pf = old.get("pipeline_fingerprint")
    new_pf = new.get("pipeline_fingerprint")
    pipeline_fp_changed = old_pf != new_pf

    # --- Fingerprint helpers ---
    def _fp_changes(old_fps: dict[str, Any], new_fps: dict[str, Any]) -> dict[str, list[Any]]:
        changed: list[dict[str, Any]] = []
        added: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        all_tables = set(old_fps) | set(new_fps)
        for tname in sorted(all_tables):
            old_info = old_fps.get(tname) if isinstance(old_fps.get(tname), dict) else {}
            new_info = new_fps.get(tname) if isinstance(new_fps.get(tname), dict) else {}
            old_fp = (old_info or {}).get("fingerprint") if old_info else None
            new_fp = (new_info or {}).get("fingerprint") if new_info else None

            if tname not in old_fps:
                added.append({"table": tname, "fingerprint": new_fp})
            elif tname not in new_fps:
                removed.append({"table": tname, "fingerprint": old_fp})
            elif old_fp != new_fp:
                changed.append({"table": tname, "old": old_fp, "new": new_fp})
        return {"changed": changed, "added": added, "removed": removed}

    old_in = old.get("input_fingerprints") or {}
    new_in = new.get("input_fingerprints") or {}
    input_changes = _fp_changes(old_in, new_in)

    old_out = old.get("output_fingerprints") or {}
    new_out = new.get("output_fingerprints") or {}
    output_changes = _fp_changes(old_out, new_out)

    # --- Row count deltas ---
    old_rc: dict[str, Any] = old.get("row_counts") or {}
    new_rc: dict[str, Any] = new.get("row_counts") or {}
    all_tables = set(old_rc) | set(new_rc)
    row_count_deltas: list[dict[str, Any]] = []
    for tname in sorted(all_tables):
        old_count = old_rc.get(tname)
        new_count = new_rc.get(tname)
        if old_count != new_count:
            try:
                delta = int(new_count or 0) - int(old_count or 0)
            except (TypeError, ValueError):
                delta = None
            row_count_deltas.append(
                {"table": tname, "old": old_count, "new": new_count, "delta": delta}
            )

    # --- Warnings set-diff ---
    old_warn_keys = {_warning_key(w) for w in (old.get("warnings") or [])}
    new_warn_keys = {_warning_key(w) for w in (new.get("warnings") or [])}

    warnings_added = [
        w for w in (new.get("warnings") or []) if _warning_key(w) not in old_warn_keys
    ]
    warnings_removed = [
        w for w in (old.get("warnings") or []) if _warning_key(w) not in new_warn_keys
    ]

    # --- any_change aggregation ---
    in_has_change = bool(
        input_changes["changed"] or input_changes["added"] or input_changes["removed"]
    )
    out_has_change = bool(
        output_changes["changed"] or output_changes["added"] or output_changes["removed"]
    )
    any_change = bool(
        pipeline_fp_changed
        or in_has_change
        or out_has_change
        or row_count_deltas
        or warnings_added
        or warnings_removed
    )

    return {
        "pipeline_fingerprint_changed": pipeline_fp_changed,
        "old_pipeline_fingerprint": old_pf,
        "new_pipeline_fingerprint": new_pf,
        "input_fingerprint_changes": input_changes,
        "output_fingerprint_changes": output_changes,
        "row_count_deltas": row_count_deltas,
        "warnings_added": warnings_added,
        "warnings_removed": warnings_removed,
        "any_change": any_change,
    }


def _column_profile(df: "Any") -> dict[str, dict[str, Any]]:
    """Build a per-column summary profile from a pandas DataFrame.

    Returns a dict keyed by column name with:
      - dtype_kind: pandas dtype kind char ('i', 'f', 'u', 'O', 'M', 'b', ...)
      - null_count: int
      - unique_count: int

    Methodology: pandas.Series.nunique() and .isnull().sum() for column-level
    null/cardinality counts. No novel statistical method is used.

    EVIDENCE-SAFE: aggregate counts only -- no raw cell values are returned.
    """
    profile: dict[str, dict[str, Any]] = {}
    for col in df.columns:
        series = df[col]
        kind = series.dtype.kind
        null_count = int(series.isnull().sum())
        unique_count = int(series.nunique(dropna=True))
        profile[col] = {
            "dtype_kind": kind,
            "null_count": null_count,
            "unique_count": unique_count,
        }
    return profile


def _entry_formats(
    entries: Sequence[Mapping[str, Any]],
) -> tuple[list[tuple[str, Mapping[str, Any] | None]], list[TargetFormatError]]:
    """The recorded `(format, layout)` of every present entry, and the refusals instead.

    The one projection and check for a table seen on one side or both, so a key a reader needs
    cannot pass on one path and fail on the other. Every entry is checked before any is read.
    """
    formats: list[tuple[str, Mapping[str, Any] | None]] = []
    errors: list[TargetFormatError] = []
    for entry in entries:
        try:
            formats.append(entry_format({k: entry[k] for k in ("format", "layout") if k in entry}))
        except TargetFormatError as err:
            errors.append(err)
    return formats, errors


def compare_data(
    manifest_a: dict[str, Any],
    manifest_b: dict[str, Any],
    *,
    manifest_file_a: Path | None,
    manifest_file_b: Path | None,
) -> dict[str, Any]:
    """Compare output data files from two runs at the data level.

    Takes two whole evidence manifests and the files they were read from. Each output entry's
    `path` is resolved by `evidence.resolve_manifest_path` against its own manifest's project,
    never the working directory; an entry with a null fingerprint (nothing written) counts as
    missing. Since CLI-FMT an entry records the `format` (and fixed-width `layout`) it was
    written in; each side is read by its own entry. An entry without `format` (or with one that
    cannot be read) is refused before either side of its table is read; the table's paths go to
    `missing_files` and the refusal's code and fixed message to `refusals`. Raises
    `ManifestError` when a stored path is refused.

    Returns `any_data_change` (bool), `missing_files` (recorded paths not found, not readable or
    refused), `refusals` (sorted `(code, message)` pairs of the refused entries) and
    `table_deltas`: per table, `row_count_a`/`_b`/`_delta`, `columns_added` and
    `columns_removed` (B against A), and `column_deltas` with `null_count_delta`,
    `unique_count_delta`, `dtype_kind_a`/`_b` and `dtype_changed` for each changed column.

    Methodology: pandas.Series.nunique() and .isnull().sum() (pandas v2.x) for column-level
    null/cardinality counts. No novel statistical method is used.

    EVIDENCE-SAFE: reports aggregate counts only. Raw row/cell values are
    never included in the output.
    """
    from decoy_engine import DecoyError

    output_fps_a: dict[str, Any] = manifest_a.get("output_fingerprints") or {}
    output_fps_b: dict[str, Any] = manifest_b.get("output_fingerprints") or {}
    all_tables = sorted(set(output_fps_a) | set(output_fps_b))

    table_deltas: list[dict[str, Any]] = []
    missing_files: list[str] = []
    refusals: set[tuple[str, str]] = set()
    any_data_change = False

    def _skip(raws: tuple[str, ...], errors: Sequence[TargetFormatError] = ()) -> None:
        """The one place a table's paths are recorded as skipped, with any refusal codes."""
        shown = (redacted_location(r) for r in raws)
        missing_files.extend(s for s in dict.fromkeys(shown) if s not in missing_files)
        refusals.update((err.code, str(err)) for err in errors)

    for table in all_tables:
        fp_a = output_fps_a.get(table) or {}
        fp_b = output_fps_b.get(table) or {}
        path_a_str = fp_a.get("path") if isinstance(fp_a, dict) else None
        path_b_str = fp_b.get("path") if isinstance(fp_b, dict) else None

        if not path_a_str or not path_b_str:
            # Table only in one run -- treat as a change, unless its one entry is refused.
            present = [(raw, fp) for raw, fp in ((path_a_str, fp_a), (path_b_str, fp_b)) if raw]
            _, lone_errors = _entry_formats([fp for _, fp in present])
            if lone_errors:
                _skip(tuple(raw for raw, _ in present), lone_errors)
                continue
            any_data_change = True
            table_deltas.append(
                {
                    "table": table,
                    "row_count_a": None,
                    "row_count_b": None,
                    "row_count_delta": None,
                    "columns_added": [],
                    "columns_removed": [],
                    "column_deltas": [],
                    "note": "table only exists in one run",
                }
            )
            continue

        sides = ((manifest_a, fp_a, manifest_file_a), (manifest_b, fp_b, manifest_file_b))
        found: list[Path] = []
        for manifest, entry, where in sides:
            raw = entry["path"]
            path = None
            if entry.get("fingerprint") is not None:
                field = f"output_fingerprints.{table}.path"
                path = resolve_manifest_path(manifest, raw, manifest_file=where, field=field)
            try:
                if path is not None and path.exists():
                    found.append(path)
                    continue
            except (OSError, ValueError):
                pass
            _skip((raw,))

        if len(found) != len(sides):
            continue

        # Both sides are checked before either is read, each on its own recorded format.
        formats, errors = _entry_formats([fp_a, fp_b])
        if errors:
            _skip((path_a_str, path_b_str), errors)
            continue
        (fmt_a, layout_a), (fmt_b, layout_b) = formats
        try:
            df_a = read_file(found[0], fmt_a, layout_a, table=table)
            df_b = read_file(found[1], fmt_b, layout_b, table=table)
        except (OSError, ValueError, DecoyError):
            # Unreadable (corrupt, truncated, or not its recorded format): treat it as missing so
            # --require-data still fails. The parser message is dropped: it can echo cell values.
            _skip((path_a_str, path_b_str))
            continue

        rows_a = len(df_a)
        rows_b = len(df_b)
        row_delta = rows_b - rows_a

        cols_a = set(df_a.columns)
        cols_b = set(df_b.columns)
        columns_added = sorted(cols_b - cols_a)
        columns_removed = sorted(cols_a - cols_b)
        common_cols = sorted(cols_a & cols_b)

        profile_a = _column_profile(df_a)
        profile_b = _column_profile(df_b)

        column_deltas: list[dict[str, Any]] = []
        for col in common_cols:
            pa = profile_a.get(col, {})
            pb = profile_b.get(col, {})
            nc_a = pa.get("null_count")
            nc_b = pb.get("null_count")
            uc_a = pa.get("unique_count")
            uc_b = pb.get("unique_count")
            dk_a = pa.get("dtype_kind")
            dk_b = pb.get("dtype_kind")
            dtype_changed = dk_a != dk_b

            nc_delta = (nc_b - nc_a) if (nc_a is not None and nc_b is not None) else None
            uc_delta = (uc_b - uc_a) if (uc_a is not None and uc_b is not None) else None

            has_col_change = bool(
                dtype_changed
                or (nc_delta is not None and nc_delta != 0)
                or (uc_delta is not None and uc_delta != 0)
            )
            if has_col_change:
                column_deltas.append(
                    {
                        "column": col,
                        "dtype_kind_a": dk_a,
                        "dtype_kind_b": dk_b,
                        "dtype_changed": dtype_changed,
                        "null_count_delta": nc_delta,
                        "unique_count_delta": uc_delta,
                    }
                )

        table_changed = bool(row_delta != 0 or columns_added or columns_removed or column_deltas)
        if table_changed:
            any_data_change = True

        table_deltas.append(
            {
                "table": table,
                "row_count_a": rows_a,
                "row_count_b": rows_b,
                "row_count_delta": row_delta,
                "columns_added": columns_added,
                "columns_removed": columns_removed,
                "column_deltas": column_deltas,
            }
        )

    return {
        "any_data_change": any_data_change,
        "table_deltas": table_deltas,
        "missing_files": missing_files,
        "refusals": sorted(refusals),
    }
