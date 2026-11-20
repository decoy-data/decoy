"""AT-7 and AT-13 (writer half): the finding writer refuses values and publishes once."""

from __future__ import annotations

import datetime
import os
import threading
from pathlib import Path

import pytest
from scripts.qa import findings, io, sweep

NEEDLES = sweep.read_needles("qamark0042\nS3cretValueXYZ\n")
REFUSAL = sweep.RefusalSet.build(
    ["Zelda Quinn", 90210, datetime.date(2020, 1, 2), "N7-4471", "O'Brien", "Smith, John",
     "(555) 123-4567", "Acme Inc.", "$1,234.50", datetime.datetime(2020, 1, 2, 10)]
)  # fmt: skip


def record(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "t1-001", "layer": "L1", "persona": "", "group": "RUN", "platform": "linux-x86_64",
        "cli_version": "1.0.0", "engine_version": "1.0.0", "bundle_digest": "sha256:ab",
        "corpus_item": "single-csv-s", "command": "decoy run shop", "config": "values removed",
        "expected": "docs/cli-reference.md:108", "actual": "output differs", "exit": 1,
        "repro": "sh repro.sh", "proposed_tier": "V1", "confusing": False,
    }  # fmt: skip
    return base | over


def put(tmp_path: Path, rec: dict[str, object], **kw) -> Path:
    return findings.write(tmp_path, "pass-1", rec, NEEDLES, REFUSAL, **kw)


def test_a_clean_record_round_trips(tmp_path: Path) -> None:
    path = put(tmp_path, record())
    assert path == tmp_path / "pass-1" / "t1-001.toml"
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    got = findings.read_record(path.read_text())
    assert got["id"] == "t1-001" and got["exit"] == 1 and got["confusing"] is False


@pytest.mark.parametrize("field", ["actual", "command", "config", "expected", "repro"])
@pytest.mark.parametrize(
    "value",
    [
        "saw qamark0042 in output",  # marker
        "key S3cretValueXYZ",  # secret
        "row for Zelda Quinn",  # non-PII, multi-token
        "zip 90210 leaked",  # numeric
        "dated 2020-01-02",  # date
        "id N7-4471 appeared",  # output-only value
        "customer O'Brien",
        "Smith, John",
        "call (555) 123-4567",
        "vendor Acme Inc.",
        "total $1,234.50",
        "name zelda quinn",
        "at 2020-01-02T10:00:00",
        "at 2020-01-02 10:00:00",
    ],
)
def test_every_text_field_refuses_each_kind_of_value(
    tmp_path: Path, field: str, value: str
) -> None:
    with pytest.raises(findings.Refused) as err:
        put(tmp_path, record(**{field: value}))
    assert value.split()[-1] not in str(err.value) and field in str(err.value)
    assert err.value.__cause__ is None and err.value.__context__ is None
    assert not (tmp_path / "pass-1").exists()  # nothing was written


SHORT_REFUSAL = sweep.RefusalSet.build(["Bob", "Ann", "O'Neil", "Zoë", 123, "F", "CA", 0, -1, 3.5])


@pytest.mark.parametrize("value", ["met Bob today", "Ann", "o'neil", "Zoe\u0308", "row 123"])
def test_short_scalars_are_refused_in_a_record(tmp_path: Path, value: str) -> None:
    with pytest.raises(findings.Refused):
        findings.write(tmp_path, "pass-1", record(actual=value), NEEDLES, SHORT_REFUSAL)


def test_a_non_utf8_needle_is_found_in_an_artifact_byte_for_byte(tmp_path: Path) -> None:
    needles = (b"\xff\xfeSECRET\x80",)
    blob = b"before \xff\xfeSECRET\x80 after"
    with pytest.raises(findings.Refused):
        findings.write(tmp_path, "pass-1", record(), needles, None, artifacts={"o.bin": blob})
    assert not (tmp_path / "pass-1").exists()


