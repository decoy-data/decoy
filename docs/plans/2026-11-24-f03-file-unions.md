Status: plan

# F03: several files as one logical table, and pattern selection of input files

Owner: Cam. Author: Opus plan agent. Date: 2026-11-24. Revision 2 (Codex write-up review folded in; turned into the plan).

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN: established solutions, choke point, placement, size, pinned guarantee), `feature-dev.md`, `api-and-compatibility.md`, `reuse-first.md`, `cross-cutting-concerns.md`, `security.md`, `architecture.md`, `testing.md` (test depth); vault `Decoy-Plan-Contract-and-Defect-Catalog.md`.

Owner decision 2026-11-24: partitioned tables (roadmap candidate F03) and pattern-matched input file
names come first in 1.x, together with the S3 and GCS source work (rows 64 CLI-CLOUD and 87 F02).
1.0 stays "the engine works on small local files". Nothing here moves into 1.0.

Bases: CLI `origin/main` `488d98b3`; engine `origin/main` `9f7bb1f4a`. Engine paths are relative to
`src/decoy_engine/` and carry `E:`; CLI paths are relative to `src/decoy/` and carry `C:`; platform
paths carry `P:`. Line numbers are from those heads.

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
  executor already owns the cloud stream. Everything else reuses Arrow, the F02 executor, the F25
  protected allocator and the existing readers.

## 4. Issues the design must answer

Items 1 to 15 came from the orchestrator, 16 to 27 from the write-up survey, N1 to N17 from the
Codex review. Each line names the slice that closes it (section 15).

1. **Pinned member list** (E2, E4, C2). Every member: ordinal, size, ETag or generation or local
   file identity, SHA-256 of the bytes consumed. Refuse a member that changed or vanished.
2. **Zero match** (E1). Coded refusal `source_set.no_match`, never an empty table.
3. **Export debris** (E1). Skip `_SUCCESS`, `_committed_*`, `_started_*`, `.crc`, names starting
   `_` or `.`, `_temporary/` subtrees, and keys ending in `/`. Count skips by reason; do not list
   skipped names (N4).
4. **Empty parts** (E2, E3). Rewritten per N5: a zero-row Parquet member with the right schema and
   a header-only CSV member are valid members. A zero-byte or malformed matched Parquet member is a
   refusal, not debris. A zero-byte member of a headerless CSV or fixed-width source is valid.
5. **Schema drift** (E2). Strict equality in F03 (D5); widenings are a later candidate.
6. **Hive partition columns** (E7). Off by default; see N12.
7. **Output layout** (E8, C6). One output file by default; parts are a separate later pair (D6, D7).
8. **Row identity** (E6). Member ordinal plus row within the member, where the coordinate survives
   (N10).
9. **CSV per-part headers and compression** (E3). Record-aware join (D4); gzip per member.
10. **Incremental runs and cross-run FK.** Out of scope. Keyed strategies still give the same
    masked value across runs under the same key.
11. **`init` and `scan` on a prefix** (C5). One table per selector (N11).
12. **Parallel FK components.** Out of scope (CHUNK-PARALLEL, 1.3).
13. **Pattern grammar** (E1, E9). Glob first; regex after a dependency call (D2).
14. **Run variables** (C4). See D8.
15. **Count guards** (E1). `min_files`, `expect_files`, `max_files`.
16. **Commit marker** (E1). `require_marker:`, checked before and after staging, and newer than every
    member (N1).
17. **Deterministic order** (E1). Sort by the UTF-8 bytes of the relative name; do not trust
    provider order.
18. **Runaway match** (E1). `max_files` plus listing bounds (N4).
19. **Output inside the input prefix** (C1). Extended to every publication path (N14).
20. **One object in two tables** (C1). Refused; local by file identity, cloud by provider, bucket
    and exact key (N3, N14).
21. **Value-free messages** (E1 to E6, C1 to C3). Messages name table and ordinal only (N16).
22. **Output names leak partition values** (E8). Parts named by ordinal only.
23. **Scratch disk** (E2). Protected allocator, reclaim after a crash (N15), disk admission (N9).
24. **Wrong-kind members** (E1, E3). Refuse by content, not suffix (N6).
25. **Resume** (E6, C3). Bind the snapshot before the first resumable effect (N13).
26. **Sampling bias** (E2). Profiling runs on the staged file, so it equals the consolidated
    baseline by construction (N11). `--sample` stays refused until SC2.
