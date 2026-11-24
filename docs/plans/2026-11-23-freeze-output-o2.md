Status: plan

# FREEZE-OUTPUT O2: compressed CSV targets stop storing the staging name and the write time

Owner: Cam. Author: Opus plan agent. Date: 2026-11-23. Revision 2. Roadmap row: FREEZE-OUTPUT item 2 (`docs/roadmap/groups/run.md:23`, "Left: O2"; O1 merged as engine #702, O3 as engine #704). Record: `docs/records/2026-11-07-atomic-output-build.md:48` (V2-LOG "`.gz` header can store the staging basename.").

Source plan: engine `docs/plans/2026-11-23-freeze-output-o2.md` on `plan/freeze-output-o2` (`044b4b4b1`, revision 2.1; Dennis R1 GO-WITH-FIXES, R2 GO with two lows). That plan already settled the design and states the fix is CLI-only. This file is the build copy for the CLI repo. It does not change the design. Where the two differ, the source plan wins. Anchors below were re-read at CLI `origin/main` `6544b6ec`. Since `6aec4451` only `src/decoy/cli/io/__init__.py` (two export lines) and an unrelated read sentry changed under `cli/io` and its tests.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN, Proportion), `cross-cutting-concerns.md`, `api-and-compatibility.md`, `proportionality.md`, `testing.md` (Test depth).

Risk: R2. Output bytes of `decoy detokenize` and `decoy unmask` change. Output bytes freeze at REL-GATE (row 93), so a change after 1.0 is a 2.0 break; this must land before 1.0. Plan review: done on the source plan. Code gate: Codex, then Dennis. Tests: T0, T1, then a full CLI suite before merge (frozen-bytes trigger).

Repo: CLI (`decoy-data/decoy`). The engine has no gzip, zip or tar writer.

## Revision history

| Rev | Date | Change |
|---|---|---|
| 1 | 2026-11-23 | First build copy of the source plan |
| 2 | 2026-11-23 | Codex R1 (GO-WITH-FIXES). V1: tar picks PAX when the member name is over 100 bytes, not only by size (AT-O9); a suffix-only target (`-o .zip`) gets the member name `data.csv` (AT-O10). DESIGN: `tests/sentry/io_policy/test_target_writes.py` joins the change list and checks each descriptor's stager and mode. V2-LOG items fixed here: AT-O3 clocks 10 s apart, AT-O5 pre-existing 0644 target under umask 077, AT-O8 asserts the chunked archive refusal, the `.tar.bz2` previous-mode claim, the `test_compression.py` deletion range, a note that the private goldens are checked on Linux only |
| 3 | 2026-11-23 | Codex R2 delta (GO-WITH-FIXES). V1: tar name length is counted in `tarfile.ENCODING` bytes with `surrogateescape`; AT-O9 adds a multibyte and a raw-byte name. DESIGN: AT-O11 checks each writer's descriptor and seeds a swap. V2-LOG: CHANGELOG says suffix-only archive target |

## 1. Problem

A `decoy detokenize -o out.csv.gz` file carries the staging file name `.out.csv.gz.decoy-<hex>.tmp` in its gzip FNAME field and the wall-clock time in MTIME. Two runs on the same input give different bytes, and the temp name leaks into the output. The same DataFrame route gives `.zip` members the current time, needs `zstandard` for `.zst`, and fails on `.tar.bz2`. Private archive members (detokenize, unmask) extract as 0644.

## 2. Current code

