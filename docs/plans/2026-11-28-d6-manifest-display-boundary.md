Status: plan, revision 4

Changelog, revision 4 (Codex round 2, edits 1 to 7). Rows 51 to 64 trace authority ambiguity, project refusals, pointer components, opaque envelopes, default export, valid fixtures and the isolated R4 seed.

# D6-manifest redesign: one display boundary for report output (PR #416)

Slice 24zk D6-manifest, worktree `wt-prop-shims-d6m`, base head `c708039bf`. Risk R3 (credential leak).
Revision 3: applies Codex plan review round 1 (`~/scratch/codex-d6m-plan.out`, final section,
edits 1 to 6 plus the row fixes). Revision 2 applied Dennis round 1 (`~/scratch/d6m-dennis-r1.md`).
Rules consulted: 00-universal.md, risk-and-exceptions.md, development-loop.md (PLAN), testing.md,
cross-cutting-concerns.md, architecture.md, workspace-and-vcs.md.

## Earlier changes (revision 3)

- Codex 1: one span rule for userinfo. The last `@` on the line decides, and a host is shown only
  when every surveyed parser would agree on it; otherwise `(remote location)` (section 1, step 3).
  Bare `//` references use the same rule when the first segment holds `@`, or holds `:` with an
  `@` later (step 4). Explicit normalization of a collapsed `scheme:/` (step 2). Backtick added to
  the closers. An unchanged share is rescanned from its authority (step 5). Survey in section 4.
- Codex 2: components are displayed before they are composed: table keys in field names, digest
  previews only for canonical digests, evidence file names taken after display (section 4, "Built
  clean").
- Codex 3: `library show` uses the field policy from the engine's evidence `path_fields`. Default
  `library export` is tracked as separate V1 row `ENGINE-EXPORT-REMOTE-PATH` (section 8).
- Codex 4: public `render_html`/`render_markdown` keep their dict input and run it through
  `display_manifest`. The 19 direct test calls are not ported. Collision suffix rule names a free
  suffix (rows 41, 42).
- Codex 5: sentry rewritten with exact forwarders and clean producers; renderer rule scoped to
  functions; green baseline plus attributable red per seed (section 5).
- Codex 6: valid success fixtures, separate refusal fixtures, two different manifests for both
  diffs, presence assertions next to absence checks, A4 positives only at admitted boundaries.
- Rows: 5 and 6 traced through step 2; 12 split (path field vs text); 15 now fails closed; 17 and 18
  re-traced; 30 keeps its backtick. New rows 36 to 50. Test placement table added (section 6).

Guarantee: in the stdout, stderr, JSON and written report files of `report show`, `report render`,
`report diff`, `report verify`, `library show` and `library diff`, no manifest or record string shows
the userinfo of any URL; a scheme URL shows no path, query or fragment (`scheme://host[:port]`); a
`//` reference shows no query or fragment (`//host`). Verify and fingerprints keep reading raw
values. Not covered here: default `library export` (V1 row in section 8). Non-goals: the V2-LOG
items; hostile edits (V1 threat model: accidental leaks only).

## 1. Behavior

One span scanner and one URL parser serve both kinds of string.

Terms. A **start** is S1 or S2 below. **A** is the authority start (the character after `//`, or
after `:/` for a collapsed scheme). The **line** is the text from A to the next `\r`, `\n` or end.
The **first segment** is the text from A to the first `/ ? #` or whitespace.

- S1: any `://` (the span takes in the run of `[A-Za-z0-9+.-]` just before it), or
  `[A-Za-z][A-Za-z0-9+.-]+:/` (2+ characters, so `C:/` is a drive). No left boundary.
- S2: a bare `//` followed by a character that is not whitespace or `/`, where the character before
  `//` is not a path character `[A-Za-z0-9._~/\-]` (start of text counts as allowed).

Steps for one span:

1. **Start.** Find the earliest start at or after the scan position.
2. **Normalize.** For S1, the shown scheme is the scheme run, lower case, and the shown separator
   is always `://`: `https:/u:PW@h/x` is read as `https://u:PW@h/x` (rows 5, 6). A scheme run that
   is empty or does not start with a letter has no scheme to show (rows 20, 31).
3. **Userinfo (S1, and S2 when suspect).** Let `at` be the last `@` on the line. With no `@`, the
   span has no userinfo. With an `@`, the userinfo is `U = text[A:at]` and the host part `H` runs
   from `at + 1` to the first `/ ? #` or whitespace. A host is shown only when `U` holds no
   whitespace and none of `/ ? # @`.
   Before emitting any host, including a no-userinfo host, reject a backslash in the candidate
   authority (before `/ ? #` or whitespace), in `U`, or in `H`. Consume the full step-5 span
   and return `(remote location)`. Apply this check before the ordinary-share branch too.
   Otherwise the span is `(remote location)`. `H` must also parse: `safe_url_parts(f"x://{H}")`
   returns a host, else `(remote location)` (bad port, row 20).
4. **S2 suspect test.** An S2 span is suspect when its first segment holds `@`, or holds `:` and an
   `@` follows on the line. Also inspect the prefix from A up to `/`, `?`, `#` or line end,
   including spaces. An `@` in that prefix, or a colon in it followed by a later `@` on the line,
   makes the span suspect. Row 47 stops at `/` before reaching the unrelated email. A suspect span uses step 3 and shows `//host[:port]`. Any other S2 span
   is an ordinary share: no userinfo. It shows `//host` when the span holds `?` or `#`, shows
   `(remote location)` when a later `//` authority in the span holds `@` (row 12), and is
   otherwise unchanged.
5. **End and resume.** Without userinfo the span ends at the next whitespace. With userinfo it ends
   at the next whitespace after `H` (so everything up to the last `@` on the line is inside it). A
   closing `` > ) ] } " ' ` `` at the span end that matches the opener just before the span start
   (`<` `(` `[` `{` `"` `'` backtick) is kept outside the span (rows 1, 30). After a replaced span,
   scanning resumes at its end. After an unchanged share, scanning resumes at A, so an inner
   collapsed scheme is still found (row 44).
