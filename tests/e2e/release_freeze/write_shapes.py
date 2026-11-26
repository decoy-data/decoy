"""Build and write the `--json` shape snapshot (REL-GATE 5.2).

A shape keeps key paths and JSON types and never a cell value. Object keys can carry data (a map
keyed by table or column name), so each command declares those maps in ``DYNAMIC`` and their keys
collapse to ``*``. Two lists keep "content varies by host" apart from "key may be absent":
``OPAQUE`` names keys that are always present but whose content varies, and the shape keeps their
declared type only, so the key cannot vanish unseen. ``OPTIONAL`` names keys that appear only on some
paths; they are left out of the shape, so the snapshot covers the listed paths only.

A person regenerates the snapshot and reviews the diff:

    python -m tests.e2e.release_freeze.write_shapes

No environment switch regenerates it, and the test never writes it.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd
from typer.testing import CliRunner

from decoy.__main__ import app

SNAPSHOT = Path(__file__).resolve().parents[2] / "fixtures" / "release_freeze" / "json-shapes.json"
MARKER_COL = "zzmarkercol"
MARKER_VAL = "zzmarkerval"
SECRET_ENV = "DECOY_RG_F2_SECRET"

# Commands with `--json` and no good input in a test environment, each with its reason.
EXEMPT: dict[str, str] = {
    "doctor": "the check list depends on the installed extras and the host",
    "schema": "prints the engine PipelineConfig schema, pinned by the engine snapshot",
    "setup": "writes the user's settings file outside the test directory",
    "upgrade": "manages a bundled install and refuses a pip or dev install",
}

# Per command: pointers of maps whose keys are data (table, column or file names), pointers of keys
# that are always present with host-varying content (kept as a declared type), and pointers of keys
# present on some paths only (left out). A pointer is the object keys from the root, joined by
# `/`; arrays are walked without a segment.
DYNAMIC: dict[str, list[str]] = {
    "fit": ["/columns", "/null_rates"],
    "library show": ["/record/payload/table_rows", "/record/payload/subset_seed_counts"],
    "report show": [
        "/manifest/input_fingerprints",
        "/manifest/output_fingerprints",
        "/manifest/row_counts",
    ],
}
OPAQUE: dict[str, dict[str, str]] = {
    "info": {"/native_companion": "null|object"},
    # Each row's fields are null or text by whether that model can run on this host.
    "models list": {
        "/models/version": "null|string",
        "/models/runtime_version": "null|string",
        "/models/reason": "null|string",
        "/models/cause": "null|string",
        "/models/hint": "null|string",
    },
    # `library` is always present; its members depend on the store outcome (plan 4.16, 4.17).
    "run": {"/library": "object", "/warnings": "array"},
}
OPTIONAL: dict[str, list[str]] = {
    # `_render.py` adds each of these only when the run used the feature.
    "run": ["/native_route", "/notify", "/report", "/subset"],
    # The engine's out-of-core residency warning sets `resident_source` only for a source passed
    # resident; a plain run now passes a local source lazily, so the key depends on the path.
    "report show": ["/manifest/warnings/detail/resident_source"],
}

# A command whose failing document also has a pinned shape: the first `messages` entry of a run
# that exits 1 on a `.decoy` loader finding, which carries `position`. The success shape pins `messages` as `[]`, so a position field on an error entry
# could vanish unseen. Each value is the pipeline file the step reads (written by the workspace).
ERROR_STEPS: dict[str, str] = {"validate config": "bad.decoy"}
ERROR_SUFFIX = " (error entry)"
_BAD_DECOY = """decoy 1

