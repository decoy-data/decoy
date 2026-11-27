#!/usr/bin/env bash
# Run the local gates in CI order and print an EVIDENCE block to paste.
# Usage: scripts/dev/gates.sh [--keep-going] [--baseline] [--baseline-file FILE]
#        [--write-baseline FILE] [--outcomes-file FILE] [--full] [--steps LIST] [test paths...]
#   --keep-going  run every step even after a failure (default: stop at the first)
#   --baseline    rerun every step on origin/main in a temporary detached worktree, with the
#                 SAME venv, and diff the failures of every step (test ids; mypy/ruff error
#                 lines). Implies --keep-going. Fails only on branch-only failures: a step main
#                 passes, a crash or kill, an unidentified failure, or more of a failure than
#                 main has. Failures main shares are not the branch's.
#   --baseline-file FILE
#                 with --baseline (implied): do NOT rerun origin/main. Load the stored
#                 failing-id baseline FILE, run only the branch pass, then report new
#                 failing ids (exit 1), baseline ids that now pass, and the collected
#                 count delta. Exit 2 before running when FILE is for another repo, was
#                 written in a different run mode (workers, dist, platform, order), is
#                 malformed, or is behind origin/main in anything but Markdown or generated
#                 diagrams that no test reads. Fails unless a whole-suite tests step finished
#                 with collected > 0, the branch skips no more tests than the baseline did,
#                 and it collects no fewer tests than the baseline beyond the test ids in
#                 test files the branch deleted. A missing totals line, or one that
#                 disagrees with the JUnit failure count, exits 3.
#   --write-baseline FILE
#                 after a full-suite run (--full or `tests`, steps include tests, all
#                 steps ran, pytest exit 0 or 1, JUnit with collected > 0) write {repo,
#                 main_sha, head_sha, collected, skipped, failing, workers, dist, platform,
#                 order, order_seconds, file_seconds} to FILE; refused for a selection, and
#                 unless HEAD equals origin/main with a clean tree. Needs origin/main. A
#                 failing id with a memory address in it is refused (it never matches again).
#                 The exit code is still 1 after a successful write when main has known failures.
#   --steps LIST  comma list from: env,ruff,lintdebt,format,mypy,sentry,layers,tests (default: all)
#                 layers bootstraps .venv-layers from requirements-dev.lock and runs only
#                 $LAYER_TEST there. `--steps layers` alone needs no ordinary .venv and no
#                 origin/main.
#   lintdebt      per-file counts of extra ruff rules (BLE001, ANN401, PTH, C901, T20, ...) against
#                 tests/sentry/baselines/lint-debt.json; new debt fails, `scripts/dev/lintdebt.py
#                 --shrink` lowers the baseline after a fix. CI's `ruff check` does not select them.
#   --full        run the whole `tests` directory (same as passing `tests`)
#   --outcomes-file FILE
#                 after the run write one `<outcome>\t<id>` line per collected test of the tests
#                 step (passed, failed, error or skipped; ids only, never a message), sorted, from
#                 both passes. Two runs of one head are equal when their files are byte-equal.
# GATES_WORKERS=N|auto (default auto) sets the pytest-xdist worker count of the tests step.
#   N > 1 runs two passes that partition the selection: a parallel pass (-n N --dist loadfile,
#   tests marked `serial` deselected), then a plain serial pass of the `serial` tests, which
#   need the host to themselves (a wall-clock bound, a memory measurement, a snapshot of the
#   checkout or the real home). Both JUnit files count as one run. N = 1, or a venv without
#   pytest-xdist, is one plain pytest run in collection order. auto is min(cpus, 4), at most 2 on
#   a host under 14 GB (1 when under 4 GB is free). The workers: line of the EVIDENCE header names
#   the choice. A stored baseline records it and refuses a run with another count (exit 2); pin
#   GATES_WORKERS for any baseline write or compare. A bad value exits 2.
#   test paths    default: tests touching files changed against origin/main. That is a
#                 SELECTION, not the full suite; the header says so. Use --full (or `tests`).
set -uo pipefail

