Status: proposal

# F03: several files as one logical table, and pattern selection of input files

Owner: Cam. Author: Opus plan agent. Date: 2026-11-24. Revision 1 (write-up, before the Codex review).

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN: established solutions, choke point, placement), `feature-dev.md`, `api-and-compatibility.md`, `reuse-first.md`, `cross-cutting-concerns.md`, `security.md`, `architecture.md`.

Owner decision 2026-11-24: partitioned tables (roadmap candidate F03) and pattern-matched input file
names come first in 1.x, together with the S3 and GCS source work (rows 64 CLI-CLOUD and 87 F02).
1.0 stays "the engine works on small local files". Nothing here moves into 1.0.

Bases: CLI `origin/main` `488d98b3`; engine `origin/main` `9f7bb1f4a`. Engine paths are relative to
`src/decoy_engine/` and carry `E:`; CLI paths are relative to `src/decoy/` and carry `C:`; platform
paths carry `P:`. Line numbers are from those heads.

Risk: R2 (data handling across a new input route, FK integrity, evidence contract, SDK surface).

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

## 2. Current state (checked on main)

- **Sources take one literal locator.** The language has five connectors, each with one locator:
  `csv`, `parquet`, `fixed_width` (`path`), `s3` (`bucket`, `key`), `gcs` (`bucket`, `object`)
  (C:lang/_connectors.py:35-42). The engine models match: `FileSource.path` (E:config/_sources.py:101),
  `S3Source.key` (E:config/_sources.py:274), `GCSSource.object` (E:config/_sources.py:331). The
  language guide says the same (CLI `docs/guides/decoy-language/agent-card.md:42-45`). No glob,
  regex, prefix or directory form exists.
- **One descriptor, one reader.** `build_profile_source` dispatches one descriptor to one reader
  (E:profile/_readers.py:520). The lazy reader holds one `path` (E:profile/_readers.py:233). The
  identity check that refuses a file changed between the routing pass and the read covers one
  local file (E:profile/_lazy_identity.py:43, reason `runtime.lazy_source_changed`).
- **Single-path assumptions are spread wide.** `isinstance(..., LazySource)` appears 34 times in 24
  engine files (execution routes, out-of-core, subset, declared casting, profiling). A new
  multi-file source type would have to pass every one of them.
- **Cloud sources are read whole.** The S3 and GCS readers fetch the full object into memory for a
  full read (E:profile/_cloud_readers.py:233 `_s3_full`, and the `to_frame` methods at
  E:profile/_cloud_readers.py:268, :316, :388, :435). Ranged reads exist only for footers and samples.
- **Connectors can list, but list results carry no version.** `list(prefix)` exists on S3
  (E:connectors/s3.py:152), GCS (E:connectors/gcs.py:127) and SFTP (E:connectors/sftp.py:279). It
  yields `FileMeta`, which has `path`, `size`, `content_type`, `modified` and no ETag, S3
  `VersionId` or GCS generation (E:sdk.py:104). The S3 body reader already pins the ETag of the
  first response with `IfMatch` on resume (E:connectors/s3.py:205, :239, F02-E1). The GCS
  generation pin is F02-E2, not merged.
- **F02 names this as a non-goal.** The F02 plan lists "prefix, glob or directory sources" under
  non-goals (engine branch `plan/f02-sftp-cloud`, `docs/plans/2026-11-17-f02-sftp-cloud.md:155`).
  F02-E6 (merged) lets subset read a remote source through a local copy the caller makes
  (E:subset/_api.py:351, :357).
- **The CLI already stages one input to a local file.** `--duckdb-source TABLE=DB_PATH`
  (C:cli/run/__init__.py:358) acquires a DuckDB relation into a temporary Parquet file and runs the
  normal file path over it unchanged (C:cli/_duckdb_source.py:1-6). It is the only per-run source
  override. There are no run variables, and no `${` interpolation anywhere in the language.
- **The only globs in the CLI select repo files, not data.** `decoy ci` staged-scan contracts accept
  `*`, `**` and `?` and refuse `[`, `]`, `{`, `}`, `!` and backslash
  (C:ci/staged.py:52, C:ci/staged.py:88 `glob_matches`, C:ci/contracts.py:481-492).
