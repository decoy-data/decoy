Status: plan (revision 3.6, 2026-11-20; coordinator ruling on the Codex delta review of rev 3.5)

# QA-BETA: agent beta testing, a shared corpus and a mechanical oracle for the V1 QA pass

Owner: Cam. Author: Opus (plan author, CLI). Date: 2026-11-20. Roadmap row: QA-BETA in `docs/roadmap/groups/release.md` (added by slice S0, owner 2026-11-20).

Sources: owner request 2026-11-20 ("use subagents as beta testers ... a set of input files ... different input file types, different job and file sizes, different settings ... come back with specific issues and we can build QA remediation"; "we'll want a robust QA process to find issues in v1 before the users do ... set it up as needed so we're ready when QA is slotted to begin"). Existing QA: `docs/qa/cli-v1-checklist.md` (row 92a, 16 groups, 204 checks), `docs/qa/cli-v1-journey.md` (row 75), `docs/qa/cli-v1-run-template.md`, engine `E:docs/qa/` (18 sections, about 225 checks), `docs/records/2026-11-14-qa-readiness-map.md`.

Anchors: a path with no prefix is in this repository (decoy CLI); `E:` is decoy-engine. CLI `origin/main` `93ed40fb`; engine `origin/main` `a1058463e`.

Rules consulted: dev-rules `README.md` (routing), `00-universal.md`, `development-loop.md` (PLAN: guarantee, failure modes, acceptance tests first, placement, slices), `risk-and-exceptions.md`, `workspace-and-vcs.md`, `reuse-first.md`, `exploration.md`, `scope-discipline.md`, `proportionality.md`, `verification.md`, `code-review.md`, `testing.md` (test depth, oracles, property tests), `architecture.md`, `cross-cutting-concerns.md`, `api-and-compatibility.md`, `data-and-migrations.md`, `observability-and-resilience.md`, `security.md`, `config-secrets-and-supply-chain.md`, `documentation.md`, `delegation.md`, `pre-release-audit.md`, `autonomous-operation.md` and `catalogs/recurring-defects.md`.

Review history: Dennis r1 reviewed revision 1 at `775efe04`. Codex r1 gave NO-GO on revision 2 at `048021bb`. Codex reviewed rev 3.1 at `70874c98` and gave NO-GO on the tester isolation design; rev 3.4 (Codex plan review of rev 3.1) fixes it. Rev 3.4 also applies the owner decision of 2026-11-20 evening (section 11): QA covers the whole product, testers explore like human testers, and there is no program line ceiling. Codex reviewed rev 3.4 at `42206eb3` and gave NO-GO (8 V1, 2 DESIGN, 5 V2-LOG); rev 3.5 (Codex plan review of rev 3.4) fixes them. Codex delta-reviewed `3a93cb22` and gave NO-GO on four items; past the review-round cap, the coordinator ruled on them and rev 3.6 applies that ruling. Sections 17 to 21 map the fixes.

## 1. Current state

The V1 QA pass is planned as a scripted checklist run, one feature group at a time, after every row in the group closes (owner rule 2026-11-11, standing). Three gaps remain:

1. Nothing tests the product the way a new user meets it: from the public docs, with their own data, without a script. The scripted checks test what we thought to write down.
2. There is no shared input corpus. The journey uses one two-table fixture (`tests/fixtures/qa_first_user/`), the checklist builds its own `qamark` data, and the first-user records used ad hoc files. Formats, encodings, sizes and odd shapes are not covered in one place.
3. There is no mechanical oracle shared by all QA. The checklist and the journey each carry their own leak sweep (`docs/qa/cli-v1-checklist.md:125`, `tests/e2e/first_user/journey/test_cli_journey.py:225`), and an agent tester that says "this looks wrong" is weak evidence; past agent reports have claimed fixes and failures that were not real.

## 2. Guarantee and non-goals

Guarantee. When QA is slotted to begin, a tester can be started on any V1-complete feature group within one hour (timed in the S3 dry run). Every V1 feature group is covered by at least one layer or by a named non-tester gate (section 5.9). Every `bug` finding that reaches the roadmap:

- names the command, the config with values removed, the corpus item, the platform and the versions;
- cites the public doc line that set the expectation, or names the invariant that failed;
- was reproduced from its repro script on a clean node by someone other than the tester;
- holds no cell value, no marker text and no secret. It uses opaque coordinate ids that contain no data-derived text.

Feedback findings (`usability`, `docs` and `performance`, section 5.6) carry the fields their kind requires and hold no value. They do not need a repro script.

Non-goals:

- No product code changes. QA-BETA builds test tooling, data and briefs. Remediation of findings is separate roadmap rows through the normal dev loop.
- No QA of an unfinished group. The owner rule stands; prep work may run the product only to test the harness, and anything it finds is filed against its group and held (section 6, F9).
- No runs above 1M rows. Scale above that is extrapolated (owner decision A-2), and `mask-big` (RUN-07, RUN-08) already covers large single runs.
- Not a replacement for the checklists or the journey. They stay the scripted floor; this adds exploration, data breadth and a shared oracle.

## 3. Established solutions

