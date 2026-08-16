#!/usr/bin/env bash
set -euo pipefail
mode="${1:-all}"
case "$mode" in
  network)
    units=(ywd-network-manager.service)
    ;;
  web|dashboard)
    units=(ywd-dashboard.service)
    ;;
  setup)
    units=(ywd-setup.service)
    ;;
  rf)
    units=(ywd-mmdvmhost.service ywd-dmrgateway.service)
    ;;
  oled)
    units=(ywd-headless-oled.service)
    ;;
  all)
    units=(ywd-network-manager.service ywd-dashboard.service ywd-setup.service ywd-headless-oled.service ywd-mmdvmhost.service ywd-dmrgateway.service)
    ;;
  -h|--help|help)
    echo 'Usage: ywd-logs [all|network|web|setup|rf|oled]'
    exit 0
    ;;
  *)
    echo "Unknown log group: $mode" >&2
    echo 'Usage: ywd-logs [all|network|web|setup|rf|oled]' >&2
    exit 2
    ;;
esac
args=()
for unit in "${units[@]}"; do args+=( -u "$unit" ); done
if [[ "$(id -u)" -eq 0 ]]; then
  exec journalctl -f -n 80 --no-pager "${args[@]}"
fi
exec sudo -n journalctl -f -n 80 --no-pager "${args[@]}"
