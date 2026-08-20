#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OS_DIR="$ROOT_DIR/os"
PIN_FILE="$OS_DIR/pi-gen/PI-GEN-COMMIT"
PI_GEN_DIR="$OS_DIR/.pi-gen"
WORK_DIR="${YWD_OS_WORK_DIR:-$OS_DIR/work/unified}"
DEPLOY_DIR="${YWD_OS_DEPLOY_DIR:-$OS_DIR/deploy}"
LOCAL_DIR="$OS_DIR/local"
LOCAL_WIFI="$LOCAL_DIR/provision.env"
DEV_KEY="$LOCAL_DIR/ywd-os-dev_ed25519"

HEADLESS_STAGE_SRC="$OS_DIR/pi-gen/stage2/10-ywd-headless"
HEADLESS_STAGE_DST="$PI_GEN_DIR/stage2/10-ywd-headless"
NETWORK_STAGE_SRC="$OS_DIR/pi-gen/stage2/15-ywd-network"
NETWORK_STAGE_DST="$PI_GEN_DIR/stage2/15-ywd-network"
RUNTIME_STAGE_SRC="$OS_DIR/pi-gen/stage2/20-ywd-runtime"
RUNTIME_STAGE_DST="$PI_GEN_DIR/stage2/20-ywd-runtime"
FIRSTBOOT_STAGE_SRC="$OS_DIR/pi-gen/stage2/25-ywd-firstboot"
FIRSTBOOT_STAGE_DST="$PI_GEN_DIR/stage2/25-ywd-firstboot"
POLISH_STAGE_SRC="$OS_DIR/pi-gen/stage2/27-ywd-polish"
POLISH_STAGE_DST="$PI_GEN_DIR/stage2/27-ywd-polish"

IMG_NAME="${YWD_IMG_NAME:-ywd-hotspot-os}"
OS_VERSION="${YWD_OS_VERSION:-M4.2-unified-dev}"
CHECKSUM_FILE="SHA256SUMS-YWD-HOTSPOT-OS"

TARGET_HOSTNAME="${YWD_TARGET_HOSTNAME:-ywd-hotspot}"
TIMEZONE_DEFAULT_VALUE="${YWD_TIMEZONE:-America/Los_Angeles}"
LOCALE_DEFAULT_VALUE="${YWD_LOCALE:-en_US.UTF-8}"
KEYBOARD_KEYMAP_VALUE="${YWD_KEYBOARD_KEYMAP:-us}"
KEYBOARD_LAYOUT_VALUE="${YWD_KEYBOARD_LAYOUT:-English (US)}"
WPA_COUNTRY_VALUE="${YWD_WIFI_COUNTRY:-US}"
ENABLE_SSH_VALUE="${YWD_ENABLE_SSH:-1}"
PUBKEY_ONLY_SSH_VALUE="${YWD_PUBKEY_ONLY_SSH:-1}"
RF_AUTOSTART_VALUE="${YWD_RF_AUTOSTART:-0}"