# Repo config. Mirrors .github/workflows/ci.yml (ruff and pytest jobs).
REPO_NAME=decoy
RUFF_PATHS=(src tests)
MYPY_ARGS=()           # ci.yml has no mypy gate; the step reports SKIP
FORMAT_GATE=0          # ci.yml runs ruff check only (main is not format-clean); SKIP
# test_sentry_manifest.py fails when a file in its SENTRIES manifest is not collected here
SENTRY_PATHS=(
  tests/sentry
  tests/unit/test_cli_surface.py
  tests/unit/test_surface_docs_consistency.py
  tests/unit/test_no_dead_command_strings.py
)
# The one sentry outside the sentry step: the import-layer contract runs in its own venv, in the
# `layers` step. Every other pytest route ignores it.
LAYER_TEST=tests/sentry/layout/test_import_layers.py
LAYER_IGNORE=(--ignore=$LAYER_TEST)
PYTEST_ARGS=()
# The `-m` expression of PYTEST_ARGS, empty when there is none. A parallel run adds `not serial`
# and `serial` to it; with no expression the passes are exactly `not serial` and `serial`, never
# an empty parenthesis or a leading `and`.
PYTEST_MARK=''
for ((i = 0; i + 1 < ${#PYTEST_ARGS[@]}; i++)); do
  [ "${PYTEST_ARGS[$i]}" = -m ] && PYTEST_MARK=${PYTEST_ARGS[$((i + 1))]}
done
if [ -n "$PYTEST_MARK" ]; then
  PAR_MARK="($PYTEST_MARK) and not serial" SER_MARK="($PYTEST_MARK) and serial"
else
  PAR_MARK='not serial' SER_MARK=serial
fi
SRC_MATCH='src/*.py'   # changed files that map to a dotted module
SRC_STRIP='src/'       # prefix removed before turning a path into a module
PYPATH_DIRS=(src)
IMPORT_PKG=decoy
# Files a stored baseline may be behind main by without going stale, besides Markdown: output
# that .github/workflows/regen-diagrams.yml commits to main after a merge. Like Markdown, a file
# here still makes the baseline stale when a test under tests/ names it.
GENERATED_UNREAD_GLOBS=('docs/diagrams/*.svg')
# Directories a test reads by walking them. The CLI has none (tests/sentry/test_baseline_registry.py
# walks docs/ for json and toml only, and it is a sentry, so DOC_WALK_GUARDS covers it).
DOC_WALK_ROOTS=()
# Any stored failing id under a sentry path makes every main move stale, because a Markdown fix on
# main could hide a re-break on the branch. Derived from SENTRY_PATHS so there is one list.
DOC_WALK_GUARDS=(${SENTRY_PATHS[@]+"${SENTRY_PATHS[@]}"})

ROOT=$(git rev-parse --show-toplevel) || exit 2
VENV=${DECOY_VENV:-$ROOT/.venv}
BIN=$VENV/bin
KEEP=0 BASELINE=0 FULL=0 BASEFILE='' WRITEBASE='' OUTCOMES='' STEPS=env,ruff,lintdebt,format,mypy,sentry,layers,tests PATHS=()
while [ $# -gt 0 ]; do
  case $1 in
    --keep-going) KEEP=1 ;;
    --baseline) BASELINE=1 ;;
    --full) FULL=1 ;;
    --baseline-file|--write-baseline|--outcomes-file|--steps)
      # A missing operand, or another flag where it belongs, is a usage error: swallowing it
      # would turn `--write-baseline --full` into a baseline file named --full. An empty --steps
      # list is allowed (it runs nothing and the gate then says no step ran); an empty path is not.
      what='a file operand'; [ "$1" = --steps ] && what='a list of steps'
      if [ $# -lt 2 ] || { [ -z "$2" ] && [ "$1" != --steps ]; }; then
        echo "gates: $1 needs $what" >&2; exit 2
      fi
      case $2 in -*) echo "gates: $1 needs $what, not the flag $2" >&2; exit 2 ;; esac
      case $1 in
        --baseline-file) BASEFILE=$2; BASELINE=1 ;;
        --write-baseline) WRITEBASE=$2 ;;
        --outcomes-file) OUTCOMES=$2 ;;
        --steps) STEPS=$2 ;;
      esac
      shift ;;
    -h|--help) awk 'NR > 1 { if (!/^#/) exit; print }' "$0"; exit 0 ;;
    -*) echo "gates: unknown flag $1" >&2; exit 2 ;;
    *) PATHS+=("$1") ;;
  esac
  shift
done
# The outcomes writer would overwrite the stored baseline it just compared against.
if [ -n "$OUTCOMES" ] && [ -n "$BASEFILE" ] && [ "$OUTCOMES" -ef "$BASEFILE" ]; then
  echo "gates: --outcomes-file and --baseline-file name the same file" >&2; exit 2
fi
# A baseline verdict compares every step, so a step skipped after an early failure can never
# read as shared with main.
if [ $BASELINE = 1 ]; then KEEP=1; fi
for name in ${STEPS//,/ }; do
  case $name in env|ruff|lintdebt|format|mypy|sentry|layers|tests) ;; *) echo "gates: unknown step $name" >&2; exit 2 ;; esac