27. **Evidence size** (C2). Members go to a sidecar bound by digest (N17).
- N1. **Export boundary across tables** (E1, docs). Pinning each object does not stop yesterday's
  parents with today's children. F03 promises only the observed set. The marker must be newer than
  every selected member, or the run refuses `source_set.marker_stale`. Docs say cross-table
  consistency needs an immutable export root per run from the producer.
- N2. **Pin and hash the bytes consumed** (E2, E4). Local: open under the authorized directory
  handle, compare the listed identity with `fstat` of the held handle, hash from that handle, check
  size and identity at the end. Cloud: first GET under the pin, check `Content-Range` and total
  bytes on each retry, hash once before decompression, request the stored bytes on GCS.
- N3. **Path semantics** (E1). Local listing through the rooted file access (held directory, no
  symlink or junction following out of the base, regular files only, non-UTF-8 names refused).
  Matching is case-sensitive on `/`-separated relative names; no Unicode normalization; distinct
  cloud keys stay distinct. Duplicates are checked by file identity locally. A cloud key never
  becomes a scratch path name. A base that the cloud joiner would strip to the bucket root is
  refused.
- N4. **Listing bounds** (E1). Bound entries inspected (`max_listed`, default 1,000,000), pages,
  and elapsed time apart from `max_files`. Stream pages; aggregate skip reasons; refuse an
  incomplete listing. Cost fixture with sparse matches reports LIST, HEAD and GET counts.
- N5. **Empty versus corrupt** (E1, E3). Order: list, debris filter, match, count checks, validate
  each member's content. An external `column_names_file` is an input dependency, recorded, and never
  a member.
- N6. **Valid files that are not parts** (E1, docs). Refuse a base that holds `_delta_log/` or an
  Iceberg `metadata/` folder (`source_set.table_format_root`). Docs give tested selectors per
  exporter (Spark, DMS full load, Redshift, Athena) and say CDC replay is out of scope.
- N7. **FK and uniqueness per route** (E6, C3). A union table that takes part in a declared FK or a
  uniqueness check is refused on a route that skips that check (today the explicit CLI chunked
  route, C:cli/run/_execute.py:313-326). Parity tests per admitted route.
- N8. **Stage once at a defined point** (E2, C3). One acquisition before preflight; every later
  phase uses the staged binding; evidence keeps the logical binding.
- N9. **Residency budget** (E2). Admission counts staged bytes for every union table at once
  against free scratch space, using the existing spool-capacity error. The subset index limit
  (`UInt32`, E:subset/_inputs.py:86-93) is stated as a limit and refused above it.
- N10. **Row lineage** (E6). Declared-casting quarantine maps `row_position` to member ordinal and
  row through the cumulative row counts recorded at staging. Ordinary quarantine after transforms
  gets no member coordinates in F03 (non-goal, documented).
- N11. **Profiling, sampling, discovery** (E2, C5). Profiling and seeded sampling run on the staged
  file, so plans match the consolidated baseline. `scan` and `init` get grouped input syntax.
- N12. **Hive values become data** (E7). Strings only, never inferred; refuse a name that clashes
  with a physical column; percent-decode after matching; a key missing in one member is refused;
  refused for fixed-width; injected columns must be declared like any column.
- N13. **Record identity before any resumable effect** (E6, C3). The ordered snapshot digest and
  parser policy join the F23 resume fingerprint before the first checkpoint.
- N14. **Every publication path is a collision candidate** (C1). Extend the placement check
  (C:cli/io/_placement.py:128-179) to compare resolved input members with every planned output
  path: outputs, delivery run folders, evidence, vaults, quarantine, scratch.
- N15. **Scratch ownership after a kill** (E2). Use the protected allocator; reclaim abandoned
  stages with the existing owner and age checks (E:fileaccess/_reclaim.py:47, :129-159); never
  sweep a live run's stage.