- **Evidence records one entry per table, and none for a cloud source.** `build_manifest` writes
  `input_fingerprints[table] = {path, fingerprint, fingerprint_method, size_bytes}` from
  `src.get("path")`. An S3 or GCS source has no `path` key and is skipped, so a cloud-source run
  records no input identity at all today (C:cli/evidence.py:286-303). The entry schema checks the
  listed fields only and does not refuse extra keys (C:cli/evidence.py:126-133, :437-445), so a new
  field is additive.
- **The gate cannot see remote sources.** It warns "declared columns not checked: remote source,
  checked at run" (C:cli/gate/_layers.py:418).
- **GCS targets are refused in the CLI** until real-bucket evidence exists (C:cli/io/_cloud.py:25).
  Quarantine and `--chunked` are refused with cloud targets (C:cli/io/_cloud.py:104-107).
- **The platform fans files out.** Platform `iteration: files` lists a bucket and starts one child
  job per file (P:api/jobs/iteration.py:1-22, listing at :191-219). That is the behavior that makes
  cross-part FK references look like orphans and lets uniqueness see one part. The platform is parked.
- **Quarantine identifies a row by its index in the table** and adds `_quarantine_trigger` and
  `_quarantine_reason` (E:quarantine.py:19, :195). It has no notion of a member file.
- **An old multi-part Parquet stager exists on a branch.** Engine branch
  `claude/v2-warehouse-sources-and-tokenization-vault` (roadmap WAREHOUSE.1, far behind main) has
  `connectors/parquet_dataset.py`. It merges local Parquet parts in sorted-path order into one staged
  Parquet file, refuses any schema difference (`schema_mismatch`, exact equality), streams row group
  by row group, publishes atomically and names parts by basename only. Reference only: it does not
  list, pin, handle CSV, or record evidence.
- **Roadmap.** F03 sits under "Candidates with no plan yet" (CLI `docs/roadmap/groups/connect.md:36`).

## 3. How established tools do it