6. **Shown form.** S1 with a scheme: `scheme://host[:port]`; S1 without one: `(remote location)`;
   S1 with no host (`file:///x`): `(remote location)`; S2: as step 4. A fail-closed
   result takes precedence over every host or unchanged-share output.

Two entry points:

- **`display_location(value)`** for location fields (`pipeline_path`, `project_manifest`,
  `scan_baseline.path`, `input_fingerprints.*.path`, `output_fingerprints.*.path`, and every echoed
  CLI path argument). For a multiline location apply L1 to L4 per line and preserve line breaks. (L1) the value starts with S1: steps 2, 3, 6 with
  the whole value as the span. (L2) a scheme marker appears later: `(remote location)` (row 4).
  (L3) the value starts with `//`: step 4 with the whole value as the span. (L4) otherwise
  `display_text(value)`, so a `//` inside a path field is still caught (row 32).
- **`display_text(text)`** for every other string and every dict key at any depth: steps 1 to 6
  across the text.

| # | Input (where) | Display output |
|---|---|---|
| 1 | `See <https://host/hook/TOKEN>` (warning) | `See <https://host>` |
| 2 | `URL:https://u:p@h/x` (warning) | `URL:https://h` |
| 3 | `a,https://u:p@h/x` / `a;...` / `a\|...` | `a,https://h` / `a;https://h` / `a\|https://h` |
| 4 | `/project/https:/user:PW@host/in.csv` (path field) | `(remote location)` (L2) |
| 5 | `could not read /project/https:/user:PW@host/in.csv` (warning) | `could not read /project/https://host` (step 2) |
| 6 | `https:/u:PW@h/x` (path field) | `https://h` (step 2, then L1) |
| 7 | row_counts key `https://u:PW@h/x` (terminal card and JSON key) | `https://h` |
| 8 | `//id.example/callback#access_token=T` (path field) | `//id.example` |
| 9 | `source comment: // WARNING: checksum mismatch for archive@2026.csv` | unchanged |
| 10 | `/var/run//deploy@prod/output.csv` (path field or text) | unchanged (`n` before `//`) |
| 11 | `\\server\share\f.csv`, `/data//exports/current.csv` | unchanged |
| 12 | `//share/https://u:PW@host/f` | path field: `(remote location)` (L2); text: `(remote location)` (step 4, inner authority) |
| 13 | `//host/p?token`, `//host?access_token=T` | `//host` |
| 14 | `could not open //user:pass@first word@host/path today` | `could not open (remote location) today` |
| 15 | `https://user:pass word@host/path`, `//user:pass word@host/path` | `(remote location)`, `(remote location)` (whitespace in `U`) |
| 16 | `//user:pw@files.example permission denied for ops@example.com` | `(remote location)` |
| 17 | `paths: //plain/share,//u:PW@host/f` | `paths: (remote location)` (ordinary share, inner authority with `@`) |
| 18 | `paths: //plain/share, //u:PW@host/f` | `paths: //plain/share, //host` |
| 19 | `source'//host/p?token` (each of `' " ( [ { = < , ; \|` and backtick) | `source'//host` |
| 20 | `https://u:PW@h:bad/o.csv?t=T` (bad port), `://u:PW@h/o.csv` (S1, no scheme) | `(remote location)` |
| 21 | `sftp://u:PW@[::1]:22/o.csv` | `sftp://[::1]:22` |
| 22 | `/tmp/x/payroll@2026.csv`, `payroll#2026.csv`, `payroll?year=2026.csv` (path field) | unchanged |
| 23 | `//files/share/payroll?2026.csv` (path field) | `//files` |
| 24 | `C:/Users/a@b/x.csv` | unchanged (one-letter scheme is a drive) |
| 25 | verify issue for table key `https://u:PW@h/t` (`EvidenceIssue.message`) | `(table 'https://h')` |
| 26 | malformed `output_fingerprints` entry under key `https://u:PW@h/x` (`exc.message`, `str(exc)`) | `` `output_fingerprints.https://h` must be an object `` |
| 27 | `postgresql://admin:2024#Secret@db.example/prod` | `(remote location)` (`#` in `U`) |
| 28 | `https://u:12/ss@h/x`, `https://u:12?ss@h/x` | `(remote location)` |
| 29 | `https://h/x@2026.csv` | `(remote location)` (over-redacted, section 7) |
| 30 | `` `//u:PW@h/x` `` (backticks), `*//u:PW@h/x`, `see://u:PW@h/x` | `` `//h` ``, `*//h`, `see://h` |
| 31 | `at 12://u:PW@h/x`, `x ://u:PW@h/o.csv` | `at (remote location)`, `x (remote location)` |
| 32 | `/data/a=//u:pw@h/x` (path field, L4) | `/data/a=//h` |
| 33 | `file:///data/x.csv`, `file://nas/x.csv` | `(remote location)`, `file://nas` |
| 34 | `//server/share/payroll#2026.csv` (path field) | `//server` |
| 35 | two row_counts keys `https://a:1@h/x`, `https://b:2@h/y` | `https://h`, `https://h (2)` |
| 36 | `postgresql://admin:2024#Secret word@db.example/prod` (text and path field) | `(remote location)` (Codex 1) |
| 37 | `//u:12/ss@h/x` (text and path field) | `(remote location)` (suspect: `:` then `@`; `/` in `U`) |
| 38 | malformed row count under key `//u:PW@host/t` (`exc.message`, `str(exc)`) | `` `row_counts.//host` must be an integer `` |
| 39 | verify, recorded fingerprint `https://bob:2024@db/x`, file changed | `(recorded (not a digest), current sha256:<first 9 hex>...)` |
| 40 | `report show` on unparsable file `<tmp>/https:/h/hook/TOKEN` | `could not parse (remote location) as JSON: ...` |
| 41 | row_counts keys in order `https://h (2)`, `https://a:1@h/x`, `https://b:2@h/y` | `https://h (2)`, `https://h`, `https://h (3)` |
| 42 | row_counts keys in order `https://a:1@h/x`, `https://b:2@h/y`, `https://h (2)` | `https://h`, `https://h (2)`, `https://h (2) (2)` |
| 43 | `library show` of an evidence record whose `input_fingerprints.t.path` is row 4 | `(remote location)` (location rule, not text rule) |
| 44 | `//share/https:/h/hook/TOKEN` | text: `//share/https://h` (step 5 rescan); path field: `(remote location)` (L2) |
| 45 | `https://S:2024#S@h/x`, `//u:S/S@h/x` (secret on both sides of the delimiter) | `(remote location)` |
| 46 | `wrote https://h/x, contact ops@example.com` | `wrote (remote location)` (over-redacted, section 7) |
| 47 | `see //plain/share and ops@example.com` | unchanged (ordinary share; email untouched) |
| 48 | `//host:8080/x` (path field) | unchanged (`:` but no `@` on the line) |
| 49 | `see https://status.example and ops@example.com` | `see (remote location)` (whitespace in `U`) |
| 50 | `report diff`, old fingerprint `https://bob:2024@db/x` | `(not a digest)` (shared `digest_preview`) |
| 51 | `https://hooks.example\incoming\marker`, `https://u:marker@hooks.example\incoming\marker` | both yield `(remote location)` in text and location fields; raw authority or H contains a backslash |
| 52 | `see //service account:marker@files.example/x today` | `see (remote location) today` (suspect prefix, whitespace in U); row 47 keeps its email |
| 53 | parsed project-bound file at `<tmp>/https:/h/hook/marker`, no project marker above it | `project_not_found`, message starts `(remote location) records paths relative to a Decoy project` |
| 54 | same file inside an explicit project, recorded at a different relative file | `project_mismatch`, message starts `(remote location) is not where its run wrote it` |
| 55 | known sample-run changes the value at raw keys `future_metadata`, `https://u:marker@h/x` | structural `changed` contains `/payload/future_metadata/https:~1~1h` once in both modes |
| 56 | unknown `future-thing`, label `pipelines/demo.yaml`, marker in unreadable payload | JSON status `opaque`, label `pipelines/demo.yaml`, no payload key; terminal shows label and existing unreadable-payload notice |
| 57 | engine default export, pipeline path `https://h/hook/marker` | exported record's pipeline path is `https://h` |
| 58 | input path `//id.example/callback?access_token=marker` | exported entry path is `//id.example` |
| 59 | both fingerprint maps and row_counts keyed by `https://u:marker@h/x` | exported maps each contain `https://h` with original entry or count |
| 60 | structured warning column `https://u:marker@h/x`, code `probe` | exported warning keeps code `probe`, column `https://h`, empty detail |
| 61 | A has zero warnings, B adds row 60 and changes the displayed table's count 3 to 4 | B card warning count 1; library evidence diff `warnings_added == ["probe"]` and delta +1 |
| 62 | correctly bound manifest, pipeline path `../https:/h/hook/marker` climbs above project root | `path_outside_project` names `pipeline_path`; no marker |
| 63 | unmodified sentry input, then one extra `DisplayCopy({})` in `_show.py` | no diagnostics, then R4 alone (no loader-bound input) |
| 64 | HTTPS path before row 55 pointer escaping, sibling key `a~/b` | displayed URL component `https:~1~1h`; ordinary sibling `a~0~1b` |