- N16. **Diagnostic and evidence surfaces** (E1 to E6, C2). The shareable manifest, run result,
  reports, notifications and logs carry table, ordinal, count, size, pin and digests only. Member
  relative names go to a private sidecar. A canary in a member name and in a cell must not reach
  `str(exc)`, logs, the manifest or a library export.
- N17. **Sidecar ownership** (C2). Canonical JSON, byte limit, digest in the manifest, written
  before the manifest, stored in the library with the run, exported only with an explicit flag.
  Verify checks the digest offline and never opens the network.

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
- `files:` uses the one path-glob grammar (D1): `*`, `**`, `?`; refused: `[`, `]`, `{`, `}`, `!`,
  backslash, empty, absolute, drive prefix, `..` segments, control characters.
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

One run-owned **acquisition** turns each union descriptor into an execution binding: a local
descriptor over a staged file in a protected scratch stage, the ordered member facts, and a cleanup
lifetime. It runs once, before preflight. Declarations, capacity, profile, native admission,
subset and execution all receive the execution binding; evidence receives the logical binding plus
member facts (N8). Single-file sources do not pass through it and keep today's route.

- **Parquet (D5).** Read every pinned footer first (ranged reads on cloud). Require exact schema
  equality: names, order, types, nullability, nested fields, dictionary types and pandas metadata.
  Then stream each member's batches into one `ParquetWriter` with bounded `iter_batches`.
- **CSV (D4).** Parse each member with the existing dialect and encoding rules. Find the end of the
  header record (a quoted header can span lines), compare decoded header fields, and refuse a
  difference. Copy data records as exact bytes. Strip a member's BOM; refuse a member that ends
  inside a quoted field; add the first member's terminator when a member lacks a final one.
  Headerless sources (`header: false` or `column_names_file`) copy every record. Cloud CSV unions
  take only the options the cloud model has; adding the local dialect fields to cloud models is a
  non-goal.
- **Fixed-width.** No header. Copy records, check record length and terminator per member.
- **Pins and hashes (N2, F3).** Each member is read under its pin from the first byte; its SHA-256
  is computed on the stored bytes in the same pass; its identity is checked again at the end.
- **Disk (N9).** Before staging, admission sums the stated sizes of all union tables and refuses
  with the existing spool-capacity error when scratch space is short.

### 5.3 Where it lives

- **Engine**: selector model, grammar, listing, pins, acquisition, staging, schema rule, member
  facts in the run result, quarantine mapping, resume binding, records model change, later hive
  columns and output parts.
- **CLI**: language keys, validate and gate checks, CI glob migration to the engine API, placement
  collision check, run wiring and route refusal, evidence sidecar, verify, report diff, `--var`,
  `scan` and `init`.

### 5.4 Schema rule

F03 ships strict equality (D5). A later candidate may add order-independent widening (int sizes,
float sizes, large string and binary, nullability), decided from all footers before the writer
opens. Any difference is `source_set.member_schema_mismatch` naming the member ordinal and column.

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
`..` are impossible, no `/`, no glob characters). `${var.name}` expands once, only in a locator and
in `files:`, never in endpoint, credential or regex fields. `$${` writes a literal `${`. The complete
resolved locator is validated before any I/O, including Windows reserved names. `decoy validate`
checks syntax and positions; `decoy validate --var ...` also checks the resolved form. A missing
variable is `run.var_missing`; an unused one is `run.var_unused`, scoped per pipeline under `--all`.
Evidence records names and SHA-256 digests of values, not raw values.

## 6. Combined with S3 and GCS sources

- Depends on row 64 CLI-CLOUD wiring cloud sources through the CLI guard (F1).
- Listing uses `list(prefix)` with the base as the prefix. `FileMeta` gains optional `etag` and
  `generation` fields filled from the listing (no extra HEAD per object, no extra permission). It
  is experimental, so the change is additive and recorded in the surface inventory with F02.
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
- F03 is 17 slices (section 15). With 87 at about 9, 1.1 grows to about 56 slices. Splitting 1.1
  (cloud and file sources first) is an owner call.
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

## 9. Pinned guarantee and non-goals

