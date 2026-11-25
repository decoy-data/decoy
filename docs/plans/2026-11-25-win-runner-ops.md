Status: plan

# WIN-RUNNER ops: nightly Windows runs, node-watch entry, runbook (roadmap row 6)

Owner: Cam. Author: Opus planner. Date: 2026-11-25. Revision 3 (Dennis R1 and R2 folded).

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
`~/bin/node-watch` (373 lines), and the 31 lane logs in `~/.cache/win-run/logs/`, all read on
2026-11-25. Notation: `C:` is the CLI repo, `B:` is `~/bin` on the `.55` devbox (copied daily
into the private `agent-config` repo by `agent-config/sync.sh`).

Revision 2 changes (Dennis R1, 1 BLOCKER, 6 MAJOR, 14 MINOR, all folded): the verdict now uses
the `win-run` process exit code and the log together (a log can end `EXIT 0` while `win-run`
returns 1 or 255); every `win-run` end carries a fixed reason word; failing test ids come from
an added `-rfE` report and are cut before the message text; the retry check moved behind the
devbox lock with an atomic claim and no lock-hash compare; one cleanup function replaces the
trap plan; LOCK-FOREIGN, QUEUED, BUILD and DISK moved to 1.x; labels carry the time; OC4 asks
whether to build ahead of the Windows chain.

Revision 3 changes (Dennis R2, 0 BLOCKER, 2 MAJOR, 6 MINOR, all folded): the job pipeline runs
in the background so INT and TERM handlers can act; one ordered `classify()` table gives each
end exactly one reason word (adds `deps`, `killed`, `unknown`); early ends before the lock are
named as rc-only; event lines are read only when complete; the memory-note edit moves into WL1;
`jobs.json` is edited right after a row 89 slice merges; non-pytest jobs carry their own green
rule.

## 0. Summary for the owner

Row 6 (`C:docs/roadmap/groups/release.md:19`) is PARTLY MERGED. The Windows proof lane on the
Dell's Windows 11 side works and gate readers use it. The lane record lists three items still
open (`C:docs/records/2026-11-18-win-lane.md:108`): nightly runs on both `main` heads, a
node-watch entry, and a dated vault runbook. Reading the tooling found three more gaps:

- `win-run` appends its `DONE` line to a hard-coded queue log inside a dead session scratchpad
  (`B:win-run` line 38). Nothing reads it, so a finished Windows job wakes nobody. This is a
  defect in tooling used today.
- `win-run` returns 1 while its log ends `EXIT 0` when a `windows`-marked test was skipped
  (line 83 changes the code after the log closes). Any reader that trusts the log alone can call
  a failed run green.
- The timing-retry rule in WIN-FEAS 4.3 (one retry on the same clean SHA, both logs kept, a
  second failure is red) is prose only.

Four slices close the row. None touches CLI or engine product code, packaging or the release
pipeline. WL1 fixes live tooling and updates the lane memory note so gate readers use the fix
at once; it can be built now. WL2 to WL4 are new ops tooling for a row
in the release group; OC4 asks whether they are built now or after the Windows chain (default:
after, section 12.2).

## 1. FRAME

### 1.1 Problem

The lane runs only when a gate reader calls it. A Windows regression that reaches `main`
through a slice outside the WIN-FEAS path set (`docs/plans/2026-11-18-win-feas.md:515`) shows
up only at the next Windows-touching gate, possibly days later, and is then blamed on the wrong
slice. A running, stalled or finished Windows job is invisible to the orchestrator: node-watch
knows the Dell only as the WSL node `dell-wsl` (`B:node-watch` line 40), and the `DONE` line goes
to a dead file. The recovery steps (Dell reboot, ssh key, update pause, venv reset, stuck lock)
exist only in a memory note.

### 1.2 Guarantee

After this plan:

1. Every night both `main` heads run the enabled lane jobs. Each job ends in exactly one
   verdict: `green`, `red`, `not-run` (with a reason word) or `disabled` (with a reason). Green
   needs all of: `win-run` exit 0, log final line `EXIT 0`, the head-proof line for the expected
   SHA, no `WINRUN FAIL` line and at least one passed test. Anything else is not green.
2. A new red, a new not-run or a missed nightly reaches the orchestrator through node-watch
   events and reaches Cam through one plain-language Slack line. An unchanged known red does
   not repeat on Slack.
3. node-watch shows the Windows lane as its own node `dell-win` (busy or idle, job and age,
   C: free, Windows build, update-pause end) and raises START, DONE, STALLED, UNREACHABLE,
   PAUSE, NIGHTLY-MISSED and NIGHTLY events.
4. A retry is a second `win-run` call that names its first attempt. It must be on the same SHA
   and the first attempt must have failed. A first attempt has at most one retry, enforced
   under the devbox lock. Both logs stay.
5. A dated runbook in the vault tells an agent or Cam how to run, read, retry and recover the
   lane.

### 1.3 Out of scope

- A GitHub Actions runner or a cloud VM (owner Q5, 2026-11-18). OC3 corrects the row text.
- The row 89 product slices (EW2 to EW5, CW1 to CW8, R0). They only add paths to the nightly job
  catalog when they merge (section 4.2).
- The pve2 Windows 11 evaluation VM release-build floor (WIN-FEAS 4.3, row 94).
- The engine companion wheel build on Windows until OC1 is answered.
- 1.x (section 5): LOCK-FOREIGN, QUEUED, BUILD and DISK events, and a weekly broad census.

### 1.4 Failure modes this plan designs against

