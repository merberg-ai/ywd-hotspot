#!/bin/bash -e

THIS_STAGE="$(pwd -P)"
APP_SRC="${THIS_STAGE}/files/app"
BUILD_ENV="${THIS_STAGE}/files/build.env"
CACHE_STAGE="${THIS_STAGE}/files/runtime-cache"
CACHE_ROOTFS="${ROOTFS_DIR}/var/cache/ywd-hotspot/runtime-build"

sync_runtime_cache_back() {
  if [ -d "${CACHE_ROOTFS}" ]; then
    rm -rf "${CACHE_STAGE}"
    mkdir -p "${CACHE_STAGE}"
    cp -a "${CACHE_ROOTFS}/." "${CACHE_STAGE}/" 2>/dev/null || true
    chmod -R a+rX "${CACHE_STAGE}" 2>/dev/null || true
    if [ -n "${SUDO_UID:-}" ] && [ -n "${SUDO_GID:-}" ]; then
      chown -R "${SUDO_UID}:${SUDO_GID}" "${CACHE_STAGE}" 2>/dev/null || true
    fi
  fi
}
trap sync_runtime_cache_back EXIT

printf 'YWD runtime stage directory: %s\n' "$THIS_STAGE"
printf 'YWD runtime app payload:    %s\n' "$APP_SRC"

if [ ! -d "${APP_SRC}" ] || [ ! -f "${APP_SRC}/pins.env" ]; then
  echo "ERROR: runtime app payload was not injected by os/builder/BUILD.sh" >&2
  exit 1
fi
if [ ! -f "${BUILD_ENV}" ]; then
  echo "ERROR: build metadata was not injected by os/builder/BUILD.sh" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${APP_SRC}/pins.env"
# shellcheck disable=SC1090
source "${BUILD_ENV}"

: "${YWD_GIT_BRANCH:?missing YWD_GIT_BRANCH}"
: "${YWD_GIT_COMMIT:?missing YWD_GIT_COMMIT}"
: "${YWD_GIT_COMMIT_DATE:?missing YWD_GIT_COMMIT_DATE}"
: "${YWD_UPDATE_CHANNEL:=dev}"
: "${YWD_OS_VERSION:=M4.2-unified-dev}"
: "${YWD_RUNTIME_CACHE_BYPASS:=0}"

printf 'Installing current YWD-Hotspot runtime payload...\n'

on_chroot <<'EOF'
if ! id ywd-hotspot >/dev/null 2>&1; then
  useradd --system --home /var/lib/ywd-hotspot --create-home --shell /usr/sbin/nologin ywd-hotspot
fi
for g in dialout i2c systemd-journal; do
  getent group "$g" >/dev/null 2>&1 && usermod -a -G "$g" ywd-hotspot || true
done
EOF

install -d -m 0755 "${ROOTFS_DIR}/opt/ywd-hotspot/app" "${ROOTFS_DIR}/usr/local/libexec" "${ROOTFS_DIR}/usr/local/sbin"
install -d -m 0750 "${ROOTFS_DIR}/etc/ywd-hotspot"
install -d -m 0750 "${ROOTFS_DIR}/var/lib/ywd-hotspot" "${ROOTFS_DIR}/var/lib/ywd-hotspot/diagnostics"
install -d -m 0700 "${ROOTFS_DIR}/var/lib/ywd-hotspot/private" "${ROOTFS_DIR}/var/lib/ywd-hotspot/private/config-history"
install -d -m 0755 "${CACHE_ROOTFS}"
cp -a "${APP_SRC}/." "${ROOTFS_DIR}/opt/ywd-hotspot/app/"
if [ -d "${CACHE_STAGE}" ]; then
  cp -a "${CACHE_STAGE}/." "${CACHE_ROOTFS}/" 2>/dev/null || true
fi

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
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/lib/admin_dispatch.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/lib/setup_entry.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/lib/oled_owner.sh" \
  "${ROOTFS_DIR}/opt/ywd-hotspot/app/lab/mmdvm-diag.sh"

install -m 0755 "${APP_SRC}/bin/ywd-hotspotctl" "${ROOTFS_DIR}/usr/local/sbin/ywd-hotspotctl"
install -m 0755 "${APP_SRC}/lib/admin.py" "${ROOTFS_DIR}/usr/local/libexec/ywd-hotspot-admin-core"
install -m 0755 "${APP_SRC}/lib/setup_admin.py" "${ROOTFS_DIR}/usr/local/libexec/ywd-hotspot-setup-admin"
install -m 0755 "${APP_SRC}/lib/update_admin.py" "${ROOTFS_DIR}/usr/local/libexec/ywd-hotspot-update-admin"
install -m 0755 "${APP_SRC}/lib/update_runner.py" "${ROOTFS_DIR}/usr/local/libexec/ywd-update-runner"
install -m 0755 "${APP_SRC}/lib/admin_dispatch.sh" "${ROOTFS_DIR}/usr/local/libexec/ywd-hotspot-admin"
install -m 0440 "${APP_SRC}/sudoers/ywd-hotspot" "${ROOTFS_DIR}/etc/sudoers.d/ywd-hotspot"

