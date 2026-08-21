#!/usr/bin/env bash
set -euo pipefail
umask 027
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $EUID -ne 0 ]]; then exec sudo "$0" "$@"; fi
VERSION="$(cat "$SELF/VERSION")"

cat <<EOF
============================================================
 YWD-Hotspot update -> $VERSION
 GitHub Integration + About
============================================================
This updater does NOT recompile MMDVM-Host or DMRGateway.
It preserves whether RF was running/enabled before the update.
EOF

if ! id ywd-hotspot >/dev/null 2>&1; then
  echo "[FAIL] Existing YWD-Hotspot service account not found. Use INSTALL.sh."
  exit 1
fi
if [[ ! -f /etc/ywd-hotspot/config.json ]]; then
  echo "[FAIL] Existing /etc/ywd-hotspot/config.json not found. Use INSTALL.sh."
  exit 1
fi

# Validate the incoming application before touching the live install.
required=(
  VERSION bin lib web systemd sudoers
  INSTALL.sh INSTALL-core.sh UPDATE.sh UPDATE-core.sh UNINSTALL.sh
  GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh
)
for item in "${required[@]}"; do [[ -e "$SELF/$item" ]] || { echo "[FAIL] Update source missing $item"; exit 1; }; done
for f in UPDATE.sh UPDATE-core.sh INSTALL.sh INSTALL-core.sh GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh UNINSTALL.sh bin/ywd-hotspotctl bin/ywd-hotspotctl-core bin/ywd-ui.sh lab/mmdvm-diag.sh; do
  [[ -f "$SELF/$f" ]] && bash -n "$SELF/$f"