| ID | Failure mode | Slice | Closed by |
|---|---|---|---|
| FM1 | The nightly tests a stale `origin/main` (the CLI clone once lacked a fetch refspec) | WL2 | `ls-remote` compare, AT-6 |
| FM2 | A catalog path is missing at the head (moved or deleted tests) and the nightly runs less, or pytest exits 4 | WL2 | every catalog path must exist; a missing one is red until `jobs.json` changes, AT-7 |
| FM3 | A run that `win-run` counted as failed reads as green (log ends `EXIT 0`, `win-run` returns 1 from line 83), or a run with zero passed tests reads as green | WL1, WL2 | `decide(rc, log, reason)`, AT-5 |
| FM4 | Low Windows memory (75) or a stall (124) reads as a pass or as a test failure | WL2 | verdict table, AT-5 |
| FM5 | The `DONE` line goes to a dead file and nobody wakes | WL1 | lane event log, AT-1 |
| FM6 | Retry chains (attempt 3) or a retry on another SHA, including two retries started together | WL1 | retry claim under the devbox lock, AT-4 |
| FM7 | Two nightlies overlap after a slow night | WL2 | non-blocking nightly lock, AT-8 |
| FM8 | The devbox cron or the devbox is down and no nightly runs, unnoticed | WL3 | NIGHTLY-MISSED, AT-13 (node-watch runs on the devbox, so a devbox outage shows only once it is back) |
| FM9 | The update pause ends and Windows reboots (killing the WSL CI runners too) without warning | WL3 | PAUSE event, AT-13 |
| FM10 | A failed or killed `win-run` leaves `current.json` behind, or a kill no longer stops the job | WL1 | one cleanup function and signal handlers, AT-3 |
| FM11 | The node-watch probe hangs or two polls overlap and double-report | WL3 | timeouts and a poll lock, AT-12, AT-13 |
| FM12 | A nightly red repeats on Slack every night and Cam stops reading it | WL2 | change-only Slack, AT-9 |
| FM13 | Test output text (which can hold data values) leaks into Slack or the results file | WL2 | ids cut before ` - `, fixed reason words, AT-9 |
| FM14 | A live edit to `win-run` or `node-watch` breaks a running job or a cron poll | all | atomic edit rule, section 11 |

## 2. Established solutions (survey)

Searched: the vault and memory notes (`win-run`, `node-watch`, nightly, T4), the WIN-FEAS plan,
the lane record and the existing `~/bin` tools (no nightly runner exists to reuse); plus how
common CI systems model these states.

- "Not run" as its own state: Buildbot and GitHub Actions keep `skipped` and `cancelled` apart
  from `success`. WIN-FEAS already says "a Windows job that did not run is 'not run', never
  green" (`docs/plans/2026-11-18-win-feas.md:521`).
- Linked retry attempts: GitHub Actions "re-run" keeps attempt 1 and attempt 2 under one run id
  and never hides attempt 1. This plan copies "linked attempts, both kept" with a cap of one.
- Change-only alerts: Prometheus Alertmanager notifies on state change. node-watch already
  dedupes with its `alerted` set (`B:node-watch` lines 275 and 318); this plan reuses it.
- pytest short summary: `-r` chars choose the summary lines; `f` and `E` give `FAILED <id> - <msg>`
  and `ERROR <id> - <msg>`. A later `-r` on the command line overrides the one in
  `PYTEST_ADDOPTS`.
- Custom code is still needed because no off-the-shelf tool drives a Windows host over ssh from
  this devbox with the lane's exact-head proof; the new code is small glue around the existing
  `win-run` and `node-watch`.

## 3. Design notes

No new abstraction: one new script (`win-nightly`) and one data file (`jobs.json`) beside the
existing tools. Each fact has one home: the job list in `jobs.json`, the verdict rules in one
`decide()` table, the lane state in `current.json` and the lane event log.

- **Reason words.** Every `win-run` end after the devbox lock has one reason word, picked by one
  `classify()` function in `win-run` from its own branch, its final rc and the log. The rules
  apply in this order; the first match wins:

  | # | Condition | Word |
  |---|---|---|
  | 1 | refused retry or bad label after the lock (rc 2) | `usage` |
  | 2 | INT or TERM handler ran (rc 130 or 143) | `killed` |
  | 3 | devbox branch: ssh check (line 44) failed | `ssh` |
  | 4 | devbox branch: install, bundle or wheel copy failed (lines 51, 57, 59, 62, 70, 71) | `setup` |
  | 5 | log has `WINRUN STALLED` (`winrun.ps1:142`) | `stall` |
  | 6 | log has `refused, free memory` (`winrun.ps1:63`) | `memory` |
  | 7 | log has `Windows lock not free` (`winrun.ps1:39`) | `lock-wait` |
  | 8 | log has `head proof failed` (`winrun.ps1:83`) | `proof` |
  | 9 | log has a uv venv, uv pip sync, uv sync, colorama or editable-install failure (`winrun.ps1:96`, `100`, `103`, `107`, `114`) | `deps` |
  | 10 | log has a token, fetch, checkout, clean or wheel-hash failure (`winrun.ps1:56`, `73`, `76`, `78`, `122`, `123`) | `setup` |
  | 11 | log has a `running:` line and no final `EXIT` line | `ssh` (session dropped) |
  | 12 | log has no `running:` line and no final `EXIT` line | `setup` |
  | 13 | rc changed by line 83 (`WINRUN FAIL`) or line 81 | `logcheck` |
  | 14 | final `EXIT 0` and rc 0 | `ok` |
  | 15 | final `EXIT n`, n not 0, after `running:` | `tests` |
  | 16 | anything else | `unknown` |

  The rules match the fixed `win-run:` message prefixes, never free text. Only the word leaves
  the devbox logs. Ends before the devbox lock (usage exits at lines 27 to 31, a dirty worktree
  at line 32, a bad `WINRUN_LABEL` before the lock) write no event line; they report through
  the process rc and stderr only, and the nightly reads them as "no DONE line".
