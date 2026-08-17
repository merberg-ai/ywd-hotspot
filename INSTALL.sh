#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
[[ -r "$SELF/bin/ywd-ui.sh" ]] && source "$SELF/bin/ywd-ui.sh"
VERSION="$(cat "$SELF/VERSION" 2>/dev/null || echo unknown)"
if declare -F ywd_banner >/dev/null; then
  ywd_banner "INSTALLER" "$VERSION"
  ywd_info "Lightweight Raspberry Pi + MMDVM DMR appliance"
  ywd_info "RF never starts without explicit confirmation."
fi

if [[ -d "$SELF/lib/console" ]]; then
  python3 -m py_compile "$SELF/lib/console/ywd-system-info.py"
  for f in ywd-info-wrapper.sh ywd-logs.sh ywd-env.sh ywd-prompt.sh ywd-motd.sh; do
    bash -n "$SELF/lib/console/$f"
  done
fi
for f in \
  lib/update_runner.py lib/update_admin.py lib/oled.py lib/oled_owner.sh \
  lib/plugin_manifest.py lib/plugin_manager.py lib/plugin_package_manager.py lib/plugin_service_manager.py \
  lib/plugin_catalog_overlay.py lib/plugin_package_archive.py lib/plugin_service_runner.py \
  lib/plugin_admin_common.py lib/plugin_admin_state.py lib/plugin_admin_packages.py lib/plugin_admin_upload.py lib/plugin_admin.py \
  lib/dashboard_plugins.py lib/dashboard_plugin_upload.py lib/dashboard_backup.py \
  lib/settings_backup.py lib/settings_admin.py lib/setup_restore_server.py lib/setup_entry.sh \
  lib/mmdvm_telemetry.py lib/mmdvm_telemetry_bridge.py lib/telemetry_runtime.py lib/ywd-mosquitto.conf \
  lib/plugin_packages/system-info/plugin.json lib/plugin_packages/system-info/config.schema.json \
  lib/service_plugin_packages/service-heartbeat/plugin.json lib/service_plugin_packages/service-heartbeat/config.schema.json lib/service_plugin_packages/service-heartbeat/service.py \
  lib/service_plugin_packages/mmdvm-live-telemetry/plugin.json lib/service_plugin_packages/mmdvm-live-telemetry/config.schema.json lib/service_plugin_packages/mmdvm-live-telemetry/service.py \
  web/plugin-manager-render.js web/plugin-package-actions.js web/plugin-package-upload.js web/plugin-manager.js web/plugin-manager.css web/plugin-config-actions.js web/plugin-telemetry.js \
  web/backup-restore.js web/backup-restore.css \
  systemd/ywd-plugin@.service systemd/ywd-mqtt.service systemd/ywd-mmdvm-telemetry.service \
  web/instrumentation.js web/instrumentation-bootstrap.js web/instrumentation.css; do
  [[ -f "$SELF/$f" ]] || { echo "[FAIL] Install source missing $f" >&2; exit 1; }
done
python3 -m py_compile \
  "$SELF/lib/update_runner.py" "$SELF/lib/update_admin.py" "$SELF/lib/oled.py" \
  "$SELF/lib/plugin_manifest.py" "$SELF/lib/plugin_manager.py" "$SELF/lib/plugin_package_manager.py" "$SELF/lib/plugin_service_manager.py" \
  "$SELF/lib/plugin_catalog_overlay.py" "$SELF/lib/plugin_package_archive.py" "$SELF/lib/plugin_service_runner.py" \
  "$SELF/lib/plugin_admin_common.py" "$SELF/lib/plugin_admin_state.py" "$SELF/lib/plugin_admin_packages.py" "$SELF/lib/plugin_admin_upload.py" "$SELF/lib/plugin_admin.py" \
  "$SELF/lib/dashboard_plugins.py" "$SELF/lib/dashboard_plugin_upload.py" "$SELF/lib/dashboard_backup.py" "$SELF/lib/settings_backup.py" "$SELF/lib/settings_admin.py" "$SELF/lib/setup_restore_server.py" \
  "$SELF/lib/mmdvm_telemetry.py" "$SELF/lib/mmdvm_telemetry_bridge.py" "$SELF/lib/telemetry_runtime.py" \
  "$SELF/lib/service_plugin_packages/service-heartbeat/service.py" "$SELF/lib/service_plugin_packages/mmdvm-live-telemetry/service.py"
[[ -f "$SELF/lib/system_branding.sh" ]] && bash -n "$SELF/lib/system_branding.sh"
bash -n "$SELF/lib/oled_owner.sh" "$SELF/lib/setup_entry.sh"

