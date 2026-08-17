#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -r "$SELF/bin/ywd-ui.sh" ]] && source "$SELF/bin/ywd-ui.sh"
VERSION="$(cat "$SELF/VERSION" 2>/dev/null || echo unknown)"
if declare -F ywd_banner >/dev/null; then
  ywd_banner "APPLIANCE UPDATE" "$VERSION"
  ywd_info "Configuration, credentials and calibration data are preserved."
  ywd_info "MMDVM-Host / DMRGateway are not recompiled by normal app updates."
fi

# Nested console/update/display/plugin helpers are validated before any live
# service/config work begins.
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
  lib/dashboard_plugins.py lib/dashboard_plugin_upload.py lib/dashboard_backup.py lib/plugin_update_safety.py \
  lib/settings_backup.py lib/settings_admin.py lib/setup_restore_server.py lib/setup_entry.sh \
  lib/mmdvm_telemetry.py lib/mmdvm_telemetry_bridge.py lib/telemetry_runtime.py lib/ywd-mosquitto.conf \
  lib/plugin_packages/system-info/plugin.json \
  lib/plugin_packages/system-info/config.schema.json \
  lib/service_plugin_packages/service-heartbeat/plugin.json \
  lib/service_plugin_packages/service-heartbeat/config.schema.json \
  lib/service_plugin_packages/service-heartbeat/service.py \
  lib/service_plugin_packages/mmdvm-live-telemetry/plugin.json \
  lib/service_plugin_packages/mmdvm-live-telemetry/config.schema.json \
  lib/service_plugin_packages/mmdvm-live-telemetry/service.py \
  web/update.js web/update.css web/update-progress.js \
  web/instrumentation.js web/instrumentation-bootstrap.js web/instrumentation.css \
  web/plugin-manager-render.js web/plugin-package-actions.js web/plugin-package-upload.js web/plugin-manager.js web/plugin-manager.css web/plugin-config-actions.js web/plugin-telemetry.js \
  web/backup-restore.js web/backup-restore.css \
  systemd/ywd-update.service systemd/ywd-plugin@.service systemd/ywd-mqtt.service systemd/ywd-mmdvm-telemetry.service; do
  [[ -f "$SELF/$f" ]] || { echo "[FAIL] Update source missing $f" >&2; exit 1; }
done
python3 -m py_compile \
  "$SELF/lib/update_runner.py" "$SELF/lib/update_admin.py" "$SELF/lib/dashboard_update.py" "$SELF/lib/oled.py" \
  "$SELF/lib/plugin_manifest.py" "$SELF/lib/plugin_manager.py" "$SELF/lib/plugin_package_manager.py" "$SELF/lib/plugin_service_manager.py" \
  "$SELF/lib/plugin_catalog_overlay.py" "$SELF/lib/plugin_package_archive.py" "$SELF/lib/plugin_service_runner.py" \
  "$SELF/lib/plugin_admin_common.py" "$SELF/lib/plugin_admin_state.py" "$SELF/lib/plugin_admin_packages.py" "$SELF/lib/plugin_admin_upload.py" "$SELF/lib/plugin_admin.py" \
  "$SELF/lib/dashboard_plugins.py" "$SELF/lib/dashboard_plugin_upload.py" "$SELF/lib/dashboard_backup.py" \
  "$SELF/lib/plugin_update_safety.py" "$SELF/lib/settings_backup.py" "$SELF/lib/settings_admin.py" "$SELF/lib/setup_restore_server.py" \
  "$SELF/lib/mmdvm_telemetry.py" "$SELF/lib/mmdvm_telemetry_bridge.py" "$SELF/lib/telemetry_runtime.py" \
  "$SELF/lib/service_plugin_packages/service-heartbeat/service.py" "$SELF/lib/service_plugin_packages/mmdvm-live-telemetry/service.py"
bash -n "$SELF/lib/oled_owner.sh" "$SELF/lib/setup_entry.sh"
[[ -f "$SELF/lib/system_branding.sh" ]] && bash -n "$SELF/lib/system_branding.sh"