- **Lane event log.** `win-run` writes one line per end after the lock to
  `~/.cache/win-run/events.log`:
  `DONE <label> rc=<n> reason=<word> repo=<r> sha=<12 hex> retry_of=<label|-> <UTC time>`. The
  `rc` is the final process code after lines 80 to 83. It also appends the old-format line to
  `$WINRUN_QUEUE_LOG` when that is set. The hard-coded path goes away. node-watch and
  `win-nightly` read this file.
- **Holder file and cleanup.** Before the lock `win-run` sets every variable the cleanup reads
  (`B=""`, `PIPE=""`, `REASON=""`), because `set -u` (line 19) would abort the trap on an early
  end. After `flock 9` it writes `~/.cache/win-run/current.json` (`label`, `pid`, `repo`, `sha`,
  `log`, `started`, `retry_of`) with write-to-temp then `mv`. One `cleanup` function, set as the
  EXIT trap after the lock (replacing the bundle-only trap at line 54), removes the bundle,
  removes `current.json` only when its `pid` is `$$`, and writes the event line.
- **Job pipeline and signals.** Bash runs a trap only after a foreground command ends, so the
  job pipeline at line 76 moves to the background:
  `{ ssh ... | sed -u ... | tee -a "$LOG"; } & PIPE=$!` then `wait "$PIPE"; rc=$?`. Under
  `set -o pipefail` (line 19) `wait` returns the last failing part, in practice ssh's code, which
  replaces `PIPESTATUS[0]`. INT and TERM handlers run `pkill -TERM -P "$PIPE"; kill "$PIPE"` and
  exit 130 or 143, so a kill ends the devbox side at once and the EXIT cleanup still runs. A
  queued waiter has no handler that touches `current.json`. What Windows OpenSSH does to the
  remote tree when the client dies is not verified: if `winrun.ps1` keeps running it holds
  `C:\dc\win-run.lock`, the next job waits up to 60 minutes and ends `lock-wait`. The runbook's
  stuck-lock steps cover that case; AT-3 records what happens.
- **Label override.** `WINRUN_LABEL` sets the label when it matches `^[a-z0-9][a-z0-9-]{0,47}$`
  and no log of that name exists. Anything else exits 2 before any ssh call. The nightly uses
  `n<YYYYMMDD>t<HHMM>-<job>-a<attempt>` (the start time stops same-day collisions).
- **Retry.** `WINRUN_RETRY_OF=<label>` marks a call as attempt 2. The checks run after
  `flock 9`, so a retry also waits for a still-running first attempt:
  - the lane event log has a `DONE <label>` line with `rc` not 0 and the same 12-hex SHA as this
    call's HEAD (the first attempt may have no log at all, for example an `ssh` end);
  - the first label is not itself a retry (its `current.json` record said `retry_of` empty, kept
    in the event line as `retry_of=-`);
  - `mkdir ~/.cache/win-run/logs/<label>.retried` succeeds (an atomic claim; a second retry of
    the same label fails here).
  Otherwise exit 2 with reason `usage`. The new log's first line (written by `win-run` before
  the ssh output) is `win-run: retry of <label> attempt 2`. The lock-hash compare from revision 1
  is dropped: the same SHA means the same lock file in the tree.
- **Log header lines.** `win-run` writes its own header lines (`win-run: retry of ...`) into the
  log, then starts `tee -a`. The last line stays `EXIT n` (frozen contract, section 10).
- **Nightly runner.** `B:win-nightly` (Python, stdlib only) runs from cron once a night. It
  keeps two dedicated worktrees, `~/decoy-nightly/win/cli` and `~/decoy-nightly/win/engine`,
  detached at `origin/main` of `/home/cam/vscode/decoy` and `/home/cam/vscode/decoy-engine`. It
  resets only paths under `~/decoy-nightly/win/` and refuses any other path. Per repo: fetch
  `main`, compare `origin/main` with `git ls-remote origin refs/heads/main`, check out the head,
  check the catalog paths, call `win-run` per job, take its process exit code, read its event
  line and log, decide the verdict, retry where section 4.3 allows, and write the results.
- **Job catalog.** `B:win-run.d/jobs.json` is the one registry of lane jobs: `name`, `repo`,
  `paths` (repo-relative, each must match `^[A-Za-z0-9_./-]+$`), `command` (with a `{paths}`
  slot), optional `disabled` (a reason) and optional `green` (`"exit0"` for a non-pytest job).
  `jobs.json` lives in `~/bin`, not in a product repo, so the builder of a row 89 slice edits it
  right after that slice merges; one red `catalog-path-missing` night in between is expected. `win-nightly --print-cmd <job>` prints the `win-run` command, so
  gate readers can use the same entries.
- **Results.** One TSV row per job attempt in `~/.local/state/win-nightly/results.tsv`, and
  `~/.local/state/win-nightly/fails/<label>.txt` with the failing test ids. `fail_ids()` reads
  `FAILED <id>`, `ERROR <id>` and `WINRUN FAIL: ... <id>` lines and cuts each at the first
  ` - `, so assertion text never leaves the log.
- **Windows probe.** node-watch sends one short PowerShell script through
  `ssh dell-win powershell -NoProfile -EncodedCommand <b64>` (payload under cmd.exe's 8191
  characters), inside the existing `sh()` 40-second timeout and with `ConnectTimeout=8`. It prints
  `CDISK <gb>` (`Get-PSDrive C`), `BUILD <n>` (registry `CurrentBuild` and `UBR`, as
  `winrun.ps1:53` does) and `PAUSE <yyyy-mm-dd|none|unknown>` (registry
  `HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings` `PauseUpdatesExpiryTime`). No WMI, no
  Add-Type compile, no lock open. `PAUSE unknown` never raises an event.