def test_an_attached_artifact_is_scanned_and_published(tmp_path: Path) -> None:
    with pytest.raises(findings.Refused):
        put(tmp_path, record(), artifacts={"out.txt": b"leaked 90210"})
    assert not (tmp_path / "pass-1").exists()
    put(tmp_path, record(), artifacts={"out.txt": b"clean text"})
    assert (tmp_path / "pass-1" / "t1-001.out.txt").read_bytes() == b"clean text"


def test_marker_text_in_a_coordinate_id_is_refused_even_without_a_needle(tmp_path: Path) -> None:
    for rec in (record(id="qamark99-001"), record(coordinate="QAmark7")):
        with pytest.raises(findings.Refused, match="marker text"):
            put(tmp_path, rec)


def test_ids_are_tester_scoped_and_shaped(tmp_path: Path) -> None:
    with pytest.raises(findings.Refused, match="tester-scoped"):
        put(tmp_path, record(), tester="t2")
    with pytest.raises(findings.Refused):
        put(tmp_path, record(id="../x"))
    assert put(tmp_path, record(), tester="t1").name == "t1-001.toml"


def test_unknown_missing_and_mistyped_fields_are_refused(tmp_path: Path) -> None:
    bad = [
        record(extra="x"), record(exit=True), record(exit="1"), record(confusing=1),
        record(group=3), {k: v for k, v in record().items() if k != "actual"},
    ]  # fmt: skip
    for rec in bad:
        with pytest.raises(findings.Refused):
            put(tmp_path, rec)


# Reader cases (AT-7) ------------------------------------------------------------------------
def toml_of(**over: object) -> str:
    return findings._render(record(**over)).decode()


def test_reader_version_rules() -> None:
    good = toml_of()
    assert findings.read_record(good)["group"] == "RUN"
    for text in (
        good.replace("schema_version = 1\n", ""),
        good.replace("schema_version = 1", "schema_version = 2"),
        good.replace("schema_version = 1", 'schema_version = "1"'),
        good.replace("schema_version = 1", "schema_version = true"),
        "not = [toml",
    ):
        with pytest.raises(findings.ReaderError) as err:
            findings.read_record(text)
        assert err.value.__context__ is None


def test_reader_is_strict_about_types_and_allows_minor_fields() -> None:
    with pytest.raises(findings.ReaderError):
        findings.read_record(toml_of().replace("exit = 1", 'exit = "1"'))
    with pytest.raises(findings.ReaderError):
        findings.read_record(toml_of().replace("confusing = false", "confusing = 0"))
    assert findings.read_record(toml_of() + "new_minor_field = 3\n")["new_minor_field"] == 3


# AT-13 --------------------------------------------------------------------------------------
def test_concurrent_same_id_writes_allow_one_complete_record(tmp_path: Path) -> None:
    results: list[object] = []
    gate = threading.Barrier(8)

    def go(n: int) -> None:
        gate.wait()
        try:
            put(tmp_path, record(actual=f"attempt {n}"))
            results.append("won")
        except FileExistsError:
            results.append("lost")

    threads = [threading.Thread(target=go, args=(n,)) for n in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == ["lost"] * 7 + ["won"]
    final = findings.read_record((tmp_path / "pass-1" / "t1-001.toml").read_text())
    assert str(final["actual"]).startswith("attempt ")
    assert [p.name for p in (tmp_path / "pass-1").iterdir()] == ["t1-001.toml"]


def test_an_interrupted_write_leaves_no_target_and_allows_one_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_a: object) -> None:
        raise KeyboardInterrupt

    with monkeypatch.context() as m:
        m.setattr(os, "link", boom)
        with pytest.raises(KeyboardInterrupt):
            put(tmp_path, record())
    assert list((tmp_path / "pass-1").iterdir()) == []  # no target, no reservation
    put(tmp_path, record())
    with pytest.raises(io.AlreadyPublished):
        put(tmp_path, record())