Guarantee. For a source declared with a base and a selector, on local files and on S3 (GCS after
F02-E2):

1. The run reads exactly the members selected from one listing, in UTF-8 byte order of their
   relative names, each under its pin, and refuses when any member changes, vanishes or fails
   validation during the run.
2. Masking, FK handling, uniqueness, subset and profiling give the same result as the same run on
   one file that holds every member's records in that order.
3. Evidence binds the run to the ordered member set (ordinal, size, pin, SHA-256), and messages,
   logs and the shareable manifest hold no member name or data value.
4. The scratch stage is private to the run and removed on every exit path a process can run;
   abandoned stages are reclaimed by the next run.

Non-goals: cross-table export consistency without a producer contract (N1); incremental runs and
cross-run FK; Delta, Iceberg, CDC replay; schema widening across members; a virtual union reader;
member coordinates for ordinary quarantine after transforms; cloud CSV dialect fields; SFTP union
sources; parallel FK components; the platform.

## 10. Acceptance tests (hostile corpus, red first)

Each test is written first and must fail on the base. "Oracle" means the same pipeline run on one
consolidated file built by the test from the members in sorted order.

| # | Test | Expected |
|---|---|---|
| AT-1 | Cross-part FK: `orders` parts reference `customers` rows that live only in other parts | no orphans; masked FK values equal the oracle |
| AT-2 | Composite key across parts, and a self-referencing `employees.manager_id` whose parent is in a later part | equal to the oracle on every admitted route |
| AT-3 | Duplicate parent keys in two parts, and a genuine orphan | the same duplicate and orphan findings and policy outcome as the oracle |
| AT-4 | Masked uniqueness collision across a member boundary | detected as on the oracle |
| AT-5 | Schema mismatch: type, column order, nullability, pandas metadata, in either member order | `source_set.member_schema_mismatch` naming ordinal and column, both orders |
| AT-6 | Member changed between list and read (local rewrite, S3 overwrite, GCS new generation), and a vanished member | `source_set.member_changed` or `source_set.member_missing`; no output |
| AT-7 | Zero match; match below `min_files`; not equal `expect_files`; above `max_files`; listing above `max_listed` with ten matches | coded refusal each, listing stops at the bound |
| AT-8 | Debris: `_SUCCESS`, `.crc`, `_temporary/` subtree, hidden file, `/`-terminated key | skipped, counted by reason, no names in output |
| AT-9 | Missing marker, and a marker older than a member (late part, reused marker) | `source_set.marker_missing`, `source_set.marker_stale` |
| AT-10 | Zero-byte Parquet member; header-only CSV member; zero-row Parquet member; all members zero rows | refusal; valid; valid; empty table recorded |
| AT-11 | CSV: headerless members; quoted header spanning lines; BOM on one member; member without final newline; CRLF and LF mixed; member ending inside a quote; gzip members | staged data equals the oracle records byte for byte; the open quote is refused |
| AT-12 | Bounded memory: 200 members, 2M rows, peak RSS under 1.5x the single-file run on the oracle | holds; scratch peak about table size plus one member |
| AT-13 | Equivalence: CSV output byte-equal to the oracle run; Parquet output equal in schema, rows, order and seeded masked values | holds for mask, shuffle, subset, dedupe |
| AT-14 | Evidence lists every member: ordinal, size, pin, SHA-256 in sidecar order; digest in manifest; verify re-hashes local members; report diff shows member changes | holds; tampered sidecar fails verify |
| AT-15 | Value-free canary in a member name, a partition value and a cell, through parser, gzip, schema and cloud errors | canary absent from `str(exc)`, logs, stdout, manifest, run result, library export |
| AT-16 | Target or evidence or quarantine path under a source base and matching the selector; one object matched by two tables (also via hard link and case alias on a case-insensitive file system) | refused at validate or preflight |
| AT-17 | Explicit `--chunked` with a union table in a declared FK | refused, not run without the check |
| AT-18 | Kill the run during staging, start a second run | first stage reclaimed, live stages of a parallel run untouched |
| AT-19 | Resume after interruption with an extra member added | refused with the resume mismatch code |
| AT-20 | Delta `_delta_log/` or Iceberg `metadata/` under the base | `source_set.table_format_root` |
| AT-21 | Symlink or junction out of the base, special file, non-UTF-8 name | refused |
| AT-22 | `--var` with `..`, `/`, a glob character, a repeated name, an unused name; `$${` literal | refused or literal as specified |
| AT-23 | Cost: S3 fixture of 50,000 keys with 10 matches | one listing pass, 10 footer reads, 10 GETs, no per-key HEAD |

