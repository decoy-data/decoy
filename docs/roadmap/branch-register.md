# Branch register (engine and CLI)

Status: current

Part of the roadmap: [ROADMAP.md](../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

The live list of every branch in every repo, with a category and a suggested action for each, is
`~/obsidian-vault/10_Projects/decoy/BRANCH-LIST.md` in the vault (kept current from branch-watch).
This register keeps only the dispositions the roadmap owns.

Every open row names its branch. A remote branch neither merged nor named here has no owner on record
and is a cleanup candidate (`~/bin/branch-analysis`).

| Branch | What it holds | Disposition |
|---|---|---|
| engine PR #333 `claude/sharp-goodall-ikag71` | superseded A-4 draft | per-branch check, then delete |
| engine `feat/file-access-policy`, `feat/file-access-integrated-wip`, `feat/file-access-sink-coverage`, `claude/laughing-galileo-h18woa` | superseded A-4 work | cleanup candidates |
| engine `claude/youthful-ride-0azacx` (`e780df30`) | earlier copy of the native-release workflow | compare with #353, then retire |
| engine and platform `claude/v2-warehouse-sources-and-tokenization-vault` | warehouse connectors (home F01, F02) | FOLD; HIGH lost-work risk |
| engine `fix/faker-40-31-migration` (`e68b66c1`) | mimesis rebinding regression tests; no merge base | replay by patch after R1 (D-4) |
| engine `feat/b6-batch-vault-writer-engine` (`e3c539d6`) | B-6 batch vault writer | owner: fold into the B-6 core chain or retire |
| engine `feat/f13-e1-file-secret-permissions` (`37f43e47`) | shipped inside A-4 | retire |
| engine `plan/b6-vault-crypto-remediation` (`91488afb`) | B-6 crypto plan | retire after B-6 core merges |
| engine `plan/cdf-exact-arithmetic` (`f89f4ab7`) | built as #363 | retire |
| engine `plan/slice0` (`3a49b782`) | slice 0 plans | retire after slice 0 merges |
| engine `plan/route-coverage-ph2` (`864c2352`), `claude/optimistic-feynman-m5cfy5` (`2086fc73`), `claude/blissful-goldberg-mkwpdk` (`e1f96acb`) | route-coverage phase 2 (post-V1; Codex GO-WITH-FIXES with 5 HIGH) | keep; `blissful-goldberg` HIGH lost-work risk, do not delete |
| CLI `claude/eager-clarke-14deh1` (`7bdbdf97`) | stale rename branch, superseded by rows 16 and 56 | retire after the CLI half |
| CLI `claude/vibrant-feynman-1khw1v` (`8fa00fb2`) | CLI pre-scan and post-scan work | owner: compare with the re-cut CLI slices |
| CLI `feat/f26-local-cleanup`, PR #68 | F26 CLI half | parked until F22 |
| CLI `plan/f43-ci-integration` | F43 plan; built as #69 | retire |

Platform branches are in the platform pause record.

## Added 2026-11-27 from the branch inventory

Added from the 2026-11-27 inventory (`BRANCH-LIST.md` in the vault). "Row" is the roadmap row the branch belongs to; "no row" means none names it.

### Needs testing

| Branch | What it holds | Disposition |
|---|---|---|
| engine `chore/push-gate-pr-only` (#823) | Moves the push gate to PRs while retaining checks on pushes that could lose work. | needs testing; no row. The last fix changes shell argument handling, so verify quoted push and PR arguments on #823. |
| engine `dependabot/github_actions/actions/setup-python-7` (#656) | Upgrades the GitHub Actions Python setup step from v6 to v7. | needs testing; no row. The major setup-python change touches six workflow files and needs a runner check. |
| engine `dependabot/pip/python-minor-patch-b74079fc7b` (#583) | Updates six Python dependencies together in the lockfile. | needs testing; no row. The six dependency updates share one lockfile and need a compatibility run together. |
| CLI `chore/certified-pin-cves-c1` (#345) | Updates four certified runtime pins and checks the allowed dependency changes. | needs testing; row 24zc. Row 24zc requires a matching engine fingerprint before these pins change. |
| CLI `claude/decoy-engine-demo-questions-q9250l` | Adds a 15-minute demo with example pipelines, inputs and CI configuration. | needs testing; no row. The nine demo files are unique and the walkthrough is 153 commits behind main. |
| CLI `dependabot/pip/python-dateutil-3.0.0` (#154) | Changes the certified python-dateutil pin to 3.0.0. | needs testing; no row. PR #154 changes a major version in the certified requirements file. |
| CLI `dependabot/pip/python-minor-patch-c08877b1b9` (#249) | Updates 38 Python dependencies in the package and certified requirements. | needs testing; no row. PR #249 changes both dependency lists in one batch. |
| CLI `feat/chunked-struct-s2` (#387) | Checks nested-column passthrough in both chunked and plain runs. | needs testing; row CHUNKED-STRUCT. Draft #387 supplies the CLI regression test for the fix in engine #754. |
| platform `chore/org-decoy-data` (#203) | Updates workflow and repository links for decoy-data and changes the package author. | needs testing; no row. PR #203 is current with main and its workflow references still need verification. |
| platform `chore/remap-rewritten-shas` (#204) | Updates historical commit references in documents after the Git history rewrite. | needs testing; no row. PR #204 is current with main and the replacement IDs need a resolution check. |
| dev-loop `feat/dash-mission-control` | The dashboard shows live worker activity, displays stalled slices and accepts owner decisions. | needs testing; no row. The worktree has five more dashboard commits, so test the intended tip before integration. |

### Needs development

| Branch | What it holds | Disposition |
|---|---|---|
| engine `docs/plans-gsa-eor-1125` | Plans streamed validation and generation of Faker, provider and lookup columns. | needs development; no row. Check the plan files on the branch for the next step. |
| engine `docs/plans-prop-reanchor-1125` | Updates the plan for silent fallbacks, unused APIs and compatibility shims. | needs development; rows 24zi, 24zj, 24zk. The head marks revision 7 ready for implementation. |
| engine `feat/f01-e0` (#667) | Probes PostgreSQL cancellation during writes, queries and lock waits. | needs development; row 86. Roadmap row 86 records a failed PostgreSQL spike case that blocks E1. |
| engine `plan/deliv-r5-be0-fold` | Folds the V1 best-effort refusal into the staged delivery plan. | needs development; row 61 (DELIV). Revision 5.3 identifies E2a and E2f as ready to build. |
| CLI `docs/plans-inbox-triage-1125` | Plans fixes for example paths, generated scaffold fidelity and validate output. | needs development; no row. The branch has three reviewed plan files and no implementation commits. |
| CLI `docs/plans-init-scan-scaffold-1125` | Plans how init scans sources and writes a scaffold for the user to review. | needs development; no row. Revision 7 replaces the earlier revision 3 and supplies the plan for the remaining slices. |
| CLI `docs/plans-win-runner-1125` | Plans nightly Windows tests, runner monitoring and a runbook. | needs development; row 6. Row 6 still lists the nightly jobs and monitoring. |
| CLI `plan/cli-rel` | Plans the release workflow, publish modes and smoke tests. | needs development; row 94. PR #363 delivered release identity, one part of row 94. |
| CLI `plan/column-shape-rule` | Defines when column types come from a schema and when text inputs require a declaration. | needs development; row COLUMN-SHAPE-RULE. Check the revised plan against the roadmap row. |
| CLI `plan/pre-scan-run` | Plans how run executes the configured pre-scan and records its result. | needs development; row PRE-SCAN-RUN. Engine #748 and #749 landed, while #418 covers the |
| CLI `plan/rel-docs` | Plans the public documentation for the signed CLI release. | needs development; row 92. Row 92 keeps the public docs in draft pending release and web |
| CLI `plan/rel-web` | Plans the download page, update-client contract and proof publication. | needs development; row 91. PRs #272 and #279 shipped |
| CLI `plan/upgrade-key` | Plans rotation and revocation of the CLI update-signing key using an offline backup. | needs development; row UPGRADE-KEY. PR #328 shipped the trust |
| CLI `plan/win-feas` | Plans Windows file access, installer and version-switch behavior. | needs development; row 89. Row 89 records the engine import fix but still lists CLI install |
| web `docs/header-promo-checklist` | It adds a production checklist for the homepage video to the website roadmap. | needs development; no row. Main already ships the video and poster, and the checklist still names Cloudflare Pages instead of GitHub Pages. |

### Rebase

| Branch | What it holds | Disposition |
|---|---|---|
| engine `chore/remap-rewritten-shas` (#662) | Updates stored commit references after the history rewrite. | rebase; no row. All 37 edited paths differ on main, so refresh the hash mapping before accepting #662. |
| engine `claude/pensive-lamport-hn9vqe` (#335) | Adds signed-evidence verification and lets an ordinary user remove sealed staging trees. | rebase; row 72. Previously kept for #335, the sealed-staging fix now needs a fresh base after the verifier landed in #658. |
| engine `docs/cross-column-dependency-plans` (#313) | Plans how to read and mask columns that depend on other columns. | rebase; row 68 (F36). Previously kept for #313, the plan now needs a current base alongside the condition-reader work in #783. |
| engine `feat/detectors-split` (#670) | Moves built-in detectors and name hints into separate detection modules. | rebase; no row. All 15 detector and test paths differ on main after 134 intervening commits. |
| engine `feat/f02-e2` (#685) | Adds content digests to cloud writes and cleans up failed GCS writes. | rebase; row 87. The cloud digest and cleanup PR is 117 commits behind with 20 affected paths differing. |
| engine `feat/f07-e2b` (#686) | Bounds observation of nested paths while profiling JSON columns. | rebase; row 82. All 26 paths in the JSON profiling change differ after 119 main commits. |
| engine `feat/f07-e3b` (#684) | Applies multiple masking rules to one nested column. | rebase; row 82. The nested-rule PRs form a stack and both need a current shared base. |
| engine `feat/f07-e4a` (#691) | Resolves references in nested rules against the correct parent and compile scope. | rebase; row 82. The nested-rule PRs form a stack and both need a current shared base. |
| engine `feat/f13-e1-aws` (#663) | Reads the mask secret from AWS Secrets Manager. | rebase; row 83. The AWS change is a parent of the Vault SDK branch and both are 134 commits behind. |
| engine `feat/f13-e3-kit` (#678) | Freezes Vault secret reads at build time and adds SDK conformance tests. | rebase; row 83. The AWS change is a parent of the Vault SDK branch and both are 134 commits behind. |
| engine `feat/gen-providers-e3` | Adds sex and age fields to generated person records. | rebase; row 24p. The composite-person follow-up is on an earlier base than its open E2 dependency in #778. |
| engine `fix/ci-owner-mypy` (#660) | Runs mypy on pull requests. | rebase; no row. The mypy workflow change in #660 is 135 commits behind the current CI configuration. |
| engine `fix/docs-build-w` | Repairs the strict documentation build and enables it on push. | rebase; no row. The older strict-docs fixes still differ on all seven files and have a live worktree. |
| CLI `docs/prop-reachability` (#308) | Traces which code is reachable for the four proportionality audit rows. | rebase; rows 24zi to 24zl. PR #308 holds a unique report whose call paths predate 139 main commits. |
| CLI `feat/mac-v1a` (#282) | Selects OpenSSL or ssh-keygen to verify a signed installer on stock macOS. | rebase; no row. The signer half shipped in #281 and the open installer half is 174 commits behind. |

### Needs plan

| Branch | What it holds | Disposition |
|---|---|---|
| engine `claude/route-rules-plan` | Plans one set of facts and rules for choosing an execution route. | needs plan; row ROUTE-RULES. The roadmap calls for a new base after per-column routing and route-label work. |
| engine `plan/derived-closure` | Plans to parse and compile each derived expression once per column. | needs plan; no row. Revision 1 proposes the expression change and has no review or build PR in the input. |
| engine `plan/gen-unique-stream` | Plans streaming for columns that require unique generated values. | needs plan; no row. Only the first plan revision is present, with no review or implementation PR on this branch. |
| engine `plan/geo-gen-counts` | Plans one geographic masking decision per distinct ZIP code. | needs plan; no row. Only the first plan revision is present, with no review or implementation PR on this branch. |
| engine `plan/grouped-series-vector` | Plans vectorized execution within the grouped-series handler. | needs plan; no row. Only the first plan revision is present, with no review or implementation PR on this branch. |
| engine `plan/joint-mask-vector` | Plans indexed array selection of reference rows for joint masking. | needs plan; no row. Only the first plan revision is present, with no review or implementation PR on this branch. |
| engine `plan/shuffle-arrow` | Plans to write a shuffle permutation in one vectorized operation. | needs plan; no row. Only the first plan revision is present, with no review or implementation PR on this branch. |

### Owner decision

| Branch | What it holds | Disposition |
|---|---|---|
| engine `claude/clever-albattani-6iq27c` | Documents that the unified execution path is enabled by default. | owner decision, no row: Does main still enable the unified execution path by default, so these docs can merge, or do they retire? |
| engine `claude/optimistic-mayer-sfrak5` | Batches token-vault operations to avoid a round trip for each cell. | owner decision, no row: Retire this earlier batch-write copy now that the vault core shipped in #559, or port its batching? |
| engine `feat/f26-retention-contract` (#337) | Defines versioned retention policies, reports and outcome exit codes. | owner decision, row 74 (F26): Retire #337 in favour of the recovery work in #638, or keep the broad retention contract for a later row? |
| engine `feat/f31-ae1-render` (#793) | Introduces checked error text and a renderer for engine failures. | owner decision, row F31-AUDIT: Retire the closed #793 now that #795 carries SafeText, or does part of it still need a home? |
| engine `feat/postscan-ps11` | Copies loader and transformed baselines to scratch when post-scan cannot reread them. | owner decision, no row: Keep this scratch-baseline copy for post-scan, or retire it because #585 covers only the loader part? |
| engine `fix/gate-select-transitive` | Selects tests through transitive imports. | owner decision, no row: Retire this selector because #834 added the impact map? |
| engine `plan/execution-grouping` | Proposes grouping the execution package by responsibility. | owner decision, no row: Adopt the package grouping proposal as a plan, or drop it? |
| engine `plan/gate-speed-branch-only` | Plans branch-only merge checks against per-test-file results from main. | owner decision, no row: Approve branch-only merge checks as merge policy, or drop the plan? |
| CLI `dependabot/pip/polars-2.0.0` (#153) | Changes the certified Polars pin from 1.43.0 to 2.0.0. | owner decision, no row: Take Polars 2.0.0 into the certified stack, or close #153? |
| CLI `docs/outside-review-buckets` (#319) | Sorts the outside readiness review into existing work and proposed follow-ups. | owner decision, no row: Close #319 after the remaining items are reconciled, or keep it as the record? |
| CLI `docs/remote-worker-rules` (#316) | Adds repository instructions for remote workers. | owner decision, no row: Adopt these remote-worker rules, or close #316? |
| CLI `plan-rs5-e5redesign` | Revises the streaming plan so the E5 pre-pass runs after config and subset checks. | owner decision, row 63a (RUN-STREAM): Keep the E5 pre-pass redesign, or drop it for the current R5 line? |
| platform `audit/scattered-enforcement-2026-11-03` | Maps where transactions, notifications and admission enforce the same rules in different places. | owner decision, no row: Who owns the remaining findings in the two audit documents? |
| platform `audit/test-trust-2026-11-04` | Records which platform test results can be trusted and where coverage is missing. | owner decision, no row: Keep the test-trust writeup as a record, since the plan landed in #179, or retire it? |
| platform `docs/roadmap-v1-ux-map` | Updates roadmap sequencing for the UX map, scan checks and CLI dialect coverage. | owner decision, no row: What is the fourth-round UX review decision this roadmap waits on? |
| platform `docs/v1-ux-map` | Maps V1 user actions to scan, check and pipeline behavior. | owner decision, no row: Run the fourth UX map review round, or accept the map as it stands? |
| platform `feat/prodsim-native-coverage` | Adds native production-simulation workloads, a GCP soak driver and recorded runs. | owner decision, no row: Retire this pre-consolidation snapshot, or mine it for native coverage first? |
