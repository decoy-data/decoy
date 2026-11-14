"""CONFIG-EXPLICIT C1a: every route that reads a declared source checks its columns first.

Engine 0.24.0 already refuses an undeclared column inside `decoy run` and `run --chunked`. The
cells below pin that and cover the routes that read a row before the engine does: `tokenize`,
`demo`, `decoy.mask()` with config, DataFrame and Arrow data, `--duckdb-source`, `subset` and
`detokenize`. The sentry (`tests/sentry/io_policy/test_declared_read_choke_point.py`) pins the
order by construction; these run the routes.

AT-C2  header file runs like inline names, from another working directory (pin on run; red on
       the routes that did not resolve the names file against the YAML).
AT-C3  an undeclared column or table fails before any row read, stage or acquisition.
AT-C4  a headerless file declared `has_header: true` refuses without echoing its first row.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pytest
import yaml
from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.api import mask
from tests.csv_sources import csv_source
from tests.keyed_secret import TEST_MASK_SECRET_REF

pytestmark = pytest.mark.usefixtures("mask_secret")

runner = CliRunner()

_ALL = [
    {"name": "id", "strategy": "passthrough"},
    {"name": "name", "strategy": "hash", "namespace": "name_ns"},
    {"name": "age", "strategy": "passthrough"},
]
_PLAIN = [
    {"name": "id", "strategy": "passthrough"},
    {"name": "name", "strategy": "redact"},
    {"name": "age", "strategy": "passthrough"},
]
_ROWS = [("1", "Alice", "31"), ("2", "Bob", "4"), ("3", "Carol", "57")]
_NAMES = ["id", "name", "age"]


def _write_csv(path: Path, *, header: bool = True, names: list[str] = _NAMES) -> Path:
    lines = ([",".join(names)] if header else []) + [",".join(r) for r in _ROWS]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _config(
    root: Path,
    source: dict[str, Any] | None,
    columns: list[dict[str, Any]],
    *,
    extra_sources: dict[str, Any] | None = None,
    out: str = "out.csv",
) -> Path:
    sources = {} if source is None else {"people": source}
    sources.update(extra_sources or {})
    cfg = {
        "version": 2,
        "global_settings": {"seed": 42, "mask_secret_ref": TEST_MASK_SECRET_REF},
        "sources": sources,
        "tables": [{"name": "people", "columns": columns}],
        "targets": {"people": {"type": "file", "format": "csv", "path": str(root / out)}},
    }
    path = root / "pipeline.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


class _Spies:
    """Counts of the places a row is read, staged or acquired outside the engine's own gate."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import decoy.cli._sources as sources_mod
        import decoy.cli.run._prepare as prepare_mod

        self.calls: list[str] = []
        real_read = sources_mod.read_csv_frame

        def read(*a, **k):
            self.calls.append("read_csv_frame")
            return real_read(*a, **k)

        monkeypatch.setattr(sources_mod, "read_csv_frame", read)
        real_acquire = prepare_mod.acquire_relation

        def acquire(*a, **k):
            self.calls.append("acquire_relation")
            return real_acquire(*a, **k)

        monkeypatch.setattr(prepare_mod, "acquire_relation", acquire)
        import pyarrow.parquet as pq

        real_write = pq.write_table

        def write(*a, **k):
            self.calls.append("write_table")
            return real_write(*a, **k)

        monkeypatch.setattr(pq, "write_table", write)


# ---------------------------------------------------------------- AT-C2


def _two_dirs(tmp_path: Path) -> tuple[Path, Path]:
    cfg_dir, elsewhere = tmp_path / "cfg", tmp_path / "elsewhere"
    cfg_dir.mkdir()
    elsewhere.mkdir()
    return cfg_dir, elsewhere


def _headerless_config(cfg_dir: Path, dialect: dict[str, Any], out: str) -> Path:
    _write_csv(cfg_dir / "people.csv", header=False)
    return _config(cfg_dir, csv_source("people.csv", **dialect), _PLAIN, out=out)