Trace notes. Rows 1 to 35 were re-traced against steps 1 to 6; all keep their revision 2 result
except row 12 (now split by entry point, same placeholder), row 15 (fails closed: a password with
whitespace cannot be told from `host:port text@host`), and row 26 (example changed to an entry key,
where the field name is built from the displayed key). Rows 36 and 45 are Codex's ambiguous
credentials: `U` holds `#` or `/`, so no host is shown, and nothing from the line up to the host
survives. Row 37 is suspect because its first segment holds `:` and an `@` follows.

## 2. Failure modes

1. A renderer reads the raw manifest instead of the display copy (leak 3 at `_show.py:134`).
2. A start rule needs a delimiter that the text does not have (leak 1, rows 30 and 31).
3. The scanner skips a string because it lacks `//` (leak 2).
4. A value derived from the raw manifest outside the copy reaches output: `compare_data` table
   names and `missing_files`, `library diff` output of `diff_payloads`.
5. The display copy is fed back to verify or fingerprinting, so verify checks the wrong path.
6. Redaction is not idempotent: a second pass over shown text changes it or breaks it.
7. Over-redaction erases ordinary findings text (`// WARNING ...`, `/var/run//deploy@prod`,
   rows 47, 48).
8. A display copy is not JSON serializable, so `--json` crashes instead of printing.
9. A parser stops the authority at `/ ? #` or whitespace inside a password and shows part of the
   password as host or port (rows 27, 28, 36, 37, 45).