done
LAYER_VENV=$ROOT/.venv-layers
LAYERS_ONLY=0
# The layer venv is bootstrapped once per run, here; the layers step only runs pytest in it.
LAYER_BOOT=skip
case ",$STEPS," in
  *,layers,*) if DECOY_VENV=$LAYER_VENV bash "$ROOT/scripts/dev/bootstrap.sh" >&2; then LAYER_BOOT=ok; else LAYER_BOOT=fail; fi ;;
esac
if [ "$STEPS" = layers ]; then
  # The layer venv is the only venv this run needs, so it also runs the reporter.
  LAYERS_ONLY=1
  [ $LAYER_BOOT = ok ] || { echo "gates: FAIL: could not bootstrap $LAYER_VENV" >&2; exit 2; }
  VENV=$LAYER_VENV BIN=$LAYER_VENV/bin
fi
[ -x "$BIN/python" ] || { echo "gates: no venv at $VENV; run scripts/dev/bootstrap.sh" >&2; exit 2; }
# Worker count for the tests step, recorded in a stored baseline's run mode. The reporter owns the
# rule (_gate_workers.py); a venv without pytest-xdist resolves to 1 there and says why. Only
# stdout is captured: the reporter's own diagnostics reach the terminal as written. Exit 64 is its
# usage error (GATES_WORKERS is not a number or auto); any other failure is a crash.
WORKERS_RC=0
WORKERS_LINE=$("$BIN/python" "$ROOT/scripts/dev/_gates_report.py" --workers) || WORKERS_RC=$?
if [ $WORKERS_RC != 0 ]; then
  if [ $WORKERS_RC = 64 ]; then exit 2; fi
  echo "gates: FAIL: no complete EVIDENCE block (the reporter failed before the run)" >&2; exit 3
