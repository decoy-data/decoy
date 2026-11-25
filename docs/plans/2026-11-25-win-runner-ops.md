Status: plan

# WIN-RUNNER ops: nightly Windows runs, node-watch entry, runbook (roadmap row 6)

Owner: Cam. Author: Opus planner. Date: 2026-11-25. Revision 1.

Rules consulted: `dev-rules/README.md`, `00-universal.md`, `development-loop.md`,
`risk-and-exceptions.md`, `autonomous-operation.md`, `observability-and-resilience.md`,
`profiles/local-operations.md`; owner memory rules: V1 bar, PLAN defines acceptance tests, root
cause not patch, edit live scripts atomically, one test runner per box, Mac first for tests,
report times in CST, Slack in plain language, release and Windows rows last, test depth T0 to T4.

Risk: R1 for WL2, WL3 and WL4 (bounded, reversible devbox tooling and docs). WL1 changes
`win-run`, which gate readers use as gate machinery, so it takes the risky-slice review tier
(Dennis then Codex) while staying reversible (the old file is kept as a `.bak`).

Bases: CLI `origin/main` at `fffca916`; the WIN-FEAS plan on `plan/win-feas` (revision 3,
`docs/plans/2026-11-18-win-feas.md`, section 4.3 and the WR row); the lane record
`docs/records/2026-11-18-win-lane.md` (CLI #323); the live tooling `~/bin/win-run` (85 lines),
`~/bin/win-run.d/winrun.ps1` (150 lines), `~/bin/win-run.d/winrun_plugin.py` (22 lines) and
`~/bin/node-watch` (373 lines), read on 2026-11-25. Notation: `C:` is the CLI repo, `B:` is
`~/bin` on the `.55` devbox (copied daily into the private `agent-config` repo by
`agent-config/sync.sh`).

## 0. Summary for the owner

Row 6 (`C:docs/roadmap/groups/release.md:19`) is PARTLY MERGED. The Windows proof lane on the
Dell's Windows 11 side works and gate readers use it (31 logs in `~/.cache/win-run/logs/` on
2026-11-25). The record lists three items still open (`C:docs/records/2026-11-18-win-lane.md:108`):
nightly runs on both `main` heads, a node-watch entry, and a dated vault runbook. Reading the
tooling found two more gaps that the nightly and node-watch work needs:

- `win-run` appends its `DONE` line to a hard-coded queue log inside a dead session scratchpad
  (`B:win-run` line 38). Nothing reads it, so a finished Windows job wakes nobody.
- The timing-retry rule in WIN-FEAS 4.3 (one retry on the same clean SHA and lock hash, both
  logs kept, a second failure is red) is prose only. Nothing links a retry to its first attempt
  or stops a third attempt.

Four slices close the row. All four are devbox and vault tooling plus CLI docs. None touches CLI
or engine product code, the release rows (88, 90 to 94, UPGRADE-KEY) or the row 89 WIN-FEAS
product slices. **All four can be built now** without changing the "release and Windows last"
order (section 12.2).

Owner calls (section 13): Rust and MSVC Build Tools on the Dell (licence), what happens when the
Windows Update pause ends on 2026-12-04, and the row 6 text, which still says "GCP VM" although
owner answer Q5 ruled out a cloud VM.

## 1. FRAME

### 1.1 Problem

The lane runs only when a gate reader calls it. A Windows regression that reaches `main`
through a slice outside the WIN-FEAS path set (`docs/plans/2026-11-18-win-feas.md:515`) shows
up only at the next Windows-touching gate, possibly days later, and is then blamed on the wrong
slice. A queued, stalled or finished Windows job is invisible to the orchestrator: node-watch
knows the Dell only as the WSL node `dell-wsl` (`B:node-watch` line 40), and the `DONE` line goes
to a dead file. The recovery steps (Dell reboot, ssh key, update pause, venv reset, stuck lock)
exist only in a memory note.

### 1.2 Guarantee

After this plan:

1. Every night both `main` heads (CLI and engine) run the enabled lane jobs. Each job ends in
   exactly one verdict: `green`, `red`, `not-run` (with a reason) or `disabled` (with a reason).
   A job that did not run is never `green`.
2. A new red, a new not-run or a missed nightly reaches the orchestrator through node-watch
   events and reaches Cam through one plain-language Slack line. An unchanged known red does
   not repeat on Slack.
3. node-watch shows the Windows lane as its own node `dell-win`: busy or idle, job and age,
   queued waiters, free memory, free disk, Windows build and update-pause end date. It raises
   START, DONE, QUEUED, STALLED, UNREACHABLE, DISK, BUILD, PAUSE, LOCK-FOREIGN, NIGHTLY-MISSED
   and NIGHTLY events.