- **node-watch placement.** `dell-win` is not added to the `nodes` list, so the existing
  per-node IDLE and load-stall loop (lines 313 to 320) never sees it. It gets its own
  `win_lane()` step and status line. `poll` takes `flock -n ~/.cache/node-watch/poll.lock` and
  writes `state.json` with write-to-temp then rename, so overlapping cron polls cannot report
  the same DONE twice.
- **Live edits.** Each change to a live file in `~/bin` is made on a copy, checked, then put in
  place with `mv`. The old file stays as `<name>.bak-<mmdd>`.

## 4. Behavior

### 4.1 Nightly schedule

One crontab line (the devbox clock is UTC):
`30 7 * * * $HOME/bin/win-nightly run >> $HOME/.local/state/win-nightly/cron.log 2>&1`.
07:30 UTC is 01:30 CST (02:30 CDT in summer). The engine runs first, then the CLI, inside one
process. `win-nightly` writes `START <UTC time>` to `~/.local/state/win-nightly/last-start` as its
first action. A nightly can wait on the devbox `win-run` lock behind a gate job; that is normal.

### 4.2 Job catalog (initial content)

| Job | Repo | Paths (all present on 2026-11-25 `main`) | State |
|---|---|---|---|
| `engine-win` | engine | `tests/windows`, `tests/fileaccess/test_osflags.py` (the set gate readers run) | enabled |
| `cli-win` | CLI | `tests/unit/private_file`, `tests/e2e/private_file`, `tests/unit/distribution`, `tests/unit/library`, `tests/sentry/test_atomic_writer.py` | enabled |
| `engine-win-companion` | engine | the native companion wheel build | disabled: "Rust and MSVC Build Tools not installed (OC1)" |
| `demo-win` | CLI | fresh venv from candidate wheels, `decoy --version`, `doctor`, `demo --json`, quickstart, golden hash | disabled: "needs the E-REL Windows artifact (row 89 CW5)" |

Both enabled jobs run `%PY% -m pytest -q -p no:cacheprovider -rfEs {paths}`. `win-run` already
sets `PYTEST_ADDOPTS=-p winrun_plugin -rs` (`winrun.ps1` line 131); the later `-rfEs` adds the
FAILED and ERROR summary lines, and the plugin still fails a skipped `windows`-marked test
(`winrun_plugin.py:15`). The rest of `tests/fileaccess` imports `fcntl` and is not Windows-ready;
it joins the catalog with the row 89 slice that makes it so.

### 4.3 Verdict and retry table

`decide(rc, reason, log)` uses the `win-run` process code, the reason word from the event line,
and the log (which may be missing).

| rc and reason | Attempt 1 | Attempt 2 |
|---|---|---|
| 0, `ok`, log ends `EXIT 0`, head-proof line shows the expected SHA, no `WINRUN FAIL`, pytest summary shows at least 1 passed | green | green, row notes "green on retry" |
| 0 but any green condition above is false | red, reason `logcheck` | n/a |
| any rc, `stall` | retry at once | red |
| any rc, `memory` | retry after 20 minutes | not-run: `memory` |
| any rc, `ssh` | retry after 5 minutes | not-run: `ssh` |
| any rc, `lock-wait` | retry at once (the wait was already 60 minutes) | not-run: `lock-wait` |
| any rc, `setup` | not-run, no retry (it will not heal by itself) | n/a |
| any rc, `deps` | red (a `main` that cannot install on Windows is a Windows regression) | n/a |
| any rc, `proof` or `logcheck` | red | n/a |
| non-zero, `tests` | red, no retry | n/a |
| 2, `usage` or 130/143, `killed` | not-run, no retry | n/a |
| any rc, `unknown` | red (someone must look) | n/a |
| no `DONE` line for the label | not-run: `no-result` | n/a |

A job whose `jobs.json` entry sets `"green": "exit0"` (for a non-pytest job such as `demo-win`)
skips the "at least 1 passed" condition; `decide()` reads that field.

The nightly never retries a test failure. A gate reader who judges a test failure to be
runner-load timing may retry it once by hand with `WINRUN_RETRY_OF`; the gate record then names
both labels.

### 4.4 Catalog path check

Before each job the runner checks each catalog path with `git cat-file -e <sha>:<path>`. If
every path exists, they fill `{paths}`. If any path is missing, the job does not run and its
verdict is red with reason `catalog-path-missing` and `missing=<p1>,<p2>`. This stays red every
night until `jobs.json` is changed, so a moved or deleted test folder cannot go quiet.

### 4.5 Results and alerts

`results.tsv` columns, tab-separated, one row per attempt: `date_utc`, `repo`, `job`, `sha`,
`label`, `attempt`, `retry_of`, `rc`, `verdict`, `reason`, `fail_count`, `missing`,
`windows_build`. A refused overlapping nightly writes one run-level row with `job=*` and reason
`overlap`; the change comparison ignores `job=*` rows.

`win-nightly run` exits 0 when every enabled job is green, 1 when any is red, 3 when none is red
but any is not-run, 2 on a usage error. After the run it compares each job's final verdict and
failing-id set with that job's previous final row. Only on a change (a new red, a new not-run,
new failing ids, or red turning green) does it send one Slack line through
`~/.claude/scripts/slack-notify.sh manual`, in plain words built only from the job name, verdict,
fail count and a fixed phrase per reason word. For example: "Windows nightly: the CLI Windows
tests started failing tonight (3 tests). The engine Windows tests pass." A disabled job never
triggers Slack.