fi
WORKERS=${WORKERS_LINE%% *}
WORKERS_WHY=${WORKERS_LINE#* }
OUT=$(mktemp -d "${TMPDIR:-/tmp}/gates.XXXXXX")
[ -n "$OUT" ] && [ -d "$OUT" ] || { echo "gates: FAIL: cannot create a temp dir" >&2; exit 3; }
# Each tests pass gets its own basetemp here, removed on exit: pytest's default
# /tmp/pytest-of-<user> keeps the last three runs. Kept directly under /tmp, not under $OUT:
# TMPDIR can be long (T3 sets /tmp/decoy-out-<label>), and tests that bind AF_UNIX sockets under
# tmp_path fail once the path passes the 104-108 byte limit. /tmp on purpose, ignoring TMPDIR.
TMP_ROOT=$(mktemp -d /tmp/gt.XXXXXX)
[ -n "$TMP_ROOT" ] && [ -d "$TMP_ROOT" ] || { echo "gates: FAIL: cannot create a basetemp dir" >&2; exit 3; }
mkdir -p "$TMP_ROOT/root"
# Pytest runs that tests start themselves have no --basetemp; this moves their default root too.
export PYTEST_DEBUG_TEMPROOT=$TMP_ROOT/root
WT=$OUT/baseline-tree
MBT=$OUT/merge-base-tree
STORED=$OUT/stored-baseline.json
# shellcheck disable=SC2329  # invoked by the EXIT trap
cleanup() {
  local d
  for d in "$WT" "$MBT"; do [ -d "$d" ] && git -C "$ROOT" worktree remove --force "$d" 2>/dev/null; done
  rm -rf -- "${TMP_ROOT:?}"
  return 0
}
trap cleanup EXIT

changed_tests() {
  local base f mod
  base=$(git -C "$ROOT" merge-base origin/main HEAD) || return 1
  { git -C "$ROOT" diff --name-only "$base"; git -C "$ROOT" ls-files --others --exclude-standard; } |
    sort -u | while read -r f; do
      [ -f "$ROOT/$f" ] || continue
      # shellcheck disable=SC2254  # SRC_MATCH is a glob on purpose
      case $f in
        tests/*test_*.py) echo "$f" ;;
        $SRC_MATCH)
          mod=${f#"$SRC_STRIP"}; mod=${mod%.py}; mod=${mod%/__init__}; mod=${mod//\//.}
          (cd "$ROOT" && grep -rlE --include='test_*.py' "${mod//./\\.}([^A-Za-z0-9_]|\$)" tests) ;;
      esac
    done | grep -vxF "$LAYER_TEST" | sort -u
}

if [ $FULL = 1 ] && [ ${#PATHS[@]} -eq 0 ]; then
  PATHS=(tests)
  SELECTION="full suite (tests)"
elif [ ${#PATHS[@]} -eq 0 ] && [ $LAYERS_ONLY = 1 ]; then
  SELECTION="none: the layers step runs only $LAYER_TEST"
elif [ ${#PATHS[@]} -eq 0 ]; then
  if ! git -C "$ROOT" rev-parse -q --verify origin/main >/dev/null; then
    echo "gates: origin/main missing; run: git fetch origin main" >&2; exit 2
  fi
  # No read-into-array builtin: the Mac runner has bash 3.2.
  SELECTED=$(changed_tests)
  while IFS= read -r p; do [ -n "$p" ] && PATHS+=("$p"); done <<EOT
$SELECTED
EOT
  SELECTION="changed vs origin/main: ${#PATHS[@]} test file(s)"
else
  SELECTION="explicit: ${PATHS[*]+${PATHS[*]}}"
fi

MAIN_SHA=$(git -C "$ROOT" rev-parse -q --verify origin/main || true)
WHOLE_SUITE=0
[ ${#PATHS[@]} -eq 1 ] && [ "${PATHS[0]}" = tests ] && WHOLE_SUITE=1
if [ -n "$WRITEBASE" ]; then
  # Refuse before spending the run on a result that could not be stored.
  if [ $WHOLE_SUITE = 0 ] || [[ ",$STEPS," != *,tests,* ]]; then
    echo "gates: --write-baseline refused: this run is a selection, not the whole suite (needs --full or the path 'tests', and the tests step)" >&2; exit 2
  fi
  [ -n "$MAIN_SHA" ] || { echo "gates: --write-baseline needs origin/main; run: git fetch origin main" >&2; exit 2; }
  # A baseline describes origin/main, so only a clean checkout of exactly that commit may store one.
  HEAD_SHA=$(git -C "$ROOT" rev-parse HEAD)
  if [ "$HEAD_SHA" != "$MAIN_SHA" ] || [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
    echo "gates: --write-baseline refused: HEAD must equal origin/main ($MAIN_SHA) and the tree must be clean" >&2; exit 2
  fi
fi

# 0 when the stored baseline (main_sha $1) is behind origin/main in something a test could read.
# A main move is harmless only if every changed path is Markdown or a GENERATED_UNREAD_GLOBS file
# outside src/ and tests/, outside DOC_WALK_ROOTS, and no file under tests/ (helpers included)
# names it. Reads the copy $STORED, never the original.
baseline_is_stale() {
  local changed f root g harmless
  git -C "$ROOT" cat-file -e "$1^{commit}" 2>/dev/null || { echo "stored main_sha $1 is not in this repository"; return 0; }
  changed=$(git -C "$ROOT" diff --name-only --no-renames "$1" "$MAIN_SHA") || { echo "could not diff $1 against origin/main"; return 0; }
  if [ -n "$changed" ] && "$BIN/python" "$ROOT/scripts/dev/_gates_report.py" --stored-failing-under "$STORED" ${DOC_WALK_GUARDS[@]+"${DOC_WALK_GUARDS[@]}"}; then
    echo "main moved and the stored failing list holds a sentry failure that a Markdown change on main could have hidden"; return 0
  fi
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    harmless=0
    case $f in
      src/*|tests/*) ;;
      *.md) harmless=1 ;;
      *)
        for g in ${GENERATED_UNREAD_GLOBS[@]+"${GENERATED_UNREAD_GLOBS[@]}"}; do
          # shellcheck disable=SC2254  # GENERATED_UNREAD_GLOBS entries are globs on purpose
          case $f in $g) harmless=1 ;; esac
        done ;;
    esac
    [ $harmless = 1 ] || { echo "main changed $f"; return 0; }
    for root in ${DOC_WALK_ROOTS[@]+"${DOC_WALK_ROOTS[@]}"}; do
      case $f in "$root"/*) echo "main changed $f, which a sentry walks"; return 0 ;; esac
    done
    if grep -rlFq -- "${f##*/}" "$ROOT/tests"; then echo "main changed $f, which a test names"; return 0; fi
  done <<EOT
$changed
EOT
  return 1
}

if [ -n "$BASEFILE" ]; then
  [ -f "$BASEFILE" ] || { echo "gates: baseline file not found: $BASEFILE" >&2; exit 2; }
  # Copy first, then check and read only the copy: the file the gate checks is the file it uses,
  # even when something rewrites the original while the suite runs.
  cp "$BASEFILE" "$STORED" || { echo "gates: could not copy the baseline file: $BASEFILE" >&2; exit 2; }
  stored_sha=$("$BIN/python" "$ROOT/scripts/dev/_gates_report.py" --check-stored "$STORED" "$REPO_NAME" "$WORKERS" "$ROOT") || exit 2
  [ -n "$MAIN_SHA" ] || { echo "gates: --baseline-file needs origin/main; run: git fetch origin main" >&2; exit 2; }
  if [ "$MAIN_SHA" != "$stored_sha" ]; then
    if reason=$(baseline_is_stale "$stored_sha"); then
      echo "gates: the stored baseline (main_sha $stored_sha) is stale against origin/main $MAIN_SHA: $reason; rewrite it with --write-baseline" >&2; exit 2
    fi
  fi