10. Two keys display the same and one silently overwrites the other (rows 35, 41, 42).
11. A path field skips free-text scanning, so a `//` inside it is shown raw (row 32).
12. Text is composed before display, so a separator (`row_counts.`) blocks a start, a prefix
    (`[:16]`) cuts a URL into a host-like stub, or a basename turns a URL into a bare token
    (rows 26, 38, 39, 40, 50).
13. One display surface (library show) uses a different field policy from the others (row 43).
14. A public entry point changes its input contract (`render_html(dict)`).

## 3. Acceptance tests

Red before green: A1 to A3 and A10 fail at `c708039bf` on rows 1 to 7, 25 to 28, 30 to 32, 35 to
46 and 50. Builders may add tests; none of these may be weakened.

- **A1 unit table** `tests/unit/test_safe_url.py`: scanner rows of section 1 through `display_text`
  (text rows) and `display_location` (path field rows), exact output. Rows 27, 28, 36, 37, 45, 51 and the unprefixed locator in 52
  also through `build_manifest`: the writer records `(remote location)`. Rows 7, 25, 26, 35, 38 to
  43 and 50 are asserted at their own boundary, not through `display_text`: the card's row-counts
  table and the JSON key (7), `EvidenceIssue.message` (25, 39), `exc.message` and `str(exc)` (26,
  38, 40), the `DisplayCopy` mapping with every original count present once (35, 41, 42), the
  `library show` JSON and terminal record (43), and the `report diff` terminal line (50).
- **A2 property, in-process** `tests/unit/report/test_display_boundary.py`. Start with a real
  build_manifest result. Use typed warnings, strategies, timings, scan_baseline and one CLI-only
  additive field. Rotate a unique lowercase sentinel over free string leaves and dynamic keys.
  Keep the literal schema, producer, hash, method, format and numeric fields valid. For legacy
  fixtures omit both binding keys. For project fixtures set path_base to project and point
  project_manifest at the fixture's actual relative location. Recompute compute_manifest_hash
  after edits. Exercise legacy noncanonical digests only in separate CLI-only preview cases.
  Assert every planted leaf or key at its corresponding path in report show JSON. For the card,
  rendered documents and diff commands, check absence throughout and assert a positive witness
  only in a field the surface renders. Check document text after markup decoding. For fields
  omitted by a view, verify its normal output (such as the warning count) and use JSON for the leaf.
  Carriers (the secret sits on both sides of each delimiter): `https://u:{S}@h/x`,
  `https://{S}:pw@h/x`, `https://h/hook/{S}`, `https://h/x?t={S}`, `//h/p#{S}`, `//u:{S}@h/p`,
  `https:/u:{S}@h/x`, `/project/https:/u:{S}@h/in.csv`, `<https://h/hook/{S}>`,
  `URL:https://u:{S}@h/x`, `,https://u:{S}@h`, `;https://u:{S}@h`, `|https://u:{S}@h`,
  `https://u:{S} {S}@h/x`, `//share/https://u:{S}@h/f`, `//share/https:/h/hook/{S}`,
  `https://u:{S}#{S}@h/x`, `https://u:{S}?{S}@h/x`, `https://u:{S}/{S}@h/x`,
  `postgresql://admin:{S}#Secret {S}@db.example/prod`, `//u:{S}/{S}@h/x`, `` `//u:{S}@h/x` ``,
  `12://u:{S}@h/x`, `/data/a=//u:{S}@h/x`.
  Add row 51 with and without userinfo, the bare reference in row 52, and unchanged row 47.
- **A3 e2e**. Use two different legacy manifests A and B from real pipeline/CSV fixtures.
  Follow `test_library_read_commands.py::_evidence` and the existing envelope builder. Use
  `cli-local-1`, `decoy-cli`, actual sha256 fingerprints, method `full`, integer sizes/counts,
  supported format, and the registered evidence payload schema. Keep CLI-only extras out of
  writer fixtures. Rehash each final manifest, store both records and assert both decode as known.
  Use a shared carrier key in both records (row 59). Change that table's file contents, recorded
  digest and count, add one table in B, and give B one warning with code `probe`, provider null,
  row-60 column and detail {}. Preserve A's original files for a successful verify.
  Run _reader_routes on B, substituting A,B for both same-file diffs. Also run library show B
  and library diff A B in both formats. Check expected exits, both streams and fresh written
  reports for every sentinel. Read show JSON by field, library show by envelope payload, card by
  warning count and row-count table, HTML and Markdown by their row-count tables. Verify success
  by summary or zero issues. In both diffs assert the displayed changed table and delta in the
  corresponding list/terminal section. Library diff shows warning codes (row 61).
  Use separate fixtures for the following cases:
  - Rows 26, 38, 40: malformed entry, malformed count and invalid JSON; assert their exact
    displayed diagnostics and EXIT_USAGE. Rows 25, 39: CLI-only verify of an existing changed file
    with a URL-shaped recorded digest and table key; expect EXIT_FINDINGS and the safe issue.
  - Rows 53, 54, 62: keep a valid non-null pipeline fingerprint. For 53 set project_manifest to
    a relative name, omit --project, and isolate the fixture from markers. For 54 pass a valid
    marked project and a different recorded relative location. For 62 match the recorded manifest
    location and reject the relative climb. Assert read_manifest exception kind, message and
    str(exc), and verify terminal/JSON refusal text, EXIT_USAGE and no sentinel. Separately pass
    a nonexistent explicit project under a carrier path to the project-bound verify route.
  - Rows 55, 64: add same-schema future_metadata to encoded sample-run envelopes, recompute
    payload_digest and record id and write canonical bytes as in the opaque fixture. Verify both
    decode as known. Change the raw leaf, diff the stored IDs, assert the exact changed pointers
    in JSON and the terminal list. Use a separate collision fixture for two different raw sibling keys displaying alike and
    require both change entries, plus an ordinary sibling exercising RFC 6901 escaping.
  - Row 56: extend the existing opaque/newer test. Use a valid relative pipeline label and put the marker in the unreadable
    payload before recomputing its digest and ID. Assert success, displayed envelope and omitted payload in both modes;
    retain the distinct newer-schema status and notice for the known kind.