pipeline {
  mask patients from csv("patients.csv", header: true) to csv("out/patients.csv") {
    ssn : redact
  }
}
"""

_TYPES = {bool: "boolean", int: "integer", float: "number", str: "string", type(None): "null"}


def _kind(value: Any) -> str:
    """The top-level JSON kind of ``value``: `object`, `array` or a scalar type."""
    if isinstance(value, dict):
        return "object"
    return "array" if isinstance(value, list) else _TYPES[type(value)]


def shape_of(
    value: Any,
    dynamic: list[str] | None = None,
    optional: list[str] | None = None,
    opaque: dict[str, str] | None = None,
    _at: str = "",
) -> Any:
    """Reduce ``value`` to key paths and JSON types; never copy a cell value.

    A key in ``opaque`` keeps its declared type string and nothing below it; a value of a kind the
    declaration does not list raises, so the declaration cannot go stale unseen.
    """
    dynamic, optional, opaque = dynamic or [], optional or [], opaque or {}
    if isinstance(value, dict):
        collapse = _at in dynamic
        out: dict[str, Any] = {}
        for key, sub in value.items():
            at = f"{_at}/{key}"
            if at in optional:
                continue
            if at in opaque:
                if _kind(sub) not in opaque[at].split("|"):
                    raise ValueError(f"{at} is {_kind(sub)}, declared {opaque[at]}")
                out[key] = opaque[at]
                continue
            child = shape_of(sub, dynamic, optional, opaque, f"{_at}/*" if collapse else at)
            if collapse:
                out["*"] = _merge(out.get("*"), child)
            else:
                out[key] = child
        return dict(sorted(out.items()))
    if isinstance(value, list):
        merged: Any = None
        for item in value:
            merged = _merge(merged, shape_of(item, dynamic, optional, opaque, _at))
        return [] if merged is None else [merged]
    return _TYPES[type(value)]


def flatten(shape: Any, at: str = "") -> dict[str, str]:
    """One line per key path, so a snapshot diff names the path that changed.

    An array adds `[]` to its path; an empty array or object is a leaf of its own. A key seen as
    several kinds (`null|object`) is a leaf of its own and keeps the sub-paths of its object.
    """
    if isinstance(shape, dict) and "|" in shape:
        out = {at or "/": shape["|"]}
        if shape.get("{}"):
            out.update(flatten(shape["{}"], at))
        if shape.get("[]") is not None:
            out.update(flatten(shape["[]"], f"{at}[]"))
        return out
    if isinstance(shape, dict) and shape:
        return {k: v for key, sub in shape.items() for k, v in flatten(sub, f"{at}/{key}").items()}
    if isinstance(shape, list) and shape:
        return flatten(shape[0], f"{at}[]")
    return {at or "/": "[]" if isinstance(shape, list) else "{}" if shape == {} else shape}


def _parts(shape: Any) -> tuple[set[str], Any, Any]:
    """Split a shape into its kinds, its object shape and its array item shape."""
    if isinstance(shape, dict) and "|" in shape:
        return set(shape["|"].split("|")), shape.get("{}"), shape.get("[]")
    if isinstance(shape, dict):
        return {"object"}, shape, None
    if isinstance(shape, list):
        return {"array"}, None, shape[0] if shape else None
    return set(shape.split("|")), None, None


def _union_objects(a: dict | None, b: dict | None) -> dict | None:
    if a is None or b is None:
        return a if b is None else b
    return {k: _merge(a.get(k), b.get(k)) for k in sorted({*a, *b})}


def _join(a: Any, b: Any) -> Any:
    return b if a is None else a if b is None else _merge(a, b)


def _merge(a: Any, b: Any) -> Any:
    """Union of two shapes, the same in either order.

    Object keys are unioned and differing kinds are joined with `|`. An object seen beside a scalar
    keeps its sub-paths: the result is ``{"|": "null|object", "{}": {...}}``.
    """
    if a is None:
        return b
    if b is None:
        return a
    (ka, oa, ia), (kb, ob, ib) = _parts(a), _parts(b)
    kinds, obj, item = ka | kb, _union_objects(oa, ob), _join(ia, ib)
    if kinds == {"object"} and obj is not None:
        return obj
    if kinds == {"array"}:
        return [] if item is None else [item]
    joined = "|".join(sorted(kinds))
    if obj is None and item is None:
        return joined
    out: dict[str, Any] = {"|": joined}
    if obj is not None:
        out["{}"] = obj
    if item is not None:
        out["[]"] = item
    return out


_PIPELINE = """version: 2
global_settings: {seed: 7}
sources:
  patients: {type: file, path: patients.csv, format: csv, has_header: true}
  visits: {type: file, path: visits.csv, format: csv, has_header: true}
targets:
  patients: {type: file, path: out/patients.csv, format: csv}
  visits: {type: file, path: out/visits.csv, format: csv}
tables:
  - name: patients
    columns:
      - {name: patient_id, strategy: hash, namespace: patient_ids}
      - {name: full_name, strategy: redact}
      - {name: ssn, strategy: redact}
      - {name: MARKER_COL, strategy: redact}
  - name: visits
    columns:
      - {name: patient_id, strategy: hash, namespace: patient_ids}
      - {name: diagnosis, strategy: redact}
relationships:
  - parent: {table: patients, columns: [patient_id]}
    children:
      - {table: visits, columns: [patient_id]}
    orphan_policy: fail
    namespace: patient_ids
