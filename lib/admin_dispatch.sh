#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  setup-finish)
    exec /usr/local/libexec/ywd-hotspot-setup-admin "$@"
    ;;
  update-check|update-start|set-hotspot-password|config-apply|config-revert|service-restart)
    exec /usr/local/libexec/ywd-hotspot-update-admin "$@"
    ;;
  config-save|tgif-configure|set-tgif-password)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/tgif_admin.py "$@"
    ;;
  tgif-control)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/tgif_scanner_admin.py "$@"
    ;;
  update-branches|update-branch-check|update-branch-switch)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/branch_update_admin.py "$@"
    ;;
  settings-export|settings-preview|settings-import)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/settings_admin.py "$@"
    ;;
  ssh-status|ssh-configure|ssh-password-set)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/ssh_runtime_admin.py "$@"
    ;;
  ssh-keys-export)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/ssh_keys_admin.py "$@"
    ;;
  ssh-client-key-create)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/ssh_client_key_admin.py "$@"
    ;;
  diagnostics)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/diagnostics_policy.py "$@"
    ;;
  mmdvm-system-info)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/mmdvm_system_info.py
    ;;
  shutdown)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/system_admin.py "$@"
    ;;
  dmrid-status|dmrid-check|dmrid-update)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/dmrid_admin.py "$@"
    ;;
  plugin-system-set|plugin-set|plugin-config-save|plugin-runtime|plugin-package-install|plugin-package-uninstall|plugin-data-remove|plugin-package-upload|plugin-package-review|plugin-package-apply|plugin-package-remove)
    exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/plugin_admin.py "$@"
    ;;
  *)
    exec /usr/local/libexec/ywd-hotspot-admin-core "$@"
    ;;
esac
