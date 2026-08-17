#!/usr/bin/env bash
# this_file: sweep.sh
#
# Sweep every model of every provider into ./02-testllm/<provider>/<model>/.
#
# Providers run CONCURRENTLY, one process each. They do not contend: outputs are
# grouped per provider, each writes its own log, and only LM Studio touches local
# memory -- the others are remote HTTP, so the wall clock is the slowest single
# provider rather than their sum. LM Studio is started first because it is
# reliably the longest leg (one load/unload per model, verified between each).
#
# Providers that are unreachable are reported and skipped, never fatal — a dead
# CLIProxy must not cost the LM Studio sweep. Runs are resumable: re-running
# picks up where an interrupted sweep stopped, and a model whose outputs all
# exist is not loaded again.
#
# Usage:
#   ./sweep.sh                        # everything, in parallel
#   ./sweep.sh --limit 5              # 5 smallest models per provider
#   ./sweep.sh --max_size_mb 8000     # skip models above 8 GB
#   PROVIDERS="lmstudio" ./sweep.sh   # one provider only
#   PARALLEL=0 ./sweep.sh             # one provider at a time
#
# Any extra arguments are passed straight through to `milkwashy run`.

set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

# LM Studio first: longest leg, and starting it first means the others finish
# inside its runtime rather than after it.
PROVIDERS="${PROVIDERS:-lmstudio cliproxy chat2api}"
PARALLEL="${PARALLEL:-1}"
LOG_DIR="02-testllm/_logs"
LOCK_DIR="02-testllm/_logs/.lmstudio.lock"
mkdir -p "$LOG_DIR"

# .env carries the endpoints and keys (python-dotenv reads it too, but exporting
# here means the values are also visible to this script's own diagnostics).
if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
else
    echo "note: no .env found; providers fall back to built-in defaults" >&2
fi

if ! command -v milkwashy >/dev/null 2>&1; then
    echo "error: milkwashy is not on PATH. Install it with:" >&2
    echo "  ./install.sh" >&2
    echo "  (or: uv pip install milkwashy)" >&2
    exit 1
fi

stamp() { date +"%Y-%m-%d %H:%M:%S"; }

# One LM Studio sweep at a time, machine-wide. Concurrency between providers is
# safe; concurrency between two *lmstudio* sweeps is not -- they would race on
# load/unload and break the "exactly one model resident" invariant. `mkdir` is
# the atomic test-and-set here.
lms_lock() {
    if ! mkdir "$LOCK_DIR" 2>/dev/null; then
        echo "error: another lmstudio sweep is running (lock: $LOCK_DIR)." >&2
        echo "       If no sweep is running, remove the lock directory." >&2
        return 1
    fi
    echo $$ > "$LOCK_DIR/pid"
    return 0
}
# Only the owner clears the lock: a second invocation that was refused the lock
# must not delete the running sweep's lock on its way out.
lms_unlock() {
    [[ -f "$LOCK_DIR/pid" && $(cat "$LOCK_DIR/pid" 2>/dev/null) == "$$" ]] && rm -rf "$LOCK_DIR"
    return 0
}

run_provider() {
    local provider=$1; shift
    local log="$LOG_DIR/${provider}.log"
    local start rc elapsed

    if [[ $provider == lmstudio ]] && ! lms_lock; then
        echo "$provider|1|refused: another lmstudio sweep holds the lock"
        return 0
    fi

    start=$(date +%s)
    milkwashy run --provider "$provider" "$@" > "$log" 2>&1
    rc=$?
    elapsed=$(( $(date +%s) - start ))

    if [[ $provider == lmstudio ]]; then
        # Never leave a model resident once this provider is done.
        milkwashy lms_unload_all >>"$log" 2>&1 || true
        lms_unlock
    fi

    # run_sweep reports an unreachable provider in its output rather than by exit
    # code, so the log is the authority on whether anything actually ran. Match
    # the CLI's flat summary line, not the loguru "sweep done:" line -- the
    # latter only exists at INFO level and would vanish under --verbose=False.
    local result
    result=$(grep -o "sweep ${provider}: .*" "$log" | tail -1 | sed "s/^sweep ${provider}: //")

    if [[ $rc -ne 0 ]]; then
        echo "$provider|1|FAILED (exit $rc, ${elapsed}s) — see $log"
    elif grep -q 'unreachable; nothing to do' "$log"; then
        echo "$provider|0|unreachable, skipped (${elapsed}s)"
    elif [[ -n "$result" ]]; then
        echo "$provider|0|$result (${elapsed}s)"
    else
        echo "$provider|1|finished with no result line (${elapsed}s) — see $log"
    fi
}

echo "[$(stamp)] providers: $PROVIDERS   (parallel=$PARALLEL)"
echo "[$(stamp)] logs: $LOG_DIR/<provider>.log   —   tail -f to watch"

RESULT_DIR=$(mktemp -d)
trap 'rm -rf "$RESULT_DIR"; lms_unlock' EXIT

declare -a PIDS=()
for provider in $PROVIDERS; do
    if [[ $PARALLEL == 1 ]]; then
        run_provider "$provider" "$@" > "$RESULT_DIR/$provider" &
        PIDS+=("$!")
        echo "[$(stamp)] started $provider (pid $!)"
    else
        run_provider "$provider" "$@" > "$RESULT_DIR/$provider"
        echo "[$(stamp)] finished $provider"
    fi
done

# A provider that dies must not take the others' results with it, so failures are
# read from the per-provider result files rather than from wait's exit status.
for pid in ${PIDS+"${PIDS[@]}"}; do
    wait "$pid"
done

overall_rc=0
echo
echo "=============================================================="
echo "[$(stamp)] summary"
echo "=============================================================="
for provider in $PROVIDERS; do
    line=$(cat "$RESULT_DIR/$provider" 2>/dev/null)
    if [[ -z $line ]]; then
        echo "  $provider: no result (killed?) — see $LOG_DIR/${provider}.log"
        overall_rc=1
        continue
    fi
    IFS='|' read -r _name rc text <<< "$line"
    echo "  $provider: $text"
    [[ $rc -ne 0 ]] && overall_rc=1
done

if [[ " $PROVIDERS " == *" lmstudio "* ]]; then
    echo
    echo "lms residency after sweep: $(lms ps --json 2>/dev/null || echo 'unknown')"
fi

echo
echo "outputs: 02-testllm/<provider>/<model>/<text>.txt (+ .plan.json)"

exit $overall_rc
