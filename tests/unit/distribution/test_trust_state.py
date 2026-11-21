"""AT-UK1-12, AT-UK1-18 and AT-UK1-29 of the UPGRADE-KEY plan: the one trust-state reader and
writer (`decoy.distribution.trust_state`), its three new fields and the shell contract."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.unit.test_distribution_acceptance import (
    _publish_doc,
    _run_install_sh,
    _signed_doc,
    needs_shell_tools,
)

from decoy.distribution import errors, signing, trust_state

_FUTURE = "2999-01-01T00:00:00Z"


def _decision(epoch: int, main_pem: str | None, revoked: set[str]) -> SimpleNamespace:
    return SimpleNamespace(main_pem=main_pem, epoch=epoch, revoked=frozenset(revoked))


def _fp(pem: str) -> str:
    return signing.fingerprint(pem)


def _put(home: Path, text: str) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    path = home / "trust_state.json"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------- AT-UK1-12: reader refusals
def _bad_states(release_pins) -> list[tuple[str, str]]:
    k1, k2 = release_pins.pem(release_pins.k1), release_pins.pem(release_pins.k2)
    good_fp = _fp(k1)
    return [
        ("epoch string", json.dumps({"serial": 1, "key_epoch": "2"})),
        ("epoch bool", json.dumps({"serial": 1, "key_epoch": True})),
        ("epoch zero", json.dumps({"serial": 1, "key_epoch": 0})),
        ("epoch negative", json.dumps({"serial": 1, "key_epoch": -1})),
        ("epoch float", json.dumps({"serial": 1, "key_epoch": 2.0})),
        ("revoked not list", json.dumps({"serial": 1, "revoked_keys": "ab"})),
        (
            "revoked not hex",
            json.dumps({"serial": 1, "key_epoch": 2, "main_key": k2, "revoked_keys": ["zz"]}),
        ),
        (
            "revoked upper",
            json.dumps(
                {"serial": 1, "key_epoch": 2, "main_key": k2, "revoked_keys": [good_fp.upper()]}
            ),
        ),
        (
            "revoked newline",
            json.dumps(
                {"serial": 1, "key_epoch": 2, "main_key": k2, "revoked_keys": [good_fp + "\n"]}
            ),
        ),
        ("revoked at epoch 1", json.dumps({"serial": 1, "revoked_keys": [good_fp]})),
        (
            "epoch 2 no main_key",
            json.dumps({"serial": 1, "key_epoch": 2, "revoked_keys": [good_fp]}),
        ),
        (
            "epoch 2 bad main_key",
            json.dumps(
                {"serial": 1, "key_epoch": 2, "main_key": "nope", "revoked_keys": [good_fp]}
            ),
        ),
        (
            "epoch 2 revoked main_key",
            json.dumps({"serial": 1, "key_epoch": 2, "main_key": k2, "revoked_keys": [_fp(k2)]}),
        ),
    ]


def test_every_malformed_new_field_is_refused_as_unreadable(tmp_path, release_pins):
    for label, text in _bad_states(release_pins):
        home = tmp_path / label.replace(" ", "_")
        _put(home, text)
        with pytest.raises(errors.InstallError, match="trust state unreadable"):
            trust_state.read_trust_state(home)


def test_absent_new_fields_read_as_epoch_one_and_an_empty_set(tmp_path):
    _put(tmp_path, json.dumps({"latest": "1.0.0", "serial": 7}))
    state = trust_state.read_trust_state(tmp_path)
    assert (state.serial, state.epoch, state.main_key, state.revoked) == (7, 1, None, frozenset())


def test_a_missing_file_is_a_first_run(tmp_path):
    state = trust_state.read_trust_state(tmp_path / "no-home")
    assert (state.serial, state.epoch, state.revoked) == (0, 1, frozenset())


def test_an_epoch_two_write_keeps_the_stored_revocation_too(tmp_path, release_pins):
    k1, k2, k3 = (release_pins.pem(k) for k in (release_pins.k1, release_pins.k2, release_pins.k3))
    extra = _fp(k3)
    _put(
        tmp_path,
        json.dumps(
            {
                "latest": "1.0.0",
                "serial": 4,
                "key_epoch": 2,
                "main_key": k2,
                "revoked_keys": [extra],
            }
        ),
    )
    trust_state.write_trust_state(
        tmp_path, _decision(2, k2, {_fp(k1)}), latest="1.0.1", document_serial=5
    )
    written = json.loads((tmp_path / "trust_state.json").read_text())
    assert written["revoked_keys"] == sorted({extra, _fp(k1)})
    assert written["key_epoch"] == 2 and written["main_key"] == k2 and written["serial"] == 5


def test_the_epoch_and_revocations_only_grow(tmp_path, release_pins):
    k1, k2 = release_pins.pem(release_pins.k1), release_pins.pem(release_pins.k2)
    _put(
        tmp_path,
        json.dumps({"serial": 4, "key_epoch": 3, "main_key": k2, "revoked_keys": [_fp(k1)]}),
    )
    trust_state.write_trust_state(
        tmp_path, _decision(1, None, set()), latest="1.0.0", document_serial=6
    )
    written = json.loads((tmp_path / "trust_state.json").read_text())
    assert (
        written["key_epoch"] == 3
        and written["main_key"] == k2
        and written["revoked_keys"] == [_fp(k1)]
    )


# -------------------------------------------------- epoch rise resets the serial (R2-H1, R1-B2)
def test_an_epoch_rise_without_a_document_writes_serial_zero(tmp_path, release_pins):
    k1, k2 = release_pins.pem(release_pins.k1), release_pins.pem(release_pins.k2)
    _put(tmp_path, json.dumps({"serial": 2**53, "latest": "1.0.0"}))
    trust_state.write_trust_state(
        tmp_path, _decision(2, k2, {_fp(k1)}), latest=None, document_serial=None
    )
    assert json.loads((tmp_path / "trust_state.json").read_text())["serial"] == 0


def test_an_epoch_rise_with_a_document_writes_that_documents_serial(tmp_path, release_pins):
    k1, k2 = release_pins.pem(release_pins.k1), release_pins.pem(release_pins.k2)
    _put(tmp_path, json.dumps({"serial": 2**53, "latest": "1.0.0"}))
    trust_state.write_trust_state(
        tmp_path, _decision(2, k2, {_fp(k1)}), latest="1.1.0", document_serial=1000
    )
    assert json.loads((tmp_path / "trust_state.json").read_text())["serial"] == 1000


def test_a_no_document_write_within_an_epoch_never_lowers_the_serial(tmp_path):
    _put(tmp_path, json.dumps({"serial": 9, "latest": "1.0.0"}))
    trust_state.write_trust_state(
        tmp_path, _decision(1, None, set()), latest=None, document_serial=None
    )
    assert json.loads((tmp_path / "trust_state.json").read_text())["serial"] == 9


def test_a_lower_document_serial_in_the_same_epoch_never_lowers_the_stored_one(tmp_path):
    _put(tmp_path, json.dumps({"serial": 9, "latest": "1.0.0"}))
    trust_state.write_trust_state(
        tmp_path, _decision(1, None, set()), latest="1.0.0", document_serial=5
    )
    assert json.loads((tmp_path / "trust_state.json").read_text())["serial"] == 9


# ------------------------------------------------------------- AT-UK1-29: unknown fields kept
def test_an_unknown_top_level_field_survives_a_recording_write(tmp_path):
    future = {"b": [1, 2, {"c": None}], "a": "x"}
    _put(tmp_path, json.dumps({"serial": 3, "latest": "1.0.0", "future_field": future}))
    trust_state.write_trust_state(
        tmp_path, _decision(1, None, set()), latest="1.0.1", document_serial=4
    )
    text = (tmp_path / "trust_state.json").read_text()
    assert json.loads(text)["future_field"] == future
    assert json.dumps(future, sort_keys=True, separators=(",", ":")) in text


# ---------------------------------------------------- AT-UK1-18: guard after the move + shell read
def test_corrupt_state_is_refused_and_replay_is_refused_through_the_installer(tmp_path):
    from decoy.distribution import installer
    from decoy.distribution import version_document as vd

    doc = vd.build_document(
        latest="1.0.0", min_supported="1.0.0", artifacts={}, serial=5, expires=_FUTURE
    )
    home = tmp_path / "h"
    installer.check_document_freshness(doc, home)  # absent state is a first run
    assert json.loads((home / "trust_state.json").read_text())["serial"] == 5
    stale = vd.build_document(
        latest="1.0.0", min_supported="1.0.0", artifacts={}, serial=4, expires=_FUTURE
    )
    with pytest.raises(errors.InstallError, match="rollback"):
        installer.check_document_freshness(stale, home)
    _put(home, "not json")
    with pytest.raises(errors.InstallError, match="trust state unreadable"):
        installer.check_document_freshness(doc, home)


def test_refusals_carry_no_path_and_no_file_text(tmp_path):
    secret = "SECRET-MARKER-VALUE"
    _put(tmp_path, '{"serial": "' + secret + '"}')
    with pytest.raises(errors.InstallError) as info:
        trust_state.read_trust_state(tmp_path)
    assert str(tmp_path) not in str(info.value) and secret not in str(info.value)
    assert info.value.__cause__ is None and info.value.__context__ is None


@needs_shell_tools
def test_install_sh_reads_the_serial_the_new_writer_wrote(tmp_path, release_pins):
    key, pub = release_pins.k3, release_pins.pem(release_pins.k3)
    k1, k2 = release_pins.pem(release_pins.k1), release_pins.pem(release_pins.k2)
    home = tmp_path / "sh_home"
    home.mkdir()
    trust_state.write_trust_state(
        home, _decision(2, k2, {_fp(k1)}), latest="1.0.0", document_serial=10
    )
    text = (home / "trust_state.json").read_text()
    assert '"main_key"' in text and '"revoked_keys"' in text
    stale, _ = _signed_doc(
        key, tmp_path / "serve", "0.2.0", mutate=lambda d: d.update(serial=9, expires=_FUTURE)
    )
    r, _ = _run_install_sh(tmp_path, pub, _publish_doc(tmp_path, key, stale))
    assert r.returncode != 0 and "rollback" in r.stderr
    assert json.loads((home / "trust_state.json").read_text())["serial"] == 10


def _shell_serial(text: str) -> str:
    """What install.sh's `json_top_number` returns: the first match of its grep pattern."""
    import re

    first = re.search(
        r'"serial"[[:space:]]*:[[:space:]]*[0-9]+'.replace("[[:space:]]", r"\s"), text
    )
    assert first is not None
    return first.group().split(":")[-1].strip()


