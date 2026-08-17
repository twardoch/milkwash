#!/usr/bin/env bash
# this_file: install.sh
#
# Installs milkwashr + milkwashy into the interpreter uv considers the system
# Python, so `milkwashy` is on PATH everywhere. The wheels are built from this
# checkout and smoke-tested in a throwaway environment first. The checkout is
# left byte-identical.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
TEMP_DIR=""

cleanup() {
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        rm -rf -- "$TEMP_DIR"
    fi
}
trap cleanup EXIT

usage() {
    printf 'Usage: %s [--python PATH]\n' "$0"
}

TARGET_PYTHON=""
while (( $# > 0 )); do
    case "$1" in
        --python)
            (( $# >= 2 )) || { printf '%s\n' '--python requires a path' >&2; exit 2; }
            TARGET_PYTHON=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

for tool in cargo rustc uv python3 git; do
    command -v "$tool" >/dev/null 2>&1 || {
        printf 'Required tool is missing: %s\n' "$tool" >&2
        exit 1
    }
done

for required in milkwashr/pyproject.toml milkwashy/pyproject.toml scripts/check-python-artifacts.py; do
    [[ -e "$ROOT/$required" ]] || {
        printf 'Canonical project path is missing: %s\n' "$required" >&2
        exit 1
    }
done

TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/milkwash-install.XXXXXX")"
DIST="$TEMP_DIR/dist"
VENV="$TEMP_DIR/smoke-venv"
mkdir -p "$DIST/milkwashr" "$DIST/milkwashy"

git -C "$ROOT" status --porcelain=v1 --untracked-files=all >"$TEMP_DIR/before.status"
git -C "$ROOT" diff --no-ext-diff --binary HEAD -- >"$TEMP_DIR/before.diff"

VERSION="$(python3 "$ROOT/scripts/release-manifests.py" check)"
if [[ -z "$TARGET_PYTHON" ]]; then
    TARGET_PYTHON="$(uv python find --system --no-managed-python)"
fi
printf 'Installing milkwash %s\n' "$VERSION"
printf 'rustc: %s\n' "$(rustc --version)"
printf 'uv: %s\n' "$(uv --version)"
printf 'target Python: %s\n' "$TARGET_PYTHON"

(cd "$ROOT/milkwashr" && uv build --no-sources --python "$TARGET_PYTHON" --out-dir "$DIST/milkwashr")
(cd "$ROOT/milkwashy" && uv build --no-sources --out-dir "$DIST/milkwashy")
python3 "$ROOT/scripts/check-python-artifacts.py" "$DIST/milkwashr" "$VERSION" >"$TEMP_DIR/r.txt"
python3 "$ROOT/scripts/check-python-artifacts.py" "$DIST/milkwashy" "$VERSION" >"$TEMP_DIR/y.txt"
RUST_WHEEL="$(sed -n '1p' "$TEMP_DIR/r.txt")"
PY_WHEEL="$(sed -n '1p' "$TEMP_DIR/y.txt")"

# Smoke-test the exact wheels in isolation before touching the target Python.
uv venv --clear --python "$TARGET_PYTHON" "$VENV"
uv pip install --python "$VENV/bin/python" "$RUST_WHEEL" "$PY_WHEEL"
"$VENV/bin/python" - "$VERSION" <<'PY'
import sys

import milkwashr
import milkwashy

expected = sys.argv[1]
assert milkwashy.__version__ == expected, (milkwashy.__version__, expected)
assert milkwashr.ping() == "milkwashr-ok"
print(f"Wheel smoke passed: milkwashy {milkwashy.__version__}")
PY

uv pip install --system --python "$TARGET_PYTHON" --reinstall "$RUST_WHEEL" "$PY_WHEEL"
"$TARGET_PYTHON" -c 'import milkwashr, milkwashy; print("installed milkwashy", milkwashy.__version__)'

git -C "$ROOT" status --porcelain=v1 --untracked-files=all >"$TEMP_DIR/after.status"
git -C "$ROOT" diff --no-ext-diff --binary HEAD -- >"$TEMP_DIR/after.diff"
if ! cmp -s "$TEMP_DIR/before.status" "$TEMP_DIR/after.status" || \
    ! cmp -s "$TEMP_DIR/before.diff" "$TEMP_DIR/after.diff"; then
    printf 'Install changed the checkout. Before/after status follows.\n' >&2
    diff -u "$TEMP_DIR/before.status" "$TEMP_DIR/after.status" >&2 || true
    exit 1
fi

printf '\nInstallation complete: milkwashy %s\n' "$VERSION"
printf 'CLI: %s\n' "$(dirname "$TARGET_PYTHON")/milkwashy"