[[ -f "$PIN_FILE" ]] || { echo "ERROR: missing $PIN_FILE" >&2; exit 1; }
PI_GEN_COMMIT="$(tr -d '[:space:]' < "$PIN_FILE")"
[[ "$PI_GEN_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR: invalid pi-gen commit in $PIN_FILE" >&2; exit 1; }

for stage in "$HEADLESS_STAGE_SRC" "$NETWORK_STAGE_SRC" "$RUNTIME_STAGE_SRC" "$FIRSTBOOT_STAGE_SRC" "$POLISH_STAGE_SRC"; do
  [[ -d "$stage" ]] || { echo "ERROR: missing custom OS stage: $stage" >&2; exit 1; }
done

for required in \
  VERSION pins.env MANIFEST.txt \
  lib/oled.py lib/admin.py lib/admin_dispatch.sh lib/setup_admin.py lib/setup_entry.sh \
  lib/update_admin.py lib/update_runner.py lib/dashboard_update.py lib/oled_owner.sh \
  lib/branding/issue lib/branding/motd \
  lib/console/ywd-system-info.py lib/console/ywd-info-wrapper.sh lib/console/ywd-logs.sh \
  lib/console/ywd-env.sh lib/console/ywd-prompt.sh lib/console/ywd-motd.sh \
  web/index.html web/update.js web/update-progress.js web/instrumentation.js \
  systemd/ywd-dashboard.service systemd/ywd-setup.service systemd/ywd-update.service \
  sudoers/ywd-hotspot; do
  [[ -e "$ROOT_DIR/$required" ]] || { echo "ERROR: current application source missing: $required" >&2; exit 1; }
done

SOURCE_BRANCH="$(git -C "$ROOT_DIR" branch --show-current 2>/dev/null || true)"
SOURCE_COMMIT="$(git -C "$ROOT_DIR" rev-parse HEAD 2>/dev/null || true)"
SOURCE_COMMIT_SHORT="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || true)"
SOURCE_COMMIT_DATE="$(git -C "$ROOT_DIR" show -s --format=%cI HEAD 2>/dev/null || true)"
SOURCE_BRANCH="${SOURCE_BRANCH:-unknown}"
SOURCE_COMMIT="${SOURCE_COMMIT:-unknown}"
SOURCE_COMMIT_SHORT="${SOURCE_COMMIT_SHORT:-unknown}"
SOURCE_COMMIT_DATE="${SOURCE_COMMIT_DATE:-unknown}"
APP_VERSION="$(tr -d '\r\n' < "$ROOT_DIR/VERSION")"

if [[ "$SOURCE_BRANCH" == "unknown" || "$SOURCE_COMMIT" == "unknown" ]]; then
  echo 'ERROR: BUILD.sh must run from a Git checkout with a resolvable branch/commit.' >&2
  exit 1
fi
if ! git -C "$ROOT_DIR" diff --quiet --ignore-submodules -- || ! git -C "$ROOT_DIR" diff --cached --quiet --ignore-submodules --; then
  echo 'ERROR: tracked source changes are present. Commit/stash them before building a reproducible image.' >&2
  exit 1
fi

if [[ -n "${YWD_UPDATE_CHANNEL:-}" ]]; then
  UPDATE_CHANNEL="$YWD_UPDATE_CHANNEL"
else
  case "$SOURCE_BRANCH" in
    main|dev) UPDATE_CHANNEL="$SOURCE_BRANCH" ;;
    *) UPDATE_CHANNEL="dev" ;;
  esac
fi
case "$UPDATE_CHANNEL" in main|dev) ;; *) echo "ERROR: invalid update channel: $UPDATE_CHANNEL" >&2; exit 1 ;; esac

[[ "$TARGET_HOSTNAME" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]] || { echo "ERROR: invalid target hostname: $TARGET_HOSTNAME" >&2; exit 1; }
[[ "$WPA_COUNTRY_VALUE" =~ ^[A-Z]{2}$ ]] || { echo "ERROR: invalid Wi-Fi country: $WPA_COUNTRY_VALUE" >&2; exit 1; }
[[ "$ENABLE_SSH_VALUE" == "0" || "$ENABLE_SSH_VALUE" == "1" ]] || { echo 'ERROR: YWD_ENABLE_SSH must be 0 or 1' >&2; exit 1; }
[[ "$PUBKEY_ONLY_SSH_VALUE" == "1" ]] || { echo 'ERROR: YWD-Hotspot builder currently permits only public-key-only SSH' >&2; exit 1; }
[[ "$RF_AUTOSTART_VALUE" == "0" || "$RF_AUTOSTART_VALUE" == "1" ]] || { echo 'ERROR: YWD_RF_AUTOSTART must be 0 or 1' >&2; exit 1; }