## 11. Defect classes

| # | Class | Closing structure | Sentry or property test | Mutation that must turn it red |
|---|---|---|---|---|
| 1 | Value-bearing output | member names only in the private sidecar; every `source_set.*` message built from the reason catalog with table and ordinal fields only | AT-15 canary test plus a reason-catalog test that no `source_set.*` template takes a name or value field | add the relative name to the `member_changed` message |
| 2 | Cleanup missing on an exit path | the acquisition is a context manager that owns the stage; the stage comes from the protected allocator with reclaim | AT-18 and a test that raises at every staging step and checks the stage is gone | remove the `finally` release in the acquisition |
| 3 | State machine and concurrency | stage names carry the run id; reclaim checks owner and age; the publish of parts is one pointer step | AT-18 two-run test; E8 test that a failed part write leaves the old generation current | reclaim without the owner check |
| 4 | Route parity and silent fallback | one acquisition before preflight; the route table refuses a union table on routes that skip FK checks | AT-2, AT-13 per route, AT-17; sentry that only the acquisition builds a union execution binding | let the chunked route accept a union table with FK |
| 5 | Referential integrity | consolidation gives FK code one table, so cross-part parents are visible | AT-1 to AT-4 against the oracle | stage only the first member |
| 6 | Untrusted producer | content checks per member: schema, header, quote state, magic bytes; marker freshness; table-format root refusal | AT-5, AT-9, AT-10, AT-11, AT-20 | accept a member by suffix without the magic-byte check |
| 7 | TOCTOU (check then use) | hash and read from the held handle; first GET under the listed pin; identity check at the end | AT-6 with a rewrite between list and open and between open and end | open the member by path again after the identity check |
| 8 | Weak tests and overclaimed evidence | equivalence against a test-built oracle, not against the code's own staging; evidence digests checked by verify | AT-13 with the oracle built by plain Arrow concat; AT-14 tamper test | build the oracle with the stager itself |
| 9 | Behavior-preserving refactor drift | the CI glob moves to the engine API with a parity corpus of every current CI contract pattern | parity test over the CI contract fixtures, old and new matcher | change `**` to match zero segments differently |
| 10 | Frozen contract drift | additive fields only; evidence version bump with a legacy single-file fixture; language freeze file updated in the same slice | `test_language_freeze.py`, frozen-surface sentry, legacy evidence fixture test | drop `FileFingerprint` single-file support |

## 12. Enumerations

### Exit paths of a union run

- Validate refusal (selector, counts, var, placement): no I/O, exit code for config errors.
- Listing refusal (no match, counts, bounds, marker, table-format root): no stage created.
- Staging refusal (schema, header, quote, changed, missing, disk): stage released by the acquisition.
- Execution failure after staging: stage released by the acquisition (E:fileaccess/_scratch.py:340).
- Kill or power loss: stage left; reclaimed by the next run (E:fileaccess/_reclaim.py:129).
- Success: evidence and sidecar written, then stage released.

### Routes a union table can take

- Full frame and stream: admitted; AT-13.
- Native companion: admitted on the staged file path (E:execution/_chunked_input.py:150).
- Out-of-core FK: admitted; last-write-wins duplicates follow global row order, which is the staged
  order (E:execution/out_of_core/_relation.py:348).
- Engine chunked FK: admitted within its existing single-column limits
  (E:execution/_chunked_fk_edge_checks.py:418).
- Explicit CLI `--chunked`: refused when the union table is in a declared FK (C:cli/run/_execute.py:313).
- Subset stage and standalone subset: admitted on the staged file (E:execution/pipeline/_subset_stage.py:149).

### FK shapes

