"""The pure target-format rule (CLI-FMT Part A): suffix claims, issues, messages, one resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from decoy.cli.io import _targets
from decoy.cli.io._targets import (
    FORMAT_UNKNOWN,
    STREAMING_UNSUPPORTED,
    SUFFIX_MISMATCH,
    UNREADABLE,
    UNRECORDED,
    TargetFormatError,
    check_target_formats,
    claimed_format,
    entry_format,
    format_for_path,
    input_format,
    target_format_issues,
)


@pytest.mark.parametrize(
    ("name", "claimed"),
    [
        ("out.csv", "csv"),
        ("out.CSV", "csv"),
        ("out.parquet", "parquet"),
        ("out.PQ", "parquet"),
        ("out.csv.gz", "csv"),
        ("out.parquet.tar.gz", "parquet"),
        ("out.csv.parquet", "parquet"),
        ("out.txt", None),
        ("out.dat.gz", None),
        ("out", None),
        (".gz", None),
    ],
)
def test_claimed_format(name: str, claimed: str | None) -> None:
    assert claimed_format(Path(name)) == claimed
    assert format_for_path(Path(name)) == (claimed or "csv")


def _config(fmt: str, path: str, **extra: object) -> dict:
    return {"targets": {"t": {"type": "file", "format": fmt, "path": path, **extra}}}


@pytest.mark.parametrize("suffix", [".gz", ".bz2", ".xz", ".zst"])
def test_stream_compressors_stay_allowed_when_chunked(suffix: str) -> None:
    assert target_format_issues(_config("csv", f"/d/out.csv{suffix}"), chunked=True) == []


@pytest.mark.parametrize("suffix", [".zip", ".tar", ".tar.gz", ".tar.bz2", ".tar.xz"])
def test_archives_are_refused_when_chunked_only(suffix: str) -> None:
    config = _config("csv", f"/d/out.csv{suffix}")
    assert target_format_issues(config, chunked=False) == []
    (issue,) = target_format_issues(config, chunked=True)
    assert issue.code == STREAMING_UNSUPPORTED


def test_messages_are_value_free() -> None:
    cases = {
        SUFFIX_MISMATCH: _config("parquet", "/zz_marker_dir/out.csv"),
        STREAMING_UNSUPPORTED: _config("fixed_width", "/zz_marker_dir/out.txt", layout={}),
        FORMAT_UNKNOWN: _config("xlsx", "/zz_marker_dir/out.xlsx"),
    }
    for code, config in cases.items():
        (issue,) = target_format_issues(config, chunked=True)
        assert issue.code == code
        with pytest.raises(TargetFormatError) as err:
            check_target_formats(config, chunked=True)
        assert str(err.value) == issue.message
        assert err.value.code == code
        assert err.value.__cause__ is None and err.value.__context__ is None
        for text in (str(err.value), issue.message):
            assert "zz_marker_dir" not in text
            assert "xlsx" not in text
            assert "targets.t" in text
    assert "'parquet'" in target_format_issues(cases[SUFFIX_MISMATCH], chunked=False)[0].message


def test_issues_come_in_sorted_table_order_and_skip_non_file_targets() -> None:
    config = {
        "targets": {
            "b": {"type": "file", "format": "csv", "path": "b.parquet"},
            "a": {"type": "file", "format": "parquet", "path": "a.csv"},
            "c": {"type": "s3", "format": "csv", "path": "c.parquet"},
            "d": "not a dict",
        }
    }
    assert [i.table for i in target_format_issues(config, chunked=False)] == ["a", "b"]


def test_one_path_resolver() -> None:
    from decoy.cli import _sources, demo, run

    assert run._resolve_path is _sources.resolve_path
    assert not hasattr(demo, "_resolve_path")
    assert _targets.resolve_path is _sources.resolve_path
    assert _sources.resolve_path("/abs/x.csv", Path("/base")) == Path("/abs/x.csv")
    assert _sources.resolve_path("rel/x.csv", Path("/base")) == Path("/base/rel/x.csv")


@pytest.mark.parametrize(
    ("value", "canonical"),
    [
        ("42", True),
        ("-7", True),
        ("0", True),
        ("42\n", False),
        ("007", False),
        ("-0", False),
        ("9223372036854775807", True),
        ("-9223372036854775808", True),
        ("9223372036854775808", False),
        ("-9223372036854775809", False),
    ],
)
def test_canonical_int_strings(value: str, canonical: bool) -> None:
    import pandas as pd

    got = _targets._coerce_canonical_int_strings(pd.Series([value], dtype=object))
    assert (got is not None) == canonical


# ---------------------------------------------------------------------------
# CLI-FMT Part B: the read-side rule
# ---------------------------------------------------------------------------

_LAYOUT = {"columns": [{"name": "a", "start": 0, "width": 3}]}


def _targets_config(fmt: object, path: str, **extra: object) -> dict:
    return {"targets": {"t": {"type": "file", "format": fmt, "path": path, **extra}}}


def test_input_format_uses_the_declaration_for_the_target_file(tmp_path: Path) -> None:
    target = tmp_path / "out.dat"
    config = _targets_config("parquet", "out.dat")
    assert input_format(config, "t", target, tmp_path) == ("parquet", None)
    config = _targets_config("fixed_width", "out.dat", layout=_LAYOUT)
    assert input_format(config, "t", target, tmp_path) == ("fixed_width", _LAYOUT)
    # Any other file, or another table's name, has no declaration: the suffix rule.
    other = tmp_path / "copy.pq"
    assert input_format(config, "t", other, tmp_path) == ("parquet", None)
    assert input_format(config, "u", target, tmp_path) == ("csv", None)


@pytest.mark.parametrize(
    "target",
    [
        _targets_config("xml", "out.dat"),
        _targets_config("fixed_width", "out.dat"),
        _targets_config(None, "out.dat"),
    ],
)
def test_input_format_refuses_an_unreadable_declaration_before_any_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: dict
) -> None:
    import builtins

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("opened a file before the refusal")

    monkeypatch.setattr(builtins, "open", boom)
    monkeypatch.setattr("decoy.cli._sources.read_csv_frame", boom)
    with pytest.raises(TargetFormatError) as err:
        input_format(target, "t", tmp_path / "out.dat", tmp_path)
    assert err.value.code == UNREADABLE
    assert err.value.__cause__ is None and err.value.__context__ is None
    assert "xml" not in str(err.value) and "out.dat" not in str(err.value)


@pytest.mark.parametrize(
    ("recorded", "expected"),
    [
        ({"format": "parquet"}, ("parquet", None)),
        ({"format": "csv"}, ("csv", None)),
        ({"format": "fixed_width", "layout": _LAYOUT}, ("fixed_width", _LAYOUT)),
        ({"format": "csv", "layout": _LAYOUT}, ("csv", None)),
    ],
)
def test_entry_format(recorded: dict, expected: tuple) -> None:
    assert entry_format(recorded) == expected


_UNRECORDED_TEXT = (
    "the evidence manifest entry records no format (written before format recording); "
    "re-run the pipeline to write a new manifest"
)


@pytest.mark.parametrize("recorded", [{}, {"layout": _LAYOUT}, {"layout": "SEEDED_LAYOUT_ZZ"}])
def test_entry_format_refuses_an_entry_with_no_format(recorded: dict) -> None:
    with pytest.raises(TargetFormatError) as err:
        entry_format(recorded)
    assert err.value.code == UNRECORDED == "target_format_unrecorded"
    assert str(err.value) == _UNRECORDED_TEXT
    assert err.value.__cause__ is None and err.value.__context__ is None


@pytest.mark.parametrize(
    "recorded",
    [
        {"format": "xml"},
        {"format": None},
        {"format": "fixed_width"},
        {"format": "fixed_width", "layout": 5},
        {"format": "fixed_width", "layout": True},
        {"format": "fixed_width", "layout": "x"},
        {"format": "fixed_width", "layout": [1]},
        {"format": "fixed_width", "layout": {}},
    ],
)
def test_entry_format_refuses_what_it_cannot_read(recorded: dict) -> None:
    with pytest.raises(TargetFormatError) as err:
        entry_format(recorded)
    assert err.value.code == UNREADABLE
    assert "xml" not in str(err.value)


def _fp(**keys: object) -> dict:
    return {"path": "p", "fingerprint": "sha256:" + "0" * 64, **keys}


def _compare(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, side_a: dict, side_b: dict) -> dict:
    """`compare_data` over two one-table manifests, with every file read forbidden."""
    from decoy.cli.report import _compare as compare_mod

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("a file was read for a refused table")

    monkeypatch.setattr(compare_mod, "read_file", boom)
    for name in ("pa", "pb", "pa2", "pb2"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    manifests = [{"output_fingerprints": side} for side in (side_a, side_b)]
    return compare_mod.compare_data(*manifests, manifest_file_a=None, manifest_file_b=None)


def _entry(tmp_path: Path, name: str, **keys: object) -> dict:
    return {"t": {**_fp(**keys), "path": str(tmp_path / name)}}


_UNREADABLE_PAIR = ("target_format_unreadable", "the file's format cannot be determined")
_UNRECORDED_PAIR = ("target_format_unrecorded", _UNRECORDED_TEXT)


@pytest.mark.parametrize(
    ("fmt_a", "fmt_b", "expected"),
    [
        (None, "csv", [_UNRECORDED_PAIR]),
        ("csv", None, [_UNRECORDED_PAIR]),
        (None, None, [_UNRECORDED_PAIR]),
        ("xml", None, [_UNREADABLE_PAIR, _UNRECORDED_PAIR]),
        (None, "xml", [_UNREADABLE_PAIR, _UNRECORDED_PAIR]),
    ],
)
def test_compare_data_checks_both_sides_before_any_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fmt_a: str | None,
    fmt_b: str | None,
    expected: list,
) -> None:
    def keys(fmt: str | None) -> dict:
        return {} if fmt is None else {"format": fmt}

    result = _compare(
        monkeypatch,
        tmp_path,
        _entry(tmp_path, "pa", **keys(fmt_a)),
        _entry(tmp_path, "pb", **keys(fmt_b)),
    )
    assert sorted(map(tuple, result["refusals"])) == sorted(expected)
    assert result["missing_files"] == [str(tmp_path / "pa"), str(tmp_path / "pb")]
    assert result["table_deltas"] == []


@pytest.mark.parametrize("only_in", ["a", "b"])
def test_compare_data_refuses_a_one_sided_entry_with_no_format(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, only_in: str
) -> None:
    old, none = _entry(tmp_path, "pa"), {}
    side_a, side_b = (old, none) if only_in == "a" else (none, old)
    result = _compare(monkeypatch, tmp_path, side_a, side_b)
    assert [tuple(r) for r in result["refusals"]] == [_UNRECORDED_PAIR]
    assert result["missing_files"] == [str(tmp_path / "pa")]
    assert result["table_deltas"] == []
    assert result["any_data_change"] is False


@pytest.mark.parametrize("only_in", ["a", "b"])
def test_compare_data_keeps_the_delta_for_a_one_sided_current_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, only_in: str
) -> None:
    current, none = _entry(tmp_path, "pa", format="csv"), {}
    side_a, side_b = (current, none) if only_in == "a" else (none, current)
    result = _compare(monkeypatch, tmp_path, side_a, side_b)
    assert result["refusals"] == [] and result["missing_files"] == []
    assert [d["note"] for d in result["table_deltas"]] == ["table only exists in one run"]
    assert result["any_data_change"] is True


def test_every_declared_format_has_a_display_name() -> None:
    from decoy.cli import tokenize

    assert set(tokenize._FORMAT_NAMES) == set(_targets.TARGET_SUFFIX)


def test_a_private_fixed_width_write_is_refused(tmp_path: Path) -> None:
    import pyarrow as pa

    out = tmp_path / "restored.txt"
    with pytest.raises(_targets.TargetFormatError):
        _targets.write_private_table(pa.table({"a": [1]}), "fixed_width", out, {"a": 4})
    assert not out.exists()