printf '==================================================\n'
printf ' YWD-Hotspot OS Unified Image Builder\n'
printf '==================================================\n\n'
printf 'Application:        %s\n' "$APP_VERSION"
printf 'Source repo:        merberg-ai/ywd-hotspot\n'
printf 'Source branch:      %s\n' "$SOURCE_BRANCH"
printf 'Source commit:      %s\n' "$SOURCE_COMMIT_SHORT"
printf 'Update channel:     %s\n' "$UPDATE_CHANNEL"
printf 'OS identity:        %s\n' "$OS_VERSION"
printf 'Hostname:           %s (.local)\n' "$TARGET_HOSTNAME"
printf 'Timezone:           %s\n' "$TIMEZONE_DEFAULT_VALUE"
printf 'Locale:             %s\n' "$LOCALE_DEFAULT_VALUE"
printf 'Keyboard:           %s / %s\n' "$KEYBOARD_KEYMAP_VALUE" "$KEYBOARD_LAYOUT_VALUE"
printf 'Wi-Fi country:      %s\n' "$WPA_COUNTRY_VALUE"
printf 'SSH:                 %s\n' "$([[ "$ENABLE_SSH_VALUE" == "1" ]] && printf 'enabled / key-only' || printf 'disabled')"
printf 'RF autostart:       %s\n' "$([[ "$RF_AUTOSTART_VALUE" == "1" ]] && printf 'ON' || printf 'OFF')"
printf 'Target:             Raspberry Pi Zero W / Zero WH\n'
printf 'Architecture:       armhf\n'
printf 'Base:               Raspberry Pi OS Lite / trixie\n'
printf 'Image:              %s\n' "$IMG_NAME"
printf 'pi-gen commit:      %s\n' "$PI_GEN_COMMIT"
printf 'Work directory:     %s\n' "$WORK_DIR"
printf 'Deploy directory:   %s\n\n' "$DEPLOY_DIR"
printf 'Safety model:\n'
printf '  - current root application is packaged verbatim\n'
printf '  - RF startup follows the validated hotspot profile and is warned when enabled\n'
printf '  - SSH, hostname, locale, timezone and regulatory domain follow the validated System / OS profile\n'
printf '  - ywd-headless-oled remains the sole SSD1306 owner\n'
printf '  - OLED/console presentation is injected from current canonical app source\n'
printf '  - normal GitHub app updates remain available after imaging\n\n'

mkdir -p "$OS_DIR" "$DEPLOY_DIR" "$LOCAL_DIR"
chmod 0700 "$LOCAL_DIR"

if [[ ! -d "$PI_GEN_DIR/.git" ]]; then
  echo '[1/8] Cloning upstream pi-gen...'
  git clone https://github.com/RPi-Distro/pi-gen.git "$PI_GEN_DIR"
else
  echo '[1/8] Reusing local pi-gen checkout...'
fi

echo '[2/8] Fetching and checking out pinned pi-gen revision...'
git -C "$PI_GEN_DIR" fetch --quiet origin master
git -C "$PI_GEN_DIR" checkout --quiet --detach "$PI_GEN_COMMIT"
git -C "$PI_GEN_DIR" reset --hard --quiet "$PI_GEN_COMMIT"
git -C "$PI_GEN_DIR" clean -fdx --quiet
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"

for pair in \
  "$HEADLESS_STAGE_SRC|$HEADLESS_STAGE_DST" \
  "$NETWORK_STAGE_SRC|$NETWORK_STAGE_DST" \
  "$RUNTIME_STAGE_SRC|$RUNTIME_STAGE_DST" \
  "$FIRSTBOOT_STAGE_SRC|$FIRSTBOOT_STAGE_DST" \
  "$POLISH_STAGE_SRC|$POLISH_STAGE_DST"; do
  src="${pair%%|*}"
  dst="${pair#*|}"
  rm -rf "$dst"
  mkdir -p "$dst"
  cp -a "$src/." "$dst/"
done

# Replace historical OS copies with the current canonical application assets.
# This is intentionally done after staging so a new image cannot silently ship
# an old OLED renderer or old console branding while the root app has moved on.
install -m 0755 "$ROOT_DIR/lib/oled.py" "$HEADLESS_STAGE_DST/files/ywd-headless-oled.py"
install -m 0644 "$ROOT_DIR/lib/branding/issue" "$POLISH_STAGE_DST/files/issue"
install -m 0644 "$ROOT_DIR/lib/branding/motd" "$POLISH_STAGE_DST/files/motd"
install -m 0755 "$ROOT_DIR/lib/console/ywd-system-info.py" "$POLISH_STAGE_DST/files/ywd-system-info.py"
install -m 0755 "$ROOT_DIR/lib/console/ywd-info-wrapper.sh" "$POLISH_STAGE_DST/files/ywd-info-wrapper.sh"
install -m 0755 "$ROOT_DIR/lib/console/ywd-logs.sh" "$POLISH_STAGE_DST/files/ywd-logs.sh"
install -m 0644 "$ROOT_DIR/lib/console/ywd-env.sh" "$POLISH_STAGE_DST/files/ywd-env.sh"
install -m 0644 "$ROOT_DIR/lib/console/ywd-prompt.sh" "$POLISH_STAGE_DST/files/ywd-prompt.sh"
install -m 0644 "$ROOT_DIR/lib/console/ywd-motd.sh" "$POLISH_STAGE_DST/files/ywd-motd.sh"

