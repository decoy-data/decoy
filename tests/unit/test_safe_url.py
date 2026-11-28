"""The one safe-URL parser and display boundary: no user, password or query ever comes out.

Row numbers name the behavior table in `docs/plans/2026-11-28-d6-manifest-display-boundary.md`,
section 1.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from decoy.cli.evidence import build_manifest
from decoy.safe_url import (
    DisplayCopy,
    display_copy,
    display_file_name,
    display_location,
    display_safe,
    display_text,
    redacted_location,
    safe_url_parts,
)

_PW = "SENTINEL-pw-1a2b"
_TOK = "SENTINEL-tok-3c4d"


@pytest.mark.parametrize(
    ("url", "scheme", "netloc", "path"),
    [
        (
            f"https://u:{_PW}@hooks.example.com:8443/a/b?t={_TOK}",
            "https",
            "hooks.example.com:8443",
            "/a/b",
        ),
        (f"https://u:{_PW}@hooks.example.com/x", "https", "hooks.example.com", "/x"),
        (f"s3://u:{_PW}@[::1]:9000/x?t={_TOK}", "s3", "[::1]:9000", "/x"),
    ],
)
def test_parts_carry_no_credential(url: str, scheme: str, netloc: str, path: str) -> None:
    parts = safe_url_parts(url)
    assert parts is not None
    assert (parts.scheme, parts.netloc, parts.path) == (scheme, netloc, path)
    assert _PW not in repr(parts)
    assert _TOK not in repr(parts)


@pytest.mark.parametrize("url", ["https://h:notaport/x", "not a url", "https:///only-path", ""])
def test_unreadable_url_gives_none(url: str) -> None:
    assert safe_url_parts(url) is None


@pytest.mark.parametrize(
    ("raw", "shown"),
    [
        ("data/out.csv", "data/out.csv"),
        ("data/payroll@2026?#.csv", "data/payroll@2026?#.csv"),
        ("//files/share/payroll@2026.csv", "//files/share/payroll@2026.csv"),
        ("//files/share/payroll?2026.csv", "//files"),
        ("//files/share/payroll#2026.csv", "//files"),
        (f"//share/https://u:{_PW}@host/f", "(remote location)"),
        (f"//host?access_token={_TOK}", "//host"),
        ("///data/report?#.csv", "///data/report?#.csv"),
        (f"https://u:{_PW}@files.example.com/o.csv?t={_TOK}", "https://files.example.com"),
        (f"sftp://u:{_PW}@[::1]:22/o.csv", "sftp://[::1]:22"),
        (f"https://u:{_PW}@h:bad/o.csv?t={_TOK}", "(remote location)"),
        (f"://u:{_PW}@h/o.csv", "(remote location)"),
        (f"//u:{_PW}@files.example.com:8443/p?t={_TOK}", "//files.example.com:8443"),
        (f"//u@[::1]/p?t={_TOK}", "//[::1]"),
        (f"//u:{_PW}@h:bad/p", "(remote location)"),
        ("//server/share/out.csv", "//server/share/out.csv"),
        ("//build[1]/share/report.csv", "//build[1]/share/report.csv"),
        (f"//files.example.com/f.csv?access_token={_TOK}", "//files.example.com"),
        (f"//files.example.com:99/f.csv#{_TOK}", "//files.example.com:99"),
    ],
)
def test_redacted_location(raw: str, shown: str) -> None:
    assert redacted_location(raw) == shown


def test_display_safe_redacts_multiple_locations_inside_text() -> None:
    text = f"could not open //u:{_PW}@files.example/share or https://h/path?token={_TOK} today"
    assert display_safe(text) == "could not open //files.example or https://h today"


# --- A1: the behavior table, text rows through display_text ---

_REMOTE = "(remote location)"
_TEXT_ROWS = [
    ("1", "See <https://host/hook/TOKEN>", "See <https://host>"),
    ("2", "URL:https://u:p@h/x", "URL:https://h"),
    ("3a", "a,https://u:p@h/x", "a,https://h"),
    ("3b", "a;https://u:p@h/x", "a;https://h"),
    ("3c", "a|https://u:p@h/x", "a|https://h"),
    (
        "5",
        "could not read /project/https:/user:PW@host/in.csv",
        "could not read /project/https://host",
    ),
    ("9", "source comment: // WARNING: checksum mismatch for archive@2026.csv", None),
    ("10", "/var/run//deploy@prod/output.csv", None),
    ("11a", "\\\\server\\share\\f.csv", None),
    ("11b", "/data//exports/current.csv", None),
    ("12", "//share/https://u:PW@host/f", _REMOTE),
    ("13a", "//host/p?token", "//host"),
    ("13b", "//host?access_token=T", "//host"),
    (
        "14",
        "could not open //user:pass@first word@host/path today",
        "could not open (remote location) today",
    ),
    ("15a", "https://user:pass word@host/path", _REMOTE),
    ("15b", "//user:pass word@host/path", _REMOTE),
    ("16", "//user:pw@files.example permission denied for ops@example.com", _REMOTE),
    ("17", "paths: //plain/share,//u:PW@host/f", "paths: (remote location)"),
    ("18", "paths: //plain/share, //u:PW@host/f", "paths: //plain/share, //host"),
    ("20a", "https://u:PW@h:bad/o.csv?t=T", _REMOTE),
    ("20b", "://u:PW@h/o.csv", _REMOTE),
    ("21", "sftp://u:PW@[::1]:22/o.csv", "sftp://[::1]:22"),
    ("24", "C:/Users/a@b/x.csv", None),
    ("27", "postgresql://admin:2024#Secret@db.example/prod", _REMOTE),
    ("28a", "https://u:12/ss@h/x", _REMOTE),
    ("28b", "https://u:12?ss@h/x", _REMOTE),
    ("29", "https://h/x@2026.csv", _REMOTE),
    ("30a", "`//u:PW@h/x`", "`//h`"),
    ("30b", "*//u:PW@h/x", "*//h"),
    ("30c", "see://u:PW@h/x", "see://h"),
    ("31a", "at 12://u:PW@h/x", "at (remote location)"),
    ("31b", "x ://u:PW@h/o.csv", "x (remote location)"),
    ("32", "/data/a=//u:pw@h/x", "/data/a=//h"),
    ("33a", "file:///data/x.csv", _REMOTE),
    ("33b", "file://nas/x.csv", "file://nas"),
    ("36", "postgresql://admin:2024#Secret word@db.example/prod", _REMOTE),
    ("37", "//u:12/ss@h/x", _REMOTE),
    ("44", "//share/https:/h/hook/TOKEN", "//share/https://h"),
    ("45a", "https://S:2024#S@h/x", _REMOTE),
    ("45b", "//u:S/S@h/x", _REMOTE),
    ("46", "wrote https://h/x, contact ops@example.com", "wrote (remote location)"),
    ("47", "see //plain/share and ops@example.com", None),
    ("49", "see https://status.example and ops@example.com", "see (remote location)"),
    ("51a", "https://hooks.example\\incoming\\marker", _REMOTE),
    ("51b", "https://u:marker@hooks.example\\incoming\\marker", _REMOTE),
    ("52", "see //service account:marker@files.example/x today", "see (remote location) today"),
]


@pytest.mark.parametrize(
    ("raw", "shown"), [(r, s) for _, r, s in _TEXT_ROWS], ids=[i for i, _, _ in _TEXT_ROWS]
)
def test_text_rows(raw: str, shown: str | None) -> None:
    assert display_text(raw) == (raw if shown is None else shown)


@pytest.mark.parametrize("opener", ["'", '"', "(", "[", "{", "=", "<", ",", ";", "|", "`"])
def test_row_19_opening_delimiter_starts_span(opener: str) -> None:
    assert display_text(f"source{opener}//host/p?token") == f"source{opener}//host"


# --- A1: path field rows through display_location ---

_LOCATION_ROWS = [
    ("4", "/project/https:/user:PW@host/in.csv", _REMOTE),
    ("6", "https:/u:PW@h/x", "https://h"),
    ("8", "//id.example/callback#access_token=T", "//id.example"),
    ("10", "/var/run//deploy@prod/output.csv", None),
    ("11", "/data//exports/current.csv", None),
    ("12", "//share/https://u:PW@host/f", _REMOTE),
    ("13", "//host/p?token", "//host"),
    ("15a", "https://user:pass word@host/path", _REMOTE),
    ("15b", "//user:pass word@host/path", _REMOTE),
    ("20", "https://u:PW@h:bad/o.csv?t=T", _REMOTE),
    ("22a", "/tmp/x/payroll@2026.csv", None),
    ("22b", "payroll#2026.csv", None),
    ("22c", "payroll?year=2026.csv", None),
    ("23", "//files/share/payroll?2026.csv", "//files"),
    ("27", "postgresql://admin:2024#Secret@db.example/prod", _REMOTE),
    ("28", "https://u:12/ss@h/x", _REMOTE),
    ("32", "/data/a=//u:pw@h/x", "/data/a=//h"),
    ("33", "file:///data/x.csv", _REMOTE),
    ("34", "//server/share/payroll#2026.csv", "//server"),
    ("36", "postgresql://admin:2024#Secret word@db.example/prod", _REMOTE),
    ("37", "//u:12/ss@h/x", _REMOTE),
    ("44", "//share/https:/h/hook/TOKEN", _REMOTE),
    ("45", "//u:S/S@h/x", _REMOTE),
    ("48", "//host:8080/x", None),
    ("51a", "https://hooks.example\\incoming\\marker", _REMOTE),
    ("51b", "https://u:marker@hooks.example\\incoming\\marker", _REMOTE),
]


@pytest.mark.parametrize(
    ("raw", "shown"),
    [(r, s) for _, r, s in _LOCATION_ROWS],
    ids=[i for i, _, _ in _LOCATION_ROWS],
)
def test_location_rows(raw: str, shown: str | None) -> None:
    assert display_location(raw) == (raw if shown is None else shown)


def test_multiline_location_is_shown_per_line() -> None:
    raw = "https:/u:PW@h/x\n/data/plain.csv\r\n//id.example/cb#t=T"
    assert display_location(raw) == "https://h\n/data/plain.csv\r\n//id.example"


def test_display_file_name_shows_location_first_then_base_name() -> None:
    assert display_file_name(Path("/tmp/x/https:/h/hook/TOKEN")) == _REMOTE
    assert display_file_name(Path("/tmp/x/evidence.json")) == "evidence.json"


# --- A1 writer: build_manifest records the placeholder for the ambiguous locators ---

_WRITER_ROWS = {
    "r27": "postgresql://admin:2024#Secret@db.example/prod",
    "r28a": "https://u:12/ss@h/x",
    "r28b": "https://u:12?ss@h/x",
    "r36": "postgresql://admin:2024#Secret word@db.example/prod",
    "r37": "//u:12/ss@h/x",
    "r45a": "https://S:2024#S@h/x",
    "r45b": "//u:S/S@h/x",
    "r51a": "https://hooks.example\\incoming\\marker",
    "r51b": "https://u:marker@hooks.example\\incoming\\marker",
    "r52": "//service account:marker@files.example/x",
    "relative": "relative/https:/h/hook/marker",
}


def test_writer_records_placeholder_for_ambiguous_locators(tmp_path: Path) -> None:
    pipeline = tmp_path / "pipeline.yaml"
    pipeline.write_text("version: 2\n", encoding="utf-8")
    config = {"sources": {k: {"type": "s3", "path": v} for k, v in _WRITER_ROWS.items()}}
    manifest = build_manifest(
        pipeline_path=pipeline,
        config_dict=config,
        run_result={"row_counts": {}},
        cli_version="0",
        engine_version="0",
    )
    recorded = manifest["input_fingerprints"]
    assert {k: v["path"] for k, v in recorded.items()} == dict.fromkeys(_WRITER_ROWS, _REMOTE)
    assert all(v["fingerprint"] is None for v in recorded.values())
    for secret in ("Secret", "ss@", "marker", "2024"):
        assert secret not in json.dumps(recorded)


# --- A9: return types and collisions (rows 35, 41, 42) ---


def test_display_copy_return_types() -> None:
    assert type(display_copy("s")) is str
    assert type(display_copy(["a", ("b",)])) is list
    assert type(display_copy(("a",))) is list
    nested = display_copy({"a": {"b": [{"c": "https://u:p@h/x"}]}})
    assert type(nested) is DisplayCopy
    assert type(nested["a"]) is DisplayCopy
    assert type(nested["a"]["b"][0]) is DisplayCopy
    assert nested["a"]["b"][0]["c"] == "https://h"
    assert display_copy(3) == 3
    assert display_copy(None) is None


@pytest.mark.parametrize(
    ("keys", "shown"),
    [
        (["https://a:1@h/x", "https://b:2@h/y"], ["https://h", "https://h (2)"]),
        (
            ["https://h (2)", "https://a:1@h/x", "https://b:2@h/y"],
            ["https://h (2)", "https://h", "https://h (3)"],
        ),
        (
            ["https://a:1@h/x", "https://b:2@h/y", "https://h (2)"],
            ["https://h", "https://h (2)", "https://h (2) (2)"],
        ),
    ],
    ids=["row35", "row41", "row42"],
)
def test_colliding_keys_stay_apart(keys: list[str], shown: list[str]) -> None:
    raw = {k: i for i, k in enumerate(keys)}
    copy = display_copy(raw)
    assert list(copy) == shown
    assert Counter(copy.values()) == Counter(raw.values())


def test_location_fields_apply_location_rule_only_at_their_paths() -> None:
    from decoy.safe_url import location_fields

    fields = location_fields(["/payload/a/*/path", "/payload/b~1c", "/other/x"], "/payload/")
    assert fields == frozenset({("a", "*", "path"), ("b/c",)})
    raw = {"a": {"t": {"path": "/p/https:/u:PW@h/x"}}, "b/c": "/p/https:/u:PW@h/x"}
    raw["note"] = "/p/https:/u:PW@h/x"
    shown = display_copy(raw, fields)
    assert shown["a"]["t"]["path"] == _REMOTE
    assert shown["b/c"] == _REMOTE
    assert shown["note"] == "/p/https://h"


# --- A4, A5, A8: properties of the scanner ---

_S = "zqxsentinelqz"
_CARRIERS = [
    "https://u:{S}@h/x",
    "https://{S}:pw@h/x",
    "https://h/hook/{S}",
    "https://h/x?t={S}",
    "//h/p#{S}",
    "//u:{S}@h/p",
    "https:/u:{S}@h/x",
    "/project/https:/u:{S}@h/in.csv",
    "<https://h/hook/{S}>",
    "URL:https://u:{S}@h/x",
    ",https://u:{S}@h",
    ";https://u:{S}@h",
    "|https://u:{S}@h",
    "https://u:{S} {S}@h/x",
    "//share/https://u:{S}@h/f",
    "//share/https:/h/hook/{S}",
    "https://u:{S}#{S}@h/x",
    "https://u:{S}?{S}@h/x",
    "https://u:{S}/{S}@h/x",
    "postgresql://admin:{S}#Secret {S}@db.example/prod",
    "//u:{S}/{S}@h/x",
    "`//u:{S}@h/x`",
    "12://u:{S}@h/x",
    "/data/a=//u:{S}@h/x",
    "https://h\\{S}",
    "https://u:{S}@h\\{S}",
    "//service account:{S}@files.example/x",
]
_ADMITTED = " \t\n<>:,;|'\"([{=*`"
_ALPHABET = "ab/:@?#.\\-_=~ \n<>()'\"`*,;|0123456789"
_SINGLE_TOKEN = "ab/:@?#.\\-_=~<>()'\"`*,;|0123456789"


def _carrier_text(prefix: str, carrier: str, suffix: str) -> str:
    if carrier.startswith("//") and prefix and prefix[-1] not in _ADMITTED:
        prefix += " "
    return prefix + carrier.format(S=_S) + suffix


@settings(max_examples=400, deadline=None)
@given(
    prefix=st.text(_ALPHABET, max_size=12),
    carrier=st.sampled_from(_CARRIERS),
    suffix=st.text(_ALPHABET, max_size=12),
)
def test_a4_no_carrier_survives_and_display_is_idempotent(
    prefix: str, carrier: str, suffix: str
) -> None:
    text = _carrier_text(prefix, carrier, suffix)
    shown = display_text(text)
    assert _S not in shown
    assert display_text(shown) == shown


@settings(max_examples=300, deadline=None)
@given(st.text(max_size=40))
def test_a5_text_without_a_start_is_unchanged(text: str) -> None:
    assume(":/" not in text and "//" not in text)
    assert display_text(text) == text


@pytest.mark.parametrize("before", list("azAZ09._~/-"))
@pytest.mark.parametrize("carrier", ["//u:{S}@h/x", "//h/p#{S}"])
def test_a5_double_slash_after_a_path_character_is_unchanged(before: str, carrier: str) -> None:
    text = "x" + before + carrier.format(S=_S)
    assert display_text(text) == text


@pytest.mark.parametrize(
    "raw",
    [
        "source comment: // WARNING: checksum mismatch for archive@2026.csv",
        "/var/run//deploy@prod/output.csv",
        "/tmp/x/payroll@2026.csv",
        "C:/Users/a@b/x.csv",
        "see //plain/share and ops@example.com",
        "//host:8080/x",
    ],
)
def test_a5_named_rows_unchanged(raw: str) -> None:
    assert display_text(raw) == raw


@settings(max_examples=400, deadline=None)
@given(
    prefix=st.text(_SINGLE_TOKEN, max_size=12),
    carrier=st.sampled_from([c for c in _CARRIERS if " " not in c]),
    suffix=st.text(_SINGLE_TOKEN, max_size=12),
)
def test_a8_location_is_at_least_as_strict_as_text(prefix: str, carrier: str, suffix: str) -> None:
    if carrier.startswith("//") and prefix and prefix[-1] not in _ADMITTED:
        prefix += "="
    token = prefix + carrier.format(S=_S) + suffix
    shown = display_location(token)
    if _S not in display_text(token):
        assert _S not in shown
    assert display_text(shown) == shown


def _deep_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in (k, *_deep_strings(v))]
    if isinstance(value, list):
        return [s for v in value for s in _deep_strings(v)]
    return []


def test_display_safe_reaches_every_key_and_leaf() -> None:
    raw = {f"https://u:{_PW}@h/k": [{"x": f"see https://h/hook/{_TOK}"}]}
    assert not any(_PW in s or _TOK in s for s in _deep_strings(display_safe(raw)))