for unit in "${APP_SRC}"/systemd/*.service "${APP_SRC}"/systemd/*.timer; do
  install -m 0644 "$unit" "${ROOTFS_DIR}/etc/systemd/system/$(basename "$unit")"
done

# Generate the factory placeholder using the current canonical configuration
# model so future schema additions do not require another hand-maintained JSON
# copy in the image builder.
on_chroot <<'EOF'
python3 - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, '/opt/ywd-hotspot/app/lib')
import config_model
c = config_model.defaults()
c['station']['callsign'] = 'NOCALL'
c['station']['base_dmr_id'] = '00000'
c['station']['essid'] = '01'
c['brandmeister']['enabled'] = False
c = config_model.normalize(c)
Path('/etc/ywd-hotspot/config.json').write_text(json.dumps(c, indent=2) + '\n')
PY
EOF

printf '%s\n' "$YWD_UPDATE_CHANNEL" > "${ROOTFS_DIR}/etc/ywd-hotspot/update-channel"
printf '%s\n' "$YWD_OS_VERSION" > "${ROOTFS_DIR}/etc/ywd-hotspot/os-version"
touch "${ROOTFS_DIR}/var/lib/ywd-hotspot/DMRIds.dat"

# Pi Zero W GPIO14/15 UART for the MMDVM HAT. Bluetooth is disabled so
# /dev/serial0 maps to PL011 /dev/ttyAMA0.
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

DETECTED_CPUS="$(nproc 2>/dev/null || printf '1')"
case "$DETECTED_CPUS" in ''|*[!0-9]*) DETECTED_CPUS=1 ;; esac
BUILD_JOBS="$DETECTED_CPUS"
[ "$BUILD_JOBS" -lt 1 ] && BUILD_JOBS=1
[ "$BUILD_JOBS" -gt 4 ] && BUILD_JOBS=4
printf 'Installing canonical MMDVM-Host + DMRGateway inside armhf rootfs...\n'
printf 'MMDVM-Host source: %s @ %s + YWD patch API %s\n' "$MMDVM_HOST_REPO" "$MMDVM_HOST_COMMIT" "$MMDVM_YWD_PATCH_API"
printf 'MMDVM patch SHA256: %s\n' "$MMDVM_YWD_PATCH_SHA256"
printf 'Runtime compile parallelism: detected %s CPU(s), using -j%s (cap 4)\n' "$DETECTED_CPUS" "$BUILD_JOBS"
on_chroot <<EOF
set -e
YWD_RUNTIME_BUILD_CACHE=/var/cache/ywd-hotspot/runtime-build \
YWD_RUNTIME_CACHE_BYPASS='${YWD_RUNTIME_CACHE_BYPASS}' \
YWD_BUILD_JOBS='${BUILD_JOBS}' \
python3 /opt/ywd-hotspot/app/lib/runtime_build.py install
EOF

# Keep a normal full-ref Git checkout in the image. The deployed runtime stays
# /opt/ywd-hotspot/app; future app updates continue to use the managed checkout.
on_chroot <<EOF
set -e
rm -rf /opt/ywd-hotspot/repo
git clone --quiet https://github.com/merberg-ai/ywd-hotspot.git /opt/ywd-hotspot/repo
git -C /opt/ywd-hotspot/repo config --unset-all remote.origin.fetch >/dev/null 2>&1 || true
git -C /opt/ywd-hotspot/repo config --add remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
git -C /opt/ywd-hotspot/repo fetch --quiet --prune origin
git -C /opt/ywd-hotspot/repo checkout --quiet -B '${YWD_GIT_BRANCH}' '${YWD_GIT_COMMIT}'
if git -C /opt/ywd-hotspot/repo show-ref --verify --quiet 'refs/remotes/origin/${YWD_GIT_BRANCH}'; then
  git -C /opt/ywd-hotspot/repo branch --set-upstream-to='origin/${YWD_GIT_BRANCH}' '${YWD_GIT_BRANCH}' >/dev/null 2>&1 || true
fi
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
YWD_UPDATE_CHANNEL='${YWD_UPDATE_CHANNEL}' \
python3 /opt/ywd-hotspot/app/lib/build_info.py write --source-dir /opt/ywd-hotspot/app >/dev/null
systemctl disable hciuart.service >/dev/null 2>&1 || true
systemctl enable ywd-activity.service ywd-dashboard.service ywd-dmrid-update.timer
systemctl disable ywd-mmdvmhost.service ywd-dmrgateway.service ywd-oled.service >/dev/null 2>&1 || true
systemctl enable ywd-headless-oled.service
EOF

install -d -m 0755 "${ROOTFS_DIR}/var/log/journal" "${ROOTFS_DIR}/etc/systemd/journald.conf.d"
cat > "${ROOTFS_DIR}/etc/systemd/journald.conf.d/10-ywd-hotspot-persistent.conf" <<'EOF'
[Journal]
Storage=persistent
SystemMaxUse=100M
RuntimeMaxUse=50M
EOF

cat > "${ROOTFS_DIR}/etc/ywd-hotspot/image-safety.txt" <<EOF
YWD-Hotspot OS unified image safety state

Application: $(tr -d '\r\n' < "${APP_SRC}/VERSION")
OS: ${YWD_OS_VERSION}
Source: ${YWD_GIT_BRANCH} @ ${YWD_GIT_COMMIT}
MMDVM-Host: ${MMDVM_HOST_COMMIT} + YWD voice tap patch API ${MMDVM_YWD_PATCH_API}
MMDVM patch SHA256: ${MMDVM_YWD_PATCH_SHA256}

RF services are disabled at image build time. The first-boot safety gate and
secure setup wizard/factory restore must complete before RF follows the selected
autostart policy.
EOF

printf 'Current YWD-Hotspot runtime installation complete; canonical patched MMDVM installed; RF remains disabled.\n'