- **A4 hypothesis** `tests/unit/test_safe_url.py`: text = prefix + carrier + suffix. S2 carriers
  get a prefix that ends in an admitted boundary only (start of text, whitespace, or one of
  `` <>:,;|'"([{=*` ``); S1 carriers get any prefix. Assert `S` is absent from
  `display_text(text)`, and `display_text(display_text(t)) == display_text(t)` (failure mode 6).
- **A5 no-op bound**: hypothesis text with no `:/` and no `//` is returned unchanged (failure mode
  7); rows 9 to 11, 22, 24, 47 and 48 stay unchanged. Separately, a `//` carrier after each path
  character `[A-Za-z0-9._~/\-]` is returned unchanged (the named limit in section 7).
- **A6 verify keeps raw**: existing drift cases (`payroll@2026.csv`, `#`, `?`, `?year=2026` in both
  project layouts) still report drift after an edit. New cases where display and raw differ, made
  under `tmp_path` and recorded with a leading `//` (Linux reads `//tmp/...` as `/tmp/...`):
  `"/" + str(tmp_path / "share/payroll#2026.csv")` and its `?2026.csv` counterpart show as
  `//tmp` and still report drift after an edit. A legacy entry of row 4 still resolves and reports
  missing.
- **A7 sentry self-test**: the unmutated tree passes; each seeded mutation in section 5 fails with
  the rule ID it seeds and no other rule.
- **A8 strictness link**: for every single-token `x` from the A4 generator, `S not in
  display_text(x)` implies `S not in display_location(x)`, and
  `display_text(display_location(x)) == display_location(x)`.
- **A9 return types and collisions**: `display_copy("s")` is `str`, a list or tuple gives `list`, a
  dict gives `DisplayCopy` at every depth; rows 35, 41 and 42 in insertion order, and the values of
  the shown mapping equal the input values as a multiset.
- **A10 public renderers**: `render_html(raw_dict)` and `render_markdown(raw_dict)` with a row-7
  key and a row-36 path return text with no secret and the shown host; passing a `DisplayCopy`
  gives the same text. The 19 existing direct calls in `tests/unit/test_report.py` stay as they
  are (raw dicts) and pass.

Ported tests (port, never delete): `tests/sentry/test_report_raw_value_isolation.py` (renderer
inputs become `DisplayCopy` for the private document functions only),
`tests/e2e/cli_fmt/test_credential_paths.py:128,151` (patch `display_manifest` instead of
`redact_manifest_paths`; the tagger marks every leaf and table-name key, `row_counts` included).

Test depth: T0 per edit, T1 per commit. The slice head runs the full suite (diffed against the saved
main baseline), because changed tests, sentry tooling and changed `decoy.cli.report` exports are
escalation triggers.

## 4. Design and choke point

Survey of established redactors (sources read on 2026-11-28; source files under
`~/scratch/d6m-survey/` or the installed package):

- CPython 3.11.2 `urllib.parse` (`_NetlocResultMixinStr`): the netloc ends at the first `/ ? #`;
  userinfo is split off with `netloc.rpartition('@')` (last `@` in the authority). Checked:
  `urlsplit("postgresql://admin:2024#Secret word@db.example/prod").hostname` is `admin`.
- urllib3 2.7.0 `urllib3/util/url.py`: `_URI_RE` ends the authority at `\ / ? #`, then
  `authority.rpartition("@")`. Checked: the same DSN gives host `admin`, fragment
  `Secret word@db.example/prod`.
- yarl 1.25.1 `yarl/_parse.py`: `split_url` ends the netloc at the first `/ ? #`; `split_netloc`
  uses `netloc.rpartition("@")`. `URL.origin()` drops user, password, path, query and fragment.
- SQLAlchemy 2.0.50 `sqlalchemy/engine/url.py`: `_parse_url` takes `username` as `[^:/]*` and
  `password` as `[^@]*`, so a password may hold `/ ? #` and spaces but ends at the first `@`.
  `URL.render_as_string(hide_password=True)` prints `***`. Checked: `postgresql://u:12/ss@h/x`
  renders `postgresql://u:***@h/x`, but `postgresql://u:p@ss@h/x` gives host `ss@h` (shown).
- libpq (PostgreSQL master `src/interfaces/libpq/fe-connect.c`, `conninfo_uri_parse_options`):
  "Look ahead for possible user credentials designator" scans to the first `@` or `/`; a `/` first
  means no credentials. A password may hold `? #` and spaces, not `/`.
- git (master `transport.c`, `transport_anonymize_url`): takes the first `@` (`strchr`), keeps the
  URL literal when a `/` after `://` comes before it ("@ past the first slash does not count"),
  and requires an RFC 1738 scheme. `urlmatch.c` `url_normalize` uses the first `@` before the first
  `/ ? #`.
- pip 26.1.2 `redact_auth_from_url`, sentry-python `sanitize_url`, detect-secrets
  `BasicAuthDetector`: as in revision 2 (parse with `urlsplit`, split on the last `@`, keep host;
  detect-secrets anchors on `://` with no left boundary).

Finding: the parsers can also disagree on where the host ends when the authority contains `\`.
RFC parsers (CPython, urllib3, yarl, pip, Sentry) take the last `@` before the first `/ ? #`;
DSN parsers take the first `@` (libpq, git, SQLAlchemy), and SQLAlchemy lets `/ ? #` and spaces
into the password. No surveyed tool handles both, and none fails closed: each prints whatever host
its own rule finds. Chosen rule: treat everything from the authority start to the last `@` on the
line as userinfo (the widest reading any of them could take), and show a host only when `U` holds
no whitespace and none of `/ ? # @`, and the backslash check in step 3 passes.
Otherwise `(remote location)`. The shown form is built from parsed parts (pip, Sentry, yarl
`origin()`), never by deleting from raw text, and drops the path because a webhook URL carries its
token there. The single boundary follows cross-cutting-concerns.md (one choke point plus a sentry).

Pieces in `safe_url.py`:
- `safe_url_parts` unchanged in contract (host or `None`); `remote_location(raw, local_file)`
  (writer) uses the step 3 and step 4 rules for its `://` and suspect `//` branches and keeps its
  `local_file` check for ordinary shares, so the writer records `(remote location)` for rows 27,
  28, 36, 37, 45, 51 and 52 (whole locators).
- `display_location(raw)` (L1 to L4), `display_text(text)` (steps 1 to 6), and
  `display_file_name(path)`: `shown = display_location(str(path))`; return `shown` when it differs
  from `str(path)`, else `path.name` (display first, basename after).
- `display_copy(value, location_fields)`: `str -> str`, `list | tuple -> list[object]`,
  `dict -> DisplayCopy` at every depth, other values unchanged. Keys use `display_text`; a key whose
  shown form is already taken gets the smallest ` (n)`, n >= 2, not yet taken; keys are taken in
  insertion order and a later key never displaces an earlier one (rows 41, 42). `DisplayCopy` is a
  `dict` subclass (JSON serializes as is), built only by `display_copy`.
- `location_fields(pointers, prefix)`: turns JSON-pointer patterns such as
  `/payload/input_fingerprints/*/path` into key paths. `display_safe(value)` stays as
  `display_copy(value, frozenset())`. `display_path` becomes `display_location(str(path))`; the
  `^`-anchored `_COLLAPSED_SCHEME` is replaced by step 2.

Pieces in `evidence.py`:
- `evidence_location_fields()` (cached): `location_fields(kind_spec("evidence").path_fields,
  "/payload/")`, read lazily from the pinned engine, so `scan_baseline.path` is included and the
  list has one owner (Codex 3). `display_manifest(manifest) -> DisplayCopy` replaces
  `redact_manifest_paths`; `manifest_hash_ok(manifest) -> bool`; `digest_preview(value, width)`.
- **Built clean** (Codex 2): `_field(group, table, leaf)` joins `display_text(table)` into every
  field name (`_check_fields` prefix, both `_malformed` table sites, `_stored_files`, so resolver
  refusals too). `ManifestError.__init__` runs `display_text` on the message before
  `super().__init__`, so `exc.message` and `str(exc)` match (second layer only). Verify builds path
  text with `display_location(raw)`, the table label with `repr(display_text(table))`, and every
  digest with `digest_preview`: `value[:width] + "..."` only when `value` matches
  `re.fullmatch(r"sha256:[0-9a-f]{64}", value)` for a string, else `(not a digest)`. `report diff`'s `_fp_short` calls
  `digest_preview(fp, 23)` for a present fingerprint and keeps `(none)` for a missing one. The parse refusal, `_verify.py:134,140` and `_manifest_root` at evidence.py:601
  call `display_file_name` on the full path before formatting. Keep `the manifest` for None.
- At evidence.py:310 the non-file relative source fallback has no file to verify. Write
  `display_location(declared_path)` there. Seed `relative/https:/h/hook/marker` on that branch
  in A1 and assert `(remote location)` and a null fingerprint in the built manifest. Ordinary
  relative source names and paths used for hashing retain their existing behavior.
- `evidence.py` net size: `redact_manifest_paths` (-10) offsets the new helpers; the file stays at
  or under its current 770 lines.

Choke point:
- Each report command loads the raw manifest once through `_load_manifest` and passes it only to
  `display_manifest`, `manifest_hash_ok`, `verify_manifest`, `compare_manifests` or
  `compare_data`. `compare_manifests`, `compare_data` and `diff_payloads` return raw-derived
  dicts, so their result goes straight into `display_safe(...)`: `report diff` wraps the first two;
  `library diff` wraps `diff_payloads` at `_read.py:226` (the `_diff.py:65` call is a forwarder).
  In library/_diff.py:115-140 keep tuples of raw components through leaf matching, ordering and
  value comparison. For each changed/added/removed tuple, display each key with display_text,
  escape each shown component (~ to ~0, / to ~1), then join under /payload. Keep list indices.
  Append one output per raw difference, even when two displayed pointers coincide. Never key a
  comparison map or set by the displayed pointer. Hash original payloads.
  `compare_data`'s `_skip` uses `display_location` for paths (location rule at the source).
- `verify_manifest` and `verify_manifest_issues` are clean producers: every message is composed
  from displayed parts (above). `ci/adapters.py:229-236` sends only `issue.message` and
  `ManifestError` text, so it needs no wrap.
- Renderers: the private document functions (`_html_document`, `_markdown_document`,
  `render_manifest_card`, `_render_manifest_compare`, `_render_data_diff`) take a `DisplayCopy` and
  check `isinstance` at entry. Public `render_html(manifest: Mapping[str, Any])` and
  `render_markdown(...)` keep their documented dict input: a `DisplayCopy` passes through, anything
  else goes through `display_manifest` first (Codex 4). Commands build the copy once and pass it.
  The row-counts table moves into `render_manifest_card`, so terminal and JSON read the same copy.
- `library show` (Codex 3): `shown = display_copy(record_without_unreadable_payload,
  fields)` over the whole envelope. Start with an empty field policy. For a known, readable
  record use `location_fields(spec.path_fields, "/")` from `kind_spec(kind)`. For opaque or newer
  records omit payload first and use the empty policy. Read every printed field, including the
  JSON wrapper's payload_schema, from the displayed envelope;
  terminal and JSON both print `shown`. Evidence records thus get the same field policy as
  `report show` (row 43), and run-result and sample-run paths get theirs.
- Raw stays raw: `_stored_files`, `resolve_manifest_path`, `hash_file`, the fingerprint and
  verify reads.

## 5. Sentry

`tests/sentry/defects/test_report_display_boundary.py`, registered in
`tests/sentry/test_sentry_manifest.py` (`SENTRIES`) and `scripts/dev/sentry_registry.toml`. Calls are
resolved with `tests/sentry/io_policy/_calls.py` (as in
`tests/sentry/cli_text/test_json_command_names.py:37,219-225`). The resolver binds imports only, so
the sentry adds module-level `def` names of the scanned module itself (a bare same-file call
resolves to `module.name`). Recognize both `decoy.cli.library.diff_payloads` and the defining
  module after resolving aliases. Keep `_calls.py` unchanged. Add no baseline or allow-list entries.

- R1 (`decoy.cli.report.*`, `decoy.cli.library.*`): `read_manifest` is called only as `return
  read_manifest(...)` inside `decoy.cli.report._shared._load_manifest` (the one forwarder). A call to
  `_load_manifest` appears only as the right side of a plain name assignment. A name so bound is
  loaded only as a direct positional argument of `display_manifest`, `manifest_hash_ok`,
  `verify_manifest`, `compare_manifests` or `compare_data`. Subscript, `.get`, iteration,
  f-string, any other call, and an inline call such as `render_html(_load_manifest(...))` fail.
- R2 (`src/decoy`): a call to `compare_manifests`, `compare_data` or `diff_payloads` is the direct
  argument of `display_safe(...)`, except the exact forwarder
  `decoy.cli.library._diff._evidence -> compare_manifests`. The sentry also asserts that each
  forwarder's own callers are R2 producers or wrapped (`_evidence` is reached only from
  `diff_payloads`), and that the forwarder list matches the unwrapped sites found, so a stale
  exception fails. `verify_manifest` and `verify_manifest_issues` are clean producers, not R2
  sinks; A2, A3 and A10 hold their text.