### 4.6 node-watch entry

- Status line: `dell-win  BUSY <label> <age> | IDLE <age>  C: <gb> GB  build <n>  pause to <date>  last nightly <date> <verdicts>`.
- Busy means `current.json` names a live pid; a dead pid shows `IDLE (stale holder)`.
- Events, each raised once per state change through the existing `alerted` set:
  - `START dell-win <label>` when a new holder label appears.
  - `DONE dell-win <label> rc=<n> <reason>` for each new complete line in the lane event log
    (stored byte offset moved only past lines ending in a newline; a file shorter than the
    offset restarts at 0).
  - `STALLED dell-win <label>` when the holder's log has a `win-run: running:` line
    (`winrun.ps1` line 132) and has not grown for 10 minutes. Lock waits, the memory wait and the
    venv build come before that line and never raise STALLED.
  - `UNREACHABLE dell-win` when the probe returns nothing, once per outage.
  - `PAUSE dell-win ends <date>` when the update pause ends within 3 days, and
    `PAUSE dell-win ended` once it has passed; at most once per UTC day.
  - `NIGHTLY-MISSED dell-win` when `last-start` has no time from today by 08:30 UTC.
  - `NIGHTLY dell-win <job> <verdict>` when a job's final verdict changes in `results.tsv`.
- The documented Monitor grep gains `PAUSE|NIGHTLY` (runbook and memory note, WL4).

## 5. Later (1.x)

- LOCK-FOREIGN (an orphan job holding the Dell lock), QUEUED, BUILD and DISK events. Note for
  that work: admin-identity jobs lock `C:\dca\win-run.lock` (`B:win-run` line 33), not
  `C:\dc\win-run.lock`, and the two identities do not block each other on the Dell; only the
  devbox lock serialises them.
- A weekly broad Windows census (the full CLI unit suite on Windows) once the CW slices land.
- A nightly on the pve2 Windows 11 evaluation VM if the release-build floor starts to drift.

## 6. Enumerations

### 6.1 Exit paths

- `win-run`: 0 or the job's own code; 124 stall or timeout; 75 low memory; 255 setup, proof,
  ssh or log-check failure; 1 when a log ending `EXIT 0` carries `WINRUN FAIL`; 2 usage, a bad
  `WINRUN_LABEL` or a refused retry (new); 130 or 143 on INT or TERM (new). The old list is in
  the `B:win-run` header (line 18) and `winrun.ps1` line 4.
- `win-nightly run`: 0 all green; 1 any red; 3 not-run without red; 2 usage. A refused second
  nightly writes its run-level row and exits 3.
- node-watch `poll`: unchanged; a poll that cannot take its lock exits 0 at once.

### 6.2 Routes

- Gate route: a gate reader calls `win-run` on a gate or merge head
  (`docs/plans/2026-11-18-win-feas.md:519`). Unchanged apart from the event line.
- Retry route: a gate reader or the nightly calls `win-run` with `WINRUN_RETRY_OF`.
- Nightly route: cron calls `win-nightly run`, which calls `win-run` with `WINRUN_LABEL`.
- Watch route: cron calls `node-watch poll` every 2 minutes; the probe and the lane files feed
  it.
- Plugin route (unchanged): a skipped `windows`-marked test fails the job inside pytest
  (`winrun_plugin.py:15`); `win-run` then returns 1 and the nightly reads red.

### 6.3 Fields

- `current.json`: `label`, `pid`, `repo`, `sha`, `log`, `started`, `retry_of`.
- Lane event line: `DONE`, label, `rc=`, `reason=`, `repo=`, `sha=` (12 hex), `retry_of=`, UTC time.
- `results.tsv`: the 13 columns of section 4.5.
- `jobs.json`: `name`, `repo`, `paths`, `command`, `disabled`.
- Probe lines: `CDISK`, `BUILD`, `PAUSE`.

### 6.4 FK shapes

N/A: this plan moves no table data and handles no foreign keys; it runs test jobs and reads
their logs.

### 6.5 Output surfaces

- `~/.cache/win-run/logs/<label>.log` (same format plus header lines) and `<label>.retried`.
- `~/.cache/win-run/events.log` and `~/.cache/win-run/current.json` (new).
- `~/.local/state/win-nightly/results.tsv`, `fails/<label>.txt`, `last-start` and `cron.log` (new).
- `~/.cache/node-watch/status.txt` and `events.log` (new `dell-win` lines).
- Slack: one plain-language line on change.
- The vault runbook and the CLI record (WL4). Row 6 itself sits at `docs/roadmap/groups/release.md:19`.

## 7. Class table

| # | Class | Applies | Closing structure | Sentry or test | Mutation |
|---|---|---|---|---|---|
| 1 | value-free text | yes: results and Slack | `fail_ids()` cuts at ` - `; Slack text built from fixed phrases per reason word | AT-9 | M-11 copy the log tail into the Slack text; M-17 keep the text after ` - ` |
| 2 | cleanup | yes: holder file, nightly worktrees | one `cleanup` after the lock, pid-checked; resets limited to `~/decoy-nightly/win/` | AT-3, AT-8 | M-3 keep the line 54 bundle-only trap |
| 3 | state | yes: verdicts and dedupe | one `decide()` table; `alerted` set, stored offsets, poll lock | AT-5, AT-13 | M-6 map 75 to green; M-18 ignore `rc` |
| 4 | route | yes: gate, retry, nightly, watch | every route goes through `win-run`; the nightly never talks to Windows itself | AT-6, AT-10 | M-8 skip the `ls-remote` compare |
| 5 | referential | yes: retry links | `retry_of` must name a failed first attempt on the same SHA; claimed with `mkdir` under the lock | AT-4 | M-5 drop the claim |
| 6 | untrusted input | yes: `WINRUN_LABEL`, catalog paths | label regex; path regex and `git cat-file` | AT-2, AT-7 | M-2 skip the label check |
| 7 | toctou | yes: two retries at once | checks and claim run after `flock 9` | AT-4 (concurrent case) | M-19 run the checks before the lock |
| 8 | weak tests | yes | every unit AT has a mutation that must fail it; fixtures cut from real lane logs; live ATs read `EXIT` lines and rows | section 8 | M-7 retry on `tests` |
| 9 | refactor | no | N/A: no existing behaviour is restructured; old exit codes and log lines stay | N/A, nothing moves | N/A, nothing to mutate |
| 10 | frozen contract | yes: the lane log format | the SHA line and final `EXIT n` line stay; lines are only added at the top | AT-LANE-1 rerun in AT-10 | M-1 keep writing the dead queue path |

