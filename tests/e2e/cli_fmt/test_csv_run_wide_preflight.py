"""CSV-WRITE-FAST A5 and A6 (run side): no CSV target is placed before every target passes.

Resident runs go through `write_targets`; chunked runs through the `--chunked` coordinator, which
drains each CSV target's masked stream through `check_csv_types` before any target is staged. The
chunked cases wrap the engine's chunk stream to put a bad type or a changed schema in a later
chunk of the second target, and record when each stream opens, yields and closes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pytest
import yaml
from click.testing import Result
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.io import RunLayout, TargetFormatError, write_targets
from tests.csv_sources import csv_source
from tests.keyed_secret import TEST_MASK_SECRET_REF

pytestmark = pytest.mark.usefixtures("mask_secret")

runner = CliRunner()


def _targets(tmp_path: Path) -> dict[str, Any]:
    return {
        "targets": {
            "a": {"type": "file", "format": "csv", "path": str(tmp_path / "newdir" / "a.csv")},
            "b": {"type": "file", "format": "csv", "path": str(tmp_path / "b.csv")},
        }
    }


@pytest.mark.parametrize(
    "bad",
    [pa.list_(pa.int64()), pa.struct([("x", pa.int64())]), pa.duration("us"), pa.binary()],
    ids=["list", "struct", "duration", "binary"],
)
def test_resident_refusal_precedes_every_target(tmp_path: Path, bad: pa.DataType) -> None:
    outputs = {
        "a": pa.table({"x": [1, 2]}),
        "b": pa.table({"x": [1, 2], "bad": pa.nulls(2, bad)}),
    }
    with pytest.raises(TargetFormatError) as caught:
        write_targets(_targets(tmp_path), outputs, RunLayout.fixed(tmp_path))
    assert caught.value.code == "target.csv_unsupported_type"
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert "'b'" in str(caught.value) and "'bad'" in str(caught.value)
    assert not (tmp_path / "newdir").exists()
    assert not (tmp_path / "b.csv").exists()


def test_resident_refusal_keeps_an_old_target(tmp_path: Path) -> None:
    old = tmp_path / "b.csv"
    old.write_bytes(b"old\n")
    first = tmp_path / "a.csv"
    first.write_bytes(b"older\n")
    config = {
        "targets": {
            "a": {"type": "file", "format": "csv", "path": str(first)},
            "b": {"type": "file", "format": "csv", "path": str(old)},
        }
    }
    outputs = {"a": pa.table({"x": [1]}), "b": pa.table({"x": pa.array([[1]])})}
    with pytest.raises(TargetFormatError):
        write_targets(config, outputs, RunLayout.fixed(tmp_path))
    assert first.read_bytes() == b"older\n"
    assert old.read_bytes() == b"old\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.csv", "b.csv"]


def _chunked_config(tmp_path: Path) -> Path:
    tables, sources, targets = [], {}, {}
    for name in ("a", "b"):
        src = tmp_path / f"{name}.csv"
        pd.DataFrame({"id": [f"{name}{i}" for i in range(6)], "v": list("uvwxyz")}).to_csv(
            src, index=False
        )
        sources[name] = csv_source(src)
        targets[name] = {
            "type": "file",
            "format": "csv",
            "path": str(tmp_path / "out" / f"{name}.csv"),
        }
        tables.append(
            {
                "name": name,
                "columns": [
                    {"name": "id", "strategy": "hash", "namespace": f"{name}_id"},
                    {"name": "v", "strategy": "passthrough"},
                ],
            }
        )
    (tmp_path / "out").mkdir()
    cfg = {
        "version": 2,
        "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
        "sources": sources,
        "tables": tables,
        "targets": targets,
    }
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


Mutate = Callable[[str, int, pa.Table], pa.Table]


def _instrument(monkeypatch: pytest.MonkeyPatch, mutate: Mutate) -> list[tuple]:
    import decoy_engine

    events: list[tuple] = []
    real = decoy_engine.run_mask_pipeline_chunked

    def wrapped(*args: object, table: str, **kwargs: object) -> Iterator[pa.Table]:
        stream = real(*args, table=table, **kwargs)

        def gen() -> Iterator[pa.Table]:
            events.append(("open", table))
            try:
                for index, chunk in enumerate(stream):
                    events.append(("chunk", table, index))
                    yield mutate(table, index, chunk)
            finally:
                events.append(("close", table))

        return gen()

    monkeypatch.setattr(decoy_engine, "run_mask_pipeline_chunked", wrapped)
    return events


def _run(tmp_path: Path) -> Result:
    return runner.invoke(
        app, ["run", str(_chunked_config(tmp_path)), "--chunked", "--chunk-size", "2"]
    )


def _add_list(table: str, index: int, chunk: pa.Table) -> pa.Table:
    if table == "b" and index >= 1:
        return chunk.append_column("l", pa.nulls(chunk.num_rows, pa.list_(pa.int64())))
    return chunk


def _retype(table: str, index: int, chunk: pa.Table) -> pa.Table:
    if table == "b" and index == 1:
        return chunk.set_column(1, "v", chunk.column("v").cast(pa.large_string()))
    return chunk


def _assert_nothing_placed(tmp_path: Path) -> None:
    assert list((tmp_path / "out").iterdir()) == []


@pytest.mark.parametrize(
    ("mutate", "message"),
    [(_add_list, "cannot write"), (_retype, "changed its output schema")],
    ids=["unsupported-type", "drift"],
)
def test_chunked_run_refuses_before_any_target_is_placed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutate: Mutate, message: str
) -> None:
    events = _instrument(monkeypatch, mutate)
    result = _run(tmp_path)
    assert result.exit_code != 0
    assert message in result.output
    _assert_nothing_placed(tmp_path)
    assert events[:2] == [("open", "a"), ("chunk", "a", 0)]
    # Table a's stream is drained and closed before table b's opens.
    assert events.index(("close", "a")) < events.index(("open", "b"))
    assert [e for e in events if e[0] == "chunk" and e[1] == "a"] == [
        ("chunk", "a", i) for i in range(3)
    ]
    assert events.count(("open", "a")) == 1  # nothing reached the publication pass
    assert events[-1] == ("close", "b")


def test_chunked_run_drains_each_stream_then_publishes_with_the_same_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = _instrument(monkeypatch, lambda _t, _i, chunk: chunk)
    result = _run(tmp_path)
    assert result.exit_code == 0, result.output
    opens = [e[1] for e in events if e[0] == "open"]
    assert opens == ["a", "b", "a", "b"]  # validate a, validate b, publish a, publish b
    first_publish = (tmp_path / "out" / "a.csv").read_bytes()
    assert first_publish.startswith(b'"id","v"\n')
    assert first_publish.count(b"\n") == 7


def test_prepared_targets_hold_no_table_batch_or_iterator() -> None:
    import dataclasses

    from decoy.cli.run._execute import _ChunkedTarget

    names = {f.name for f in dataclasses.fields(_ChunkedTarget)}
    assert names == {"name", "src_spec", "tgt_spec", "fmt", "csv_schema"}


def test_validation_keeps_no_masked_chunk_between_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """The drain retains no chunk: each is gone once the next is requested, and the stream closes."""
    import gc
    import weakref

    from decoy.cli.run import _execute

    refs: list[Any] = []
    closed: list[bool] = []

    def stream() -> Iterator[pa.Table]:
        try:
            for i in range(4):
                chunk = pa.table({"a": [i]})
                refs.append(weakref.ref(chunk))
                yield chunk
                del chunk
        finally:
            closed.append(True)

    seen_alive: list[int] = []
    real_check = _execute.check_csv_types

    def spying(*args: object, **kwargs: object) -> pa.Schema:
        gc.collect()
        seen_alive.append(sum(1 for r in refs if r() is not None))
        return real_check(*args, **kwargs)

    monkeypatch.setattr(_execute, "_masked_chunks", lambda *_a, **_k: stream())
    monkeypatch.setattr(_execute, "check_csv_types", spying)
    target = _execute._ChunkedTarget("t", {}, {}, "csv")
    schema = _execute._validate_csv_stream(target, {}, Path(), 1, None)
    assert schema.names == ["a"]
    assert seen_alive == [1, 1, 1, 1]
    assert closed == [True]