# Validate both plugin catalogs with isolated missing state/config/package paths.
# Missing activation state remains fail-closed. Missing package state uses only
# the explicit Alpha15 legacy-installed IDs so the Alpha16 update preserves the
# two already-proven reference plugins but future new packages stay available,
# not installed.
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
system_info = [p for p in base["plugins"] if p.get("id") == "system-info"]
assert len(system_info) == 1 and system_info[0].get("valid") and system_info[0].get("installed"), system_info
services = plugin_service_manager.snapshot()
heartbeat = [p for p in services if p.get("id") == "service-heartbeat"]
assert len(heartbeat) == 1 and heartbeat[0].get("valid") and heartbeat[0].get("installed"), heartbeat
telemetry = [p for p in services if p.get("id") == "mmdvm-live-telemetry"]
assert len(telemetry) == 1 and telemetry[0].get("valid") and not telemetry[0].get("installed"), telemetry
assert telemetry[0].get("provider") == "mmdvm-telemetry", telemetry
assert all(not p.get("rf_mode") for p in services)
PY

CORE="$SELF/UPDATE-core.sh"
[[ -f "$CORE" ]] || CORE="/opt/ywd-hotspot/repo/UPDATE-core.sh"
[[ -f "$CORE" ]] || { echo "[FAIL] Updater core not found." >&2; exit 1; }

repair_live_admin_bridge(){
  local live=/opt/ywd-hotspot/app
  [[ -f "$live/lib/admin_dispatch.sh" && -f "$live/lib/admin.py" ]] || return 0
  sudo install -o root -g root -m 0755 "$live/lib/admin.py" /usr/local/libexec/ywd-hotspot-admin-core
  [[ -f "$live/lib/setup_admin.py" ]] && sudo install -o root -g root -m 0755 "$live/lib/setup_admin.py" /usr/local/libexec/ywd-hotspot-setup-admin
  [[ -f "$live/lib/update_admin.py" ]] && sudo install -o root -g root -m 0755 "$live/lib/update_admin.py" /usr/local/libexec/ywd-hotspot-update-admin
  [[ -f "$live/lib/update_runner.py" ]] && sudo install -o root -g root -m 0755 "$live/lib/update_runner.py" /usr/local/libexec/ywd-update-runner
  sudo install -o root -g root -m 0755 "$live/lib/admin_dispatch.sh" /usr/local/libexec/ywd-hotspot-admin
  [[ -f "$live/sudoers/ywd-hotspot" ]] && sudo install -o root -g root -m 0440 "$live/sudoers/ywd-hotspot" /etc/sudoers.d/ywd-hotspot
  if command -v visudo >/dev/null 2>&1 && [[ -f /etc/sudoers.d/ywd-hotspot ]]; then
    sudo visudo -cf /etc/sudoers.d/ywd-hotspot >/dev/null
  fi
  sudo systemctl daemon-reload
}

# Capture plugin intent + exact service boot/runtime state before replacing the
# application. State/config/package files are not changed here; services are
# simply made inert for the duration of the core update.
PLUGIN_UPDATE_SNAPSHOT="$(mktemp /run/ywd-hotspot-plugin-update.XXXXXX.json)"
cleanup_plugin_snapshot(){ sudo rm -f "$PLUGIN_UPDATE_SNAPSHOT" 2>/dev/null || true; }
trap cleanup_plugin_snapshot EXIT
sudo python3 "$SELF/lib/plugin_update_safety.py" capture \
  --snapshot "$PLUGIN_UPDATE_SNAPSHOT" --lib /opt/ywd-hotspot/app/lib >/dev/null
sudo python3 "$SELF/lib/plugin_update_safety.py" quiesce \
  --snapshot "$PLUGIN_UPDATE_SNAPSHOT" --lib /opt/ywd-hotspot/app/lib >/dev/null
echo "Plugin services quiesced for application update."

# YWD-Hotspot OS already has one authoritative OLED owner. Ensure the legacy
# app unit is off before the core updater captures service state so it cannot be
# restarted alongside ywd-headless-oled during this transition.
if sudo systemctl cat ywd-headless-oled.service >/dev/null 2>&1; then
  sudo systemctl disable --now ywd-oled.service >/dev/null 2>&1 || true
fi

# Preserve the proven core updater/rollback engine. If it fails, it restores the
# old app/config first; this wrapper repairs the restored split admin bridge and
# then restores the captured plugin runtime against that old application.
set +e
if declare -F ywd_run_colored >/dev/null; then
  ywd_run_colored bash "$CORE" "$@"
  core_rc=$?