def _run_route(route: str, config: Path, tmp_path: Path) -> None:
    if route == "run":
        result = runner.invoke(app, ["run", str(config)])
        assert result.exit_code == 0, result.output
    elif route == "chunked":
        result = runner.invoke(app, ["run", str(config), "--chunked", "--chunk-size", "2"])
        assert result.exit_code == 0, result.output
    elif route == "mask":
        mask(config=config)
    else:
        from decoy.cli.demo import _run_v2_mask

        _run_v2_mask(config)


@pytest.mark.parametrize("route", ["run", "chunked", "mask", "demo"])
def test_header_file_runs_like_inline_names(
    route: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inline_dir = tmp_path / "inline"
    inline_dir.mkdir()
    inline = _headerless_config(inline_dir, {"has_header": False, "column_names": _NAMES}, "o.csv")
    monkeypatch.chdir(tmp_path)
    _run_route(route, inline, tmp_path)

    file_dir, elsewhere = _two_dirs(tmp_path)
    (file_dir / "header.csv").write_text("id,name,age\n", encoding="utf-8")
    # A decoy header with other names sits in the working directory and must not be read.
    (elsewhere / "header.csv").write_text("x,y,z\n", encoding="utf-8")
    from_file = _headerless_config(
        file_dir, {"has_header": False, "column_names_file": "header.csv"}, "o.csv"
    )
    monkeypatch.chdir(elsewhere)
    _run_route(route, from_file, tmp_path)

    pd.testing.assert_frame_equal(
        pd.read_csv(file_dir / "o.csv", dtype=str), pd.read_csv(inline_dir / "o.csv", dtype=str)
    )


# ---------------------------------------------------------------- AT-C3


_PARTIAL = [c for c in _ALL if c["name"] != "age"]
_SECRET_SOURCE = {"secret": csv_source("secret.csv")}


def _undeclared_column(tmp_path: Path) -> Path:
    _write_csv(tmp_path / "people.csv")
    return _config(tmp_path, csv_source(tmp_path / "people.csv"), _PARTIAL)


def _undeclared_table(tmp_path: Path) -> Path:
    _write_csv(tmp_path / "people.csv")
    (tmp_path / "secret.csv").write_text("ssn,email\n123-45-6789,a@b.c\n", encoding="utf-8")
    cfg = _config(
        tmp_path,
        csv_source(tmp_path / "people.csv"),
        _ALL,
        extra_sources={"secret": csv_source(tmp_path / "secret.csv")},
    )
    raw = yaml.safe_load(cfg.read_text())
    raw["targets"]["secret"] = {
        "type": "file",
        "format": "csv",
        "path": str(tmp_path / "secret_out.csv"),
    }
    cfg.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return cfg


CASES = {
    "column": ("source_file.undeclared_column", _undeclared_column),
    "table": ("source_file.undeclared_table", _undeclared_table),
}


def _assert_refused(text: str, code: str, tmp_path: Path, spies: _Spies) -> None:
    assert code in text
    assert "123-45-6789" not in text and str(tmp_path) not in text
    assert spies.calls == []
    assert not (tmp_path / "out.csv").exists()
    assert not (tmp_path / "secret_out.csv").exists()


@pytest.mark.parametrize("case", sorted(CASES))
@pytest.mark.parametrize("route", ["run", "chunked"])
def test_undeclared_fails_before_any_row_read_cli(
    route: str, case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code, build = CASES[case]
    config = build(tmp_path)
    spies = _Spies(monkeypatch)
    args = ["run", str(config)] + (["--chunked"] if route == "chunked" else [])
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    _assert_refused(result.output, code, tmp_path, spies)


@pytest.mark.parametrize("case", sorted(CASES))
@pytest.mark.parametrize("route", ["path", "dataframe", "arrow"])
def test_undeclared_fails_before_any_row_read_mask(
    route: str, case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from decoy_engine import PipelineValidationError

    code, build = CASES[case]
    config = build(tmp_path)
    spies = _Spies(monkeypatch)
    frame = pd.DataFrame(_ROWS, columns=_NAMES)
    data: Any = {
        "path": None,
        "dataframe": {"people": frame},
        "arrow": {"people": pa.Table.from_pandas(frame, preserve_index=False)},
    }[route]
    if route != "path" and case == "table":
        pytest.skip("the in-memory tables are declared; only the file source is undeclared")
    with pytest.raises(PipelineValidationError) as excinfo:
        mask(data, config)
    _assert_refused(str(excinfo.value), code, tmp_path, spies)


@pytest.mark.parametrize("case", sorted(CASES))
def test_undeclared_fails_before_demo_profiles(
    case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from decoy_engine import PipelineValidationError

    from decoy.cli.demo import _run_v2_mask

    code, build = CASES[case]
    config = build(tmp_path)
    spies = _Spies(monkeypatch)
    import decoy_engine.profile as profile_mod

    def boom(*a, **k):
        raise AssertionError("profile_source ran before the declaration check")

    monkeypatch.setattr(profile_mod, "profile_source", boom)
    with pytest.raises(PipelineValidationError) as excinfo:
        _run_v2_mask(config)
    _assert_refused(str(excinfo.value), code, tmp_path, spies)


def test_undeclared_tokenize_fails_before_any_row_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_csv(tmp_path / "people.csv")
    cols = [
        {"name": "id", "strategy": "passthrough"},
        {"name": "name", "strategy": "tokenize", "namespace": "name_ns"},
    ]
    config = _config(tmp_path, csv_source(tmp_path / "people.csv"), cols)
    spies = _Spies(monkeypatch)
    result = runner.invoke(app, ["tokenize", str(config), "--vault", str(tmp_path / "v.db")])
    assert result.exit_code == 1
    _assert_refused(result.output, "source_file.undeclared_column", tmp_path, spies)
    assert not (tmp_path / "v.db").exists()


def test_undeclared_duckdb_fails_before_acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import duckdb

    db = tmp_path / "in.duckdb"
    con = duckdb.connect(str(db))
    con.register("df", pd.DataFrame(_ROWS, columns=_NAMES))
    con.execute("CREATE TABLE people AS SELECT * FROM df")
    con.close()
    config = _config(tmp_path, None, _PARTIAL)
    spies = _Spies(monkeypatch)
    result = runner.invoke(app, ["run", str(config), "--duckdb-source", f"people={db}"])
    assert result.exit_code == 1
    _assert_refused(result.output, "source_file.undeclared_column", tmp_path, spies)


def _envelope(output: str) -> dict[str, Any]:
    line = next(ln for ln in output.splitlines() if ln.startswith("{"))
    return json.loads(line)


class _DuckSpies:
    """Counts every database access and temp dir of `--duckdb-source` staging (r12.1)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import tempfile

        import decoy.cli._duckdb_source as duck_mod
        import decoy.cli.run._prepare as prepare_mod

        self.describe: list[str] = []
        self.acquire: list[str] = []
        self.tmpdirs: list[str] = []
        real_describe, real_acquire = duck_mod.describe_relation, duck_mod.acquire_relation
        real_mkdtemp = tempfile.mkdtemp

        def describe(*a, **k):
            self.describe.append("describe")
            return real_describe(*a, **k)

        def acquire(*a, **k):
            self.acquire.append("acquire")
            return real_acquire(*a, **k)

        def mkdtemp(*a, **k):
            if k.get("prefix") == "decoy-duckdb-":
                self.tmpdirs.append("mkdtemp")
            return real_mkdtemp(*a, **k)

        monkeypatch.setattr(duck_mod, "describe_relation", describe)
        monkeypatch.setattr(duck_mod, "acquire_relation", acquire)
        monkeypatch.setattr(prepare_mod, "acquire_relation", acquire)
        monkeypatch.setattr(tempfile, "mkdtemp", mkdtemp)

    def untouched(self) -> bool:
        return self.describe == [] and self.acquire == [] and self.tmpdirs == []


def _duck_db(tmp_path: Path) -> Path:
    import duckdb

    db = tmp_path / "in.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE people AS SELECT 1 AS id, 'a' AS name, '3' AS age")
    con.close()
    return db


def test_unparseable_config_keeps_the_gate_error_on_duckdb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _duck_db(tmp_path)
    config = _config(tmp_path, None, _PARTIAL)
    raw = yaml.safe_load(config.read_text())
    raw["version"] = "not-a-version"
    config.write_text(yaml.safe_dump(raw), encoding="utf-8")
    spies = _DuckSpies(monkeypatch)
    result = runner.invoke(app, ["run", str(config), "--duckdb-source", f"people={db}", "--json"])
    assert result.exit_code == 1
    assert "undeclared_column" not in result.output
    # Config validity first (r12.1): no describe, no acquisition, no temp dir for it.
    assert spies.untouched()
    envelope = _envelope(result.output)
    assert envelope["error_kind"] == "validation"
    assert any(m["code"] == "literal_error" for m in envelope["messages"])


def test_a_malformed_flag_refuses_before_any_relation_is_acquired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _duck_db(tmp_path)
    config = _config(tmp_path, None, _ALL)
    spies = _DuckSpies(monkeypatch)
    result = runner.invoke(
        app, ["run", str(config), "--duckdb-source", f"people={db}", "--duckdb-source", "nope"]
    )
    assert result.exit_code == 1
    assert "--duckdb-source: expected TABLE=DB_PATH, got 'nope'" in result.output
    assert spies.untouched()


def test_an_undeclared_flag_table_refuses_before_any_relation_is_acquired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _duck_db(tmp_path)
    config = _config(tmp_path, None, _ALL)
    spies = _DuckSpies(monkeypatch)
    result = runner.invoke(
        app,
        ["run", str(config), "--duckdb-source", f"people={db}", "--duckdb-source", f"ghost={db}"],
    )
    assert result.exit_code == 1
    assert "'ghost' is not a table in the pipeline" in result.output
    assert spies.untouched()


def _subset_config(tmp_path: Path, columns: list[dict[str, Any]]) -> Path:
    config = _config(tmp_path, csv_source(tmp_path / "people.csv"), columns)
    raw = yaml.safe_load(config.read_text())
    raw["subset"] = {
        "seeds": [{"table": "people", "mode": "sample", "key_columns": ["id"], "fraction": 0.5}]
    }
    config.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return config


def test_undeclared_subset_refuses_before_the_engine_opens_a_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import decoy_engine.subset as subset_mod

    def boom(*a, **k):
        raise AssertionError("the engine subset ran before the declaration check")

    monkeypatch.setattr(subset_mod, "plan_subset", boom)
    monkeypatch.setattr(subset_mod, "run_subset", boom)
    _write_csv(tmp_path / "people.csv")
    config = _subset_config(tmp_path, _PARTIAL)
    result = runner.invoke(app, ["subset", str(config), "--dry-run"])
    assert result.exit_code == 1
    assert "source_file.undeclared_column" in result.output


@pytest.mark.parametrize("flag", [[], ["--json"]])
def test_subset_with_a_missing_source_is_a_coded_refusal(flag: list[str], tmp_path: Path) -> None:
    config = _subset_config(tmp_path, _PLAIN)
    result = runner.invoke(app, ["subset", str(config), "--dry-run", *flag])
    assert result.exit_code == 1
    assert "source_file.file_not_found" in result.output
    assert "internal error" not in result.output
    assert "people.csv" not in result.output
    if flag:
        assert json.loads(result.output)["code"] == "source_file.file_not_found"
    else:
        assert result.output.count("source_file.file_not_found") == 1


def test_a_malformed_source_is_a_coded_value_free_refusal(tmp_path: Path) -> None:
    (tmp_path / "people.csv").write_bytes(b"\xff\xfe\x00zz_marker\n1\n")
    config = _subset_config(tmp_path, _PLAIN)
    result = runner.invoke(app, ["subset", str(config), "--dry-run", "--json"])
    assert result.exit_code == 1
    assert "internal error" not in result.output
    assert "zz_marker" not in result.output and "people.csv" not in result.output
    assert json.loads(result.output)["code"] == "csv_malformed"


# ---------------------------------------------------------------- AT-C4


def test_headerless_file_declared_headered_refuses_without_echoing_a_value(
    tmp_path: Path,
) -> None:
    names = ["zz_marker_a", "zz_marker_b", "zz_marker_c"]
    (tmp_path / "people.csv").write_text("zz_marker_a,zz_marker_b,zz_marker_c\n1,2,3\n")
    config = _config(tmp_path, csv_source(tmp_path / "people.csv"), _ALL)
    for args in (["run", str(config)], ["run", str(config), "--json"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 1
        assert "source_file.undeclared_column" in result.output
        assert not any(n in result.output for n in names)
    assert not (tmp_path / "out.csv").exists()


# ---------------------------------------------------------------- r12.3 refusal contract


def _tokenize_config(tmp_path: Path) -> Path:
    cols = [
        {"name": "id", "strategy": "passthrough"},
        {"name": "name", "strategy": "tokenize", "namespace": "name_ns"},
        {"name": "age", "strategy": "passthrough"},
    ]
    return _config(tmp_path, csv_source(tmp_path / "people.csv"), cols)


_BROKEN = {
    "missing": ("source_file.file_not_found", None),
    "malformed": ("csv_malformed", b"\xff\xfe\x00zz_marker\n1\n"),
}


def _assert_one_coded_refusal(result: Any, code: str, *, as_json: bool) -> None:
    assert result.exit_code == 1, result.output
    out = result.output
    assert "internal error" not in out and "zz_marker" not in out and "people.csv" not in out
    if as_json:
        envelope = _envelope(out)
        assert envelope["code"] == code
        assert code not in envelope["error"]
    else:
        assert out.count(code) == 1


@pytest.mark.parametrize("kind", sorted(_BROKEN))
@pytest.mark.parametrize("as_json", [False, True])
def test_tokenize_refuses_a_broken_source_once_with_its_code(
    kind: str, as_json: bool, tmp_path: Path
) -> None:
    code, data = _BROKEN[kind]
    if data is not None:
        (tmp_path / "people.csv").write_bytes(data)
    config = _tokenize_config(tmp_path)
    args = ["tokenize", str(config), "--vault", str(tmp_path / "v.db")]
    result = runner.invoke(app, args + (["--json"] if as_json else []))
    _assert_one_coded_refusal(result, code, as_json=as_json)
    assert not (tmp_path / "v.db").exists()


@pytest.mark.parametrize("kind", sorted(_BROKEN))
@pytest.mark.parametrize("as_json", [False, True])
def test_demo_refuses_a_broken_source_once_with_its_code(
    kind: str, as_json: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import decoy.cli.demo as demo_mod

    code, data = _BROKEN[kind]
    real = demo_mod._run_v2_mask

    def broken(pipeline_yaml: Path, *a: Any, **k: Any) -> Any:
        sample = pipeline_yaml.parent / "customers.csv"
        if data is None:
            sample.unlink()
        else:
            sample.write_bytes(data)
        return real(pipeline_yaml, *a, **k)

    monkeypatch.setattr(demo_mod, "_run_v2_mask", broken)
    args = ["demo", "--dir", str(tmp_path / "d")] + (["--json"] if as_json else [])
    result = runner.invoke(app, args)
    _assert_one_coded_refusal(result, code, as_json=as_json)


@pytest.mark.parametrize("kind", sorted(_BROKEN))
def test_a_read_refusal_carries_no_cause_or_context(kind: str, tmp_path: Path) -> None:
    from decoy_engine import PipelineValidationError

    from decoy.cli._sources import prepared_sources

    code, data = _BROKEN[kind]
    if data is not None:
        (tmp_path / "people.csv").write_bytes(data)
    config = yaml.safe_load(
        _config(tmp_path, csv_source(tmp_path / "people.csv"), _PLAIN).read_text()
    )
    with pytest.raises(PipelineValidationError) as excinfo:
        prepared_sources(config, base_dir=tmp_path)
    assert excinfo.value.code == code
    assert excinfo.value.__cause__ is None and excinfo.value.__context__ is None
