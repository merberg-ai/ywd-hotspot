#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-install}"
ROOT="${2:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
UNIT="ywd-vocoder-mbelib.service"
POLICY_NAME="20-ywd-hotspot-normal-priority.conf"
SRC="$ROOT/systemd/${UNIT}.d/$POLICY_NAME"
DST_DIR="/etc/systemd/system/${UNIT}.d"
DST="$DST_DIR/$POLICY_NAME"

if [[ $EUID -ne 0 ]]; then
  exec sudo "$0" "$ACTION" "$ROOT"
fi

apply_policy(){
  [[ -f "$SRC" ]] || { echo "[FAIL] Missing vocoder scheduling policy: $SRC" >&2; return 1; }
  install -d -o root -g root -m 0755 "$DST_DIR"
  install -o root -g root -m 0644 "$SRC" "$DST"
  systemctl daemon-reload

  # If the separately installed socket-activated backend is currently running,
  # restart only that backend so Nice=0 takes effect immediately. If it is
  # dormant or absent, the next socket activation will inherit the policy.
  if systemctl is-active --quiet "$UNIT" 2>/dev/null; then
    systemctl try-restart "$UNIT" >/dev/null 2>&1 || true
  fi
}

remove_policy(){
  rm -f "$DST"
  rmdir "$DST_DIR" 2>/dev/null || true
  systemctl daemon-reload
  if systemctl is-active --quiet "$UNIT" 2>/dev/null; then
    systemctl try-restart "$UNIT" >/dev/null 2>&1 || true
  fi
}

case "$ACTION" in
  install|ensure)
    apply_policy
    ;;
  remove)
    remove_policy
    ;;
  verify)
    if [[ -f "$DST" ]]; then
      echo "policy=$DST"
    else
      echo "policy=missing"
      exit 1
    fi
    if systemctl cat "$UNIT" >/dev/null 2>&1; then
      systemctl show "$UNIT" -p Nice
    else
      echo "unit=external-not-installed"
    fi
    ;;
  *)
    echo "Usage: $0 {install|ensure|remove|verify} [source-root]" >&2
    exit 2
    ;;
esac
