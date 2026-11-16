"""AT-C2 (part one): text a command prints at run time holds no retired name.

The banned-text sentry reads help, `explain` topics, string constants and templates. It cannot see
what a command prints while it runs, so this test runs `decoy scan` and `decoy report integrity`
on a synthetic fixture, human and `--json`, and checks every stream. Each command path is found in
the live command tree first, so a renamed path fails here instead of being skipped.

The match uses `RETIRED_PATTERN` from the residual sentry, the object the banned-text registry
takes over once it carries the name. There is no second matcher.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from tests.command_tree import visible_paths
from tests.sentry.release.test_retired_name_residual import RETIRED_PATTERN
from typer.testing import CliRunner

from decoy.__main__ import app

runner = CliRunner()


@pytest.fixture
def pair(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "src.csv"
    masked = tmp_path / "masked.csv"
    pd.DataFrame(
        {
            "customer_id": ["1", "2", "3"],
            "email": ["alice@example.com", "bob@example.com", "carol@example.com"],
            "ssn": ["111-22-3333", "222-33-4444", "333-44-5555"],
        }
    ).to_csv(src, index=False)
    pd.DataFrame(
        {
            "customer_id": ["1", "2", "3"],
            "email": ["fake1@redacted.test", "fake2@redacted.test", "fake3@redacted.test"],
            "ssn": ["000-00-0001", "000-00-0002", "000-00-0003"],
        }
    ).to_csv(masked, index=False)
    return src, masked


def _streams(args: list[str]) -> str:
    result = runner.invoke(app, args)
    assert result.exit_code in (0, 1, 2), (args, result.exit_code, result.output)
    return result.stdout + "\n" + result.stderr


def test_the_command_paths_under_test_still_exist() -> None:
    paths = visible_paths()
    assert ("scan",) in paths
    assert ("report", "integrity") in paths


@pytest.mark.parametrize("json_flag", [[], ["--json"]], ids=["human", "json"])
def test_scan_output_holds_no_retired_name(pair: tuple[Path, Path], json_flag: list[str]) -> None:
    src, _ = pair
    text = _streams(["scan", str(src), "--has-header", *json_flag])
    assert "PII candidate" in text or "pii_candidate" in text  # the footnote path ran
    assert RETIRED_PATTERN.search(text) is None, text


@pytest.mark.parametrize("json_flag", [[], ["--json"]], ids=["human", "json"])
def test_report_integrity_output_holds_no_retired_name(
    pair: tuple[Path, Path], json_flag: list[str]
) -> None:
    src, masked = pair
    text = _streams(["report", "integrity", str(masked), "--source", str(src), *json_flag])
    assert "integrity" in text.lower()
    assert RETIRED_PATTERN.search(text) is None, text
