"""`decoy scan` and `decoy demo` make one engine call through `decoy.cli.scanning` (freeze item 3 C1).

The expected documents are computed in the same run with the arguments `run_scan` passed to the
engine before the refactor (`sample_rows` from `--rows`, `strategy` from `--rows 0` or
`--strategy`), never from bytes recorded at an older commit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from typer.testing import CliRunner

from decoy.__main__ import app

runner = CliRunner()
_EPOCH = "1970-01-01T00:00:00+00:00"


def _csv(path: Path) -> Path:
    pd.DataFrame({"id": range(40), "mail": [f"u{i}@example.com" for i in range(40)]}).to_csv(
        path, index=False
    )
    return path


def _parquet(path: Path) -> Path:
    pd.DataFrame({"pid": range(12), "note": ["x"] * 12}).to_parquet(path)
    return path


def _fixed(path: Path) -> tuple[Path, Path]:
    path.write_text("".join(f"{i:03d}ab{i % 7}\n" for i in range(30)), encoding="utf-8")
    layout = path.with_suffix(".yaml")
    layout.write_text(
        "columns:\n"
        "  - {name: a, start: 0, width: 3}\n"
        "  - {name: b, start: 3, width: 2}\n"
        "  - {name: c, start: 5, width: 1}\n",
        encoding="utf-8",
    )
    return path, layout


def _norm(doc: dict[str, Any]) -> dict[str, Any]:
    return {**doc, "scanned_at": _EPOCH}


@pytest.fixture
def engine_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Records each `scan_sources` call made through the shared module."""
    import decoy_engine

    import decoy.cli.scanning._engine_call  # noqa: F401  (red until the choke point exists)

    calls: list[dict[str, Any]] = []
    real = decoy_engine.scan_sources

    def spy(descriptors: Any, **kwargs: Any):
        calls.append(kwargs)
        return real(descriptors, **kwargs)

    monkeypatch.setattr(decoy_engine, "scan_sources", spy)
    return calls


def _expected(
    path: Path,
    *,
    row_cap: int | None,
    effective: str,
    has_header: bool | None = True,
    layout: Path | None = None,
    detectors: bool = False,
) -> dict[str, Any]:
    """The pre-refactor call, spelled out: what `run_scan` did before `scan_descriptors`."""
    from decoy_engine import scan_set_to_dict, scan_sources

    from decoy.cli.scanning import resolve_sources

    descriptors, _ = resolve_sources(
        [path], fmt=None, layout=layout, has_header=has_header, column_names=None
    )
    pre_scan = None
    if detectors:
        from decoy.cli.scanning import _detectors

        pre_scan = _detectors.resolve_pre_scan("regex", None)
    result = scan_sources(
        descriptors,
        sample_rows=row_cap,
        strategy=effective,
        pre_scan=pre_scan,  # type: ignore[arg-type]
    )
    return scan_set_to_dict(result, detail=False)


def _cells(tmp_path: Path) -> list[tuple[str, list[str], dict[str, Any]]]:
    csv = _csv(tmp_path / "c.csv")
    pq = _parquet(tmp_path / "p.parquet")
    fw, layout = _fixed(tmp_path / "f.fwf")
    flag = ["--has-header"]
    return [
        (
            "csv default rows",
            [str(csv), *flag],
            {"path": csv, "row_cap": 10_000, "effective": "head"},
        ),
        (
            "csv rows 0",
            [str(csv), *flag, "--rows", "0"],
            {"path": csv, "row_cap": None, "effective": "full"},
        ),
        (
            "csv rows 5 random",
            [str(csv), *flag, "--rows", "5", "--strategy", "random"],
            {"path": csv, "row_cap": 5, "effective": "random"},
        ),
        (
            "parquet",
            [str(pq)],
            {"path": pq, "row_cap": 10_000, "effective": "head", "has_header": None},
        ),
        (
            "fixed width layout file",
            [str(fw), "--layout", str(layout)],
            {
                "path": fw,
                "row_cap": 10_000,
                "effective": "head",
                "has_header": None,
                "layout": layout,
            },
        ),
        (
            "csv detectors regex",
            [str(csv), *flag, "--detectors", "regex"],
            {"path": csv, "row_cap": 10_000, "effective": "head", "detectors": True},
        ),
    ]


@pytest.mark.parametrize("index", range(6))
def test_at0_output_file_matches_the_pre_refactor_engine_call(
    tmp_path: Path, engine_calls: list[dict[str, Any]], index: int
) -> None:
    label, argv, expect = _cells(tmp_path)[index]
    out = tmp_path / "o.json"
    result = runner.invoke(app, ["scan", *argv, "--output", str(out)])
    assert result.exit_code == 0, f"{label}: {result.output}"
    assert len(engine_calls) == 1, label
    want = _expected(**expect)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert json.dumps(_norm(saved), indent=2) == json.dumps(_norm(want), indent=2), label


def test_at0_output_dash_streams_compact_json_and_a_newline(
    tmp_path: Path, engine_calls: list[dict[str, Any]]
) -> None:
    csv = _csv(tmp_path / "c.csv")
    result = runner.invoke(app, ["scan", str(csv), "--has-header", "--output", "-"])
    assert result.exit_code == 0, result.output
    assert len(engine_calls) == 1
    want = _expected(csv, row_cap=10_000, effective="head")
    streamed = json.loads(result.stdout)
    assert result.stdout == json.dumps(streamed) + "\n"
    assert _norm(streamed) == _norm(want)


def test_at9_demo_scan_json_is_core_bytes_and_goes_through_the_shared_call(
    tmp_path: Path, engine_calls: list[dict[str, Any]]
) -> None:
    from decoy.cli.scanning import core_bytes

    work = tmp_path / "demo"
    result = runner.invoke(app, ["demo", "--dir", str(work)])
    assert result.exit_code == 0, result.output
    assert len(engine_calls) == 1
    assert engine_calls[0]["sample_rows"] is None
    assert engine_calls[0]["strategy"] == "full"
    raw = (work / "scan.json").read_bytes()
    assert raw == core_bytes(json.loads(raw))
    assert b"\n  " in raw  # indent=2, not compact


def test_at14_negative_rows_is_a_usage_error_before_the_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import decoy_engine

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("the engine was called")

    monkeypatch.setattr(decoy_engine, "scan_sources", boom)
    csv = _csv(tmp_path / "f.csv")
    result = runner.invoke(app, ["scan", str(csv), "--has-header", "--rows", "-1"])
    assert result.exit_code == 1, result.output
    assert "rows must be 0 or more" in result.output