| Tool | Selection | Part discovery and debris | Schema across parts | Snapshot and evidence |
|---|---|---|---|---|
| Spark file sources ([partition discovery](https://spark.apache.org/docs/latest/sql-data-sources-parquet.html#partition-discovery), [generic options](https://spark.apache.org/docs/latest/sql-data-sources-generic-options.html)) | a path or glob; `pathGlobFilter`, `recursiveFileLookup` | `key=value` directories become columns, types inferred unless `spark.sql.sources.partitionColumnTypeInference.enabled=false`; `basePath` sets where partitions start; files starting with `_` or `.` are ignored | first file's schema unless `mergeSchema=true` | none: the listing at query time is the set; Hadoop committers write `_SUCCESS` when the job commits |
| Hive | table location plus metastore partitions | `MSCK REPAIR TABLE` adds partition directories | table schema in the metastore | metastore, no per-file pin |
| DuckDB ([multiple files](https://duckdb.org/docs/data/multiple_files/overview), [hive partitioning](https://duckdb.org/docs/data/partitioning/hive_partitioning)) | `read_parquet('dir/**/*.parquet')`, `*`, `**`, `?`, `[...]`, or a list of files | `hive_partitioning=true` adds columns, `hive_types` fixes their types; `filename=true` adds the source file as a column | `union_by_name=true` aligns by name, otherwise by position | none; an empty match is an error ("No files found that match the pattern") |
| pyarrow.dataset ([docs](https://arrow.apache.org/docs/python/dataset.html)) | a directory, a list of paths, a `FileSelector` | `partitioning="hive"`; `ignore_prefixes` defaults to `['.', '_']`; `exclude_invalid_files` | schema from the first fragment unless given; `pa.unify_schemas` for explicit unification | none |
| Delta Lake ([protocol](https://github.com/delta-io/delta/blob/master/PROTOCOL.md)) | the table root | the `_delta_log` lists every data file (`add` and `remove` actions), so a listing is never trusted | schema in the log; evolution is explicit | a table version pins the exact file set |
| Apache Iceberg ([spec](https://iceberg.apache.org/spec/)) | the table | metadata file, then manifest list, then manifests naming each data file with record count, size and partition values | schema ids in metadata | a snapshot id pins the exact file set |
| Redshift `UNLOAD ... MANIFEST` ([docs](https://docs.aws.amazon.com/redshift/latest/dg/r_UNLOAD.html)) | the manifest | the manifest lists each part URL and `content_length` | one schema per unload | the manifest is the pinned set |
| Athena `UNLOAD` and CTAS ([docs](https://docs.aws.amazon.com/athena/latest/ug/unload.html)) | a prefix | `PARTITIONED BY` writes `key=value` directories; a manifest in the results location lists the files written | one schema per query | the manifest |
| AWS DMS to S3 ([docs](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Target.S3.html)) | `bucketFolder/schema/table/` | full load `LOAD00000001.csv` and up; CDC files named by timestamp; optional date partition folders; CSV or Parquet, optional gzip | one table schema, but a source DDL change mid-stream changes later files | none |
| Snowflake `COPY INTO <table>` ([docs](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table)) | stage prefix plus `PATTERN = '<regex>'` (a full-path regex) or `FILES = (...)` | none beyond the pattern | table schema | load metadata remembers files already loaded (incremental) |
| BigQuery external tables | a URI with one `*` wildcard | hive partition detection options | per table | none |
| S3 itself ([consistency](https://aws.amazon.com/s3/consistency/), [ListObjectsV2](https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListObjectsV2.html)) | prefix and delimiter | keys listed in UTF-8 binary order | n/a | strong read-after-write consistency since December 2020; a multipart ETag is not an MD5 of the body |

What we take from this:

- **A listing is not a snapshot.** Delta, Iceberg and the UNLOAD manifests exist because "list the
  prefix" is not a consistent set while an export is writing. A run must pin the set it read (path,
  size, version) and refuse a set that changes under it. S3 and GCS listings are strongly consistent,
  but a listing taken during an export still returns a partial set. Only a commit marker or a
  manifest says the export finished.
- **Debris rules are a convention.** Spark and pyarrow skip names starting with `_` or `.`. Hadoop
  also writes `.crc` checksum files beside parts on local and HDFS file systems.
- **Hive partition columns are opt-in, and their types are a known trap.** Spark and DuckDB both
  infer types from path text, and both offer a switch to stop it.
- **Schema across parts is either strict or explicitly unified.** Union by name is a per-tool
  option, never the only behavior.
- **Patterns:** glob is the common form (Spark, DuckDB, BigQuery). A regex is the escape hatch
  (Snowflake `PATTERN`).

## 4. Issues the design must answer

The orchestrator's list first, then the ones this survey added (marked new).

1. **Pinned member list.** Record every member (path or key, size, ETag or `VersionId` or GCS
   generation, SHA-256 of the bytes read) in evidence. Read each member under its pin. Refuse a
   member that changed or vanished mid-run.
2. **Zero match.** A pattern that matches nothing is a coded refusal, never an empty table.
3. **Export debris.** Skip `_SUCCESS`, `_committed_*`, `_started_*`, `.crc`, hidden names, and S3
   "folder" keys ending in `/`. Record what was skipped and why.
4. **Empty parts.** A zero-row Parquet part with the right schema is a member. A zero-byte file is
   not a valid Parquet file, and for CSV with a header it has no header. Both are skipped as debris
   and recorded.
5. **Schema drift across parts.** Identical after a short list of safe widenings, otherwise a coded
   refusal naming the member by ordinal and the column by name.
6. **Hive partition columns** (`dt=2026-11-24/region=eu/`). Off by default. Opt-in adds string
   columns. Types are never inferred.
7. **Output layout.** One output file, or parts. Mirroring input parts is natural for a drop-in
   pipeline, but see issue 22.
8. **Row identity across parts** for quarantine, validation findings and evidence: member ordinal
   plus row within the member.
9. **CSV per-part headers and compression.** Each part repeats the header. DMS and Spark often gzip.
10. **Incremental nightly runs and cross-run FK.** A nightly run over "new parts only" cannot check
    FKs against rows from earlier runs. Out of scope. Deterministic keyed strategies still give the
    same masked value across runs under the same key. Named so nobody assumes it.
11. **`decoy init` and `decoy scan` on a prefix** should propose one table, not one table per part.
12. **Parallelism across independent FK components.** Out of scope (row CHUNK-PARALLEL, 1.3).
13. **Pattern grammar.** Glob by default, regex as an escape hatch, anchored and limited to a listed
    prefix.
14. **Run variables** (`--var run_date=2026-11-24`, `${var.run_date}` in a locator), checked by
    validate.
15. **Count guards.** Optional `min_files` and `expect_files`.
16. (new) **Commit marker.** A listing taken while the export is still writing is a partial set.
    Optional `require_marker: "_SUCCESS"` refuses the run when the marker is missing.
17. (new) **Deterministic order.** Local directory order differs by OS and file system. Members are
    sorted by the UTF-8 bytes of the path relative to the base (S3 lists in that order already), so
    row order, sampling and `limit` are the same everywhere.
18. (new) **Runaway match.** `**` at a bucket root can list millions of keys. A `max_files` cap
    (default 10,000) refuses above it. Listing stops at the cap plus one.
19. (new) **Output inside the input prefix.** A nightly job whose target sits under its own source
    base reads yesterday's masked output as input. Refuse when a target location is under a source
    base and matches its pattern.
20. (new) **One object in two tables.** `orders*` also matches `orders_lines/...`. Refuse a member
    claimed by two tables in one run.
21. (new) **Value-free messages.** Object keys can hold data (`customer_id=123/`). Errors, logs and
    stdout name a member by table and ordinal, never by key. Only the evidence file lists keys,
    as it records local paths today.
22. (new) **Output names can leak partition values.** A mirrored layout that copies input names
    republishes `customer_id=123` in clear beside masked data. Output parts are named by ordinal
    (`part-00000.parquet`), with the input-to-output map in evidence only.
23. (new) **Scratch disk.** Staging a table needs local scratch space about the size of the table.
    It must go through the F25 scratch root (E:fileaccess/_protected_dir.py:294) and be removed on
    every exit path.
24. (new) **Members of the wrong kind.** A `.csv` member in a `parquet(...)` source, a gzip member
    when the source does not allow it, an archived (S3 Glacier) object, a symlink leaving the base
    directory, the same member reached through two paths. Each is a coded refusal.
25. (new) **Resume (row 85, F23).** A resumed run must refuse when the pinned member set differs
    from the one the interrupted run recorded.
26. (new) **Sampling bias.** `--sample N` and profiling samples read the first N rows, which come
    from the first members. Profiling must sample across members.
27. (new) **Evidence size.** 50,000 members make a large manifest. Store the member list as a
    sidecar file beside the manifest when it passes a size limit, bound by its digest.

## 5. Design options

### 5.1 How the user names the set

| Option | Form | For | Against |
|---|---|---|---|
| A. Glob in the existing locator | `parquet("exports/orders/*.parquet")` | shortest | changes the meaning of literal paths that contain `*`, `?` or `[`, which are legal file names, so "single-file configs unchanged" breaks; no clear listing root |
| **B. Base plus `files:` (recommended)** | `parquet("exports/orders/", files: "part-*.parquet")`, `s3("bucket", "exports/orders/", files: "**/*.parquet")` | additive (a source without `files:` is today's source); the base is a literal listing root, which keeps S3 and GCS listing to one prefix; the pattern is relative to it | two arguments instead of one |
| C. Manifest file | `parquet("exports/orders/", files_from: "manifest.json")` (Redshift `MANIFEST`, Athena manifest, a plain list) | an exact set written by the exporter; strongest snapshot | needs the exporter to write one; three manifest dialects |
| D. Table formats | read Delta or Iceberg metadata | exact snapshots | a different feature (WAREHOUSE and X-06 territory) |

Recommendation: **B now, C later as a 1.x candidate, D out of scope.** Under B:

- `files: "glob"` uses the `decoy ci` glob grammar (`*`, `**`, `?`; `[`, `]`, `{`, `}`, `!` and
  backslash refused), so the product has one glob grammar. The engine does the matching (5.3), so
  the grammar moves to the engine and the CLI's `ci` code imports it, or both keep a copy with a
  parity test. The plan picks one.
- `files_regex: "..."` is the escape hatch. It is matched with `fullmatch` against the path relative
  to the base, so it is always anchored and always inside the base. Validate refuses it when it is
  over 256 characters or holds a backreference or a lookaround. It is a separate key because the
  language has no call values in options (C:lang/_ast.py:10-18).
- `files:` and `files_regex:` are mutually exclusive. With either, the positional locator is a base
  directory or prefix and must end with `/`.
- Optional keys: `min_files: N`, `expect_files: N`, `max_files: N` (default 10,000),
  `require_marker: "_SUCCESS"`, `partitions: "hive"`, `compression: "gzip"` (CSV and fixed-width
  only).

### 5.2 How the engine reads the set

| Option | Shape | For | Against |
|---|---|---|---|
| X. Fan out child jobs (platform today) | one job per part | exists | the defect: cross-part FK refs become orphans, uniqueness sees one part |
| **Y. Stage and consolidate (recommended)** | list, pin, stream every member in order into one local file of the source's format under the scratch root, then run the normal single-file path on it | every route, the native companion, FK masking, uniqueness, dedupe, shuffle, subset and the 34 `LazySource` sites work unchanged; byte-equal to a consolidated input by construction; the same pattern as `--duckdb-source` and WAREHOUSE.1; remote members must be downloaded anyway, because cloud full reads are whole-object today | a scratch copy about the size of the table; one extra write pass |
| Z. Virtual union reader | a `LazySource` subclass whose batches chain the members | no copy | touches every route seam and the native input path; a `.path` that is not one file breaks code that hands a path to DuckDB or Rust |

Recommendation: **Y for F03.** Z is a later optimization, only if a benchmark shows that the staging
pass or its disk is the bottleneck. Staging details:

- Parquet: remote members are downloaded under their pin to a scratch temp file first, one at a time,
  and deleted after they are appended. Each member is opened, its schema checked against the first
  member's (5.4), and its row groups streamed into one `ParquetWriter`. Peak scratch is the
  consolidated file plus one member.
- CSV and fixed-width: bytes are appended. Each member's header line must equal the first member's
  header bytes after a UTF-8 BOM is stripped. The first member's header is written once. A member
  whose last line has no line terminator gets the first member's terminator. gzip members are
  decompressed as they stream when `compression: "gzip"`.
- Hive columns, when asked for, are added to each member's rows as strings as it is appended.
- A member's SHA-256 is computed during the same pass, and its pin is re-checked after the pass:
  the local identity rule from E:profile/_lazy_identity.py:43, S3 `IfMatch` or `VersionId`, GCS
  `if_generation_match`.
- The staged file is published into the scratch directory atomically and removed when the run
  ends, on every exit path.
- The engine records per member: ordinal, relative path, size, version, SHA-256, row count.

### 5.3 Where it lives

- **Engine**: the source keys (on `FileSource`, `S3Source`, `GCSSource`), the selection (match,
  debris, sort, caps, marker), the pin, the staging, the schema rule, the hive columns, the member
  facts in the run result, the quarantine member fields and the output parts. The engine owns it, so
  a future platform restart uses the same code instead of its fan-out.
- **CLI**: the language keys pass through unchanged (every option goes to the engine under its own
  name, C:lang/_connectors.py:1-7), validate and gate checks, `--var`, the target-under-source
  refusal, the evidence `members` field, report diffs, `init` and `scan` support.

### 5.4 Schema rule across Parquet members

Names, order and types must match the first member. These widenings are applied to the whole table
when any member needs them: nullability (non-null becomes nullable); `int8`, `int16`, `int32` to
`int64`; `float32` to `float64`; `string` with `large_string` (to `large_string`); `binary` with
`large_binary`; dictionary-encoded with plain of the same value type. Field metadata is ignored.
Everything else is refused with `source.member_schema_mismatch`: a different column set or order, a
time zone or unit change on timestamps, a decimal precision or scale change, any narrowing.

### 5.5 Output layout

- Target is a file name (today's form): one output file. Default.
- Target is a directory or prefix ending in `/` with `parts: "mirror"`: one output part per input
  member, named `part-NNNNN.<ext>` by member ordinal, rows split by the member row counts. Allowed
  only when the table's pipeline keeps every row in order (mask, shuffle). Validate refuses it when
  subset, dedupe, limit, sample or quarantine can drop rows (`target.parts_mirror_drops_rows`).
- Target ending in `/` with `rows_per_part: N`: parts of N rows, named by ordinal.
- Input names and hive directories are never copied into output names (issue 22).

### 5.6 Run variables

`decoy run --var run_date=2026-11-24` (repeatable). `${var.name}` may appear only inside locator
strings and `files:`, not in `files_regex:`, so a value cannot change a regex. The syntax matches
the platform's `${var.X}` resolver (E:sdk.py:96 docstring). Values must match
`[A-Za-z0-9._=-]{1,128}`: no `/` and no glob characters, so a variable can never widen a selection.
`decoy validate` checks the syntax and the positions without values. `decoy run` refuses a missing
variable (`run.var_missing`) and an unused `--var` (`run.var_unused`, a typo guard). Evidence records
names and values. Logs name variables only.

## 6. Combined with S3 and GCS sources

- Listing uses the S3 and GCS `list` methods with the base as the prefix. The first build lists the
  whole prefix and filters, capped by `max_files`.
- `FileMeta` gets an additive optional `version` field: S3 `VersionId` when the bucket is versioned,
  else the ETag; GCS generation. `FileMeta` is exported from the SDK, so the change goes through the
  frozen-surface process as an additive field with a default.
- Downloads reuse the F02 executor: S3 body resume under `IfMatch` (F02-E1, merged) and the GCS
  generation pin (F02-E2, not merged). **F03 on GCS needs F02-E2 first.** S3 and local can go
  before it.
- Evidence fills a real gap: a cloud-source run records no input identity today
  (C:cli/evidence.py:286-303). With F03 every cloud source, a single object or a set, gets a pinned
  entry.
- The CLI-CLOUD delivery code (C:cli/io/_cloud.py) is the target side. Issue 19 (target under a
  source base) is checked there for cloud targets and in the local layout check for files.
- GCS targets stay refused in the CLI until CLI-CLOUD's real-bucket run (C:cli/io/_cloud.py:25).
  GCS sources are not affected by that refusal.

## 7. Slotting in 1.x

- New row F03 (file unions and pattern selection) in 1.1, "Run in production pipelines", beside
  64 CLI-CLOUD: owner 2026-11-24, first in 1.x with cloud sources; 1.0 stays small local files.
- 87 F02 is listed in 1.4. The owner decision names F02 with F03, and F03 on GCS needs F02-E2.
  This write-up moves 87 F02 to 1.1 as well and records it in `docs/roadmap/decisions.md`. If the
  orchestrator reads the owner's words differently, the alternative is: F02-E2 alone moves to 1.1,
  and the rest of 87 stays in 1.4.
- 1.1 was about 30 slices. F03 adds about 12 and 87 about 9, so 1.1 becomes about 51. The release
  table will need a split (1.1 cloud and files, 1.2 the rest of "production pipelines") when 1.1 is
  planned. That is the owner's call. This write-up does not reorder the other releases.
- The WAREHOUSE.1 multi-part Parquet reader (1.5) is replaced by F03's Parquet staging. WAREHOUSE.1
  keeps the DuckDB attach and catalog browser.

## 8. Open questions for the owner

- OQ-1. Default output for a union source with a directory target: refuse until `parts:` or
  `rows_per_part:` is given (recommended), or mirror by default.
- OQ-2. Is a `max_files` default of 10,000 right for the SQL Server case (hundreds of tables, a few
  to a few hundred parts each)?
- OQ-3. Manifest input (option C) in 1.x after F03, or wait for a customer ask?
