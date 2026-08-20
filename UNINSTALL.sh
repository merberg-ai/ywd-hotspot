#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then exec sudo "$0" "$@"; fi
echo "This removes YWD-Hotspot services/binaries but keeps configuration/history by default."
read -r -p "Type REMOVE to continue: " a
[[ "$a" == REMOVE ]] || exit 0

# If this application had taken over the OS-owned headless OLED renderer, put
# the image's original ExecStart back before removing /opt/ywd-hotspot.
if [[ -f /opt/ywd-hotspot/app/lib/oled_owner.sh ]]; then
  bash /opt/ywd-hotspot/app/lib/oled_owner.sh restore /opt/ywd-hotspot/app || true
fi

systemctl disable --now ywd-dmrgateway.service ywd-mmdvmhost.service ywd-dashboard.service ywd-activity.service ywd-oled.service ywd-dmrid-update.timer ywd-mmdvm-telemetry.service ywd-mqtt.service 2>/dev/null || true
systemctl stop ywd-update.service 2>/dev/null || true
rm -f /etc/systemd/system/ywd-{dmrgateway,mmdvmhost,dashboard,activity,oled,dmrid-update,update,mmdvm-telemetry,mqtt}.service /etc/systemd/system/ywd-dmrid-update.timer
rm -f /etc/sudoers.d/ywd-hotspot \
  /usr/local/libexec/ywd-hotspot-admin \
  /usr/local/libexec/ywd-hotspot-admin-core \
  /usr/local/libexec/ywd-hotspot-setup-admin \
  /usr/local/libexec/ywd-hotspot-update-admin \
  /usr/local/libexec/ywd-update-runner \
  /usr/local/bin/MMDVM-Host /usr/local/bin/DMRGateway /usr/local/sbin/ywd-hotspotctl
rm -f /etc/systemd/journald.conf.d/10-ywd-hotspot-persistent.conf

# Restore the host's pre-YWD console/MOTD files and dynamic MOTD executable
# state before removing the deployed application tree.
if [[ -f /opt/ywd-hotspot/app/lib/system_branding.sh ]]; then
  bash /opt/ywd-hotspot/app/lib/system_branding.sh restore /opt/ywd-hotspot/app || true
fi

systemctl daemon-reload
systemctl restart systemd-journald.service 2>/dev/null || true
rm -rf /opt/ywd-hotspot
echo "Removed YWD-Hotspot application/services."
echo "Kept /etc/ywd-hotspot and /var/lib/ywd-hotspot. Mosquitto OS packages, if installed, are left in place but YWD's broker service is removed."
echo "Remove retained data/packages manually only if you intend to erase credentials/history or no longer need them."