4. A retry is a second `win-run` call that names its first attempt. It must use the same SHA
   and lock hash. A first attempt can have at most one retry. Both logs stay.
5. A dated runbook in the vault tells an agent or Cam how to run, read, retry and recover the
   lane.

### 1.3 Out of scope

- A GitHub Actions runner or a cloud VM (owner Q5, 2026-11-18). OC3 corrects the row text.
- The row 89 product slices (EW2 to EW5, CW1 to CW8, R0) and their tests. They only add paths
  to the nightly job catalog when they merge (section 4.2).
- The pve2 Windows 11 evaluation VM release-build floor (WIN-FEAS 4.3, row 94). It runs at the
  CW5 and CW6 merge heads, not nightly.
- The engine companion wheel build on Windows until OC1 is answered.

### 1.4 Failure modes this plan designs against

| ID | Failure mode | Slice | Closed by |
|---|---|---|---|
| FM1 | The nightly tests a stale `origin/main` (the CLI clone once lacked a fetch refspec) | WL2 | `ls-remote` compare, AT-6 |
| FM2 | A catalog path is absent at the head, so pytest exits 4 (usage error); several recent lane logs end `EXIT 4` | WL2 | path filter, AT-7 |
| FM3 | A test folder is moved or deleted and the nightly silently runs less | WL2 | `GONE` flag, AT-7 |
| FM4 | Low Windows memory (exit 75) or a stall (exit 124) reads as a pass or as a test failure | WL1, WL2 | verdict table, AT-5 |
| FM5 | The `DONE` line goes to a dead file and nobody wakes | WL1 | lane event log, AT-1 |
| FM6 | Retry chains (attempt 3, 4 until something passes) or a retry on another SHA | WL1 | retry rule, AT-4 |
| FM7 | Two nightlies overlap after a slow night | WL2 | non-blocking nightly lock, AT-8 |
| FM8 | The devbox cron or the devbox is down and no nightly runs, unnoticed | WL3 | NIGHTLY-MISSED, AT-13 |
| FM9 | Windows reboots for an update (also killing the WSL CI runners) and nobody notices | WL3 | BUILD and PAUSE events, AT-13 |
| FM10 | An orphan job or another identity holds `C:\dc\win-run.lock`; every job waits 60 minutes, then exits 255 | WL3 | LOCK-FOREIGN, AT-13 |
| FM11 | The node-watch probe hangs the 2-minute cron | WL3 | ssh timeouts, AT-12 |
| FM12 | A nightly red repeats on Slack every night and Cam stops reading it | WL2 | change-only Slack, AT-9 |
| FM13 | Test output text (which can hold data values) leaks into Slack or the results file | WL2 | ids and codes only, AT-9 |
| FM14 | A live edit to `win-run` or `node-watch` breaks a running job or a cron poll | all | atomic edit rule, section 11 |

## 2. Established solutions (survey)

Searched: the vault and memory notes (`win-run`, `node-watch`, nightly, T4), the WIN-FEAS plan,
the lane record, and the existing `~/bin` tools; plus how common CI systems model these states.

- "Not run" as its own state: Buildbot and GitHub Actions keep `skipped` and `cancelled` apart
  from `success`. WIN-FEAS already says "a Windows job that did not run is 'not run', never
  green" (`docs/plans/2026-11-18-win-feas.md:521`).
- Linked retry attempts: GitHub Actions "re-run" keeps attempt 1 and attempt 2 under one run id
  and never hides attempt 1. pytest-rerunfailures marks reruns in the report. This plan copies
  "linked attempts, both kept" and adds a hard cap of one retry.
- Change-only alerts: Prometheus Alertmanager notifies on state change, not on every
  evaluation. node-watch already dedupes with its `alerted` set (`B:node-watch` near line 318);
  this plan reuses it.
- Observing a Windows lock without holding it: an open with `FileShare.None` fails while another
  handle is open. The probe opens and closes at once (section 3).
- Custom code is still needed because no off-the-shelf tool drives a Windows host over ssh from
  this devbox with the lane's exact-head proof; the new code is small glue around the existing
  `win-run` and `node-watch`.

## 3. Design notes

No new abstraction: one new script (`win-nightly`) and one data file (`jobs.json`) beside the
existing tools. Each fact has one home: the job list in `jobs.json`, the verdict rules in one
`decide()` table, the lane state in `current.json` and the lane event log.

- **Lane event log.** `win-run` writes one line per finished job to
  `~/.cache/win-run/events.log`: `DONE <label> rc=<n> repo=<r> sha=<12 hex> <UTC time>`. It also
  appends the old-format line to `$WINRUN_QUEUE_LOG` when that is set, so a session that wants
  its own queue log still gets one. The hard-coded path goes away. node-watch reads the lane
  event log from a stored byte offset.