## 8. Acceptance tests (red first)

"Unit" means stdlib `unittest` tests of pure functions run on the Mac, or the bash test run on
Dell WSL (section 11). "Live" means a real run against the Dell, read by `EXIT` lines, event
lines and rows. Fixtures for log parsing are cut from real lane logs in `~/.cache/win-run/logs/`.

| AT | Slice | Kind | Behaviour | Red today because | Mutation |
|---|---|---|---|---|---|
| AT-1 | WL1 | live | each `win-run` end appends one `DONE` line with label, final rc, reason word, repo and 12-hex SHA to `~/.cache/win-run/events.log`, for a green run, a `tests` run and an `ssh` end (bad host; also a unit case in the bash test with a failing ssh stub at line 44, which must not abort cleanup under `set -u`); with `WINRUN_QUEUE_LOG` set the old line also goes there; with it unset nothing is written under `/tmp/claude-1000/` | the line goes to the hard-coded scratchpad path | M-1 keep the hard-coded path |
| AT-2 | WL1 | unit (bash) | `WINRUN_LABEL=n20261125t0730-cli-win-a1` names the log; `../x`, an upper-case label, a 49-character label and an existing label exit 2 before any ssh call (an ssh stub on `PATH` records calls) | no override exists | M-2 skip the regex check |
| AT-3 | WL1 | live | `current.json` exists while the job holds the lock; after a normal end, an `ssh` end and a `kill -TERM` of `win-run` during the job pipeline it is gone, the devbox process has ended within 10 seconds of the signal and the event line says `killed`; a queued waiter killed with TERM leaves the holder's file in place; the record notes whether the Windows side kept running | no holder file | M-3 keep the line 54 trap |
| AT-4 | WL1 | unit (bash) and live | refused with exit 2: a first attempt with `rc=0`, a first attempt on a different SHA, a first attempt that is itself a retry, a second retry of the same label, and one of two retries started together (stub ssh); allowed: a retry of a first attempt that has no log (`ssh` end); live: a retry of a red first label runs and its log starts `win-run: retry of <label> attempt 2` | no retry link | M-4 allow a retry of a retry; M-5 drop the claim; M-19 check before the lock |
| AT-5 | WL2 | unit | `decide()` returns the section 4.3 verdict and retry for every row, including: rc 1 with a log ending `EXIT 0` and a `WINRUN FAIL` line (red); rc 255 `logcheck` with a log ending `EXIT 0` (red); rc 0 with all tests skipped (red); rc 0 with a wrong-SHA proof line (red); rc 75 with no `lock` or `running:` line (retry, then not-run); no `DONE` line (not-run) | no runner | M-6 map 75 to green; M-7 retry on `tests`; M-18 ignore `rc` |
| AT-5b | WL1 | unit (bash) | `classify()` returns the section 3 word for: the real log w96727b-3812486 (PowerShell error, no `running:`, no `EXIT`: `setup`), a 255 log with a uv sync failure (`deps`), a log with `running:` and no `EXIT` (`ssh`), a `WINRUN STALLED` log (`stall`), rc 143 (`killed`), rc 2 after the lock (`usage`), a log ending `EXIT 0` with `WINRUN FAIL` (`logcheck`), and an unmatched end (`unknown`); the order in the table holds when two rules match | no classifier | M-20 swap rules 11 and 13; M-21 drop the `unknown` fallback |
| AT-6 | WL2 | unit | when `origin/main` after fetch differs from `ls-remote` main, the repo's jobs are `not-run: stale-main` and `win-run` is never called | no runner | M-8 skip the compare |
| AT-7 | WL2 | unit | a catalog path missing at the head makes the job red with `missing=` and no `win-run` call, on this night and the next; a path failing the regex is a usage error | no runner | M-9 run with the paths that exist |
| AT-8 | WL2 | unit | a second `win-nightly run` while the first holds `~/.cache/win-nightly.lock` writes one `job=*` `overlap` row and exits 3 within 5 seconds (test timeout 10 seconds); the next run's change comparison ignores that row; a worktree path outside `~/decoy-nightly/win/` is refused | no runner | M-10 block on the lock |
| AT-9 | WL2 | unit | from a real lane log plus a planted `FAILED tests/x.py::t - assert 'SECRET-VALUE-7731' == ...` line, `fail_ids()` returns `tests/x.py::t` and `SECRET-VALUE-7731` is in neither `results.tsv`, `fails/`, nor the Slack text; Slack fires on a new red, a new not-run, new failing ids or red to green, and not for an unchanged red or a disabled job | no runner | M-11; M-12 alert on every red; M-17 |
| AT-10 | WL2 | live | `win-nightly run --now` writes rows whose SHAs equal `ls-remote` main for both repos, whose logs have the SHA line and a final `EXIT` line, and whose verdicts match `decide()` on the event lines; a red row has `fail_count` > 0; `crontab -l` has exactly one `win-nightly` line | no nightly | M-18 |
| AT-11 | WL2 | live | a test catalog job that sleeps, run with `WINRUN_STALL_MIN=1`, gives two logs, rows `attempt 1` and `attempt 2 retry_of=<label 1>`, and a final red | no nightly | M-4 |
| AT-12 | WL3 | unit | `parse_win_probe()` reads `CDISK`, `BUILD`, `PAUSE`, ignores bad lines and returns None for empty output; the probe call carries `ConnectTimeout=8` and the 40-second timeout; the encoded payload is under 8191 characters | no Windows node | M-13 raise on a bad line |
| AT-13 | WL3 | unit | given state before and after, `win_events()` raises each section 4.6 event once: START; DONE from new event lines (offset kept, truncated file restarts at 0); STALLED only after a `running:` line and 10 minutes without growth; UNREACHABLE once per outage; PAUSE at most daily; NIGHTLY-MISSED after 08:30 UTC with no start today; NIGHTLY on a verdict change; no IDLE event for `dell-win`; a half-written last event line is not read and the offset stops before it; a second poll holding no lock emits nothing | no Windows node | M-14 drop the dedupe; M-15 raise STALLED during a lock wait |
| AT-14 | WL3 | unit | the status table has the `dell-win` line with the section 4.6 fields for busy, idle, stale-holder and unreachable states | no Windows node | M-16 print BUSY for a dead holder pid |
| AT-15 | WL3 | live | with cron running, a real `win-run` job shows `START dell-win` and `DONE dell-win ... rc=` in `~/.cache/node-watch/events.log`, each within 4 minutes, and no IDLE line for `dell-win` | no Windows node | none of its own; the unit mutations M-14 to M-16 cover the logic |
| AT-16 | WL4 | doc | the runbook is in the vault, `qmd search "windows lane runbook"` finds it, it names every exit code of section 6.1, every reason word of section 3 and every event of section 4.6, and the memory note's Monitor grep includes the new event names | no runbook | n/a (reviewer doc check) |