chmod +x \
  "$HEADLESS_STAGE_DST/01-run.sh" \
  "$HEADLESS_STAGE_DST/files/ywd-headless-oled.py" \
  "$HEADLESS_STAGE_DST/files/ywd-headless-provision.sh" \
  "$NETWORK_STAGE_DST/01-run.sh" \
  "$NETWORK_STAGE_DST/files/ywd-network-manager.py" \
  "$RUNTIME_STAGE_DST/01-run.sh" \
  "$FIRSTBOOT_STAGE_DST/01-run.sh" \
  "$POLISH_STAGE_DST/01-run.sh" \
  "$POLISH_STAGE_DST/files/ywd-system-info.py" \
  "$POLISH_STAGE_DST/files/ywd-info-wrapper.sh" \
  "$POLISH_STAGE_DST/files/ywd-logs.sh"

RUNTIME_APP="$RUNTIME_STAGE_DST/files/app"
rm -rf "$RUNTIME_APP"
mkdir -p "$RUNTIME_APP"
for item in \
  bin lib web systemd sudoers lab \
  INSTALL.sh INSTALL-core.sh UPDATE.sh UPDATE-core.sh UNINSTALL.sh \
  GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh \
  VERSION pins.env README.md MANIFEST.txt; do
  [[ -e "$ROOT_DIR/$item" ]] || { echo "ERROR: runtime payload source missing: $item" >&2; exit 1; }
  cp -a "$ROOT_DIR/$item" "$RUNTIME_APP/"
done
mkdir -p "$RUNTIME_APP/assets/branding"
install -m 0644 "$ROOT_DIR/assets/branding/ywd-hotspot-badge-256.webp" "$RUNTIME_APP/assets/branding/ywd-hotspot-badge-256.webp"

{
  printf 'YWD_GIT_BRANCH=%q\n' "$SOURCE_BRANCH"
  printf 'YWD_GIT_COMMIT=%q\n' "$SOURCE_COMMIT"
  printf 'YWD_GIT_COMMIT_DATE=%q\n' "$SOURCE_COMMIT_DATE"
  printf 'YWD_UPDATE_CHANNEL=%q\n' "$UPDATE_CHANNEL"
  printf 'YWD_OS_VERSION=%q\n' "$OS_VERSION"
} > "$RUNTIME_STAGE_DST/files/build.env"
chmod 0644 "$RUNTIME_STAGE_DST/files/build.env"

{
  printf 'YWD_OS_VERSION=%q\n' "$OS_VERSION"
  printf 'YWD_SOURCE_BRANCH=%q\n' "$SOURCE_BRANCH"
  printf 'YWD_SOURCE_COMMIT=%q\n' "$SOURCE_COMMIT"
  printf 'YWD_PI_GEN_COMMIT=%q\n' "$PI_GEN_COMMIT"
} > "$POLISH_STAGE_DST/files/build-polish.env"
chmod 0644 "$POLISH_STAGE_DST/files/build-polish.env"

if [[ -f "$LOCAL_WIFI" ]]; then
  # shellcheck disable=SC1090
  source "$LOCAL_WIFI"
  if [[ -n "${WIFI_SSID:-}" ]]; then
    install -m 0600 "$LOCAL_WIFI" "$HEADLESS_STAGE_DST/files/provision.env"
    printf '[INFO] Initial Wi-Fi provisioning: %s\n' "$WIFI_SSID"
  else
    printf '[INFO] Provision file has no SSID; setup AP will handle Wi-Fi.\n'
  fi
else
  printf '[INFO] No build-time Wi-Fi provisioning. Setup AP will handle first connection.\n'
fi