""".replace("MARKER_COL", MARKER_COL)

# The `run` step's pipeline: post-scan integrity on, so `run --json` carries its `post_scan`
# block. `full_name` is hashed because a redacted name column is a regex `fail` that blocks.
_INTEGRITY = (
    _PIPELINE.replace(
        "{name: full_name, strategy: redact}", "{name: full_name, strategy: hash, namespace: names}"
    )
    + "post_scan: {integrity: true}\n"
)

_TOKENIZE = """version: 2
global_settings: {seed: 7, mask_secret_ref: "env:SECRET_ENV"}
sources:
  patients: {type: file, path: patients.csv, format: csv, has_header: true}
targets:
  patients: {type: file, path: tokenized.csv, format: csv}
tables:
  - name: patients
    columns:
      - {name: patient_id, strategy: passthrough}
      - {name: full_name, strategy: tokenize, namespace: people.name}
      - {name: ssn, strategy: redact}
      - {name: MARKER_COL, strategy: redact}
""".replace("MARKER_COL", MARKER_COL).replace("SECRET_ENV", SECRET_ENV)

_VAULTED = """version: 2
global_settings: {seed: 7, mask_secret_ref: "env:SECRET_ENV"}
sources:
  patients: {type: file, path: patients.csv, format: csv, has_header: true}
targets:
  patients: {type: file, path: vaulted.csv, format: csv}
tables:
  - name: patients
    columns:
      - {name: patient_id, strategy: passthrough}
      - {name: full_name, strategy: hash, namespace: names, vault: true}
      - {name: ssn, strategy: redact}
      - {name: MARKER_COL, strategy: redact}
""".replace("MARKER_COL", MARKER_COL).replace("SECRET_ENV", SECRET_ENV)


_SUBSET = """version: 2
global_settings: {seed: 7}
sources:
  cust: {type: file, path: cust.parquet, format: parquet}
  orders: {type: file, path: orders.parquet, format: parquet}
targets:
  cust: {type: file, path: out_cust.parquet, format: parquet}
  orders: {type: file, path: out_orders.parquet, format: parquet}
tables:
  - {name: cust, columns: [{name: id, strategy: passthrough}]}
  - {name: orders, columns: [{name: id, strategy: passthrough}, {name: cust_id, strategy: passthrough}]}
relationships:
  - parent: {table: cust, columns: [id]}
    children:
      - {table: orders, columns: [cust_id]}
    orphan_policy: fail
subset:
  seeds:
    - {table: cust, mode: sample, key_columns: [id], fraction: 0.5}