- **Holder file.** After `win-run` takes `~/.cache/winrun.lock`, it writes
  `~/.cache/win-run/current.json` (`label`, `pid`, `repo`, `sha`, `log`, `started`, `retry_of`)
  with write-to-temp then `mv`. A `trap` on EXIT, INT and TERM removes it. node-watch treats a
  file whose pid is dead as a stale holder (no job).
- **Label override.** `WINRUN_LABEL` sets the label when it matches `^[a-z0-9][a-z0-9-]{0,47}$`
  and no log of that name exists. The nightly uses `n<YYYYMMDD>-<job>-a<attempt>`. Anything else
  exits 2 before any ssh call.
- **Retry.** `WINRUN_RETRY_OF=<label>` marks a call as attempt 2. Before taking the lock: the
  first log must exist, must not itself contain a `win-run: retry of` line, must end with
  `EXIT n` where `n` is not 0, and its `SHA requested` must equal this call's HEAD; no other log
  may already carry `retry of <label>`. Otherwise exit 2. The new log carries
  `win-run: retry of <label> attempt 2` on its second line. After the run, the
  `lock ... sha256` lines of both logs must match; if not, the result is 255 with
  `win-run: retry lock hash differs from the first attempt`.
- **Nightly runner.** `B:win-nightly` (Python, stdlib only) runs from cron once a night. It
  keeps two dedicated worktrees, `~/decoy-nightly/win/cli` and `~/decoy-nightly/win/engine`,
  detached at `origin/main` of `/home/cam/vscode/decoy` and `/home/cam/vscode/decoy-engine`. It
  resets only paths under `~/decoy-nightly/win/` and refuses any other path. Per repo: fetch
  `main`, compare `origin/main` with `git ls-remote origin refs/heads/main`, check out the head,
  build each job's path list, call `win-run` per job, read the log, decide the verdict, retry
  where section 4.3 allows, and write the results.
- **Job catalog.** `B:win-run.d/jobs.json` is the one registry of lane jobs: `name`, `repo`,
  `paths` (repo-relative), `command` (with a `{paths}` slot) and optional `disabled` (a reason).
  Row 89 slices add their paths here when they merge. Gate readers use the same entries:
  `win-nightly --print-cmd <job> <worktree>` prints the `win-run` command for that head.
- **Results.** One TSV row per job attempt in `~/.local/state/win-nightly/results.tsv`, and
  `~/.local/state/win-nightly/fails/<label>.txt` with the failing test ids (from `FAILED <id>`,
  `ERROR <id>` and `WINRUN FAIL: ... <id>` lines). Only ids, exit codes and reasons are stored;
  test output text never leaves the log.
- **Windows probe.** node-watch sends one PowerShell script through
  `ssh dell-win powershell -NoProfile -EncodedCommand <b64>`, inside the existing `sh()` 40-second
  timeout and with `ConnectTimeout=8`. It prints `FREE <gb>`, `CDISK <gb>`, `BUILD <n>`,
  `PAUSE <yyyy-mm-dd|none|unknown>` (from `HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings`
  `PauseUpdatesExpiryTime`) and `LOCK held|free` (an open of `C:\dc\win-run.lock` with
  `FileShare.None`, closed at once). A free-lock probe can make a starting `win-run` wait one
  5-second retry (its loop at `winrun.ps1` line 36); that cost is accepted. `PAUSE unknown`
  never raises a PAUSE event.
- **Live edits.** Each change to a live file in `~/bin` is made on a copy, checked, then put in
  place with `mv`. The old file stays as `<name>.bak-<mmdd>`, as the other `~/bin` tools do.

## 4. Behavior

### 4.1 Nightly schedule

One crontab line:
`30 7 * * * $HOME/bin/win-nightly run >> $HOME/.local/state/win-nightly/cron.log 2>&1`.
07:30 UTC is 01:30 CST, when the owner is not working and the Dell gate runners are usually
idle. The engine runs first, then the CLI, inside one process (serial jobs in one command, never
chained waiters). Wall time is about 25 to 60 minutes with today's paths.

### 4.2 Job catalog (initial content)

| Job | Repo | Paths on 2026-11-25 `main` | State |
|---|---|---|---|
| `engine-win` | engine | `tests/windows`, `tests/fileaccess` | enabled |
| `cli-win` | CLI | `tests/unit/private_file`, `tests/e2e/private_file`, `tests/unit/distribution`, `tests/unit/library`, `tests/sentry/test_atomic_writer.py` | enabled |
| `engine-win-companion` | engine | the native companion wheel build | disabled: "Rust and MSVC Build Tools not installed (OC1)" |
| `demo-win` | CLI | fresh venv from candidate wheels, `decoy --version`, `doctor`, `demo --json`, quickstart, golden hash | disabled: "needs the E-REL Windows artifact (row 89 CW5)" |

