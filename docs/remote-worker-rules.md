Status: current

# Rules for every remote worker

Read this before you start any handoff. Handoffs for the CLI repo (decoy-data/decoy) and the engine (decoy-data/decoy-engine) both point here. A handoff can add rules or change one of these; when it does, the handoff wins for that task.

## Your role

You build and test on your own nodes. You never review your own work and you never merge. The orchestrator runs the reviews (Dennis and Codex), gates the exact head and merges.

Report each PR as:
- PR number and exact head SHA
- red-first evidence
- mutation table
- test counts with the command
- OS lanes run and not run
- CI state

## V1 bar and scope

- Only these block V1: a function break, data loss, or a real value or secret reaching a non-admin. Anything else you notice goes in the PR body or the evidence record as V2-LOG. Do not build it.
- V1 threat model: accidental leaks and accidental data loss only. Hostile same-user attacks are V2.
- Scope is fixed. A new feature is an owner decision: stop and report.
- A new dependency is an owner decision: stop and report before you add it to `pyproject.toml` or `uv.lock`.

## Code rules

- Records, logs and error messages are value-free. They hold names, counts, digests and codes only, never data values or expression text.
- One central mechanism per concern. Never write a second copy of a registry, reader, writer or width rule. If an owner for the concern exists, use it.
- Never raise a ceiling, pin, cap, sentry baseline, census or allowlist. Never skip a test or weaken an assertion to make a change pass. A new module that a sentry must register is allowed only when your plan names it, with a one-line reason.
- Engine:
  - Never edit `tests/fixtures/f29/reason-baseline.json` (a frozen digest), `REGISTRY_VERSION` or the release manifests.
  - New reason codes use `since=UNRELEASED`.
  - Do not add new top-level files to `execution/`.
- CLI: do not add new top-level files to `src/decoy/cli/`. New commands go in a sub-package.
- Comments explain why, not what. Leave task ids, review rounds, dates and names out of comments.

## Git

- Commit subject: Conventional Commits, at most 72 characters. Final line `cam`. Author `ckeep <decoy@trydecoy.com>`. No other trailers.
- Never force-push and never rebase a pushed branch. If `main` moves, merge `origin/main` into your branch.
- For stacked slices, each slice branches from the slice it depends on, and its PR base is that branch.
- An engine PR needs two things:
  - the `docs/compatibility-contract.md` section 9 checklist in the PR body, with only the true boxes ticked (`compat-preflight`);
  - a `changelog.d/` fragment for each feat or fix (`changelog-fragment`).

## Tests

- Per slice:
  - Red-first tests are the first commit. Record them red, with the reason.
  - Apply every mutation the plan names once, show it red, then revert it. List each one in a table in the PR body, with the head it ran on.
- T1 runs on the exact head and covers:
  - the slice's tests and `tests/sentry`;
  - `ruff check`, `ruff format --check` and mypy;
  - `scripts/dev/gates.sh --steps layers`.
  
  Do not run the full suite per slice. The orchestrator runs it before the merge.
- `tests/unit/test_import_layers.py` needs importlinter, which only the layers environment has. Run it through `gates.sh --steps layers`.
- If `main` has known failures that are not yours, the handoff names them. Do not fix them. Report anything else that is red.

## Stop and report when

- the plan is wrong, or says nothing about something that changes a guarantee, a record format or a public CLI surface;
- a defect of a class the plan already closes appears again, or one of a class in the recurring-defect catalog. Name the class of each finding you report;
- a size or census number would have to rise, or a test would need to be weakened;
- you need an owner decision, a new dependency or new spend.