- R3 (functions, not modules): each private document function in section 4 annotates its
  manifest or diff parameter `DisplayCopy`, and its body names none of `read_manifest`,
  `_load_manifest`, `redacted_location`, `compare_manifests`, `compare_data`. Public
  `render_html` and `render_markdown` pass their parameter to `display_manifest` (or the
  `isinstance` pass-through) before calling the document function. `_diff.py` may keep its command
  and its two renderers in one module.
- R4: `DisplayCopy(` is called only inside `safe_url.py`.

Seeded in-memory mutations (A7). On the final implementation head run a green unmutated scan, apply each seed separately to that same head and assert the exact singleton rule ID:
1. R1: in `_show.py`, read `manifest.get("row_counts")` for the table again (leak 3).
2. R1 inline, alias: in `_render.py`, `from decoy.cli.report._shared import _load_manifest as lm`
   then `render_html(lm(...))`.
3. R2: in `report diff`, drop `display_safe(` around `compare_data(...)`.
4. R2 alias: in `library/_read.py`, `from decoy.cli import library as lib` then an unwrapped
   `lib.diff_payloads(...)`.
5. R2 stale forwarder: add an unwrapped `compare_manifests` call to a second function in
   `library/_diff.py`.
6. R3: annotate `_html_document`'s parameter `dict[str, Any]`.
7. R3 public entry: `render_markdown` calls `_markdown_document(manifest)` without
   `display_manifest`.
