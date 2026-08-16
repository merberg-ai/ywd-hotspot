#!/bin/bash -e

# pi-gen executes substage run scripts after pushd'ing into the substage, but
# SUB_STAGE_DIR is a non-exported parent-shell variable. Anchor all payload
# paths to this script's actual working directory instead of relying on that
# variable being inherited.
THIS_STAGE="$(pwd -P)"
APP_SRC="${THIS_STAGE}/files/app"
BUILD_ENV="${THIS_STAGE}/files/build.env"

printf 'M2 runtime stage directory: %s\n' "$THIS_STAGE"
printf 'M2 runtime app payload:    %s\n' "$APP_SRC"

if [ ! -d "${APP_SRC}" ] || [ ! -f "${APP_SRC}/pins.env" ]; then
  echo "ERROR: M2 runtime app payload was not injected by os/builder/BUILD.sh" >&2
  echo "       Expected: ${APP_SRC}/pins.env" >&2
  ls -la "${THIS_STAGE}/files" 2>/dev/null || true
  exit 1
fi
if [ ! -f "${BUILD_ENV}" ]; then
  echo "ERROR: M2 build metadata was not injected by os/builder/BUILD.sh" >&2
  echo "       Expected: ${BUILD_ENV}" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${APP_SRC}/pins.env"
# shellcheck disable=SC1090
source "${BUILD_ENV}"

printf 'Installing YWD-Hotspot M2 runtime payload...\n'

on_chroot <<'EOF'
if ! id ywd-hotspot >/dev/null 2>&1; then
  useradd --system --home /var/lib/ywd-hotspot --create-home --shell /usr/sbin/nologin ywd-hotspot
fi
for g in dialout i2c systemd-journal; do
  getent group "$g" >/dev/null 2>&1 && usermod -a -G "$g" ywd-hotspot || true
done
EOF

install -d -m 0755 "${ROOTFS_DIR}/opt/ywd-hotspot/app" "${ROOTFS_DIR}/usr/local/libexec"
install -d -m 0750 "${ROOTFS_DIR}/etc/ywd-hotspot"
install -d -m 0750 "${ROOTFS_DIR}/var/lib/ywd-hotspot" "${ROOTFS_DIR}/var/lib/ywd-hotspot/diagnostics"
install -d -m 0700 "${ROOTFS_DIR}/var/lib/ywd-hotspot/private" "${ROOTFS_DIR}/var/lib/ywd-hotspot/private/config-history"
cp -a "${APP_SRC}/." "${ROOTFS_DIR}/opt/ywd-hotspot/app/"

chmod +x \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/INSTALL.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/INSTALL-core.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/UPDATE.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/UPDATE-core.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/UNINSTALL.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/GITHUB-UPDATE.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/GITHUB-UPDATE-core.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/MIGRATE-TO-GITHUB.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/MIGRATE-TO-GITHUB-core.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/bin/ywd-hotspotctl" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/bin/ywd-hotspotctl-core" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/bin/ywd-ui.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/lib/"*.py \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/lab/mmdvm-diag.sh"

install -m 0755 "${APP_SRC}/bin/ywd-hotspotctl" "${ROOTFS_DIR}/usr/local/sbin/ywd-hotspotctl"
install -m 0755 "${APP_SRC}/lib/admin.py" "${ROOTFS_DIR}/usr/local/libexec/ywd-hotspot-admin"
install -m 0440 "${APP_SRC}/sudoers/ywd-hotspot" "${ROOTFS_DIR}/etc/sudoers.d/ywd-hotspot"