# publish ------------------------------------------------------------------------------------
def test_publish_writes_the_pass_record_and_notifies_with_counts_and_ids(tmp_path: Path) -> None:
    put(tmp_path, record())
    put(tmp_path, record(id="t1-002", group="GEN"))
    for ident in ("t1-001", "t1-002"):
        findings.write_triage(tmp_path, "pass-1", ident, "v1")
    sent: list[str] = []
    out = findings.publish(
        tmp_path, "pass-1", NEEDLES, REFUSAL, records_dir=tmp_path / "rec",
        notify=sent.append, today=datetime.date(2026, 12, 1),
    )  # fmt: skip
    assert out.name == "2026-12-01-qa-beta-pass-1.md"
    assert "| t1-002 | GEN | V1 | v1 |" in out.read_text()
    assert sent == ["QA-BETA pass pass-1: 2 findings. Ids: t1-001, t1-002"]


def test_publish_stops_on_a_value_in_a_stored_record(tmp_path: Path) -> None:
    put(tmp_path, record())
    findings.write_triage(tmp_path, "pass-1", "t1-001", "v1")
    # A needle that joined the set after the record was written: the publish sweep catches it.
    late = sweep.read_needles("t1-001\n")
    sent: list[str] = []
    with pytest.raises(findings.Refused):
        findings.publish(
            tmp_path, "pass-1", late, None, records_dir=tmp_path / "rec", notify=sent.append
        )
    assert sent == [] and not (tmp_path / "rec").exists()


def test_a_tester_cannot_write_triage_and_nested_strings_are_guarded(tmp_path: Path) -> None:
    with pytest.raises(findings.Refused):
        put(tmp_path, record(triage="v1"))
    with pytest.raises(findings.Refused):
        put(tmp_path, record(schema_version=["Zelda Quinn"]))
    with pytest.raises(findings.Refused):
        put(tmp_path, record(schema_version=2))


def test_the_triager_writes_a_verdict_once_and_publish_joins_it(tmp_path: Path) -> None:
    put(tmp_path, record())
    path = findings.write_triage(tmp_path, "pass-1", "t1-001", "v1")
    assert path.name == "t1-001.triage.toml"
    with pytest.raises(io.AlreadyPublished):
        findings.write_triage(tmp_path, "pass-1", "t1-001", "v2-log")
    with pytest.raises(findings.Refused):
        findings.write_triage(tmp_path, "pass-1", "t1-002", "Zelda Quinn")
    out = findings.publish(tmp_path, "pass-1", NEEDLES, REFUSAL, records_dir=tmp_path / "rec")
    assert "| t1-001 | RUN | V1 | v1 |" in out.read_text()


def test_an_artifact_cannot_pose_as_a_record_or_a_verdict(tmp_path: Path) -> None:
    for name in ("x.toml", "triage.toml"):
        with pytest.raises(findings.Refused):
            put(tmp_path, record(), artifacts={name: b"clean"})
    put(tmp_path, record(), artifacts={"out.txt": b"clean"})
    findings.write_triage(tmp_path, "pass-1", "t1-001", "v1")
    out = findings.publish(tmp_path, "pass-1", NEEDLES, REFUSAL, records_dir=tmp_path / "rec")
    assert "Findings: 1" in out.read_text()


def test_the_slack_status_is_posted_skipped_or_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("QA_SLACK_SCRIPT", raising=False)
    assert findings._slack("x").startswith("skipped")
    for name, code in (("ok.sh", 0), ("bad.sh", 1)):
        script = tmp_path / name
        script.write_text(f"#!/bin/sh\nexit {code}\n")
        script.chmod(0o700)
    monkeypatch.setenv("QA_SLACK_SCRIPT", str(tmp_path / "ok.sh"))
    assert findings._slack("x") == "posted"
    monkeypatch.setenv("QA_SLACK_SCRIPT", str(tmp_path / "bad.sh"))
    assert findings._slack("x") == "failed"
    monkeypatch.setenv("QA_SLACK_SCRIPT", str(tmp_path / "missing"))
    assert findings._slack("x") == "failed"