fi

pypath() { local d out=""; for d in ${PYPATH_DIRS[@]+"${PYPATH_DIRS[@]}"}; do out="$out${out:+:}$1/$d"; done; echo "$out"; }

# The layers step: run only the layer test in the layer venv bootstrapped above (pytest args in $@).
layer_step() {
  [ "$LAYER_BOOT" = ok ] || { echo "gates: could not bootstrap $LAYER_VENV"; return 2; }
  "$LAYER_VENV/bin/python" -m pytest "$@" "$LAYER_TEST"
}

# Exit code of the two tests passes as one: pytest's 5 (nothing collected) in one pass is not a
# failure when the other pass ran tests; two 5s are a failure (nothing ran); a crash code (not 0,
# 1 or 5) wins over a plain failure; else 1 beats 0. (Ported from the engine's gates.sh.)
combine_rc() {  # $1 parallel-pass rc, $2 serial-pass rc
  local a=$1 b=$2
  if [ "$a" = 5 ] && [ "$b" = 5 ]; then echo 5; return; fi
  [ "$a" = 5 ] && a=0
  [ "$b" = 5 ] && b=0
  case $a in 0|1) ;; *) echo "$a"; return ;; esac
  case $b in 0|1) ;; *) echo "$b"; return ;; esac
  if [ "$a" = 1 ] || [ "$b" = 1 ]; then echo 1; else echo 0; fi
}

