#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  setup-finish)
    exec /usr/local/libexec/ywd-hotspot-setup-admin "$@"
    ;;
  *)
    exec /usr/local/libexec/ywd-hotspot-admin-core "$@"
    ;;
esac