echo '[3/8] Verifying staged unified payload...'
required_payload=(
  "$HEADLESS_STAGE_DST/files/ywd-headless-oled.py"
  "$NETWORK_STAGE_DST/00-packages"
  "$NETWORK_STAGE_DST/01-run.sh"
  "$NETWORK_STAGE_DST/files/ywd-network-manager.py"
  "$NETWORK_STAGE_DST/files/ywd-network-manager.service"
  "$RUNTIME_STAGE_DST/01-run.sh"
  "$RUNTIME_STAGE_DST/files/build.env"
  "$FIRSTBOOT_STAGE_DST/00-packages"
  "$FIRSTBOOT_STAGE_DST/01-run.sh"
  "$POLISH_STAGE_DST/01-run.sh"
  "$POLISH_STAGE_DST/files/build-polish.env"
  "$POLISH_STAGE_DST/files/ywd-system-info.py"
  "$RUNTIME_APP/pins.env"
  "$RUNTIME_APP/VERSION"
  "$RUNTIME_APP/lib/dashboard.py"
  "$RUNTIME_APP/lib/config_model.py"
  "$RUNTIME_APP/lib/oled.py"
  "$RUNTIME_APP/lib/oled_owner.sh"
  "$RUNTIME_APP/lib/setup_server.py"
  "$RUNTIME_APP/lib/setup_admin.py"
  "$RUNTIME_APP/lib/setup_entry.sh"
  "$RUNTIME_APP/lib/admin_dispatch.sh"
  "$RUNTIME_APP/lib/update_admin.py"
  "$RUNTIME_APP/lib/update_runner.py"
  "$RUNTIME_APP/lib/dashboard_update.py"
  "$RUNTIME_APP/systemd/ywd-dashboard.service"
  "$RUNTIME_APP/systemd/ywd-setup.service"
  "$RUNTIME_APP/systemd/ywd-update.service"
  "$RUNTIME_APP/sudoers/ywd-hotspot"
  "$RUNTIME_APP/web/index.html"
  "$RUNTIME_APP/web/update.js"
  "$RUNTIME_APP/web/update-progress.js"
  "$RUNTIME_APP/web/instrumentation.js"
  "$RUNTIME_APP/assets/branding/ywd-hotspot-badge-256.webp"
)
for f in "${required_payload[@]}"; do
  [[ -f "$f" ]] || { echo "ERROR: staged unified payload is incomplete: $f" >&2; exit 1; }
done