# The one place that builds the tests step's command(s): the worker rule, the scrubber fallback,
# the `not serial` / `serial` split and the junit and basetemp names. Sets cmd, cmd2 (the serial
# pass; empty when the run is not parallel) and note. Reads tree, label, OUT, TMP_ROOT, WORKERS,
# jbase, pyt, LAYER_IGNORE and tests from run_steps.
split_pytest_cmds() {
  local w=$WORKERS
  note=''
  cmd2=()
  # A tree without the xdist report scrubber (origin/main before it lands) would abort a
  # parallel run on the first lone surrogate in a captured log, so that tree runs serial.
  if [ "$w" -gt 1 ] && [ ! -f "$tree/tests/_xdist_safe_reports.py" ]; then
    w=1; note=" (serial: this tree has no tests/_xdist_safe_reports.py)"
  fi
  if [ "$w" -gt 1 ]; then
    # PYTEST_ARGS is not repeated here: its -m is already part of PAR_MARK and SER_MARK. The serial
    # pass says `-n 0` because an inherited PYTEST_ADDOPTS with `-n 4` would put the serial tests
    # on workers; a command-line -n wins over addopts.
    cmd=(${pyt[@]+"${pyt[@]}"} ${jbase[@]+"${jbase[@]}"} -m "$PAR_MARK" -n "$w" --dist loadfile ${LAYER_IGNORE[@]+"${LAYER_IGNORE[@]}"} ${tests[@]+"${tests[@]}"})
    cmd2=(${pyt[@]+"${pyt[@]}"} -p no:cacheprovider -q -rfE -o junit_family=xunit1 "--junitxml=$OUT/$label-tests-serial.xml" "--basetemp=$TMP_ROOT/$label-tests-serial" -n 0 -m "$SER_MARK" ${LAYER_IGNORE[@]+"${LAYER_IGNORE[@]}"} ${tests[@]+"${tests[@]}"})
  else
    cmd=(${pyt[@]+"${pyt[@]}"} ${jbase[@]+"${jbase[@]}"} ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"} ${LAYER_IGNORE[@]+"${LAYER_IGNORE[@]}"} ${tests[@]+"${tests[@]}"})
  fi
}

run_steps() {  # $1 label, $2 tree
  local label=$1 tree=$2 name rc rc2 stop=0 p cmd cmd2 shown tests=() pyt note
  : >"$OUT/$label.steps"
  for name in ${STEPS//,/ }; do
    cmd2=() note=
    local jbase=(-p no:cacheprovider -q -rfE -o junit_family=xunit1 "--junitxml=$OUT/$label-$name.xml")
    local junit=(${jbase[@]+"${jbase[@]}"} ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"})
    case $name in
      env) cmd=(bash "$ROOT/scripts/dev/bootstrap.sh" --check) ;;
      ruff) cmd=("$BIN/ruff" check ${RUFF_PATHS[@]+"${RUFF_PATHS[@]}"}) ;;
      # extra ruff rules in report mode against the lint-debt baseline; CI's ruff check is untouched.
      # Skipped in trees that predate the script (the baseline worktree).
      lintdebt) cmd=(bash -c 'if [ -f scripts/dev/lintdebt.py ]; then exec "$0" scripts/dev/lintdebt.py --ruff "$1"; fi' "$BIN/python" "$BIN/ruff") ;;
      format) cmd=("$BIN/ruff" format --check ${RUFF_PATHS[@]+"${RUFF_PATHS[@]}"}) ;;
      mypy) cmd=("$BIN/mypy" ${MYPY_ARGS[@]+"${MYPY_ARGS[@]}"}) ;;
      # ratchet_check first (baselines never grow); skipped in trees that predate it (the baseline worktree)
      sentry)
        cmd=(bash -c 'if [ -f scripts/dev/ratchet_check.py ]; then "$0" scripts/dev/ratchet_check.py || exit 1; fi; exec "$0" -m pytest "$@"' "$BIN/python" ${junit[@]+"${junit[@]}"} ${LAYER_IGNORE[@]+"${LAYER_IGNORE[@]}"} ${SENTRY_PATHS[@]+"${SENTRY_PATHS[@]}"}) ;;
      layers) cmd=(layer_step ${junit[@]+"${junit[@]}"}) ;;
      tests)
        tests=(); for p in ${PATHS[@]+"${PATHS[@]}"}; do [ -e "$tree/${p%%::*}" ] && tests+=("$p"); done
        pyt=("$BIN/python" -m pytest)
        # A stored or compared baseline must come from the whole suite: ignore selections
        # smuggled in through PYTEST_ADDOPTS, PYTEST_PLUGINS or the config's addopts (this
        # script's own args stay, they are part of the junit array).
        if [ -n "$WRITEBASE$BASEFILE" ]; then
          pyt=(env -u PYTEST_ADDOPTS -u PYTEST_PLUGINS PY_COLORS=0 NO_COLOR=1 "$BIN/python" -m pytest -o addopts= --color=no)
        fi
        jbase+=("--basetemp=$TMP_ROOT/$label-tests")
        split_pytest_cmds ;;
      *) echo "gates: unknown step $name" >&2; exit 2 ;;
    esac
    if [ $stop = 1 ]; then rc=-2
    elif [ "$name" = tests ] && [ ${#tests[@]} -eq 0 ]; then rc=-1; cmd=("(no test paths present)")
    elif [ "$name" = layers ] && [ ! -f "$tree/$LAYER_TEST" ]; then rc=-1; cmd=("(not applicable: this tree predates $LAYER_TEST)")
    elif [ "$name" = env ] && [ "$label" = baseline ]; then rc=-1; cmd=("(same venv as branch)")
    elif [ "$name" = mypy ] && [ ${#MYPY_ARGS[@]} -eq 0 ]; then rc=-1; cmd=("(no mypy gate in ci.yml)")
    elif [ "$name" = format ] && [ $FORMAT_GATE = 0 ]; then rc=-1; cmd=("(no format gate in ci.yml)")
    else
      echo "gates: [$label] $name ..." >&2
      (cd "$tree" && PYTHONPATH=$(pypath "$tree") ${cmd[@]+"${cmd[@]}"}) >"$OUT/$label-$name.log" 2>&1
      rc=$?
      if [ "$name" = tests ]; then  # raw argv and status of each executed pass, for the T3 proof
        printf '%s\t%s\t%s\n' "$([ ${#cmd2[@]} -gt 0 ] && echo parallel || echo plain)" "$rc" "$(printf '%q ' ${cmd[@]+"${cmd[@]}"})" >"$OUT/$label-tests.passes"
      fi
      if [ ${#cmd2[@]} -gt 0 ]; then
        # Unconditional: the serial pass must run (and be read) even when the parallel pass failed.
        echo "gates: [$label] $name (serial pass) ..." >&2
        (cd "$tree" && PYTHONPATH=$(pypath "$tree") ${cmd2[@]+"${cmd2[@]}"}) >"$OUT/$label-$name-serial.log" 2>&1
        rc2=$?
        printf '%s\t%s\t%s\n' serial "$rc2" "$(printf '%q ' ${cmd2[@]+"${cmd2[@]}"})" >>"$OUT/$label-tests.passes"
        if [ $rc2 != 0 ] && [ $rc2 != 5 ]; then tail -n 15 "$OUT/$label-$name-serial.log" | sed "s/^/  $label $name serial| /" >&2; fi
        rc=$(combine_rc "$rc" "$rc2")
      fi
      if [ $rc != 0 ]; then
        tail -n 15 "$OUT/$label-$name.log" | sed "s/^/  $label $name| /" >&2
        [ $KEEP = 1 ] || stop=1
      fi
    fi
    [ $rc = -1 ] && shown=${cmd[*]+${cmd[*]}} || shown=$(printf '%q ' ${cmd[@]+"${cmd[@]}"})
    shown="$shown$note"
    if [ ${#cmd2[@]} -gt 0 ]; then shown="$shown; then $(printf '%q ' ${cmd2[@]+"${cmd2[@]}"})"; fi
    printf '%s\t%s\t%s\n' "$name" "$rc" "$shown" >>"$OUT/$label.steps"
  done
}

ver() { local v; v=$("$@" 2>/dev/null | head -n 1); echo "${v:-not installed}"; }
{
  echo "repo:       $REPO_NAME @ $(git -C "$ROOT" rev-parse HEAD) ($(git -C "$ROOT" branch --show-current))"
  echo "dirty:      $(git -C "$ROOT" status --porcelain | wc -l) path(s) uncommitted"
  echo "origin/main $(git -C "$ROOT" rev-parse -q --verify origin/main || echo missing)"
  echo "venv:       $VENV"
  echo "python:     $(ver "$BIN/python" --version)"
  echo "ruff:       $(ver "$BIN/ruff" --version)"
  echo "mypy:       $(ver "$BIN/mypy" --version)"
  echo "pytest:     $(ver "$BIN/python" -m pytest --version)"
  echo "steps:      $STEPS (keep-going=$KEEP)"
  echo "workers:    $WORKERS ($WORKERS_WHY)"
  echo "test paths: $SELECTION"
} >"$OUT/meta"

run_steps branch "$ROOT"
if [ -n "$BASEFILE" ]; then
  {
    echo "baseline:   stored file $BASEFILE (main_sha $stored_sha); origin/main NOT rerun"
    echo "run mode:   workers=$WORKERS, collection order (the baseline was written in the same mode)"
    if [ "$MAIN_SHA" != "$stored_sha" ]; then
      echo "NOTE:       origin/main is $MAIN_SHA; main moved only in Markdown or generated diagrams no test reads"
    fi
  } >>"$OUT/meta"
elif [ $BASELINE = 1 ]; then
  git -C "$ROOT" worktree add -q --detach "$WT" origin/main || exit 2
  {
    echo "baseline:   origin/main @ $(git -C "$WT" rev-parse HEAD) in a detached worktree, same venv and lock as branch"
    echo "            $IMPORT_PKG imported from: $(cd "$WT" && PYTHONPATH=$(pypath "$WT") "$BIN/python" "$ROOT/scripts/dev/_gates_report.py" --import-origin "$IMPORT_PKG" 2>&1 | tail -n 1)"
  } >>"$OUT/meta"
  run_steps baseline "$WT"
fi
echo "logs:       $OUT" >>"$OUT/meta"

REPORT_ARGS=(--workers "$WORKERS")
[ -n "$OUTCOMES" ] && REPORT_ARGS+=(--outcomes-file "$OUTCOMES")
[ $WHOLE_SUITE = 1 ] && REPORT_ARGS+=(--whole-suite)
# A whole-suite result is only trustworthy if the tests step ran the whole suite,
# pytest finished (rc 0 or 1), and its JUnit file parses with at least one case.
tests_rc=$(awk -F'\t' '$1=="tests"{print $2}' "$OUT/branch.steps")
if awk -F'\t' '$2 == -2 {hit = 1} END {exit !hit}' "$OUT/branch.steps"; then tests_rc=skipped; fi
SUITE_OK=0
if [ $WHOLE_SUITE = 1 ] && { [ "$tests_rc" = 0 ] || [ "$tests_rc" = 1 ]; } &&
  [ "$("$BIN/python" "$ROOT/scripts/dev/_gates_report.py" --suite-collected "$OUT" 2>/dev/null)" -gt 0 ] 2>/dev/null; then
  SUITE_OK=1
fi
WRITE_REFUSED=0
if [ -n "$WRITEBASE" ]; then
  if [ $SUITE_OK = 1 ]; then
    REPORT_ARGS+=(--write-baseline "$WRITEBASE" --repo "$REPO_NAME" --main-sha "$MAIN_SHA" --head-sha "$HEAD_SHA")
  else
    echo "gates: --write-baseline refused: the tests step did not finish the whole suite with a JUnit file and collected > 0 (tests rc ${tests_rc:-none}); use --keep-going" >&2
    WRITE_REFUSED=1
  fi
fi

# Test ids in the test files this branch deleted, counted at the merge base. A rename is not a
# deletion (git -M), so a moved file keeps its ids in the branch's own count.
deleted_test_ids() {
  local base f files=() n
  base=$(git -C "$ROOT" merge-base origin/main HEAD) || return 1
  while IFS= read -r f; do
    case $f in tests/*test_*.py) files+=("$f") ;; esac
  done <<EOT
$(git -C "$ROOT" diff --name-only -M --diff-filter=D "$base")
EOT
  [ ${#files[@]} -gt 0 ] || { echo 0; return 0; }
  git -C "$ROOT" worktree add -q --detach "$MBT" "$base" || return 1
  # A collection error in a deleted file counts no ids, so the shortfall stays and the gate fails.
  n=$(cd "$MBT" && PYTHONPATH=$(pypath "$MBT") env -u PYTEST_ADDOPTS -u PYTEST_PLUGINS "$BIN/python" -m pytest --collect-only -q -p no:cacheprovider -o addopts= --color=no ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"} ${files[@]+"${files[@]}"} 2>/dev/null | grep -cE '^[^ ]+\.py::') || true
  echo "${n:-0}"
}

# A gate passes only on a complete EVIDENCE block and at least one step that ran green.
"$BIN/python" "$ROOT/scripts/dev/_gates_report.py" "$OUT" ${REPORT_ARGS[@]+"${REPORT_ARGS[@]}"} | tee "$OUT/evidence"
report_rc=${PIPESTATUS[0]}
if [ "$report_rc" = 4 ]; then
  echo "gates: FAIL: the failure count in the pytest log disagrees with the JUnit (logs in $OUT)" >&2; exit 3
fi
# The reporter exits 1 only when it refused to write the baseline, after printing the whole block.
write_failed=0
[ "$report_rc" = 1 ] && [ -n "$WRITEBASE" ] && write_failed=1
if { [ "$report_rc" != 0 ] && [ $write_failed = 0 ]; } || ! grep -qx '=* EVIDENCE =*' "$OUT/evidence" || ! tail -n 1 "$OUT/evidence" | grep -qx '=\{70\}'; then
  echo "gates: FAIL: no complete EVIDENCE block (reporter exit $report_rc; logs in $OUT)" >&2; exit 3
fi
if [ $write_failed = 1 ] || [ $WRITE_REFUSED = 1 ]; then exit 1; fi
if [ -n "$BASEFILE" ]; then
  [ $SUITE_OK = 1 ] || { echo "gates: FAIL: baseline comparison needs a completed whole-suite tests step with a JUnit file and collected > 0 (tests rc ${tests_rc:-none})" >&2; exit 1; }
  # A smaller suite is green only when the branch itself deleted those tests; a collection error
  # in a kept file shrinks the count too and must not read as a smaller, passing suite.
  if [ -s "$OUT/shortfall" ]; then
    short=$(cat "$OUT/shortfall")
    if ! deleted=$(deleted_test_ids); then echo "gates: FAIL: could not count the tests the branch deleted" >&2; exit 1; fi
    if [ "$short" -gt "$deleted" ]; then
      echo "gates: FAIL: the branch collects $short fewer tests than the baseline but deleted only $deleted" >&2; exit 1
    fi
    echo "gates: collected $short fewer tests than the baseline; the branch deleted $deleted" >&2
  fi
  # Known failures are not a failure of the branch: only a new id, a failing
  # non-test step, or a pytest run that did not finish blocks.
  [ -s "$OUT/new-failing" ] && exit 1
  [ -s "$OUT/skip-increase" ] && exit 1
  awk -F'\t' '$1!="tests" && $2!=0 && $2!=-1 {bad=1} $1=="tests" && $2!=0 && $2!=1 && $2!=-1 {bad=1} END{exit !bad}' "$OUT/branch.steps" && exit 1
elif [ $BASELINE = 1 ]; then
  # Same host, same venv: a step that also fails on origin/main is a host or main problem, not this
  # branch's. Fail only on branch-only failures (see _gates_report.branch_only_steps).
  if ! BRANCH_ONLY=$("$BIN/python" "$ROOT/scripts/dev/_gates_report.py" --verdict "$OUT"); then
    echo "gates: FAIL: could not compute the baseline verdict" >&2; exit 3
  fi
  [ -n "$BRANCH_ONLY" ] && exit 1
else
  # One awk reads the whole file: a cut | grep -q pipe under pipefail can SIGPIPE and drop a failure.
  awk -F'\t' '$2 != 0 && $2 != -1 {bad = 1} END {exit !bad}' "$OUT/branch.steps" && exit 1
fi
# A step that ended rc 1 only on failures main also has did run. The engine counts this for a
# stored compare only because its format step always runs green; here format and mypy are SKIP,
# so a legacy run whose one real step shares main's failures would otherwise read as "no step ran".
ran_max=0; [ $BASELINE = 1 ] && ran_max=1
awk -F'\t' -v max="$ran_max" '$2 >= 0 && $2 <= max {ran = 1} END {exit !ran}' "$OUT/branch.steps" || { echo "gates: FAIL: no step ran (all skipped or none selected)" >&2; exit 3; }
exit 0
