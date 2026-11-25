"""``decoy report`` -- the single post-run surface over local run artifacts.

Every subcommand is file-first: it reads only the evidence manifest path(s) it
is given (and, where noted, the source/output data files those manifests or
arguments reference). There is no run catalog or workspace.

  show      -- Summarize one evidence manifest (the union card) or render a file.
  render    -- Write an HTML or Markdown report to a file.
  verify    -- Re-hash the recorded files and report fingerprint drift.
  fidelity  -- Recompute distribution fidelity between a source and an output.
  integrity -- Verify a masked file against its pre-mask source (post-mask checks).
  diff      -- Compare two manifests: fingerprints always, data when files exist.
  vault     -- Inspect a vault file written by `decoy run --vault`.

S4b (CLI redesign) folded the former `report summarize` + `report compare`,
the `evidence` verbs (show/verify), the `validate` distribution check, the
old integrity check group, and `vault info` into this one noun. The relocated
bodies are reused verbatim; their engine deps stay lazy-imported inside each
body.

RAW-VALUE ISOLATION (Dennis review note, cli-first-capability-guide.md L534-538):

  Reports build from evidence-safe data only. The manifest already excludes
  raw row values (strategy names + fingerprints + metadata only), so rendering
  the manifest is safe by construction.

  The manifest renderers accept a manifest DICT and render it. They do NOT:
    - Read source or output CSV files from disk.
    - Embed raw cell/row values in any report.
    - Render full scan profiles or raw diagnostic values.

  What is intentionally excluded is stated in each report footer so reviewers
  know the omission is deliberate. (`fidelity`/`integrity` DO read the data
  files they are pointed at, by design -- they report aggregate metrics only.)
"""

from __future__ import annotations

import typer

# Command modules are imported whole: binding `_show` (the function) here would hide the
# `decoy.cli.report._show` submodule, so a patch path through it would miss the moved code.
from decoy.cli.report import _diff, _fidelity, _integrity, _render, _show, _verify
from decoy.cli.report._compare import compare_data, compare_manifests
from decoy.cli.report._html import render_html
from decoy.cli.report._markdown import render_markdown
from decoy.cli.reports import VAULT_EPILOG, vault_command

report_app = typer.Typer(
    name="report",
    help=(
        "The post-run surface: show / render / verify / fidelity / integrity / "
        "diff / vault. Operates on files -- evidence manifests produced by "
        "`decoy run --evidence-out` plus the source/output data they reference."
    ),
    no_args_is_help=True,
)

report_app.command(name="show", epilog=_show._SHOW_EPILOG)(_show._show)
report_app.command(name="render", epilog=_render._RENDER_EPILOG)(_render._render)
report_app.command(name="verify", epilog=_verify._VERIFY_EPILOG)(_verify._verify)
report_app.command(name="fidelity", epilog=_fidelity._FIDELITY_EPILOG)(_fidelity._fidelity)
report_app.command(name="integrity", epilog=_integrity._INTEGRITY_EPILOG)(_integrity._integrity)
report_app.command(name="diff", epilog=_diff._DIFF_EPILOG)(_diff._diff)
report_app.command(name="vault", epilog=VAULT_EPILOG)(vault_command)

# Public exports
__all__ = [
    "compare_data",
    "compare_manifests",
    "render_html",
    "render_markdown",
    "report_app",
]
