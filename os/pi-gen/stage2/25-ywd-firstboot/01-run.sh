#!/bin/bash -e

APP="${ROOTFS_DIR}/opt/ywd-hotspot/app"
LIBEXEC="${ROOTFS_DIR}/usr/local/libexec"

for f in \
  "${APP}/lib/setup_server.py" \
  "${APP}/lib/setup_admin.py" \
  "${APP}/lib/setup_entry.sh" \
  "${APP}/lib/admin_dispatch.sh" \
  "${APP}/systemd/ywd-setup.service"; do
  if [ ! -f "$f" ]; then
    echo "ERROR: M4 first-boot payload missing: $f" >&2
    exit 1
  fi
done

# Preserve the existing validated admin helper behind a root-owned dispatcher.
install -m 0755 "${APP}/lib/admin.py" "${LIBEXEC}/ywd-hotspot-admin-core"
install -m 0755 "${APP}/lib/setup_admin.py" "${LIBEXEC}/ywd-hotspot-setup-admin"
install -m 0755 "${APP}/lib/admin_dispatch.sh" "${LIBEXEC}/ywd-hotspot-admin"
chmod 0755 "${APP}/lib/setup_server.py" "${APP}/lib/setup_admin.py" "${APP}/lib/setup_entry.sh" "${APP}/lib/admin_dispatch.sh"

install -d -m 0700 "${ROOTFS_DIR}/var/lib/ywd-hotspot/setup-tls"
printf '%s\n' 'M4-firstboot-dev' > "${ROOTFS_DIR}/etc/ywd-hotspot/os-version"
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

M3 owns Wi-Fi onboarding first. After station Wi-Fi is online, M4 starts an
HTTPS setup wizard on port 8443 and requires the six-digit code shown on the
OLED. RF services remain disabled until the final wizard page explicitly asks
to enable them.
EOF

printf 'Installed YWD-Hotspot M4 secure first-boot setup layer; RF remains disabled.\n'