Both enabled jobs run `%PY% -m pytest -q -p no:cacheprovider {paths}`. `win-run` already adds
`-p winrun_plugin -rs` through `PYTEST_ADDOPTS` (`winrun.ps1` line 129), so a skipped
`windows`-marked test still fails the job (`winrun_plugin.py:15`).

### 4.3 Verdict and retry table

The runner reads the log, never a summary line: the final `EXIT n` and whether the
`win-run: running:` line (`winrun.ps1` line 131) appears.

| Observed | Attempt 1 | Attempt 2 (only where retried) |
|---|---|---|
| `EXIT 0` | green | green, row notes "green on retry" |
| `EXIT 124` (stall or timeout) | retry at once | red |
| `EXIT 75` (low memory) | retry after 20 minutes | not-run: low Windows memory |
| `EXIT 255`, no `running:` line (ssh, install, bundle, venv or lock wait) | retry after 5 minutes | not-run: setup, with the last `win-run:` line as reason |
| `EXIT 255` after `running:` (log check failed) | red | n/a |
| any other non-zero after `running:` (test failures, pytest usage errors) | red, no retry | n/a |
| no log, or no final `EXIT` line | not-run: no result | n/a |

The nightly never retries a test failure. A gate reader who judges a test failure to be
runner-load timing may retry it once by hand with `WINRUN_RETRY_OF`; the gate record then names
both labels.

### 4.4 Path filter

Before each job the runner checks each catalog path with `git cat-file -e <sha>:<path>`. Present
paths fill `{paths}`. Absent paths go in the row as `absent=<p1>,<p2>`. With no present path the
job is `not-run: no catalog path at head`. A path that was present in this job's last row and is
absent now sets `GONE=<path>` and the verdict is red even if the rest pass (a moved or deleted
test is an escalation trigger and must be looked at).

### 4.5 Results and alerts

`results.tsv` columns, tab-separated, one row per attempt: `date_utc`, `repo`, `job`, `sha`,
`label`, `attempt`, `retry_of`, `exit`, `verdict`, `reason`, `fail_count`, `absent`, `gone`,
`windows_build`.

`win-nightly run` exits 0 when every enabled job is green, 1 when any is red, 3 when none is red
but any is not-run, 2 on a usage error. After the run it compares each job's final verdict and
failing-id set with that job's previous final row. Only on a change (a new red, a new not-run,
new failing ids, or red turning green) does it send one Slack line through
`~/.claude/scripts/slack-notify.sh manual`, in plain words with no SHAs, paths or test text. For
example: "Windows nightly: the CLI Windows tests started failing tonight (3 tests). The engine
Windows tests pass." A disabled job never triggers Slack.

### 4.6 node-watch entry

- Status line: `dell-win  BUSY <label> <age> | IDLE <age>  free <gb> GB  C: <gb> GB  build <n>  pause to <date>`,
  plus `queued <k>` when waiters exist and `last nightly <date> <verdicts>`.
- Busy means `current.json` names a live pid. Waiters are other live `win-run` processes
  (`pgrep -f '/bin/win-run '`) that are not the holder.
- Events, each raised once per state change through the existing `alerted` set:
  - `START dell-win <label>` when a new holder label appears.
  - `DONE dell-win <label> rc=<n>` for each new line in the lane event log.
  - `QUEUED dell-win <label> waiting <age>` when a waiter is older than 5 minutes.
  - `STALLED dell-win <label>` when the holder's log has not grown for 10 minutes (the job's own
    guard kills it at 15).
  - `UNREACHABLE dell-win` when the probe returns nothing, once per outage.
  - `DISK dell-win` when C: free is under 25 GB.
  - `BUILD dell-win <old> -> <new>` when the Windows build changes.
  - `PAUSE dell-win ends <date>` when the update pause ends within 3 days, and
    `PAUSE dell-win ended` once it has passed; at most once per UTC day.
  - `LOCK-FOREIGN dell-win` when the Dell lock is held for 10 or more minutes with no local
    holder.
  - `NIGHTLY-MISSED dell-win` when no `results.tsv` row has today's UTC date by 10:00 UTC.
  - `NIGHTLY dell-win <job> <verdict>` when a job's final verdict changes.
- The `/loop` hook already prints node-watch status and events. The documented Monitor grep
  gains `BUILD|PAUSE|LOCK-FOREIGN|NIGHTLY` (runbook and memory note, WL4).

## 5. Later (1.x)

- A weekly broad Windows census (the full CLI unit suite on Windows) once the CW slices land
  and the expected reds are gone.
- A nightly on the pve2 Windows 11 evaluation VM if the release-build floor starts to drift.

## 6. Enumerations

### 6.1 Exit paths