# Commit order and retry ---------------------------------------------------------------------
def test_the_record_is_written_last_so_it_marks_the_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = io.publish_private_once
    order: list[str] = []

    def spy(target: Path, data: bytes) -> None:
        order.append(target.name)
        real(target, data)

    monkeypatch.setattr(findings, "publish_private_once", spy)
    monkeypatch.setattr(
        findings, "publish_or_same", lambda t, d: (order.append(t.name), real(t, d))
    )
    put(tmp_path, record(), artifacts={"a.txt": b"one", "b.txt": b"two"})
    assert order[-1] == "t1-001.toml" and set(order[:-1]) == {"t1-001.a.txt", "t1-001.b.txt"}


def test_a_retry_after_an_interruption_between_artifacts_and_record_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    arts = {"a.txt": b"one", "b.txt": b"two"}
    real = io.publish_private_once

    def die_on_record(target: Path, data: bytes) -> None:
        if target.suffix == ".toml":
            raise KeyboardInterrupt
        real(target, data)

    with monkeypatch.context() as m:
        m.setattr(findings, "publish_private_once", die_on_record)
        with pytest.raises(KeyboardInterrupt):
            put(tmp_path, record(), artifacts=arts)
    assert not (tmp_path / "pass-1" / "t1-001.toml").exists()  # no commit marker yet
    put(tmp_path, record(), artifacts=arts)  # identical artifacts count as done
    assert (tmp_path / "pass-1" / "t1-001.toml").exists()


def test_an_existing_artifact_with_other_bytes_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "pass-1"
    io.publish_private_once(folder / "t1-001.a.txt", b"somebody else")
    with pytest.raises(io.AlreadyPublished):
        put(tmp_path, record(), artifacts={"a.txt": b"mine"})
    assert not (folder / "t1-001.toml").exists()
    assert (folder / "t1-001.a.txt").read_bytes() == b"somebody else"


