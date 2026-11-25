Status: plan

# WIN-RUNNER ops: nightly Windows runs, node-watch entry, runbook (roadmap row 6)

Owner: Cam. Author: Opus planner. Date: 2026-11-25. Revision 6 (Dennis R1, R2, Codex R1 and R2 folded, Codex R3 folded by codex-fix).

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

Revision 4 changes (Codex R1, 6 HIGH, 5 MEDIUM, 1 LOW, all folded): failing test ids are
stored only as digests (pytest ids can carry parameter values); lane and nightly files are
private (`umask 077`, 0700 folders); every label is reserved under the devbox lock; a retry is
bound to the first attempt's repo, full SHA, command and inputs; the wrapper rc override wins
over inferred transport loss and every second-attempt outcome has a verdict; Slack goes through
a send path that reports failure, and node-watch sends the missed-nightly alert; `last-start` is
written only after the nightly lock; the nightly marks each job's final row; `win-run` writes a
`START` event line; the poll lock covers interactive refreshes; `demo-win` waits for all its
inputs.

Revision 5 changes (Codex R2, 4 HIGH, 5 MEDIUM, all folded): a label with an existing log
(from before WL1) is refused like a claimed one; nightly labels carry a per-run id and the
nightly accepts only a `DONE` line appended during its own call with a matching rc; dated run
records and an open-jobs file let an interrupted nightly and a whole missed day end in a
`not-run` verdict and an alert; Slack alerts sit in a pending queue apart from the result
comparison, and node-watch tracks its local event and its Slack send apart; node-watch writes
its event lines before it moves the offset; the `in` digest covers the stall, timeout and
memory limits; the failing-test digest is taken from the full node id inside pytest; AT-4 and
M-20 are corrected.

Revision 6 changes (Codex R3): fresh completion evidence distinguishes collection failures from refusals.
The plugin hashes failed collection IDs. Recovery preserves final rows and replays alerts from a durable cursor.
Missed slots get one row per enabled job, starting at the first expected cron slot. M-20 now uses raw rc 0 and final rc 255.

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
| FM3 | A run that `win-run` counted as failed reads as green (log ends `EXIT 0`, `win-run` returns 1 from line 83), or a run with zero passed tests reads as green, or a collection error reads as a refusal | WL1, WL2 | `decide(rc, log, reason)`, fresh DONE and final EXIT for rc 2, AT-5 and AT-9 |
| FM4 | Low Windows memory (75) or a stall (124) reads as a pass or as a test failure | WL2 | verdict table, AT-5 |
| FM5 | The `DONE` line goes to a dead file and nobody wakes | WL1 | lane event log, AT-1 |
| FM6 | Retry chains (attempt 3), a retry on another SHA or with other inputs, two retries started together, or a reused label overwriting the first attempt | WL1 | label reservation and retry claim under the devbox lock, retry bound to repo, full SHA and `in` digest, AT-2, AT-4 |
| FM7 | Two nightlies overlap after a slow night | WL2 | non-blocking nightly lock, AT-8 |
| FM8 | The devbox cron or the devbox is down and no nightly runs, or a nightly is killed part way, unnoticed | WL2, WL3 | first expected slot in `armed`, NIGHTLY-MISSED per date, NIGHTLY-INCOMPLETE and locked reconcile that fills only missing final rows, AT-8, AT-13 (node-watch runs on the devbox, so a devbox outage shows only once it is back) |
| FM9 | The update pause ends and Windows reboots (killing the WSL CI runners too) without warning | WL3 | PAUSE event, AT-13 |
| FM10 | A failed or killed `win-run` leaves `current.json` behind, or a kill no longer stops the job | WL1 | one cleanup function and signal handlers, AT-3 |
| FM11 | The node-watch probe hangs or two polls overlap and double-report | WL3 | timeouts and a poll lock, AT-12, AT-13 |
| FM12 | A nightly red repeats on Slack every night and Cam stops reading it | WL2 | change-only Slack, AT-9 |
| FM13 | Test output text or parametrised test ids (which can hold data values) leak into Slack, the results file or `cron.log`, or lane files are readable by other users | WL1, WL2 | ids stored only as digests, fixed reason words, `umask 077` and 0700 folders, `win-run` output to `/dev/null` under cron, AT-9, AT-10 |
| FM15 | A crash before enqueue or a failed send loses a Slack alert | WL2, WL3 | replay final rows, save cursor and queue together, remove only after send succeeds, AT-9, AT-13 |
| FM16 | A poll between a failed attempt 1 and a green attempt 2 reports a red, or a short job between two polls is missed | WL2, WL3 | `final` column; `START` event line read through the offset, AT-13 |
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
  | 1 | (removed in revision 4: refusals end before the event line, see Label and Retry) | n/a |
  | 2 | INT or TERM handler ran (rc 130 or 143) | `killed` |
  | 3 | devbox branch: ssh check (line 44) failed | `ssh` |
  | 4 | devbox branch: install, bundle or wheel copy failed (lines 51, 57, 59, 62, 70, 71) | `setup` |
  | 5 | log has `WINRUN STALLED` (`winrun.ps1:142`) | `stall` |
  | 6 | log has `refused, free memory` (`winrun.ps1:63`) | `memory` |
  | 7 | log has `Windows lock not free` (`winrun.ps1:39`) | `lock-wait` |
  | 8 | log has `head proof failed` (`winrun.ps1:83`) | `proof` |
  | 9 | log has a uv venv, uv pip sync, uv sync, colorama or editable-install failure (`winrun.ps1:96`, `100`, `103`, `107`, `114`) | `deps` |
  | 10 | log has a token, fetch, checkout, clean or wheel-hash failure (`winrun.ps1:56`, `73`, `76`, `78`, `122`, `123`) | `setup` |
  | 11 | raw pipeline rc was 0 and `win-run` changed it at line 81 (no SHA or `EXIT` line) or line 83 (`WINRUN FAIL`) | `logcheck` |
  | 12 | log has a `running:` line, no final `EXIT` line and raw pipeline rc not 0 | `ssh` (session dropped) |
  | 13 | log has no `running:` line and no final `EXIT` line | `setup` |
  | 14 | final `EXIT 0` and rc 0 | `ok` |
  | 15 | final `EXIT n`, n not 0, after `running:` | `tests` |
  | 16 | anything else | `unknown` |

  `classify()` reads the raw pipeline rc (before lines 80 to 83) and the final rc. The rules
  match the fixed `win-run:` message prefixes, never free text. Only the word leaves
  the devbox logs. Ends before the devbox lock (usage exits at lines 27 to 31, a dirty worktree
  at line 32, a bad `WINRUN_LABEL`) and refusals right after the lock (a taken label, a refused
  retry; both exit 2 before the cleanup is armed) write no event line; they report through
  the process rc and stderr only. A pytest collection failure can also exit 2. It writes DONE
  with reason `tests` and ends its log with `EXIT 2`.
