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

[[ -f "$SELF/lib/candidate_validate.py" ]] || { echo "[FAIL] Install source missing lib/candidate_validate.py" >&2; exit 1; }
python3 "$SELF/lib/candidate_validate.py" "$SELF"

if [[ -d "$SELF/lib/console" ]]; then
  python3 -m py_compile "$SELF/lib/console/ywd-system-info.py"
  for f in ywd-info-wrapper.sh ywd-logs.sh ywd-env.sh ywd-prompt.sh ywd-motd.sh; do
    bash -n "$SELF/lib/console/$f"
  done
fi
for f in \
  lib/candidate_validate.py \
  lib/update_runner.py lib/update_admin.py lib/oled.py lib/oled_owner.sh \
  lib/mmdvm_runtime_state.py \
  lib/plugin_manifest.py lib/plugin_manager.py lib/plugin_package_manager.py lib/plugin_package_update.py lib/plugin_service_manager.py lib/plugin_ui_manager.py \
  lib/plugin_catalog_overlay.py lib/plugin_package_archive.py lib/plugin_service_runner.py lib/plugin_feature_runtime.py \
  lib/plugin_admin_common.py lib/plugin_admin_state.py lib/plugin_admin_packages.py lib/plugin_admin_upload.py lib/plugin_admin.py \
  lib/dashboard_plugins.py lib/dashboard_plugin_upload.py lib/dashboard_plugin_vocoder.py lib/dashboard_plugin_wasm.py lib/dashboard_backup.py \
  lib/settings_backup.py lib/settings_admin.py lib/setup_restore_server.py lib/setup_entry.sh \
  lib/mmdvm_telemetry.py lib/mmdvm_telemetry_bridge.py lib/mmdvm_session.py lib/telemetry_runtime.py lib/ywd-mosquitto.conf \
  lib/mmdvm_voice.py lib/mmdvm_voice_bridge.py lib/mmdvm_voice_build.py lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch \
  lib/vocoder_protocol.py lib/vocoder_client.py lib/vocoder_fake_backend.py lib/vocoder_runtime_policy.sh \
  web/plugin-manager-render.js web/plugin-package-actions.js web/plugin-package-upload.js web/plugin-package-update.js web/plugin-manager.js web/plugin-manager.css web/plugin-config-actions.js \
  web/plugin-ui-host.js web/plugin-ui-runtime.js web/plugin-ui.css \
  web/backup-restore.js web/backup-restore.css \
  systemd/ywd-plugin@.service systemd/ywd-mqtt.service systemd/ywd-mmdvm-telemetry.service systemd/ywd-mmdvm-voice.service systemd/ywd-mmdvm-voice-build.service \
  systemd/ywd-vocoder-fake.service systemd/ywd-vocoder-fake.socket \
  systemd/ywd-vocoder-mbelib.service.d/20-ywd-hotspot-normal-priority.conf \
  web/instrumentation.js web/instrumentation-bootstrap.js web/instrumentation.css; do
  [[ -f "$SELF/$f" ]] || { echo "[FAIL] Install source missing $f" >&2; exit 1; }
done

mapfile -t py_sources < <(find "$SELF/lib" -type f -name '*.py' -print | sort)
((${#py_sources[@]})) || { echo "[FAIL] No Python runtime sources found" >&2; exit 1; }
python3 -m py_compile "${py_sources[@]}"
[[ -f "$SELF/lib/system_branding.sh" ]] && bash -n "$SELF/lib/system_branding.sh"
bash -n "$SELF/lib/oled_owner.sh" "$SELF/lib/setup_entry.sh" "$SELF/lib/vocoder_runtime_policy.sh"

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
import dashboard_backup, dashboard_plugin_upload, dashboard_plugin_vocoder
import mmdvm_runtime_state, vocoder_client, vocoder_protocol
import plugin_catalog_overlay, plugin_package_archive, plugin_service_runner, plugin_feature_runtime
import plugin_manager, plugin_service_manager, settings_backup
base = plugin_manager.snapshot({"hostname":"candidate","uptime_s":1,"temperature_c":25,"load":[0,0,0]})
assert base["system"]["enabled"] is False
assert all(p.get("valid") is True for p in base.get("plugins", [])), base.get("plugins", [])
services = plugin_service_manager.discover()
assert all(p.get("valid") is True for p in services), services
assert all(not p.get("manifest", {}).get("rf_mode") for p in services if p.get("valid")), services
PY

CORE="$SELF/INSTALL-core.sh"
[[ -f "$CORE" ]] || CORE="/opt/ywd-hotspot/repo/INSTALL-core.sh"
[[ -f "$CORE" ]] || { echo "[FAIL] Installer core not found." >&2; exit 1; }

# INSTALL-core is intentionally interactive. Do not pipe it through the normal
# stream colorizer: doing so makes Python/read prompts cease to behave like a
# real terminal on some SSH/console combinations. Keep stdin and stdout attached
# to the operator's terminal so typed values, defaults and validation feedback
# remain visible throughout fresh/recovery installation.
if [[ -r /dev/tty && -w /dev/tty ]]; then
  bash "$CORE" "$@" </dev/tty
else
  bash "$CORE" "$@"
fi

# The external vocoder remains separately installed. YWD owns only the normal
# scheduling policy proven necessary for smooth RX audio on constrained hosts.
sudo bash "$SELF/lib/vocoder_runtime_policy.sh" install "$SELF"

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

# Telemetry is passive core infrastructure. Failure here never turns a successful
# DMR install into an RF outage; dashboard diagnostics can report the bridge state.
if ! sudo python3 /opt/ywd-hotspot/app/lib/telemetry_runtime.py ensure; then
  echo "[WARN] Passive MMDVM telemetry runtime was not activated. Core hotspot operation is unaffected."
fi

# Persist capability identity from the exact installed MMDVM binary without
# compiling or restarting RF.
if ! sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_runtime_state.py refresh >/dev/null; then
  echo "[WARN] MMDVM runtime capability metadata could not be refreshed. Exact observed checks remain authoritative."
fi

# Optional high-rate feature runtimes are owned by aggregate plugin capability
# demand, never by installation alone. Fresh installs therefore converge to OFF.
if ! sudo python3 /opt/ywd-hotspot/app/lib/plugin_feature_runtime.py reconcile; then
  echo "[WARN] Optional plugin feature runtime did not reconcile. Core hotspot operation is unaffected."
fi
