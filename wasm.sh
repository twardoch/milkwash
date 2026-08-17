#!/usr/bin/env bash
# this_file: wasm.sh
#
# Builds the WebAssembly module and tests it against the Python extension
# module.
#
#   ./wasm.sh            # test only; the files in docs/ do not change
#   ./wasm.sh --refresh  # test, and then write the new module into docs/
#
# `build.sh` calls this script without `--refresh`. The check must not change the
# checkout, because a release depends on a build that changes nothing.
#
# Use `--refresh` when you change the Rust code. Then commit the new module. The
# documentation site serves that copy, so the site needs no build step of its
# own.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DOCS_WASM="$ROOT/docs/assets/wasm"
REFRESH=0
TEMP_DIR=""

cleanup() {
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        rm -rf -- "$TEMP_DIR"
    fi
}
trap cleanup EXIT

usage() {
    printf 'Usage: %s [--refresh]\n' "$0"
}

while (( $# > 0 )); do
    case "$1" in
        --refresh) REFRESH=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
done

for tool in cargo rustup wasm-pack node uv python3; do
    command -v "$tool" >/dev/null 2>&1 || {
        printf 'Required tool is missing: %s\n' "$tool" >&2
        exit 1
    }
done

rustup target list --installed | grep -qx 'wasm32-unknown-unknown' || {
    printf 'The wasm32-unknown-unknown target is missing. Add it with:\n' >&2
    printf '  rustup target add wasm32-unknown-unknown\n' >&2
    exit 1
}

VERSION="$(python3 "$ROOT/scripts/release-manifests.py" check)"
TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/milkwash-wasm.XXXXXX")"
WEB_DIR="$TEMP_DIR/web"
NODE_DIR="$TEMP_DIR/node"
VENV="$TEMP_DIR/venv"
DIST="$TEMP_DIR/dist"
REFERENCE="$TEMP_DIR/reference.json"

printf 'milkwashr %s\n' "$VERSION"
printf 'wasm-pack: %s\n' "$(wasm-pack --version)"
printf 'node: %s\n' "$(node --version)"

# The web build goes to the documentation site. The Node build is only for the
# parity test, because Node cannot load the web build directly.
(cd "$ROOT/milkwashr-wasm" && wasm-pack build --release --target web \
    --out-dir "$WEB_DIR" --out-name milkwashr)
(cd "$ROOT/milkwashr-wasm" && wasm-pack build --release --target nodejs \
    --out-dir "$NODE_DIR" --out-name milkwashr)

# The reference values come from the Python extension module of this checkout,
# not from a released wheel.
mkdir -p "$DIST"
(cd "$ROOT/milkwashr" && uv build --no-sources --out-dir "$DIST" >/dev/null)
uv venv --clear --python python3 "$VENV" >/dev/null
# `--no-sources` keeps uv from replacing the built wheel with the editable path
# that `milkwashy/pyproject.toml` declares for local development.
uv pip install --quiet --no-sources --python "$VENV/bin/python" \
    "$(ls "$DIST"/*.whl | head -1)" "$ROOT/milkwashy" >/dev/null
"$VENV/bin/python" "$ROOT/scripts/wasm-reference.py" "$REFERENCE" "$VERSION"
node "$ROOT/tests/wasm_parity.mjs" "$NODE_DIR" "$REFERENCE"

if (( REFRESH == 1 )); then
    mkdir -p "$DOCS_WASM"
    # Copy only the files that the browser needs. wasm-pack also writes a
    # package.json and a .gitignore, and the site has no use for them.
    cp "$WEB_DIR/milkwashr.js" "$WEB_DIR/milkwashr_bg.wasm" "$WEB_DIR/milkwashr.d.ts" \
        "$DOCS_WASM/"
    printf '%s\n' "$VERSION" >"$DOCS_WASM/VERSION"
    printf '\nRefreshed %s\n' "$DOCS_WASM"
    ls -l "$DOCS_WASM"
    printf '\nCommit these files. The documentation site serves them as they are.\n'
else
    [[ -f "$DOCS_WASM/milkwashr_bg.wasm" && -f "$DOCS_WASM/milkwashr.js" ]] || {
        printf 'The module is missing from %s. Run ./wasm.sh --refresh.\n' "$DOCS_WASM" >&2
        exit 1
    }
    committed="$(cat "$DOCS_WASM/VERSION" 2>/dev/null || printf 'unknown')"
    [[ "$committed" == "$VERSION" ]] || {
        printf 'The module in docs/ is version %s, but the manifests say %s.\n' \
            "$committed" "$VERSION" >&2
        printf 'Run ./wasm.sh --refresh and commit the result.\n' >&2
        exit 1
    }
    printf '\nWASM CHECK PASSED: the build works, and docs/ holds version %s.\n' "$committed"
fi
