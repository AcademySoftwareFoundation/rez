#!/usr/bin/env sh
set -eu
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "Error: python3 or python not found in PATH" >&2
    exit 1
fi
exec "$PYTHON_BIN" "$SCRIPT_DIR/vendor_update.py" "$@"