- `win-run`: 0 or the job's own code; 124 stall or timeout; 75 low memory; 255 setup, proof or
  log-check failure; 2 usage, a bad `WINRUN_LABEL` or a refused retry (new). `B:win-run` line 18
  and `C:docs/records/2026-11-18-win-lane.md:108` hold the old list.
- `win-nightly run`: 0 all green; 1 any red; 3 not-run without red; 2 usage. A refused second
  nightly writes its not-run rows and exits 3.
- node-watch `poll`: unchanged (errors go to `cron.err`).

### 6.2 Routes

- Gate route: a gate reader calls `win-run` on a gate or merge head
  (`docs/plans/2026-11-18-win-feas.md:519`). Unchanged apart from the lane event log.
- Retry route: a gate reader or the nightly calls `win-run` with `WINRUN_RETRY_OF`.
- Nightly route: cron calls `win-nightly run`, which calls `win-run` with `WINRUN_LABEL`.
- Watch route: cron calls `node-watch poll` every 2 minutes; the probe and the lane files feed
  it.
- Plugin route (unchanged): a skipped `windows`-marked test fails the job inside pytest
  (`winrun_plugin.py:15`); the nightly reads that as a red.

### 6.3 Fields

- `current.json`: `label`, `pid`, `repo`, `sha`, `log`, `started`, `retry_of`.
- Lane event line: `DONE`, label, `rc=`, `repo=`, `sha=` (12 hex), UTC time.
- `results.tsv`: the 14 columns of section 4.5.
- `jobs.json`: `name`, `repo`, `paths`, `command`, `disabled`.
- Probe lines: `FREE`, `CDISK`, `BUILD`, `PAUSE`, `LOCK`.

### 6.4 FK shapes

N/A: this plan moves no table data and handles no foreign keys; it runs test jobs and reads
their logs.

### 6.5 Output surfaces

- `~/.cache/win-run/logs/<label>.log` (same format plus the retry line).
- `~/.cache/win-run/events.log` and `~/.cache/win-run/current.json` (new).
- `~/.local/state/win-nightly/results.tsv`, `fails/<label>.txt` and `cron.log` (new).
- `~/.cache/node-watch/status.txt` and `events.log` (new `dell-win` lines).
- Slack: one plain-language line on change.
- The vault runbook and the CLI record (WL4).

## 7. Class table

| # | Class | Applies | Closing structure | Sentry or test | Mutation |
|---|---|---|---|---|---|
| 1 | value-free text | yes: results and Slack | only ids, codes and reasons leave the log, through one `fail_ids()` reader | AT-9 | M-11 copy the log tail into the Slack text |
| 2 | cleanup | yes: holder file, nightly worktrees | `trap` removes `current.json` on every exit; resets limited to `~/decoy-nightly/win/` | AT-3, AT-8 | M-3 remove `current.json` only on success |
| 3 | state | yes: verdicts and dedupe | one `decide()` table; node-watch `alerted` set and stored offsets | AT-5, AT-13 | M-6 map 75 to green |
| 4 | route | yes: gate, retry, nightly, watch | every route goes through `win-run`; the nightly never talks to Windows itself | AT-10 | M-8 skip the `ls-remote` compare |
| 5 | referential | yes: retry links | `retry_of` must name an existing first attempt on the same SHA and lock hash | AT-4 | M-5 skip the lock-hash compare |
| 6 | untrusted input | yes: `WINRUN_LABEL`, catalog paths | label regex; paths checked with `git cat-file` and passed as separate words | AT-2, AT-7 | M-2 skip the label check |
| 7 | toctou | yes: Dell lock probe | the probe holds the lock for one open and close only; `win-run` keeps its 5-second retry loop | AT-15 (live) | N/A for a unit mutation: the race costs one 5-second retry and is checked live |
| 8 | weak tests | yes | every unit AT has a mutation that must fail it; live ATs read `EXIT` lines and rows | section 8 | M-7 retry on exit 1 |
| 9 | refactor | no | N/A: no existing behaviour is restructured; old exit codes and log lines stay | N/A, nothing moves | N/A, nothing to mutate |
| 10 | frozen contract | yes: the lane log format | the SHA line and final `EXIT n` line stay; lines are only added | AT-LANE-1 rerun in AT-10 | M-1 keep writing the dead queue path |

## 8. Acceptance tests (red first)

"Unit" means stdlib `unittest` tests of pure functions, run on the Mac (section 11). "Live" means
a real run against the Dell, read by `EXIT` lines and rows.

