#!/bin/bash -e

THIS_STAGE="$(pwd -P)"
APP="${ROOTFS_DIR}/opt/ywd-hotspot/app"
LIBEXEC="${ROOTFS_DIR}/usr/local/libexec"
FACTORY_CONFIG="${THIS_STAGE}/files/factory-config.json"
FACTORY_PAYLOAD="${THIS_STAGE}/files/factory-provision.json"
FACTORY_RESTORE="${THIS_STAGE}/files/factory-restore.json"
FACTORY_HELPER="${THIS_STAGE}/files/ywd-factory-provision.py"
FACTORY_UNIT="${THIS_STAGE}/files/ywd-factory-provision.service"

for f in \
  "${APP}/lib/setup_server.py" \
  "${APP}/lib/setup_restore_server.py" \
  "${APP}/lib/settings_backup.py" \
  "${APP}/lib/settings_admin.py" \
  "${APP}/lib/setup_admin.py" \
  "${APP}/lib/setup_entry.sh" \
  "${APP}/lib/admin_dispatch.sh" \
  "${APP}/lib/update_admin.py" \
  "${APP}/lib/update_runner.py" \
  "${APP}/systemd/ywd-setup.service" \
  "${APP}/systemd/ywd-update.service" \
  "${FACTORY_HELPER}" \
  "${FACTORY_UNIT}"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: first-boot/current-update payload missing: $f" >&2
    exit 1
  fi
done

install -m 0755 "${APP}/lib/admin.py" "${LIBEXEC}/ywd-hotspot-admin-core"
install -m 0755 "${APP}/lib/setup_admin.py" "${LIBEXEC}/ywd-hotspot-setup-admin"
install -m 0755 "${APP}/lib/update_admin.py" "${LIBEXEC}/ywd-hotspot-update-admin"
install -m 0755 "${APP}/lib/update_runner.py" "${LIBEXEC}/ywd-update-runner"
install -m 0755 "${APP}/lib/admin_dispatch.sh" "${LIBEXEC}/ywd-hotspot-admin"
install -m 0755 "${FACTORY_HELPER}" "${LIBEXEC}/ywd-factory-provision"
install -m 0644 "${FACTORY_UNIT}" "${ROOTFS_DIR}/etc/systemd/system/ywd-factory-provision.service"
chmod 0755 \
  "${APP}/lib/setup_server.py" "${APP}/lib/setup_restore_server.py" \
  "${APP}/lib/settings_backup.py" "${APP}/lib/settings_admin.py" \
  "${APP}/lib/setup_admin.py" "${APP}/lib/setup_entry.sh" \
  "${APP}/lib/admin_dispatch.sh" "${APP}/lib/update_admin.py" "${APP}/lib/update_runner.py"

if [ -f "${FACTORY_CONFIG}" ]; then
  # Install from the builder host, but apply named ownership in the target
  # chroot below. Resolving ywd-hotspot on the builder host is incorrect and
  # fails when that group does not exist outside the image rootfs.
  install -m 0640 "${FACTORY_CONFIG}" "${ROOTFS_DIR}/etc/ywd-hotspot/config.json"
  printf 'Installed builder-supplied canonical hotspot configuration.\n'
fi

install -d -m 0700 "${ROOTFS_DIR}/var/lib/ywd-hotspot/private"
if [ -f "${FACTORY_PAYLOAD}" ]; then
  install -m 0600 "${FACTORY_PAYLOAD}" "${ROOTFS_DIR}/var/lib/ywd-hotspot/private/factory-provision.json"
  chown root:root "${ROOTFS_DIR}/var/lib/ywd-hotspot/private/factory-provision.json"
  printf 'Installed sealed factory preconfiguration payload.\n'
fi
if [ -f "${FACTORY_RESTORE}" ]; then
  install -m 0600 "${FACTORY_RESTORE}" "${ROOTFS_DIR}/var/lib/ywd-hotspot/private/factory-restore.json"
  chown root:root "${ROOTFS_DIR}/var/lib/ywd-hotspot/private/factory-restore.json"
  printf 'Installed sealed dashboard settings restore payload.\n'
fi

install -d -m 0755 "${ROOTFS_DIR}/etc/systemd/system/ywd-setup.service.d"
cat > "${ROOTFS_DIR}/etc/systemd/system/ywd-setup.service.d/10-factory-provision.conf" <<'EOF'
[Unit]
Wants=ywd-factory-provision.service
After=ywd-factory-provision.service
EOF

on_chroot <<'EOF'
set -e
if [ -f /etc/ywd-hotspot/config.json ]; then
    chown root:ywd-hotspot /etc/ywd-hotspot/config.json
    chmod 0640 /etc/ywd-hotspot/config.json
fi
chmod 0700 /var/lib/ywd-hotspot/private
chown root:root /var/lib/ywd-hotspot/private
rm -f /var/lib/ywd-hotspot/setup-state.json
rm -f /etc/ywd-hotspot/web-auth.json /etc/ywd-hotspot/bm-api.key
visudo -cf /etc/sudoers.d/ywd-hotspot >/dev/null
systemctl enable ywd-factory-provision.service
systemctl enable ywd-setup.service
systemctl disable ywd-mmdvmhost.service ywd-dmrgateway.service ywd-oled.service >/dev/null 2>&1 || true
systemctl enable ywd-headless-oled.service

# Public factory images ship with SSH closed and no reusable server identity.
# openssh-server remains installed so the authenticated dashboard can enable it
# later. Unique ssh_host_* keys are generated locally on the appliance the
# first time SSH is explicitly enabled.
systemctl disable ssh.service >/dev/null 2>&1 || true
rm -f /etc/ssh/ssh_host_*_key /etc/ssh/ssh_host_*_key.pub
EOF

cat > "${ROOTFS_DIR}/etc/ywd-hotspot/m4-safety.txt" <<'EOF'
YWD-Hotspot OS first-boot safety state

The appliance is factory-unconfigured until:
  /var/lib/ywd-hotspot/setup-state.json
exists with state=complete.

A complete builder profile is finalized before the setup wizard starts.
If the builder imported a dashboard .ywdsettings backup, the first-boot
finalizer uses the same authenticated settings-import implementation as the
live dashboard restore flow. This preserves the imported dashboard credential,
BrandMeister/TGIF state, calibration baseline and compatible plugin state/config.

If the builder profile is partial, invalid, or the factory finalizer fails, the
normal flow remains authoritative: network onboarding owns Wi-Fi first, then the
HTTP first-boot setup wizard starts on port 8443 and requires the six-digit OLED
code. Use http://<LAN-IP>:8443/ or http://ywd-hotspot.local:8443/ when mDNS is
available. RF stays disabled unless the completed configuration explicitly
requests RF autostart.

Public factory SSH policy:
  - openssh-server is installed but disabled
  - no client key is embedded
  - no reusable ssh_host_* identity key is shipped
  - enabling SSH from the authenticated dashboard generates unique host keys
  - root SSH remains disabled; password authentication is only enabled by an
    explicit dashboard choice
EOF

printf 'Installed current YWD-Hotspot HTTP first-boot + factory-preconfiguration layer; RF/SSH remain gated.\n'
