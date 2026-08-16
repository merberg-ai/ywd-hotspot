#!/bin/bash -e

install -d -m 0755 "${ROOTFS_DIR}/usr/local/libexec" "${ROOTFS_DIR}/usr/local/sbin"
install -d -m 0700 "${ROOTFS_DIR}/etc/ywd-headless"
install -d -m 0755 "${ROOTFS_DIR}/etc/systemd/system" "${ROOTFS_DIR}/etc/modules-load.d"

install -m 0755 files/ywd-headless-oled.py "${ROOTFS_DIR}/usr/local/libexec/ywd-headless-oled.py"
install -m 0755 files/ywd-headless-provision.sh "${ROOTFS_DIR}/usr/local/sbin/ywd-headless-provision"
install -m 0644 files/ywd-headless-oled.service "${ROOTFS_DIR}/etc/systemd/system/ywd-headless-oled.service"
install -m 0644 files/ywd-headless-provision.service "${ROOTFS_DIR}/etc/systemd/system/ywd-headless-provision.service"

echo 'i2c-dev' > "${ROOTFS_DIR}/etc/modules-load.d/ywd-i2c.conf"

if [ -f files/provision.env ]; then
    install -m 0600 files/provision.env "${ROOTFS_DIR}/etc/ywd-headless/provision.env"
fi

# Enable the Pi's I2C controller using Raspberry Pi's own supported helper.
on_chroot <<'EOF'
raspi-config nonint do_i2c 0
systemctl enable NetworkManager.service
systemctl enable avahi-daemon.service
systemctl enable ywd-headless-oled.service
if [ -f /etc/ywd-headless/provision.env ]; then
    systemctl enable ywd-headless-provision.service
else
    systemctl disable ywd-headless-provision.service >/dev/null 2>&1 || true
fi
EOF