| AT | Slice | Kind | Behaviour | Red today because | Mutation |
|---|---|---|---|---|---|
| AT-1 | WL1 | live | A finished `win-run` appends one `DONE` line with label, rc, repo and 12-hex SHA to `~/.cache/win-run/events.log`; with `WINRUN_QUEUE_LOG` set it also appends the old line there; with it unset nothing is written under `/tmp/claude-1000/` | the line goes to the hard-coded scratchpad path | M-1 keep the hard-coded path |
| AT-2 | WL1 | unit (bash) | `WINRUN_LABEL=n20261125-cli-win-a1` names the log; `../x`, an upper-case label, a 49-character label and an existing label exit 2 before any ssh call (checked with an ssh stub on `PATH` that records calls) | no override exists | M-2 skip the regex check |
| AT-3 | WL1 | live | `current.json` exists while the job holds the lock and is gone after a normal end, an ssh failure (bad host) and a `kill -TERM` of `win-run` | no holder file | M-3 remove it only on the success path |
| AT-4 | WL1 | unit (bash) and live | refused with exit 2 before any ssh call: a first log ending `EXIT 0`, a first log for a different HEAD, a first log that is itself a retry, a second retry of the same label; live: a retry of a red first label on the same head runs and logs `retry of <label> attempt 2`, and a forged lock-hash line in the first log makes the retry end 255 | no retry link | M-4 allow a retry of a retry; M-5 skip the lock-hash compare |
| AT-5 | WL2 | unit | `decide()` returns the section 4.3 verdict and retry for every table row, including 255 with and without the `running:` line and a log with no `EXIT` line | no runner | M-6 map 75 to green; M-7 retry on exit 1 |
| AT-6 | WL2 | unit | when `origin/main` after fetch differs from `ls-remote` main, the repo's jobs are `not-run: stale main` and `win-run` is never called | no runner | M-8 skip the compare |
| AT-7 | WL2 | unit | absent catalog paths are listed and never passed to pytest; no present path gives not-run; a path present in the last row and absent now sets `GONE` and red | no runner; recent lane logs end `EXIT 4` | M-9 pass absent paths through |
| AT-8 | WL2 | unit | a second `win-nightly run` while the first holds `~/.cache/win-nightly.lock` writes not-run rows (`previous nightly still running`) and exits 3 at once; a worktree path outside `~/decoy-nightly/win/` is refused | no runner | M-10 block on the lock |
| AT-9 | WL2 | unit | `fail_ids()` keeps only `FAILED`, `ERROR` and `WINRUN FAIL` ids; a log holding the planted value `SECRET-VALUE-7731` in an assertion message never puts it in `results.tsv`, `fails/` or the Slack text; Slack fires on a new red, a new not-run, new failing ids or red to green, and not for an unchanged red or a disabled job | no runner | M-11 copy the log tail into Slack; M-12 alert on every red |
| AT-10 | WL2 | live | `win-nightly run --now` writes rows whose SHAs equal `ls-remote` main for both repos, whose labels have logs with the SHA line and a final `EXIT` line, and whose verdicts match those `EXIT` lines; `crontab -l` has exactly one `win-nightly` line | no nightly | M-8 is caught by the SHA check |
| AT-11 | WL2 | live | a test catalog job that sleeps, run with `WINRUN_STALL_MIN=1`, gives two logs, rows `attempt 1` and `attempt 2 retry_of=<label 1>`, and a final red | no nightly | M-4 |
| AT-12 | WL3 | unit | `parse_win_probe()` reads `FREE`, `CDISK`, `BUILD`, `PAUSE`, `LOCK`, ignores bad lines and returns None for empty output; the probe call carries `ConnectTimeout=8` and the 40-second timeout | no Windows node | M-13 raise on a bad line |
| AT-13 | WL3 | unit | given state before and after, `win_events()` raises each section 4.6 event once: START; DONE from new event-log lines (offset kept, a truncated file restarts at 0); QUEUED after 5 minutes; STALLED after 10 minutes without log growth; UNREACHABLE once per outage; DISK; BUILD; PAUSE at most daily; LOCK-FOREIGN after 10 minutes; NIGHTLY-MISSED after 10:00 UTC; NIGHTLY on a verdict change | no Windows node | M-14 drop the dedupe; M-15 never raise BUILD |
| AT-14 | WL3 | unit | the status table has the `dell-win` line with the section 4.6 fields for busy, idle, stale-holder and unreachable states | no Windows node | M-16 print BUSY for a dead holder pid |
| AT-15 | WL3 | live | with cron running, a real `win-run` job shows `START dell-win` and `DONE dell-win ... rc=` in `~/.cache/node-watch/events.log`, each within 4 minutes; a Dell lock held by the admin identity with no local holder raises LOCK-FOREIGN after 10 minutes; a job started during probes still runs | no Windows node | covered by M-14 and M-16 |
| AT-16 | WL4 | doc | the runbook is in the vault, `qmd search "windows lane runbook"` finds it, it names every exit code of section 6.1 and every event of section 4.6, and the memory note's Monitor grep includes the new event names | no runbook | n/a (reviewer doc check) |

