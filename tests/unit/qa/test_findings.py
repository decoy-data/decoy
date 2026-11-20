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
        "corpus_item": "shop-s", "command": "decoy run shop", "config": "values removed",
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


SHORT_REFUSAL = sweep.RefusalSet.build(["Bob", "Ann", "O'Neil", "Zoë", 123])


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
    sent: list[str] = []
    out = findings.publish(
        tmp_path, "pass-1", NEEDLES, REFUSAL, records_dir=tmp_path / "rec",
        notify=sent.append, today=datetime.date(2026, 12, 1),
    )  # fmt: skip
    assert out.name == "2026-12-01-qa-beta-pass-1.md"
    assert "| t1-002 | GEN | V1 | untriaged |" in out.read_text()
    assert sent == ["QA-BETA pass pass-1: 2 findings. Ids: t1-001, t1-002"]


def test_publish_stops_on_a_value_in_a_stored_record(tmp_path: Path) -> None:
    put(tmp_path, record())
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
    monkeypatch.delenv("QA_SLACK_SCRIPT", raising=False)
    assert _cli(tmp_path) == 1
    assert not (tmp_path / "rec").exists()  # refused before any record was written
    assert _cli(tmp_path, "--no-slack") == 0


def test_a_failed_post_exits_nonzero_and_a_rerun_posts_again_without_rewriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    put(tmp_path, record())
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