done
python3 -m py_compile "$SELF"/lib/*.py

# Install the privileged bridge as one coherent generation. Newer runtimes use
# admin_dispatch.sh as the public sudo entry point and keep the historical
# admin.py helper behind ywd-hotspot-admin-core. Older installations without a
# dispatcher retain the legacy monolithic layout for rollback compatibility.
install_admin_bridge_from(){
  local root="$1"
  [[ -f "$root/lib/admin.py" ]] || return 0
  if [[ -f "$root/lib/admin_dispatch.sh" ]]; then
    install -o root -g root -m 0755 "$root/lib/admin.py" /usr/local/libexec/ywd-hotspot-admin-core
    [[ -f "$root/lib/setup_admin.py" ]] && install -o root -g root -m 0755 "$root/lib/setup_admin.py" /usr/local/libexec/ywd-hotspot-setup-admin
    [[ -f "$root/lib/update_admin.py" ]] && install -o root -g root -m 0755 "$root/lib/update_admin.py" /usr/local/libexec/ywd-hotspot-update-admin
    [[ -f "$root/lib/update_runner.py" ]] && install -o root -g root -m 0755 "$root/lib/update_runner.py" /usr/local/libexec/ywd-update-runner
    install -o root -g root -m 0755 "$root/lib/admin_dispatch.sh" /usr/local/libexec/ywd-hotspot-admin
  else
    install -o root -g root -m 0755 "$root/lib/admin.py" /usr/local/libexec/ywd-hotspot-admin
  fi
}

# Capture the current appliance state before replacing units/scripts.
mmdvm_active=0; gateway_active=0; dashboard_active=0; oled_active=0; activity_active=0; dmrid_active=0
mmdvm_enabled=0; gateway_enabled=0; dashboard_enabled=0; oled_enabled=0; activity_enabled=0; dmrid_enabled=0
systemctl is-active --quiet ywd-mmdvmhost.service 2>/dev/null && mmdvm_active=1 || true
systemctl is-active --quiet ywd-dmrgateway.service 2>/dev/null && gateway_active=1 || true
systemctl is-active --quiet ywd-dashboard.service 2>/dev/null && dashboard_active=1 || true
systemctl is-active --quiet ywd-oled.service 2>/dev/null && oled_active=1 || true
systemctl is-active --quiet ywd-activity.service 2>/dev/null && activity_active=1 || true
systemctl is-active --quiet ywd-dmrid-update.timer 2>/dev/null && dmrid_active=1 || true
systemctl is-enabled --quiet ywd-mmdvmhost.service 2>/dev/null && mmdvm_enabled=1 || true
systemctl is-enabled --quiet ywd-dmrgateway.service 2>/dev/null && gateway_enabled=1 || true
systemctl is-enabled --quiet ywd-dashboard.service 2>/dev/null && dashboard_enabled=1 || true
systemctl is-enabled --quiet ywd-oled.service 2>/dev/null && oled_enabled=1 || true
systemctl is-enabled --quiet ywd-activity.service 2>/dev/null && activity_enabled=1 || true
systemctl is-enabled --quiet ywd-dmrid-update.timer 2>/dev/null && dmrid_enabled=1 || true

mkdir -p /var/backups/ywd-hotspot
stamp="$(date +%Y%m%d-%H%M%S)"
backup_dir="/var/backups/ywd-hotspot/pre-${VERSION}-${stamp}"
install -d -m 0700 "$backup_dir"
tar -czf "$backup_dir/config.tar.gz" /etc/ywd-hotspot 2>/dev/null
[[ -d /opt/ywd-hotspot/app ]] && tar -czf "$backup_dir/app.tar.gz" /opt/ywd-hotspot/app 2>/dev/null || true
chmod 600 "$backup_dir"/*.tar.gz 2>/dev/null || true
echo "Protected pre-update backup: $backup_dir"

rollback(){
  rc=$?
  trap - ERR INT TERM
  set +e
  echo
  echo "[FAIL] Update failed (exit $rc). Restoring the previous YWD-Hotspot application/configuration..."
  systemctl stop ywd-dmrgateway.service ywd-mmdvmhost.service ywd-dashboard.service ywd-oled.service ywd-activity.service ywd-dmrid-update.timer 2>/dev/null || true

  if [[ -f "$backup_dir/config.tar.gz" ]]; then
    rm -rf /etc/ywd-hotspot
    tar -xzf "$backup_dir/config.tar.gz" -C /
  fi
  if [[ -f "$backup_dir/app.tar.gz" ]]; then
    rm -rf /opt/ywd-hotspot/app
    tar -xzf "$backup_dir/app.tar.gz" -C /
  fi

  if [[ -d /opt/ywd-hotspot/app ]]; then
    [[ -f /opt/ywd-hotspot/app/bin/ywd-hotspotctl ]] && install -m 0755 /opt/ywd-hotspot/app/bin/ywd-hotspotctl /usr/local/sbin/ywd-hotspotctl
    install_admin_bridge_from /opt/ywd-hotspot/app
    [[ -f /opt/ywd-hotspot/app/sudoers/ywd-hotspot ]] && install -o root -g root -m 0440 /opt/ywd-hotspot/app/sudoers/ywd-hotspot /etc/sudoers.d/ywd-hotspot
    for unit in /opt/ywd-hotspot/app/systemd/*.service /opt/ywd-hotspot/app/systemd/*.timer; do
      [[ -e "$unit" ]] && install -m 0644 "$unit" "/etc/systemd/system/$(basename "$unit")"
    done
  fi
  systemctl daemon-reload

  if (( mmdvm_enabled )); then systemctl enable ywd-mmdvmhost.service >/dev/null 2>&1 || true; else systemctl disable ywd-mmdvmhost.service >/dev/null 2>&1 || true; fi
  if (( gateway_enabled )); then systemctl enable ywd-dmrgateway.service >/dev/null 2>&1 || true; else systemctl disable ywd-dmrgateway.service >/dev/null 2>&1 || true; fi
  if (( dashboard_enabled )); then systemctl enable ywd-dashboard.service >/dev/null 2>&1 || true; else systemctl disable ywd-dashboard.service >/dev/null 2>&1 || true; fi
  if (( oled_enabled )); then systemctl enable ywd-oled.service >/dev/null 2>&1 || true; else systemctl disable ywd-oled.service >/dev/null 2>&1 || true; fi
  if (( activity_enabled )); then systemctl enable ywd-activity.service >/dev/null 2>&1 || true; else systemctl disable ywd-activity.service >/dev/null 2>&1 || true; fi
  if (( dmrid_enabled )); then systemctl enable ywd-dmrid-update.timer >/dev/null 2>&1 || true; else systemctl disable ywd-dmrid-update.timer >/dev/null 2>&1 || true; fi

  if (( activity_active )); then systemctl start ywd-activity.service >/dev/null 2>&1 || true; fi
  if (( dmrid_active )); then systemctl start ywd-dmrid-update.timer >/dev/null 2>&1 || true; fi
  if (( mmdvm_active )); then systemctl start ywd-mmdvmhost.service >/dev/null 2>&1 || true; fi
  if (( gateway_active )); then sleep 1; systemctl start ywd-dmrgateway.service >/dev/null 2>&1 || true; fi
  if (( dashboard_active )); then systemctl start ywd-dashboard.service >/dev/null 2>&1 || true; fi
  if (( oled_active )); then systemctl start ywd-oled.service >/dev/null 2>&1 || true; fi

  echo "Previous installation restored. Backup retained at: $backup_dir"
  exit "$rc"
}
trap rollback ERR INT TERM

echo "Installing $VERSION runtime files..."
for g in dialout i2c systemd-journal; do
  getent group "$g" >/dev/null 2>&1 && usermod -a -G "$g" ywd-hotspot || true
done
install -d -m 0755 /opt/ywd-hotspot/app /usr/local/libexec
install -d -o root -g ywd-hotspot -m 0750 /etc/ywd-hotspot
install -d -o ywd-hotspot -g ywd-hotspot -m 0750 /var/lib/ywd-hotspot /var/lib/ywd-hotspot/diagnostics
install -d -o root -g root -m 0700 /var/lib/ywd-hotspot/private /var/lib/ywd-hotspot/private/config-history
rm -rf /opt/ywd-hotspot/app
install -d -m 0755 /opt/ywd-hotspot/app

# Copy only runtime/source files needed by the appliance. Keep the managed .git
# checkout separate in /opt/ywd-hotspot/repo. Wrapper/core pairs are copied
# together so future updates never depend on files that were left in the repo.
for item in \
  bin lib web systemd sudoers lab \
  INSTALL.sh INSTALL-core.sh UPDATE.sh UPDATE-core.sh UNINSTALL.sh \
  GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh \
  VERSION pins.env README.md MANIFEST.txt; do
  [[ -e "$SELF/$item" ]] && cp -a "$SELF/$item" /opt/ywd-hotspot/app/
done

# Ship only the small WebP badge to the appliance; keep the large master artwork
# in the repository rather than wasting Pi storage/runtime backups.
install -d -m 0755 /opt/ywd-hotspot/app/assets/branding
install -m 0644 "$SELF/assets/branding/ywd-hotspot-badge-256.webp" /opt/ywd-hotspot/app/assets/branding/ywd-hotspot-badge-256.webp

chmod +x \
  /opt/ywd-hotspot/app/INSTALL.sh /opt/ywd-hotspot/app/INSTALL-core.sh \
  /opt/ywd-hotspot/app/UPDATE.sh /opt/ywd-hotspot/app/UPDATE-core.sh \
  /opt/ywd-hotspot/app/UNINSTALL.sh \
  /opt/ywd-hotspot/app/GITHUB-UPDATE.sh /opt/ywd-hotspot/app/GITHUB-UPDATE-core.sh \
  /opt/ywd-hotspot/app/MIGRATE-TO-GITHUB.sh /opt/ywd-hotspot/app/MIGRATE-TO-GITHUB-core.sh \
  /opt/ywd-hotspot/app/bin/ywd-hotspotctl /opt/ywd-hotspot/app/bin/ywd-hotspotctl-core \
  /opt/ywd-hotspot/app/bin/ywd-ui.sh /opt/ywd-hotspot/app/lib/*.py /opt/ywd-hotspot/app/lab/mmdvm-diag.sh
install -m 0755 /opt/ywd-hotspot/app/bin/ywd-hotspotctl /usr/local/sbin/ywd-hotspotctl
install_admin_bridge_from /opt/ywd-hotspot/app
install -o root -g root -m 0440 "$SELF/sudoers/ywd-hotspot" /etc/sudoers.d/ywd-hotspot
if command -v visudo >/dev/null 2>&1; then visudo -cf /etc/sudoers.d/ywd-hotspot >/dev/null; fi
for unit in "$SELF"/systemd/*.service "$SELF"/systemd/*.timer; do
  [[ -e "$unit" ]] || continue
  install -m 0644 "$unit" "/etc/systemd/system/$(basename "$unit")"
done
systemctl daemon-reload

# Migrate config schema, then preserve the real pre-update systemd boot policy as
# the canonical rf_autostart setting.
python3 /opt/ywd-hotspot/app/lib/migrate.py
RF_ENABLED=$(( mmdvm_enabled && gateway_enabled )) python3 - <<'PY'
import json, os
from pathlib import Path
p=Path('/etc/ywd-hotspot/config.json'); c=json.loads(p.read_text())
c.setdefault('maintenance',{})['rf_autostart']=bool(int(os.environ.get('RF_ENABLED','0')))
t=p.with_suffix('.policy.tmp'); t.write_text(json.dumps(c,indent=2)+'\n'); os.chmod(t,0o640)
try:
 import grp; os.chown(t,0,grp.getgrnam('ywd-hotspot').gr_gid)
except Exception: pass
os.replace(t,p)
PY
python3 /opt/ywd-hotspot/app/lib/generate-config.py

# Record build provenance before the dashboard restarts. Environment variables
# supplied by GITHUB-UPDATE.sh override archive/no-.git discovery.
python3 /opt/ywd-hotspot/app/lib/build_info.py write --source-dir "$SELF" >/dev/null

# Keep persistent crash evidence enabled when configured.
read -r JOURNAL_ENABLED JOURNAL_MB < <(python3 - <<'PY'
import json
c=json.load(open('/etc/ywd-hotspot/config.json')); m=c.get('maintenance',{})
print(1 if m.get('persistent_journal',True) else 0, int(m.get('journal_max_mb',100)))
PY
)
if [[ "$JOURNAL_ENABLED" == "1" ]]; then
  install -d -m 0755 /var/log/journal /etc/systemd/journald.conf.d
  cat > /etc/systemd/journald.conf.d/10-ywd-hotspot-persistent.conf <<EOF
[Journal]
Storage=persistent
SystemMaxUse=${JOURNAL_MB}M
RuntimeMaxUse=50M
EOF
else
  install -d -m 0755 /etc/systemd/journald.conf.d
  cat > /etc/systemd/journald.conf.d/10-ywd-hotspot-persistent.conf <<'EOF'
[Journal]
Storage=volatile
RuntimeMaxUse=50M
EOF
fi
systemctl restart systemd-journald.service || true

# Mark the freshly generated configuration as the applied baseline.
printf '{}\n' | /usr/local/libexec/ywd-hotspot-admin init-applied >/dev/null

# ID updater is a cheap due-check; do not download if the local file is fresh.
python3 /opt/ywd-hotspot/app/lib/id-update.py || echo "[WARN] RadioID due-check/update failed; existing database retained."

# Restart only side services that were already running. Enable/disable policy is
# restored exactly below.
if (( activity_active )); then systemctl restart ywd-activity.service; fi
if (( dmrid_active )); then systemctl restart ywd-dmrid-update.timer; fi

# Apply new units without ever starting an RF path that was previously stopped.
if (( gateway_active )); then systemctl stop ywd-dmrgateway.service || true; fi
if (( mmdvm_active )); then systemctl restart ywd-mmdvmhost.service; fi
if (( gateway_active )); then sleep 2; systemctl start ywd-dmrgateway.service; fi
if (( dashboard_active )); then systemctl restart ywd-dashboard.service; fi
if (( oled_active )); then systemctl restart ywd-oled.service || true; fi

# Restore pre-update enable/disable state exactly for RF.
if (( mmdvm_enabled )); then systemctl enable ywd-mmdvmhost.service >/dev/null 2>&1; else systemctl disable ywd-mmdvmhost.service >/dev/null 2>&1 || true; fi
if (( gateway_enabled )); then systemctl enable ywd-dmrgateway.service >/dev/null 2>&1; else systemctl disable ywd-dmrgateway.service >/dev/null 2>&1 || true; fi
if (( dashboard_enabled )); then systemctl enable ywd-dashboard.service >/dev/null 2>&1; else systemctl disable ywd-dashboard.service >/dev/null 2>&1 || true; fi
if (( oled_enabled )); then systemctl enable ywd-oled.service >/dev/null 2>&1; else systemctl disable ywd-oled.service >/dev/null 2>&1 || true; fi
if (( activity_enabled )); then systemctl enable ywd-activity.service >/dev/null 2>&1; else systemctl disable ywd-activity.service >/dev/null 2>&1 || true; fi
if (( dmrid_enabled )); then systemctl enable ywd-dmrid-update.timer >/dev/null 2>&1; else systemctl disable ywd-dmrid-update.timer >/dev/null 2>&1 || true; fi

trap - ERR INT TERM
sleep 2
echo
echo "Updated to $VERSION."
echo "About/build provenance and GitHub-management support are now installed."
echo "Persistent journal: $([[ "$JOURNAL_ENABLED" == 1 ]] && echo enabled || echo disabled)"
echo "Backup retained: $backup_dir"
echo
ywd-hotspotctl status || true
