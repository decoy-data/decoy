"""AT-7 and AT-13 (writer half): the finding writer refuses values and publishes once."""

from __future__ import annotations

import datetime
import os
import threading
from pathlib import Path

import pytest
from scripts.qa import findings, io, sweep

NEEDLES = sweep.read_needles("qamark0042\nS3cretValueXYZ\n")
REFUSAL = sweep.RefusalSet.build(["Zelda Quinn", 90210, datetime.date(2020, 1, 2), "N7-4471"])


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
