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

# Enable I2C in the target boot configuration directly. Do not call
# `raspi-config do_i2c` inside the builder chroot: that helper tries to probe
# configfs and modprobe i2c-dev against the *builder host* kernel, which causes
# noisy false failures when building armhf on a Pi 5.
CONFIG_TXT="${ROOTFS_DIR}/boot/firmware/config.txt"
if [ -f "${CONFIG_TXT}" ]; then
    if grep -Eq '^[[:space:]]*dtparam=i2c_arm=' "${CONFIG_TXT}"; then
        sed -i -E 's/^[[:space:]]*dtparam=i2c_arm=.*/dtparam=i2c_arm=on/' "${CONFIG_TXT}"
    else
        printf '\n# YWD-Hotspot OLED / I2C\ndtparam=i2c_arm=on\n' >> "${CONFIG_TXT}"
    fi
fi

on_chroot <<'EOF'
systemctl enable NetworkManager.service
systemctl enable avahi-daemon.service
systemctl enable ywd-headless-oled.service
if [ -f /etc/ywd-headless/provision.env ]; then
    systemctl enable ywd-headless-provision.service
else
    systemctl disable ywd-headless-provision.service >/dev/null 2>&1 || true
fi
EOF