def test_concurrent_writers_with_different_artifacts_leave_one_complete_set(tmp_path: Path) -> None:
    outcomes: list[str] = []
    gate = threading.Barrier(6)

    def go(n: int) -> None:
        gate.wait()
        try:
            put(tmp_path, record(), artifacts={"a.txt": f"v{n}".encode()})
            outcomes.append("won")
        except FileExistsError:
            outcomes.append("lost")

    threads = [threading.Thread(target=go, args=(n,)) for n in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert outcomes.count("won") == 1
    assert (tmp_path / "pass-1" / "t1-001.toml").exists()


# One descriptor for both sides (design) -----------------------------------------------------
def test_writer_and_reader_agree_on_every_field_and_type() -> None:
    good = record()
    assert findings.read_record(findings._render(good).decode())
    bad_values: dict[str, list[object]] = {
        name: [3, True, None, ["x"]] if spec is str else ["x", 1.5, None]
        for name, spec in findings.FIELDS.items()
    }
    for name, values in bad_values.items():
        for value in values:
            if value is None and name in findings.OPTIONAL:
                continue
            rec = dict(good)
            rec[name] = value
            with pytest.raises(findings.Refused):
                findings._check_record(rec, None)
            text = "\n".join(f"{k} = {_toml(v)}" for k, v in rec.items() if v is not None)
            with pytest.raises(findings.ReaderError):
                findings.read_record("schema_version = 1\n" + text)
    for name in findings.FIELDS:  # a missing required field fails on both sides
        rec = {k: v for k, v in good.items() if k != name}
        required = name not in findings.OPTIONAL
        text = "schema_version = 1\n" + "\n".join(f"{k} = {_toml(v)}" for k, v in rec.items())
        for check in (
            lambda r=rec: findings._check_record(r, None),
            lambda t=text: findings.read_record(t),
        ):
            if required:
                with pytest.raises((findings.Refused, findings.ReaderError)):
                    check()
            else:
                check()


def test_unknown_members_are_refused_on_write_and_kept_on_read() -> None:
    with pytest.raises(findings.Refused):
        findings._check_record(record(extra="x"), None)
    assert (
        findings.read_record(findings._render(record()).decode() + 'extra = "x"\n')["extra"] == "x"
    )


def _toml(value: object) -> str:
    import json

    return "true" if value is True else "false" if value is False else json.dumps(value)


# Slack fails closed -------------------------------------------------------------------------
def _cli(tmp_path: Path, *extra: str) -> int:
    needles, refusal = tmp_path / "needles.txt", tmp_path / "refusal.json"
    if not needles.exists():
        needles.write_text("qamark0042\n")
        refusal.write_text(REFUSAL.dumps())
    args = ["publish", "--root", str(tmp_path), "--pass", "pass-1", "--needles", str(needles)]
    args += ["--refusal", str(refusal), "--records-dir", str(tmp_path / "rec"), *extra]
    return findings.main(args)


def _script(tmp_path: Path, code: int) -> Path:
    path = tmp_path / f"slack{code}.sh"
    path.write_text(f"#!/bin/sh\nexit {code}\n")
    path.chmod(0o700)
    return path


def test_publish_without_a_slack_script_fails_unless_no_slack_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    put(tmp_path, record())
    findings.write_triage(tmp_path, "pass-1", "t1-001", "v1")
    monkeypatch.delenv("QA_SLACK_SCRIPT", raising=False)
    assert _cli(tmp_path) == 1
    assert not (tmp_path / "rec").exists()  # refused before any record was written
    assert _cli(tmp_path, "--no-slack") == 0


def test_a_failed_post_exits_nonzero_and_a_rerun_posts_again_without_rewriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    put(tmp_path, record())
    findings.write_triage(tmp_path, "pass-1", "t1-001", "v1")
    monkeypatch.setenv("QA_SLACK_SCRIPT", str(_script(tmp_path, 1)))
    assert _cli(tmp_path) == 1
    [record_file] = (tmp_path / "rec").iterdir()
    before = record_file.stat().st_ino, record_file.read_bytes()
    monkeypatch.setenv("QA_SLACK_SCRIPT", str(_script(tmp_path, 0)))
    assert _cli(tmp_path) == 0
    assert (record_file.stat().st_ino, record_file.read_bytes()) == before


# Empty input sets are not-run, not clean ---------------------------------------------------------
@pytest.mark.parametrize("refusal", [None, sweep.RefusalSet.build([])])
def test_write_and_publish_treat_empty_input_sets_as_not_run(
    tmp_path: Path, refusal: sweep.RefusalSet | None
) -> None:
    with pytest.raises(sweep.NothingRead):
        findings.write(tmp_path, "pass-1", record(), (), refusal)
    assert not (tmp_path / "pass-1").exists()
    put(tmp_path, record())
    with pytest.raises(sweep.NothingRead):
        findings.publish(tmp_path, "pass-1", (b"",), refusal, records_dir=tmp_path / "rec")
    assert not (tmp_path / "rec").exists()


def test_the_cli_exits_2_when_the_input_sets_are_empty(tmp_path: Path) -> None:
    (tmp_path / "needles.txt").write_text("\n")
    (tmp_path / "refusal.json").write_text(sweep.RefusalSet.build([]).dumps())
    args = ["publish", "--root", str(tmp_path), "--pass", "pass-1", "--no-slack"]
    args += [
        "--needles",
        str(tmp_path / "needles.txt"),
        "--refusal",
        str(tmp_path / "refusal.json"),
    ]
    assert findings.main(args) == 2


def test_an_artifact_named_toml_is_refused(tmp_path: Path) -> None:
    with pytest.raises(findings.Refused):
        put(tmp_path, record(), artifacts={"toml": b"clean"})


def test_artifacts_are_checked_as_utf16_too(tmp_path: Path) -> None:
    for blob in (
        "leaked 90210".encode("utf-16"),  # BOM
        "leaked 90210".encode("utf-16-le"),  # no BOM, NULs
        "leaked 90210".encode("utf-16-be"),
        "token=S3cretValueXYZ".encode("utf-16-le"),  # a needle, not a scalar
    ):
        with pytest.raises(findings.Refused):
            put(tmp_path, record(), artifacts={"o.txt": blob})
    assert not (tmp_path / "pass-1").exists()


def test_a_latin1_and_a_utf32_artifact_are_checked_too(tmp_path: Path) -> None:
    refusal = sweep.RefusalSet.build(["José García"])
    needles = sweep.read_needles("qamark0042\n")
    for blob in (
        "name José García".encode("latin-1"),
        "name José García".encode("utf-32"),  # BOM
        "id qamark0042".encode("utf-32"),
    ):
        with pytest.raises(findings.Refused):
            findings.write(
                tmp_path, "pass-1", record(), needles, refusal, artifacts={"o.txt": blob}
            )
    assert not (tmp_path / "pass-1").exists()


# Short values (coordinator ruling): every scalar is indexed; one and two characters match whole.
@pytest.mark.parametrize("value", ["sex F", "state CA.", "count 0", "delta -1", "ratio 3.5", "-1"])
@pytest.mark.parametrize("field", ["actual", "command", "config", "expected", "repro"])
def test_short_whole_tokens_are_refused_in_every_string_field(
    tmp_path: Path, field: str, value: str
) -> None:
    with pytest.raises(findings.Refused):
        findings.write(tmp_path, "pass-1", record(**{field: value}), NEEDLES, SHORT_REFUSAL)


@pytest.mark.parametrize("value", ["F", "CA", "0", "-1"])
def test_short_whole_tokens_are_refused_in_artifacts(tmp_path: Path, value: str) -> None:
    for blob in (f"x {value} y".encode(), f"x {value} y".encode("utf-16")):
        with pytest.raises(findings.Refused):
            findings.write(
                tmp_path, "pass-1", record(), NEEDLES, SHORT_REFUSAL, artifacts={"a.txt": blob}
            )


@pytest.mark.parametrize("value", ["the CAT sat", "Fred left", "10 and 100", "item-1", "1.50"])
def test_the_same_characters_inside_a_longer_word_are_accepted(tmp_path: Path, value: str) -> None:
    findings.write(tmp_path, "pass-1", record(actual=value), NEEDLES, SHORT_REFUSAL)


# V1-5: valid TOML for any text ---------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    ["UI showed \U0001f600", 'quote " and \\ slash', "tab\there\nnew\x7f del\x01", "\u2028 é 日本"],
)
def test_a_record_with_non_bmp_and_special_text_round_trips(tmp_path: Path, text: str) -> None:
    path = put(tmp_path, record(actual=text))
    assert findings.read_record(path.read_text(encoding="utf-8"))["actual"] == text