- Single-column parent and child in different members.
- Composite key across members.
- Self-reference with the parent in a later member.
- Duplicate parent keys in two members (last-write-wins by staged order).
- Genuine orphan, and null child keys.
- Parent table single-file, child table union, and the reverse.

### Fields added

- Engine source models (E:config/_sources.py:101, :274, :331): `files`, `files_regex` (E9),
  `min_files`, `expect_files`, `max_files`, `max_listed`, `require_marker`, `partitions` (E7),
  `compression`.
- `FileMeta` (E:sdk.py:104): `etag`, `generation`, both optional.
- Run result: per table `members_count`, `members_digest`, `staged_bytes`.
- Engine records model and CLI manifest (C:cli/evidence.py:286): `input_fingerprints[table]`
  gains `fingerprint_method: "member_set"`, `members_digest`, `members_count`, `sidecar`.
- Sidecar: per member `ordinal`, `name`, `size`, `etag` or `generation` or local identity, `sha256`,
  `rows`.
- Target models (E8): `parts`, `rows_per_part`.
- Run options: `--var` (C4).

### Output surfaces

- stdout and the `--json` envelope: counts and codes only.
- Logs and notifications: table, ordinal, counts.
- Run result document (C:cli/run/_result.py): member counts and digests.
- Evidence manifest: digests and counts; sidecar: names (private).
- Library store and export: sidecar stored with the run, export needs an explicit flag.
- Quarantine files: declared-casting member mapping (E:declared_casting/_quarantine_protocol.py:71).
- Output parts (E8): ordinal names only.

## 13. Reuse inventory

| Need | Reused | Where |
|---|---|---|
| Path glob grammar | the `decoy ci` grammar, moved to the engine | C:ci/contracts.py:481-492, C:ci/staged.py:56-92 |
| Local listing and safe open | rooted file access with a held directory | E:fileaccess/_rooted.py:197-219 |
| Cloud listing and streaming | connector `list` and `open`, F02 executor | E:connectors/s3.py:152, E:connectors/object_store.py:141-176 |
| Scratch stage | F25 protected allocator and reclaim | E:fileaccess/_protected_dir.py:278-312, E:fileaccess/_reclaim.py:47 |
| CSV dialect and header rules | the one CSV parser | E:profile/_csv_reader.py:84-113 |
| Parquet writing | Arrow `ParquetWriter`, bounded `iter_batches` | WAREHOUSE.1 stager pattern |
| Disk refusal | spool-capacity error | E:execution/out_of_core/_budget.py:523 |
| Reason codes | reason registry, new `source_set` catalog | E:reasons/_registry.py |
| Placement collisions | CLI placement check | C:cli/io/_placement.py:128-179 |
| Resume binding | F23 fingerprint | E:delivery/resume/_fingerprint.py:66-72 |
| Atomic multi-file publish (E8) | batch publish | C:_atomic_batch.py:62-92 |

## 14. Frozen contracts

- `FileMeta` (experimental SDK export): additive optional fields; surface inventory updated with F02.
- New public engine API for the path glob (`decoy_engine.sdk`, experimental): `validate_path_glob`,
  `match_path_glob`.
- Source config models: additive keys; selector mode refuses on targets.
- `.decoy` grammar: new connector options; `tests/fixtures/release_freeze/lang-surface.json`
  updated in C1 with the freeze test.
- Evidence `cli-local-1`: new `fingerprint_method` value and fields; version stays readable by older
  readers that ignore extra keys; the engine records model widens; legacy single-file fixture kept.
- Run result: additive fields.
- Reason codes: new `source_set.*` and `run.var_*` codes in the catalogs; `target.parts_*` in E8.
- F23 resume fingerprint: gains the snapshot digest; an older checkpoint without it cannot resume a
  union table (refused, not guessed).

## 15. Slices

Builder-days are for one builder. Risk tier per slice. "Rev" is the review set: two reviewers
(Codex then Dennis) for risky slices, Codex only for low risk.

