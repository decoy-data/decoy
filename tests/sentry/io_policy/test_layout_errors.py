"""G-ONE-LAYOUT-CODE: every `layout.*` and `report.*` code lives in the registry
`cli/io/_layout_errors.py`.

- no string literal in `src/` outside the registry carries a `layout.<code>` or `report.<code>`
  token (docstrings aside), so gate findings, command errors and tests of those read one source;
- the registry is well formed: unique codes, each `layout.` plus lower-case words, every gate
  descriptor reachable through `decoy.cli.io` and its code in the CI rule-code set;
- code outside `cli/io` imports the layout services from the public `decoy.cli.io` package,
  never from `_layout`, `_project`, `_pipelines` or `_layout_errors`.

- AT-S4b: the gate and warning vocabulary (`GATE_CODES`, `WARNING_CODES`, `_CLI_GATE_CODES`) is an
  exact snapshot, so adding, removing or renaming a reason code changes this file in review.

Named limit: a code assembled at run time (`"layout." + name`) is not seen.
Other reason codes, including `CLI_WARNING_CODES`, are not pinned.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import decoy.cli.io as public
from decoy.ci.rule_codes import _CLI_GATE_CODES
from decoy.cli.io import _layout_errors as registry

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src" / "decoy"
REGISTRY_FILE = "cli/io/_layout_errors.py"
PRIVATE_MODULES = ("_layout", "_project", "_pipelines", "_layout_errors")
_TOKEN = re.compile(r"(?<![\w.])(?:layout|report)\.[a-z]+(?:_[a-z]+)+")
_CODE = re.compile(r"(?:layout|report)\.[a-z]+(?:_[a-z]+)+")
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)


def _docstrings(tree: ast.AST) -> set[int]:
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, _SCOPES) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                found.add(id(first.value))
    return found


def literal_findings(source: str, rel: str) -> list[str]:
    """`file:line` of each string literal that carries a `layout.<code>` or `report.<code>` token."""
    if rel == REGISTRY_FILE:
        return []
    tree = ast.parse(source)
    docs = _docstrings(tree)
    return [
        f"{rel}:{node.lineno} {match.group(0)}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs
        for match in _TOKEN.finditer(node.value)
    ]


def import_findings(source: str, rel: str) -> list[str]:
    """`file:line` of each import of a private layout module from outside `cli/io/`."""
    if rel.startswith("cli/io/"):
        return []
    bad = {f"decoy.cli.io.{m}" for m in PRIVATE_MODULES}
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [f"{rel}:{node.lineno} {a.name}" for a in node.names if a.name in bad]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            if node.module in bad:
                found.append(f"{rel}:{node.lineno} {node.module}")
            elif node.module == "decoy.cli.io":
                found += [
                    f"{rel}:{node.lineno} {node.module}.{a.name}"
                    for a in node.names
                    if a.name in PRIVATE_MODULES
                ]
    return found


def _scan(finder) -> list[str]:  # type: ignore[no-untyped-def]
    out: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        out += finder(path.read_text(encoding="utf-8"), path.relative_to(SRC).as_posix())
    return out


def test_no_layout_code_is_written_outside_the_registry() -> None:
    assert _scan(literal_findings) == []


def test_nothing_outside_cli_io_imports_a_private_layout_module() -> None:
    assert _scan(import_findings) == []


def test_the_registry_codes_are_unique_and_well_formed() -> None:
    every = registry.GATE_DESCRIPTORS + registry.WARNING_DESCRIPTORS
    codes = [d.code for d in every]
    assert len(set(codes)) == len(codes)
    assert all(_CODE.fullmatch(c) for c in codes)
    assert registry.GATE_CODES.isdisjoint(registry.WARNING_CODES)


def test_every_descriptor_in_the_module_is_listed() -> None:
    declared = {v.code for v in vars(registry).values() if isinstance(v, registry.Descriptor)}
    listed = registry.GATE_CODES | registry.WARNING_CODES
    assert declared == listed


def test_the_registry_is_exported_through_the_public_package() -> None:
    for name in (
        "GATE_CODES",
        "GATE_DESCRIPTORS",
        "WARNING_CODES",
        "WARNING_DESCRIPTORS",
        "Descriptor",
        "LayoutError",
        "LayoutWarning",
    ):
        assert name in public.__all__
        assert getattr(public, name) is getattr(registry, name)


def test_every_gate_code_is_in_the_derived_ci_rule_set() -> None:
    from decoy.ci.rule_codes import validation_codes

    assert public.GATE_CODES <= validation_codes()


def test_a_layout_error_text_is_the_fixed_message_and_nothing_more() -> None:
    err = registry.OUTPUT_PATH_ESCAPES.error(path="a/b", base="/p/out/x")
    assert err.code == "layout.output_path_escapes"
    assert (
        str(err) == err.message == registry.OUTPUT_PATH_ESCAPES.message(path="a/b", base="/p/out/x")
    )
    assert err.__cause__ is None
    assert err.__context__ is None


@pytest.mark.parametrize(
    "source",
    [
        'CODE = "layout.project_not_found"\n',
        'def f():\n    return {"rule": "layout.pipeline_unknown"}\n',
        'x = f"bad layout.output_path_escapes {y}"\n',
        'CODE = "report.source_ambiguous"\n',
    ],
)
def test_a_layout_code_literal_outside_the_registry_is_caught(source: str) -> None:
    assert literal_findings(source, "cli/run.py") != []
    assert literal_findings(source, REGISTRY_FILE) == []


def test_a_docstring_may_mention_a_code() -> None:
    assert literal_findings('"""Raises layout.project_not_found."""\n', "cli/run.py") == []


@pytest.mark.parametrize(
    "source",
    [
        "from decoy.cli.io._project import find_project\n",
        "from decoy.cli.io import _layout\n",
        "import decoy.cli.io._layout_errors\n",
        "from decoy.cli.io._pipelines import resolve_pipeline\n",
    ],
)
def test_a_private_layout_import_outside_cli_io_is_caught(source: str) -> None:
    assert import_findings(source, "cli/run.py") != []
    assert import_findings(source, "cli/io/_targets.py") == []


def test_the_public_import_is_allowed() -> None:
    assert import_findings("from decoy.cli.io import find_project\n", "cli/run.py") == []


# AT-S4b snapshot.
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
        "layout.delivery_member_too_deep",
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
        "layout.publication_commit_uncertain",
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


def test_gate_codes_snapshot_is_the_layout_set_plus_the_report_set() -> None:
    assert public.GATE_CODES == LAYOUT_GATE_CODES | REPORT_CODES


def test_report_descriptors_hold_exactly_the_report_codes() -> None:
    assert {d.code for d in public.REPORT_DESCRIPTORS} == REPORT_CODES
    assert set(public.REPORT_DESCRIPTORS) <= set(public.GATE_DESCRIPTORS)


def test_warning_codes_snapshot() -> None:
    assert public.WARNING_CODES == WARNING_SNAPSHOT


def test_cli_gate_codes_snapshot() -> None:
    assert _CLI_GATE_CODES == CLI_GATE_SNAPSHOT