- **Lane event log.** `win-run` writes one line per end after the lock to
  `~/.cache/win-run/events.log`:
  `START <label> repo=<r> sha=<40 hex> in=<12 hex> retry_of=<label|-> <UTC time>` once the
  holder file is written, and
  `DONE <label> rc=<n> reason=<word> repo=<r> sha=<40 hex> in=<12 hex> retry_of=<label|-> <UTC time>`
  at the end. `in` is the first 12 hex of the sha256 of the command, the host identity, the
  wheel sha256 (empty when no wheel) and the effective `-StallMin`, `-TimeoutMin` and
  `-MinFreeGB` values passed at line 76, so a retry cannot loosen the limits that failed; the command itself never enters the event log. The
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
- **Label override and reservation.** `WINRUN_LABEL` sets the label when it matches
  `^[a-z0-9][a-z0-9-]{0,47}$`; a bad form exits 2 before the lock. Every label, given or
  generated, is reserved right after `flock 9`: the call exits 2 when
  `~/.cache/win-run/logs/<label>.log` already exists (the 31 logs from before WL1 have no claim
  folder) or when `mkdir ~/.cache/win-run/claims/<label>` fails. This runs before the cleanup is
  armed and before any ssh call. A taken label exits 2 and writes nothing,
  so the first attempt's event lines and log stay the only ones for that label, even when that
  attempt had no log (an `ssh` end). The nightly uses
  `n<YYYYMMDD>t<HHMMSS>-<run>-<job>-a<attempt>`, where `<run>` is a four-hex suffix for this run (within the 48-character limit for
  the current job names). Use the full timestamp and suffix as the stored run ID.
  Under the nightly lock, choose another suffix if a run record already has that ID.
- **Retry.** `WINRUN_RETRY_OF=<label>` marks a call as attempt 2. The checks run after
  `flock 9`, so a retry started while the first attempt runs waits for it, then is checked
  against its `DONE` line (allowed after a red end, refused after a green one):
  - the lane event log has a `DONE <label>` line with `rc` not 0 and the same `repo`, the same
    full SHA and the same `in` digest as this call (same command, identity and wheel; the first
    attempt may have no log at all, for example an `ssh` end);
  - the first label is not itself a retry (its `current.json` record said `retry_of` empty, kept
    in the event line as `retry_of=-`);
  - `mkdir ~/.cache/win-run/logs/<label>.retried` succeeds (an atomic claim; a second retry of
    the same label fails here).
  Otherwise exit 2 before the cleanup is armed (no event line). The new log's first line (written by `win-run` before
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
  line (only a `DONE` line for that label appended after the event-log size noted just before
  the call, and only when its `rc` equals the process exit code; anything else is
  `no-result`) and log, decide the verdict, retry where section 4.3 allows, and write the results.
- **Job catalog.** `B:win-run.d/jobs.json` is the one registry of lane jobs: `name`, `repo`,
  `paths` (repo-relative, use `re.fullmatch(r"[A-Za-z0-9_./-]+", path)` and reject absolute paths and parent segments), `command` (with a `{paths}`
  slot), optional `disabled` (a reason) and optional `green` (`"exit0"` for a non-pytest job).
  `jobs.json` lives in `~/bin`, not in a product repo, so the builder of a row 89 slice edits it
  right after that slice merges; one red `catalog-path-missing` night in between is expected. `win-nightly --print-cmd <job>` prints the `win-run` command, so
  gate readers can use the same entries.
- **Results.** One TSV row per job attempt in `~/.local/state/win-nightly/results.tsv`, and
  `~/.local/state/win-nightly/fails/<label>.txt` with one digest per failing test. The digest is
  taken inside pytest, from the full node id: WL2 adds `pytest_runtest_logreport` and `pytest_collectreport` hooks to
  `winrun_plugin.py` (the plugin is copied to Windows on every run, `B:win-run`
  line 50). Both hooks record failed reports. The existing marker check also records skipped Windows tests.
  One helper hashes the full node ID with SHA-256. The terminal summary prints one
  `WINRUN FAILID <16 hex>` per distinct digest, including failed collection reports.
  Keep the fixed skip prefix that the wrapper reads at line 83. Drop the raw ID from that error. `fail_ids()` reads only complete digest lines, so
  `test_t[left - 1]` and `test_t[left - 2]` stay distinct and no id text leaves the log:
  pytest ids can carry parameter values (`test_x[value]`). The digest set only drives the
  "failing set changed" comparison; a human reads the ids in the private lane log.