AT-LANE-1 from WIN-FEAS (`docs/plans/2026-11-18-win-feas.md:711`) stays green: AT-10 reruns it on
the nightly logs.

## 9. Reuse inventory

- `B:win-run` and `B:win-run.d/winrun.ps1`: exact-head proof, lock-keyed venv, one-job locks,
  memory gate, stall guard and the AT-LANE-1 log check. WL1 adds about 50 lines and rewrites
  nothing. `winrun.ps1` does not change.
- `B:win-run.d/winrun_plugin.py`: unchanged.
- `B:node-watch`: `sh()` with timeouts, the `probe()` parse shape, the thread pool in `poll()`,
  the `state.json` store, the `alerted` dedupe set, and the events and status files.
- `~/.claude/scripts/slack-notify.sh manual`: the Slack path.
- `agent-config/sync.sh`: puts `~/bin` into git; each slice runs it once after its change.
- The WIN-FEAS 4.3 job list and path set (`docs/plans/2026-11-18-win-feas.md:505`): the source
  of the catalog.

## 10. Frozen contracts touched

No CLI or engine contract. One tooling contract: the lane log format read by gate readers and
by AT-LANE-1 (fact lines first, a `win-run: SHA requested` line, last line `EXIT n`). This plan
only adds a line (`win-run: retry of ...`). The `win-run` arguments do not change; new
behaviour is opt-in through environment variables.

## 11. Placement

`~/bin` has no CODEMAP; the tools follow the existing `~/bin` layout (`<tool>` plus a
`<tool>.d/` folder, as `win-run.d/` already does).

| File | Slice | Kind | Budget | Beside |
|---|---|---|---|---|
| `B:win-run` | WL1 | edit | 85 to about 135 lines | itself |
| `B:win-run.d/tests/test_win_run.sh` | WL1 | new | about 100 lines (AT-2, AT-4 refusals with an ssh stub) | `winrun.ps1` |
| `B:win-nightly` | WL2 | new, Python stdlib | about 260 lines | `B:win-run` |
| `B:win-run.d/jobs.json` | WL2 | new | about 40 lines | `winrun_plugin.py` |
| `B:win-run.d/tests/test_win_nightly.py` | WL2 | new | about 220 lines | the bash test |
| `B:node-watch` | WL3 | edit | 373 to about 530 lines | itself |
| `B:node-watch.d/tests/test_win_lane.py` | WL3 | new | about 200 lines | new folder, same pattern as `win-run.d/` |
| `~/obsidian-vault/10_Projects/decoy/guides/2026-11-25-windows-lane-runbook.md` | WL4 | new | about 170 lines | `decoy-report-and-v1-commands.md` |
| `C:docs/records/2026-11-25-win-lane-ops.md` | WL4 | new record | about 90 lines | `2026-11-18-win-lane.md` |
| `C:docs/roadmap/groups/release.md` row 6 | WL4 | edit | one row | n/a |
| memory note `win-run-dell-windows-lane.md` | WL4 | edit | a few lines | n/a |

Build rules for every slice:

- Edit a copy (`<name>.new`), run the checks, then `mv` it over the live file. Keep
  `<name>.bak-<mmdd>`.
- Static checks on the devbox only: `bash -n` and `shellcheck` for bash, `python3 -m py_compile`
  for Python.
- Unit tests run on the Mac, not the devbox: `rsync` the files to a temp folder on
  `camkeep@192.168.4.103` and run `python3 -m unittest discover -s <dir>/tests` and the bash test
  there. The scripts have no `.py` suffix, so tests load them with
  `importlib.machinery.SourceFileLoader`.
- After the live ATs pass, run `agent-config/sync.sh` so the tooling diff is in the
  `agent-config` history. The WL4 record cites those commits.

## 12. Slices

| Slice | Where | Content | Size | Review tier | Depends on |
|---|---|---|---|---|---|
| WL1 | devbox `~/bin` | `win-run`: lane event log and `WINRUN_QUEUE_LOG`; `WINRUN_LABEL`; `current.json` with trap cleanup; `WINRUN_RETRY_OF` with the section 3 checks; exit 2 for refusals; header comment updated | about 50 changed lines, 100 test lines | Dennis then Codex (gate machinery) | none |
| WL2 | devbox `~/bin`, crontab | `win-nightly` (worktrees, `ls-remote` check, path filter, `decide()`, retries, results, change-only Slack, overlap lock, `--print-cmd`); `jobs.json`; one crontab line | about 300 lines plus 220 test lines | Codex | WL1 |
| WL3 | devbox `~/bin` | node-watch Windows probe, `dell-win` status line, `win_events()`, event-log reader | about 160 lines plus 200 test lines | Codex | WL1; its NIGHTLY events read WL2's `results.tsv` and stay quiet until that file exists |
| WL4 | vault, CLI docs | dated runbook; CLI record of what was built and the first two real nightly results; row 6 text and status; memory note and Monitor grep | about 280 doc lines | Codex low | WL1, WL2, WL3 |