| Site | Today |
|---|---|
| `src/decoy/cli/io/_targets.py:568-570` (in `_write_table`, `:544`) | `with stage(path) as tmp:` then `data.to_csv(tmp, index=False, compression=csv_compression(path))`. pandas opens `tmp` by name, so FNAME is the staging basename, MTIME is now, level 9 |
| `src/decoy/cli/io/_targets.py:571-578` | Arrow branch already uses `open_csv_sink(tmp, path)` |
| `src/decoy/cli/io/_compression.py:146` | `open_csv_sink`, the frozen codec opener; gzip at `:97` is `GzipFile(fileobj=raw, mode="wb", compresslevel=6, filename="", mtime=0)` |
| `src/decoy/cli/io/_compression.py:120`, `:130` | `_tar_member` (mode 0o644 at `:123`), `_zip_member` (`external_attr` 0o100644 << 16 at `:134`) |
| `src/decoy/cli/io/_compression.py:81-87` | `_archive_name` cuts the archive suffix. For a suffix-only name (`.zip`, `.tar.gz`) it returns `""`. pandas then names the member after the staging file; the Arrow route writes an empty member name, which Python `zipfile` cannot extract |
| `src/decoy/cli/io/_compression.py:167` | Tar format is USTAR unless the size is over `_USTAR_MAX_SIZE`. A member name over 100 bytes raises `ValueError: name is too long` in USTAR. pandas today uses `tarfile`'s default (PAX), so detokenize succeeds with such a name |
| `src/decoy/cli/io/_targets.py:729-730` | The chunked writer refuses an archive CSV target (`STREAMING_UNSUPPORTED`), so chunked output has no archive members |
| `tests/sentry/io_policy/test_target_writes.py:451-468` | `_stagers_passed_to_write_table` reads the last argument of each `_write_table` call as a literal stager name and requires `{staged_local_target, staged_private_target}`; `STAGE_CALLS` (`:59`) lists the names the staged-path rule accepts |
| `src/decoy/cli/io/_compression.py:60-80` | `csv_compression`, imported only at `_targets.py:42` |
| `src/decoy/cli/io/_targets.py:587`, `:602` | `write_table` (`staged_local_target`, `:599`) and `write_private_table` (`staged_private_target`, `:614`) |
| `src/decoy/cli/io/_targets.py:753` | chunked `open_csv_sink` call |
| Callers | detokenize `src/decoy/cli/tokenize.py:732` (DataFrame), unmask `src/decoy/cli/unmask.py:268` (`pa.Table`) |

## 3. Guarantee and non-goals

- G1. Every compressed CSV target from `write_table`, `write_private_table` and the chunked writer goes through `open_csv_sink`. The gzip header is `1f8b08000000000000ff`: no FNAME, MTIME 0.
- G2. The same input gives the same bytes on every run, for all nine suffixes.
- G3. Archive members of a private target are 0600; public ones stay 0644.
- G4. The decoded CSV text does not change.
- G5. Every tar target whose member name fits today still writes: the format is PAX when the member name is over 100 UTF-8 bytes or the size is over the USTAR limit, else USTAR.
- G6. An archive member name is never empty. A suffix-only target name gives the member `data.csv`, on every route.

Non-goals: `run` and chunked public bytes (already on the codec) except a suffix-only archive name (G6), new suffixes, compression level options.

## 4. Design

- Choke point: `open_csv_sink`. `_write_table` writes `data.to_csv(sink, index=False)` inside `with open_csv_sink(tmp, path, member_mode=...) as sink`. pandas no longer opens a file or picks a codec.
- No FNAME and MTIME 0, not the final basename. This matches the Arrow route and the reproducible-builds practice (`gzip -n`, `SOURCE_DATE_EPOCH`) the source plan cites. The final name adds no value to a file that already has it.
- `member_mode` is a required keyword on `open_csv_sink`, `_tar_member` and `_zip_member`. Constants `PUBLIC_MEMBER_MODE = 0o644` and `PRIVATE_MEMBER_MODE = 0o600` sit in `_compression.py`. A frozen dataclass `_TargetPrivacy(stage, member_mode)` has two instances, `PUBLIC_TARGET` and `PRIVATE_TARGET`; `_write_table` takes one. So the staging mode and the member mode cannot disagree.
- Tar format: `fmt = PAX_FORMAT if size > _USTAR_MAX_SIZE or len(name.encode(tarfile.ENCODING, "surrogateescape")) > tarfile.LENGTH_NAME else USTAR_FORMAT`. A PAX header from `tarfile` has mtime 0 and no user names, so the output stays deterministic. The member has no `/`, so the USTAR prefix field cannot help. The byte count uses `tarfile`'s own encoding with `surrogateescape`, so a POSIX name holding raw bytes (`os.fsdecode(b"x\xff.csv.tar")`) is measured, not refused.
- Member name: `_archive_name` returns the constant `FALLBACK_MEMBER_NAME = "data.csv"` when the cut name is empty. One rule in the opener, so DataFrame, Arrow and `run` targets agree.
- Delete `csv_compression` and its test.
- Target-writes sentry (`tests/sentry/io_policy/test_target_writes.py`). `_write_table` now gets a `_TargetPrivacy` and opens `with target.stage(path) as tmp`. The sentry changes in the same PR:
  - The staged-path rule accepts a `<param>.stage(...)` call on `_write_table`'s descriptor parameter, with a seed that a different attribute (`target.open(...)`) stays red.
  - `test_the_public_whole_table_writers_pass_a_real_stager` requires the descriptors passed to `_write_table` to be exactly `{PUBLIC_TARGET, PRIVATE_TARGET}`. It reads each module-level `_TargetPrivacy(...)` assignment and checks `PUBLIC_TARGET` names `staged_local_target` and `PUBLIC_MEMBER_MODE`, and `PRIVATE_TARGET` names `staged_private_target` and `PRIVATE_MEMBER_MODE`. It also checks the descriptor each writer passes: `write_table` passes `PUBLIC_TARGET` and `write_private_table` passes `PRIVATE_TARGET`. Seeds: a swapped stager, a swapped mode, the two writers' descriptors swapped, and an inline `_TargetPrivacy(open, 0o644)` passed to `_write_table` each fail.
