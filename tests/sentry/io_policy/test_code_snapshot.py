"""AT-S4b: the gate and warning vocabulary is pinned as an exact snapshot.

A reason code is a frozen name (`--json` error `code`, CI report `rule_id`). Adding, removing
or renaming a code in `GATE_CODES`, `WARNING_CODES` or `_CLI_GATE_CODES` must change this file,
so the change is visible in review. Named limit: other reason codes are not pinned.
"""

from __future__ import annotations

from decoy.ci.rule_codes import _CLI_GATE_CODES
from decoy.cli.io import _layout_errors as registry

LAYOUT_GATE_CODES = frozenset(
    {
        "layout.project_marker_invalid",
        "layout.project_marker_untrusted",
        "layout.project_not_found",
        "layout.project_mismatch",
        "layout.pipeline_unknown",
        "layout.pipeline_name_invalid",
        "layout.pipeline_name_mismatch",
        "layout.pipeline_name_collision",
        "layout.output_path_escapes",
        "layout.path_too_long",
        "layout.output_path_collision",
        "layout.output_dir_unusable",
        "layout.project_root_refused",
        "layout.delivery_root_split",
        "layout.side_file_in_out",
        "layout.cloud_target_invalid",
        "layout.cloud_target_unsupported",
    }
)
REPORT_CODES = frozenset({"report.source_ambiguous"})
WARNING_SNAPSHOT = frozenset(
    {
        "layout.latest_invalid",
        "layout.latest_link_failed",
        "layout.latest_write_failed",
        "layout.gitignore_write_failed",
        "layout.report_not_written",
        "layout.project_nested",
        "layout.config_inside_out",
    }
)
CLI_GATE_SNAPSHOT = frozenset(
    {
        "capacity.out_of_core_fk",
        "capacity.plan_uncompilable",
        "capacity.source_unreadable",
        "compile_error",
        "compile.needs_profile",
        "compile_warning",
        "missing_extra",
        "source.declared_columns",
        "source.declared_columns_not_checked",
        "native.companion",
        "native.eligibility",
        "pipeline.validation_error",
        "target_format_suffix_mismatch",
        "target_format_unknown",
        "validation_error",
        "yaml.empty",
        "yaml.not_mapping",
        "yaml.not_utf8",
        "yaml.parse_error",
    }
)


def test_gate_codes_are_the_layout_set_plus_the_report_set() -> None:
    assert registry.GATE_CODES == LAYOUT_GATE_CODES | REPORT_CODES


def test_report_descriptors_hold_exactly_the_report_codes() -> None:
    assert {d.code for d in registry.REPORT_DESCRIPTORS} == REPORT_CODES
    assert set(registry.REPORT_DESCRIPTORS) <= set(registry.GATE_DESCRIPTORS)


def test_warning_codes_snapshot() -> None:
    assert registry.WARNING_CODES == WARNING_SNAPSHOT


def test_cli_gate_codes_snapshot() -> None:
    assert _CLI_GATE_CODES == CLI_GATE_SNAPSHOT
