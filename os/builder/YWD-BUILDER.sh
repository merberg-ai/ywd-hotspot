#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILDER_DIR="$ROOT_DIR/os/builder"
LOCAL_DIR="$ROOT_DIR/os/local"
VENV="$LOCAL_DIR/builder-venv"
REQ="$BUILDER_DIR/requirements.txt"

mkdir -p "$LOCAL_DIR"
chmod 0700 "$LOCAL_DIR"

if [[ ! -x "$VENV/bin/python" ]]; then
  command -v python3 >/dev/null 2>&1 || { echo 'ERROR: python3 is required.' >&2; exit 1; }
  if ! python3 -m venv "$VENV" >/dev/null 2>&1; then
    echo 'ERROR: Python venv support is required.' >&2
    echo 'On Debian/Ubuntu: sudo apt install python3-venv' >&2
    exit 1
  fi
fi

if ! "$VENV/bin/python" - <<'PY' >/dev/null 2>&1
import textual
assert textual.__version__ == '8.2.8'
PY
then
  echo 'Preparing YWD-Hotspot Textual builder environment...'
  "$VENV/bin/python" -m pip install --disable-pip-version-check -q -r "$REQ"
fi

exec "$VENV/bin/python" "$BUILDER_DIR/ywd_builder.py"