- **Exploratory testing with charters and personas** (Bach and Bolton's session-based test management; Hendrickson, "Explore It!"). A tester gets a mission, a time box and a debrief, not a script. Persona briefs (section 5.3) are charters.
- **Pairwise (all-pairs) combinatorial testing** (NIST combinatorial testing program; Kuhn et al.). Most configuration faults are triggered by one or two settings together, so covering every pair of setting values finds most of them in a few dozen runs instead of thousands. Tool: `allpairspy` (MIT), with constraints for combinations the docs refuse or ignore.
- **Metamorphic and invariant oracles** (Chen et al., "Metamorphic Testing"). When the exact right output is unknown, check relations that must hold: same input and key give the same output, foreign keys still join, rows are accounted for, no original value survives where the strategy replaces it. Section 5.5.
- **Canary values for leak detection** (the checklist's `qamark` markers and the journey's needles; honeytoken practice). A leak is a substring or same-row comparison, not a judgement.
- **Docs as the oracle for user-facing behaviour** (doc-driven QA; the 2026-11 CLI doc audit). A tester who reads only the public docs finds every place where the docs and the product disagree.
- **Bug triage with a reproduction gate** (Mozilla and Chromium triage practice: no repro, no bug). Section 5.7.

## 4. Reuse inventory

| Need | Reuse | Where |
|---|---|---|
| Scripted checks per group | the CLI checklist and its run template | `docs/qa/cli-v1-checklist.md`, `docs/qa/cli-v1-run-template.md` |
| Engine checks | the engine QA sections | `E:docs/qa/` |
| Marker convention and sweep rules | the checklist's `qamark` sweep (exit 1 pass, exit 0 finding unless passthrough, exit 2 not run) | `docs/qa/cli-v1-checklist.md:125` |
| Secret needles | the journey's needle list | `tests/e2e/first_user/journey/test_cli_journey.py:225` |
| External services | the checklist's services table (MinIO, fake-gcs-server, Postgres, SFTP, Vault and LocalStack containers) | `docs/qa/cli-v1-checklist.md:131` |
| Installing a clean bundle | the fresh-install smoke and release smoke | `docs/release/fresh-install-smoke.md`, `packaging_tools/smoke_install.py`, `tests/e2e/test_release_smoke.py` |
| Large single runs | `mask-big` checks | checklist RUN-07, RUN-08 |
| Exit code meanings | the exit registry and `RUN_EXIT_MAP` | `src/decoy/cli/exit_codes.py` |
| Error and CI JSON shapes | the versioned schemas | `docs/schemas/` |
| Running on nodes | `~/bin/vm-run`, node-watch, the Dell, Mac and GCP test nodes | local operations profile |
| Pairwise generation | `allpairspy` (MIT) in the dev dependency group | `pyproject.toml` |
| Synthetic data | NumPy and the standard library only; not Faker, so the corpus is not built by the library the product uses | `scripts/qa/corpus/` |
| Public data | Synthea (Apache-2.0, already used by `decoy-synthea`) and Chinook (MIT) | corpus manifest, section 5.2 |
| Private atomic files | standard-library `os.open`, `tempfile`, `os.fchmod` and `os.replace` in one QA helper | `scripts/qa/io.py` |

One shared sweep. The checklist and the journey each have a leak sweep today. S1b builds `scripts/qa/sweep.py`. It keeps the checklist's `qamark` prefix and exit meanings. It also uses the journey's needle list and the pass secrets. The checklist and journey then call this module. Nothing in this plan copies a product mechanism. The harness calls only the installed `decoy` binary.

## 5. Behaviour

### 5.1 Four layers

| Layer | Who runs it | Input | Oracle | When |
|---|---|---|---|---|
| L1 Checklist pass | one Sonnet agent per checklist group | the group's checks, the corpus | the check's expected exit and output, plus invariants | as each group becomes V1 complete |
| L2 Doc walk | one Sonnet agent per public docs page set | every example in the public docs, run as written; the `.decoy` language guide is one page set, and each example `.decoy` file in it is written out and run as given | the doc text, plus invariants | as each group becomes V1 complete, for that group's pages |
| L3 Persona beta testers | five Sonnet agents, one per persona | a charter, the public docs, the corpus | the docs and the invariants for `bug` findings; the agent's own judgement for `usability`, `docs` and `performance` feedback | after the V1 build is complete (personas cross groups) |
| L4 Matrix runs | the harness, no agent | the pairwise settings matrices over the corpus | invariants only | after the V1 build is complete; a smoke subset runs in S3 to test the harness |

Gating for `.decoy` (rev 3.4). Coverage of the `.decoy` language in every layer (the L2 guide walk, the `.decoy` personas and the matrix pipeline-source value) runs only once the DECOY-LANG group is V1 complete. This is the standing rule that QA runs only on complete groups. Until then, testers use YAML configs.

L4 is scripted on purpose: coverage is cheap and mechanical. Agents (L1 to L3) are used where judgement, docs reading and exploration pay.

Command coverage. L4 covers `decoy run` only, so every other command has a named layer:

| Command | L1 | L2 | L3 persona |
|---|---|---|---|
| `run` (mask, generate, `--all`) | yes | yes | P1, P2, P3, P5 |
| `fit` (incl. `--fanout`), then generate, then `report fidelity` | yes | yes | P1 |
| `scan`, `scan fields`, `scan show`, `scan diff` | yes | yes | P2, P4 |
| `subset` | yes | yes | P2 |
| `report show`, `render`, `verify`, `fidelity`, `integrity`, `diff`, `vault` | yes | yes | P4 |
| `tokenize`, `detokenize`, `unmask` | yes | yes | P4 |
| `validate config`, `compile`, `preflight` | yes | yes | P3, P5 |
| `ci check` | yes | yes | P3 |
| `init`, `demo`, `explain`, `info`, `doctor`, `setup` | yes | yes | P1, P5 |
| `library path`, `schema`, `list`, `show`, `project` | yes | yes | P1 |
| `library fsck`, `library prune`, `clean` | yes | yes | P4 |
| `upgrade` | yes | yes | P1 |

Sandbox. Every tester runs in a fresh, throwaway sandbox: a rootless Podman container on Linux, a Tart guest on macOS (section 10a). The sandbox holds only the installed release bundle, the public docs, a read-only copy of the tester's corpus items and its own inbox. Repository checkouts, other testers, the host home, the pass needles file and the refusal set do not exist inside it. Its only network path is the Squid egress proxy, which allows `CONNECT api.anthropic.com:443` and nothing else. "The public docs" means the built public docs set, mounted read-only. It includes the `.decoy` language guide (`docs/guides/decoy-language/`) and the `decoy` CLI reference. The tester also has `decoy --help` and any built-in language help command that DECOY-LANG ships. Briefs forbid values in messages. The launcher captures tester stdout and stderr in a node-local file. The coordinator receives only finding ids and counts.

Submission (rev 3.5, descriptor rev 3.6). Everything a tester writes in its sandbox is an untrusted candidate. `scripts/qa/submission.py` is the one descriptor of the id grammar, the submission types (`finding` and `workflow-candidate`), the artifact suffixes allowed for each type and their size limits. The sandbox and the host import this same module. The image holds the submission client `qa-submit` (`scripts/qa/image/qa-submit.py`), plus exact copies of `scripts/qa/submission.py` and `scripts/qa/io.py`. `qa-submit` checks structure only through `submission.py`: the id is one of the issued ids in `QA_FINDING_IDS`, the file names fit the type, and the sizes are in bounds. It writes into `QA_INBOX` only through `io.publish_private_once`. It has no regex, limit or writer of its own (AT-17). It has no needles, no refusal set and no token check, because none of those exist inside. After the sandbox exits and its inbox is exported, the launcher groups the inbox with the same `submission.py` and passes each candidate to the one host-side choke point, `findings.write`, which takes the submission type. That call gets the host-only needles file, the refusal set and the subscription token as an in-memory needle (10a.4). Only a candidate that passes is published. A refused candidate becomes a `candidate-refused` event (5.6) and is kept node-local until the pass record is published.

### 5.2 Corpus

One manifest, `docs/qa/corpus/manifest.toml` (`schema_version = 1`), lists every corpus item: id, origin (public URL or `generated`), license, SHA-256, size tier, format, shape tags and the marker column list. Data never enters git. `scripts/qa/corpus/fetch.py` downloads public items and `scripts/qa/corpus/generate.py` builds generated items, both into `~/decoy-qa-corpus/<id>/` on a node.

Formats: CSV (comma, semicolon, tab, quoted newlines, BOM, Latin-1 and UTF-16 encodings, CRLF), TSV, Parquet (plain and dictionary-encoded), fixed width with a layout file, and a DuckDB database (`--duckdb-source`). Connector sources and targets (Postgres, S3, GCS, SFTP) use the checklist's local containers (`docs/qa/cli-v1-checklist.md:131`) and join the corpus only when their group closes; the checklist marks several as not built (DLV-08 to DLV-11).

Shapes: single table; parent and child; a three-level FK chain; a self-reference; a composite key; a cycle (the docs refuse it in V1); wide (200 columns); free text with names and emails inside; dates in five formats and bad dates; heavy nulls (90%); all-null and constant columns; duplicate keys; a header-only file; an empty file; a malformed file per format.

Size tiers: S 1k rows, M 100k, L 1M. L runs only on the Dell or a GCP test node, never the devbox. Above L is extrapolated from the S to L timings (owner, A-2).

Markers. Every generated text cell holds `qamark` plus a unique number. Public items keep their data. I1 uses a same-row comparison for public items. Each pass writes a node-local needles file. It holds every marker and each secret that the pass uses. A second node-local refusal set holds salted indexes of canonical scalar forms. It covers every scalar in the pass input and output files. Canonical forms use the decoded scalar type and its stable text form. This set includes non-PII, numeric, date, multi-token and output-only values. The sets never leave the node. Every canonical scalar is indexed, whatever its length (rev 3.6). Scalars of three or more characters match as before. One- and two-character scalars match only as a complete canonical lexical token, never as a substring: a token is a maximal run of letters and digits, or one signed decimal number with its sign and decimal point. So `F` matches the token `F` but not `File`, `CA` matches `CA` but not `CAT`, `0` matches `0` but not `10` or `0.5`, and `-1` matches `-1` but not `-12`. A match refuses the text, fail-closed. Briefs tell testers to describe counts and codes in words or in typed fields, because a bare short value in narrative text can be refused. An empty needles file together with an empty or missing refusal set means the pass input was not read: the sweep, the finding writer and publish all treat it as not run (exit 2), through one shared check. Numeric-only matches (a bare integer or decimal) count on error and log surfaces only, not on the run summary on stdout, because a run's own row counts collide with sequential key values (rev 3.3; S2 wires the surfaces).

Licenses. An item enters the manifest only with a license that allows internal testing. Nothing from the corpus is redistributed, committed or quoted in a record.

### 5.3 Personas (L3 charters)

Each charter states the persona, the mission, the time box (2 hours of agent time), the corpus items in scope, the node, and the debrief questions. Charters live in `docs/qa/briefs/`.

Testers explore like human testers (owner 2026-11-20 evening). An L3 charter has no step list: only a persona, a mission, data and time. The missions below name areas to explore, not steps or an order. The tester decides what to try, follows what looks odd, and goes back to what was slow or confusing. Besides bugs, the tester reports how the product felt to use: speed on each size tier it ran, confusing messages or flags, and places where the docs did not get it to its goal. These are `usability`, `docs` and `performance` findings (5.6). L1 and L2 stay scripted, because they walk the checklist and the docs.

| Persona | Mission | Node |
|---|---|---|
| P1 Solo developer | install and upgrade offline from the staged signed release artifacts as the install docs describe, run the demo, mask a mix of local files, change settings between runs, re-run, `fit` a table then generate from it and grade it with `report fidelity`, upgrade | Mac (macOS arm64), then Dell (Linux) |
| P2 Data engineer | DuckDB sources, subsetting a three-level FK chain, chunked and native runs on M and L items, scans of a new source; connector sources and targets once their group closes | Dell |
| P3 CI engineer | set Decoy up the way a company would in CI: pinned install, secrets from the environment, `decoy ci check`, exit codes as gates, evidence and result files kept as artifacts; write a CI workflow candidate and note every step a company would need | Dell (container); the workflow runs on GitHub through the orchestrator (below) |
| P4 Compliance reviewer | evidence records, `decoy report verify`, the vault and `decoy unmask` with and without the vault file and mask secret, post-scan reports, the local record library (`list`, `show`, `library fsck`, `prune`, `clean`), what an auditor can and cannot see | Dell |
| P5 Careless user | wrong flags, wrong file types, missing secret, interrupted runs (Ctrl-C mid-write), full disk, read-only output folder, re-running into an existing output | Dell, Mac |

Pipeline source (rev 3.4, DECOY-LANG). The `.decoy` pipeline language (CLI PR #359) replaced the init wizard as the way users write pipelines (owner 2026-11-19). P1 and P5 write their pipelines as `.decoy` files from the language guide alone. P2 and P3 start from a YAML config. P4 uses whatever the pipeline it audits was written in. Each charter names its pipeline source.

Install and upgrade (P1, rev 3.5). The sandbox has no route to the download page or the release channel. P1 gets a read-only `/qa/dist` folder with the signed release artifacts for two versions (N-1 and N) and their checksums and signatures, staged by the orchestrator from the release channel. P1 installs N-1 from it by the documented install steps, verifies it as the docs say, and then upgrades to N. If the public docs give no offline upgrade path, P1 checks that `decoy upgrade` and `decoy upgrade --check` refuse offline with a clear, documented message, and that refusal is what is tested. The real download-page path and the real `decoy upgrade` against the release channel are a separate release probe with no agent: the orchestrator runs the fresh-install smoke (`docs/release/fresh-install-smoke.md`, `packaging_tools/smoke_install.py`) in a clean container with ordinary egress, no Claude token and no corpus. S2 adds an upgrade step (install N-1, then `decoy upgrade`) to that smoke doc.

CI workflow route (P3, rev 3.5). P3 runs in a Dell container like every other tester. It writes a workflow candidate and submits it with `qa-submit` as a `workflow-candidate` (5.6): an issued id with only `<id>.workflow.yml` and no finding record. It is not a finding. It passes the same host choke point, `findings.write`, with the same needle, refusal-set and token scan, and is stored outside `findings/`, under `~/decoy-qa-runs/<pass>/workflows/`. It is never triaged. Then the orchestrator, not the agent, commits it to a branch of the private sandbox repo (Q2) and runs it on GitHub-hosted runners. The run has no Claude token and no corpus. It uses only `decoy demo` data or data the workflow generates, and a throwaway mask secret stored as a sandbox-repo secret. The orchestrator returns sanitized evidence: the run conclusion, each step's name and exit code, and artifact names and sizes, swept with the pass needles and the token before use. A follow-up P3 session reads that evidence from a read-only mount and may revise the workflow (a new `workflow-candidate`). Only an observation P3 makes about the evidence becomes a finding, as a normal record of its kind. The path is: workflow-only candidate, hosted run, sanitized evidence, then an optional P3 finding (AT-10). At most three rounds per pass. This is the only route by which P3 covers CI.

P3's notes become the draft of a "Running Decoy in CI" guide (owner rule: every built capability is expressed to customers), handed to REL-DOCS row 92 after triage.

### 5.4 Settings matrices (L4)

Two matrices, because generate has no file source. Parameters come from `docs/cli-reference.md` (run options at lines 105 to 129).

Mask matrix:

| Parameter | Values |
|---|---|
| strategy mix | hash only; fpe and date_shift; faker and categorical (with pool_size and categories); bucketize and truncate; text_redact on free text; tokenize with `vault: true`; passthrough mixed in |
| source | csv, tsv, parquet, fixed-width, duckdb |
| size tier | S, M, L |
| `--mask-secret` | absent, `env:` ref |
| chunked | off, `--chunked` |
| native | default, `--native`, `--no-native` |
| threads | default, `--threads 1`, `--threads 4` |
| memory budget | default, `--max-memory` at a quarter of the item size |
| subset | config subset on, `--no-subset`, no subset block |
| post-scan | off, `--post-validate`, `--post-validate-enforce` |
| evidence | off, `--evidence-out` |
| vault | off, `--vault` |
| output | default run folder, `--out-dir` |
| `--json` | off, on |
| pipeline source | `.decoy` file, YAML config (only where the docs give both forms) |

Generate matrix:

| Parameter | Values |
|---|---|
| key | none (seeded), `--master-key` with `--key-label` |
| rows | config size, `--rows 100` preview |
| tables | single, parent and child, three-level chain |
| output format | csv, parquet |
| native | default, `--no-native` (`--native` is refused up front) |
| evidence | off, `--evidence-out` |
| `--json` | off, on |
| pipeline source | `.decoy` file, YAML config (only where the docs give both forms) |

Constraints have three kinds, each citing its doc line in `docs/qa/matrix.toml`:

- **refused**: the run must exit with the documented code and a value-free reason. Examples: `--chunked` with `--vault`, with a subset block (even with `--no-subset`), with fixed-width, with `--post-validate`, or with a strategy that is not value-keyed; `--duckdb-source` with `--evidence-out`; `--native` on a generate config; an unkeyed `date_shift`; `--rows` with any flag on its refusal list.
- **ignored**: the run must succeed and its outputs must equal the run without the ignored flag (I3). Examples: `--max-memory` and `--threads` under `--chunked`.
- **refused after the run**: `--native` on a table with no compiled-kernel evidence (FK tables, passthrough/redact/truncate only) must refuse before any output is written.

`allpairspy` covers every value pair not removed by a constraint, about 60 mask runs and 15 generate runs per platform. The generated run list is written per QA pass, not committed.

### 5.5 Invariants (the oracle)

`scripts/qa/invariants/` checks every run's outputs after the fact. A failed invariant is a finding with no judgement needed.

| Id | Invariant | How it is checked |
|---|---|---|
| I1 | No original value survives where the column's strategy replaces it, and no needle (marker or secret) appears on any output surface (section 15.2.5) except the documented exceptions below | per column, by the config's strategy (rev 3.3, S1b review round 2; the rule is: an exact-cell check only where the output domain cannot overlap the input by construction): `hash`, `tokenize`, `redact`, and `faker` over marker inputs get an exact-cell check and a same-row check (output cell differs from the same row's input cell); `date_shift` gets the same-row check plus `0 < |out - in| <= configured range`; `fpe` and `faker` with a pool get the same-row check plus a swap check: the column fails when, on 20 or more non-null row pairs, 90% or more of the output values also appear in the input multiset (a null output counts as a non-match), because a row shift or a pool drawn from other rows leaks as surely as an exact permutation (rev 3.4, S1b review round 3); single exact-cell hits do not fail it. A `faker` column gets this swap check only when its rule sets a pool; otherwise it keeps the exact-cell check over marker inputs; `categorical` and `bucketize` get no exact-cell or same-row check, because a legitimate mapping can return the input value; instead each output must be in the rule's `allowed` set and the mapping must be deterministic (equal canonical inputs give equal outputs); `passthrough` is exempt; `truncate` must set its prefix length and keeps exactly that prefix; `text_redact` may keep the surrounding text but no detected entity, matched case-insensitively; non-data surfaces get the needles sweep (`scripts/qa/sweep.py`) |
| I2 | Each output FK obeys its configured orphan policy | `fail` refuses the source orphan, `remap` produces a child tuple that joins, and `preserve` keeps the documented orphan relation (`docs/cli-reference.md:897`); the checker compares complete key tuples |
| I3 | Re-runs and route pairs give equal outputs exactly where the docs promise it | SHA-256 per output data file, ignoring run ids and timestamps in result and evidence files; pairs and their promises: re-run with `--mask-secret` (`docs/cli-reference.md:108`), `--chunked` vs plain for value-keyed strategies (`:109`), generate with `--master-key` across runs and machines (`:107`), a flag the docs say is ignored vs without it (`:111`, `:112`) |
| I4 | Every input row is accounted for | mask: input rows = output rows + quarantined rows per table; subset: output rows ≤ input rows and I2 holds; generate: rows per table match the config or the `--rows` ratio |
| I5 | Column names, order and types match the docs for the strategy | schema read per output |
| I6 | The exit code means what the registry says (section 15.2.1) | registry check, the `internal error` form always classified as a crash, stderr classification for other exit 1 cases, `--json` parsed against `docs/schemas/` |
| I7 | Every refusal and error text holds no value | the needles sweep and the same-row check over stdout, stderr and logs |

Peak RSS and wall time are recorded per run (`/usr/bin/time -v` on Linux, `-l` on macOS) as metrics for the job-time estimate and as the timings in `performance` findings. They are notes, not pass or fail, and not an invariant: `--max-memory` is a route budget, not an RSS ceiling (`docs/cli-reference.md:111`).

Leak findings cite the surface and an opaque coordinate id. The id is independent from marker text and data-derived suffixes. Findings never carry the matched text.

### 5.6 Finding record

One file exists per finding at `findings/<pass>/<id>.toml`. The launcher issues tester-scoped ids before it starts a tester. An id can be used once. The record has `schema_version = 1` and the fields in section 15.2.4.

Each finding has one `kind` (rev 3.4, owner 2026-11-20 evening; it replaces the `confusing` flag). Rev 3.5 puts every kind rule in one registry, `KINDS` in `scripts/qa/findings.py`. Each `FindingKind` entry holds its required, optional and forbidden fields, its metric fields with type and range, its repro policy and its triage destination. `findings.write`, `findings.read_record`, `findings.publish`, the triage step and `docs/qa/finding-template.toml` all derive from it, and AT-16 guards that. S2 extends S1b's `FIELDS` descriptor into this registry: `FIELDS` keeps the fields common to every kind.

- `bug`: the product did something the docs or an invariant say it must not, or any observed contradiction between the docs and the product. It stays a `bug` until reproduction decides which side is wrong; then triage routes a wrong doc to REL-DOCS. It needs a repro.
- `usability`: a message, flag, default or step confused the tester or made a task harder than it should be, where the product does what the docs say.
- `docs`: guidance is missing or unclear, and the product does not contradict it. A doc that states something the product does not do is a `bug`, not `docs`.
- `performance`: a timing note with typed metrics. It is a note, never pass or fail.

Fields per kind. Every kind requires the common fields `id`, `kind`, `layer`, `persona`, `group`, `platform`, `cli_version`, `engine_version`, `bundle_digest` and `command`. Unknown fields and unknown kinds are refused.

| Kind | Also required | Optional | Forbidden | Repro | Triage destination |
|---|---|---|---|---|---|
| `bug` | `corpus_item`, `config`, `expected` (doc line or invariant id), `actual`, `exit`, `signature`, artifact `repro.sh` | `coordinate`, `route`, `tier` | metric fields | required: `repro.run` with `exit` and `signature` | a V1 row in the group file, or V2-LOG |
| `usability` | `actual`, `expected` (what the tester expected) | `corpus_item`, `config`, `exit`, `route`, `tier` | `signature`, artifact `repro.sh`, metric fields | none | the owning group as a row or V2-LOG |
| `docs` | `doc` (the page and line, or the page that lacks it), `actual` | `corpus_item`, `config` | `signature`, `exit`, artifact `repro.sh`, metric fields | none | REL-DOCS row 92 or the docs-truth row |
| `performance` | `route`, `tier`, `wall_seconds`, `peak_rss_mib`, `felt_slow` | `corpus_item`, `config`, `actual` | `signature`, `expected`, artifact `repro.sh` | none | the pass record's timing table |

Metric fields are metadata. `wall_seconds` is a float with 0 < value ≤ 86,400. `peak_rss_mib` is an integer with 1 ≤ value ≤ 1,048,576. `felt_slow` is a boolean. `exit` is an integer from 0 to 255. These typed fields skip the refusal-set lookup, in `findings.write` and in the publish sweep, because a timing can equal a corpus number by chance. Every string field (narrative, `command`, `config`, `doc`) still gets the needles and refusal-set check. A number written into a string field is checked like any other text.

Artifact layout, from `submission.py`. Each issued id is used by one submission type. A `finding` is `<id>.toml` (at most 64 KiB) and optionally `<id>.repro.sh` (at most 32 KiB); both names carry the same id. A `workflow-candidate` (P3 only) is `<id>.workflow.yml` (at most 32 KiB) and nothing else: no record, never under `findings/`, never triaged. Anything else in the inbox is refused. `findings.write` scans every file of either type the same way. For a `finding` it publishes the artifacts first and the record last, so the record is the commit marker and an interrupted write is finished by a retry through `io.publish_or_same`. Triage runs a `bug` repro only through `scripts/qa/repro.py` (`repro.run`, from S1b): in a private copy made by `io.copy_private_tree`, through the `decoy` shim, with exit 2 meaning not run.

Events. Harness and process events are not findings and have no kind. They are separate records under `findings/<pass>/events/<event-id>.toml`, written by the launcher through `findings.write_event`, with one registry `EVENTS`: `stall`, `paused`, `failed`, `export-failed`, `recovery-blocked`, `candidate-refused` and `publish-hit`. An event record holds the event name, the tester id, the lifecycle step and a count. It holds no narrative text. The pass record lists event counts. Triage never files an event as a product row.

`findings.write` is the one host-side choke point that turns a candidate into a finding. It refuses text that contains a needle (including the in-memory token) or any canonical scalar from the refusal set. It also refuses a coordinate id that contains marker text. Testers return only counts and finding ids to the coordinator.

All QA writers use `scripts/qa/io.py:publish_private_once`. This helper creates a 0600 temporary file and reserves the target with create-once semantics. It uses `os.replace` for atomic publication. A controlled interruption removes the reservation, and a retry can use the same id. QA tooling does not import private product modules. A syntax-tree guard refuses any other open-for-write operation in `scripts/qa`.

### 5.7 Triage

1. **Collect.** The triager reads finding records through `findings.py`. The coordinator hand-back has counts and finding ids only.
2. **Check our own text.** The sweep and refusal-set check run over the node-local pass folder before publication, skipping only the registry's typed metric fields. A hit stops publication and writes a `publish-hit` event.
3. **Dedupe.** Group findings with the same root cause; keep the clearest record, and its repro when the kind requires one.
4. **Reproduce.** Run each `bug` repro script through `repro.run` on a clean node, not the tester's. No repro: closed as not reproduced, kept in the record. Feedback kinds skip this step, as their registry entry says. A `docs` or `usability` finding that turns out to describe a docs and product contradiction is re-filed by the triager as a `bug` with a triager-written repro.
5. **Classify** by the V1 bar (only a function break, data loss, a non-admin leak, or a copy of a central mechanism blocks V1; everything else V2-LOG). Each kind goes to the triage destination in its registry entry. A reproduced `bug` whose fault is the doc goes to REL-DOCS row 92 or the docs-truth row. `performance` notes feed the job-time estimate and the speed rows; a note blocks V1 only if it shows a function break, such as a run that never ends.
6. **Class check.** If two or more findings share a class, propose a sentry or choke point, not one patch per finding (owner rule: best practice becomes a sentry).
7. **File.** Each V1 finding becomes a roadmap row in its group file. V2-LOG items go to the V2 log.
8. **Publish.** `findings.py publish` writes the pass record and sends the Slack text. The pass record lists each finding and its triage result.

`findings.py publish` is the only QA function that writes under `docs/records` or calls the Slack script. Slack posts carry counts and row ids only. No git hook is added.

Remediation follows the owner rule: after the group's QA pass, through the normal dev loop.

### 5.8 Capacity and nodes

Testers count against the builder cap (6 builders and 2 reviewers). Tester capacity (rev 3.5) has one total and one Mac limit. Total testers across nodes = `min(4, free worker slots, configured subscription concurrency)`. Mac testers = `min(2, that total)`, because Apple's licence allows two macOS guests at once. Linux testers fill the rest of the total. The orchestrator passes free worker slots to the launcher from the capacity tool. Subscription concurrency is one constant in the launcher's capacity module, set to 2; the owner can raise it. The cap of 4 leaves 2 builder slots for remediation. One pass runs on a node at a time: the launcher holds a node-wide `flock` on `~/decoy-qa-runs/node.lock` for the whole pass, and a second pass on that node refuses to start. Token removal and label cleanup run under that lock.

Usage limits. Tester sessions share the owner's subscription limits with the builders. When `claude -p` ends with a recognized usage-limit response (a fixed pattern list in the capacity module, matched on the node-local capture only), the launcher writes a `paused` event. It does not write a finding and triage never sees it as a product finding. Teardown runs as normal and keeps the safe artifacts: the findings already in the inbox are published, and the capture stays node-local. The launcher retries after the reset time in the response, or after 60 minutes when none is given, at most 6 times. The retry starts a fresh sandbox with the remaining time box and the ids of findings already filed. Any other nonzero `claude` exit writes a `failed` event, which is a harness count, not a product finding. The pass record lists the event counts. Tester agents are Sonnet; the triager is Opus. L runs use the Dell first, then the GCP test nodes (local first). macOS runs use the Mac. Windows cells wait for rows 89 and 6, as in the checklist.

### 5.9 Whole-product coverage

Every V1 feature group in `docs/ROADMAP.md` section 4 (the group table; section 5 lists the linked documents) maps to at least one layer, or to a named non-tester gate for an internal group. Engine behaviour is covered where the CLI reaches it: routes, strategies, generation and FK handling run through `decoy`. Engine features with no CLI path are covered by the engine QA sections, not here. Each group's coverage runs only once that group is V1 complete (owner rule 2026-11-11).

| Group | L1 checklist | L2 doc walk | L3 persona | L4 matrix |
|---|---|---|---|---|
| Scan and detection | scan group | scan pages | P2, P4 | post-scan cells in the mask matrix |
| Config, validation and the `.decoy` language | config group | CLI reference (validate, compile, preflight); the `.decoy` guide | P1 and P5 (`.decoy`), P3 (`validate`, `ci check`, through the CI workflow route) | pipeline-source cell |
| Masking, policy, vault and secrets | mask group | masking and vault pages | P1, P2, P4, P5 | strategy mix, `--mask-secret`, vault cells |
| Fit and generate | generate group | fit, generate and fidelity pages | P1 | the generate matrix |
| Run, publication and results | run group | run pages and CLI reference | all five | routes, chunked, native, threads, memory, output and `--json` cells in both matrices |
| Local record library | library group | library pages | P1 (`list`, `show`, `project`), P4 (`fsck`, `prune`, `clean`) | none |
| Sources and targets | connect group | source pages | P2 (DuckDB now; connectors when built) | source cell (CSV, TSV, Parquet, fixed width, DuckDB) |
| Quality and evidence | trust group | report and evidence pages | P4, P1 (`report fidelity`) | evidence cell |
| Install, packaging and release | release group | install, download and upgrade pages | P1 (offline install and upgrade from staged signed artifacts, demo), P3 (pinned CI install, through the CI workflow route), P5; plus the non-agent release probe for the real download page and `decoy upgrade` | none |
| Codebase health and CI | none | none | none | none; named non-tester gate: CI and the sentries |

Gaps today:

- Codebase health and CI has no user-facing surface. Its named non-tester gate is CI and the sentries. This is by design.
- Windows. The release group puts Windows in 1.0, but no Windows node or charter exists. Windows cells wait for rows 89 and 6, as in the checklist. When they close, P1 and P5 rerun on Windows and the checklist's Windows cells run. Until then, Windows has no QA coverage.
- Connector sources and targets (Postgres, S3, GCS, SFTP). Their remaining rows are Later (1.x), and the checklist marks DLV-08 to DLV-11 as not built. P2 and L1 cover them when they are built. The shipped local file sources and DuckDB are covered now.

## 6. Failure modes

| Id | Failure | Handling |
|---|---|---|
| F1 | An agent reports a failure that is not real | no `bug` reaches the roadmap without a repro on a clean node (5.7 step 4); feedback kinds skip reproduction on purpose and never block V1 alone |
| F2 | An agent pastes a cell value into a finding, a hand-back or a record | `findings.py write` refuses it (AT-7); the launcher keeps stdout and stderr node-local; hand-backs contain counts and ids only |
| F3 | A tester reads source or tests and stops behaving like a user | no checkout is mounted or shared into the tester's container or guest (5.1, 10a); the S3 probes (10a) prove it on Linux and macOS |
| F4 | A corpus download is tampered with or changed | SHA-256 checked on a temp file before rename; mismatch refuses (AT-8); downloads are read only as data, with `python -I` |
| F5 | A large run exhausts a node | L only on the Dell or GCP; the harness sets a per-run timeout and records a stall as a `stall` event (5.6), not a finding; the test stall guard and node-watch stay on |
| F6 | The matrix misses a pair because a constraint removed it | every removed pair is listed with its constraint kind and turns into a refusal check, an ignored-flag equality check, or a documented n/a (AT-6) |
| F7 | An invariant check has a bug and passes everything | every checker has a planted-defect test (AT-2 to AT-5 and AT-12); the leak checker and finding writer carry mutations |
| F8 | Findings pile up with no owner | the triager files each V1 finding as a roadmap row in the same pass; the board shows the pass with its open count |
| F9 | Prep work QAs an unfinished group | the S3 dry run uses the demo template and one closed group if any; anything found is filed against its group and held until that group's pass |
| F10 | Agent time or subscription usage runs out | each charter has a time box; capacity is a total of `min(4, free worker slots, configured subscription concurrency)` with Mac testers at `min(2, total)` (5.8); a recognized usage-limit response pauses the tester, keeps its safe artifacts and retries after the reset, and is never a product finding (5.8, AT-10) |
| F14 | A tester or the CLI under test reaches the network directly, or the agent uses a paid API path | Linux testers join only an internal Podman network; macOS guests run pf default deny as a non-admin user; the one Squid config allows only `CONNECT api.anthropic.com:443`; the entrypoint clears every API-key, base-URL and alternate-provider variable (10a, AT-10, AT-14, M5) |
| F15 | Findings are lost, or a sandbox is left behind, when a run is interrupted | the inbox sits outside the throwaway layer; teardown always publishes, then deletes; the next launch recovers stale inboxes, named or labelled containers and clones; a clone is never deleted before a complete, validated export, and is kept as `recovery-blocked` after repeated failure (10a, AT-10) |
| F16 | A tester cannot submit, or submits a value the sandbox cannot check | candidates are untrusted; `qa-submit` checks structure only; the host-side `findings.write` checks needles, the refusal set and the in-memory token before publication (5.1, 5.6, AT-7, AT-10) |
| F17 | Egress constants drift between the Squid config, pf, the launcher, the entrypoint and the node notes | one topology descriptor; a cross-file guard (AT-15); mutations M6 and M7 |
| F11 | Public data license does not allow the use | an item without a recorded license on the allowed list is refused by `fetch.py` (AT-8) |
| F12 | A leak check flags documented behaviour (passthrough, truncate prefix, text_redact context) | I1 rules are per strategy (5.5); AT-2 has a pass case for each exception |
| F13 | An exit is misread (crash as refusal, Ctrl-C as unknown) | I6 classification table (15.2.1), pinned by AT-5 |

## 7. Acceptance tests (red first)

Unit tests live in `tests/unit/qa/` and run in the normal suite. The Squid allow and deny tests in `tests/e2e/qa/` need Podman and run on the Dell (they skip elsewhere). The real sandbox probes (section 10a, P-1 to P-10) run in S3 on the Dell and the Mac. `allpairspy` joins the dev dependency group in S1a.

| Id | Test | Red on main because |
|---|---|---|
| AT-1 | `generate.py` with the same seed writes byte-identical files; every text cell of every generated table holds a `qamark` marker; every FK column joins | `scripts/qa/corpus/generate.py` does not exist |
| AT-2 | The I1 sweep test is parameterized from the surface registry. Each registered surface gets a planted marker, secret and indexed scalar. The documented exception cases come from the same registry. A consistency test proves that dispatch, test parameters and exceptions use the same entries | no checker or registry |
| AT-3 | The I2 checker covers `fail`, `remap` and `preserve`. It covers single, chain, self-reference and composite keys. The composite defect uses parents `(A,1)` and `(B,2)` with child `(A,2)` | no checker |
| AT-4 | The I3 checker flags one changed data byte between two runs, ignores a changed run id or timestamp in a result file, and passes identical runs | no checker |
| AT-5 | I6 classifies the default and verbose `error: internal error (<ClassName>)` forms as crashes. Other documented exit 1 forms are refusals. Exit 3 passes only in named injected read-only, disk and quota cells after atomicity checks. Exit 5 passes only for memory capacity. The test also covers exits 2, 6, 130, unknown exits and invalid `--json` | no classifier |
| AT-6 | The pairwise generator covers every value pair not removed by a constraint (property test over random parameter sets), and lists every removed pair with its kind and doc line | no generator |
| AT-7 | `findings.write` refuses needles and canonical scalars from any string field or attached artifact. Cases include non-PII, numeric, multi-token and output-only values, and the subscription token passed as an in-memory needle (refused in a record field and in a `repro.sh` artifact). The same number is accepted in `wall_seconds` and refused inside `actual` text; the publish sweep accepts it in the metric field. Metric fields out of range or of the wrong type are refused. An unknown kind is refused, and so is each kind's forbidden field and each missing required field, parameterized from `KINDS`. Artifact cases: a normal record with `repro.sh`; an interruption between the artifact and the record, finished by one retry; a recovery rerun with equal bytes; a symlinked artifact; an oversize artifact; and a `repro.sh` whose id differs from the record's. Short scalars (rev 3.6): with `F`, `CA`, `0` and `-1` in the refusal set, each is refused as a token in every string field, in `repro.sh` and in `workflow.yml`; `File`, `CAT`, `10`, `0.5` and `-12` are accepted. It refuses marker text in an opaque coordinate id. Reader cases cover strict primitive types, missing and next-major versions, and allowed minor fields. Each safe error has empty `__cause__` and `__context__` | no writer |
| AT-8 | `fetch.py` refuses an item whose SHA-256 differs, an item with no license, and an item whose license is not on the allowed list; a good item lands only after its hash checks | no fetcher |
| AT-9 | A repro command writes a launcher nonce witness in a fresh `DECOY_HOME`. The recorded failure signature must recur. A replayed exit without the witness fails | no repro tooling |
| AT-10 | Each brief has the required fields, and no L3 charter has a numbered or ordered step list. Unit tests, with a fake command runner, cover: every row of the argv table (10a) for Podman, Tart, Squid and the token copy, including read-only mounts, the internal network only, no published ports, the security flags, the validated `--name qa-<pass>-<tester>` (an invalid pass or tester id is refused) and no secret in any argv; `qa-submit` (an id not in `QA_FINDING_IDS`, a wrong layout name and an oversize file are refused; a second write of the same name is refused; it never reads needles); the host candidate step (every candidate goes through `findings.write` with the token needle; a refused one makes a `candidate-refused` event and is not published); the Tart host preflight (a locked keychain, where the probe item read exits nonzero or times out, refuses before `tart clone`; so do a NAT address or subnet that differs from the topology; a guest gateway mismatch refuses before pf); the P3 path (a workflow-only candidate is accepted with no record, stored under `workflows/`, never under `findings/`; one holding a needle or the token is refused; a `workflow-candidate` id that also carries a `.toml` is refused; the sanitized evidence mount; a follow-up finding is a normal record); the token-file checks (mode 0600, directory 0700, owner, regular file, symlink refused at the file and the directory, a mode change between check and open refused); the Linux and Tart lifecycles, where a failure injected at each step still runs that step's cleanup and the inbox is published before it is deleted; Linux timeout, launcher signal and launcher kill each leave no container, found by name and, when the name lookup fails, by the pass and tester labels; recovery of a stale inbox and a stale clone; an injected recovery boot failure, and an injected incomplete export, keep the clone and, after the third try, write `recovery-blocked`; the node-wide pass lock refuses a second pass; capacity and usage-limit pause; tester-scoped id allocation, local output capture and counts-and-ids hand-back. The node probes P-1 to P-10 (10a) cover proxy bypass, direct sockets, the token path, refusal-set and needles-file absence, inbox persistence and cleanup on real nodes in S3 | no briefs or launcher |
| AT-11 | The checklist's sweep step and the journey test call `scripts/qa/sweep.py`; no second sweep implementation remains | the sweeps are separate today |
| AT-12 | Planted defects cover I4 row loss and wrong quarantine counts, I5 column names, order and types, and I7 non-marker input and output scalars | no complete oracle |
| AT-14 | `scripts/qa/proxy/squid.conf` shape test: the source ACL lists only the two QA subnets, the one `allow` line names CONNECT, `api.anthropic.com` and port 443, no `ssl_bump` or second port exists, and the last `http_access` line is `deny all`. Dell allow and deny tests run the stock Squid image with this file: CONNECT to `api.anthropic.com:443` is allowed; CONNECT to another domain, to port 80, to an IP literal, a plain GET, and a client outside the source ACL are each refused | no proxy config |
| AT-15 | Topology guard: `scripts/qa/proxy/topology.toml` is the one source of the proxy port, both subnets, the Mac proxy address and the model endpoint. The guard parses `squid.conf` (`http_port`, the `src` ACL, `dstdomain`, the port ACL), `pf.qa.conf` (the allowed address and port), the argv rows from `argv.py`, `qa-entry.sh` (which must hold no address or port literal) and the setup commands in `nodes.md`, and proves each equals the descriptor | no descriptor |
| AT-16 | Kind registry guard: `docs/qa/finding-template.toml` lists exactly the kinds and per-kind fields in `KINDS`; the triage destinations cover every kind; no module in `scripts/qa` other than `findings.py` holds a kind name or field list as a literal; the AT-7 kind cases are generated from `KINDS` | no registry |
| AT-17 | Submission descriptor guard: `qa-submit.py` and `findings.py` import the id grammar, types, suffixes and limits from `submission.py`, and `qa-submit.py` holds no regex, size literal or open-for-write of its own; `submission.py` and `io.py` import only the standard library and each other; the Containerfile and the Tart base setup in `nodes.md` copy exactly `scripts/qa/io.py` and `scripts/qa/submission.py`, and the launcher refuses a pass when the SHA-256 of either copy in the image or base VM differs from the repository file. Boundary cases use literal sizes, not the descriptor's constants: a `repro.sh` of exactly 32 KiB is accepted and one byte more is refused, on the sandbox path and on the host path | no descriptor |
| AT-13 | Concurrent same-id writes allow one complete record and refuse the other. An interrupted write leaves no partial target, removes its reservation and permits one retry. Syntax-tree sentries detect direct writes outside `io.py`, direct `docs/records` writes outside `findings.py publish`, private product imports and direct Slack calls | no writer or sentries |

## 8. Mutations (gate set)

Core only (owner 2026-11-10): the leak checker, the finding writer, the fetcher, the repro guarantee and, from rev 3.4, the egress proxy config and its topology.

| Id | Mutation | Must turn red |
|---|---|---|
| M1 | I1 checker skips stderr | AT-2 |
| M2 | `findings.py write` skips the canonical-scalar lookup | AT-7 |
| M3 | `fetch.py` renames before checking the hash | AT-8 |
| M4 | `repro.py` returns `recorded_exit` without running the command | AT-9 |
| M6 | `squid.conf` `http_port` changed to 3129 | AT-15 |
| M7 | the `qa_nodes` subnet in `squid.conf` (or the address in `pf.qa.conf`) changed | AT-15 |
| M8 | the `repro.sh` size limit in `submission.py` raised to 64 KiB | AT-17 boundary cases |
| M5 | `squid.conf` loses its final `http_access deny all` | AT-14 shape test. Squid's implicit default would still deny at run time, because the line before is an `allow`; the shape test is what keeps the explicit rule, so a later reorder cannot open the proxy |

## 9. Placement (against `CODEMAP.md`)

| Path | Contents | CODEMAP row |
|---|---|---|
| `docs/qa/beta-program.md` | the method (sections 5.1 to 5.8 as a current doc) | "QA checklists and run templates", `docs/qa/` (extend the row) |
| `docs/qa/briefs/*.md` | five persona charters, the checklist-pass brief, the doc-walk brief, the triager brief | same row |
| `docs/qa/corpus/manifest.toml` | corpus manifest | same row |
| `docs/qa/matrix.toml` | the two matrices, constraints with kinds and doc lines | same row |
| `docs/qa/finding-template.toml` | the finding record fields | same row |
| `docs/qa/surfaces.toml` | the surface registry and documented exceptions | same row |
| `scripts/qa/sweep.py` | the one needles sweep, used by the checklist, the journey and QA-BETA | new row "QA tooling (not shipped)", `scripts/qa/`, beside "Release scripts" |
| `scripts/qa/corpus/{fetch,generate}.py` | corpus tools | same new row |
| `scripts/qa/invariants/*.py` | I1 to I7 checkers, one module per invariant | same new row |
| `scripts/qa/{io,matrix,findings,launch,repro}.py` | private writer, pairwise runs, finding commands, launcher command line and repro runner | same new row |
| `scripts/qa/sandbox/{argv,podman,tart,token,capacity}.py` | the one argv table, the Linux and Tart lifecycles, the token-file checks, capacity and usage-limit handling | same new row, named subpackage |
| `scripts/qa/proxy/squid.conf` | the one egress proxy config, used by the Dell and the Mac | same new row |
| `scripts/qa/proxy/pf.qa.conf` | the macOS guest pf rules (default deny, proxy only) | same new row |
| `scripts/qa/image/{Containerfile,qa-entry.sh}` | the pinned tester image and the fixed entrypoint (also copied into the Tart base image with `qa-submit.py`, `submission.py` and `io.py`) | same new row |
| `scripts/qa/nodes.md` | one-time node setup: Podman and its networks on the Dell, Tart and the base image on the Mac, Squid on both | same new row |
| `CODEMAP.md` | the "QA tooling (not shipped)" row: replace the OS-user launcher and `setup-testers.sh` text with the launcher, `sandbox/`, `proxy/`, `image/` and `nodes.md` | changed by S2 |
| `scripts/qa/proxy/topology.toml` | the one topology descriptor: proxy port, subnets, Mac proxy address, model endpoint | same new row |
| `scripts/qa/submission.py` | the one submission descriptor: id grammar, submission types, artifact suffixes, size limits; imported by the sandbox client and the host | same new row |
| `scripts/qa/io.py` (copied into the image) | the one private writer; the image and the Tart base VM hold an exact copy, checked by SHA-256 | same new row |
| `scripts/qa/image/qa-submit.py` | the in-sandbox submission client; structure checks through `submission.py`, writes through `io.publish_private_once` | same new row |
| `tests/unit/qa/` | AT-1 to AT-16 unit parts | new row with the tooling |
| `tests/e2e/qa/test_proxy_rules.py` | AT-14 allow and deny tests (need Podman; run on the Dell) | same new row |

Nothing goes under `src/`. `scripts/qa/` is not in the wheel. It does not import private product modules. No module exceeds 400 lines. The package has fewer than 10 direct Python modules. The `corpus`, `invariants` and `sandbox` concerns use named subpackages.

Original estimate: 30 to 36 new or changed files and about 3,600 hand-written lines. New public tooling names are `findings.py write`, `findings.py publish`, `publish_private_once` and the invariant ids I1 to I7. Size estimates are for review planning, not caps (owner 2026-11-20 evening: "I don't care how long it is"). There is no program line ceiling. Each slice keeps its own estimate in section 13. A slice that runs well past its estimate (more than 20 percent) gets a scope check by the orchestrator, who confirms the extra lines are in scope and not a copied mechanism. It is not an owner stop. Re-baseline 2026-11-20: S1a came in near 3,500 lines; S1b is estimated at 1,700; S2 at 4,150 (rev 3.6).

## 10. Design notes

- **Why agents and a script both.** Agents find what nobody wrote down; the matrices find what agents skip. The oracle keeps both honest.
- **Why our own generator, not Faker.** The product masks with Faker; data generated by the same library could hide a defect that depends on Faker's own patterns.
- **Why per-strategy leak rules.** A blanket "no marker anywhere" fails on documented behaviour (passthrough, truncate, text_redact) and misses same-domain leaks (fpe); the strategy in the config says what may survive.
- **Why docs-only testers.** A tester who reads the code tests the code's intent, not the user's experience. Doc mismatches are real V1 findings (REL-DOCS).
- **Why triage reproduces.** Agent reports have been wrong before (a docs agent claimed fixes not in files; a builder reported a passing ratchet that failed). One clean repro is the gate.

### 10a. Tester isolation (rev 3, after S2 review round 3; rev 3.4, Codex plan review of rev 3.1)

Three Codex rounds on S2 failed on one class: a hand-built sandbox made of OS users, groups and file modes, changed by root, where every rerun and every path is a new attack surface. A codex-fix pass closed the gaps, but only by adding more of the same machinery (per-pass generations, private groups, mount tables, disk images). Rev 3 removes the class. Isolation comes from established tools that start from a clean image each time. Rev 3.4 makes egress enforced on both nodes, keeps the inbox outside the throwaway layer, defines the token path and gives every lifecycle step its cleanup.

Threat model. V1 covers accidental leaks only (owner standing rule). Hostile code inside the sandbox that tries to break out is V2. The controls below stop a careless agent or a CLI defect from reading what it should not, reaching a network it should not, or using a paid API.

What remains ours: the launcher (`scripts/qa/launch.py` and `scripts/qa/sandbox/`), the one argv table (10a.5), the Squid and pf configs, the tester image file and entrypoint, and the node setup notes in `scripts/qa/nodes.md`. The launcher captures tester stdout and stderr through `io.open_private_capture`. No setup script runs as root on a schedule. No tester OS users exist on any node. `scripts/qa/setup-testers.sh`, its test and `provision.py` are deleted.

#### 10a.1 Egress: one Squid config

Topology descriptor (rev 3.5). `scripts/qa/proxy/topology.toml` is the one source of the egress constants: `proxy_port = 3128`, `linux_subnet = "10.89.7.0/24"`, `mac_subnet = "192.168.64.0/24"`, `mac_proxy_address = "192.168.64.1"`, `model_host = "api.anthropic.com"` and `model_port = 443`. `argv.py` builds every address and port from it, and the launcher passes `HTTPS_PROXY` to the entrypoint from it. `squid.conf`, `pf.qa.conf` and `nodes.md` stay readable stock files, and the AT-15 guard proves they equal the descriptor. M6 and M7 change the port and a subnet.

Both nodes use the stock Squid forward proxy with one checked-in config, `scripts/qa/proxy/squid.conf`. It holds no node paths (no disk cache, `pid_filename none`, logs to stdio), so the Dell and the Mac load the same bytes. Before each pass the launcher compares the SHA-256 of the config the node's Squid loaded with the repository file and refuses to start on a mismatch. Squid does not decrypt TLS: no `ssl_bump`. The rules, in order:

```
http_port 3128
acl qa_nodes src 10.89.7.0/24 192.168.64.0/24
acl model_api dstdomain -n api.anthropic.com
acl ip_literal dstdom_regex -n ^[0-9.]+$ ^\[?[0-9A-Fa-f]*:[0-9A-Fa-f:]*\]?$
acl tls_port port 443
acl connect_method method CONNECT
http_access deny !qa_nodes
http_access deny ip_literal
http_access deny !connect_method
http_access deny !tls_port
http_access allow connect_method model_api tls_port
http_access deny all
```

`10.89.7.0/24` is the Dell's internal Podman network. `192.168.64.0/24` is Tart's default NAT network on the Mac. A client from any other address is refused, so a LAN host cannot use either proxy. Testers set `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` and `DISABLE_AUTOUPDATER=1`, so the agent needs only the model API. If S3 shows that the subscription path needs a second host, S3 stops: adding a host is a plan change, not a config edit. AT-14 tests the config and M5 removes its final deny.

#### 10a.2 Linux (Dell)

The Dell is WSL2 Ubuntu 22.04 with rootless Podman 3.4.4 (installed and checked 2026-11-20). It has no systemd user session, so `~/.config/containers/containers.conf` sets `cgroup_manager = "cgroupfs"`. Podman 3.4 uses CNI networking. The plan assumes neither netavark nor pasta.

Topology. Setup creates two networks once (`nodes.md`): `qa-internal` with `podman network create --internal --subnet 10.89.7.0/24`, which has no route out, and `qa-egress`, an ordinary bridge. The Squid container `qa-proxy` is dual-homed: it joins `qa-internal` and `qa-egress`. A tester container joins `qa-internal` only. Its one way out is the proxy, whose `qa-internal` address the launcher reads with `podman inspect` and passes as `HTTPS_PROXY`. No container publishes a port. If rootless Podman 3.4 refuses the dual-homed proxy, S3 stops. There is no fallback to host networking or `slirp4netns`.

One tester run. The image is `scripts/qa/image/Containerfile`: `ubuntu:22.04` by digest, the pinned Claude Code version, and `scripts/qa/image/qa-entry.sh` as `/usr/local/bin/qa-entry`. The launcher runs it by digest with `podman run --rm` and:

- `--network qa-internal`, `--userns=keep-id` and `--user <host uid>:<host gid>`, so the tester is the node user mapped into its own user namespace and can read the token file and write its inbox;
- `--read-only` root file system, `--cap-drop=ALL`, `--security-opt no-new-privileges`, `--memory` and `--pids-limit`;
- read-only bind mounts for the bundle, the docs copy and the tester's corpus items;
- `--tmpfs /work:size=2g` as HOME and cwd, and `--tmpfs /fault:size=64m` for P5 only;
- the inbox as a private bind mount: host folder `~/decoy-qa-runs/<pass>/<tester>/inbox` (made 0700 by `io.make_private_dir`) on `/work/inbox`, read-write. It is the only writable host path;
- the token file only, read-only, on `/run/qa/claude-token` (10a.4);
- `--name qa-<pass>-<tester>`, built from ids that match `findings.PASS_ID` and the tester id pattern, so cleanup can find the container by name;
- labels `qa.pass=<pass>` and `qa.tester=<tester>`, the recovery fallback when the name lookup fails;
- `QA_INBOX=/work/inbox` and `QA_FINDING_IDS` (the issued ids, comma-separated, each checked against `findings.ID`), passed to the entrypoint.

The rest of `/work` stays on tmpfs and disappears with the container. The pass folder `~/decoy-qa-runs/<pass>/` also holds the node-local captures, the needles file and the refusal set. Only the inbox subfolder is mounted.

Order, with cleanup:

1. Create. Take the tester lock (`flock` on `~/decoy-qa-runs/<pass>/<tester>/lock`), make the inbox folder, and allocate the tester-scoped ids. Failure: remove the empty inbox folder, release the lock, stop.
2. Run. `podman run --rm` as above, with a timeout of the time box plus 10 minutes. On timeout or a signal to the launcher: `podman stop --time 30 qa-<pass>-<tester>`, then `podman rm -f` by name; if the name is not found, the same two commands run on the ids from `podman ps -a` filtered by both labels. Then go to step 3. The inbox is on the host, so stopping the container loses no finding.
3. Publish. List the inbox and fail closed on a listing error. Accept only regular files, no symlinks, in the artifact layout (5.6) for ids issued to this tester, within the size limits. Group each id's files. Parse the record with the strict reader, then call `findings.write` with the host needles, the refusal set, the in-memory token needle and the artifacts. An id already published with equal bytes completes through `io.publish_or_same` (a recovery rerun). A refused candidate, or a published id with different bytes, writes a `candidate-refused` event and moves to the node-local `refused/` folder, which is deleted when the pass record is published.
4. Delete. Remove the inbox folder only after step 3 published or recorded every file. Then confirm by name and by `podman ps -a --filter label=qa.pass=<pass> --filter label=qa.tester=<tester>` that nothing is left, and release the lock.

Interruption. A signal to the launcher runs steps 2 to 4 through one `finally` path. After a kill or power loss, the next launch on the node runs recovery first: for each `~/decoy-qa-runs/<pass>/<tester>/` whose lock it can take, it removes the container by name, then by the pass and tester labels, then runs steps 3 and 4. Create-once ids make a second publish safe.

#### 10a.3 macOS (Mac mini)

The Mac mini runs macOS 15 arm64 with Tart 2.42.0 (installed from the checksummed release, owner Q5). Apple's licence allows two macOS guests at once, so the Mac runs at most two testers (5.8).

Base image. `nodes.md` makes the local base VM `qa-macos15-base` once from the Cirrus Labs macOS 15 base image pinned by digest. The setup adds a standard (non-admin) user `qa` with no sudo rights, the pinned Claude Code version, `qa-entry.sh` as `/usr/local/bin/qa-entry` (root-owned, 0755), and `scripts/qa/proxy/pf.qa.conf` as `/etc/pf.qa.conf` (root-owned, 0644). The image keeps the stock admin user with passwordless sudo, which only the launcher uses through `tart exec`. The setup checks that no Claude settings file exists for `qa` or as a managed settings file. Squid runs on the Mac host from the pinned Homebrew package with the same `squid.conf`.

Guest egress. `pf.qa.conf` blocks everything, then allows only: outbound TCP to the Squid address `192.168.64.1` port 3128, DHCP on the NAT link, and loopback. `pfctl` needs root, and `qa` has no sudo, so `qa` cannot change or disable pf. The guest agent that `tart exec` uses talks over virtio-vsock, not IP, so pf does not cut it (S3 checks this). Proxy variables in the entrypoint are now only a convenience: with them unset, every direct connection still fails (P-4, P-5).

Host preflight (rev 3.5). Before each pass, and before any `tart clone`, the launcher proves two things and refuses the pass on a failure:

- The login keychain is unlocked and usable. Tart's FAQ says a headless macOS 15 host needs it, or guests can fail to start. The Mac logs the node user in at boot, and `nodes.md` provisions one QA probe item in the login keychain (`security add-generic-password -a decoy-qa -s decoy-qa-keychain-probe` with a random non-secret value, readable by `/usr/bin/security`). The preflight runs `security find-generic-password -a decoy-qa -s decoy-qa-keychain-probe -w` non-interactively, with stdin closed, stdout and stderr discarded and a 10-second timeout. Reading a protected item fails on a locked keychain. A nonzero exit or a timeout refuses the pass before `tart clone`.
- The NAT network matches the topology. The launcher reads `Shared_Net_Address` and `Shared_Net_Mask` from `/Library/Preferences/SystemConfiguration/com.apple.vmnet.plist` with `defaults read` (an absent key means the vmnet default, 192.168.64.1/24). The address must equal `mac_proxy_address` and the subnet `mac_subnet` in the topology descriptor. Tart runs with its default NAT only: T2 has no `--net-bridged` or `--net-softnet`. After boot, step 4 also checks inside the guest that `route -n get default` names the same gateway before pf loads.

Order, with cleanup. The clone is `qa-<pass>-<tester>`. One `finally` path runs the cleanup named at each step. A clone is never deleted after step 5 starts until a complete, validated export has succeeded (step 8):

1. Clone. `tart clone qa-macos15-base <clone>`. Failure: `tart delete <clone>` if it exists, release the lock, stop.
2. Boot. `tart run --no-graphics --dir=qa-ro:<pass read-only folder>:ro <clone>` as a child process that the launcher owns (not a shell `&`). The read-only folder holds the bundle, the docs copy and the tester's corpus items. Failure: kill the child, `tart delete <clone>`.
3. Wait. Poll `tart exec <clone> true` for up to 180 seconds. Failure: `tart stop <clone>`, kill the child, `tart delete <clone>`.
4. Install pf. The guest's default gateway must equal `mac_proxy_address`. `tart exec <clone> sudo -n shasum -a 256 /etc/pf.qa.conf` must equal the repository file. Then `tart exec <clone> sudo -n pfctl -E -f /etc/pf.qa.conf`, and `pfctl -s info` must show it enabled. Then, as `qa` with the proxy variables unset, a direct `curl` to `https://api.anthropic.com` must fail. Failure at any check: steps 7 and 9, and a `failed` event. The charter has not run yet, so no inbox exists and deleting the clone loses nothing.
5. Run. `tart exec -i <clone> sudo -n -u qa -H /usr/local/bin/qa-entry <charter> <issued ids>`, with the token on stdin (10a.4); the entrypoint sets `QA_INBOX=/Users/qa/inbox` and `QA_FINDING_IDS` from its arguments after checking each id against the id pattern. The timeout is the time box plus 10 minutes. On timeout or a signal: go to step 6. The guest is still running.
6. Export the inbox. The named channel is the `inbox` export stream: `tart exec <clone> sudo -n tar -C /Users/qa -cf - inbox`. The launcher writes it through `io.open_private_capture` to `~/decoy-qa-runs/<pass>/<tester>/inbox.tar`. Every shared folder stays read-only. The export is complete only when `tart exec` exits 0 and the tar stream ends with a valid end-of-archive. Failure or an incomplete stream: an `export-failed` event; go to step 7 and keep the clone for recovery. Steps 8 and 9 do not run.
7. Shut down. `tart stop --timeout 60 <clone>`, then kill the child if it is still alive.
8. Validate and publish. Read the tar as untrusted data with `tarfile`. Accept only regular files under `inbox/` in the artifact layout (5.6) for ids issued to this tester, within the size limits. Refuse links, absolute paths and `..`; a refused member writes a `candidate-refused` event. Then publish each id as in Linux step 3. The export counts as validated when every member is published or recorded. Delete `inbox.tar` after that.
9. Delete. Only after step 8 validated the export: `tart delete <clone>`, confirm with `tart list` that it is gone, release the lock.

Interruption. After a kill or power loss, recovery at the next launch finds `qa-*` clones in `tart list` whose lock it can take. It boots each one (steps 2 and 3), exports, validates and publishes (steps 6 to 8), and deletes it only after step 8 succeeds (step 9). A boot or export failure stops that clone and keeps it. Recovery tries each kept clone again at the next launch, up to three tries in all. After the third failed try the launcher writes a `recovery-blocked` event and keeps the clone. It is excluded from automatic recovery and waits for the manual recovery steps in `nodes.md`, which mount the clone's disk read-only and export the inbox by hand into the same step 8. A stopped clone does not count against the two-guest limit. The charter does not rerun while its clone holds unexported findings.

P5's bounded disk is a 64 MiB disk image created inside the guest. A careless fill only hurts the guest.

#### 10a.4 Credential path

Testers run on the owner's Claude subscription, not a paid API key (owner 2026-11-20, Q4). The token comes from `claude setup-token` (an owner step) and is valid for one year. The plan never contains it.

- Devbox master copy: `~/.config/decoy-qa/claude-token`, a regular file, mode 0600, in a directory with mode 0700, both owned by the orchestrator's user.
- Checks, in `scripts/qa/sandbox/token.py`, run on every copy before every use: `lstat` the directory and the file; refuse a symlink at either; require a directory with mode exactly 0700 and a regular file with mode exactly 0600, both owned by the effective user; then open with `O_NOFOLLOW` and `fstat` the open file, and refuse if the result differs from the `lstat` result. Every refusal is a fixed, value-free message.
- To a node: at pass start the orchestrator sends the token over `ssh <node>` on stdin to a fixed remote command: `umask 077`, make the 0700 directory, write a temporary file, then rename it to `~/.config/decoy-qa/claude-token`. The token is never in argv. On the Dell the path must be on the WSL ext4 file system, never under `/mnt/c`, where modes are not real. The node launcher then runs the same checks.
- Into the Linux sandbox: the one file, mounted read-only at `/run/qa/claude-token`.
- Into the Mac guest: never on the guest disk. Tart shares folders, not files, so the launcher opens the checked node file and writes it to the stdin of the step 5 `tart exec`. The entrypoint reads one line and closes stdin.
- Entrypoint: `qa-entry` is the only command the sandbox runs. It refuses (exit 78) a `QA_INBOX` other than the fixed path for its platform and any issued id that does not match the id pattern. It starts from `env -i` and sets only `PATH`, `HOME`, `LANG`, `HTTPS_PROXY`, an empty `NO_PROXY`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `DISABLE_AUTOUPDATER=1`, `CLAUDE_CODE_OAUTH_TOKEN` from the file or stdin, and the structural values `QA_INBOX` and `QA_FINDING_IDS`. It explicitly unsets `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_BEDROCK_BASE_URL`, `ANTHROPIC_VERTEX_BASE_URL`, `ANTHROPIC_VERTEX_PROJECT_ID`, every `ANTHROPIC_FOUNDRY_*` name, `CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX`, `CLAUDE_CODE_USE_FOUNDRY`, every `CLAUDE_CODE_SKIP_*_AUTH` name, every `AWS_*` name, `GOOGLE_APPLICATION_CREDENTIALS` and `CLOUD_ML_REGION`. It exits 78 before starting `claude` when the token is missing or empty, when `HTTPS_PROXY` is missing, or when a user or managed Claude settings file exists (a settings file could set `apiKeyHelper` or another provider). Then it runs `claude -p` with the charter, stdin from `/dev/null`. `--permission-mode bypassPermissions` is allowed only because the sandbox is throwaway, has no checkout and reaches only the model API.
- The token is a pass secret, checked in memory only. The launcher and the triager read it through `token.py` and pass it as one extra needle to `findings.write`, `findings.publish` and the sweep, so it is refused on every surface. It is never written to the needles file or the refusal set.
- Removal: at pass end, and in recovery, the orchestrator runs `ssh <node> rm -f ~/.config/decoy-qa/claude-token`. The Linux mount ends with the container and the Mac guest never holds a file copy. The devbox master copy stays. If a node is lost, the owner revokes the token on claude.ai and runs `claude setup-token` again.

Inside the sandbox the token is readable by the agent and by the CLI under test. Under the V1 threat model that is accepted: the proxy lets it reach only the model API.

#### 10a.5 The argv table

`scripts/qa/sandbox/argv.py` holds the one table. No other module builds a `podman`, `tart`, `ssh` or `squid` command. AT-10 has a unit case for each row.

| Row | Node | Command family | Fixed parts |
|---|---|---|---|
| N1 | Dell, setup | `podman network create` | `--internal --subnet 10.89.7.0/24 qa-internal`; `qa-egress` without `--internal` |
| N2 | Dell | `podman run -d` (proxy) | `--name qa-proxy`, `--network qa-internal,qa-egress`, stock Squid image by digest, `squid.conf` mounted read-only, `--read-only`, `--cap-drop=ALL --cap-add=SETUID,SETGID`, no `-p` |
| N3 | Dell | `podman inspect` | proxy `qa-internal` address; image digests |
| N4 | Dell | `podman run --rm` (tester) | every flag in 10a.2, including `--name qa-<pass>-<tester>` from validated ids; entrypoint `/usr/local/bin/qa-entry`; no `-p`, no `--privileged`, no other network |
| N5 | Dell | `podman stop`, `podman rm -f` | by `qa-<pass>-<tester>`, `--time 30`; fallback by the ids from N6 |
| N6 | Dell | `podman ps -a` | `--filter label=qa.pass=<pass>` or `qa.tester=<tester>` |
| H1 | Mac host | `security find-generic-password -a decoy-qa -s decoy-qa-keychain-probe -w` (stdin closed, output discarded, 10-second timeout), `defaults read` | login keychain unlocked; vmnet `Shared_Net_Address` and `Shared_Net_Mask` against the topology |
| T1 | Mac | `tart clone` | `qa-macos15-base`, clone `qa-<pass>-<tester>` |
| T2 | Mac | `tart run` | `--no-graphics`, one `--dir=qa-ro:<path>:ro`, no writable share |
| T3 | Mac | `tart exec` (wait, pf, checks) | `true`; `route -n get default`; `sudo -n shasum`; `sudo -n pfctl -E -f /etc/pf.qa.conf`; `sudo -n pfctl -s info`; direct `curl` probe as `qa` |
| T4 | Mac | `tart exec -i` (run) | `sudo -n -u qa -H /usr/local/bin/qa-entry <charter> <issued ids>`, token on stdin |
| T5 | Mac | `tart exec` (export) | `sudo -n tar -C /Users/qa -cf - inbox` |
| T6 | Mac | `tart stop`, `tart delete`, `tart list` | `--timeout 60` on stop |
| S1 | Mac | `squid` | `-N -f <checkout>/scripts/qa/proxy/squid.conf` |
| K1 | devbox to node | `ssh` (token copy) | fixed remote command, token on stdin |
| K2 | devbox to node | `ssh` (token removal) | `rm -f ~/.config/decoy-qa/claude-token` |

#### 10a.6 Tests and probes

Unit tests (AT-7, AT-10, AT-14 to AT-16) check every argv row, `qa-submit`, the host candidate step, the Tart host preflight, the topology and kind registries, the token checks, the entrypoint's environment rules (run as a shell script against a fake `claude`), each lifecycle step's cleanup under an injected failure, recovery, and the Squid config shape. The Dell allow and deny tests (AT-14) run the real Squid image with the real config.

S3 runs these probes (P-1 to P-11) for real, on the Dell in a container and on the Mac in a guest as `qa`. Each is recorded in the S3 record with its command and exit, never with a value:

- P-1. A planted file in the node's checkout path cannot be read; the checkout path does not exist inside.
- P-2. Other testers' inboxes and the host home do not exist inside. A write to `/fault` stops at 64 MiB.
- P-3. The pass needles file, the refusal set and the host `findings.py` do not exist inside, under their host paths or by a file-name search. Only `qa-submit` is present, and it writes into `QA_INBOX` only.
- P-4. With every proxy variable unset, a raw TCP connect to a public address on ports 443 and 80 fails, and so does a name lookup through the network.
- P-5. With every proxy variable unset, direct HTTPS to `api.anthropic.com` fails.
- P-6. Through the proxy, CONNECT to another domain, to an IP literal of the model API, and to port 80 is refused. On the Mac, `pfctl -d` and `sudo -n true` fail as `qa`.
- P-7. `claude -p` with a one-line prompt succeeds through the proxy. The entrypoint's environment name list (names only) holds no API-key, base-URL or alternate-provider name, and no Claude settings file exists. So the only credential is the subscription token.
- P-8. Fail closed: with the token file missing, or empty, the entrypoint exits 78 before `claude` starts. With the proxy stopped, `claude -p` fails and P-4 still holds.
- P-9. Inbox persistence: a planted candidate submitted with `qa-submit`, with a `repro.sh`, is published by the host `findings.write`, and a planted candidate holding a needle, or the token, is refused with a `candidate-refused` event. A planted finding is published after a normal exit, after a stop mid-run (`podman stop` on the Dell, a launcher signal on the Mac), and after a launcher kill followed by recovery at the next launch. On the Mac, a recovery whose boot is made to fail keeps the clone.
- P-11. With the login keychain locked (`security lock-keychain`), the preflight refuses before `tart clone`; after unlocking, it passes.
- P-10. Cleanup: after each P-9 case, no container with the pass label is left, the inbox folder and `inbox.tar` are gone, `tart list` shows no `qa-<pass>-` clone except a kept `recovery-blocked` one, and after pass end no token file is left on the node.

## 11. Owner questions

- Q5 (added 2026-11-20, rev 3): install Podman on the Dell and Tart plus one pinned macOS 15 base image (about 25 GB) on the Mac mini. No new spend. Answered: yes, owner 2026-11-20. Tart 2.42.0 installed on the Mac from the checksummed release (FSL-1.1, internal use allowed).
- Owner decision, 2026-11-20 evening, in the owner's words: "I don't care how long it is, I want QA on the whole product and I want them to be able to interact like a human QA/tester would so that we get actual good feedback on how it performs before we expose V1." Applied in rev 3.4: the 8,000-line program ceiling is removed (section 9), section 5.9 maps every V1 feature group to a layer, L3 charters carry no step lists (5.3), and findings have `usability`, `docs` and `performance` kinds next to `bug` (5.6).
- Q4 (added 2026-11-20, rev 3): model access for testers. Answered by the owner 2026-11-20: use the Claude subscription, not the API. Testers run Claude Code in local containers and Tart guests. Owner step: run `claude setup-token` once and give the token to the orchestrator as a file on the devbox, at the path and modes in 10a.4.

| Id | Question | Recommendation |
|---|---|---|
| Q1 | Add QA-BETA as a 1.0 row in the release group | Yes (owner 2026-11-20: "do a writeup ... let's add to QA methodology"). Answered. |
| Q2 | The CI persona needs a real CI system. Create a private sandbox repo in the `decoy-data` organization, run on GitHub-hosted runners? | Yes, through the CI workflow route (5.3): P3 writes the workflow inside its container; the orchestrator runs it on hosted runners with no Claude token and no corpus and returns sanitized evidence. Hosted runners are what most companies use and give real secret masking, artifacts and re-runs, within the organization's included private-repo minutes. Proceeding on recommended (owner 2026-11-20 go-with-recommended). |
| Q3 | Public data set: Synthea and Chinook | Yes; both licenses allow internal testing; nothing is redistributed. |
| Q4 | Model access and spend | Answered (owner 2026-11-20): testers use the Claude subscription, not the API, so there is no metered spend; the entrypoint clears every API-key and alternate-provider variable (10a.4). L runs fit the Dell and the existing GCP test nodes. No new spend. |

## 12. Compatibility impact

None. No product surface changes. The tooling reads the exit registry and schemas. S1a adds `allpairspy` to the dev dependency group. The lock change requires one full suite on the merge head.

## 13. Slices

| Slice | Dates and estimate | Contents | Risk | Review |
|---|---|---|---|---|
| S0 | 2026-11-21, 1 day, 5 files, 300 lines | merge this plan; add the roadmap row, current method, checklist pointer and CODEMAP rows | R1 docs | Codex |
| S1a | 2026-11-22 to 2026-11-25, 4 days, 11 files, 1,200 lines (actual about 27 files, 3,500 lines; re-baselined 2026-11-20) | add `io.py`, corpus manifest and tools, matrices, `allpairspy`, surface registry and AT-1, AT-6 and AT-8; run M3 on the final head | R2 data and atomic writes | Dennis then Codex |
| S1b | 2026-11-26 to 2026-12-01, 6 days, 15 files, 1,700 lines | add the shared sweep, I1 to I7, `findings.py`, `repro.py`, AT-2 to AT-5, AT-7, AT-9 and AT-11 to AT-13; run M1, M2 and M4 on the final head | R2 oracle and publication controls | Dennis then Codex |
| S2 | 2026-11-22 to 2026-11-30, 9 days, 48 files, about 4,150 lines (rev 3.6; file list below; an estimate, not a cap) | add five charters, checklist, doc-walk and triager briefs, finding template, the launcher and `sandbox/` package, the topology descriptor, the Squid and pf configs, the tester image, entrypoint and `qa-submit`, `nodes.md`, the CODEMAP row, the `KINDS` and `EVENTS` registries and `write_event` in `findings.py`, the release-probe upgrade step, `submission.py` and the `workflow-candidate` type, AT-7 additions, AT-10, AT-14, AT-15, AT-16 and AT-17; delete the setup script and its test; run M5 to M8 on the final head. Starts its `findings.py` work after S1b (#360) merges | R2 credentials, isolation and egress | Dennis then Codex |
| S3 | 2026-12-02 to 2026-12-03, 2 days, 1 record | run the dry run on Linux and macOS; run the sandbox probes P-1 to P-10 (10a.6) on the Dell and the Mac; build S and M on both systems and L on Linux; run a 10-cell matrix smoke and one 30-minute charter; triage one finding | R2 operational proof | Codex reads the record |
| Reserve | 2026-12-04, 1 day | correct dry-run failures only; defer new scope | same as the failed slice | required review for the changed slice |

S2 file list (rev 3.6). Line counts are estimates of added or changed lines:

- Kept from the S2 branch, about 650 lines, with rev 3.4 edits: the eight briefs in `docs/qa/briefs/` (L3 charters lose their step lists and name their pipeline source; P1 takes the offline install route and P3 the CI workflow route; every brief uses `qa-submit`), `docs/qa/beta-program.md`, `docs/qa/finding-template.toml` (per-kind fields, checked against `KINDS` by AT-16), `tests/unit/qa/__init__.py`, `tests/unit/qa/_paths.py`, `tests/unit/qa/test_briefs.py` and `tests/sentry/layout/test_codemap_paths.py`.
- Changed, about 100 lines: `CODEMAP.md` (the QA tooling row, section 9) and this plan.
- Rewritten, about 250 lines: `scripts/qa/launch.py` (command line only, at most 150 lines) and `tests/unit/qa/test_launcher.py`.
- New code, about 1,080 lines: `scripts/qa/submission.py` and `scripts/qa/sandbox/__init__.py`, `argv.py`, `podman.py`, `tart.py` (with the host preflight), `token.py` and `capacity.py`.
- Changed code, about 310 lines: `scripts/qa/findings.py` (`KINDS`, `EVENTS`, `write_event`, metric fields, the token needle, the `workflow-candidate` type, ids and limits from `submission.py`) after S1b merges.
- New config and image, about 280 lines: `scripts/qa/proxy/topology.toml`, `scripts/qa/proxy/squid.conf`, `scripts/qa/proxy/pf.qa.conf`, `scripts/qa/image/Containerfile`, `scripts/qa/image/qa-entry.sh` and `scripts/qa/image/qa-submit.py`.
- Changed docs, about 40 lines: `docs/release/fresh-install-smoke.md` (the upgrade step of the release probe).
- New docs, about 150 lines: `scripts/qa/nodes.md` (with the keychain login and the manual clone recovery).
- New or changed tests, about 1,290 lines: `tests/unit/qa/test_argv.py`, `test_lifecycle.py`, `test_token.py`, `test_entrypoint.py`, `test_submit.py`, `test_proxy_config.py`, `test_topology.py`, `test_kinds.py`, `test_submission.py`, the AT-7 additions in S1b's `test_findings.py`, and `tests/e2e/qa/test_proxy_rules.py` with its `__init__.py`.
- Deleted, 546 lines, not counted: `scripts/qa/setup-testers.sh` and `tests/unit/qa/test_setup_script.py`.

S1a and S2 start after S0. S1b starts after the `io.py` and corpus work from S1a. S3 needs S1b and S2. This critical path finishes before 2026-12-04.

## 14. Done when

- S0 to S3 merged. The dry-run record shows one finding from tester submission through repro and triage. A planted finding is acceptable.
- The dry-run record shows a tester started on a closed group within one hour of the launch command.
- The corpus S, M and L tiers are built and hash-checked on the Dell, S and M on the Mac.
- The S3 record shows probes P-1 to P-10 (10a.6) passing on the Dell and the Mac, including a planted checkout read that fails, direct sockets that fail with the proxy variables unset, and a `claude -p` call on the subscription that fails closed without the token or the proxy.
- The coordinator hand-back contains only counts and finding ids. The captured tester output stays node-local.
- The board shows QA-BETA closed and each checklist group's "ready for QA" state, so the first L1 pass can start the day a group closes.

## 15. Defect catalog and enumerations

### 15.1 Plan defect catalog classes

| Class | Name | Closing structure | Sentry or property test | Mutation |
|---|---|---|---|---|
| 1 | value leak | `findings.py write` checks every tester record; `findings.py publish` checks each pass record and Slack text; one surface registry drives the sweep | AT-2, AT-7, AT-11 and AT-13 | M1 and M2 |
| 2 | cleanup | each run uses a fresh `DECOY_HOME` and output folder; an interrupted private write leaves no partial target; every sandbox lifecycle step has its cleanup in one `finally` path, containers are found by name and then by labels, the inbox is published before it is deleted, a clone is deleted only after a validated export, and recovery handles stale inboxes and clones (10a.2, 10a.3) | AT-9, AT-10 and AT-13; probes P-9 and P-10 | N/A: cleanup is wiring; AT-10 and AT-13 inject the failure at each step, including a recovery boot failure |
| 3 | state | each run has its own home and output folder; launcher-issued ids are tester-scoped and create-once | AT-9 and concurrent AT-13 | mutation M4 returns the recorded exit without a run |
| 4 | route | the matrices cover every route the docs name (pandas, native, chunked, out-of-core) and I3 compares routes only where the docs promise equality | AT-6 coverage property, AT-4 | N/A: mutations are core only (owner 2026-11-10); AT-6 is a property test over random parameter sets |
| 5 | referential | I2 applies `fail`, `remap` and `preserve` to complete FK tuples | AT-3 | N/A: AT-3 plants a tuple-only orphan; builder mutations stay on core leak and repro logic |
| 6 | untrusted input | downloaded data is untrusted: hash checked, own folder, read as data only with `python -I`; testers run in a container or guest with no checkout and egress only to the model API; inbox files and the Tart export stream are untrusted candidates, accepted only in the artifact layout with issued ids and published only through the host `findings.write` | AT-7, AT-8, AT-10, AT-14, AT-15 | M3 (rename before the hash check); M5 (final proxy deny removed); M6 and M7 (topology drift) |
| 7 | TOCTOU (check-then-use) | `fetch.py` downloads to a temp file, checks the hash on that file, then renames it; the checked file is the used file | AT-8 | M3 (rename before the hash check) |
| 8 | weak tests | each invariant checker has a planted defect and each documented exception has a pass case | AT-2 to AT-6 and AT-12 | M1; other checker cases use planted defects because the owner limits mutations |
| 9 | refactor | the checklist and journey call one `sweep.py`; no product code moves | AT-11 detects another sweep | N/A: this is QA wiring, and AT-11 supplies the realistic bypass case |
| 10 | frozen contracts | strict versioned readers load manifests and finding records; unknown major and missing versions fail | AT-5 plus reader cases for missing version, next major, wrong primitive type and extra minor fields | N/A: QA-BETA changes no product contract; reader defect cases cover its stored records |

Recurring-defect checks also apply. All regex validation uses `fullmatch`. Stored primitives are strict. Safe raised errors have no `__cause__` or `__context__`. Guards normalize common command and import forms. The sentries reject private imports, hidden CI exits, unchecked allowlisted helpers and raised pins. Mutations run again on the final slice head.

### 15.2 Enumerations

#### 15.2.1 Exit paths

I6 classifies every exit the CLI can give:

- `EXIT_OK` 0 (`src/decoy/cli/exit_codes.py:45`): pass when the docs expect success.
- `EXIT_USAGE` 1 (`src/decoy/cli/exit_codes.py:49`): the `error: internal error (<ClassName>)` form is always a crash. This applies with and without verbose output (`src/decoy/__main__.py:154`, `src/decoy/__main__.py:187`). Other documented `error:` reasons are refusals. A traceback or missing reason is a crash.
- 2 (`src/decoy/cli/exit_codes.py:56` as `EXIT_WARNINGS`; also Click's usage error, `("failed", "parameter")` in `RUN_EXIT_MAP`, `src/decoy/cli/exit_codes.py:135`): pass when a documented warning code is present or the docs describe the usage refusal.
- `EXIT_RUNTIME` 3 (`src/decoy/cli/exit_codes.py:66`): a pass only for the named read-only, disk-full and quota-fault cells. Each cell must also prove that no partial output became current. It is a finding elsewhere (`docs/qa/cli-v1-checklist.md:275`).
- `EXIT_FINDINGS` 4 (`src/decoy/cli/exit_codes.py:74`): pass for a documented findings exit (`run --post-validate-enforce`, `scan diff --strict`, `ci check`, a `report` check, `library fsck`, an incomplete `library prune` or `clean`) when the output names the findings.
- `EXIT_CAPACITY` 5 (`src/decoy/cli/exit_codes.py:82`): a pass only for a named memory-capacity cell. It is a finding for disk and quota faults.
- `EXIT_PARTIAL` 6 (`src/decoy/cli/exit_codes.py:103`): always a finding; it is reserved and no path reaches it in V1.
- 130 (`_EXIT_INTERRUPTED`, `src/decoy/cli/exit_codes.py:111`): pass after a Ctrl-C in P5; a finding anywhere else.
- Any other code, or a signal death: a finding.

#### 15.2.2 Routes

- pandas (`--no-native`)
- native (`--native`, and default when the companion is present)
- chunked (`--chunked`)
- out-of-core (a `--max-memory` budget below the item size)
- subset on and off (`--no-subset`)
- installed bundle on Linux x86-64, macOS arm64; Windows after rows 89 and 6

#### 15.2.3 FK shapes

- single parent and child
- three-level chain
- self-reference
- composite key
- cycle (refused in V1 by owner decision; a refusal check)
- child with orphans in the input (the docs' orphan policy and quarantine decide the expected output; I4 counts quarantined rows)

#### 15.2.4 Fields

Finding record fields (section 5.6):

- `schema_version`, `id`, `layer`, `persona`, `group`
- `platform`, `cli_version`, `engine_version`, `bundle_digest`
- `corpus_item`, `command`, `config` (values removed)
- `expected` (doc path and line, or invariant id), `actual`, `exit`, `signature`, `doc`
- `kind` (`bug`, `usability`, `docs` or `performance`), `proposed_tier` (optional for every kind)
- metric fields: `route`, `tier`, `wall_seconds`, `peak_rss_mib`, `felt_slow`
- artifacts: `<id>.repro.sh` (required for `bug`, forbidden otherwise), `<id>.workflow.yml` (P3 only)

The per-kind required, optional and forbidden sets are the table in 5.6, held in `KINDS`. S1b's string field `repro` becomes the `repro.sh` artifact.

Event record fields (5.6): `schema_version`, `event` (one of `EVENTS`), `tester`, `step`, `count`.

Corpus manifest fields: `schema_version`, `id`, `origin`, `license`, `sha256`, `tier`, `format`, `shapes`, `marker_columns`.

#### 15.2.5 Output surfaces

`docs/qa/surfaces.toml` is the only surface list. It drives sweep dispatch, AT-2 parameters and documented exceptions. AT-2 fails if these consumers do not use the same registry entries. The registry contains:

- output data files (CSV, TSV, Parquet, fixed width)
- stdout, including `--json` documents
- stderr
- log files under the project and `DECOY_HOME`
- run result files (`--result`)
- evidence manifests (`--evidence-out`)
- post-scan and integrity reports (`--integrity-out`)
- scan documents (`decoy scan --output`)
- vault files (searched for needles; encrypted values are expected)
- notification payloads (`--notify` to a local sink)
- node-local tester stdout and stderr capture, finding records and pass records
- Slack text from `findings.py publish`

Documented exceptions: `passthrough` columns; the documented `truncate` prefix; `text_redact` surrounding text; `unmask` and `detokenize` output files when the run holds the vault file and the mask secret.

### 15.3 Frozen contracts

QA-BETA changes no frozen contract. It reads two: the exit registry (`src/decoy/cli/exit_codes.py`) and the versioned schemas (`docs/schemas/`). If either changes before a pass, the pass uses the new version; AT-5 reads the live registry, so a change shows up in the test, not as silent drift.

## 16. Pre-mortem

Assume the V1 QA pass found too little and users hit bugs in January. Likely causes and the guard for each:

- **Testers stayed on the happy path.** Guard: P5 careless-user charter, refusal checks for every refused pair, and the malformed-file shapes in the corpus.
- **The corpus was too clean.** Guard: Synthea's real-world mess, five date formats, encodings, heavy nulls, duplicates.
- **Findings were lost in triage.** Guard: every finding has a record and a triage result in the pass record; the board shows open counts.
- **Agents invented findings and the real ones were drowned out.** Guard: the repro gate; dedupe by root cause.
- **The oracle had a hole or cried wolf.** Guard: planted-defect tests with pass cases for every documented exception; the class check in triage turns repeated findings into sentries.
- **QA started late.** Guard: S0 to S3 finish before the V1 build ends; L1 starts per group as groups close.
- **The CI story was never tried.** Guard: P3 on a real hosted CI system (Q2), with its notes going to REL-DOCS.

## 17. Review map (Dennis r1)

| Finding | Closed in |
|---|---|
| H1 third leak sweep, no secret needles | 4 (one sweep), 5.2 (needles), AT-2, AT-11 |
| H2 exit classification | 15.2.1, AT-5, F13 |
| H3 leak false positives on documented behaviour | 5.5 I1 per strategy, 15.2.5 exceptions, AT-2, F12 |
| H4 matrix flags and constraints | 5.4 (two matrices, strategy mix, three constraint kinds), AT-6 |
| M1 connectors not built | 5.2, P2 |
| M2 command coverage, fit | 5.1 command table, P1 |
| M3 I3 promises | 5.5 I3 with doc lines, AT-4 |
| M4 I4 not computable | 5.5 I4 |
| M5 I8 not an RSS ceiling | 5.5 (metric only) |
| M6 sandbox and hand-backs | 5.1 sandbox, 5.7 step 2, AT-10, F2, F3 |
| M7 allpairspy in CI | 7, 12 (dev group, full suite on S1a) |
| M8 proportionality | 2 (no XL), 5.2 (Synthea and Chinook), 8 (four mutations), 13 (two risk-cohesive harness slices) |
| M9 hosted runners | Q2 |
| M10 no admin role | P4, 15.2.5 |
| L1 one-hour guarantee check | 14 |
| L2 schema_version | 5.2, 5.6, 15.2.4 |

## 18. Review map (Codex r1)

| Finding | Label | Closed in |
|---|---|---|
| 1. Default crash form passed as a refusal | V1 | I6, AT-5 and 15.2.1 classify both `internal error` forms as crashes |
| 2. I/O-fault exits contradicted the registry | V1 | AT-5 and 15.2.1 allow exit 3 only in named I/O-fault cells; exit 5 is memory only |
| 3. I2 rejected documented preserved orphans | V1 | I2 and AT-3 cover `fail`, `remap` and `preserve` |
| 4. Free-form tester hand-backs escaped the writer | V1 | 5.1, 5.6 and 5.7 keep output node-local and return counts and ids only |
| 5. The refusal set covered only input PII | V1 | 5.2 and AT-7 cover canonical forms of every input and output scalar |
| 6. AT-2 omitted declared surfaces | V1 | `docs/qa/surfaces.toml` drives the sweep and AT-2 |
| 7. I4, I5 and I7 lacked planted defects | V1 | AT-12 adds the required defects |
| 8. The composite FK case was not tuple-only | V1 | AT-3 uses parents `(A,1)` and `(B,2)` with child `(A,2)` |
| 9. Repro could return a saved exit | V1 | AT-9 requires a nonce witness and recurring signature; M4 returns the saved exit |
| 10. Concurrent findings could collide or tear | V1 | 5.6 and AT-13 use tester-scoped ids, create-once publication and interruption cases |
| 11. A unit test could not prove OS isolation | V1 | AT-10 checks commands; S3 runs real Linux and macOS probes after owner setup |
| 12. Publication rules were scattered | DESIGN | `findings.py publish` is the only pass-record and Slack path; AT-13 guards it |
| 13. Surface tables could drift | DESIGN | one surface registry drives dispatch, tests and exceptions |
| 14. QA writers could copy product private helpers | DESIGN | `io.py` owns 0600 create-once atomic writes; AT-13 rejects other writers and private imports |
| 15. Marker id could contain marker text | V2-LOG | 2, 5.5 and AT-7 require opaque coordinate ids |
| 16. S1 did not fit the preparation window | V2-LOG | section 13 splits S1, gives dated estimates and reserves 2026-12-04 |

## 19. Review map (Codex plan review of rev 3.1, closed in rev 3.4)

| Finding | Label | Closed in |
|---|---|---|
| 1. The Linux inbox was lost with tmpfs and `--rm` | V1 | 10a.2: a private bind-mounted inbox per tester; create, run, publish through `io.py`, then delete; recovery after interruption; AT-10, P-9, P-10 |
| 2. macOS egress was advisory | V1 | 10a.3: guest pf default deny, proxy address and port only, Claude runs as non-admin `qa`; P-4 to P-6 with the proxy variables unset |
| 3. No concrete proxy registry and guard | DESIGN | 10a.1: one Squid config for both nodes, dual-homed Linux proxy; AT-14 allow and deny tests; M5; section 9 |
| 4. No safe, proven credential path | V1 | 10a.4: 0600 file in a 0700 directory, owner and symlink checks, one read-only file mount or stdin, fixed entrypoint with a clean environment, transfer and removal; P-7, P-8 |
| 5. No executable Tart lifecycle | V1 | 10a.3 steps 1 to 9 with cleanup at each step; 10a.5 argv rows T1 to T6; AT-10 |
| 6. Quota exhaustion became failed QA jobs | V1 | 5.8 capacity formula and usage-limit pause; F10 |
| 7. Placement described the discarded mechanism | DESIGN | section 9 lists `CODEMAP.md`, `sandbox/`, `proxy/`, `image/`; S2 changes the CODEMAP row |
| 8. Stale text, risk, Q4, citation, size, AT-10 | V2-LOG | F3, section 7, S2, S3 and Done no longer name OS users; S2 is R2 with Dennis then Codex; Q4 row is model access and spend; 5.8 is cited; S2 file list and 2,800-line bound in 13; AT-10 and 10a.6 cover each named case |

## 20. Review map (Codex plan review of rev 3.4, closed in rev 3.5)

Prior findings 1, 2, 3, 6 and 7 were closed in rev 3.4. Prior 4 (credential path) closes with finding 1 below; prior 5 (Tart lifecycle) closes with finding 4.

| Finding | Label | Closed in |
|---|---|---|
| 1. No executable submission path | V1 | 5.1 and 5.6: sandbox files are untrusted candidates; `qa-submit` checks structure only; `QA_INBOX` and `QA_FINDING_IDS` are passed in; the host `findings.write` checks host needles, the refusal set and the in-memory token; AT-7, AT-10, P-3, P-9 |
| 2. Repro scripts rejected and lost | V1 | 5.6 artifact layout (`<id>.toml`, `<id>.repro.sh`, P3's `<id>.workflow.yml`), size limits, record last as commit marker; triage through `repro.run`; AT-7 normal, interrupted, recovery, symlink, oversize and mismatched-id cases |
| 3. P1 and P3 could not run under isolation | V1 | 5.3: P1 installs and upgrades offline from staged signed artifacts, plus a non-agent release probe; P3 writes a workflow candidate that the orchestrator runs without the token or corpus; Q2 proceeding on recommended; 5.9 claims P3 only through this route |
| 4. Recovery deleted unexported findings | V1 | 10a.3: no clone deletion before a validated export; three tries, then `recovery-blocked` keeps the clone; AT-10 injected recovery boot failure; P-9 |
| 5. No container name for teardown | V1 | 10a.2 and N4: validated `--name qa-<pass>-<tester>`, label fallback; AT-10 timeout, signal and launcher-kill cases |
| 6. Finding kinds did not fit the oracle | V1 | 5.6: contradictions are `bug` until reproduced; `docs` is missing or unclear guidance only; events are separate records; per-kind field table; unknown kind refused (AT-7) |
| 7. Metrics collided with corpus scalars | V1 | 5.6: typed, range-checked metric fields skip the refusal lookup; string fields keep it; AT-7 same-number case |
| 8. Tart host prerequisites | V1 | 10a.3 host preflight: login keychain usable, vmnet address and subnet equal the topology, guest gateway check; argv H1; AT-10 |
| 9. Kind policy scattered | DESIGN | one `KINDS` registry in `findings.py`; template, reader, writer, publish and triage derive from it; AT-16 |
| 10. Topology constants scattered | DESIGN | `scripts/qa/proxy/topology.toml`; AT-15 cross-file guard; M6 and M7 |
| V2-LOG: layer for every group | V2-LOG | section 2 and 5.9 say "layer or named non-tester gate" |
| V2-LOG: F1 wording | V2-LOG | F1 says no `bug` reaches the roadmap without a repro |
| V2-LOG: dedupe wording | V2-LOG | 5.7 step 3 keeps the clearest record, and its repro when required |
| V2-LOG: capacity formulas | V2-LOG | 5.8 gives the total and the Mac limit separately |
| V2-LOG: one pass per node | V2-LOG | 5.8 node-wide `flock`; AT-10 |

## 21. Review map (Codex delta review of rev 3.5, coordinator ruling, closed in rev 3.6)

Codex's delta review at `3a93cb22` closed prior findings 1, 2, 4 to 7, 9 and 10. Prior 3 (P3) and prior 8 (keychain) were partly open. The review was past the round cap, so the coordinator ruled on the edits below.

| Finding | Label | Closed in |
|---|---|---|
| 1. P3 could not submit a workflow before a finding existed | V1 | 5.3 and 5.6: a `workflow-candidate` type, stored under `workflows/` outside `findings/`, never triaged, scanned by the same `findings.write`; only a follow-up observation is a finding; AT-10 path |
| 2. The keychain preflight did not prove unlock | V1 | 10a.3 and H1: `nodes.md` provisions a probe item; preflight reads it with `security find-generic-password -w`, stdin closed, output discarded; refuses before `tart clone`; AT-10 locked case; P-11 |
| 3. `qa-submit` was a second validator and writer | DESIGN | `scripts/qa/submission.py` is the one descriptor; `qa-submit` writes through `io.publish_private_once`; the image holds exact copies of `io.py` and `submission.py`; AT-17 same-source guard; M8 |
| 4. The short-scalar exemption let real values through | V1 | 5.2: every scalar indexed; one- and two-character values match as whole tokens; AT-7 cases for `F`, `CA`, `0`, `-1` and substring non-matches |
| V2-LOG: F10 formula | V2-LOG | F10 uses the 5.8 total and Mac limit |
| V2-LOG: status and S2 list label | V2-LOG | header says rev 3.6; the S2 file list says rev 3.6 |
