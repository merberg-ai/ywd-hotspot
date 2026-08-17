#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  setup-finish)
    exec /usr/local/libexec/ywd-hotspot-setup-admin "$@"
    ;;
  update-check|update-start|set-hotspot-password|config-apply|config-revert|service-restart)
    exec /usr/local/libexec/ywd-hotspot-update-admin "$@"
    ;;
  settings-export|settings-preview|settings-import)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/settings_admin.py "$@"
    ;;
  plugin-system-set|plugin-set|plugin-config-save|plugin-runtime|plugin-package-install|plugin-package-uninstall|plugin-data-remove|plugin-package-upload|plugin-package-remove)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/plugin_admin.py "$@"
    ;;
  *)
    exec /usr/local/libexec/ywd-hotspot-admin-core "$@"
    ;;
esac