PYTHONPATH="$SELF/lib" \
YWD_PLUGIN_CATALOG="$SELF/lib/plugin_packages" \
YWD_SERVICE_PLUGIN_CATALOG="$SELF/lib/service_plugin_packages" \
YWD_LOCAL_PLUGIN_ROOT="$SELF/.plugin-local-does-not-exist" \
YWD_PLUGIN_TRUST_DIR="$SELF/.plugin-trust-does-not-exist" \
YWD_PLUGIN_STATE="$SELF/.plugin-state-does-not-exist" \
YWD_PLUGIN_PACKAGE_STATE="$SELF/.plugin-package-state-does-not-exist" \
YWD_PLUGIN_CONFIG_DIR="$SELF/.plugin-config-does-not-exist" \
YWD_PLUGIN_DATA_DIR="$SELF/.plugin-data-does-not-exist" \
YWD_MMDVM_TELEMETRY="$SELF/.telemetry-does-not-exist" \
python3 - <<'PY'
import dashboard_backup, dashboard_plugin_upload
import plugin_catalog_overlay, plugin_package_archive, plugin_service_runner
import plugin_manager, plugin_service_manager, settings_backup
base = plugin_manager.snapshot({"hostname":"candidate","uptime_s":1,"temperature_c":25,"load":[0,0,0]})
assert base["system"]["enabled"] is False
assert any(p.get("id") == "system-info" and p.get("valid") and p.get("installed") for p in base["plugins"])
services = plugin_service_manager.snapshot()
assert any(p.get("id") == "service-heartbeat" and p.get("valid") and p.get("installed") for p in services)
telemetry = [p for p in services if p.get("id") == "mmdvm-live-telemetry"]
assert len(telemetry) == 1 and telemetry[0].get("valid") and not telemetry[0].get("installed"), telemetry
assert telemetry[0].get("provider") == "mmdvm-telemetry", telemetry
PY

CORE="$SELF/INSTALL-core.sh"
[[ -f "$CORE" ]] || CORE="/opt/ywd-hotspot/repo/INSTALL-core.sh"
[[ -f "$CORE" ]] || { echo "[FAIL] Installer core not found." >&2; exit 1; }
if declare -F ywd_run_colored >/dev/null; then
  ywd_run_colored bash "$CORE" "$@"
else
  bash "$CORE" "$@"
fi

# Install the same narrow dispatcher/helper layout used by the appliance image.
# Generic installs never activate first-boot setup because they lack the M4 gate.
if [[ -f "$SELF/lib/admin_dispatch.sh" && -f "$SELF/lib/setup_admin.py" ]]; then
  sudo install -o root -g root -m 0755 "$SELF/lib/admin.py" /usr/local/libexec/ywd-hotspot-admin-core
  sudo install -o root -g root -m 0755 "$SELF/lib/setup_admin.py" /usr/local/libexec/ywd-hotspot-setup-admin
  sudo install -o root -g root -m 0755 "$SELF/lib/update_admin.py" /usr/local/libexec/ywd-hotspot-update-admin
  sudo install -o root -g root -m 0755 "$SELF/lib/update_runner.py" /usr/local/libexec/ywd-update-runner
  sudo install -o root -g root -m 0755 "$SELF/lib/admin_dispatch.sh" /usr/local/libexec/ywd-hotspot-admin
  sudo install -o root -g root -m 0440 "$SELF/sudoers/ywd-hotspot" /etc/sudoers.d/ywd-hotspot
  command -v visudo >/dev/null 2>&1 && sudo visudo -cf /etc/sudoers.d/ywd-hotspot >/dev/null
  sudo systemctl daemon-reload
fi

if [[ -f "$SELF/lib/system_branding.sh" ]]; then
  sudo bash "$SELF/lib/system_branding.sh" install "$SELF"
fi

# On YWD-Hotspot OS, preserve ywd-headless-oled as the only SSD1306 owner while
# using the same renderer as generic installs. On non-OS installs this is a no-op.
if [[ -f "$SELF/lib/oled_owner.sh" ]]; then
  sudo bash "$SELF/lib/oled_owner.sh" install "$SELF"
fi

# Telemetry is passive infrastructure. Failure here never turns a successful
# DMR install into an RF outage; the new plugin will simply report missing deps.
if ! sudo python3 /opt/ywd-hotspot/app/lib/telemetry_runtime.py ensure; then
  echo "[WARN] Passive MMDVM telemetry runtime was not activated. Core hotspot operation is unaffected."
fi
