"""End-to-end tests for `decoy explain`."""

from __future__ import annotations

import json as _json

from typer.testing import CliRunner

from decoy.__main__ import app
from decoy.cli.explain import topic_names
from tests.sentry.release.test_retired_name_residual import RETIRED_NAME, RETIRED_PATTERN

runner = CliRunner()


def test_explain_help_includes_examples():
    result = runner.invoke(app, ["explain", "--help"])
    assert result.exit_code == 0
    assert "Examples:" in result.stdout
    assert "See also:" in result.stdout


def test_explain_no_topic_lists_index():
    result = runner.invoke(app, ["explain"])
    assert result.exit_code == 0
    # Listing should mention several known topics.
    for topic in ("modes", "transforms", "disguises", "output"):
        assert topic in result.stdout


def test_explain_known_topic_renders_panel():
    result = runner.invoke(app, ["explain", "modes"])
    assert result.exit_code == 0
    # Panel title carries the topic name.
    assert "modes" in result.stdout
    assert "mask" in result.stdout
    assert "generate" in result.stdout


def test_explain_unknown_topic_suggests_close_match():
    result = runner.invoke(app, ["explain", "scn"])
    assert result.exit_code == 1
    # Cause + did-you-mean hint per CLI_UX_GUIDE.md section 9.
    assert "unknown topic" in result.stderr.lower()
    assert "scan" in result.stderr


def test_explain_unknown_topic_no_close_match_falls_back_to_list_hint():
    result = runner.invoke(app, ["explain", "zzzzzz"])
    assert result.exit_code == 1
    # No close match -- hint should point to the listing command.
    assert "decoy explain" in result.stderr


def test_explain_json_emits_full_topic():
    result = runner.invoke(app, ["explain", "transforms", "--json"])
    assert result.exit_code == 0
    payload = _json.loads(result.stdout)
    assert payload["command"] == "explain"
    assert payload["status"] == "ok"
    assert payload["topic"] == "transforms"
    assert payload["body"]
    assert payload["summary"]


def test_explain_json_index_lists_topics():
    result = runner.invoke(app, ["explain", "--json"])
    assert result.exit_code == 0
    payload = _json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert {t["name"] for t in payload["topics"]} == set(topic_names())


def test_explain_json_unknown_topic_emits_error_envelope():
    result = runner.invoke(app, ["explain", "scn", "--json"])
    assert result.exit_code == 1
    payload = _json.loads(result.stdout)
    assert payload["status"] == "error"
    assert payload["did_you_mean"] == "scan"


def test_explain_quiet_produces_empty_stdout():
    result = runner.invoke(app, ["explain", "modes", "--quiet"])
    assert result.exit_code == 0
    assert result.stdout == ""


def test_topic_names_covers_load_bearing_concepts():
    """Sanity check: the topic set must include the load-bearing concepts.

    CLI.4 (2026-06-02): forecast topic dropped (FORECAST retired with
    the V1 recommender removal). The remaining topics cover the V2 surface.
    """
    names = set(topic_names())
    expected = {"modes", "transforms", "disguises", "output", "pipeline", "scan", "keys"}
    missing = expected - names
    assert not missing, f"missing topics: {missing}"
    # CLI.1 + CLI.4 (2026-06-02): forecast topic removed; the explain
    # body across other topics now describes the removal rather than
    # documenting a deleted command.
    assert "forecast" not in names


def test_modes_topic_describes_per_table_inference_not_top_level_key():
    """Regression: the `modes` topic claimed mode is read from a top-level
    `mode:` YAML key, which FC-1 (2026-06-02) removed. It must describe
    per-table inference (columns vs generate_columns) instead, matching the
    engine and the `pipeline` topic."""
    from decoy.cli.explain import _TOPICS

    body = _TOPICS["modes"].body
    assert "inferred per-table" in body
    # The stale claim must not return.
    assert "read from the YAML's top-level `mode:` key when present" not in body


def test_feature_topics_are_documented():
    """The recently-shipped run features + DP must each have an explain
    topic so they are discoverable from `decoy explain`."""
    names = set(topic_names())
    for t in ("vault", "chunked", "substrate", "differential-privacy", "extras"):
        assert t in names, f"missing explain topic: {t}"