for unit in "${APP_SRC}"/systemd/*.service "${APP_SRC}"/systemd/*.timer; do
  install -m 0644 "$unit" "${ROOTFS_DIR}/etc/systemd/system/$(basename "$unit")"
done

cat > "${ROOTFS_DIR}/etc/ywd-hotspot/config.json" <<'EOF'
{
  "schema": 3,
  "station": {
    "callsign": "NOCALL",
    "base_dmr_id": "00000",
    "essid": "01",
    "hotspot_id": 1,
    "location": "Hotspot",
    "description": "YWD Hotspot",
    "latitude": 0.0,
    "longitude": 0.0,
    "height": 0,
    "url": ""
  },
  "radio": {
    "frequency_hz": 446525000,
    "color_code": 1,
    "rx_offset": 0,
    "tx_offset": 0,
    "tx_invert": 1,
    "rx_invert": 0,
    "rx_level": 50,
    "tx_level": 50,
    "rf_level": 100,
    "jitter_ms": 360,
    "call_hang_s": 3,
    "tx_hang_s": 4,
    "timeout_s": 180,
    "uart": "/dev/serial0",
    "uart_speed": 115200
  },
  "brandmeister": {
    "enabled": false,
    "master": "3103.master.brandmeister.network",
    "port": 62031,
    "password": ""
  },
  "display": {
    "enabled": true,
    "i2c_bus": 1,
    "address": "0x3c",
    "brightness": 127,
    "idle_timeout_s": 0
  },
  "web": {
    "bind": "0.0.0.0",
    "port": 8080
  },
  "maintenance": {
    "rf_autostart": false,
    "persistent_journal": true,
    "journal_max_mb": 100,
    "dmrid_update_days": 7,
    "config_history_keep": 10
  }
}
EOF

printf '%s\n' 'dev-os' > "${ROOTFS_DIR}/etc/ywd-hotspot/update-channel"
printf '%s\n' 'M2-runtime-dev' > "${ROOTFS_DIR}/etc/ywd-hotspot/os-version"
touch "${ROOTFS_DIR}/var/lib/ywd-hotspot/DMRIds.dat"

# Configure the Pi Zero W GPIO14/15 UART for the MMDVM HAT. Bluetooth is
# deliberately disabled so /dev/serial0 maps to the PL011 /dev/ttyAMA0.
CONFIG_TXT="${ROOTFS_DIR}/boot/firmware/config.txt"
CMDLINE_TXT="${ROOTFS_DIR}/boot/firmware/cmdline.txt"
if [ -f "${CONFIG_TXT}" ]; then
  if grep -Eq '^[[:space:]]*enable_uart=' "${CONFIG_TXT}"; then
    sed -i -E 's/^[[:space:]]*enable_uart=.*/enable_uart=1/' "${CONFIG_TXT}"
  else
    printf '\n# YWD-Hotspot MMDVM HAT UART\nenable_uart=1\n' >> "${CONFIG_TXT}"
  fi
  if ! grep -Eq '^[[:space:]]*dtoverlay=disable-bt([,[:space:]]|$)' "${CONFIG_TXT}"; then
    printf 'dtoverlay=disable-bt\n' >> "${CONFIG_TXT}"
  fi
fi
if [ -f "${CMDLINE_TXT}" ]; then
  sed -i -E \
    -e 's/(^|[[:space:]])console=(serial0|ttyAMA[0-9]*|ttyS[0-9]*),[^[:space:]]+//g' \
    -e 's/[[:space:]]+/ /g' -e 's/^[[:space:]]+//' -e 's/[[:space:]]+$//' \
    "${CMDLINE_TXT}"
fi

# Parallelize the two C++ builds based on the builder host, but cap concurrency
# at four jobs to avoid making qemu-user builds unnecessarily memory/CPU heavy.
DETECTED_CPUS="$(nproc 2>/dev/null || printf '1')"
case "$DETECTED_CPUS" in
  ''|*[!0-9]*) DETECTED_CPUS=1 ;;
esac
BUILD_JOBS="$DETECTED_CPUS"
[ "$BUILD_JOBS" -lt 1 ] && BUILD_JOBS=1
[ "$BUILD_JOBS" -gt 4 ] && BUILD_JOBS=4
printf 'Building pinned MMDVM-Host and DMRGateway inside armhf rootfs...\n'
printf 'Runtime compile parallelism: detected %s CPU(s), using -j%s (cap 4)\n' "$DETECTED_CPUS" "$BUILD_JOBS"
on_chroot <<EOF
set -e
rm -rf /tmp/ywd-m2-build
mkdir -p /tmp/ywd-m2-build

git clone --quiet '${MMDVM_HOST_REPO}' /tmp/ywd-m2-build/MMDVM-Host
git -C /tmp/ywd-m2-build/MMDVM-Host checkout --quiet --detach '${MMDVM_HOST_COMMIT}'
make -C /tmp/ywd-m2-build/MMDVM-Host -j${BUILD_JOBS}
install -m 0755 /tmp/ywd-m2-build/MMDVM-Host/MMDVM-Host /usr/local/bin/MMDVM-Host

