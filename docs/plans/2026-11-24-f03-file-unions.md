Status: plan

# F03: several files as one logical table, and pattern selection of input files

Owner: Cam. Author: Opus plan agent. Date: 2026-11-24. Revision 3 (plan rev 2: Dennis R1 folded in).

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN: established solutions, choke point, placement, size, pinned guarantee), `feature-dev.md`, `api-and-compatibility.md`, `reuse-first.md`, `cross-cutting-concerns.md`, `security.md`, `architecture.md`, `testing.md` (test depth), `catalogs/recurring-defects.md`; vault `Decoy-Plan-Contract-and-Defect-Catalog.md`.

Owner decision 2026-11-24: partitioned tables (roadmap candidate F03) and pattern-matched input file
names come first in 1.x, together with the S3 and GCS source work (rows 64 CLI-CLOUD and 87 F02).
1.0 stays "the engine works on small local files". Nothing here moves into 1.0.

Bases: CLI `origin/main` `488d98b3`; engine `origin/main` `9f7bb1f4a`. Engine paths are relative to
`src/decoy_engine/` and carry `E:`; CLI paths are relative to `src/decoy/` and carry `C:`; platform
paths carry `P:`; engine test paths carry `ET:` (relative to the engine repo root). Line numbers are
from those heads.

Risk: R2 (data handling across a new input route, FK integrity, evidence contract, SDK surface,
value-free output). Two reviewers per risky slice (Codex, then Dennis); see the slice table.

Revision history:

- R1 (2026-11-24): write-up with `Status: proposal`.
- R2 (2026-11-24): Codex review `GO-WITH-FIXES` (12 fact fixes F1 to F12, 17 new issues N1 to N17,
  8 design findings D1 to D8). All are folded in below. Main changes: the first cloud read carries
  the pin (F3); CSV and fixed-width members are joined record by record, not byte by byte (D4); the
  Parquet schema is decided from every footer before the writer opens, strict equality first (D5);
  output parts are a separate, later slice pair (D6, D7); member names leave the shareable manifest
  for a private sidecar (N16, N17); one acquisition step feeds every later phase (D3, N8); routes
  that skip FK checks refuse a union table (N7). Then the plan sections (section 9 on).
- R3 (2026-11-24, plan rev 2): Dennis R1 `GO-WITH-FIXES` (0 BLOCKER, 7 HIGH, 8 MEDIUM, 7 LOW).
  Every finding was checked against engine `9f7bb1f4a` and CLI `488d98b3`; all 22 are folded in,
  none disputed. Main changes: Parquet staging goes through the existing staging writer (H1); the
  pure glob grammar is its own low-tier package (H2); the first cut is re-sequenced so each merge
  ships cleanly (H3); evidence moves to `cli-local-1.1` with a versioned sidecar (H4); the marker
  rule is "not older than" (H5); the Parquet schema rule ignores RangeIndex bounds (H6); a
  route-by-test matrix and new ATs close the enumeration gaps (H7); 17 slices became 20, about 39
  builder-days (M13).

## Dennis R1 resolutions

Verification column: what was checked at the base heads. "Folded" means the plan text now carries
the fix; nothing was disputed.

| Finding | Verified against code | Resolution | Section |
|---|---|---|---|
| H1 second staging writer | `E:declared_casting/_stream.py:101` `stage_typed_sources` ("the one staging writer"; `open_fn`, `max_bytes`, `ScratchArena`, opaque `s0000` names, 0600); `ET:tests/sentry/test_staging_writer_choke_point.py:19` `CALLERS` has two files | Folded. Parquet members are staged by `stage_typed_sources` with an `open_fn` that reads the pinned members in order and an identity `batch_fn`; `source_sets/_acquire.py` joins `CALLERS`. The CSV and fixed-width record joiner is a second writer kind with its own guard. `--duckdb-source` and `postgres_snapshot` onto the acquisition: V2-LOG | 5.2, 13, 16, V2-LOG |
| H2 import tier | engine `.importlinter`: `exhaustive = true`; config and sdk in tier 4, declared_casting tier 3, execution tier 2; policy-direction contract forbids `config -> connectors, fileaccess`. Engine root has 25 `.py` modules (at cap), so the grammar must be a sub-package | Folded. New package `path_glob/` (pure, no I/O) in the bottom tier; `source_sets/` in the `execution` tier. `.importlinter` lines, layout snapshot and file-access registry entries named | 16 |
| H3 first cut | `C:cli/evidence.py:286-303` reads `src.get("path")`; `C:cli/run/_evidence.py:35-38` turns off evidence for `--duckdb-source` | Folded. (a) C3 refuses evidence for union tables until C2 lifts it. (b) D1 depends on C2 only; C4 writes its own docs. (c) all `${var}` work in C4. (d) "local, plus S3 when row 64 is merged" | 15 |
| H4 evidence version | `E:records/_payloads.py`: `schema_version: Literal["cli-local-1"]`, `fingerprint_method: Literal["full"] \| None`, `extra="forbid"`; `C:cli/evidence.py:459-460` refuses any other version | Folded. Bump to `cli-local-1.1`; old readers refuse it cleanly by exact match. Sidecar carries `schema_version: "decoy-members-1"`, one writer model, reader derived from it, strict types | 5.7, 11, 14 |
| H5 marker freshness | design rule only (no code yet); timestamp resolution is a provider fact | Folded. "Not older than", resolution documented, equal-timestamp case in AT-9 must pass. S3 multipart `LastModified` is the upload start time (AWS `ListObjectsV2` docs), so the rule is a stale-marker check, not a completeness proof | 4 (N1), 5.2, 10 |
| H6 pandas metadata | pandas writes `index_columns: [{"kind": "range", "start", "stop", "step"}]` per file, so `stop` differs per part | Folded. Compare Arrow fields plus pandas column entries; ignore range index bounds; the staged file drops the `pandas` schema key. New AT-5 case | 5.4, 10 |
| H7 AT coverage | section 12 enumerations against section 10 | Folded. Route-by-test matrix (native cells in the companion venv), AT-24 FK shapes, AT-25 profile versus oracle, AT-26 exit paths, AT-15 surfaces and `__cause__`/`__context__` asserts, AT-22 trailing newline | 10, 12 |
| M8 red first | every AT fails on the base because `files:` is unknown | Folded. Each AT must fail on its own assertion against the slice's scaffolding (first-member-only stager) | 10 |
| M9 disk admission | listed sizes undercount gzip and re-encoded Parquet | Folded. Up-front check stays; per-batch `max_bytes` budget from H1 added | 5.2 |
| M10 placement phase | member collisions need the listing | Folded. Static base check at validate; member collisions after listing, before staging | 5.8, 12 |
| M11 acquisition owner | `E:execution/_pipeline.py:116` `run_pipeline` takes raw sources | Folded. `source_sets.acquire` is the one entry; `run_pipeline` calls it for library callers; C3 calls the same function | 5.2, 16 |
| M12 CLI placement | `C:cli/evidence.py` 792 lines; `C:cli/library/_run_records.py:109` `store_evidence`; `C:cli/library/_export.py` exists; `C:lang/` has no vars module | Folded. Sidecar model in `C:cli/evidence_members.py`; stored via `store_evidence`; export flag in `library/_export.py`; `${var}` in `C:lang/_vars.py` | 16 |
| M13 sizing | E1, E2 overloaded; cloud listing unassigned | Folded. E0 split off E1; E2 split into E2a and E2b; cloud listing in E4; 20 slices, about 39 days | 15 |
| M14 debris versus selector | design rule | Folded. Debris applies per segment below the base; a selector whose literal segment starts with `_` or `.` is refused (`source_set.selector_names_debris`); move the base instead | 5.1, 10 |
| M15 cloud ATs skip | engine S3 tests use `moto` (`ET:tests/connectors/test_object_store.py`) | Folded. S3 and GCS ATs run on fixtures in CI, never skip markers | 10, 17 |
| L1 older stage paths | as H1 | V2-LOG | V2-LOG |
| L2 installer glob | `C:distribution/installer.py:174` | V2-LOG | V2-LOG |
| L3 digest guessability | design | Folded. `members_digest` covers ordinal, size, pin, SHA-256 only; names are bound only by the sidecar digest | 5.7 |
| L4 guard scan shapes | the engine file-access sentry already resolves aliases, `getattr`, bound methods (`ET:tests/sentry/test_file_access_boundary.py:1-8`) | V2-LOG for the new acquisition guard, QA tag | V2-LOG |
| L5 mutation head | design | Folded. Section 18 records the head each mutation ran on | 18 |
| L6 guarantee wording | design | Folded. "During acquisition"; guarantee 2 operations match section 1 and AT-13 | 9, 10 |
| L7 1.1 split | section 7 had no recommendation | Folded as OQ-6 | 7, 8 |
| QA name clash `_members.py` | engine and CLI both planned one | Folded. Engine module is `_member_facts.py`; CLI module is `evidence_members.py` | 16 |

## 1. The problem

Two requests that share one mechanism.

1. **One table, many files.** An export tool writes one table as many objects. Spark and Hive write
   `part-00000-<uuid>.snappy.parquet` files with a `_SUCCESS` marker. Redshift and Athena `UNLOAD`
   write numbered parts under a prefix. AWS DMS writes `LOAD00000001.csv`, `LOAD00000002.csv` per
   table. The customer case in the vault note "Partitioned S3 tables and foreign-key masking" is a
   SQL Server database of hundreds of tables, 50 to 100 million rows each, exported to S3 with each
   table split across several objects. Decoy must treat each set of parts as one table: an order in
   `orders/part-3` must find its customer in `customers/part-7`, and uniqueness, dedupe, shuffle,
   limit and subset must see every row of the table.