| Slice | Repo | What | Depends on | Builder-days | Risk | Rev |
|---|---|---|---|---|---|---|
| E1 | engine | `source_sets/` selection: grammar API, typed selector on the models, local listing via rooted access, debris, sort, counts, listing bounds, marker and freshness, table-format root refusal, `source_set` reason catalog; AT-7, AT-8, AT-9, AT-20, AT-21 | none | 2.5 | R2 | two |
| E2 | engine | acquisition and Parquet staging: protected stage, reclaim, held-handle hash, all footers then strict schema, disk admission, member facts in the run result, records model widening; every phase uses the staged binding; AT-1 to AT-6 (local), AT-10, AT-12, AT-13 (Parquet), AT-18 | E1 | 3 | R2 | two |
| E3 | engine | CSV and fixed-width staging, record-aware join, gzip, empty versus corrupt, `column_names_file` binding; AT-10, AT-11, AT-13 (CSV) | E2 | 2.5 | R2 | two |
| E4 | engine | S3: `FileMeta.etag` from listing, first GET under `IfMatch`, range and total checks, cost fixture; AT-6 (S3), AT-23 | E2, F02-E1 (merged) | 2 | R2 | two |
| E6 | engine | route admission and refusal for union tables, declared-casting quarantine member mapping, resume snapshot binding; AT-2, AT-17 (engine part), AT-19 | E2 | 2.5 | R2 | two |
| E-rel1 | engine | release and repin (checklist) | E1 to E4, E6 | 0.5 | R1 | one |
| C1 | CLI | language keys and `format:` for cloud unions, validate and gate checks, CI glob on the engine API with parity corpus, placement collisions; AT-16, AT-22 (syntax part) | E-rel1 | 2.5 | R2 | two |
| C3 | CLI | run wiring: acquisition before preflight, native gate on the staged binding, `--chunked` refusal, resume identity before the first checkpoint; AT-17, AT-19 end to end | C1, row 64 source wiring for cloud | 2 | R2 | two |
| C2 | CLI | evidence: member-set fingerprint, private sidecar, library store and export flag, verify, report diff, cloud single-object entries; AT-14, AT-15 | C3 | 2.5 | R2 | two |
| C4 | CLI | `--var`: grammar, expansion, resolved-locator validation, digests in evidence; AT-22 | C1 | 1.5 | R2 | two |
| C5 | CLI | `scan` and `init` grouped input over a selector | C3 | 2 | R1 | one |
| E5 | engine | GCS: generation from listing, first read under the generation, stored-bytes download; AT-6 (GCS) | F02-E2 | 1 | R2 | two |
| E7 | engine | hive partition columns (strings, clash and missing-key refusal, not for fixed-width) | E3 | 1.5 | R2 | two |
| E9 | engine | `files_regex:` on google-re2 | OQ-4 | 1 | R1 | one |
| E8 | engine | output parts: `parts: "mirror"`, `rows_per_part`, eligibility, generation publish | E-rel1 | 3 | R2 | two |
| C6 | CLI | parts delivery: generation folder, pointer publish local and S3, ledger, evidence, verify, resume over parts | E8 | 2 | R2 | two |
| D1 | CLI | docs: union sources guide, exporter selectors (Spark, DMS, Redshift, Athena), limits, cross-table consistency note, `--var` | C2, C4 | 1 | R0 | one |

Total: 17 slices, about 33 builder-days (engine 19.5 across 10 slices including one more release
for E5, E7, E8, E9; CLI 13.5 across 7). First cut, shippable on its own for local and S3: E1, E2,
E3, E4, E6, E-rel1, C1, C3, C2, D1. Then C4, C5. Then E5 after F02-E2, E7, E9, E8 with C6.

## 16. Design notes, choke point and placement

Design notes. Principles that apply: one place per fact (the acquisition owns the member list;
nothing else lists), dependency direction (the CLI imports the engine grammar, never the reverse),
typed context objects (the acquisition returns one `StagedSource` value, not a tuple). Established
pattern: stage then run, as `--duckdb-source` and WAREHOUSE.1 do; pin on read, as S3 `IfMatch` and
GCS `ifGenerationMatch` do.