- **Private files.** `win-run` and `win-nightly` set `umask 077`. WL1 makes `~/.cache/win-run`
  and its subfolders 0700 and the existing logs 0600; `win-nightly` creates
  `~/.local/state/win-nightly` as 0700 before writing anything. `win-nightly` sends `win-run`'s
  stdout and stderr to `/dev/null` (the job output is already in the lane log), so `cron.log`
  holds only `win-nightly`'s own lines (labels, verdicts, reason words). Capture git and sender
  diagnostics too. Report fixed errors without subprocess output, webhook URLs or exception text.
- **Run records.** Under the nightly lock, save the run ID, PID, UTC start and open jobs in
  `runs/<YYYY-MM-DD>/<run>.json`. Replace the file atomically on each update. Commit the digest file
  before the result row. Commit each final row before removing the job. Write `end` last.
  Signal handlers, the next run and `win-nightly reconcile` use the same recovery code under
  the same lock. For each open job, look for a complete `final=1` row with that run ID and job.
  Keep the first final verdict. Append `not-run` with reason `interrupted` only if the row is absent.
  Keep closed records when another run starts the same day. Reconcile also fills missed dates under section 4.6.
- **Slack sender.** `B:win-run.d/lane_slack.py` (stdlib, about 40 lines) posts one text to the
  webhook read from `~/.config/win-lane/slack.env` (0600, `SLACK_WEBHOOK_URL=` copied from the
  hooks' setting) and returns non-zero on a missing webhook, a network error or a non-2xx
  answer. It is used instead of `slack-notify.sh`, which exits 0 on a missing webhook and hides
  curl failures (`slack-notify.sh` lines 9 to 11 and 36). One replay path in `win-nightly`
  commits the row cursor and pending alerts together (section 4.5). Node-watch owns the
  date-level alerts and keeps its pending sends in `state.json`. Sender errors use fixed text.
- **Windows probe.** node-watch sends one short PowerShell script through
  `ssh dell-win powershell -NoProfile -EncodedCommand <b64>` (payload under cmd.exe's 8191
  characters), inside the existing `sh()` 40-second timeout and with `ConnectTimeout=8`. It prints
  `CDISK <gb>` (`Get-PSDrive C`), `BUILD <n>` (registry `CurrentBuild` and `UBR`, as
  `winrun.ps1:53` does) and `PAUSE <yyyy-mm-dd|none|unknown>` (registry
  `HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings` `PauseUpdatesExpiryTime`). No WMI, no
  Add-Type compile, no lock open. `PAUSE unknown` never raises an event.
- **node-watch placement.** `dell-win` is not added to the `nodes` list, so the existing
  per-node IDLE and load-stall loop (lines 313 to 320) never sees it. It gets its own
  `win_lane()` step and status line; its probe is submitted to the existing executor in
  `poll()` (`B:node-watch` line 197) so its timeout runs beside the others. Both writer routes
  (`node-watch` with no argument and `node-watch poll`, which share `main()` from line 263) take
  `flock -n ~/.cache/node-watch/poll.lock` before reading `state.json`; `status` and `events`
  stay lock-free readers. `state.json` is written with write-to-temp then rename, so overlapping
  polls cannot report the same event twice.
- **Live edits.** Each change to a live file in `~/bin` is made on a copy, checked, then put in
  place with `mv`. The old file stays as `<name>.bak-<mmdd>`.

## 4. Behavior

### 4.1 Nightly schedule

One crontab line (the devbox clock is UTC):
`30 7 * * * umask 077; mkdir -p $HOME/.local/state/win-nightly && $HOME/bin/win-nightly run >> $HOME/.local/state/win-nightly/cron.log 2>&1`.
The WL2 install step also writes `~/.local/state/win-nightly/armed`, which turns on the
missed-nightly check. At first install, store the next 07:30 UTC strictly after install in
`armed`. Keep that timestamp on reinstall.
07:30 UTC is 01:30 CST (02:30 CDT in summer). The engine runs first, then the CLI, inside one
process. Capture the start time when the lock is acquired, before recovery or alert sends.
Write the dated record before any slow work. A refused overlapping run writes none (`last-start` from revision 4 is replaced by the run
records). A nightly can wait on the devbox `win-run` lock behind a gate job; that is normal.

### 4.2 Job catalog (initial content)

| Job | Repo | Paths (all present on 2026-11-25 `main`) | State |
|---|---|---|---|
| `engine-win` | engine | `tests/windows`, `tests/fileaccess/test_osflags.py` (the set gate readers run) | enabled |
| `cli-win` | CLI | `tests/unit/private_file`, `tests/e2e/private_file`, `tests/unit/distribution`, `tests/unit/library`, `tests/sentry/test_atomic_writer.py` | enabled |
| `engine-win-companion` | engine | the native companion wheel build | disabled: "Rust and MSVC Build Tools not installed (OC1)" |
| `demo-win` | CLI | fresh venv from candidate wheels, `decoy --version`, `doctor`, `demo --json`, quickstart, golden hash | disabled until the selected companion wheel and its sha256, the candidate CLI artifacts and a same-head Linux golden all exist (row 89 CW5 and E-REL together); the first candidate smoke run with all three is the enablement check |

Both enabled jobs run `%PY% -m pytest -q -p no:cacheprovider -rfEs {paths}`. `win-run` already
sets `PYTEST_ADDOPTS=-p winrun_plugin -rs` (`winrun.ps1` line 131); the later `-rfEs` adds the
FAILED and ERROR summary lines, and the plugin still fails a skipped `windows`-marked test
(`winrun_plugin.py:15`). The rest of `tests/fileaccess` imports `fcntl` and is not Windows-ready;
it joins the catalog with the row 89 slice that makes it so.

### 4.3 Verdict and retry table

`decide(rc, reason, log)` uses the `win-run` process code, the reason word from the event line,
and the log (which may be missing).

An attempt counts only with a matching `DONE` event line: same label, repo, SHA and `in`,
appended during this call, with `rc` equal to the `win-run` exit code. For rc 2, require both this fresh DONE and a log ending `EXIT 2`.
Then apply the reason below. A failed collection with `tests` is red. Missing evidence gives
`not-run` with reason `no-result` on either attempt. Read digests only after the evidence check passes.
Attempt 2 applies the same rules as attempt 1 with no further retry: a word that would retry
becomes the "Attempt 2" entry below; every other word gets its attempt 1 verdict.

| rc and reason | Attempt 1 | Attempt 2 |
|---|---|---|
| 0, `ok`, log ends `EXIT 0`, head-proof line shows requested and observed SHA equal the expected SHA and the tree is clean, no `WINRUN FAIL`, pytest summary shows at least 1 passed | green | green, row notes "green on retry" |
| 0 but any green condition above is false | red, reason `logcheck` | red |
| non-zero, `ok` | red, reason `logcheck` | red |
| any rc, `stall` | retry at once | red |
| any rc, `memory` | retry after 20 minutes | not-run: `memory` |
| any rc, `ssh` | retry after 5 minutes | not-run: `ssh` |
| any rc, `lock-wait` | retry at once (the wait was already 60 minutes) | not-run: `lock-wait` |
| any rc, `setup` | not-run, no retry (it will not heal by itself) | not-run |
| any rc, `deps` | red (a `main` that cannot install on Windows is a Windows regression) | red |
| any rc, `proof` or `logcheck` | red | red |
| non-zero, `tests` | red, no retry | red |
| 130/143, `killed` | not-run, no retry | not-run |
| any rc, `unknown` | red (someone must look) | red |
| no matching `DONE` line (includes rc 2 refusals) | not-run: `no-result` | not-run: `no-result` |
| scheduled date missed | not-run: `missed` for each enabled job | no retry |
| nightly ended before the job's final row | not-run: `interrupted` (written by the handler or by reconcile) | not-run: `interrupted` |

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
`windows_build`, `final`, `run`. Store the run ID even on rows without an attempt label. `win-nightly` alone owns the final verdict: it sets `final=1` on the
last row of each job once no retry is pending (`final=0` on a row that waits for its retry).
The Slack comparison, the exit code and node-watch read only `final=1` job rows.
Compute the exit code from this run ID alone. A refused overlapping nightly writes one run-level row with `job=*` and reason
`overlap`; the change comparison ignores `job=*` rows. Serialize all TSV appends, including overlap rows, under a
short file lock. Before appending, discard any incomplete trailing row under that lock. Commit
each complete row to disk before advancing dependent state. Use same-directory temp files,
flush to disk, rename and sync the directory for durable JSON and digest files.

`win-nightly run` exits 0 when every enabled job is green, 1 when any is red, 3 when none is red
but any is not-run, 2 on a usage error. Under the nightly lock, replay results at every run
start, at every reconcile and after new final rows. Start after the last complete row counted
in `~/.local/state/win-nightly/notified.json` (zero on first use). Read rows in order.
For each final job row, compare with the preceding final row for that job, including history
before the cursor. Queue a first or changed red or not-run, a changed failing set on red, or a red-to-green recovery.
Suppress repeated not-run with the same reason.
Use the saved digest files for both rows. Ignore disabled and run-level rows for alerts.
For `missed`, node-watch sends the date-level alert once for all jobs.

Save the new row cursor and the pending queue together in one atomic replacement of
`notified.json`. Include earlier unsent entries. Send only after the save succeeds. Use the
job name, verdict, fail count and a fixed phrase per reason. Bound the sender timeout. Keep each entry until the sender
returns zero, then save the remaining queue with the same cursor. A crash after Slack accepts
a message but before the save can repeat that message. For example: "Windows nightly: the CLI Windows
tests started failing tonight (3 tests). The engine Windows tests pass." A disabled job never
triggers Slack.

### 4.6 node-watch entry

- Status line: `dell-win  BUSY <label> <age> | IDLE <age>  C: <gb> GB  build <n>  pause to <date>  last nightly <date> <verdicts>`.
- Busy means `current.json` names a live pid; a dead pid shows `IDLE (stale holder)`.
- Events, each raised once per state change through the existing `alerted` set:
  - `START dell-win <label>` for each new `START` line in the lane event log (read through the
    same offset as DONE, so a job that starts and ends between two polls still shows both).
  - `DONE dell-win <label> rc=<n> <reason>` for each new complete line in the lane event log
    (stored byte offset moved only past lines ending in a newline; a file shorter than the
    offset restarts at 0). node-watch appends its event lines first and writes `state.json`
    (with the new offset) only after the append succeeds; the live code writes state first
    (`B:node-watch` line 359), and WL3 swaps that order for all events. A failed append leaves
    the offset where it was, so the next poll raises the lines again: at least once, never lost.
  - `STALLED dell-win <label>` when the holder's log has a `win-run: running:` line
    (`winrun.ps1` line 132) and has not grown for 10 minutes. Lock waits, the memory wait and the
    venv build come before that line and never raise STALLED.
  - `UNREACHABLE dell-win` when the probe returns nothing, once per outage.
  - `PAUSE dell-win ends <date>` when the update pause ends within 3 days, and
    `PAUSE dell-win ended` once it has passed; at most once per UTC day.
  - `NIGHTLY-MISSED dell-win <date>` for each expected slot without a scheduled start between 07:30 and 08:30 UTC.
    Mark manual runs (`--now`) in their records so they cannot mask a missed cron slot.
    Start the date walk at the slot stored in `armed`. Skip all earlier dates. Compare run
    start times with each deadline, so a later start cannot hide a missed slot.
    On each armed poll call `win-nightly reconcile`. It takes the nightly lock without waiting.
    If busy, retry next poll and keep the date checkpoint. For each due missed date, reconcile
    checks `results.tsv` by UTC date and job for a final `missed` row. Append the absent rows,
    one per enabled job for that slot, with verdict `not-run`, reason `missed` and a stable missed-slot run ID.
    Keep the missed slot and its enabled job list in a dated recovery record before its first row.
    Distinguish this record from a scheduled start. Reuse that list on retry.
    Finish partial dates before reporting success. After saving its own record, a run start repairs earlier records and fills missed slots
    before launching jobs. Exclude the active run from interrupted-run recovery. Node-watch reads the reconciled dates and advances `nightly_checked_through`
    only after it records each local event and pending send, including after a devbox outage.
  - `NIGHTLY-INCOMPLETE dell-win <date>` for an unfinished run once its lock is free.
    Preserve an interrupted marker in the closed record so a later poll can report recovery.
    For both date events, append the local event before saving its dedupe key and pending send
    together in `state.json`. Retry pending sends each poll until success.
  - `NIGHTLY dell-win <job> <verdict>` when a `final=1` row changes a job's verdict.
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
  ssh or log-check failure; 1 when a log ending `EXIT 0` carries `WINRUN FAIL`; 2 for a pytest collection failure (`tests`, `EXIT 2`) or for usage, a bad
  `WINRUN_LABEL`, a taken label or a refused retry (new, no event line); 130 or 143 on INT or TERM (new). The old list is in
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
- Lane event lines: `START`, label, `repo=`, `sha=` (40 hex), `in=` (12 hex), `retry_of=`, UTC
  time; `DONE`, label, `rc=`, `reason=`, `repo=`, `sha=`, `in=`, `retry_of=`, UTC time.
- `results.tsv`: the 15 columns of section 4.5.
- `jobs.json`: `name`, `repo`, `paths`, `command`, `disabled`, `green`.
- Probe lines: `CDISK`, `BUILD`, `PAUSE`.

### 6.4 FK shapes

N/A: this plan moves no table data and handles no foreign keys; it runs test jobs and reads
their logs.

### 6.5 Output surfaces

- `~/.cache/win-run/logs/<label>.log` (same format plus header lines, 0600), `<label>.retried`
  and `~/.cache/win-run/claims/<label>/`.
- `~/.cache/win-run/events.log` and `~/.cache/win-run/current.json` (new).
- `~/.local/state/win-nightly/results.tsv`, `fails/<label>.txt` (digests only), `notified.json`,
  `runs/<date>/<run>.json`, `armed` and `cron.log` (new, folder 0700).
- `~/.cache/node-watch/status.txt` and `events.log` (new `dell-win` lines).
- Slack: one plain-language line on change, through `lane_slack.py`.
- The vault runbook and the CLI record (WL4). Row 6 itself sits at `docs/roadmap/groups/release.md:19`.

## 7. Class table

| # | Class | Applies | Closing structure | Sentry or test | Mutation |
|---|---|---|---|---|---|
| 1 | value-free text | yes: results, Slack, `cron.log`, file modes | test and collection IDs hashed inside pytest; Slack text built from fixed fields; private files | AT-9, AT-10 | M-11 copy the log tail into the Slack text; M-17 store the raw id; M-22 send `win-run` output to `cron.log` |
| 2 | cleanup | yes: holder file, nightly worktrees | one `cleanup` after the lock, pid-checked; resets limited to `~/decoy-nightly/win/` | AT-3, AT-8 | M-3 keep the line 54 bundle-only trap |
| 3 | state | yes: verdicts, dedupe, alert delivery | one evidence check and verdict table, locked recovery by run/job or missed date/job, first slot in `armed`, atomic cursor and queue, stored offsets and poll lock on both writer routes | AT-5, AT-8, AT-9, AT-13 | M-6 map 75 to green; M-18 ignore `rc`; M-23 mark an alert sent on a non-zero send; M-24 read non-final rows, M-29 to M-34 |
| 4 | route | yes: gate, retry, nightly, watch | every route goes through `win-run`; the nightly never talks to Windows itself | AT-6, AT-10 | M-8 skip the `ls-remote` compare |
| 5 | referential | yes: labels and retry links | every label reserved with `mkdir` under the lock; `retry_of` must name a failed first attempt with the same repo, full SHA and `in`; retry claimed with `mkdir` under the lock | AT-2, AT-4 | M-5 drop the retry claim; M-25 drop the label reservation; M-26 skip the `in` compare |
| 6 | untrusted input | yes: `WINRUN_LABEL`, catalog paths | label regex; path regex and `git cat-file` | AT-2, AT-7 | M-2 skip the label check |
| 7 | toctou | yes: two retries or two same-label calls at once | checks and claims run after `flock 9` | AT-2, AT-4 (concurrent cases) | M-19 run the checks before the lock |
| 8 | weak tests | yes | every unit AT has a mutation that must fail it; fixtures cut from real lane logs; live ATs read `EXIT` lines and rows | section 8 | M-7 retry on `tests` |
| 9 | refactor | no | N/A: no existing behaviour is restructured; old exit codes and log lines stay | N/A, nothing moves | N/A, nothing to mutate |
| 10 | frozen contract | yes: the lane log format | the SHA line and final `EXIT n` line stay; lines are only added at the top | AT-LANE-1 rerun in AT-10 | M-1 keep writing the dead queue path |

## 8. Acceptance tests (red first)

"Unit" means stdlib `unittest` tests of pure functions run on the Mac, or the bash test run on
Dell WSL (section 11). "Live" means a real run against the Dell, read by `EXIT` lines, event
lines and rows. Fixtures for log parsing are cut from real lane logs in `~/.cache/win-run/logs/`.

| AT | Slice | Kind | Behaviour | Red today because | Mutation |
|---|---|---|---|---|---|
| AT-1 | WL1 | live | each `win-run` run appends one `START` line once the holder is set and each end one `DONE` line with label, final rc, reason word, repo, 40-hex SHA and `in` digest to `~/.cache/win-run/events.log`, for a green run, a `tests` run and an `ssh` end (bad host; also a unit case in the bash test with a failing ssh stub at line 44, which must not abort cleanup under `set -u`); with `WINRUN_QUEUE_LOG` set the old line also goes there; with it unset nothing is written under `/tmp/claude-1000/`; `~/.cache/win-run` and its subfolders are 0700 and new logs 0600 | the line goes to the hard-coded scratchpad path | M-1 keep the hard-coded path |
| AT-2 | WL1 | unit (bash) | `WINRUN_LABEL=n20261125t0730-cli-win-a1` names the log; `../x`, an upper-case label and a label with a trailing newline and a 49-character label exit 2 before the lock; a taken label exits 2 after the lock, before any ssh call, and writes no event line; a label used by a run that ended `ssh` (no log) is still refused on reuse; a label that has a log from before WL1 and no claim folder is refused; of two queued callers with the same label, the second exits 2 and the first's log and event lines are intact (an ssh stub on `PATH` records calls) | no override exists | M-2 skip the regex check; M-25 drop the reservation |
| AT-3 | WL1 | live | `current.json` exists while the job holds the lock; after a normal end, an `ssh` end and a `kill -TERM` of `win-run` during the job pipeline it is gone, the devbox process has ended within 10 seconds of the signal and the event line says `killed`; a queued waiter killed with TERM leaves the holder's file in place; the record notes whether the Windows side kept running | no holder file | M-3 keep the line 54 trap |
| AT-4 | WL1 | unit (bash) and live | refused with exit 2 and no event line: a first attempt with `rc=0`, a first attempt on a different SHA, another repo, a narrower command (different `in`), a first attempt that is itself a retry, a second retry of the same label, a retry with a changed `WINRUN_STALL_MIN`, `WINRUN_TIMEOUT_MIN` or `WINRUN_MIN_FREE_GB`, a retry started while a green first attempt still holds the lock (it waits, then is refused), and one of two retries started together; allowed: a retry with the original command, a retry started while a red first attempt holds the lock (it waits, then runs), and a retry of a first attempt that has no log (`ssh` end); live: a retry of a red first label runs and its log starts `win-run: retry of <label> attempt 2` | no retry link | M-4 allow a retry of a retry; M-5 drop the claim; M-19 check before the lock; M-26 skip the `in` compare |
| AT-5 | WL2 | unit | `decide()` returns the section 4.3 verdict and retry for every row, including: the recorded rc 1 log ending `EXIT 1` with a windows-marked skip turned into a failure (red, `tests`); a synthetic log ending `EXIT 0` with a `WINRUN FAIL` line and rc 1 (red); rc 255 `logcheck` with a log ending `EXIT 0` (red); rc 0 with all tests skipped (red); rc 0 with a wrong-SHA proof line (red); rc 75 with no `lock` or `running:` line (retry, then not-run); every attempt 2 row of section 4.3; no `DONE` line (not-run); a `DONE` line whose `in` differs from the run's (not-run); an older green `DONE` line for the same label from before the call with `win-run` exit 2 (not-run, `no-result`); a failed collection with fresh matching DONE rc 2, reason `tests` and final `EXIT 2` (red, no retry); rc 2 with no fresh DONE despite an old matching rc 2 and log (not-run, `no-result`); a `DONE` line whose `rc` differs from the exit code (not-run); M-18 case: otherwise green evidence with a fresh DONE rc 1 matching the process, reason `ok` and log ending `EXIT 0` (red, `logcheck`) | no runner | M-6 map 75 to green; M-7 retry on `tests`; M-18 ignore `rc`; M-29 treat every rc 2 as a refusal |
| AT-5b | WL1 | unit (bash) | `classify()` returns the section 3 word for: the real log w96727b-3812486 (PowerShell error, no `running:`, no `EXIT`: `setup`), a 255 log with a uv sync failure (`deps`), the same truncated log (`running:`, no `EXIT`) with raw rc 255 (`ssh`) and with raw rc 0 and wrapper final rc 255 (`logcheck`), a `WINRUN STALLED` log (`stall`), rc 143 (`killed`), a log ending `EXIT 0` with `WINRUN FAIL` (`logcheck`), and an unmatched end (`unknown`); the order in the table holds when two rules match | no classifier | M-20 pass final rc as the raw input to classify: the truncated raw rc 0 / final rc 255 fixture changes from `logcheck` to `ssh`; M-21 drop the `unknown` fallback |
| AT-6 | WL2 | unit | when `origin/main` after fetch differs from `ls-remote` main, the repo's jobs are `not-run: stale-main` and `win-run` is never called | no runner | M-8 skip the compare |
| AT-7 | WL2 | unit | a catalog path missing at the head makes the job red with `missing=` and no `win-run` call, on this night and the next; a path with a trailing newline, an absolute path or a parent segment is a usage error | no runner | M-9 run with the paths that exist |
| AT-8 | WL2 | unit | a second `win-nightly run` while the first holds `~/.cache/win-nightly.lock` writes no run record, writes one `job=*` `overlap` row and exits 3 within 5 seconds (test timeout 10 seconds); the next run's change comparison ignores that row; a worktree path outside `~/decoy-nightly/win/` is refused; a nightly sent TERM during the 20-minute memory backoff writes `interrupted` final rows for the open jobs; a run record left without `end` (kill -9) gets those rows from `win-nightly reconcile` or from the next start (test both recovery routes); interrupt after a final red row and before removing its job, then reconcile twice: exactly one final row for that run and job retains the original red; after two poll calls to reconcile, each enabled job has exactly one final not-run row with reason `missed` for each missed date, including a date with a partial set of rows; two runs started in the same second get different labels | no runner | M-10 block on the lock; M-27 skip reconcile; M-30 omit the existing final-row check; M-31 append missed rows without checking date and job |
| AT-9 | WL2 | unit | from a real lane log plus a planted `FAILED tests/x.py::t - assert 'SECRET-VALUE-7731' == ...` line, a planted `FAILED tests/x.py::t[SECRET-PARAM-5521]` line and a planted skip id `tests/x.py::s[SECRET-SKIP-8812]`, `fail_ids()` returns digests only (from `WINRUN FAILID` lines; `test_t[left - 1]` and `test_t[left - 2]` give two digests) and none of the three sentinels is in `results.tsv`, `fails/`, `notified.json`, `cron.log` or the Slack text; Slack fires on a new red, a new not-run, a changed failing set or red to green, and not for an unchanged red or a disabled job; a real failed collect report emits the expected digest and no raw ID in the marker; fresh matching DONE rc 2 with `tests` and `EXIT 2` queues red with that digest; rc 2 without fresh DONE queues a new not-run with no stale digest; kill after committing a red row and before enqueue, then replay by reconcile and separately by run start: each queues and sends the lost alert once; inject failure during atomic replacement and recover the alert from the old cursor; with the sender stubbed to fail, the alert stays pending and the next run sends it even when that night is an unchanged red | no runner | M-11; M-12 alert on every red; M-17; M-22; M-23; M-32 advance the cursor before saving the queue; M-33 omit failed collection reports |
| AT-10 | WL2 | live | `win-nightly run --now` writes rows whose SHAs equal `ls-remote` main for both repos, whose logs have the SHA line and a final `EXIT` line, and whose verdicts match `decide()` on the event lines; a row with a failed test or collection report has `fail_count` > 0; `crontab -l` has exactly one `win-nightly` line; `~/.local/state/win-nightly` is 0700 and its files 0600 | no nightly | none of its own; AT-5 and AT-9 hold the logic mutations |
| AT-11 | WL2 | live | a test catalog job that sleeps, run with `WINRUN_STALL_MIN=1`, gives two logs, rows `attempt 1` and `attempt 2 retry_of=<label 1>` with `final=0` then `final=1`, and a final red | no nightly | none of its own; M-4 sits in AT-4 |
| AT-12 | WL3 | unit | `parse_win_probe()` reads `CDISK`, `BUILD`, `PAUSE`, ignores bad lines and returns None for empty output; the probe call carries `ConnectTimeout=8` and the 40-second timeout; the encoded payload is under 8191 characters | no Windows node | M-13 raise on a bad line |
| AT-13 | WL3 | unit | given state before and after, `win_events()` raises each section 4.6 event once: START; DONE from new event lines (offset kept, truncated file restarts at 0); STALLED only after a `running:` line and 10 minutes without growth; UNREACHABLE once per outage; PAUSE at most daily; NIGHTLY-MISSED per date with no run record after 08:30 UTC only when `armed` exists, for both deployment orders (WL3 before WL2, WL2 before WL3), and for a date skipped wholly by a devbox outage; install after 08:30 UTC, poll twice and see no event, send or missed row that day; after the first expected slot is missed, two polls leave exactly one final not-run row per enabled job with reason `missed` and one date alert; several polls with a failing sender raise exactly one local MISSED event and keep retrying the send; NIGHTLY-INCOMPLETE for a record without `end` and a free nightly lock; a nightly that overlaps the next night's start does not count as that night's start; an event-log append failure leaves the offset in place and a fresh poll raises the lines; START and DONE for a job that starts and ends between two polls; a poll between a red attempt 1 and a green attempt 2 raises no red NIGHTLY; NIGHTLY on a verdict change; no IDLE event for `dell-win`; a half-written last event line is not read and the offset stops before it; a second poll holding no lock emits nothing, for both the bare and the `poll` route | no Windows node | M-14 drop the dedupe; M-15 raise STALLED during a lock wait; M-23; M-24; M-28 write `state.json` before the event append; M-31; M-34 start the walk on the install date |
| AT-14 | WL3 | unit | the status table has the `dell-win` line with the section 4.6 fields for busy, idle, stale-holder and unreachable states | no Windows node | M-16 print BUSY for a dead holder pid |
| AT-15 | WL3 | live | with cron running, a real `win-run` job shows `START dell-win` and `DONE dell-win ... rc=` in `~/.cache/node-watch/events.log`, each within 4 minutes, and no IDLE line for `dell-win` | no Windows node | none of its own; the unit mutations M-14 to M-16 cover the logic |
| AT-16 | WL4 | doc | the runbook is in the vault, `qmd search "windows lane runbook"` finds it, it names every exit code of section 6.1, every reason word of section 3 and every event of section 4.6, and the memory note's Monitor grep includes the new event names | no runbook | n/a (reviewer doc check) |

AT-LANE-1 from WIN-FEAS (`docs/plans/2026-11-18-win-feas.md:711`) stays green: AT-10 reruns it on
the nightly logs.

## 9. Reuse inventory

- `B:win-run` and `B:win-run.d/winrun.ps1`: exact-head proof, lock-keyed venv, one-job locks,
  memory gate, stall guard and the AT-LANE-1 log check. WL1 adds about 60 lines. `winrun.ps1`
  does not change.
- `B:win-run.d/winrun_plugin.py`: WL2 reuses the skipped-test check and terminal summary for failure digests.
- `B:node-watch`: `sh()` with timeouts, the thread pool in `poll()`, the `state.json` store, the
  `alerted` dedupe set, and the events and status files.
- The webhook setting used by `~/.claude/scripts/slack-notify.sh`: `lane_slack.py` reads a copy
  of it; the shared script is not changed.
- `agent-config/sync.sh`: puts `~/bin` into git; each slice runs it once after its change.
- The WIN-FEAS 4.3 job list and path set (`docs/plans/2026-11-18-win-feas.md:505`) and the
  commands gate readers already run (the `running:` lines of the lane logs): the source of the
  catalog.

## 10. Frozen contracts touched

No CLI or engine contract. One tooling contract: the lane log format read by gate readers and
by AT-LANE-1 (a `win-run: SHA requested` line, last line `EXIT n`). This plan adds header
lines at the top and `WINRUN FAILID <16 hex>` lines in the pytest terminal summary (WL2), which
come before the final `EXIT n` line. The `win-run` arguments do not change; new behaviour is opt-in through
environment variables, except the event line, which is always written.

## 11. Placement

`~/bin` has no CODEMAP; the tools follow the existing `~/bin` layout (`<tool>` plus a
`<tool>.d/` folder, as `win-run.d/` already does).

| File | Slice | Kind | Budget | Beside |
|---|---|---|---|---|
| `B:win-run` | WL1 | edit | 85 to about 185 lines | itself |
| `B:win-run.d/tests/test_win_run.sh` | WL1 | new | about 190 lines (AT-2, AT-4, AT-5b with an ssh stub) | `winrun.ps1` |
| `B:win-nightly` | WL2 | new, Python stdlib | about 350 lines (run records, reconcile and alert replay) | `B:win-run` |
| `B:win-run.d/winrun_plugin.py` | WL2 | edit | 22 to about 42 lines (`WINRUN FAILID`) | itself |
| `B:win-run.d/lane_slack.py` | WL2 | new, Python stdlib | about 40 lines | `jobs.json` |
| `~/.config/win-lane/slack.env` | WL2 | new, 0600, not in `agent-config` | one line | n/a |
| `B:win-run.d/jobs.json` | WL2 | new | about 40 lines | `winrun_plugin.py` |
| `B:win-run.d/tests/test_win_nightly.py` | WL2 | new | about 315 lines | the bash test |
| `B:node-watch` | WL3 | edit | 373 to about 480 lines | itself |
| `B:node-watch.d/tests/test_win_lane.py` | WL3 | new | about 175 lines | new folder, same pattern as `win-run.d/` |
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
| WL2 | devbox `~/bin`, crontab | `win-nightly` (worktrees, `ls-remote` check, path check, `decide()`, retries, results, change-only Slack with a pending queue, overlap lock, run records and `reconcile`, `--print-cmd`); `lane_slack.py`; the `WINRUN FAILID` hook in `winrun_plugin.py`; `jobs.json`; one crontab line and the `armed` file | about 450 lines plus 315 test lines | Codex | WL1 |
| WL3 | devbox `~/bin` | node-watch Windows probe, `dell-win` status line, `win_events()`, event-log reader, poll lock, atomic `state.json` | about 110 lines plus 175 test lines | Codex | WL1; its NIGHTLY events read WL2's files and stay quiet until they exist |
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
  after it merges, and `demo-win` is turned on (with `"green": "exit0"`) only when its section 4.2
  inputs all exist.

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