def test_extras_topic_lists_every_pass_through_extra():
    """CLI install DX (2026-09-25): `decoy explain extras` is the in-CLI
    reference for the pass-through extras added to pyproject.toml; it must
    name every one of them with its exact install line."""
    result = runner.invoke(app, ["explain", "extras"])
    assert result.exit_code == 0
    for extra in ("cloud", "vault", "all"):
        assert f"decoy-cli[{extra}]" in result.stdout, result.stdout
    assert "decoy models install ner" in result.stdout, result.stdout
    assert "decoy-cli[ml]" not in result.stdout, "the ml extra is gone (SCAN-ML C1)"


def test_explain_keys_states_the_keyed_mask_secret_is_required():
    """Engine >=0.17.0 removed the pre-GA job_seed fallback: keyed masking with no
    admitted secret fails with keyed_strategy_requires_secret in every phase."""
    result = runner.invoke(app, ["explain", "keys", "--json"])
    assert result.exit_code == 0, result.stdout
    body = _json.loads(result.stdout)["body"]
    assert "keyed_strategy_requires_secret" in body
    assert "falling back to job_seed" not in body
    assert "still run" not in body


def test_explain_differential_privacy_says_dp_is_certified_only():
    result = runner.invoke(app, ["explain", "differential-privacy", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = _json.loads(result.stdout)
    assert "certified installs only" in payload["summary"]
    first_paragraph = " ".join(payload["body"].split("\n\n")[0].split())
    assert "certified" in first_paragraph
    assert "--include-values" in first_paragraph

    listing = runner.invoke(app, ["explain", "--json"])
    assert listing.exit_code == 0
    topics = {t["name"]: t["summary"] for t in _json.loads(listing.stdout)["topics"]}
    assert "certified installs only" in topics["differential-privacy"]


def test_explain_scan_prints_the_moved_scan_body():
    """AT-C3: the topic the old name held is now `scan`, with the same job."""
    result = runner.invoke(app, ["explain", "scan"])
    assert result.exit_code == 0, result.stderr
    assert "scan" in result.stdout.lower()
    assert RETIRED_PATTERN.search(result.stdout) is None


def test_explain_retired_topic_is_a_usage_error_and_never_suggested():
    """AT-C3: the retired topic name is unknown (usage exit); no suggestion offers it back."""
    assert RETIRED_NAME not in topic_names()
    result = runner.invoke(app, ["explain", RETIRED_NAME, "--json"])
    assert result.exit_code == 1
    payload = _json.loads(result.stdout)
    assert payload["status"] == "error"
    assert RETIRED_NAME not in str(payload.get("did_you_mean", "")).lower()
    human = runner.invoke(app, ["explain", RETIRED_NAME])
    assert human.exit_code == 1
    assert "unknown topic" in human.stderr.lower()


def _flat(*argv: str) -> str:
    result = runner.invoke(app, list(argv))
    assert result.exit_code == 0, result.output
    # Rich draws a panel border on each wrapped line; drop it so a phrase split across lines joins.
    return " ".join(result.output.replace("│", " ").split())


def test_chunked_text_states_the_nondeterministic_categorical_limits():
    """Engine 0.28.4 refuses a non-deterministic categorical for --chunked on uneven weights
    (categorical_nondeterministic_not_chunk_safe) and on an unsupported `when`
    (chunked_categorical_nondeterministic_when_not_supported); both surfaces must say so."""
    for argv in (("explain", "chunked"), ("run", "--help")):
        text = _flat(*argv)
        assert "[1, 1e-9, 1, 1]" in text, argv
        assert "`when`" in text and "text or null" in text, argv


def test_chunked_text_says_chunked_can_run_compiled_kernels():
    """PARQUET-CHUNKED-NULLABLE-INT S2 (AT-C15): after `--chunked` moved to the engine entry
    that can run compiled kernels, no text may call pandas its only substrate."""
    for argv in (
        ("explain", "chunked"),
        ("explain", "native"),
        ("explain", "substrate"),
        ("run", "--help"),
    ):
        text = _flat(*argv)
        assert "compiled kernel" in text, argv
        assert "chunked stream (native)" in text or "chunked stream" in text, argv
        assert "pandas chunked path" not in text, argv
        assert "pandas is the only masking substrate" not in text, argv
        assert "only substrate for both plain and --chunked" not in text, argv
        assert "byte-identical to a plain run" not in text, argv
    assert "chunked stream (pandas)" in _flat("explain", "native")
    substrate = _flat("explain", "substrate")
    assert "one execution adapter" not in substrate
    assert "A plain run uses the engine's unified slice" in substrate
    assert "it can also run with no kernel" in substrate
    assert "Being admitted is not running a kernel" in substrate
    assert "A --chunked run goes through run_mask_chunked with the same rule" in substrate
    assert "--no-native forces pandas on both" in substrate