### 12.1 Test depth per slice

- WL1: T0 is `bash -n`, `shellcheck` and `test_win_run.sh` on the Mac; T1 adds the live AT-1,
  AT-3 and AT-4 on the Dell.
- WL2: T0 is the unit file on the Mac; T1 adds the live AT-10 and AT-11. AT-10 is also the first
  real nightly.
- WL3: T0 is the unit file on the Mac; T1 adds the live AT-15 with cron running.
- WL4: docs only. The reviewer checks AT-16. The CLI change is two Markdown files.
- No slice hits a full-suite escalation trigger: no CLI or engine source, fixture, test config,
  lock, schema, auth, serialization, version pin or moved test changes.
- Gate readers check that the live ATs were read by `EXIT` lines and rows, never by a summary
  line.

### 12.2 Release order and early build

Owner rule (2026-11-22): the release rows (88, 90, 92, 93, UPGRADE-KEY) and the Windows rows land
after the rest of the roadmap. These four slices are lane tooling, not Windows product work:

- They change no CLI or engine source, no packaging and no release pipeline.
- They make no row 89 slice ready sooner and change no row 89 acceptance test.
- The nightly only runs tests already on `main`. A red nightly is information, not a merge gate
  on other rows. A Windows-touching slice is still gated by its own `win-run` at its gate head,
  per WIN-FEAS 4.3.

So WL1 to WL4 can be built now: WL1 first, then WL2 and WL3 in parallel (different files, one
writer each), then WL4. The only later coupling: each row 89 slice that adds Windows tests adds
its paths to `jobs.json` in the same change, and CW5 or E-REL turns `demo-win` on. Those edits
belong to the row 89 slices.

Row 6 moves to MERGED when WL4 lands with two real nightly runs on record (any verdicts, as long
as each is a real verdict with a log).

## 13. Owner calls (listed, not decided)

- **OC1. Rust and MSVC Build Tools on the Dell.** The engine companion wheel cannot be built on
  Windows without them. Visual Studio Build Tools carry a Microsoft licence that limits
  commercial use by organisations. Default until answered: do not install;
  `engine-win-companion` stays disabled and every nightly row says so.
- **OC2. Windows Update pause after 2026-12-04.** The pause keeps the Dell from rebooting, which
  would also kill the WSL engine CI runners. Default: renew the pause by hand on 2026-12-03 (the
  runbook has the steps; the PAUSE event warns from 2026-12-01) and take updates only in a
  planned window with the runners drained. The owner may prefer a fixed weekly update window.
- **OC3. Row 6 text.** The row still says "Windows self-hosted runner on a GCP VM; spend approved
  by the owner; stopped when idle". Owner answer Q5 (2026-11-18) chose no GitHub runner and no
  cloud VM. Default: WL4 rewrites the row to "Windows proof lane on the Dell's Windows 11 side
  (`win-run`), nightly on both `main` heads, watched by node-watch".

## 14. Pre-mortem

- *The nightly is red every night because the CLI side is not Windows-ready yet.* Expected until
  the CW slices land. Change-only Slack (AT-9) sends one message per change; `results.tsv` keeps
  the history.
- *A Windows reboot in the night kills the nightly and the WSL runners.* The job ends 255 or 124
  and is retried once; BUILD fires on the next poll; the gate runners raise their own
  `RUNNER OFFLINE` event.
- *The Windows probe slows every poll.* It runs in the existing thread pool beside the other
  nodes and is capped at 40 seconds. A slow Dell only turns its own line UNREACHABLE.
- *Someone runs `win-nightly` by hand during a gate run.* The devbox lock serialises the jobs;
  the nightly lock only blocks a second nightly.
- *A reader skips the retry rule by calling `win-run` again without `WINRUN_RETRY_OF`.* That is
  a new first attempt, and the gate record must still name every attempt on that head. The
  runbook says so; the tool cannot stop a reader from ignoring a red log.
- *The registry pause value is not readable as `decoyci`.* The probe prints `PAUSE unknown`, and
  the runbook gives the admin command to check the date by hand.

## 15. Done when

- AT-1 to AT-16 pass; live ATs read by `EXIT` lines and rows.
- `crontab -l` has the nightly line and two real nightly runs are in `results.tsv`.
- The tooling diff is in the `agent-config` history and cited by the CLI record.
- Row 6 reads MERGED with the corrected text (or the owner's OC3 answer).