git clone --quiet '${DMR_GATEWAY_REPO}' /tmp/ywd-m2-build/DMRGateway
git -C /tmp/ywd-m2-build/DMRGateway checkout --quiet --detach '${DMR_GATEWAY_COMMIT}'
make -C /tmp/ywd-m2-build/DMRGateway -j${BUILD_JOBS}
install -m 0755 /tmp/ywd-m2-build/DMRGateway/DMRGateway /usr/local/bin/DMRGateway
rm -rf /tmp/ywd-m2-build
EOF

# Keep a Git checkout in the image so the existing GitHub updater has a clean
# source tree to work from. The deployed runtime remains /opt/ywd-hotspot/app.
on_chroot <<EOF
set -e
rm -rf /opt/ywd-hotspot/repo
git clone --quiet --branch '${YWD_GIT_BRANCH}' --single-branch https://github.com/merberg-ai/ywd-hotspot.git /opt/ywd-hotspot/repo
git -C /opt/ywd-hotspot/repo checkout --quiet '${YWD_GIT_COMMIT}'
git -C /opt/ywd-hotspot/repo branch --set-upstream-to='origin/${YWD_GIT_BRANCH}' '${YWD_GIT_BRANCH}' >/dev/null 2>&1 || true
EOF

on_chroot <<EOF
set -e
chown -R root:root /opt/ywd-hotspot/app /opt/ywd-hotspot/repo
chown root:ywd-hotspot /etc/ywd-hotspot
chmod 0750 /etc/ywd-hotspot
chown root:ywd-hotspot /etc/ywd-hotspot/config.json
chmod 0640 /etc/ywd-hotspot/config.json
chown -R ywd-hotspot:ywd-hotspot /var/lib/ywd-hotspot/diagnostics
chown ywd-hotspot:ywd-hotspot /var/lib/ywd-hotspot /var/lib/ywd-hotspot/DMRIds.dat
chmod 0750 /var/lib/ywd-hotspot
chmod 0644 /var/lib/ywd-hotspot/DMRIds.dat
chmod 0700 /var/lib/ywd-hotspot/private /var/lib/ywd-hotspot/private/config-history
visudo -cf /etc/sudoers.d/ywd-hotspot >/dev/null
python3 /opt/ywd-hotspot/app/lib/generate-config.py
YWD_GIT_BRANCH='${YWD_GIT_BRANCH}' \
YWD_GIT_COMMIT='${YWD_GIT_COMMIT}' \
YWD_GIT_COMMIT_DATE='${YWD_GIT_COMMIT_DATE}' \
YWD_SOURCE_TYPE='os-image' \
YWD_SOURCE_STATE='packaged' \
YWD_UPDATE_CHANNEL='dev-os' \
python3 /opt/ywd-hotspot/app/lib/build_info.py write --source-dir /opt/ywd-hotspot/app >/dev/null
systemctl disable hciuart.service >/dev/null 2>&1 || true
systemctl enable ywd-activity.service ywd-dashboard.service ywd-dmrid-update.timer
systemctl disable ywd-mmdvmhost.service ywd-dmrgateway.service ywd-oled.service >/dev/null 2>&1 || true
# The M1.1 OS-level OLED remains authoritative until first-boot setup is added.
systemctl enable ywd-headless-oled.service
EOF

install -d -m 0755 "${ROOTFS_DIR}/var/log/journal" "${ROOTFS_DIR}/etc/systemd/journald.conf.d"
cat > "${ROOTFS_DIR}/etc/systemd/journald.conf.d/10-ywd-hotspot-persistent.conf" <<'EOF'
[Journal]
Storage=persistent
SystemMaxUse=100M
RuntimeMaxUse=50M
EOF

cat > "${ROOTFS_DIR}/etc/ywd-hotspot/m2-safety.txt" <<'EOF'
YWD-Hotspot OS M2 safety state

RF services are intentionally disabled at boot:
  ywd-mmdvmhost.service
  ywd-dmrgateway.service

BrandMeister networking is disabled in the placeholder configuration.
Configure a real callsign, DMR ID, frequency and Hotspot Security password
before explicitly enabling RF.
EOF

printf 'M2 runtime installation complete; RF remains disabled.\n'
