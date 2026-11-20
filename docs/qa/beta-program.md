# QA beta program (V1)

Status: current

Roadmap row QA-BETA (release group, owner 2026-11-20). Plan: `docs/plans/2026-11-20-qa-beta-program.md`.

This file says how agent beta testing works in the V1 QA pass. Read it when a QA pass starts. It
adds exploration, data breadth and one shared oracle to the scripted checks. It does not replace
the [CLI checklist](cli-v1-checklist.md), the [journey](cli-v1-journey.md) or the engine
checklist (`E:docs/qa/`). Those stay the scripted floor.

The owner rule still applies: QA runs only on a feature group that is V1 complete (see "When a
group is ready for QA" in the checklist). Anything found in an unfinished group is filed against
that group and held until its pass.

Some tooling named here is not built yet. Each such item says which slice of the plan builds it
(S1a, S1b or S2). Until that slice merges, the item does not exist and a pass cannot use it.

## Four layers

| Layer | Who runs it | Input | Oracle | When |
|---|---|---|---|---|
| L1 Checklist pass | one Sonnet agent per checklist group | the group's checks, the corpus | the check's expected exit and output, plus the invariants | as each group becomes V1 complete |
| L2 Doc walk | one Sonnet agent per set of public docs pages | every example in the public docs, run as written | the doc text, plus the invariants | as each group becomes V1 complete, for that group's pages |
| L3 Persona beta testers | five Sonnet agents, one per persona | a charter, the public docs, the corpus | the docs and the invariants; the agent's judgement only for "confusing" findings | after the V1 build is complete (personas cross groups) |
| L4 Matrix runs | the harness, no agent | the pairwise settings matrices over the corpus | the invariants only | after the V1 build is complete |

L4 is a script because wide coverage is cheap and mechanical. Agents (L1 to L3) do the work that
needs judgement, docs reading and exploration.

### Command coverage

L4 covers `decoy run` only. The other commands have these layers:

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
| `library fsck`, `diff`, `ref`, `prune`, `clean`, `export` | yes | yes | P2 |
| `models list`, `models install` | yes | yes | P1 |
| `upgrade` | yes | yes | P1 |

## Sandbox

Every tester works from the installed release bundle and reads only the public docs folder. A
tester that reads the source tests the code's intent, not the user's experience.

- Each tester runs as its own OS user on Linux and macOS. The user's home holds only the bundle,
  the public docs and a read-only corpus mount. The user cannot read repository checkouts on the
  node.
- The owner runs `scripts/qa/setup-testers.sh` once on each node to create the tester users. The
  launcher does not create users. (Built by slice S2.)
- The launcher captures tester stdout and stderr in a node-local file. The coordinator gets only
  finding ids and counts. (Built by slice S2.)
- Briefs forbid values in messages.

## Corpus

One manifest, `docs/qa/corpus/manifest.toml` (`schema_version = 1`), lists every corpus item:
`id`, `origin` (public URL or `generated`), `license`, `sha256`, `tier`, `format`, `shapes` and
`marker_columns`. Data never enters git. `scripts/qa/corpus/fetch.py` downloads public items and
`scripts/qa/corpus/generate.py` builds generated items. Both write to `~/decoy-qa-corpus/<id>/`
on a node. (The manifest and both tools are built by slice S1a.)

`fetch.py` checks the SHA-256 on a temporary file before it renames it into place. It refuses an
item with a wrong hash, no license, or a license that is not on the allowed list. Downloaded data
is read only as data, with `python -I`.

**Formats.** CSV (comma, semicolon, tab, quoted newlines, BOM, Latin-1 and UTF-16 encodings,
CRLF), TSV, Parquet (plain and dictionary-encoded), fixed width with a layout file, and a DuckDB
database (`--duckdb-source`). Connector sources and targets (Postgres, S3, GCS, SFTP) use the
checklist's local containers (see "External services" in the checklist). They join the corpus
only when their group closes.

**Shapes.** Single table; parent and child; a three-level FK chain; a self-reference; a
composite key; a cycle (the docs refuse it in V1); wide (200 columns); free text with names and
emails inside; dates in five formats and bad dates; heavy nulls (90%); all-null and constant
columns; duplicate keys; a header-only file; an empty file; one malformed file per format.

**Size tiers.** S is 1k rows, M is 100k, L is 1M. L runs only on the Dell or a GCP test node,
never on the devbox. Nothing above L runs. Larger sizes are extrapolated from the S to L timings
(owner decision A-2). `mask-big` (checklist RUN-07, RUN-08) covers large single runs.

**Generated data.** The generator uses NumPy and the standard library, not Faker. The product
masks with Faker, so data made by the same library could hide a defect that depends on Faker's
own patterns.

**Markers.** Every generated text cell holds `qamark` plus a unique number. Public items keep
their data. For public items, I1 uses a same-row comparison instead of markers.

Each pass writes two node-local files:

- a needles file with every marker and every secret the pass uses;
- a refusal set with salted indexes of the canonical form of every scalar in the pass input and
  output files. This includes non-PII, numeric, date, multi-token and output-only values. The
  canonical form uses the decoded scalar type and its stable text form.

These files never leave the node.

**Public data and licenses.** Synthea (Apache-2.0) and Chinook (MIT). An item enters the
manifest only with a license that allows internal testing. Nothing from the corpus is
redistributed, committed or quoted in a record.

## Personas (L3 charters)

Each charter states the persona, the mission, the time box (2 hours of agent time), the corpus
items in scope, the node and the debrief questions. Charters go in `docs/qa/briefs/` with the
checklist-pass, doc-walk and triager briefs. (Built by slice S2.)

| Persona | Mission | Node |
|---|---|---|
| P1 Solo developer | install from the download page steps, run the demo, mask a mix of local files, change settings between runs, re-run, `fit` a table then generate from it and grade it with `report fidelity`, upgrade | Mac (macOS arm64), then Dell (Linux) |
| P2 Data engineer | DuckDB sources, subsetting a three-level FK chain, chunked and native runs on M and L items, scans of a new source; connector sources and targets once their group closes | Dell |
| P3 CI engineer | Set Decoy up in CI the way a company would. Pin the install. Read secrets from the environment. Run `decoy ci check` and use exit codes as gates. Keep evidence and result files as artifacts. Write down every step a company needs. | GitHub-hosted runner in a private sandbox repo (owner question Q2; fallback is a shell script on a test node) |
| P4 Compliance reviewer | evidence records, `decoy report verify`, the vault and `decoy unmask` with and without the vault file and mask secret, post-scan reports, what an auditor can and cannot see | Dell |
| P5 Careless user | wrong flags, wrong file types, missing secret, interrupted runs (Ctrl-C mid-write), full disk, read-only output folder, re-running into an existing output | Dell, Mac |

P3's notes become the draft of a "Running Decoy in CI" guide. After triage they go to REL-DOCS
(row 92).

## Settings matrices (L4)

There are two matrices, because generate has no file source. Parameters come from
`docs/cli-reference.md` (the `run` options). The matrices and their constraints go in
`docs/qa/matrix.toml`, and `scripts/qa/matrix.py` writes the run list. (Both built by slice
S1a.)

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

`allpairspy` covers every pair of values that a constraint does not remove. That is 54
mask runs and 9 generate runs per platform (the generator's output on 2026-11-20; a matrix edit
changes it). Each QA pass writes its own run list. The run list
is not committed.

### Constraint kinds

Each constraint cites the doc line that sets it. There are three kinds:

- **Refused.** The run must exit with the documented code and a value-free reason. Examples:
  `--chunked` with `--vault`, with a subset block (even with `--no-subset`), with fixed width,
  with `--post-validate`, or with a strategy that is not value-keyed; `--duckdb-source` with
  `--evidence-out`; `--native` on a generate config; an unkeyed `date_shift`; `--rows` with any
  flag on its refusal list.
- **Ignored.** The run must succeed, and its outputs must equal the run without the ignored flag
  (I3). Examples: `--max-memory` and `--threads` under `--chunked`.
- **Refused after the run starts.** `--native` on a table with no compiled-kernel evidence (FK
  tables, or only passthrough, redact and truncate) must refuse before any output is written.

Every pair that a constraint removes is listed with its kind. It becomes a refusal check, an
ignored-flag equality check, or a documented n/a.

## Invariants (the oracle)

`scripts/qa/invariants/` checks the outputs of every run after the run ends. A failed invariant
is a finding. It needs no judgement. (Built by slice S1b, one module per invariant.)

| Id | Invariant | How it is checked |
|---|---|---|
| I1 | No original value survives where the column's strategy replaces it, and no needle (marker or secret) appears on any output surface, except the documented exceptions | Per column, by the config's strategy. Value-replacing strategies (hash, fpe, faker, categorical, date_shift, bucketize, tokenize, redact) get an exact-cell check and a same-row check (the output cell differs from the same row's input cell). `passthrough` is exempt. `truncate` may keep the documented prefix and nothing more. `text_redact` may keep the surrounding text but no detected entity. Non-data surfaces get the needles sweep. |
| I2 | Each output FK obeys its configured orphan policy | `fail` refuses the source orphan, `remap` gives a child tuple that joins, and `preserve` keeps the documented orphan relation. The checker compares complete key tuples. |
| I3 | Re-runs and route pairs give equal outputs exactly where the docs promise it | SHA-256 per output data file. Run ids and timestamps in result and evidence files are ignored. Pairs: a re-run with `--mask-secret`; `--chunked` against a plain run for value-keyed strategies; generate with `--master-key` across runs and machines; a flag the docs say is ignored against the run without it. |
| I4 | Every input row is accounted for | Mask: input rows = output rows + quarantined rows, per table. Subset: output rows are no more than input rows, and I2 holds. Generate: rows per table match the config or the `--rows` ratio. |
| I5 | Column names, order and types match the docs for the strategy | The schema of each output is read and compared. |
| I6 | The exit code means what the registry says | The exit classification below. `--json` output is parsed against `docs/schemas/`. |
| I7 | No refusal or error text holds a value | The needles sweep and the same-row check over stdout, stderr and logs. |

Peak RSS and wall time are recorded for each run (`/usr/bin/time -v` on Linux, `-l` on macOS).
They feed the job-time estimate. They are not an invariant: `--max-memory` is a route budget, not
an RSS ceiling.

A leak finding cites the surface and an opaque coordinate id. The id holds no marker text and no
text taken from the data. A finding never carries the matched text.

### One shared sweep

Today the checklist and the journey each have their own leak sweep. Slice S1b builds one sweep,
`scripts/qa/sweep.py`. It keeps the checklist's `qamark` prefix and exit meanings, and it uses
the journey's needle list and the pass secrets. The checklist, the journey and QA-BETA then all
call it. Until S1b merges, use the sweep step in the checklist.

### Output surfaces

`docs/qa/surfaces.toml` is the only list of surfaces. It drives the sweep, its tests and the
documented exceptions. (Built by slice S1a.) The surfaces are:

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
- the Slack text from `findings.py publish`

Documented exceptions: `passthrough` columns; the documented `truncate` prefix; `text_redact`
surrounding text; `unmask` and `detokenize` output files when the run holds the vault file and
the mask secret.

### Exit classification

I6 classifies every exit the CLI can give. The registry is `src/decoy/cli/exit_codes.py`.

| Exit | Pass when | Finding when |
|---|---|---|
| 0 | the docs expect success | the docs expect a refusal or an error |
| 1 | a documented `error:` reason is given (a refusal) | the `error: internal error (<ClassName>)` form, with or without verbose output; a traceback; no reason |
| 2 | a documented warning code is present, or the docs describe the usage refusal | anything else |
| 3 | only in a named read-only, disk-full or quota-fault cell, and no partial output became current | anywhere else |
| 4 | a documented findings exit: `run --post-validate-enforce`, `scan diff --strict`, `ci check`, a `report` check, `library fsck`, or an incomplete `library prune` or `clean`; the output names the findings | anywhere else |
| 5 | only in a named memory-capacity cell | disk and quota faults, and anywhere else |
| 6 | never: it is reserved and no V1 path reaches it | always |
| 130 | after a Ctrl-C in a P5 cell | anywhere else |
| other code or a signal death | never | always |

## Finding record

Each finding is one file at `findings/<pass>/<id>.toml` in the node-local pass folder, with
`schema_version = 1`. The template is `docs/qa/finding-template.toml` (built by slice S2). The
fields are:

- `schema_version`, `id`, `layer`, `persona`, `group`
- `platform`, `cli_version`, `engine_version`, `bundle_digest`
- `corpus_item`, `command`, `config` (with values removed)
- `expected` (a doc path and line, or an invariant id), `actual`, `exit`
- `repro`, `proposed_tier`, `confusing`

Rules for writing a finding:

- The launcher gives each tester its own ids before the tester starts. Each id can be used once.
- `scripts/qa/findings.py write` is the only way a tester submits a finding. It refuses text that
  holds a needle or any canonical scalar from the refusal set. It also refuses a coordinate id
  that holds marker text. (Built by slice S1b.)
- Every QA writer uses one private helper, `scripts/qa/io.py` (`publish_private_once`). It
  writes a 0600 file, reserves the target so it is created once, and publishes it with an atomic
  rename. (Built by slice S1a.)
- Testers return only counts and finding ids to the coordinator. Never paste a cell value, a
  marker or a secret into a finding, a message or a record.

A good finding names the command, the config with values removed, the corpus item, the platform
and the versions. It cites the public doc line that set the expectation, or the invariant that
failed.

## Triage

The triager is an Opus agent. The steps are:

1. **Collect.** Read the finding records through `findings.py`. The coordinator hand-back has
   counts and finding ids only.
2. **Check our own text.** Run the sweep and the refusal-set check over the node-local pass
   folder before anything is published. A hit stops publication and creates a process finding.
3. **Dedupe.** Group findings with the same root cause. Keep the clearest repro.
4. **Reproduce.** Run each repro script on a clean node, not the tester's node. The repro runs in
   a fresh `DECOY_HOME` and must show the same failure. `scripts/qa/repro.py` runs it (built by
   slice S1b). No repro means the finding is closed as not reproduced. It stays in the record.
5. **Classify** by the V1 bar. Only a function break, data loss, a non-admin leak, or a copy of a
   central mechanism blocks V1. Everything else goes to the V2 log. A doc-only mismatch goes to
   REL-DOCS (row 92) or the docs-truth row.
6. **Class check.** If two or more findings share a class, propose a sentry or a choke point, not
   one patch per finding.
7. **File.** Each V1 finding becomes a roadmap row in its group file. V2 log items go to the V2
   log.
8. **Publish.** `findings.py publish` writes the pass record under `docs/records/` and sends the
   Slack text. The pass record lists each finding and its triage result. Slack posts carry counts
   and row ids only.

`findings.py publish` is the only QA function that writes under `docs/records/` or calls the
Slack script. Remediation follows the owner rule: after the group's QA pass, through the normal
dev loop.

## Capacity and nodes

- Testers count against the builder cap (6 builders and 2 reviewers).
- One QA pass runs at most 4 testers at once. That leaves 2 builder slots for remediation.
- Tester agents are Sonnet. The triager is Opus.
- Each charter has a time box. Usage is checked each tick.
- L runs use the Dell first, then the GCP test nodes.
- macOS runs use the Mac.
- Windows cells wait for rows 89 (WIN-FEAS) and 6 (WIN-RUNNER), as in the checklist.
- Each run has a timeout. A stall is recorded as a finding of type `stall`. The test stall guard
  and node-watch stay on.