AT-LANE-1 from WIN-FEAS (`docs/plans/2026-11-18-win-feas.md:711`) stays green: AT-10 reruns it on
the nightly logs.

## 9. Reuse inventory

- `B:win-run` and `B:win-run.d/winrun.ps1`: exact-head proof, lock-keyed venv, one-job locks,
  memory gate, stall guard and the AT-LANE-1 log check. WL1 adds about 60 lines. `winrun.ps1`
  does not change.
- `B:win-run.d/winrun_plugin.py`: unchanged.
- `B:node-watch`: `sh()` with timeouts, the thread pool in `poll()`, the `state.json` store, the
  `alerted` dedupe set, and the events and status files.
- `~/.claude/scripts/slack-notify.sh manual`: the Slack path.
- `agent-config/sync.sh`: puts `~/bin` into git; each slice runs it once after its change.
- The WIN-FEAS 4.3 job list and path set (`docs/plans/2026-11-18-win-feas.md:505`) and the
  commands gate readers already run (the `running:` lines of the lane logs): the source of the
  catalog.

## 10. Frozen contracts touched

No CLI or engine contract. One tooling contract: the lane log format read by gate readers and
by AT-LANE-1 (a `win-run: SHA requested` line, last line `EXIT n`). This plan only adds header
lines at the top. The `win-run` arguments do not change; new behaviour is opt-in through
environment variables, except the event line, which is always written.

## 11. Placement

`~/bin` has no CODEMAP; the tools follow the existing `~/bin` layout (`<tool>` plus a
`<tool>.d/` folder, as `win-run.d/` already does).

| File | Slice | Kind | Budget | Beside |
|---|---|---|---|---|
| `B:win-run` | WL1 | edit | 85 to about 175 lines | itself |
| `B:win-run.d/tests/test_win_run.sh` | WL1 | new | about 160 lines (AT-2, AT-4, AT-5b with an ssh stub) | `winrun.ps1` |
| `B:win-nightly` | WL2 | new, Python stdlib | about 260 lines | `B:win-run` |
| `B:win-run.d/jobs.json` | WL2 | new | about 40 lines | `winrun_plugin.py` |
| `B:win-run.d/tests/test_win_nightly.py` | WL2 | new | about 240 lines | the bash test |
| `B:node-watch` | WL3 | edit | 373 to about 480 lines | itself |
| `B:node-watch.d/tests/test_win_lane.py` | WL3 | new | about 160 lines | new folder, same pattern as `win-run.d/` |
| `~/obsidian-vault/10_Projects/decoy/guides/2026-11-25-windows-lane-runbook.md` | WL4 | new | about 170 lines | `decoy-report-and-v1-commands.md` |
| `C:docs/records/2026-11-25-win-lane-ops.md` | WL4 | new record | about 90 lines | `2026-11-18-win-lane.md` |
| `C:docs/roadmap/groups/release.md` row 6 | WL4 | edit | one row | n/a |
| memory note `win-run-dell-windows-lane.md` | WL1 (gate-reader use), WL4 (Monitor grep) | edit | a few lines each | n/a |

Build rules for every slice:

- Edit a copy (`<name>.new`), run the checks, then `mv` it over the live file. Keep
  `<name>.bak-<mmdd>`.
- Static checks on the devbox only: `bash -n` and `shellcheck` for bash, `python3 -m py_compile`
  for Python.