8. R4: build `DisplayCopy({})` in `_show.py`.

## 6. Files to change

| File | Change |
|---|---|
| `src/decoy/safe_url.py` | steps 1 to 6; `display_location`, `display_text`, `display_file_name`, `display_copy`, `DisplayCopy`, `location_fields`; writer `remote_location` uses steps 3 and 4; drop `_display_text` and `_COLLAPSED_SCHEME` (stays under 600 lines) |
| `src/decoy/cli/evidence.py` | `evidence_location_fields`, `display_manifest`, `manifest_hash_ok`, `digest_preview`, `_field`; `ManifestError` cleaned; verify text built clean; remove `redact_manifest_paths` (no net growth) |
| `src/decoy/cli/report/_show.py` | one `display_manifest` call feeds JSON, card and files; row-counts loop removed |
| `src/decoy/cli/report/_render.py`, `_markdown.py`, `_html.py` | public entries keep dict input; private document functions take `DisplayCopy` |
| `src/decoy/cli/report/_diff.py`, `_compare.py` | `display_safe` around `compare_manifests` and `compare_data`; renderers take `DisplayCopy`; `_fp_short` uses `digest_preview`; `_skip` uses `display_location` |
| `src/decoy/cli/report/_verify.py` | `display_file_name` for the two summary lines |
| `src/decoy/ui/evidence_card.py` | takes `DisplayCopy`; renders row counts |
| `src/decoy/cli/library/_read.py` | `show_command` uses `display_copy` with the kind's `path_fields`; `display_safe` around `diff_payloads` |
| `src/decoy/cli/library/_diff.py` | compare raw component tuples; display individual keys before RFC 6901 escaping |
| tests | per the placement table below |
| `CODEMAP.md` | `safe_url.py` line names `display_location`/`display_copy`; sentry row lists the new sentry |