else
  bash "$CORE" "$@"
  core_rc=$?
fi
set -e
if (( core_rc != 0 )); then
  echo "Repairing restored admin bridge after core rollback..."
  repair_live_admin_bridge || echo "[WARN] Restored admin bridge needs manual review."
  echo "Restoring pre-update plugin runtime after core rollback..."
  sudo python3 "$SELF/lib/plugin_update_safety.py" restore \
    --snapshot "$PLUGIN_UPDATE_SNAPSHOT" --lib /opt/ywd-hotspot/app/lib || \
    echo "[WARN] Plugin runtime restore after rollback needs manual review."
  exit "$core_rc"
fi

# The new runtime and generic plugin unit are now installed. Reconcile against
# the target catalogs: only previously enabled plugins that still validate are
# eligible for restoration, and exact service boot/runtime state is preserved.
echo "Reconciling plugin runtime with updated application..."
sudo python3 "$SELF/lib/plugin_update_safety.py" restore \
  --snapshot "$PLUGIN_UPDATE_SNAPSHOT" --lib /opt/ywd-hotspot/app/lib

# Persist first-party update channels from the invoking GitHub updater. This is
# intentionally done by the incoming candidate so an older main/dev-only updater
# can bootstrap an appliance onto dev-plugins in one explicit branch update.
case "${YWD_UPDATE_CHANNEL:-}" in
  main|dev|dev-plugins)
    printf '%s\n' "$YWD_UPDATE_CHANNEL" | sudo tee /etc/ywd-hotspot/update-channel.tmp >/dev/null
    sudo chmod 0644 /etc/ywd-hotspot/update-channel.tmp
    sudo chown root:root /etc/ywd-hotspot/update-channel.tmp 2>/dev/null || true
    sudo mv -f /etc/ywd-hotspot/update-channel.tmp /etc/ywd-hotspot/update-channel
    ;;
esac

if [[ -f "$SELF/lib/admin_dispatch.sh" && -f "$SELF/lib/setup_admin.py" ]]; then
  sudo install -o root -g root -m 0755 "$SELF/lib/admin.py" /usr/local/libexec/ywd-hotspot-admin-core
  sudo install -o root -g root -m 0755 "$SELF/lib/setup_admin.py" /usr/local/libexec/ywd-hotspot-setup-admin
  sudo install -o root -g root -m 0755 "$SELF/lib/update_admin.py" /usr/local/libexec/ywd-hotspot-update-admin
  sudo install -o root -g root -m 0755 "$SELF/lib/update_runner.py" /usr/local/libexec/ywd-update-runner
  sudo install -o root -g root -m 0755 "$SELF/lib/admin_dispatch.sh" /usr/local/libexec/ywd-hotspot-admin
  [[ -f "$SELF/lib/setup_entry.sh" ]] && sudo chmod 0755 "$SELF/lib/setup_entry.sh"
  sudo chmod 0755 "$SELF/lib/admin_dispatch.sh" "$SELF/lib/setup_admin.py" "$SELF/lib/update_admin.py" "$SELF/lib/update_runner.py"
  if command -v visudo >/dev/null 2>&1 && [[ -f /etc/sudoers.d/ywd-hotspot ]]; then
    sudo visudo -cf /etc/sudoers.d/ywd-hotspot >/dev/null
  fi
  sudo systemctl daemon-reload
fi

if [[ -f "$SELF/lib/system_branding.sh" ]]; then
  sudo bash "$SELF/lib/system_branding.sh" install "$SELF"
fi

# Point the sole OS OLED owner at the unified renderer. Generic installs have
# no headless unit, so this helper is a no-op there.
if [[ -f "$SELF/lib/oled_owner.sh" ]]; then
  sudo bash "$SELF/lib/oled_owner.sh" install "$SELF"
fi

# Passive telemetry is intentionally fail-soft: package/broker problems must not
# turn a successful core update into a DMR outage. The plugin will expose the
# missing dependency/bridge state for repair instead.
if ! sudo python3 /opt/ywd-hotspot/app/lib/telemetry_runtime.py ensure; then
  echo "[WARN] Passive MMDVM telemetry runtime was not activated. Core hotspot operation is unaffected."
fi