2. **Pick input files by pattern.** A nightly CI job reads "today's export" or "every part under this
   prefix". The pipeline file must name the set by a pattern, not by a literal file name that
   changes every night, and the run must record which files it read.

The second request is the selection half of the first: a pattern names a set of parts, and the set
is one table.

## 2. Current state (checked on main, corrected by the Codex review)

- **Sources take one literal locator.** The language has five connectors, each with one locator:
  `csv`, `parquet`, `fixed_width` (`path`), `s3` (`bucket`, `key`), `gcs` (`bucket`, `object`)
  (C:lang/_connectors.py:35-42). For `s3` and `gcs` the compiler infers the format from the key
  suffix (C:lang/_connectors.py:75-94, :104-111), so a prefix ending in `/` needs an explicit
  `format:`. The engine models match: `FileSource.path` (E:config/_sources.py:101),
  `S3Source.key` (E:config/_sources.py:274), `GCSSource.object` (E:config/_sources.py:331). No glob,
  regex, prefix or directory form exists.
- **One descriptor, one reader.** `build_profile_source` dispatches one descriptor to one reader
  (E:profile/_readers.py:520). There are two identity checks: the identity mixin for non-footer
  lazy backends (E:profile/_lazy_identity.py:43-47, :60-94, reason `runtime.lazy_source_changed`)
  and Parquet's own open-handle and footer-fact checks (E:profile/_readers.py:245-257, :279-311).
- **Lazy sources have wide contracts.** There are 36 executable `isinstance(..., LazySource)` checks
  in 23 engine files. The count matters less than the contracts behind it: schema, ordered batches,
  footer facts, access policy and code that hands a physical path to DuckDB or Rust
  (E:execution/_chunked_input.py:150-158). A staged local file keeps every one of these as it is.
- **Cloud full reads are whole-object; the connector streams.** The four cloud `to_frame` paths read
  whole objects into memory (E:profile/_cloud_readers.py:233-270, :285-319, :388-439). CSV also uses
  ranged reads for schema inference and row estimates. The connector `open` methods already stream
  bytes (E:connectors/s3.py:193-202, E:connectors/gcs.py:161-176). The stager uses the stream.
- **Connectors list, but drop the version.** `list(prefix)` exists on S3 (E:connectors/s3.py:152),
  GCS (E:connectors/gcs.py:127) and SFTP (E:connectors/sftp.py:279; one directory, no
  subdirectories). S3 `ListObjectsV2` returns an ETag per key but no `VersionId`; Decoy drops even
  the ETag (E:connectors/s3.py:165-174). GCS list returns a generation; Decoy drops it
  (E:connectors/gcs.py:131-137). `FileMeta` has `path`, `size`, `content_type`, `modified` and is
  exported as **experimental**; the surface inventory tracks it but does not freeze its fields
  (E:sdk.py:1-8, :103-115; engine `docs/frozen-surfaces.md:114-122`).
- **F02 pins a retry, not the first read.** The S3 first GET is unconditional; only a resumed GET
  sends `IfMatch` with the ETag of the first response (E:connectors/s3.py:219-246, F02-E1). F02-E2's
  GCS test pins the generation reloaded at open (F02 plan line 758). Neither ties the read to the
  listing. F03 must send the listed pin on the first GET.
- **F02 names this as a non-goal.** F02 lists "prefix, glob or directory sources" under non-goals
  (F02 plan line 155). F02-E6 lets subset read a remote source through a caller-made local copy, but
  standalone subset preflight still needs Parquet (E:subset/_api.py:351-377,
  E:subset/_preflight.py:109-120).
- **The CLI cannot run a cloud source today.** The execution guard refuses S3 and GCS as sources
  and as targets, including for `decoy.mask()` (C:cli/extras.py:133-155,
  C:cli/run/_execute.py:121, :348-370, :403). CLI-CLOUD (row 64) wires them. So F03 on S3 or GCS
  depends on row 64's source wiring and on an engine release with it.
- **Per-run source staging exists once.** `--duckdb-source TABLE=DB_PATH` (C:cli/run/__init__.py:358)
  stages a DuckDB relation into a temporary Parquet file and runs the normal path
  (C:cli/_duckdb_source.py:1-6). Its transient snapshot turns off library evidence and refuses
  explicit evidence (C:cli/run/_evidence.py:35-38). There are no run variables.
- **The CLI's globs select repo files.** `decoy ci` staged-scan contracts accept `*`, `**` and `?`;
  they refuse `[`, `]`, `{`, `}`, `!`, backslash, empty, absolute, drive-prefixed, parent-segment and
  control-character patterns (C:ci/contracts.py:481-492, C:ci/staged.py:56-92). The installer has
  an internal glob too (C:distribution/installer.py:174). Engine table and column policy globs are a
  different thing (E:config/policy/_selectors.py:51, :134-136).
- **Evidence has one entry per table and skips cloud sources.** `build_manifest` writes
  `input_fingerprints[table]` from `src.get("path")`, so an S3 or GCS descriptor gets no entry
  (C:cli/evidence.py:286-303). That is a gap in the builder today; it only shows once row 64 lets
  cloud sources run. The CLI shape check ignores extra keys (C:cli/evidence.py:126-133, :437-445),
  but the library writer uses an engine model with `extra="forbid"` and a single-file
  `FileFingerprint` (E:records/_payloads.py:46-54, :126-136, E:records/_read_model.py:21-25). The
  verifier hashes a local path (C:cli/evidence.py:507-517, :633-672) and `report diff` compares the
  scalar fingerprint (C:cli/report.py:539-568). A `members` field is therefore a contract change in
  four places, not an additive key.
- **The gate sees remote declarations** and runs static checks, but defers remote column checks to
  the run (C:cli/gate/_layers.py:413-422).
- **Cloud targets.** GCS targets are refused until real-bucket evidence exists
  (C:cli/io/_cloud.py:25). Quarantine and `--chunked` are refused with cloud targets
  (C:cli/io/_cloud.py:104-107). `_cloud.py` computes and checks a delivery root; there is no
  source and target overlap check (C:cli/io/_cloud.py:46-51, :94-107, :187-196).
- **The platform fans files out.** Platform `iteration: files` lists a bucket (P:api/jobs/iteration.py:219),
  sorts (:229-242) and starts one child job per file (:563-574). That is what makes cross-part FK
  references look like orphans. The platform is parked.
- **Row identity.** Ordinary quarantine indexes the output table internally; its serialized row
  has `_source_table`, trigger and reason and no row index (E:quarantine.py:179-198). Declared-casting
  quarantine stores `row_position` in its own envelope (E:declared_casting/_quarantine_protocol.py:71-87).
- **Sampling.** `--sample` always refuses at this head, pending SC2 (C:cli/run/_sample.py:142-149).
  Profiling has seeded random and full modes (E:profile/_walk.py:119-134).
- **An old multi-part Parquet stager exists on a branch.** Engine branch
  `claude/v2-warehouse-sources-and-tokenization-vault` (WAREHOUSE.1) has
  `connectors/parquet_dataset.py`. It sorts parts by default (caller order allowed), refuses any
  difference in fields or schema metadata, writes bounded `iter_batches` and publishes atomically
  (lines 97-114, 128, 139-155). Reference only: it does not list, pin, handle CSV or record evidence.

## 3. Established solutions

Search run: the docs of Spark, Hive, DuckDB, Apache Arrow, Delta Lake, Iceberg, Redshift UNLOAD,
Athena UNLOAD and CTAS, AWS DMS, Snowflake COPY, BigQuery and S3 and GCS listing and transcoding;
the engine branch WAREHOUSE.1; the CLI `decoy ci` glob. Table corrected per Codex F10 to F12.