Placement of tests:

| Test | File | Tier |
|---|---|---|
| A1, A4, A5, A8, A9 | `tests/unit/test_safe_url.py` | unit |
| A2, A10 | `tests/unit/report/test_display_boundary.py` (new) | unit |
| A3, A6 | `tests/e2e/cli_fmt/test_credential_guard.py` | e2e |
| A3 library show/diff | `tests/e2e/library/test_library_read_commands.py` | e2e |
| A7 and the sentry | `tests/sentry/defects/test_report_display_boundary.py` (new) | sentry |
| ported | `tests/sentry/test_report_raw_value_isolation.py`, `tests/e2e/cli_fmt/test_credential_paths.py` | as now |

Size: about 12 source files, about +190/-100 source lines; new public names `display_location`,
`display_text`, `display_file_name`, `display_copy`, `DisplayCopy`, `location_fields`,
`display_manifest`, `manifest_hash_ok`, `digest_preview`. No new source module.
`redact_manifest_paths` is removed (a changed export; full suite on the slice head).
`render_html` and `render_markdown` keep their signatures.

## 7. Over-redacted on purpose

| Input | Shown | Why accepted |
|---|---|---|
| Any `word:/...` in text, e.g. `note:/tmp/x` | `note://tmp` | S1 cannot tell a label from a scheme; a missed scheme leaks |
| `/project/https:/u:p@h/in.csv` path field | `(remote location)` | a path that holds a URL has no single correct display host |
| `//host/share/f?2026.csv` in a `//` path field | `//host` | display cannot check that the file exists; the writer keeps the fingerprint |
| `//server/share/payroll#2026.csv` path field (row 34) | `//server` | a `#` may start a fragment token; same reason as `?` |
| `https://h/x@2026.csv` (row 29) | `(remote location)` | an `@` after `/` may end a password (SQLAlchemy reading, row 28) |
| `file:///data/x.csv` (row 33) | `(remote location)` | no host to show; a `file://host/` form shows `file://host` only |
| A scheme URL and a later `@` on the same line (rows 46, 49) | `(remote location)` through that `@`'s host | the last `@` on the line may end a pasted password |
| `https://user:pass word@host` (row 15) | `(remote location)` | cannot be told from `https://h:8443 text@other` |
| Text after `//user:pw@host` up to the last `@` on the line (row 16) | `(remote location)` | a password may hold spaces and `@` |
| `//a/x,//u:pw@h/y` with no space (row 17) | `(remote location)` | one token with two authorities has no safe split |
| Path, query and fragment of every scheme URL, even a public one | `scheme://host` | a webhook URL carries its token in the path |
| Trailing punctuation inside a span that does not close an opener, e.g. `https://h/x.` | `https://h` | the body runs to whitespace |
| `at 12://u:p@h/x` (row 31) | `at (remote location)` | no valid scheme to show |

Not redacted on purpose: one-letter schemes (`C:/`); secrets with no URL shape (bare tokens in
warnings); `//` after a path character (`/var/run//deploy@prod`, A5); an ordinary share whose
prefix fails the suspect tests in step 4 (`//share/u:PW@h` is read as a file name, the same
class as row 22).

## 8. Tracked outside this slice

- **V1, ENGINE-EXPORT-REMOTE-PATH.** Open product V1 outside #416. The pinned engine's
  _export_rules.py:23 takes the final segment before it can recognize a webhook or query.
  _kinds.py:49 keeps structured warning columns, and fingerprint-map and row-count keys survive
  unchanged. Keep envelope labels valid under their separate RelPath/SafeName rules. Fix at the engine default export boundary, before basename extraction. Use the
  registered kind rule for paths and existing warning/layout scrub, and one shared transform for
  emitted names, labels and retained strings. Preserve local basename behavior and all mapping
  entries on collisions. Route changed payloads/labels through existing digest, ID and link
  rewriting. Record remote removal in the existing unstripped header and preserve --keep-paths,
  claim and withholding behavior.
  Engine acceptance uses real decoded evidence records (A3). Assert the emitted record lines
  themselves against rows 57 to 60, with ordinary valid envelope labels independent of payload map keys, plus rows 6, 36, 37,
  51 and 52 as complete path values. Assert the expected safe host or placeholder in each
  named field, original counts and code, empty warning detail and zero sentinel occurrences in
  default export bytes. Decode the exported records and verify IDs. Repeat with --keep-paths
  and assert the exact original carriers in the corresponding record fields. Close this row
  with the engine release and CLI repin under the engine-repin checklist.

## V2-LOG (recorded, not built in this slice)

- A target with no `type` given to `build_manifest` directly loses the fingerprint of
  `//.../output#2026.csv` (round 7; the pinned engine requires an explicit type).
- `user:pw@host` with no scheme and no `//` is not redacted (a rule would also hit
  `mailto:ops@example.com` and `12:30@lunch`).
- S1 is quadratic on long letter runs before `:`; add a prefilter on `:/` and `//` before scanning.
- `note:/tmp/x` would be more truthful as `(remote location)` than `note://tmp`.
- `report diff` shows `https://h -> https://h` when only the credentials differ; it should say
  that the credentials changed.
- Rows 46 and 49 swallow an email on the same line as a URL; a later rule could stop at a sentence
  boundary once a corpus of real warnings shows it is safe.

## Revision 4 review

GO for the #416 plan at c708039bf. Rows 51 to 64 were traced against the CLI and engine
contracts. A7 remains an implementation gate on the test nodes. The engine V1 in section 8
stays open outside #416 until default export passes its record-content assertions.