@pytest.mark.parametrize(
    "kept",
    [
        {"a_nested": {"serial": 99}},  # sorts before "serial"; used to make every write refuse
        {'a"serial': 77},  # a key the old tokenizer passed and grep misreads
        {"a_nested": {"serial": None}},  # grep ignores a non-number, the old tokenizer refused it
        {"a_nested": {"serial": 99, "deeper": [{"serial": 5}]}},
    ],
)
def test_a_kept_field_never_blocks_the_write_or_changes_what_the_shell_reads(tmp_path, kept):
    _put(tmp_path, json.dumps({**kept, "serial": 5, "latest": "1.0.0"}))
    trust_state.write_trust_state(
        tmp_path, _decision(1, None, set()), latest="1.0.1", document_serial=6
    )
    text = (tmp_path / "trust_state.json").read_text()
    assert text.startswith('{"serial":6,')
    assert _shell_serial(text) == "6"
    written = json.loads(text)
    assert all(written[k] == v for k, v in kept.items())  # unknown fields kept intact


def test_the_written_state_has_serial_at_the_top_level_and_nowhere_before_it(tmp_path):
    trust_state.write_trust_state(
        tmp_path, _decision(1, None, set()), latest="1.0.0", document_serial=3
    )
    text = (tmp_path / "trust_state.json").read_text()
    assert (
        text.count('"serial":') == 1
        and json.loads(text)["serial"] == 3
        and text.startswith('{"serial":3,')
    )


def test_the_shell_pattern_check_compares_the_first_match_with_the_serial():
    check = trust_state._shell_reads_serial
    assert check('{"serial":5,"x":1}', 5)
    assert not check('{"serial":5,"x":1}', 6)
    assert not check('{"a":{"serial":9},"serial":5}', 5)  # a nested number first: the shell reads 9
    assert check('{"a":{"serial":null},"serial":5}', 5)  # grep ignores a non-number
    assert not check('{"a":1}', 5)