- Guard: the sentry `tests/sentry/io_policy/test_csv_frame_choke_point.py:146` grows. The guarded `to_csv` must write to the name bound by an enclosing `with open_csv_sink(...)` and must have no `compression=` keyword. A second check fails on any `compression=` keyword on a `to_csv` call anywhere in `src/decoy`. Its docstring names the limit: a `compression` passed through `**kwargs` is not seen.

Design notes: one small dataclass, so the stage function and member mode travel as one fact. No new module.

Established solutions: reproducible gzip output (`gzip -n`, Python `GzipFile(filename="", mtime=0)`, reproducible-builds.org `SOURCE_DATE_EPOCH`). The codec already follows it; this slice routes the last bypass through it.

## 5. Behavior and CHANGELOG

CHANGELOG `## [Unreleased]`, Breaking:

- `decoy detokenize` writing a `.csv.gz`, `.csv.tar.gz` or `.csv.zip` target now writes different bytes. The gzip header has no file name, MTIME 0 and compression level 6 (was: the staging file name, the write time, level 9). A zip member is dated 1980-01-01 (was: the write time).
- `decoy detokenize` writing `.csv.zst`: with `zstandard` installed the bytes change (pyarrow's zstd frame); without it the write now succeeds where it failed with `ImportError`. `.csv.tar.bz2` now writes instead of failing.
- `decoy detokenize` and `decoy unmask` archive outputs (`.csv.zip`, `.csv.tar`, `.csv.tar.gz`, `.csv.tar.bz2`, `.csv.tar.xz`): every member now has mode 0600. Before: unmask members were 0644; detokenize members were 0644 except the zip member (already 0600), and detokenize `.csv.tar.bz2` failed before it wrote a member.
- A suffix-only archive target (`-o .zip`, `-o .tar.gz`) now holds a member named `data.csv`, for every command. Before: detokenize named it after the staging file; `unmask` and `run` wrote an empty name that Python's `zipfile` cannot extract.
- `decoy unmask` to a tar target whose member name is over 100 bytes now writes (PAX header) where it failed with `name is too long`. detokenize already wrote it.
- The decoded CSV text is unchanged.

The record line `docs/records/2026-11-07-atomic-output-build.md:48` is marked resolved with the PR number.

## 6. Failure modes

| Failure | Handling |
|---|---|
| A future writer calls `to_csv(path, compression=...)` | Sentry second check fails (AT-O7) |
| A private writer passes the public mode | Cannot: the mode comes with `PRIVATE_TARGET`; AT-O8 |
| pandas writes into a binary handle differently on a bump | AT-O4 and the goldens catch it |
| A failed write leaves a staging file | Unchanged: `stage(path)` owns the temp file; AT-O5 |
| A tar member name over 100 bytes | PAX header; AT-O9 |
| A suffix-only archive name | Member `data.csv`; AT-O10 |
| A descriptor built with the wrong stager or mode | Target-writes sentry fails (AT-O11) |

## 7. Defect classes

| # | Class | Applies | Structure | Proof (mutation) |
|---|---|---|---|---|
| 1 | value | Yes: the staging name leaks into the file; private members extract world-readable | codec opener; `PRIVATE_TARGET` | AT-O1, AT-O8 (M-1, M-3, M-6) |
| 2 | cleanup | N/A: `stage(path)` still owns the temp file; the archive spool closes in the opener's `ExitStack` | existing | AT-O5 |
| 3 | state | N/A: one synchronous write, no shared state | none | none |
| 4 | route | Yes: DataFrame and Arrow routes used different codecs | one opener for both routes | AT-O2, AT-O7, AT-O8 (M-1, M-6) |
| 5 | referential | N/A: codec wrapping only, no rows change | none | AT-O4 |
| 6 | untrusted | N/A: no child process or extension | none | none |
| 7 | toctou | N/A: `open_csv_sink` opens the staged `tmp` once | existing atomic tests | none |
| 8 | weak | Yes: some golden cells are green on base on purpose | cells marked; red cells recorded at base | each mutation names its AT |
| 9 | refactor drift | Yes: CSV text and public member modes must not move | AT-O4, AT-O8 public cells | M-8, M-7 |
| 10 | frozen contract | Yes: detokenize and unmask bytes | fourteen goldens | AT-O2, AT-O8 (M-2, M-4, M-6) |

## 8. Acceptance tests

Fixture F is the small DataFrame from the source plan. Goldens go in `tests/fixtures/cli_fmt/csv_writer/`.

| AT | Test | Mutation that turns it red |
|---|---|---|
| AT-O1 | `write_table` and `write_private_table` to `out.csv.gz`: first 10 bytes are `1f8b08000000000000ff` and the file has no `decoy-` substring | M-1: restore `to_csv(tmp, ..., compression=csv_compression(path))`; M-3: gzip without `filename=""` |
| AT-O2 | Goldens: nine public suffixes from `write_table`, five private archive suffixes from `write_private_table` | M-2: gzip `mtime=None`; M-4: zip date set to now; M-8: `index=True` |
| AT-O3 | Two writes with the clock patched 10 seconds apart give equal bytes, all nine suffixes. ZIP times have 2-second steps, so a gap under 2 s would hide M-4 | M-2, M-4 |
| AT-O4 | The decoded payload of every suffix equals `F.to_csv(index=False).encode()` | M-8 |
| AT-O5 | Under umask 077, with an existing 0644 target, `write_private_table` to `.csv.gz` leaves mode 0600 and no staging file (green on base on purpose). The existing 0644 file makes the public stager show: it keeps the old mode | Swap the private stage for the public one |
| AT-O6 | e2e: `decoy detokenize -o out.csv.gz` twice gives equal bytes that start with the frozen header | M-1 |
| AT-O7 | Sentry passes on the fix and fails on each seed: `compression=` keyword, `to_csv` outside the block, `to_csv(tmp)` inside the block, `compression=` anywhere in `src/decoy` | M-5: `to_csv(tmp, index=False)` inside the `with` block |
| AT-O8 | Private archive members are 0600 for DataFrame and `pa.Table` input on all five archive suffixes; public members are 0644; the chunked writer refuses every archive CSV suffix with `STREAMING_UNSUPPORTED` (`_targets.py:729`); e2e `decoy unmask -o out.csv.zip` gives a 0600 member | M-6: `PRIVATE_TARGET` with `PUBLIC_MEMBER_MODE`; M-7: `_tar_member` ignores `member_mode` |
| AT-O9 | `write_private_table` and `write_table` to `<101 x "a">.csv.tar` and `.csv.tar.gz`: the write succeeds, the member name round-trips, the archive is PAX. A 100-byte name stays USTAR. A 34-character name of 3-byte UTF-8 letters (102 bytes) is PAX, and a raw-byte name from `os.fsdecode(b"x\xff.csv.tar")` writes and round-trips. e2e: `decoy detokenize` to such a target succeeds | Pick the format by size only; count `len(name)` instead of bytes; encode with strict UTF-8 |
| AT-O10 | `-o .zip`, `-o .tar` and `-o .tar.gz` targets from `write_table`, `write_private_table` and e2e `decoy detokenize`: the one member is `data.csv`, `zipfile.ZipFile.extractall` and `tarfile` extraction work, two runs give equal bytes | Return `""` from `_archive_name` |
| AT-O11 | The target-writes sentry passes on the fix and fails on each seed in section 4 (swapped stager, swapped mode, writers' descriptors swapped, inline descriptor, `target.open`) | Build `PRIVATE_TARGET` with `staged_local_target`; pass `PUBLIC_TARGET` from `write_private_table` |

The builder records red output at base for each red cell.

The five private goldens are checked on Linux only so far; the public hash prefixes matched on Linux. The builder runs AT-O2 on the Mac before merge and names any difference in the PR.

## 9. Enumerations

### Exit paths

- Clean exit: `stage(path)` (`_targets.py:568`) renames the temp file over the target.
- Exception in `to_csv` or in the codec: `stage` removes the temp file and re-raises; the opener's `ExitStack` closes the codec and archive spool first.
- Exception on `.zst` without `zstandard`: no longer possible on this route (pyarrow frame).

### Routes

- `_write_table` DataFrame branch, `_targets.py:568-570`: moves into `open_csv_sink`.
- `_write_table` Arrow branch, `_targets.py:571-578`: gains `member_mode`.
- Chunked writer, `_targets.py:753`: gains `PUBLIC_MEMBER_MODE`. Archive targets are refused first at `_targets.py:729`, so the mode never reaches a member there.
- Entry points `write_table` (`_targets.py:587`) and `write_private_table` (`_targets.py:602`); callers `tokenize.py:732` and `unmask.py:268`.

### FK shapes

N/A: no rows or keys change; this is codec wrapping only.

### Fields

- `_TargetPrivacy.stage`: the staging function (`staged_local_target` or `staged_private_target`).
- `_TargetPrivacy.member_mode`: 0o644 or 0o600.
- No public result type changes.

### Output surfaces

- Output file bytes: gzip header, zip member date, archive member mode, tar format for a long member name, member name for a suffix-only target.
- Output file mode: unchanged (AT-O5).
- stdout, stderr, `--json`, logs and errors: unchanged.

## 10. Reuse inventory

`open_csv_sink`, `stage` / `staged_local_target` / `staged_private_target`, the CSV frame choke-point sentry, `tests/sentry/io_policy/file_sinks.toml` (the `_write_table` `to_csv` row is reworded to say it writes into the codec sink). New: the two mode constants, `FALLBACK_MEMBER_NAME` and `_TargetPrivacy`.

## 11. Frozen contracts

CSV target bytes of `decoy detokenize` (DataFrame route) and archive member headers of `decoy detokenize` and `decoy unmask`. Breaking, before REL-GATE. Public `run` and chunked bytes do not change, except the member name of a suffix-only archive target (G6).

## 12. Files allowed to change

`src/decoy/cli/io/_targets.py`, `src/decoy/cli/io/_compression.py`, `tests/unit/cli_fmt/test_compression.py` (delete `test_csv_compression_follows_the_real_name` and its parameters at `:35-53` and the `csv_compression` import at `:17`; keep the suffix-parity test at `:25-32` and everything after `:53`), `tests/unit/cli_fmt/test_csv_writer_bytes.py`, `tests/sentry/io_policy/test_csv_frame_choke_point.py`, `tests/sentry/io_policy/test_target_writes.py`, `tests/sentry/io_policy/file_sinks.toml`, new goldens under `tests/fixtures/cli_fmt/csv_writer/`, one detokenize and one unmask e2e test, `CHANGELOG.md`, `docs/records/2026-11-07-atomic-output-build.md`.

## 13. Test selection

- T0: `tests/unit/cli_fmt/test_compression.py`, `tests/unit/cli_fmt/test_csv_writer_bytes.py`.
- T1: all of `tests/unit/cli_fmt/`, `tests/sentry/io_policy/`, the detokenize, unmask, tokenize and atomic-output tests, plus import-impact selection on `_targets.py` and `_compression.py`.
- Before merge: full CLI suite on the merge head against the saved main baseline (frozen-bytes and moved-test triggers).

## 14. Slices and size

One slice, CLI repo. About 55 source lines, net small (one `to_csv` call moves inside the opener, `csv_compression` goes). New names: `PUBLIC_MEMBER_MODE`, `PRIVATE_MEMBER_MODE`, `FALLBACK_MEMBER_NAME`, `_TargetPrivacy`, `PUBLIC_TARGET`, `PRIVATE_TARGET`, and the `member_mode` keyword. Fourteen golden files. PR #399 also edits `_targets.py` (a type predicate at `:405-424`); different lines, text rebase only.

## 15. Risks and pre-mortem

- A consumer that compares detokenize output bytes sees a change once. That is the point, and it lands before 1.0.
- The builder regenerates goldens from the buggy route and freezes the bug. AT-O1 and AT-O3 fail on that.
- The builder passes `member_mode` with a default to save edits. A required keyword makes a missed caller a `TypeError` at test time.
- The builder keeps the size-only tar format check because the goldens pass. AT-O9 fails on it.
- The builder edits the target-writes sentry to accept any descriptor name. AT-O11 seeds fail on that.
- `.zst` goldens differ by `zstandard` presence. The goldens are written from pyarrow's frame, which needs no extra.

No owner question. The 0600 member mode follows the private-output rule already in force.
