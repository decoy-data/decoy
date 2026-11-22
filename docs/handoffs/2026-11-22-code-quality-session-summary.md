# Handoff: code-quality planning session, what was completed

Status: current. Written 2026-11-22. For the owner and whoever picks up the code-quality work next.

## Completed

1. **Inventory of planned code-quality remediation.** Read the roadmap health group, the
   duplication census (2026-11-12), the proportionality audit (2026-11-15) and the engine
   clean-architecture review (2026-11-21), and collected every planned item by kind: module size and
   splits, directory structure and layering, imports and shims, one registry instead of many copies,
   quiet fallbacks, comments, tests, guards and docs. Measured today's oversize files in both repos.
2. **Gap scan.** Counted markers no audit covers yet: broad `except` (engine 457, CLI 84),
   `# type: ignore` and `# noqa`, `pragma: no cover`, skip and xfail markers, heavy mocking,
   `time.sleep` in tests, string-built paths (Windows is in 1.0).
3. **Audit timing decided as a recommendation.** Full read-only audit at V1 alpha, beside QA,
   triaged with QA findings; a delta pass before REL-GATE; a narrow freeze-surface audit now.
4. **Pre-merge check proposal.** Three tiers: a `lintdebt` ruff ratchet in `gates.sh`; `/simplify`
   and `/code-review` on every PR diff before the Codex and Dennis gates; `/security-review`, a
   Windows checklist and the freeze questions by area.

All of it is written up in
[2026-11-22-code-quality-audit-and-pre-merge-checks.md](2026-11-22-code-quality-audit-and-pre-merge-checks.md).
Three untriaged lines in [inbox.md](../roadmap/inbox.md) route it to triage.

## Not done

- **Dev-loop edit.** The tier B and C steps belong in `~/dev-rules/development-loop.md` (dev-rules
  repo), which was not available.
- **`lintdebt` step.** Not built. Plan it as a slice of row 24ze or 24zl (same baseline machinery).
- **Release gates.** The alpha audit and the delta pass go into `roadmap/release-gates.md` R1 after
  triage.
- **H-1 detail.** The H-1 Wave B plan lives in the private platform repo and was not read; its
  split list is not in the inventory.

## Next steps

1. Review and merge the PR from branch `docs/code-quality-handoff`.
2. Owner answers the five questions in section 6 of the main handoff.
3. Triage the three inbox lines.
4. Edit the dev loop and build `lintdebt`.
5. Run the narrow freeze-surface audit before alpha.