"""


def build_workspace(root: Path) -> None:
    """Write the synthetic inputs: a parent and child table, one marker column and cell."""
    rows = [(i, f"Person {i}", f"000-00-000{i}", MARKER_VAL) for i in range(1, 6)]
    head = f"patient_id,full_name,ssn,{MARKER_COL}\n"
    (root / "patients.csv").write_text(
        head + "".join(f"{a},{b},{c},{d}\n" for a, b, c, d in rows), encoding="utf-8"
    )
    (root / "visits.csv").write_text(
        "patient_id,diagnosis\n" + "".join(f"{i},flu\n" for i in range(1, 6)), encoding="utf-8"
    )
    (root / "pipeline.yaml").write_text(_PIPELINE, encoding="utf-8")
    (root / "bad.decoy").write_text(_BAD_DECOY, encoding="utf-8")
    (root / "integrity.yaml").write_text(_INTEGRITY, encoding="utf-8")
    (root / "tokenize.yaml").write_text(_TOKENIZE, encoding="utf-8")
    (root / "vaulted.yaml").write_text(_VAULTED, encoding="utf-8")
    (root / "subset.yaml").write_text(_SUBSET, encoding="utf-8")
    pd.DataFrame({"id": range(1, 11)}).to_parquet(root / "cust.parquet")
    pd.DataFrame({"id": range(1, 21), "cust_id": [i % 10 + 1 for i in range(20)]}).to_parquet(
        root / "orders.parquet"
    )
    wheels = root / "wheels"
    wheels.mkdir()
    for name in ("en_core_web_sm-3.8.0-py3-none-any.whl", "spacy-3.8.18-py3-none-any.whl"):
        (wheels / name).write_bytes(b"not a real wheel")


@contextlib.contextmanager
def _fake_installer() -> Iterator[None]:
    """`models install` with its one installer seam replaced: no network, nothing installed.

    The success document is the real one; only the subprocess and the probes it reads are fakes.
    """
    from unittest import mock

    from decoy_engine import ModelStatus

    from decoy.cli.models import _install

    done = {"ran": False}
    before = (("decoy-cli", "0.1.0"), ("numpy", "2.2.6"))
    after = (*before, ("en-core-web-sm", "3.8.0"), ("spacy", "3.8.18"))

    def run(argv: list[str]) -> int:
        done["ran"] = True
        return 0

    def status(model: str = "en_core_web_sm") -> ModelStatus:
        if done["ran"]:
            return ModelStatus("ner", model, True, "3.8.0", "3.8.18", None)
        return ModelStatus("ner", model, False, None, None, "provider.ner_spacy_not_installed")

    with (
        mock.patch.object(_install, "run_installer", run),
        mock.patch.object(_install, "pip_available", lambda: True),
        mock.patch.object(_install, "managed_home", lambda: None),
        mock.patch.object(_install, "ner_status", status),
        mock.patch.object(
            _install, "installed_distribution_set", lambda: after if done["ran"] else before
        ),
    ):
        yield


@contextlib.contextmanager
def _inside(root: Path) -> Iterator[None]:
    before, secret = Path.cwd(), os.environ.get(SECRET_ENV)
    os.environ[SECRET_ENV] = "ab" * 32
    os.chdir(root)
    try:
        yield
    finally:
        os.chdir(before)
        if secret is None:
            os.environ.pop(SECRET_ENV, None)
        else:
            os.environ[SECRET_ENV] = secret


class Found:
    """An output file an earlier step wrote under a run folder, located when the step runs."""

    def __init__(self, name: str) -> None:
        self.name = name

    def path(self) -> str:
        return str(next(Path.cwd().rglob(self.name)))


def _steps() -> list[tuple[str, list[Any]]]:
    """Each `--json` leaf command once, in an order where earlier steps feed later ones."""
    mask = ["--mask-secret", f"env:{SECRET_ENV}"]
    return [
        ("scan", ["scan", "patients.csv", "--has-header"]),
        ("scan fields", ["scan", "fields", "scan.json"]),
        ("scan show", ["scan", "show", "scan.json", "ssn"]),
        ("scan diff", ["scan", "diff", "scan.json", "scan2.json"]),
        ("run", ["run", "integrity.yaml", *mask]),
        ("report show", ["report", "show", "ev1.json"]),
        ("report render", ["report", "render", "ev1.json", "-o", "report.html"]),
        ("report verify", ["report", "verify", "ev1.json"]),
        ("report diff", ["report", "diff", "ev1.json", "ev2.json"]),
        ("report fidelity", ["report", "fidelity", "patients.csv", "patients.csv"]),
        ("tokenize", ["tokenize", "tokenize.yaml", "--vault", "v.db"]),
        ("report vault", ["report", "vault", "vault.bin", "--config", "vaulted.yaml"]),
        ("detokenize", ["detokenize", "tokenize.yaml", Found("tokenized.csv"), "--vault", "v.db"]),
        ("unmask", ["unmask", "vaulted.yaml", Found("vaulted.csv"), "--vault", "vault.bin"]),
        (
            "report integrity",
            ["report", "integrity", Found("patients.csv"), "--source", "patients.csv"],
        ),
        ("subset", ["subset", "subset.yaml", "--dry-run"]),
        ("validate", ["validate", "pipeline.yaml"]),
        ("validate config", ["validate", "config", "pipeline.yaml"]),
        ("validate compile", ["validate", "compile", "pipeline.yaml"]),
        ("validate preflight", ["validate", "preflight", "pipeline.yaml"]),
        ("explain", ["explain", "keys"]),
        ("list", ["list", "templates"]),
        ("show", ["show", "template", "minimal"]),
        ("info", ["info"]),
        ("models list", ["models", "list"]),
        ("models install", ["models", "install", "ner", "--from", "wheels", "--yes"]),
        ("demo", ["demo"]),
        ("init", ["init", "--preset", "minimal", "-o", "minimal.yaml"]),
        ("fit", ["fit", "patients.csv"]),
        ("library list", ["library", "list", "--library", "lib"]),
        ("library show", ["library", "show", "sample-run/latest", "--library", "lib"]),
        (
            "library diff",
            ["library", "diff", "sample-run/latest~1", "sample-run/latest", "--library", "lib"],
        ),
        ("project new", ["project", "new", "proj"]),
        ("project list", ["project", "list", "."]),
        ("project show", ["project", "show"]),
    ]


def _seed_library(root: Path) -> None:
    """Two `sample-run` records, a day apart, for `library list`, `show` and `diff`."""
    from datetime import datetime, timezone

    from decoy_engine import records

    from decoy.cli.library import open_library

    library = open_library(root)
    for n in (1, 2):
        payload = {
            "sample_size": n,
            "root_table": MARKER_COL,
            "table_rows": {MARKER_COL: n},
            "subset_seed_counts": {MARKER_COL: n},
            "approximate_columns": (),
            "scratch_dir": "scratch/sample",
            "outputs": (),
            "ttl_seconds": 60,
        }
        library.put(
            records.build(
                "sample-run",
                payload,
                producer={"name": "decoy-cli", "version": "0.0.0", "engine_version": "0.0.0"},
                invocation_id="0b6c9a3e-1d2f-4c5b-8a7e-9f0e1d2c3b4a",
                created_at=datetime(2026, 11, n, tzinfo=timezone.utc),
            )
        )


def capture(root: Path) -> dict[str, Any]:
    """Run every `--json` command once on the workspace and return each parsed document."""
    runner = CliRunner()
    docs: dict[str, Any] = {}

    def call(argv: list[Any]) -> Any:
        argv = [a.path() if isinstance(a, Found) else a for a in argv]
        result = runner.invoke(app, [*argv, "--json"])
        assert result.exit_code == 0, (
            f"{' '.join(argv)} exited {result.exit_code}: {result.stdout}{result.stderr}"
        )
        return json.loads(result.stdout)

    build_workspace(root)
    with _inside(root):
        for name, argv in _steps():
            if name == "scan fields":
                for out in ("scan.json", "scan2.json"):
                    runner.invoke(app, ["scan", "patients.csv", "--has-header", "-o", out])
            if name in ("report show", "report diff"):
                evidence = "ev1.json" if name == "report show" else "ev2.json"
                runner.invoke(
                    app,
                    [
                        "run",
                        "pipeline.yaml",
                        "--mask-secret",
                        f"env:{SECRET_ENV}",
                        "--evidence-out",
                        evidence,
                    ],
                )
            if name == "report vault":
                runner.invoke(app, ["run", "vaulted.yaml", "--vault", "vault.bin"])
            if name == "library list":
                _seed_library(root / "lib")
            if name == "project show":
                os.chdir(root / "proj")
            if name == "models install":
                with _fake_installer():
                    docs[name] = call(argv)
                continue
            docs[name] = call(argv)
        docs.update(_error_entries(runner, root))
    return docs


def _error_entries(runner: CliRunner, root: Path) -> dict[str, Any]:
    """The first `messages` entry of each failing step, keyed by command plus `ERROR_SUFFIX`."""
    out: dict[str, Any] = {}
    for name, source in ERROR_STEPS.items():
        result = runner.invoke(app, [*name.split(), str(root / source), "--json"])
        assert result.exit_code == 1, f"{name} exited {result.exit_code}: {result.stdout}"
        out[name + ERROR_SUFFIX] = json.loads(result.stdout)["messages"][0]
    return out


def snapshot() -> dict[str, Any]:
    """The full snapshot: one entry per `--json` leaf command, covered or exempt with a reason."""
    with tempfile.TemporaryDirectory() as tmp:
        docs = capture(Path(tmp))
    out: dict[str, Any] = {name: {"exempt": why} for name, why in EXEMPT.items()}
    errors = {n.removesuffix(ERROR_SUFFIX): d for n, d in docs.items() if n.endswith(ERROR_SUFFIX)}
    for name, doc in docs.items():
        if name.endswith(ERROR_SUFFIX):
            continue
        dynamic, optional = DYNAMIC.get(name, []), OPTIONAL.get(name, [])
        opaque = OPAQUE.get(name, {})
        entry: dict[str, Any] = {"paths": flatten(shape_of(doc, dynamic, optional, opaque))}
        if dynamic:
            entry["dynamic_maps"] = dynamic
        if opaque:
            entry["opaque_values"] = opaque
        if optional:
            entry["optional_keys"] = optional
        if name in errors:
            entry["error_entry"] = flatten(shape_of(errors[name], [], []))
        out[name] = entry
    return dict(sorted(out.items()))


def render(snap: dict[str, Any]) -> str:
    return json.dumps(snap, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(render(snapshot()), encoding="utf-8")


if __name__ == "__main__":
    main()