python3 -m py_compile \
  "$HEADLESS_STAGE_DST/files/ywd-headless-oled.py" \
  "$NETWORK_STAGE_DST/files/ywd-network-manager.py" \
  "$RUNTIME_APP"/lib/*.py \
  "$RUNTIME_APP/lib/console/ywd-system-info.py" \
  "$POLISH_STAGE_DST/files/ywd-system-info.py"

bash -n \
  "$RUNTIME_APP/INSTALL.sh" "$RUNTIME_APP/UPDATE.sh" "$RUNTIME_APP/GITHUB-UPDATE.sh" \
  "$RUNTIME_APP/lib/setup_entry.sh" "$RUNTIME_APP/lib/admin_dispatch.sh" "$RUNTIME_APP/lib/oled_owner.sh" \
  "$FIRSTBOOT_STAGE_DST/01-run.sh" "$POLISH_STAGE_DST/01-run.sh" \
  "$POLISH_STAGE_DST/files/ywd-info-wrapper.sh" "$POLISH_STAGE_DST/files/ywd-logs.sh" \
  "$POLISH_STAGE_DST/files/ywd-env.sh" "$POLISH_STAGE_DST/files/ywd-prompt.sh" "$POLISH_STAGE_DST/files/ywd-motd.sh"

if command -v node >/dev/null 2>&1; then
  for js in "$RUNTIME_APP"/web/*.js; do node --check "$js" >/dev/null; done
  printf '[OK] JavaScript syntax preflight passed.\n'
else
  printf '[INFO] node not installed; skipping optional JavaScript syntax preflight.\n'
fi
printf '[OK] Unified payload staged and syntax preflight passed; app version %s\n' "$APP_VERSION"

command -v ssh-keygen >/dev/null 2>&1 || { echo 'ERROR: ssh-keygen is required (install openssh-client).' >&2; exit 1; }
if [[ ! -f "$DEV_KEY" ]]; then
  echo '[4/8] Generating local OS development SSH key...'
  ssh-keygen -q -t ed25519 -N '' -C 'ywd-hotspot-os-dev' -f "$DEV_KEY"
  chmod 0600 "$DEV_KEY"
  chmod 0644 "$DEV_KEY.pub"
else
  echo '[4/8] Reusing local OS development SSH key...'
fi
PUBKEY="$(cat "$DEV_KEY.pub")"
DEV_PASS="$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"

cat > "$PI_GEN_DIR/config" <<EOF
IMG_NAME='$IMG_NAME'
PI_GEN_RELEASE='YWD-Hotspot OS unified development image'
RELEASE='trixie'
ARCH='armhf'
TARGET_HOSTNAME='$TARGET_HOSTNAME'
LOCALE_DEFAULT='$LOCALE_DEFAULT_VALUE'
KEYBOARD_KEYMAP='$KEYBOARD_KEYMAP_VALUE'
KEYBOARD_LAYOUT='$KEYBOARD_LAYOUT_VALUE'
TIMEZONE_DEFAULT='$TIMEZONE_DEFAULT_VALUE'
WPA_COUNTRY='$WPA_COUNTRY_VALUE'
ENABLE_SSH=$ENABLE_SSH_VALUE
PUBKEY_ONLY_SSH=$PUBKEY_ONLY_SSH_VALUE
PUBKEY_SSH_FIRST_USER='$PUBKEY'
FIRST_USER_NAME='ywd'
FIRST_USER_PASS='$DEV_PASS'
DISABLE_FIRST_BOOT_USER_RENAME=1
PASSWORDLESS_SUDO=1
DEPLOY_COMPRESSION='xz'
COMPRESSION_LEVEL=6
WORK_DIR='$WORK_DIR'
DEPLOY_DIR='$DEPLOY_DIR'
STAGE_LIST="\$BASE_DIR/stage0 \$BASE_DIR/stage1 \$BASE_DIR/stage2"
EOF
chmod 0600 "$PI_GEN_DIR/config"

find "$DEPLOY_DIR" -maxdepth 1 -type f -name "*${IMG_NAME}*" -delete
rm -f "$DEPLOY_DIR/$CHECKSUM_FILE"

echo '[5/8] Running builder doctor...'
bash "$OS_DIR/builder/DOCTOR.sh"

echo '[6/8] Building Raspberry Pi OS Lite + current YWD-Hotspot source...'
echo '      Runtime compilation auto-detects CPUs and is capped at four jobs.'
if [[ "$EUID" -eq 0 ]]; then
  (cd "$PI_GEN_DIR" && ./build.sh)
else
  (cd "$PI_GEN_DIR" && sudo ./build.sh)
fi

echo '[7/8] Generating SHA-256 checksum and verifying compressed image...'
(
  cd "$DEPLOY_DIR"
  shopt -s nullglob
  files=( *"$IMG_NAME"*.img *"$IMG_NAME"*.img.xz *"$IMG_NAME"*.img.gz *"$IMG_NAME"*.zip )
  (( ${#files[@]} > 0 )) || { echo 'ERROR: pi-gen completed but no YWD-Hotspot OS deploy image was found.' >&2; exit 1; }
  sha256sum "${files[@]}" > "$CHECKSUM_FILE"
)
IMAGE_XZ="$(find "$DEPLOY_DIR" -maxdepth 1 -type f -name "*${IMG_NAME}*.img.xz" -print -quit)"
if [[ -n "$IMAGE_XZ" ]]; then
  xz -t "$IMAGE_XZ"
  echo '[OK] XZ integrity test passed.'
fi

echo '[8/8] Build artifacts ready.'
printf '\n==================================================\n YWD-HOTSPOT OS BUILD COMPLETE\n==================================================\n'
printf 'Application: %s\n' "$APP_VERSION"
printf 'Source:      %s @ %s\n' "$SOURCE_BRANCH" "$SOURCE_COMMIT_SHORT"
printf 'OS:          %s\n' "$OS_VERSION"
printf 'Hostname:    %s.local\n' "$TARGET_HOSTNAME"
printf 'Update:      %s\n' "$UPDATE_CHANNEL"
printf 'RF autostart:%s\n' "$([[ "$RF_AUTOSTART_VALUE" == "1" ]] && printf ' ON' || printf ' OFF')"
find "$DEPLOY_DIR" -maxdepth 1 -type f \( -name "*${IMG_NAME}*" -o -name "$CHECKSUM_FILE" \) -printf '  %f\n' | sort
printf '\nFirst boot flow when setup is still required:\n'
printf '  1. No Wi-Fi -> open YWD-Hotspot-xxxx AP -> http://10.42.0.1/\n'
printf '  2. Wi-Fi handoff -> OLED displays six-digit setup code\n'
printf '  3. Browse https://%s.local:8443/\n' "$TARGET_HOSTNAME"
printf '  4. Finish wizard -> normal dashboard at http://%s.local:8080/\n' "$TARGET_HOSTNAME"
if [[ "$ENABLE_SSH_VALUE" == "1" ]]; then
  printf '\nSSH: ssh -i %s ywd@%s.local\n' "$DEV_KEY" "$TARGET_HOSTNAME"
else
  printf '\nSSH: disabled by System / OS profile (authorized client key is still baked for later enablement).\n'
fi
printf 'RF autostart is %s for this image profile.\n' "$([[ "$RF_AUTOSTART_VALUE" == "1" ]] && printf 'ENABLED' || printf 'disabled')"
