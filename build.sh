#!/usr/bin/env bash
# this_file: build.sh
#
# Full verification gate: Rust workspace, both Python distributions, and an
# end-to-end smoke test in a throwaway virtual environment. Leaves the checkout
# byte-identical — a build that modifies tracked files is a build failure.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
LOG="$ROOT/build.log.txt"
TEMP_DIR=""
BUILD_COMPLETED=0

cleanup() {
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        rm -rf -- "$TEMP_DIR"
    fi
}

finish() {
    local status=$?
    local message
    trap - EXIT
    if (( status == 0 && BUILD_COMPLETED == 1 )); then
        message='BUILD SUCCESS: milkwashr crate and both Python packages passed.'
    else
        (( status == 0 )) && status=1
        message="BUILD FAILURE: exit status $status; inspect $LOG"
    fi
    printf '\n%s\n' "$message" >>"$LOG" || status=1
    printf '\n%s\n' "$message"
    cleanup
    exit "$status"
}

handle_signal() {
    trap - INT TERM
    exit "$1"
}

require_tool() {
    command -v "$1" >/dev/null 2>&1 || {
        printf 'Required tool is missing: %s\n' "$1" >&2
        return 1
    }
}

verify_layout() {
    local required
    for required in \
        Cargo.toml \
        milkwashr/Cargo.toml \
        milkwashr/pyproject.toml \
        milkwashr/src/lib.rs \
        milkwashr-wasm/Cargo.toml \
        milkwashr-wasm/src/lib.rs \
        milkwashy/pyproject.toml \
        milkwashy/tests \
        tests/wasm_parity.mjs \
        wasm.sh \
        scripts/release-manifests.py \
        scripts/check-python-artifacts.py; do
        [[ -e "$ROOT/$required" ]] || {
            printf 'Canonical project path is missing: %s\n' "$required" >&2
            return 1
        }
    done
}

record_tree() {
    local destination=$1
    git -C "$ROOT" status --porcelain=v1 --untracked-files=all >"$destination.status"
    git -C "$ROOT" diff --no-ext-diff --binary HEAD -- >"$destination.diff"
}

verify_tree_unchanged() {
    local before=$1 after=$2
    if ! cmp -s "$before.status" "$after.status" || ! cmp -s "$before.diff" "$after.diff"; then
        printf 'Build changed the checkout. Before/after status follows.\n' >&2
        diff -u "$before.status" "$after.status" >&2 || true
        return 1
    fi
}

# Build both distributions into $1 and print "<wheel> <sdist>" per package.
build_distributions() {
    local dist=$1 expected=$2
    mkdir -p "$dist/milkwashr" "$dist/milkwashy"
    (cd "$ROOT/milkwashr" && uv build --no-sources --out-dir "$dist/milkwashr")
    (cd "$ROOT/milkwashy" && uv build --no-sources --out-dir "$dist/milkwashy")
    python3 "$ROOT/scripts/check-python-artifacts.py" "$dist/milkwashr" "$expected" \
        >"$dist/milkwashr.txt"
    python3 "$ROOT/scripts/check-python-artifacts.py" "$dist/milkwashy" "$expected" \
        >"$dist/milkwashy.txt"
}

python_gate() {
    local expected=$1
    local dist="$TEMP_DIR/python-dist"
    local venv="$TEMP_DIR/python-venv"
    local python="$venv/bin/python"

    build_distributions "$dist" "$expected"
    local rust_wheel python_wheel
    rust_wheel="$(sed -n '1p' "$dist/milkwashr.txt")"
    python_wheel="$(sed -n '1p' "$dist/milkwashy.txt")"

    uv venv --clear --python python3 "$venv"
    uv pip install --python "$python" "$rust_wheel" "$python_wheel" pytest
    "$python" -m pytest "$ROOT/milkwashy/tests" -q
    "$python" - "$expected" <<'PY'
import sys

import milkwashr
import milkwashy

expected = sys.argv[1]
assert milkwashy.__version__ == expected, (milkwashy.__version__, expected)
assert milkwashr.ping() == "milkwashr-ok"
spans = milkwashr.plan_chunk_spans(11, 1234, 2, 8)
assert spans and spans[0][0] == 0 and spans[-1][1] == 11, spans
assert milkwashr.plan_chunk_spans(11, 1234, 2, 8) == spans, "chunk plan is not deterministic"
plans = milkwashy.plan_chunks("One. Two. Three. Four. Five.", "en")
assert plans and plans[0].prompt in milkwashy.PROMPTS, plans
print(f"Python smoke passed: milkwashy {milkwashy.__version__}")
PY
}

# Builds the WebAssembly module, compares it with the Python module, and checks
# that docs/ holds the module for this version. `./wasm.sh --refresh` writes it.
wasm_gate() {
    if [[ "${MILKWASH_SKIP_WASM:-0}" == "1" ]]; then
        printf 'WASM gate skipped, because MILKWASH_SKIP_WASM=1.\n'
        return 0
    fi
    for tool in wasm-pack node rustup; do
        command -v "$tool" >/dev/null 2>&1 || {
            printf 'The WASM gate needs %s. Install it, or set MILKWASH_SKIP_WASM=1.\n' \
                "$tool" >&2
            return 1
        }
    done
    "$ROOT/wasm.sh"
}

run_build() {
    local tool
    for tool in git cargo rustc uv uvx python3; do
        require_tool "$tool"
    done
    verify_layout
    record_tree "$TEMP_DIR/before"

    printf 'Repository: %s\n' "$ROOT"
    printf 'rustc: %s\n' "$(rustc --version)"
    printf 'cargo: %s\n' "$(cargo --version)"
    printf 'uv: %s\n' "$(uv --version)"
    printf 'python: %s\n' "$(python3 --version 2>&1)"

    local version
    version="$(python3 "$ROOT/scripts/release-manifests.py" check)"
    printf 'Synchronized version: %s\n' "$version"

    cargo fmt --manifest-path "$ROOT/Cargo.toml" --all -- --check
    cargo clippy --manifest-path "$ROOT/Cargo.toml" --all-targets --no-deps -- -D warnings
    cargo build --manifest-path "$ROOT/Cargo.toml" --workspace
    cargo test --manifest-path "$ROOT/Cargo.toml" --workspace
    cargo test --manifest-path "$ROOT/Cargo.toml" -p milkwashr --doc
    # The crate must also build without PyO3. Rust users and the WebAssembly
    # build use it in that form.
    cargo build --manifest-path "$ROOT/Cargo.toml" -p milkwashr --no-default-features
    python_gate "$version"
    wasm_gate

    record_tree "$TEMP_DIR/after"
    verify_tree_unchanged "$TEMP_DIR/before" "$TEMP_DIR/after"
}

trap finish EXIT
trap 'handle_signal 130' INT
trap 'handle_signal 143' TERM
: >"$LOG"
TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/milkwash-build.XXXXXX")"
run_build 2>&1 | tee -a "$LOG"
BUILD_COMPLETED=1
