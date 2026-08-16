#!/bin/bash -e

install -d -m 0755 "${ROOTFS_DIR}/usr/local/libexec" "${ROOTFS_DIR}/etc/systemd/system"
install -d -m 0700 "${ROOTFS_DIR}/var/lib/ywd-hotspot-os"
install -m 0755 files/ywd-network-manager.py "${ROOTFS_DIR}/usr/local/libexec/ywd-network-manager.py"
install -m 0644 files/ywd-network-manager.service "${ROOTFS_DIR}/etc/systemd/system/ywd-network-manager.service"

# M3 supersedes the M1.1 one-shot build-time provisioner. The new manager still
# consumes /etc/ywd-headless/provision.env if present, but it owns retries,
# setup AP fallback, recovery AP fallback, and phone-based Wi-Fi setup.
on_chroot <<'EOF'
systemctl disable ywd-headless-provision.service >/dev/null 2>&1 || true
systemctl enable ywd-network-manager.service
EOF

printf 'Installed YWD-Hotspot M3 network recovery manager.\n'
