"""RG-R: the readiness template and scripts/release/readiness_check.py.

Each test breaks exactly one input of a fully valid instance and expects exactly that
check to fire, so a check that is weakened or removed turns its own test red. The
checker prints reason codes and step names only; the tests also assert that no file
content reaches its output.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "docs" / "release" / "release-readiness.md"
_spec = importlib.util.spec_from_file_location(
    "readiness_check", ROOT / "scripts" / "release" / "readiness_check.py"
)
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)

SHA = "a" * 40
SHA2 = "b" * 40
DIGEST = "c" * 64
DIGEST2 = "d" * 64
LICENSOR = "Example Licensor GmbH"
CLI_LIMIT = "V2-LOG cli-1"
ENGINE_LIMIT = "V2-LOG eng-7"

IDENTITY = {
    "g3.cli_sha": SHA,
    "g3.engine_tag": "v0.30.0",
    "g3.engine_commit": SHA2,
    "g5.sha256sums_sha256": DIGEST,
    "g7.cli_sha": SHA,
    "g7.engine_tag": "v0.30.0",
    "g7.engine_commit": SHA2,
    "g7.sha256sums_sha256": DIGEST,
}
SIGNOFF = {
    "signoff.owner": "Cam",
    "signoff.date": "2026-12-05",
    "signoff.decision": "go",
}
PASS_EVIDENCE = "https://github.com/example/decoy/actions/runs/1"
MANUAL_EVIDENCE = "Reviewer R read commit abcdef1 on 2026-12-04"
LEGAL_FILES = {
    "cli": ("LICENSE.md", "NOTICE", "LICENSING.md", "TRADEMARKS.md", "CONTRIBUTING.md"),
    "engine": ("LICENSE", "NOTICE", "TRADEMARKS.md", "CONTRIBUTING.md", "README.md"),
}


def _fill(*, rows=None, keys=None, markers=()):
    """Copy the template and fill it. ``rows`` maps id to (result, evidence)."""
    values = {**IDENTITY, **SIGNOFF, "licensor": LICENSOR}
    values.update(keys or {})
    out = []
    for line in TEMPLATE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- ([a-z0-9_.]+):\s*$", line)
        if m and m.group(1) in values:
            line = f"- {m.group(1)}: {values[m.group(1)]}"
        elif re.match(r"^\| \d+ \|", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            result, evidence = (rows or {}).get(cells[0], _default_row(cells[0], cells[3]))
            cells[4], cells[5] = result, evidence
            line = "| " + " | ".join(cells) + " |"
        out.append(line)
    out.extend(f"- {m}" for m in markers)
    return "\n".join(out) + "\n"


def _default_row(row_id, criterion):
    if row_id in rc.MANUAL_ROWS:
        return "pass", MANUAL_EVIDENCE
    return "pass", PASS_EVIDENCE


def _legal_tree(root, repo, *, licensor=LICENSOR, extra=None):
    root.mkdir(parents=True, exist_ok=True)
    for name in LEGAL_FILES[repo]:
        text = f"Copyright 2026 {licensor}\nplain text\n"
        (root / name).write_text((extra or {}).get(name, text), encoding="utf-8")


def _map(path, *test_cells):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        "| Surface | Completeness source | Owning code | Pinning test or snapshot |",
        "|---|---|---|---|",
    ]
    rows += [f"| s{i} | src | code | {cell} |" for i, cell in enumerate(test_cells)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _candidate(path, **over):
    doc = {
        "schema": "decoy-release-candidate/v1",
        "cli_version": "1.0.0",
        "cli_sha": SHA,
        "engine_tag": "v0.30.0",
        "engine_commit": SHA2,
        "sha256sums_sha256": DIGEST,
    }
    doc.update(over)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


@pytest.fixture
def env(tmp_path):
    """A CLI tree, an engine tree, both maps and a matching candidate."""
    cli, engine = tmp_path / "cli", tmp_path / "engine"
    _legal_tree(cli, "cli")
    _legal_tree(engine, "engine")
    (cli / "docs/release").mkdir(parents=True, exist_ok=True)
    (cli / "docs/release/release-readiness.md").write_text(TEMPLATE.read_text(encoding="utf-8"))
    (cli / "src/decoy").mkdir(parents=True)
    (cli / "src/decoy/_version.py").write_text('"""v."""\n\n__version__ = "1.0.0"\n')
    _map(cli / "docs/release/frozen-surfaces.md", f"accepted-known-limit: {CLI_LIMIT}", "`t.py`")
    _map(engine / "docs/frozen-surfaces.md", f"accepted-known-limit: {ENGINE_LIMIT}")
    cand = _candidate(tmp_path / "candidate.json")
    return tmp_path, cli, engine, cand


def _known_limit_rows():
    return {"4": ("accepted-known-limit", f"{CLI_LIMIT}; {ENGINE_LIMIT}")}


def _run(capsys, tmp_path, text, *flags, cli=None):
    inst = tmp_path / "instance.md"
    inst.write_text(text, encoding="utf-8")
    argv = [str(inst), *flags]
    if cli is not None:
        argv += ["--cli-root", str(cli)]
    code = rc.main(argv)
    out = capsys.readouterr()
    return code, out.out + out.err


def _release(capsys, env, text=None, *, markers=(), extra=(), engine=True):
    tmp, cli, engine_dir, cand = env
    text = text if text is not None else _fill(rows=_known_limit_rows(), markers=markers)
    flags = ["--release", "--candidate", str(cand), *extra]
    if engine:
        flags += ["--engine-repo", str(engine_dir)]
    return _run(capsys, tmp, text, *flags, cli=cli)


def test_template_rows_are_complete():
    rows = rc.parse_rows(TEMPLATE.read_text(encoding="utf-8"))
    assert [r["id"] for r in rows] == [str(i) for i in range(1, 19)]
    assert tuple(r["id"] for r in rows) == rc.ROW_IDS
    for r in rows:
        assert r["gate"] and r["command"] and r["criterion"] and r["owner"], r["id"]
        assert r["result"] == "" and r["evidence"] == "", r["id"]


def test_a_filled_template_passes_structure_and_release(capsys, env):
    code, out = _run(capsys, env[0], _fill(rows=_known_limit_rows()))
    assert code == 0, out
    code, out = _release(capsys, env)
    assert code == 0, out


def test_the_unfilled_template_is_refused(capsys, tmp_path):
    code, out = _run(capsys, tmp_path, TEMPLATE.read_text(encoding="utf-8"))
    assert code == 1
    assert "readiness_result_invalid" in out


def test_blank_or_unknown_result_is_refused(capsys, tmp_path):
    for bad in ("", "passed", "PASS", "skipped"):
        code, out = _run(capsys, tmp_path, _fill(rows={"3": (bad, PASS_EVIDENCE)}))
        assert code == 1, bad
        assert "row 3: readiness_result_invalid" in out


def test_a_missing_row_or_an_unknown_row_is_refused(capsys, tmp_path):
    text = _fill()
    kept = "\n".join(ln for ln in text.splitlines() if not ln.startswith("| 9 |"))
    code, out = _run(capsys, tmp_path, kept + "\n")
    assert code == 1 and "row 9: readiness_row_missing" in out
    extra = text.replace("| 9 |", "| 19 |")
    code, out = _run(capsys, tmp_path, extra)
    assert code == 1 and "readiness_row_unknown" in out
    dup = text + next(ln for ln in text.splitlines() if ln.startswith("| 9 |")) + "\n"
    code, out = _run(capsys, tmp_path, dup)
    assert code == 1 and "row 9: readiness_row_duplicate" in out


def test_pass_without_evidence_is_refused(capsys, tmp_path):
    for bad in ("", "tbd", "<link>", "see above"):
        code, out = _run(capsys, tmp_path, _fill(rows={"5": ("pass", bad)}))
        assert code == 1, bad
        assert "row 5: readiness_evidence_missing" in out
    # the manual rows need a date and a commit, not a link
    code, out = _run(capsys, tmp_path, _fill(rows={"12": ("pass", PASS_EVIDENCE)}))
    assert code == 1 and "row 12: readiness_evidence_missing" in out
    code, out = _run(capsys, tmp_path, _fill(rows={"14": ("pass", "Reviewer R on 2026-12-04")}))
    assert code == 1 and "row 14: readiness_evidence_missing" in out


def test_a_known_limit_row_without_an_id_is_refused(capsys, tmp_path):
    for bad in ("", "see notes", "<id>"):
        code, out = _run(capsys, tmp_path, _fill(rows={"4": ("accepted-known-limit", bad)}))
        assert code == 1, bad
        assert "row 4: readiness_known_limit_id_missing" in out


def test_duplicate_json_keys_refused(capsys, env):
    _, _, _, cand = env
    cand.write_text(
        '{"schema": "decoy-release-candidate/v1", "cli_sha": "%s", "cli_sha": "%s",'
        ' "cli_version": "1.0.0", "engine_tag": "v0.30.0", "engine_commit": "%s",'
        ' "sha256sums_sha256": "%s"}' % (SHA, SHA2, SHA2, DIGEST),
        encoding="utf-8",
    )
    code, out = _release(capsys, env)
    assert code == 1 and "readiness_candidate_invalid" in out


@pytest.mark.parametrize(
    "over",
    [
        {"schema": "decoy-release-candidate/v2"},
        {"cli_sha": 5},
        {"extra": "x"},
    ],
)
def test_a_malformed_candidate_is_refused(capsys, env, over):
    _candidate(env[3], **over)
    code, out = _release(capsys, env)
    assert code == 1 and "readiness_candidate_invalid" in out


def test_an_unreadable_candidate_or_instance_fails_closed(capsys, env, tmp_path):
    env[3].write_bytes(b"\xff\xfe not json")
    code, out = _release(capsys, env)
    assert code == 1 and "readiness_candidate_invalid" in out
    assert "Traceback" not in out
    code = rc.main([str(tmp_path / "missing.md")])
    out = capsys.readouterr().out
    assert code == 1 and "readiness_unreadable" in out and "Traceback" not in out
    bad = tmp_path / "bin.md"
    bad.write_bytes(b"\xff\xfe\x00 not utf-8")
    assert rc.main([str(bad)]) == 1
    assert "readiness_unreadable" in capsys.readouterr().out


def test_release_mode_requires_a_candidate(capsys, tmp_path):
    inst = tmp_path / "i.md"
    inst.write_text(_fill(), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        rc.main([str(inst), "--release"])
    assert exc.value.code == 2


def test_release_mode_refuses_fail_rows_and_missing_signoff(capsys, env):
    rows = {**_known_limit_rows(), "5": ("fail", PASS_EVIDENCE)}
    code, out = _release(capsys, env, _fill(rows=rows))
    assert code == 1 and "row 5: readiness_row_failed" in out
    # a fail row alone is a complete instance outside release mode
    code, _ = _run(capsys, env[0], _fill(rows=rows))
    assert code == 0
    for key, value in (
        ("signoff.owner", ""),
        ("signoff.date", "5 December"),
        ("signoff.decision", "no-go"),
    ):
        text = _fill(rows=_known_limit_rows(), keys={key: value})
        code, out = _release(capsys, env, text)
        assert code == 1 and f"{key}: readiness_signoff_missing" in out, key


@pytest.mark.parametrize(
    "key,new",
    [
        ("g7.cli_sha", "e" * 40),
        ("g7.engine_tag", "v0.31.0"),
        ("g7.engine_commit", "e" * 40),
        ("g7.sha256sums_sha256", DIGEST2),
    ],
)
def test_release_mode_refuses_identity_drift(capsys, env, key, new):
    # the candidate matches the drifted G7 value, so only the G3/G5 compare can fire
    _candidate(env[3], **{key.split(".", 1)[1]: new})
    text = _fill(rows=_known_limit_rows(), keys={key: new})
    code, out = _release(capsys, env, text)
    assert code == 1 and "readiness_identity_drift" in out
    assert "readiness_candidate_mismatch" not in out
    # a rerun line for the new value accepts the drift
    rerun = {f"rerun.{key.split('.', 1)[1]}": new}
    text = _fill(rows=_known_limit_rows(), keys={key: new, **rerun})
    code, out = _release(capsys, env, text)
    assert code == 0, out


def test_release_mode_refuses_a_blank_or_malformed_identity(capsys, env):
    for key, bad in (
        ("g3.cli_sha", ""),
        ("g5.sha256sums_sha256", "abc"),
        ("g7.engine_tag", "main"),
    ):
        text = _fill(rows=_known_limit_rows(), keys={key: bad})
        code, out = _release(capsys, env, text)
        assert code == 1 and f"{key}: readiness_identity_missing" in out, key


def test_a_duplicate_identity_key_is_refused(capsys, tmp_path):
    text = _fill() + f"- g3.cli_sha: {SHA2}\n"
    code, out = _run(capsys, tmp_path, text)
    assert code == 1 and "readiness_duplicate_key" in out


def test_stale_instance_against_a_newer_candidate_is_refused(capsys, env):
    for field, newer in (("cli_sha", "e" * 40), ("sha256sums_sha256", DIGEST2)):
        _candidate(env[3], **{field: newer})
        code, out = _release(capsys, env)
        assert code == 1, field
        assert f"g7.{field}: readiness_candidate_mismatch" in out
    _candidate(env[3])
    for field, newer in (
        ("engine_tag", "v0.31.0"),
        ("engine_commit", "e" * 40),
        ("cli_version", "0.9.0"),
    ):
        _candidate(env[3], **{field: newer})
        code, out = _release(capsys, env)
        assert code == 1 and "readiness_candidate_mismatch" in out, field


def test_engine_repo_known_limit_missing_from_instance_is_refused(capsys, env):
    only_cli = {"4": ("accepted-known-limit", CLI_LIMIT)}
    code, out = _release(capsys, env, _fill(rows=only_cli))
    assert code == 1 and "readiness_known_limit_missing" in out
    assert ENGINE_LIMIT not in out and CLI_LIMIT not in out  # ids stay out of the log
    only_engine = {"4": ("accepted-known-limit", ENGINE_LIMIT)}
    code, out = _release(capsys, env, _fill(rows=only_engine))
    assert code == 1 and "readiness_known_limit_missing" in out
    # without --engine-repo the known-limit enumeration does not run
    code, out = _run(capsys, env[0], _fill(rows=only_cli))
    assert code == 0, out


def test_an_unreadable_map_fails_closed(capsys, env):
    (env[2] / "docs/frozen-surfaces.md").unlink()
    code, out = _release(capsys, env)
    assert code == 1 and "readiness_map_unreadable" in out and "Traceback" not in out
    (env[1] / "docs/release/frozen-surfaces.md").write_text(
        "| a | b | c | accepted-known-limit: |\n", encoding="utf-8"
    )
    _map(env[2] / "docs/frozen-surfaces.md", "`t.py`")
    code, out = _release(capsys, env)
    assert code == 1 and "readiness_map_malformed" in out


def test_release_mode_refuses_counsel_markers_and_licensor_mismatch(capsys, env):
    _, cli, engine, _ = env
    classes = ("release-blocking", "carry-forward")
    # a release-blocking marker that remains
    (cli / "LICENSING.md").write_text(f"Copyright 2026 {LICENSOR}\nTODO(counsel): review\n")
    marker = "cli:LICENSING.md TODO(counsel) => release-blocking"
    code, out = _release(capsys, env, markers=[marker])
    assert code == 1 and "file cli:LICENSING.md: readiness_marker_blocking" in out
    # classified carry-forward is allowed
    code, out = _release(capsys, env, markers=[marker.replace(classes[0], classes[1])])
    assert code == 0, out
    # an unclassified marker, in the CLI tree and in the engine tree
    code, out = _release(capsys, env)
    assert code == 1 and "file cli:LICENSING.md: readiness_marker_unclassified" in out
    (cli / "LICENSING.md").write_text(f"Copyright 2026 {LICENSOR}\n")
    (engine / "README.md").write_text(f"Copyright 2026 {LICENSOR}\n(TODO: confirm inbox)\n")
    code, out = _release(capsys, env)
    assert code == 1 and "file engine:README.md: readiness_marker_unclassified" in out
    code, out = _release(capsys, env, markers=["engine:README.md TODO: => release-blocking"])
    assert code == 1 and "file engine:README.md: readiness_marker_blocking" in out
    # a classification line for a marker that is gone is stale
    (engine / "README.md").write_text(f"Copyright 2026 {LICENSOR}\n")
    code, out = _release(capsys, env, markers=["engine:README.md TODO: => carry-forward"])
    assert code == 1 and "readiness_marker_stale" in out
    # a marker in an engine file is not read without --engine-repo
    (engine / "README.md").write_text(f"Copyright 2026 {LICENSOR}\nTODO(x): y\n")
    code, out = _release(capsys, env, engine=False)
    assert code == 0, out


def test_licensor_mismatch_and_blank_licensor(capsys, env):
    _, cli, engine, _ = env
    (cli / "NOTICE").write_text("Copyright 2026 Decoy Labs LLC\n")
    code, out = _release(capsys, env)
    assert code == 1 and "file cli:NOTICE: readiness_licensor_mismatch" in out
    assert "Decoy Labs" not in out and LICENSOR not in out
    _legal_tree(cli, "cli")
    (engine / "LICENSE").write_text("Licensor: Someone Else Inc\n")
    code, out = _release(capsys, env)
    assert code == 1 and "file engine:LICENSE: readiness_licensor_mismatch" in out
    _legal_tree(engine, "engine")
    for blank in ("", "TBD", "<name>"):
        text = _fill(rows=_known_limit_rows(), keys={"licensor": blank})
        code, out = _release(capsys, env, text)
        assert code == 1 and "licensor: readiness_licensor_missing" in out, blank


def test_missing_license_files_and_absent_licensor_lines_fail_closed(capsys, env):
    _, cli, _, _ = env
    (cli / "TRADEMARKS.md").unlink()
    code, out = _release(capsys, env)
    assert code == 1 and "file cli:TRADEMARKS.md: readiness_file_unreadable" in out
    _legal_tree(cli, "cli", extra={n: "no notice here\n" for n in LEGAL_FILES["cli"]})
    code, out = _release(capsys, env, engine=False)
    assert code == 1 and "readiness_licensor_lines_absent" in out


def test_output_never_echoes_file_content(capsys, env):
    secret = "SECRET-CELL-VALUE-9931"
    _, cli, _, _ = env
    (cli / "NOTICE").write_text(f"Copyright 2026 {secret}\nTODO({secret}): x\n")
    code, out = _release(capsys, env, _fill(rows={"3": ("pass", secret)}))
    assert code == 1 and secret not in out
    code, out = _release(capsys, env, _fill(rows={"3": (secret, PASS_EVIDENCE)}))
    assert secret not in out
    text = _fill().replace("| 9 |", f"| {secret} |", 1)
    code, out = _release(capsys, env, text)
    assert code == 1 and secret not in out and "row ?: readiness_row_unknown" in out


@pytest.mark.parametrize(
    "line",
    [
        "  Copyright 2026 {n}",
        "Copyright (c) 2026 {n}",
        "Copyright (C) 2026 {n}",
        "Copyright \u00a9 2026 {n}",
        "\u00a9 2026 {n}",
        "**Copyright 2026 {n}**",
        "_Copyright 2026-2027 {n}_",
        "> Copyright 2026, {n}",
        "COPYRIGHT 2026 {n}",
        "**Licensor:** {n}",
        "  Licensor: {n}",
    ],
)
def test_licensor_line_forms_are_all_compared(capsys, env, line):
    _, cli, _, _ = env
    good = line.format(n=LICENSOR)
    (cli / "NOTICE").write_text(good + "\n")
    code, out = _release(capsys, env)
    assert code == 0, (good, out)
    (cli / "NOTICE").write_text(line.format(n="Old Entity Corp") + "\n")
    code, out = _release(capsys, env)
    assert code == 1 and "file cli:NOTICE: readiness_licensor_mismatch" in out, line


@pytest.mark.parametrize(
    "sentence",
    [
        "This product includes software developed by Decoy Labs LLC.",
        "You must obtain written permission from Decoy Labs, Inc. to do that.",
        "marks of Decoy Labs Inc.",
    ],
)
def test_a_sentence_naming_the_old_entity_is_refused(capsys, env, sentence):
    _, cli, _, _ = env
    # the copyright lines are already updated; only the prose still names the old entity
    (cli / "TRADEMARKS.md").write_text(f"Copyright 2026 {LICENSOR}\n{sentence}\n")
    code, out = _release(capsys, env)
    assert code == 1 and "file cli:TRADEMARKS.md: readiness_licensor_mismatch" in out
    # a sentence that names the current licensor is fine
    (cli / "TRADEMARKS.md").write_text(f"Copyright 2026 {LICENSOR}\nOwned by {LICENSOR}.\n")
    code, out = _release(capsys, env)
    assert code == 0, out


def test_known_limit_marker_in_a_middle_cell_is_found(capsys, env):
    _, cli, _, _ = env
    (cli / "docs/release/frozen-surfaces.md").write_text(
        "| s | src | accepted-known-limit: V2-LOG cli-9 | `t.py` |\n"
    )
    code, out = _release(capsys, env)  # rows list only cli-1 and eng-7
    assert code == 1 and "map cli: readiness_known_limit_missing" in out


def test_row_text_changed_from_the_template_is_refused(capsys, env):
    text = _fill(rows=_known_limit_rows())
    weaker = text.replace("Green. Every accepted-known-limit", "Green. Some accepted-known-limit")
    assert weaker != text
    code, out = _release(capsys, env, weaker)
    assert code == 1 and "row 4: readiness_row_text_changed" in out
    assert "Some" not in out
    for old, new in (("| G3 |", "| G9 |"), ("`scripts/release/launch_pin_check.py`", "`true`")):
        code, out = _release(capsys, env, text.replace(old, new, 1))
        assert code == 1 and "readiness_row_text_changed" in out, old
    owner = text.replace("| orchestrator |", "| nobody |", 1)
    code, out = _release(capsys, env, owner)
    assert code == 1 and "readiness_row_text_changed" in out
    (env[1] / "docs/release/release-readiness.md").unlink()
    code, out = _release(capsys, env)
    assert code == 1 and "readiness_template_unreadable" in out


def test_the_release_version_comes_from_the_cli_version_file(capsys, env):
    version_file = env[1] / "src/decoy/_version.py"
    version_file.write_text('__version__ = "1.2.0"\n')
    code, out = _release(capsys, env)  # candidate says 1.0.0
    assert code == 1 and "candidate.cli_version: readiness_candidate_mismatch" in out
    _candidate(env[3], cli_version="1.2.0")
    code, out = _release(capsys, env)
    assert code == 0, out
    for bad in ("no version here\n", ""):
        version_file.write_text(bad)
        code, out = _release(capsys, env)
        assert code == 1 and "version: readiness_version_unreadable" in out
    version_file.unlink()
    code, out = _release(capsys, env)
    assert code == 1 and "readiness_version_unreadable" in out and "Traceback" not in out


@pytest.mark.parametrize("owner", ["", "TBD", "tbd", "<owner>"])
def test_a_placeholder_signoff_owner_is_refused(capsys, env, owner):
    text = _fill(rows=_known_limit_rows(), keys={"signoff.owner": owner})
    code, out = _release(capsys, env, text)
    assert code == 1 and "signoff.owner: readiness_signoff_missing" in out
