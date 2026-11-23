"""CSV-WRITE-FAST A7 (memory growth) and A9 (speed). Opt in with `DECOY_CSV_SPEED=1`; vm-run only.

These need a quiet Linux node and a few GB of memory, so they skip in the default suite.
A7: the write phase of an already-resident Arrow table must not grow with the row count. The
peak resident-set growth over the post-construction size is measured at N and 4N rows in a fresh
subprocess each, and the difference must stay under `MAX_4X_RSS_GROWTH`.
A9: the three speed bounds of the plan, with the Parquet time as the reference.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("DECOY_CSV_SPEED") != "1", reason="set DECOY_CSV_SPEED=1 on a quiet node"
)

MAX_4X_RSS_GROWTH = 64 * 1024 * 1024
_N = 1_000_000

_CHILD = textwrap.dedent(
    """
    import gc, json, sys, threading, time
    import pyarrow as pa
    from decoy.cli.io import write_table

    def rss():
        with open("/proc/self/statm") as fh:
            return int(fh.read().split()[1]) * 4096

    rows = int(sys.argv[1]); out = sys.argv[2]
    table = pa.table({"s": pa.repeat(pa.scalar("x" * 32), rows),
                      "i": pa.array(range(rows), pa.int64())}).combine_chunks()
    gc.collect()
    base = rss(); peak = [base]; stop = threading.Event()
    def sample():
        while not stop.is_set():
            peak[0] = max(peak[0], rss()); time.sleep(0.002)
    t = threading.Thread(target=sample); t.start()
    write_table(table, "csv", __import__("pathlib").Path(out))
    stop.set(); t.join()
    print(json.dumps({"base": base, "peak": peak[0], "delta": peak[0] - base}))
    """
)


def _delta(rows: int, out: Path) -> int:
    proc = subprocess.run(
        [sys.executable, "-c", _CHILD, str(rows), str(out)],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(json.loads(proc.stdout.splitlines()[-1])["delta"])


def test_a7_write_phase_memory_does_not_scale_with_rows(
    tmp_path: Path, record_property: Callable[[str, object], None]
) -> None:
    small = _delta(_N, tmp_path / "n.csv")
    large = _delta(4 * _N, tmp_path / "4n.csv")
    print(f"A7 RSS delta N={small} 4N={large}")
    assert large - small <= MAX_4X_RSS_GROWTH


def _time(fn) -> float:  # type: ignore[no-untyped-def]
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


def test_a9_generate_csv_is_within_parquet_plus_0_6_seconds(
    tmp_path: Path, record_property: Callable[[str, object], None]
) -> None:
    import pyarrow as pa

    from decoy.cli.io import write_table

    rows = 10_000_000
    table = pa.table({"first_name": pa.array([f"name{i % 5000}" for i in range(rows)])})
    parquet = _time(lambda: write_table(table, "parquet", tmp_path / "t.parquet"))
    csv_time = _time(lambda: write_table(table, "csv", tmp_path / "t.csv"))
    print(f"A9 generate parquet={parquet:.2f}s csv={csv_time:.2f}s")
    assert csv_time <= parquet + 0.6


def test_a9_gzip_csv_10m_rows_is_within_8_seconds(
    tmp_path: Path, record_property: Callable[[str, object], None]
) -> None:
    import pyarrow as pa

    from decoy.cli.io import write_table

    rows = 10_000_000
    table = pa.table(
        {"s": pa.array([f"name{i % 5000}" for i in range(rows)]), "i": pa.array(range(rows))}
    )
    took = _time(lambda: write_table(table, "csv", tmp_path / "t.csv.gz"))
    print(f"A9 gzip csv={took:.2f}s")
    assert took <= 8.0