def test_a_lone_surrogate_is_refused_not_written(tmp_path: Path) -> None:
    with pytest.raises(findings.Refused):
        put(tmp_path, record(actual="bad \ud800 text"))
    assert not (tmp_path / "pass-1").exists() or not list((tmp_path / "pass-1").glob("*.toml"))


# V1-6: bundle atomic per id ------------------------------------------------------------------
def test_two_writers_of_one_id_with_different_artifact_names_leave_one_bundle(
    tmp_path: Path,
) -> None:
    gate = threading.Barrier(2)
    outcomes: dict[str, str] = {}

    def go(name: str) -> None:
        gate.wait()
        try:
            put(tmp_path, record(), artifacts={name: name.encode()})
            outcomes[name] = "won"
        except (FileExistsError, findings.Refused):
            outcomes[name] = "lost"

    threads = [threading.Thread(target=go, args=(n,)) for n in ("a.txt", "b.txt")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(outcomes.values()) == ["lost", "won"]
    winner = next(n for n, v in outcomes.items() if v == "won")
    assert sorted(p.name for p in (tmp_path / "pass-1").iterdir()) == sorted(
        ["t1-001.toml", f"t1-001.{winner}"]
    )


def test_a_retry_that_names_other_artifacts_than_a_killed_writer_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = io.publish_private_once

    def die_on_record(target: Path, data: bytes) -> None:
        if target.suffix == ".toml":
            raise KeyboardInterrupt
        real(target, data)

    with monkeypatch.context() as m:
        m.setattr(findings, "publish_private_once", die_on_record)
        with pytest.raises(KeyboardInterrupt):
            put(tmp_path, record(), artifacts={"a.txt": b"one"})
    with pytest.raises(findings.Refused):
        put(tmp_path, record(), artifacts={"b.txt": b"two"})
    assert not (tmp_path / "pass-1" / "t1-001.toml").exists()
    put(tmp_path, record(), artifacts={"a.txt": b"one"})  # the same names finish it


def test_duplicate_or_malformed_artifact_arguments_are_refused_by_the_cli(tmp_path: Path) -> None:
    needles, refusal = tmp_path / "n.txt", tmp_path / "r.json"
    needles.write_text("qamark0042\n")
    refusal.write_text(REFUSAL.dumps())
    rec = tmp_path / "rec.toml"
    rec.write_bytes(findings._render(record()))
    (tmp_path / "x").write_text("one")
    base = ["write", "--root", str(tmp_path / "root"), "--pass", "pass-1", "--needles", str(needles),
            "--refusal", str(refusal), "--record", str(rec), "--tester", "t1"]  # fmt: skip
    x = str(tmp_path / "x")
    assert findings.main([*base, "--artifact", f"a.txt={x}", "--artifact", f"a.txt={x}"]) == 1
    assert findings.main([*base, "--artifact", "nameonly"]) == 1
    assert not (tmp_path / "root").exists()
    assert findings.main([*base, "--artifact", f"a.txt={x}"]) == 0


# V1-7: triage integrity ----------------------------------------------------------------------
def test_an_orphan_verdict_is_refused_on_write_and_on_publish(tmp_path: Path) -> None:
    with pytest.raises(findings.Refused):
        findings.write_triage(tmp_path, "pass-1", "t1-009", "v1")
    put(tmp_path, record())
    findings.write_triage(tmp_path, "pass-1", "t1-001", "v1")
    io.publish_private_once(
        tmp_path / "pass-1" / "t1-009.triage.toml",
        findings._render({"id": "t1-009", "triage": "v1"}),
    )
    with pytest.raises(findings.Refused):
        findings.publish(tmp_path, "pass-1", NEEDLES, REFUSAL, records_dir=tmp_path / "rec")


def test_publish_before_triage_is_refused_and_republishing_after_triage_works(
    tmp_path: Path,
) -> None:
    put(tmp_path, record())
    sent: list[str] = []
    with pytest.raises(findings.Refused):
        findings.publish(
            tmp_path, "pass-1", NEEDLES, REFUSAL, records_dir=tmp_path / "rec", notify=sent.append
        )
    assert sent == [] and not (tmp_path / "rec").exists()  # nothing was committed
    findings.write_triage(tmp_path, "pass-1", "t1-001", "confirmed")
    day = datetime.date(2026, 12, 1)
    out = findings.publish(
        tmp_path, "pass-1", NEEDLES, REFUSAL, records_dir=tmp_path / "rec", today=day
    )
    again = findings.publish(
        tmp_path, "pass-1", NEEDLES, REFUSAL, records_dir=tmp_path / "rec", today=day
    )
    assert out == again and "| t1-001 | RUN | V1 | confirmed |" in out.read_text()


def test_verdict_writer_and_reader_share_one_descriptor() -> None:
    good = findings._render({"id": "t1-001", "triage": "v1"}).decode()
    assert findings.read_triage(good) == {"schema_version": 1, "id": "t1-001", "triage": "v1"}
    for bad in (
        good.replace("schema_version = 1", "schema_version = 2"),
        good.replace('triage = "v1"', 'triage = "maybe"'),
        good.replace('triage = "v1"', "triage = 1"),
        good.replace('id = "t1-001"', 'id = "T1 001"'),
        'schema_version = 1\nid = "t1-001"\n',
        "not toml [",
    ):
        with pytest.raises(findings.ReaderError):
            findings.read_triage(bad)
    for verdict in ("maybe", "", "V1"):
        with pytest.raises(findings.Refused):
            findings.write_triage(Path("/nonexistent"), "pass-1", "t1-001", verdict)


def test_publish_refuses_a_malformed_stored_verdict(tmp_path: Path) -> None:
    put(tmp_path, record())
    io.publish_private_once(tmp_path / "pass-1" / "t1-001.triage.toml", b'id = "t1-001"\n')
    with pytest.raises(findings.ReaderError):
        findings.publish(tmp_path, "pass-1", NEEDLES, REFUSAL, records_dir=tmp_path / "rec")


# V1-8: tester is required at the submission entry point -------------------------------------
def test_the_cli_write_requires_a_tester(tmp_path: Path) -> None:
    needles, refusal, rec = tmp_path / "n.txt", tmp_path / "r.json", tmp_path / "rec.toml"
    needles.write_text("qamark0042\n")
    refusal.write_text(REFUSAL.dumps())
    rec.write_bytes(findings._render(record()))
    base = ["write", "--root", str(tmp_path / "root"), "--pass", "pass-1", "--needles", str(needles),
            "--refusal", str(refusal), "--record", str(rec)]  # fmt: skip
    assert findings.main(base) == 1
    assert findings.main([*base, "--tester", ""]) == 1
    assert findings.main([*base, "--tester", "t2"]) == 1  # another tester's id
    assert not (tmp_path / "root").exists()
    assert findings.main([*base, "--tester", "t1"]) == 0


# Structural fields: typed metadata with a grammar, no refusal-set lookup -------------------------
ZERO = sweep.RefusalSet.build([0, 1, "F", "CA"])


def test_a_version_with_a_zero_is_accepted_when_zero_is_in_the_refusal_set(
    tmp_path: Path,
) -> None:
    assert ZERO.found_in("run 0 rows") and record()["cli_version"] == "1.0.0"
    findings.write(tmp_path, "pass-1", record(), NEEDLES, ZERO)


@pytest.mark.parametrize(
    ("field", "value"),
    [("cli_version", "Bob"), ("engine_version", "1.0"), ("layer", "L9"), ("persona", "Zelda"),
     ("group", "run"), ("platform", "Linux x86"), ("bundle_digest", "sha256:XYZ"),
     ("corpus_item", "not-in-manifest"), ("proposed_tier", "V3"), ("cli_version", "0")],
)  # fmt: skip
def test_a_structural_field_that_does_not_fit_its_grammar_is_refused(
    tmp_path: Path, field: str, value: str
) -> None:
    with pytest.raises(findings.Refused, match="grammar"):
        findings.write(tmp_path, "pass-1", record(**{field: value}), NEEDLES, ZERO)
    with pytest.raises(findings.ReaderError):
        findings.read_record(findings._render(record(**{field: value})).decode())


def test_free_text_still_gets_the_full_lookup_and_needles_still_scan_structural_fields(
    tmp_path: Path,
) -> None:
    with pytest.raises(findings.Refused):
        findings.write(tmp_path, "pass-1", record(actual="saw 0 rows"), NEEDLES, ZERO)
    for field in ("command", "config", "expected"):
        with pytest.raises(findings.Refused):
            findings.write(tmp_path, "pass-1", record(**{field: "a 1 b"}), NEEDLES, ZERO)
    needle = sweep.read_needles("1.0.0\n")  # a needle that equals a structural value
    with pytest.raises(findings.Refused):
        findings.write(tmp_path, "pass-1", record(), needle, ZERO)


def test_publish_with_numbers_in_the_refusal_set_is_not_blocked_by_counts_or_ids(
    tmp_path: Path,
) -> None:
    findings.write(tmp_path, "pass-1", record(), NEEDLES, ZERO)
    findings.write_triage(tmp_path, "pass-1", "t1-001", "v1")
    sent: list[str] = []
    findings.publish(
        tmp_path, "pass-1", NEEDLES, ZERO, records_dir=tmp_path / "rec", notify=sent.append
    )
    assert sent == ["QA-BETA pass pass-1: 1 findings. Ids: t1-001"]