| Tool | Selection | Part discovery and debris | Schema across parts | Snapshot and evidence |
|---|---|---|---|---|
| Spark file sources ([Parquet](https://spark.apache.org/docs/latest/sql-data-sources-parquet.html), [options](https://spark.apache.org/docs/latest/sql-data-sources-generic-options.html)) | a path or glob; `pathGlobFilter`, `recursiveFileLookup` | partition discovery is automatic for `key=value` directories; `recursiveFileLookup` turns it off; names starting `_` or `.` are skipped, with exceptions for Parquet summary files | from a summary file or one chosen data file unless `mergeSchema=true`; not promised to be the first file | none: the listing at query time is the set; Hadoop committers write `_SUCCESS` |
| Hive ([DDL](https://hive.apache.org/docs/latest/language/languagemanual-ddl/)) | ordinary external table location plus metastore partitions | `MSCK REPAIR TABLE` adds partition directories | table schema in the metastore | no per-file pin |
| DuckDB ([files](https://duckdb.org/docs/stable/data/multiple_files/overview), [hive](https://duckdb.org/docs/current/data/partitioning/hive_partitioning)) | glob with `*`, `**`, `?`, `[...]`, or a file list; `?` has a documented restriction on S3 | hive partitioning can be autodetected; `hive_types` fixes types; a virtual `filename` column exists in recent versions | `union_by_name=true` aligns by name, else by position | none; an empty match is an error by default in current versions |
| pyarrow.dataset ([dataset](https://arrow.apache.org/docs/python/generated/pyarrow.dataset.dataset.html), [factory](https://arrow.apache.org/docs/python/generated/pyarrow.dataset.FileSystemDatasetFactory.html)) | a path or a list of paths; `FileSelector` belongs to the factory | `partitioning="hive"`; ignored prefixes `.` and `_` apply to directory discovery | first fragment unless given; `pa.unify_schemas` on request | none |
| Delta Lake ([protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md)) | the table root | the log lists every data file; deletion vectors can hide rows | in the log | a version pins the set; a raw glob over data files can bring back deleted rows |
| Apache Iceberg ([spec](https://iceberg.apache.org/spec/)) | the table | metadata, manifest list, manifests; delete files | schema ids | a snapshot pins the set; a raw glob ignores delete files |
| Redshift `UNLOAD ... MANIFEST` ([docs](https://docs.aws.amazon.com/redshift/latest/dg/r_UNLOAD.html)) | the manifest | URLs; the verbose form adds sizes and row counts; parts can lack an extension | one schema | binds to the producer's run, but a URL or a length does not pin mutable bytes |
| Athena `UNLOAD`, CTAS ([docs](https://docs.aws.amazon.com/athena/latest/ug/unload.html)) | a prefix | `PARTITIONED BY` writes `key=value` directories; a failed run can leave orphan files | one schema | a manifest in the results location |
| AWS DMS to S3 ([docs](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Target.S3.html)) | `bucketFolder/schema/table/` | full load `LOAD00000001.csv`, numbering can restart per partition folder; CSV headers off by default; CDC files by timestamp; a restart can repeat records | one schema, but DDL changes alter later files | none |
| Snowflake `COPY INTO` ([docs](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table)) | `PATTERN` regex on the full storage location (Snowpipe trims the stage path) or `FILES = (...)` | the pattern only | table schema | load history with age and override rules |
| BigQuery ([tables API](https://docs.cloud.google.com/bigquery/docs/reference/rest/v2/tables)) | several source URIs with wildcards, or a newline-delimited manifest | hive partition options | per table | none |
| S3 and GCS ([ListObjectsV2](https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListObjectsV2.html), [GCS transcoding](https://docs.cloud.google.com/storage/docs/transcoding)) | prefix and delimiter | S3 lists in UTF-8 binary order for general-purpose buckets only; GCS can decompress on read and ignore `Range` | n/a | strong consistency; a multipart ETag is not an MD5 |

What the design takes from this:

- **A listing is not a snapshot.** A run pins the set it read (key, size, ETag or generation) and
  refuses a set that changed. Only a commit marker or a manifest says an export finished, and even a
  marker can be stale (N1).
- **Debris rules are a convention**: skip `_` and `.` names and `_temporary` subtrees. Delta and
  Iceberg roots need their own readers, so a raw glob refuses them (N6).
- **Hive columns change data.** They are strings from paths; any inference is a trap (N12).
- **Schema across parts is strict or explicitly unified.** First slice: strict (D5).
- **Patterns:** glob is the common form, a regex the escape hatch (Snowflake), anchored.
- **Custom code needed:** the record-aware CSV join (D4) and the pin on the first GET (F3). No
  library joins CSV members with header and quote rules while keeping exact bytes, and the F02
  executor already owns the cloud stream. Everything else reuses Arrow, the F02 executor, the
  existing staging writer (`stage_typed_sources`), `ScratchArena` and the existing readers.

## 4. Issues the design must answer

Items 1 to 15 came from the orchestrator, 16 to 27 from the write-up survey, N1 to N17 from the
Codex review. Each line names the slice that closes it (section 15).

1. **Pinned member list** (E2a, E4, C2). Every member: ordinal, size, ETag or generation or local
   file identity, SHA-256 of the bytes consumed. Refuse a member that changed or vanished.
2. **Zero match** (E1). Coded refusal `source_set.no_match`, never an empty table.
3. **Export debris** (E1). Below the base, per path segment: skip `_SUCCESS`, `_committed_*`,
   `_started_*`, `.crc`, segments starting `_` or `.`, `_temporary/` subtrees, and keys ending in
   `/`. Count skips by reason; do not list skipped names (N4). The base itself is literal and never
   filtered. A selector whose literal (wildcard-free) segment starts with `_` or `.` is refused at
   validate with `source_set.selector_names_debris` (M14); a user with `.snap/` puts it in the base.
4. **Empty parts** (E2a, E3). A zero-row Parquet member with the right schema and a header-only CSV
   member are valid members. A zero-byte or malformed matched Parquet member is a refusal, not
   debris. A zero-byte member of a headerless CSV or fixed-width source is valid.
5. **Schema drift** (E2a). Strict equality in F03 (D5, H6 rule in 5.4); widenings are a later
   candidate.
6. **Hive partition columns** (E7). Off by default; see N12.
7. **Output layout** (E8, C6). One output file by default; parts are a separate later pair (D6, D7).
8. **Row identity** (E6). Member ordinal plus row within the member, where the coordinate survives
   (N10).
9. **CSV per-part headers and compression** (E3). Record-aware join (D4); gzip per member.
10. **Incremental runs and cross-run FK.** Out of scope. Keyed strategies still give the same
    masked value across runs under the same key.
11. **`init` and `scan` on a prefix** (C5). One table per selector (N11).
12. **Parallel FK components.** Out of scope (CHUNK-PARALLEL, 1.3).
13. **Pattern grammar** (E0, E9). Glob first; regex after a dependency call (D2).
14. **Run variables** (C4). See D8.
15. **Count guards** (E0 model, E1 checks). `min_files`, `expect_files`, `max_files`.
16. **Commit marker** (E1). `require_marker:`, checked before and after staging, and **not older
    than** any selected member (N1, H5).
17. **Deterministic order** (E1). Sort by the UTF-8 bytes of the relative name; do not trust
    provider order.
18. **Runaway match** (E1 local, E4 cloud). `max_files` plus listing bounds (N4).
19. **Output inside the input prefix** (C1 static, C3 members). Extended to every publication path
    (N14, M10).
20. **One object in two tables** (C3). Refused after listing; local by file identity, cloud by
    provider, bucket and exact key (N3, N14).
21. **Value-free messages** (E0 to E6, C1 to C3). Messages name table and ordinal only (N16).
22. **Output names leak partition values** (E8). Parts named by ordinal only.
23. **Scratch disk** (E2a). `ScratchArena` stage with reclaim (N15), up-front admission plus the
    per-batch budget (N9, M9).
24. **Wrong-kind members** (E1, E3). Refuse by content, not suffix (N6).
25. **Resume** (E6, C3). Bind the snapshot before the first resumable effect (N13).
26. **Sampling bias** (E2b). Profiling runs on the staged file, so it equals the consolidated
    baseline by construction (N11); AT-25 proves it. `--sample` stays refused until SC2.
27. **Evidence size** (C2). Members go to a sidecar bound by digest (N17).

- N1. **Export boundary across tables** (E1, docs). Pinning each object does not stop yesterday's
  parents with today's children. F03 promises only the observed set. The marker must be **not
  older than** every selected member, or the run refuses `source_set.marker_stale` (H5). Equal
  timestamps pass: S3 `LastModified` has one-second resolution and some local file systems one to
  two seconds, and Spark writes `_SUCCESS` right after the commit. For an S3 multipart object
  `LastModified` is the time the upload started, so a late multipart part can look older than the
  marker; the rule catches a reused stale marker, it does not prove the export finished. Docs say
  cross-table consistency needs an immutable export root per run from the producer.
- N2. **Pin and hash the bytes consumed** (E2a, E4). Local: open under the authorized directory
  handle, compare the listed identity with `fstat` of the held handle, hash from that handle, check
  size and identity at the end. Cloud: first GET under the pin, check `Content-Range` and total
  bytes on each retry, hash once before decompression, request the stored bytes on GCS.
- N3. **Path semantics** (E1). Local listing through the rooted file access (held directory, no
  symlink or junction following out of the base, regular files only, non-UTF-8 names refused).
  Matching is case-sensitive on `/`-separated relative names; no Unicode normalization; distinct
  cloud keys stay distinct. Duplicates are checked by file identity locally. A cloud key never
  becomes a scratch path name. A base that the cloud joiner would strip to the bucket root is
  refused.
- N4. **Listing bounds** (E1 local, E4 cloud). Bound entries inspected (`max_listed`, default
  1,000,000), pages, and elapsed time (`source_set.listing_timeout`) apart from `max_files`.
  Stream pages; aggregate skip reasons; refuse an incomplete listing
  (`source_set.listing_incomplete`). Cost fixture with sparse matches reports LIST, HEAD and GET
  counts.
- N5. **Empty versus corrupt** (E1, E3). Order: list, debris filter, match, count checks, validate
  each member's content. An external `column_names_file` is an input dependency, recorded, and never
  a member.
- N6. **Valid files that are not parts** (E1, docs). Refuse a base that holds `_delta_log/` or an
  Iceberg `metadata/` folder (`source_set.table_format_root`). Docs give tested selectors per
  exporter (Spark, DMS full load, Redshift, Athena) and say CDC replay is out of scope.
- N7. **FK and uniqueness per route** (E6, C3). A union table that takes part in a declared FK or a
  uniqueness check is refused on a route that skips that check (today the explicit CLI chunked
  route, C:cli/run/_execute.py:313-326). Parity tests per admitted route (matrix in 10.1).
- N8. **Stage once at a defined point** (E2a, E2b, C3). One acquisition before preflight; every
  later phase uses the staged binding; evidence keeps the logical binding.
- N9. **Residency budget** (E2a). Admission counts the listed bytes of every union table at once
  against free scratch space, using the existing spool-capacity error. Listed sizes undercount
  gzip CSV and re-encoded Parquet, so `stage_typed_sources` also enforces `max_bytes` per batch
  (M9) and the text joiner checks the same budget per member. The subset index limit (`UInt32`,
  E:subset/_inputs.py:86-93) is stated as a limit and refused above it.
- N10. **Row lineage** (E6). Declared-casting quarantine maps `row_position` to member ordinal and
  row through the cumulative row counts recorded at staging. Ordinary quarantine after transforms
  gets no member coordinates in F03 (non-goal, documented).
- N11. **Profiling, sampling, discovery** (E2b, C5). Profiling and seeded sampling run on the staged
  file, so plans match the consolidated baseline (AT-25). `scan` and `init` get grouped input
  syntax.
- N12. **Hive values become data** (E7). Strings only, never inferred; refuse a name that clashes
  with a physical column; percent-decode after matching; a key missing in one member is refused;
  refused for fixed-width; injected columns must be declared like any column.
- N13. **Record identity before any resumable effect** (E6, C3). The ordered snapshot digest and
  parser policy join the F23 resume fingerprint before the first checkpoint.
- N14. **Every publication path is a collision candidate** (C1, C3). Extend the placement check
  (C:cli/io/_placement.py:128-179) to compare inputs with every planned output path: outputs,
  delivery run folders, evidence, vaults, quarantine, scratch. Split by phase in 5.8.
- N15. **Scratch ownership after a kill** (E2a). Use the `ScratchArena` stage; reclaim abandoned
  stages with the existing owner and age checks (E:fileaccess/_reclaim.py:47, :129-159); never
  sweep a live run's stage.
- N16. **Diagnostic and evidence surfaces** (E0 to E6, C2). The shareable manifest, run result,
  reports, notifications, `report diff`, quarantine files and logs carry table, ordinal, count,
  size, pin and digests only. Member relative names go to a private sidecar. A canary in a member
  name and in a cell must not reach `str(exc)`, the exception chain, logs, the manifest or a
  default library export.
- N17. **Sidecar ownership** (C2). Versioned model (5.7), canonical JSON, byte limit, digest in the
  manifest, written before the manifest, stored in the library with the run through
  `store_evidence`, exported only with an explicit flag. Verify checks the digest offline and never
  opens the network.

## 5. Design

### 5.1 How the user names the set: option B

| Option | Form | Verdict |
|---|---|---|
| A. Glob in the existing locator | `parquet("exports/orders/*.parquet")` | rejected: changes literal paths that contain `*`, `?` or `[` |
| **B. Base plus `files:`** | `parquet("exports/orders/", files: "part-*.parquet")`; `s3("bucket", "exports/orders/", format: parquet, files: "**/*.parquet")` | **chosen**: additive, the base is a literal listing root |
| C. Manifest file | `files_from: "manifest.json"` | later candidate (OQ-3) |
| D. Delta or Iceberg | read table metadata | out of scope; refused as a root (N6) |

Rules (D2):

- A selector key makes the source a **union source**. The mode is a typed field on the engine
  model, so it survives local path resolution that strips a trailing `/`.
- `files:` uses the one path-glob grammar (D1) from `path_glob/`: `*`, `**`, `?`; refused: `[`,
  `]`, `{`, `}`, `!`, backslash, empty, absolute, drive prefix, `..` segments, control characters,
  and a literal segment starting `_` or `.` (M14).
- `files_regex:` (slice E9) is a full match on the relative name, compiled with a linear-time
  engine (google-re2), at most 256 characters. It waits for the dependency call (OQ-4).
- Selector-only keys on a single-file source, a selector on a target, and contradictory counts are
  refused at validate. Counts are strict integers (no booleans), 1 to 1,000,000.
- Cloud union sources need `format:`. Local union sources take the format from the connector.
- Optional keys: `min_files`, `expect_files`, `max_files` (default 10,000), `max_listed` (default
  1,000,000), `require_marker: "_SUCCESS"`, `partitions: "hive"` (E7), `compression: "gzip"`
  (CSV and fixed-width).

### 5.2 How the engine reads the set: option Y, one acquisition (D3)

| Option | Verdict |
|---|---|
| X. Fan out child jobs | rejected: the defect itself |
| **Y. Stage and consolidate** | **chosen** |
| Z. Virtual union reader | later optimization, only after a benchmark |

One run-owned **acquisition**, `source_sets.acquire(...)`, turns each union descriptor into an
execution binding: a local descriptor over a staged file in a `ScratchArena` stage, the ordered
member facts, and a cleanup lifetime. It is a context manager and the only entry point (M11).
`run_pipeline` (E:execution/_pipeline.py:116) calls it for library callers (`decoy.mask()`, the
SDK) when a config holds a union source and no staged binding was passed; the CLI (C3) calls the
same function before preflight and hands the staged binding to `run_pipeline`, which then does not
acquire again. It runs once, before preflight. Declarations, capacity, profile, native admission,
subset and execution all receive the execution binding; evidence receives the logical binding plus
member facts (N8). Single-file sources do not pass through it and keep today's route.

- **Parquet (D5, H1).** Read every pinned footer first (ranged reads on cloud) and apply the schema
  rule (5.4). Then stage through the existing writer, `stage_typed_sources`
  (E:declared_casting/_stream.py:101), with: `root` the run's `ScratchArena`; `stem="union"`;
  `open_fn` a pinned member reader that yields each member's record batches in ordinal order under
  its pin and hashes the stored bytes as it reads; an identity `batch_fn`; `empty_fn` the typed
  empty table from the agreed footer schema; `max_bytes` the scratch budget. `stage_typed_sources`
  streams only `LazySource` values, so the acquisition passes a small `LazySource` per union table
  whose only reader is `open_fn` (its own `iter_batches` refuses). No new parameter is added to
  `stage_typed_sources` (10 already; Dennis QA note). `source_sets/_acquire.py` joins `CALLERS` in
  `ET:tests/sentry/test_staging_writer_choke_point.py`.
- **CSV (D4).** A second, separate writer kind: the record joiner `source_sets/_join_text.py`
  (`join_text_members`) writes bytes into the same arena with the arena's private create. It parses
  each member with the existing dialect and encoding rules, finds the end of the header record (a
  quoted header can span lines), compares decoded header fields, and refuses a difference. It
  copies data records as exact bytes, strips a member's BOM, refuses a member that ends inside a
  quoted field, and adds the first member's terminator when a member lacks a final one. Headerless
  sources (`header: false` or `column_names_file`) copy every record. It checks the scratch budget
  after each member. Cloud CSV unions take only the options the cloud model has; adding the local
  dialect fields to cloud models is a non-goal. It has its own guard (16).
- **Fixed-width.** Same joiner. No header. Copy records, check record length and terminator per
  member.
- **Pins and hashes (N2, F3).** Each member is read under its pin from the first byte; its SHA-256
  is computed on the stored bytes in the same pass; its identity is checked again at the end.
- **Disk (N9, M9).** Before staging, admission sums the listed sizes of all union tables and
  refuses with the existing spool-capacity error when scratch space is short. During staging the
  per-batch `max_bytes` check (and the joiner's per-member check) catches growth the listing cannot
  predict (gzip, re-encoded Parquet).

### 5.3 Where it lives

- **Engine**: glob grammar (`path_glob/`), selector model, listing, pins, acquisition, staging
  through the existing writer, text joiner, schema rule, member facts in the run result,
  quarantine mapping, resume binding, records model change, later hive columns and output parts.
- **CLI**: language keys, validate and gate checks, CI glob migration to the engine API, placement
  collision checks, run wiring and route refusal, evidence sidecar, verify, report diff, `--var`,
  `scan` and `init`.

### 5.4 Schema rule (H6)

F03 ships strict equality (D5) on what describes the data, and ignores what describes one file:

- Compared: Arrow fields (names, order, types, nullability, nested fields, dictionary types, field
  metadata) and, when present, the pandas metadata `columns` entries (name, field name, pandas
  type, numpy type, per-column metadata).
- Ignored: the pandas `index_columns` range entries' `start`, `stop` and `step`, and the
  `creator` and `pandas_version` keys. A stored (non-range) index is a physical field and is
  compared as one.
- The staged file carries the agreed Arrow schema with the `pandas` schema metadata key dropped, so
  a reader never sees a RangeIndex that does not match the staged row count. The oracle in AT-13
  drops the same key.

A later candidate may add order-independent widening (int sizes, float sizes, large string and
binary, nullability), decided from all footers before the writer opens. Any difference is
`source_set.member_schema_mismatch` naming the member ordinal and column.

### 5.5 Output layout (slices E8 and C6, separable)

- Default: one output file, as today. A union source with a directory target is refused until
  `parts:` or `rows_per_part:` is given (OQ-1).
- `parts: "mirror"` splits **output row positions** at the input member boundaries. It is allowed
  only when every operation on the table keeps row count and order: mask and column shuffle. It is
  refused with `target.parts_mirror_drops_rows` for `where`, `sort`, subset, dedupe, limit,
  quarantine and generated tables (D6). The final count is checked before publication.
- `rows_per_part: N` writes parts of N rows. Mutually exclusive with `parts:`.
- Parts are `part-NNNNN.<ext>` by ordinal; input names never reach output names.
- Publication (D7): write a fresh generation folder with a complete part manifest, then publish it
  in one step (local rename of the generation pointer, or a conditional cloud pointer write). Vault
  before output stays. No deletion of foreign files. Ledger, evidence, verify and resume cover
  every part.

### 5.6 Run variables (slice C4, D8)

`decoy run --var name=value`, split at the first `=`. Names match `[a-z][a-z0-9_]{0,31}`; a repeated
name is refused. Values match `[A-Za-z0-9_-][A-Za-z0-9._=-]{0,127}` (no leading `.`, so `.` and
`..` are impossible, no `/`, no glob characters). Both patterns are full matches with
`re.fullmatch` and `\Z` semantics, so a trailing newline is refused (recurring defect 1).
`${var.name}` expands once, only in a locator and in `files:`, never in endpoint, credential or
regex fields. `$${` writes a literal `${`. The complete resolved locator is validated before any
I/O, including Windows reserved names. `decoy validate` checks syntax and positions;
`decoy validate --var ...` also checks the resolved form. A missing variable is `run.var_missing`;
an unused one is `run.var_unused`, scoped per pipeline under `--all`. Evidence records names and
SHA-256 digests of values, not raw values. All of this, including the `${var.name}` syntax, lands
in C4; before C4 a `${` in a locator is an ordinary character and C1 does not parse it (H3c).

### 5.7 Evidence and sidecar (slice C2, H4, L3)

- The manifest version moves from `cli-local-1` to **`cli-local-1.1`** (a minor bump: a superset).
  The CLI writes `cli-local-1.1` for every run after C2. The CLI verifier, `report diff` and the
  engine records model accept `cli-local-1` and `cli-local-1.1`. Older readers refuse `1.1` cleanly
  because they match the version exactly (C:cli/evidence.py:459-460; the engine model is
  `Literal["cli-local-1"]`).
- `input_fingerprints[table]` becomes a union discriminated by `fingerprint_method`: the existing
  `FileFingerprint` (`"full"` or `None`), `MemberSetFingerprint` (`"member_set"`: `base`,
  `members_count`, `members_digest`, `sidecar_digest`) and `ObjectFingerprint` (`"object_pin"`:
  cloud single object, provider, bucket, key, pin, size, SHA-256). Each model is strict
  (`extra="forbid"`, strict types). Free text in `fingerprint_method` is refused.
- `members_digest` is SHA-256 over canonical JSON of `[ordinal, size, pin, sha256]` per member.
  It holds no names, so a short list of partition values cannot be tested against it (L3). Names
  are bound only by `sidecar_digest`, the SHA-256 of the canonical sidecar bytes.
- Sidecar: `schema_version: "decoy-members-1"`, one pydantic writer model (`MemberSidecar`) in
  `C:cli/evidence_members.py`; the reader is `MemberSidecar.model_validate_json` on the same model.
  Per member: `ordinal`, `name`, `size`, `etag` or `generation` or local identity, `sha256`, `rows`.
  Byte limit 8 MiB, enough for the 10,000 `max_files` default with names up to 512 bytes.
  Tests: a `decoy-members-2` sidecar, a missing tag and an unknown method value are each refused
  with a coded error.
- Stored with the run through `store_evidence` (C:cli/library/_run_records.py:109); the library
  export leaves it out unless `--include-member-names` is given (C:cli/library/_export.py).

### 5.8 Placement checks by phase (M10)

- **Validate (no I/O):** a target, evidence, vault, quarantine or scratch path under a union base
  whose relative remainder matches the selector; a selector on a target; two sources with the same
  base and overlapping selectors. Static only.
- **After listing, before staging (C3):** member collisions with every planned publication path,
  one member in two tables (file identity locally, including hard links and case aliases on a
  case-insensitive file system; provider, bucket and exact key on cloud). Refused before any member
  byte is read.

## 6. Combined with S3 and GCS sources

- Depends on row 64 CLI-CLOUD wiring cloud sources through the CLI guard (F1).
- Listing uses `list(prefix)` with the base as the prefix, page by page, under `max_listed`, the
  page bound and the time bound (E4). `FileMeta` gains optional `etag` and `generation` fields
  filled from the listing (no extra HEAD per object, no extra permission). It is experimental, so
  the change is additive and recorded in the surface inventory with F02.
- The first GET of each member sends the pin: S3 `IfMatch` with the listed ETag; GCS `generation`
  with `ifGenerationMatch`. Retries reuse it. A failed precondition is `source_set.member_changed`.
  Versioned and unversioned S3 buckets behave the same way, because the ETag is always present.
- GCS needs F02-E2 for the generation plumbing (slice E5 after F02-E2). S3 and local go first.
- GCS downloads ask for the stored bytes so transcoding cannot change the hash (N2).
- Every cloud source, single object or set, gets a pinned evidence entry (C2).
- GCS targets stay refused until CLI-CLOUD's real-bucket run.

## 7. Slotting in 1.x

- Row F03 in 1.1 beside 64 CLI-CLOUD; 87 F02 moved from 1.4 to 1.1 (owner 2026-11-24: first in 1.x
  with cloud sources; V1 stays small local files). Alternative if the owner reads it differently:
  only F02-E2 moves to 1.1.
- F03 is 20 slices, about 39 builder-days (section 15). With 87 at about 9 slices, 1.1 grows to
  about 59 slices. The first cut works on local files alone and adds S3 when row 64 merges, so the
  owner question OQ-6 recommends splitting 1.1 into a local file-sources part and a cloud part.
- The WAREHOUSE.1 multi-part Parquet reader is replaced by F03 staging.

## 8. Open questions for the owner

- OQ-1. Default for a union source with a directory target: refuse until `parts:` or
  `rows_per_part:` is given (recommended), or mirror by default.
- OQ-2. `max_files` default 10,000 and `max_listed` default 1,000,000: right for the SQL Server
  case? Recommended: yes.
- OQ-3. Manifest input (option C) in 1.x after F03, or wait for a customer ask? Recommended: wait.
- OQ-4. `files_regex:` needs a linear-time regex engine. Add `google-re2` (wheels for Linux, macOS,
  Windows) as a dependency, or ship glob only? Recommended: glob only in the first cut; E9 after the
  dependency call.
- OQ-5. Member names in a private sidecar, not in the shareable manifest (N16). Recommended: yes.
- OQ-6. How to slot 1.1 (L7): one 1.1 with F03, row 64 and F02 together; or split into **1.1a
  local file sources** (F03 first cut on local files: E0 to E3, E6, E-rel1, C1, C3, C2, D1) and
  **1.1b cloud** (row 64, F02 with F02-E2, F03 E4 and E5, the S3 and GCS cells of the ATs). The
  first cut's S3 part depends on row 64 either way. Recommended: split, so local unions ship
  without waiting on cloud wiring.

## 9. Pinned guarantee and non-goals

Guarantee. For a source declared with a base and a selector, on local files and on S3 (GCS after
F02-E2):

1. The run reads exactly the members selected from one listing, in UTF-8 byte order of their
   relative names, each under its pin, and refuses when any member changes, vanishes or fails
   validation **during acquisition** (L6). After acquisition the run reads only the staged file.
2. Masking, FK handling, uniqueness checks, dedupe, column shuffle, limit, subset and profiling
   give the same result as the same run on one file that holds every member's records in that
   order (L6; matches section 1 and AT-13).
3. Evidence binds the run to the ordered member set (ordinal, size, pin, SHA-256), and messages,
   exception chains, logs and the shareable manifest hold no member name or data value.
4. The scratch stage is private to the run and removed on every exit path a process can run;
   abandoned stages are reclaimed by the next run.

Non-goals: cross-table export consistency without a producer contract (N1); incremental runs and
cross-run FK; Delta, Iceberg, CDC replay; schema widening across members; a virtual union reader;
member coordinates for ordinary quarantine after transforms; cloud CSV dialect fields; SFTP union
sources; parallel FK components; the platform.

## 10. Acceptance tests (hostile corpus, red first)

**Red first, on the assertion (M8).** Every AT fails on the base simply because `files:` is an
unknown key, which proves nothing. So each AT must also fail on its own assertion against the
slice's scaffolding: the builder first lands a scaffold stager that reads only the first member
(the class 5 mutation) and a scaffold listing that does not filter debris, runs the ATs, and
records that each one fails on its named assertion, not on config parsing. The gate checks that
record.

"Oracle" means the same pipeline run on one consolidated file built by the test from the members
in sorted order (plain Arrow concat for Parquet, with the `pandas` key dropped; byte
concatenation of records for CSV).

**Cloud cells (M15).** The S3 cells run against `moto` in CI and the GCS cells against the engine's
GCS fake (as `ET:tests/connectors/test_gcs.py` does). No cloud cell carries a skip marker. The CLI's S3
cells are written in C3 once row 64 is merged (or in a follow-up slice if C3 lands first), never as
skipped tests.

| # | Test | Expected |
|---|---|---|
| AT-1 | Cross-part FK: `orders` parts reference `customers` rows that live only in other parts | no orphans; masked FK values equal the oracle, on every route in 10.1 |
| AT-2 | Composite key across parts, and a self-referencing `employees.manager_id` whose parent is in a later part | equal to the oracle on every route in 10.1 |
| AT-3 | Duplicate parent keys in two parts, and a genuine orphan | the same duplicate and orphan findings and policy outcome as the oracle, on every route in 10.1 |
| AT-4 | Masked uniqueness collision across a member boundary | detected as on the oracle, on every route in 10.1 |
| AT-5 | Schema mismatch: type, column order, nullability, nested field, field metadata, pandas column entry, in either member order; plus two pandas-written parts with different row counts (different RangeIndex `stop`) | mismatches: `source_set.member_schema_mismatch` naming ordinal and column, both orders; the two pandas parts are valid and the staged file has no `pandas` key |
| AT-6 | Member changed between list and read (local rewrite, S3 overwrite, GCS new generation), and a vanished member | `source_set.member_changed` or `source_set.member_missing`; no output |
| AT-7 | Zero match; match below `min_files`; not equal `expect_files`; above `max_files`; listing above `max_listed` with ten matches (local and S3) | coded refusal each, listing stops at the bound |
| AT-8 | Debris: `_SUCCESS`, `.crc`, `_temporary/` subtree, hidden file, `/`-terminated key; selector `".snap/*.csv"` | skipped, counted by reason, no names in output; the selector is refused with `source_set.selector_names_debris` at validate |
| AT-9 | Missing marker; a marker older than a member (late part, reused marker); a marker with the same timestamp as the newest member | `source_set.marker_missing`; `source_set.marker_stale`; the equal-timestamp case passes |
| AT-10 | Zero-byte Parquet member; header-only CSV member; zero-row Parquet member; all members zero rows | refusal; valid; valid; empty table recorded |
| AT-11 | CSV: headerless members; quoted header spanning lines; BOM on one member; member without final newline; CRLF and LF mixed; member ending inside a quote; gzip members | staged data equals the oracle records byte for byte; the open quote is refused |
| AT-12 | Bounded memory: 200 members, 2M rows, peak RSS under 1.5x the single-file run on the oracle | holds; scratch peak about table size plus one member |
| AT-13 | Equivalence: CSV output byte-equal to the oracle run; Parquet output equal in schema, rows, order and seeded masked values | holds for mask, column shuffle, subset, dedupe and limit, on every route in 10.1 |
| AT-14 | Evidence lists every member: ordinal, size, pin, SHA-256 in sidecar order; digests in manifest; verify re-hashes local members; report diff shows member changes; `cli-local-1` manifest still verifies; `decoy-members-2`, missing tag, unknown method refused | holds; tampered sidecar fails verify |
| AT-15 | Value-free canary in a member name, a partition value and a cell, through parser, gzip, schema, pyarrow and botocore errors | canary absent from `str(exc)`, logs, stdout, `--json`, notifications, `report diff` output, quarantine files, manifest, run result and the default library export; the default export holds no sidecar; every `source_set.*` error has `__cause__` and `__context__` equal to None (recurring defect 3) |
| AT-16 | Static: target, evidence, vault or quarantine path under a source base and matching the selector. After listing: a member that is also a planned output; one object matched by two tables (also via hard link and case alias on a case-insensitive file system) | static cases refused at validate with no I/O; member cases refused after listing with no member byte read and no stage created |
| AT-17 | Explicit `--chunked` with a union table in a declared FK | refused, not run without the check |
| AT-18 | Kill the run during staging, start a second run | first stage reclaimed, live stages of a parallel run untouched |
| AT-19 | Resume after interruption with an extra member added | refused with the resume mismatch code |
| AT-20 | Delta `_delta_log/` or Iceberg `metadata/` under the base | `source_set.table_format_root` |
| AT-21 | Symlink or junction out of the base, special file, non-UTF-8 name | refused |
| AT-22 | `--var` with `..`, `/`, a glob character, a repeated name, an unused name, a trailing newline in the name and in the value; `$${` literal | refused or literal as specified; the trailing-newline cases are refused |
| AT-23 | Cost: S3 fixture of 50,000 keys with 10 matches | one listing pass, 10 footer reads, 10 GETs, no per-key HEAD |
| AT-24 | FK shapes not covered above: null child keys across members; single-file parent with union child; union parent with single-file child | equal to the oracle on every route in 10.1 |
| AT-25 | Profiling: the profile plan (full mode, and seeded random mode with a fixed seed) on a union table | equal to the profile plan on the oracle file |
| AT-26 | Exit paths: (a) listing refusal; (b) injected failure after staging, during execution; (c) success; (d) listing over the time bound; (e) a listing page error mid-listing (local `scandir` error, S3 page error) | (a) no stage created (scratch root unchanged); (b) and (c) stage released; (d) `source_set.listing_timeout`; (e) `source_set.listing_incomplete`, no stage |

### 10.1 Route-by-test matrix (H7)

Routes from section 12. "N" cells need the native companion and run in the companion venv
(`venv-native-lock`); the gate venvs skip `NEEDS_COMPANION` tests, so the gate records that every
N cell ran and none was skipped. "R" means the route refuses the case and the AT asserts the
refusal code.

| AT | Full frame | Stream | Native companion | Out-of-core FK | Engine chunked FK | CLI `--chunked` | Subset stage | Standalone subset |
|---|---|---|---|---|---|---|---|---|
| AT-1 | yes | yes | N | yes | yes (single-column) | R | yes | yes (Parquet) |
| AT-2 | yes | yes | N | yes | same outcome as one file (composite is outside its single-column limit) | R | yes | yes (Parquet) |
| AT-3 | yes | yes | N | yes | yes | R | yes | n/a |
| AT-4 | yes | yes | N | yes | n/a | R (uniqueness) | n/a | n/a |
| AT-13 | yes | yes | N | yes | yes | yes when no FK or uniqueness on the table, else R | yes | yes (Parquet) |
| AT-24 | yes | yes | N | yes | yes (single-column) | R | yes | yes (Parquet) |

Standalone subset admits a union table on the same terms as one file of that format: its preflight
needs Parquet (E:subset/_api.py:351-377), so a CSV union is refused there as a single CSV file is.

## 11. Defect classes

| # | Class | Closing structure | Sentry or property test | Mutation that must turn it red |
|---|---|---|---|---|
| 1 | Value-bearing output | member names only in the private sidecar; every `source_set.*` message built from the reason catalog with table and ordinal fields only; errors raised `from None` | AT-15 canary test plus a reason-catalog test that no `source_set.*` template takes a name or value field | add the relative name to the `member_changed` message; raise `member_changed` `from exc` |
| 2 | Cleanup missing on an exit path | the acquisition is a context manager that owns the `ScratchArena` stage; reclaim for kills | AT-18, AT-26, and a test that raises at every staging step and checks the stage is gone | remove the `finally` release in the acquisition |
| 3 | State machine and concurrency | stage names carry the run id; reclaim checks owner and age; the publish of parts is one pointer step | AT-18 two-run test; E8 test that a failed part write leaves the old generation current | reclaim without the owner check |
| 4 | Route parity and silent fallback | one acquisition before preflight; the route table refuses a union table on routes that skip FK checks | the 10.1 matrix, AT-17; sentry that only the acquisition builds a union execution binding | let the chunked route accept a union table with FK |
| 5 | Referential integrity | consolidation gives FK code one table, so cross-part parents are visible | AT-1 to AT-4, AT-24 against the oracle | stage only the first member |
| 6 | Untrusted producer | content checks per member: schema, header, quote state, magic bytes; marker freshness; table-format root refusal | AT-5, AT-9, AT-10, AT-11, AT-20 | accept a member by suffix without the magic-byte check |
| 7 | TOCTOU (check then use) | hash and read from the held handle; first GET under the listed pin; identity check at the end | AT-6 with a rewrite between list and open and between open and end | open the member by path again after the identity check |
| 8 | Weak tests and overclaimed evidence | equivalence against a test-built oracle, not against the code's own staging; evidence digests checked by verify; red-first on the assertion (M8) | AT-13 with the oracle built by plain Arrow concat; AT-14 tamper test | build the oracle with the stager itself |
| 9 | Behavior-preserving refactor drift | the CI glob moves to the engine API with a parity corpus of every current CI contract pattern | parity test over the CI contract fixtures, old and new matcher | change `**` to match zero segments differently |
| 10 | Frozen contract drift | evidence `cli-local-1.1` with readers for both versions; versioned sidecar; additive source keys; language freeze file updated in the same slice | `test_language_freeze.py`, frozen-surface sentry, legacy `cli-local-1` fixture test, sidecar version tests | drop `FileFingerprint` single-file support; accept an unknown sidecar version |
| 11 | Second writer (H1) | Parquet staging only through `stage_typed_sources`; text staging only through `join_text_members` | `ET:tests/sentry/test_staging_writer_choke_point.py` with `source_sets/_acquire.py` in `CALLERS`; new text joiner guard (16) | open a `ParquetWriter` in `_acquire.py`; add a second byte write outside `join_text_members` |

## 12. Enumerations

### Exit paths of a union run

- Validate refusal (selector, counts, var, static placement): no I/O, exit code for config errors.
- Listing refusal (no match, counts, bounds, time bound, incomplete listing, marker, table-format
  root, member placement collisions): no stage created. AT-7, AT-9, AT-16, AT-20, AT-26 (a, d, e).
- Staging refusal (schema, header, quote, changed, missing, disk): stage released by the
  acquisition. AT-5, AT-6, AT-11, and the raise-at-every-step test.
- Execution failure after staging: stage released by the acquisition (E:fileaccess/_scratch.py:340).
  AT-26 (b).
- Kill or power loss: stage left; reclaimed by the next run (E:fileaccess/_reclaim.py:129). AT-18.
- Success: evidence and sidecar written, then stage released. AT-26 (c).

### Routes a union table can take

See the matrix in 10.1.

- Full frame and stream: admitted.
- Native companion: admitted on the staged file path (E:execution/_chunked_input.py:150).
- Out-of-core FK: admitted; last-write-wins duplicates follow global row order, which is the staged
  order (E:execution/out_of_core/_relation.py:348).
- Engine chunked FK: admitted within its existing single-column limits
  (E:execution/_chunked_fk_edge_checks.py:418).
- Explicit CLI `--chunked`: refused when the union table is in a declared FK or uniqueness check
  (C:cli/run/_execute.py:313).
- Subset stage: admitted on the staged file (E:execution/pipeline/_subset_stage.py:149).
- Standalone subset: admitted on the same terms as one file of that format.

### FK shapes

- Single-column parent and child in different members (AT-1).
- Composite key across members (AT-2).
- Self-reference with the parent in a later member (AT-2).
- Duplicate parent keys in two members, last-write-wins by staged order (AT-3).
- Genuine orphan (AT-3), and null child keys (AT-24).
- Parent table single-file, child table union, and the reverse (AT-24).

### Fields added

- Engine source models (E:config/_sources.py:101, :274, :331): `files`, `files_regex` (E9),
  `min_files`, `expect_files`, `max_files`, `max_listed`, `require_marker`, `partitions` (E7),
  `compression`.
- `FileMeta` (E:sdk.py:104): `etag`, `generation`, both optional.
- Run result: per table `members_count`, `members_digest`, `staged_bytes`.
- Engine records model and CLI manifest (C:cli/evidence.py:286): version `cli-local-1.1`;
  `input_fingerprints[table]` is a discriminated union of `FileFingerprint`,
  `MemberSetFingerprint` and `ObjectFingerprint` (5.7).
- Sidecar `decoy-members-1`: per member `ordinal`, `name`, `size`, `etag` or `generation` or local
  identity, `sha256`, `rows`.
- Target models (E8): `parts`, `rows_per_part`.
- Run options: `--var` (C4); library export option `--include-member-names` (C2).

### Output surfaces

- stdout and the `--json` envelope: counts and codes only.
- Logs and notifications: table, ordinal, counts.
- Exception chains: `source_set.*` errors carry no `__cause__` or `__context__`.
- Run result document (C:cli/run/_result.py): member counts and digests.
- Evidence manifest: digests and counts; sidecar: names (private).
- `report diff`: member counts, ordinals and digest changes, no names.
- Library store and export: sidecar stored with the run; the default export leaves it out.
- Quarantine files: declared-casting member mapping (E:declared_casting/_quarantine_protocol.py:71),
  ordinals only.
- Output parts (E8): ordinal names only.

## 13. Reuse inventory

| Need | Reused | Where |
|---|---|---|
| Path glob grammar | the `decoy ci` grammar, moved to the engine `path_glob/` | C:ci/contracts.py:481-492, C:ci/staged.py:56-92 |
| Local listing and safe open | rooted file access with a held directory | E:fileaccess/_rooted.py:197-219 |
| Cloud listing and streaming | connector `list` and `open`, F02 executor | E:connectors/s3.py:152, E:connectors/object_store.py:141-176 |
| Parquet staging writer (H1) | `stage_typed_sources` with `open_fn`, identity `batch_fn`, `max_bytes` | E:declared_casting/_stream.py:101 |
| Scratch stage | `ScratchArena` and reclaim | E:fileaccess/_scratch.py:184, E:fileaccess/_reclaim.py:47 |
| Per-batch disk budget | `check_temp_disk_budget` (inside `stage_typed_sources`) | E:execution/out_of_core/_budget.py:523 |
| CSV dialect and header rules | the one CSV parser | E:profile/_csv_reader.py:84-113 |
| Disk refusal | spool-capacity error | E:execution/out_of_core/_budget.py |
| Reason codes | reason registry, new `source_set` catalog | E:reasons/_registry.py |
| Placement collisions | CLI placement check | C:cli/io/_placement.py:128-179 |
| Evidence store | `store_evidence` (single-caller sentry) | C:cli/library/_run_records.py:109 |
| Library export | export module | C:cli/library/_export.py |
| Resume binding | F23 fingerprint | E:delivery/resume/_fingerprint.py:66-72 |
| Atomic multi-file publish (E8) | batch publish | C:_atomic_batch.py:62-92 |

New code only where nothing exists: the text record joiner (D4) and the pin on the first GET (F3).

## 14. Frozen contracts

- `FileMeta` (experimental SDK export): additive optional fields; surface inventory updated with F02.
- New public engine API for the path glob (`decoy_engine.sdk`, experimental, re-exported from
  `path_glob`): `validate_path_glob`, `match_path_glob`.
- Source config models: additive keys; selector mode refuses on targets.
- `.decoy` grammar: new connector options; `tests/fixtures/release_freeze/lang-surface.json`
  updated in C1 with the freeze test, and again in C4 for `${var}`.
- Evidence: **minor bump to `cli-local-1.1`** (H4; this replaces R2's "version stays"). Readers
  accept `1` and `1.1`; older readers refuse `1.1` by exact match; the legacy `cli-local-1`
  fixture is kept. Sidecar versioned `decoy-members-1`.
- Run result: additive fields.
- Reason codes: new `source_set.*` and `run.var_*` codes in the catalogs; `target.parts_*` in E8.
- F23 resume fingerprint: gains the snapshot digest; an older checkpoint without it cannot resume a
  union table (refused, not guessed).

## 15. Slices

Builder-days are for one builder. Risk tier per slice. "Rev" is the review set: two reviewers
(Codex then Dennis) for risky slices, Codex only for low risk.

| Slice | Repo | What | Depends on | Builder-days | Risk | Rev |
|---|---|---|---|---|---|---|
| E0 | engine | `path_glob/` pure grammar package (bottom tier) with `validate_path_glob`, `match_path_glob` and SDK re-export; typed selector fields and count rules on the source models; `source_set` reason catalog; `.importlinter` and layout snapshot for `path_glob` and `source_sets`; selector debris-segment refusal | none | 1.5 | R2 | two |
| E1 | engine | local selection in `source_sets/`: listing via rooted access, file-access registry entries, per-segment debris, sort, counts, local listing bounds and time bound, incomplete listing, marker "not older than", table-format root refusal; AT-7 (local), AT-8, AT-9, AT-20, AT-21, AT-26 (a, d, e local) | E0 | 2 | R2 | two |
| E2a | engine | acquisition and Parquet staging: `acquire` context manager, `ScratchArena` stage and reclaim, pinned member `open_fn` through `stage_typed_sources` (sentry `CALLERS` updated), held-handle hash, all footers then the 5.4 schema rule, admission plus `max_bytes`, member facts in the run result, records model widening, `run_pipeline` ownership; AT-5, AT-6 (local), AT-10 (Parquet), AT-12, AT-18, AT-26 (b, c) | E1 | 2.5 | R2 | two |
| E2b | engine | phase binding: preflight, capacity, profile, native admission, subset and execution use the staged binding; route matrix cells for every admitted engine route; AT-1 to AT-4, AT-13 (Parquet), AT-24, AT-25 | E2a | 2 | R2 | two |
| E3 | engine | CSV and fixed-width record joiner `join_text_members` and its guard, gzip, empty versus corrupt, `column_names_file` binding, per-member budget; AT-10, AT-11, AT-13 (CSV) | E2a | 2.5 | R2 | two |
| E4 | engine | S3: paged listing under `max_listed`, page and time bounds, incomplete listing; `FileMeta.etag` from listing; first GET under `IfMatch`; range and total checks; cost fixture on `moto`; AT-6 (S3), AT-7 (S3), AT-23, AT-26 (e S3) | E2a, F02-E1 (merged) | 2.5 | R2 | two |
| E6 | engine | route refusal (`plan/checks/_union_routes.py`), declared-casting quarantine member mapping, resume snapshot binding; AT-17 (engine part), AT-19 | E2b | 2.5 | R2 | two |
| E-rel1 | engine | release and repin (checklist) | E0 to E4, E6 | 0.5 | R1 | one |
| C1 | CLI | language keys and `format:` for cloud unions, validate and gate checks, CI glob on the engine API with parity corpus, static placement checks; AT-16 (static part). No `${var}` | E-rel1 | 2.5 | R2 | two |
| C3 | CLI | run wiring: `source_sets.acquire` before preflight, member placement collisions after listing, native gate on the staged binding, `--chunked` refusal, resume identity before the first checkpoint, evidence refused for union tables (as `--duckdb-source`) until C2; AT-16 (member part), AT-17, AT-19 end to end; CLI cells of the 10.1 matrix | C1; row 64 source wiring for the S3 cells | 2.5 | R2 | two |
| C2 | CLI | evidence `cli-local-1.1`: discriminated fingerprints, `evidence_members.py` sidecar model, `store_evidence`, export flag, verify, report diff, cloud single-object entries; lifts the C3 evidence refusal; AT-14, AT-15 | C3 | 3 | R2 | two |
| D1 | CLI | docs: union sources guide, exporter selectors (Spark, DMS, Redshift, Athena), limits, marker semantics, cross-table consistency note | C2 | 1 | R0 | one |
| C4 | CLI | `--var` complete: `${var.name}` syntax in `lang/_vars.py`, expansion, resolved-locator validation, digests in evidence, freeze file, its own docs; AT-22 | C2 | 2 | R2 | two |
| C5 | CLI | `scan` and `init` grouped input over a selector | C3 | 2 | R1 | one |
| E5 | engine | GCS: paged listing with bounds, generation from listing, first read under the generation, stored-bytes download; AT-6 (GCS), AT-7 (GCS) | F02-E2 | 1.5 | R2 | two |
| E7 | engine | hive partition columns (strings, clash and missing-key refusal, not for fixed-width) | E3 | 1.5 | R2 | two |
| E9 | engine | `files_regex:` on google-re2 | OQ-4, E0 | 1 | R1 | one |
| E8 | engine | output parts: `parts: "mirror"`, `rows_per_part`, eligibility, generation publish | E-rel1 | 3 | R2 | two |
| E-rel2 | engine | release and repin for E5, E7, E8, E9 | those slices | 0.5 | R1 | one |
| C6 | CLI | parts delivery: generation folder, pointer publish local and S3, ledger, evidence, verify, resume over parts | E8, E-rel2 | 2.5 | R2 | two |

Total: 20 slices, about 39 builder-days (engine 23.5 across 13 slices, CLI 15.5 across 7
including D1). Dennis estimated 38 to 42.

**First cut** (about 25 builder-days): E0, E1, E2a, E2b, E3, E4, E6, E-rel1, C1, C3, C2, D1.
It ships local unions on its own, plus S3 when row 64 is merged (H3d; E4 is engine-only, so the
CLI's S3 path needs row 64). Merge order keeps every merge clean (H3): C3 refuses evidence for
union tables, so a union run between C3 and C2 never reaches `build_manifest` with a base
directory (H3a); D1 waits only for C2 (H3b); no `${var}` parsing exists before C4 (H3c).

Then C4 and C5 (4 days). Then E5 after F02-E2, E7, E9 after OQ-4, E8, E-rel2, C6 (10 days).

## 16. Design notes, choke points and placement

Design notes. Principles that apply: one place per fact (the acquisition owns the member list;
nothing else lists), one writer per kind (H1), dependency direction (the CLI imports the engine
grammar, never the reverse; `config` reaches only the pure grammar), typed context objects (the
acquisition returns one `StagedSource` value, not a tuple). Established pattern: stage then run,
as `--duckdb-source` and the subset stage do; pin on read, as S3 `IfMatch` and GCS
`ifGenerationMatch` do.

**Choke point 1, acquisition.** Rule: "a union source is listed, pinned and staged exactly once,
by the acquisition". Enforced by construction: only `source_sets.acquire` can turn a descriptor
with a selector into a readable binding; `build_profile_source` refuses a selector descriptor
(E:profile/_readers.py:520). Guard: `ET:tests/sentry/source_config/test_union_acquisition_choke_point.py`
checks that no module outside `source_sets/` calls connector `list` for a source and that
`build_profile_source` refuses a selector. Mutation: let `build_profile_source` read the first
matching member; the guard turns red.

**Choke point 2, Parquet staging writer (H1).** The existing rule and guard: Parquet staging goes
through `stage_typed_sources`; `ET:tests/sentry/test_staging_writer_choke_point.py` gains
`source_sets/_acquire.py` in `CALLERS`. Mutation: open a `ParquetWriter` in `_acquire.py`.

**Choke point 3, text joiner (H1).** Rule: "CSV and fixed-width union stages are written only by
`source_sets/_join_text.py::join_text_members`". Guard:
`ET:tests/sentry/source_config/test_text_joiner_choke_point.py`, scanning every module in
`source_sets/` for the writer names (`open_private`, the arena's create, `os.write`, `.write(`)
outside that function, with a planted-writer self test as the existing sentry has. Mutation: add a
byte write in `_acquire.py`.

**Choke point 4, value-free messages.** Enforced by the reason catalog. Guard: the catalog test in
class 1. Mutation: add a name field to a template.

**Import tiers (H2).** Engine `.importlinter` is `exhaustive = true`, and the root holds 25 `.py`
modules (at the fan-out cap), so both new parts are sub-packages:

- `path_glob/` (pure grammar, imports only `reasons` and the standard library) goes in the bottom
  tier. E0 adds ` : path_glob` to the last `layers` line. `config` and `sdk` import it.
- `source_sets/` (acquisition, imports `connectors`, `fileaccess`, `profile`, `declared_casting`,
  `execution.out_of_core._budget`) goes in the `execution` tier. E0 adds ` : source_sets` to the
  second `layers` line. No new `ignore_imports` line is needed: everything it imports is in its own
  tier or below.
- Both names go into the layout snapshot in `ET:tests/sentry/layout/test_import_layers.py`.
- `plan/checks/_union_routes.py` reads only the selector mode from the config model and never
  imports `source_sets` (the policy-direction contract would refuse it).
- File access: the member readers in `source_sets/_listing.py` and `_members_local.py` reach files
  only through `fileaccess` capabilities; any sink call site gets an entry in
  `ET:tests/sentry/file_access_registry.toml` so `test_file_access_boundary` and
  `test_file_access_entry_points` pass without widening `file_access_modules.toml`.

Placement (engine CODEMAP "Where Things Go"; CLI CODEMAP lines 52, 55, 61):

| New file | Directory | Map row | Beside |
|---|---|---|---|
| `path_glob/__init__.py`, `_grammar.py` | `src/decoy_engine/path_glob/` (new package, bottom tier) | new row "Path glob grammar" (E0) | `reasons/` |
| `source_sets/__init__.py`, `_select.py`, `_listing.py`, `_members_local.py`, `_acquire.py`, `_join_text.py`, `_member_facts.py` | `src/decoy_engine/source_sets/` (new package, execution tier) | new row "Multi-file source sets" (E0) | `execution/` |
| selector fields | `src/decoy_engine/config/_sources.py` (366 lines; no new module, config is at its cap) | "Config models" | existing models |
| `etag`, `generation` | `src/decoy_engine/sdk.py`, `connectors/s3.py`, `connectors/gcs.py` | "Public API", "Connectors" | existing |
| `source_set` reason catalog | `src/decoy_engine/reasons/source_set/` | "Reason codes" | other catalogs |
| route refusal | `src/decoy_engine/plan/checks/_union_routes.py` | "Plan compile and checks" (plan is frozen at 30; new checks in `plan/checks/`) | other checks |
| parts writer (E8) | `src/decoy_engine/safe_output/_parts.py` | "Safe output boundary" | other output modules |
| guard tests | `tests/sentry/source_config/` | "Source readers" sentries | existing source sentries |
| CLI evidence sidecar model and reader | `src/decoy/cli/evidence_members.py` (new, public within the CLI; `evidence.py` is at 792 lines and does not grow) | CLI evidence row | `evidence.py` |
| CLI sidecar store | `src/decoy/cli/library/_run_records.py` (through `store_evidence`, no second caller) | CLI library row | existing |
| CLI export flag | `src/decoy/cli/library/_export.py` | CLI library row | existing |
| CLI `${var}` grammar and expansion | `src/decoy/lang/_vars.py` (validate, gate, `ci check` and run import it from `lang`) | CLI language row | `_connectors.py` |
| CLI `--var` option | `src/decoy/cli/run/__init__.py` (option only, calls `lang`) | CLI line 52 | existing options |
| CLI placement collisions | `src/decoy/cli/io/_placement.py` (578 lines; extend) | CLI line 55 | existing |
| CI glob migration | `src/decoy/ci/staged.py`, `contracts.py` (edit only) | CLI line 61 | existing |

Size. Engine: about 9 new modules in two packages plus one reason catalog, about 1,700 lines of
source; public names `validate_path_glob`, `match_path_glob`, `FileMeta.etag`,
`FileMeta.generation`. CLI: 2 new modules, about 750 lines of source; public options `--var` and
`--include-member-names`. Tests about twice the source.

## 17. Pre-mortem

- **The staging pass is too slow for 100M-row tables.** Mitigation: AT-12 measures it; the virtual
  reader (Z) is the named follow-up, behind a benchmark.
- **Scratch disk fills on a hundreds-of-tables job.** Mitigation: admission before staging plus the
  per-batch budget (N9, M9); for now all tables stage at once with a clear refusal.
- **A real exporter layout breaks the selector rules** (DMS restarted numbering, Redshift parts with
  no extension). Mitigation: exporter fixtures in E1 and D1; content checks, not suffixes.
- **The CSV join differs from the oracle in an edge we did not list.** Mitigation: AT-11 corpus plus
  a property test that joins random member splits of one file and compares with the file.
- **Builders weaken the oracle** (class 8, a known pattern). Mitigation: the oracle is built by
  plain Arrow and byte concatenation in the test, red-first on the assertion (M8), and the gate
  diff-checks the acceptance tests.
- **Native cells silently skip** (gate venvs lack the companion). Mitigation: 10.1 cells run in
  `venv-native-lock` and the gate records a zero skip count for them.
- **F02-E2 slips.** Mitigation: GCS is slice E5, off the first cut.
- **Row 64 slips.** Mitigation: the first cut ships local unions alone. The engine S3 cells run on
  `moto` in E4; the CLI S3 cells are written when row 64 merges, never as skip markers (M15).
- **The evidence change breaks an older reader.** Mitigation: the bump to `cli-local-1.1` makes
  older readers refuse cleanly; the legacy `cli-local-1` fixture keeps reading.

## 18. Done when

- Every AT in section 10 is green on its slice's head, and red on its own assertion against the
  slice's scaffolding (M8).
- Every 10.1 matrix cell ran; the native cells ran in the companion venv with zero skips.
- Class table rows each have their sentry and mutation recorded at the gate, with the exact head
  each mutation ran on (L5, recurring defect 9).
- Docs (D1, and C4's `--var` docs) published; roadmap row F03 closed; CHANGELOG entries per slice.

## V2-LOG

- **L1.** Move `--duckdb-source` (C:cli/_duckdb_source.py) and `postgres_snapshot` onto the
  acquisition, so every stage-then-run path has one owner (follows from H1).
- **L2.** Move the installer glob (C:distribution/installer.py:174) onto the engine `path_glob`
  grammar.
- **L4 (QA tag).** The acquisition guard (choke point 1) should resolve the same code shapes the
  engine file-access sentry already resolves: import aliases, `getattr` with a literal name, bound
  method aliases and method forms on a connector object (recurring defect 5).