- Python unit tests run on the Mac: `rsync` the files to a temp folder on
  `camkeep@192.168.4.103` and run `python3 -m unittest discover -s <dir>/tests`. The scripts have
  no `.py` suffix, so tests load them with `importlib.machinery.SourceFileLoader`.
- The bash test needs GNU `md5sum`, `base64 -w0`, `date -d` and `flock`, which the Mac lacks. It
  runs on Dell WSL (`ssh dell-wsl`), in a temp folder, with the ssh stub; it starts no pytest.
- After the live ATs pass, run `agent-config/sync.sh` so the tooling diff is in the
  `agent-config` history. The WL4 record cites those commits.

## 12. Slices

| Slice | Where | Content | Size | Review tier | Depends on |
|---|---|---|---|---|---|
| WL1 | devbox `~/bin` | `win-run`: `classify()` and reason words, lane event line and `WINRUN_QUEUE_LOG`; `WINRUN_LABEL`; `current.json` with one cleanup function; background job pipeline with INT/TERM handlers; `WINRUN_RETRY_OF` checks and claim after the lock; header lines; header comment updated; memory note `win-run-dell-windows-lane.md` tells gate readers to read rc and reason from `events.log` and to retry with `WINRUN_RETRY_OF` | about 90 changed lines, 160 test lines | Dennis then Codex (gate machinery) | none |
| WL2 | devbox `~/bin`, crontab | `win-nightly` (worktrees, `ls-remote` check, path check, `decide()`, retries, results, change-only Slack, overlap lock, `--print-cmd`); `jobs.json`; one crontab line | about 300 lines plus 240 test lines | Codex | WL1 |
| WL3 | devbox `~/bin` | node-watch Windows probe, `dell-win` status line, `win_events()`, event-log reader, poll lock, atomic `state.json` | about 110 lines plus 160 test lines | Codex | WL1; its NIGHTLY events read WL2's files and stay quiet until they exist |
| WL4 | vault, CLI docs | dated runbook; CLI record of what was built and the first two real nightly results; row 6 text and status; memory note and Monitor grep | about 280 doc lines | Codex low | WL1, WL2, WL3 |

### 12.1 Test depth per slice

- WL1: T0 is `bash -n`, `shellcheck` and `test_win_run.sh` (AT-2, AT-4, AT-5b) on Dell WSL; T1 adds the live AT-1,
  AT-3 and AT-4 on the Dell.
- WL2: T0 is the unit file on the Mac; T1 adds the live AT-10 and AT-11.
- WL3: T0 is the unit file on the Mac; T1 adds the live AT-15 with cron running.
- WL4: docs only. The reviewer checks AT-16. The CLI change is two Markdown files.
- No slice hits a full-suite escalation trigger: no CLI or engine source, fixture, test config,
  lock, schema, auth, serialization, version pin or moved test changes.

### 12.2 Release order and early build

Owner rule (2026-11-22): the release rows and the Windows chain land after the rest of the
roadmap. Row 6 sits in the release group (`C:docs/roadmap/groups/release.md`, "Blocks the 1.0
release"). None of WL1 to WL4 is required by the V1 bar today.

- **WL1 can be built now.** It fixes defects in tooling gate readers use today (the dead `DONE`
  path, and nothing recording the final code next to a log that can say `EXIT 0` for a failed
  run), and its memory-note edit points gate readers at `events.log` and `WINRUN_RETRY_OF`, so
  the fix is used before WL2 to WL4 exist. It changes no CLI or engine code and no release work. This falls under "do reasonable
  recommended fixes".
- **WL2, WL3 and WL4 wait for OC4.** They are new ops capability for a release-group row. Default:
  build them when the Windows chain (row 89) starts. If the owner says build now: WL2 and WL3 in
  parallel after WL1 (different files, one writer each), then WL4.
- Later coupling: each row 89 slice that adds Windows tests adds its paths to `jobs.json` right
  after it merges, and CW5 or E-REL turns `demo-win` on (with `"green": "exit0"`).

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
- **OC4. Build WL2 to WL4 before the Windows chain?** Default: no. WL1 is built now as a fix;
  WL2 to WL4 start with row 89.

## 14. Pre-mortem

- *The nightly is red every night at first.* Possible on both sides until the CW and EW slices
  land; the engine set is the one gate readers already run, so it should start green.
  Change-only Slack (AT-9) sends one message per change; `results.tsv` keeps the history.
- *A Windows reboot in the night drops the ssh session.* `win-run` ends 255 with reason `ssh`
  (a `running:` line and no `EXIT` line), the nightly retries once after 5 minutes, and a second
  failure is not-run, not red. The gate runners raise their own `RUNNER OFFLINE` event.
- *The Windows probe slows every poll.* It runs beside the other probes, does no compile and no
  WMI, and is capped at 40 seconds. A slow Dell only turns its own line UNREACHABLE.
- *Someone runs `win-nightly` by hand during a gate run.* The devbox lock serialises the jobs;
  the nightly lock only blocks a second nightly. Labels carry the start time, so a hand run on
  the same day does not collide.
- *A reader skips the retry rule by calling `win-run` again without `WINRUN_RETRY_OF`.* That is
  a new first attempt, and the gate record must still name every attempt on that head. The
  runbook says so; the tool cannot stop a reader from ignoring a red log.
- *The registry pause value is not readable as `decoyci`.* The probe prints `PAUSE unknown`, and
  the runbook gives the admin command to check the date by hand.

## 15. Done when

- AT-1 to AT-16 and AT-5b pass; live ATs read by `EXIT` lines, event lines and rows.
- `crontab -l` has the nightly line and two real nightly runs are in `results.tsv`.
- The tooling diff is in the `agent-config` history and cited by the CLI record.
- Row 6 reads MERGED with the corrected text (or the owner's OC3 answer).
