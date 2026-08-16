#!/usr/bin/env bash
set -euo pipefail
HELPER=/usr/local/libexec/ywd-system-info
MODE="$(basename "$0")"
ARGS=("$@")
case "$MODE" in
  ywd-services) ARGS=(--services "${ARGS[@]}") ;;
  ywd-build) ARGS=(--build "${ARGS[@]}") ;;
esac
if [[ "$(id -u)" -eq 0 ]]; then
  exec "$HELPER" "${ARGS[@]}"
fi
exec sudo -n "$HELPER" "${ARGS[@]}"