Choke point. Rule: "a union source is listed, pinned and staged exactly once, by the acquisition".
Enforced by construction: only `source_sets.acquire` can turn a descriptor with a selector into a
readable binding; `build_profile_source` refuses a selector descriptor (E:profile/_readers.py:520).
Guard test: `tests/sentry/source_config/test_union_acquisition_choke_point.py` checks that no module
outside `source_sets/` calls connector `list` for a source and that `build_profile_source` refuses a
selector. Mutation: let `build_profile_source` read the first matching member; the guard turns red.

Second rule: "every source-set message is value-free". Enforced by the reason catalog. Guard: the
catalog test in class 1. Mutation: add a name field to a template.

Placement (engine CODEMAP "Where Things Go"; CLI CODEMAP lines 52, 55, 61):

| New file | Directory | Map row | Beside |
|---|---|---|---|
| `source_sets/__init__.py`, `_select.py`, `_listing.py`, `_acquire.py`, `_stage_parquet.py`, `_stage_text.py`, `_members.py` | `src/decoy_engine/source_sets/` (new package; map change in E1: row "Multi-file source sets") | new row; the engine root is at its fan-out cap, so a sub-package | `profile/` |
| selector fields | `src/decoy_engine/config/_sources.py` (366 lines; no new module, config is at its cap) | "Config models" | existing models |
| `etag`, `generation` | `src/decoy_engine/sdk.py`, `connectors/s3.py`, `connectors/gcs.py` | "Public API", "Connectors" | existing |
| `source_set` reason catalog | `src/decoy_engine/reasons/source_set/` | "Reason codes" | other catalogs |
| route refusal | `src/decoy_engine/plan/checks/_union_routes.py` | "Plan compile and checks" (plan is frozen at 30; new checks in `plan/checks/`) | other checks |
| parts writer (E8) | `src/decoy_engine/safe_output/_parts.py` | "Safe output boundary" | other output modules |
| guard tests | `tests/sentry/source_config/` | "Source readers" sentries | existing source sentries |
| CLI evidence sidecar | `src/decoy/cli/run/_members.py` | CLI line 52 (`decoy run` internals; `evidence.py` is at 792 lines) | `_evidence.py` |
| CLI `--var` | `src/decoy/cli/run/_vars.py` | CLI line 52 | `_prepare.py` |
| CLI placement collisions | `src/decoy/cli/io/_placement.py` (578 lines; extend) | CLI line 55 | existing |
| CI glob migration | `src/decoy/ci/staged.py`, `contracts.py` (edit only) | CLI line 61 | existing |

Size. Engine: about 7 new modules plus one reason catalog, about 1,600 lines of source; public
names `validate_path_glob`, `match_path_glob`, `FileMeta.etag`, `FileMeta.generation`. CLI: 2 new
modules, about 700 lines of source; public option `--var`. Tests about twice the source.

## 17. Pre-mortem

- **The staging pass is too slow for 100M-row tables.** Mitigation: AT-12 measures it; the virtual
  reader (Z) is the named follow-up, behind a benchmark.
- **Scratch disk fills on a hundreds-of-tables job.** Mitigation: admission before staging (N9);
  tables stage when their phase needs them only if a later slice proves it is safe; for now all at
  once with a clear refusal.
- **A real exporter layout breaks the selector rules** (DMS restarted numbering, Redshift parts with
  no extension). Mitigation: exporter fixtures in E1 and D1; content checks, not suffixes.
- **The CSV join differs from the oracle in an edge we did not list.** Mitigation: AT-11 corpus plus
  a property test that joins random member splits of one file and compares with the file.
- **Builders weaken the oracle** (class 8, a known pattern). Mitigation: the oracle is built by
  plain Arrow and byte concatenation in the test, and the gate diff-checks the acceptance tests.
- **F02-E2 slips.** Mitigation: GCS is slice E5, off the first cut.
- **Row 64 slips.** Mitigation: the first cut works for local files; cloud AT runs wait for 64.
- **The evidence change breaks an older reader.** Mitigation: legacy single-file fixture test and an
  additive method value.

## 18. Done when

- Every AT in section 10 is green on its slice's head, red on the base.
- Class table rows each have their sentry and mutation recorded at the gate.
- Docs (D1) published; roadmap row F03 closed; CHANGELOG entries per slice.
