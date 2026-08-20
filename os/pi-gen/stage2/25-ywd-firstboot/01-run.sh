#!/bin/bash -e

APP="${ROOTFS_DIR}/opt/ywd-hotspot/app"
LIBEXEC="${ROOTFS_DIR}/usr/local/libexec"

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
  "${APP}/systemd/ywd-update.service"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: first-boot/current-update payload missing: $f" >&2
    exit 1
  fi
done

# Install the same narrow helper layout used by current INSTALL/UPDATE. The
# browser never receives a general-purpose root shell path.
install -m 0755 "${APP}/lib/admin.py" "${LIBEXEC}/ywd-hotspot-admin-core"
install -m 0755 "${APP}/lib/setup_admin.py" "${LIBEXEC}/ywd-hotspot-setup-admin"
install -m 0755 "${APP}/lib/update_admin.py" "${LIBEXEC}/ywd-hotspot-update-admin"
install -m 0755 "${APP}/lib/update_runner.py" "${LIBEXEC}/ywd-update-runner"
install -m 0755 "${APP}/lib/admin_dispatch.sh" "${LIBEXEC}/ywd-hotspot-admin"
chmod 0755 \
  "${APP}/lib/setup_server.py" "${APP}/lib/setup_restore_server.py" \
  "${APP}/lib/settings_backup.py" "${APP}/lib/settings_admin.py" \
  "${APP}/lib/setup_admin.py" "${APP}/lib/setup_entry.sh" \
  "${APP}/lib/admin_dispatch.sh" "${APP}/lib/update_admin.py" "${APP}/lib/update_runner.py"

install -d -m 0700 "${ROOTFS_DIR}/var/lib/ywd-hotspot/setup-tls"
on_chroot <<'EOF'
set -e
chown -R ywd-hotspot:ywd-hotspot /var/lib/ywd-hotspot/setup-tls
rm -f /var/lib/ywd-hotspot/setup-state.json
rm -f /etc/ywd-hotspot/web-auth.json /etc/ywd-hotspot/bm-api.key
visudo -cf /etc/sudoers.d/ywd-hotspot >/dev/null
systemctl enable ywd-setup.service
systemctl disable ywd-mmdvmhost.service ywd-dmrgateway.service ywd-oled.service >/dev/null 2>&1 || true
systemctl enable ywd-headless-oled.service
EOF

cat > "${ROOTFS_DIR}/etc/ywd-hotspot/m4-safety.txt" <<'EOF'
YWD-Hotspot OS M4 first-boot safety state

The appliance is factory-unconfigured until:
  /var/lib/ywd-hotspot/setup-state.json
exists with state=complete.

The network layer owns Wi-Fi onboarding first. After station Wi-Fi is online,
the secure setup wizard starts on HTTPS port 8443 and requires the six-digit
code shown on the OLED. The operator may either complete normal setup or restore
a verified encrypted .ywdsettings backup. RF services remain disabled until the
final wizard/restore action explicitly asks to enable them.
EOF

printf 'Installed current YWD-Hotspot secure first-boot + restore layer; RF remains disabled.\n'
