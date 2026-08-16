#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OS_DIR="$ROOT_DIR/os"
PIN_FILE="$OS_DIR/pi-gen/PI-GEN-COMMIT"
PI_GEN_DIR="$OS_DIR/.pi-gen"
WORK_DIR="$OS_DIR/work/m4-1-polish"
DEPLOY_DIR="$OS_DIR/deploy"
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

IMG_NAME='ywd-hotspot-os-m4-1-polish'
OS_VERSION='M4.1-polish-dev'
CHECKSUM_FILE='SHA256SUMS-M4.1'

[[ -f "$PIN_FILE" ]] || { echo "ERROR: missing $PIN_FILE" >&2; exit 1; }
PI_GEN_COMMIT="$(tr -d '[:space:]' < "$PIN_FILE")"
[[ "$PI_GEN_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "ERROR: invalid pi-gen commit in $PIN_FILE" >&2; exit 1; }

for stage in "$HEADLESS_STAGE_SRC" "$NETWORK_STAGE_SRC" "$RUNTIME_STAGE_SRC" "$FIRSTBOOT_STAGE_SRC" "$POLISH_STAGE_SRC"; do
  [[ -d "$stage" ]] || { echo "ERROR: missing custom OS stage: $stage" >&2; exit 1; }
done

SOURCE_BRANCH="$(git -C "$ROOT_DIR" branch --show-current 2>/dev/null || true)"
SOURCE_COMMIT="$(git -C "$ROOT_DIR" rev-parse HEAD 2>/dev/null || true)"
SOURCE_COMMIT_SHORT="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || true)"
SOURCE_COMMIT_DATE="$(git -C "$ROOT_DIR" show -s --format=%cI HEAD 2>/dev/null || true)"
SOURCE_BRANCH="${SOURCE_BRANCH:-unknown}"
SOURCE_COMMIT="${SOURCE_COMMIT:-unknown}"
SOURCE_COMMIT_SHORT="${SOURCE_COMMIT_SHORT:-unknown}"
SOURCE_COMMIT_DATE="${SOURCE_COMMIT_DATE:-unknown}"

printf '==================================================\n'
printf ' YWD-Hotspot OS Image Builder - Milestone 4.1\n'
printf ' OS Identity + Console/SSH Polish\n'
printf '==================================================\n\n'
printf 'Source repo:        merberg-ai/ywd-hotspot\n'
printf 'Source branch:      %s\n' "$SOURCE_BRANCH"
printf 'Source commit:      %s\n' "$SOURCE_COMMIT_SHORT"
printf 'Target:             Raspberry Pi Zero W / Zero WH\n'
printf 'Architecture:       armhf\n'
printf 'Base:               Raspberry Pi OS Lite / trixie\n'
printf 'Image:              %s\n' "$IMG_NAME"
printf 'pi-gen commit:      %s\n' "$PI_GEN_COMMIT"
printf 'Work directory:     %s\n' "$WORK_DIR"
printf 'Deploy directory:   %s\n\n' "$DEPLOY_DIR"
printf 'M4.1 includes:\n'
printf '  - all M4 secure first-boot wizard + shutdown OLED behavior\n'
printf '  - branded /etc/issue and YWD interactive login MOTD\n'
printf '  - live safe status with setup/RF/network/system state\n'
printf '  - ywd-info, ywd-services, ywd-build, ywd-logs commands\n'
printf '  - Git branch/commit/pi-gen/MMDVM/DMRGateway provenance\n'
printf '  - restrained YWD shell prompt and useful environment helpers\n'
printf '  - stock MOTD clutter suppressed without affecting noninteractive SSH\n'
printf '\nSAFETY: no secrets are printed; RF behavior is unchanged from M4.\n\n'

mkdir -p "$OS_DIR" "$WORK_DIR" "$DEPLOY_DIR" "$LOCAL_DIR"
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
    printf '[INFO] Initial WiFi provisioning: %s\n' "$WIFI_SSID"
  else
    printf '[INFO] Provision file has no SSID; M3 open setup AP will handle WiFi.\n'
  fi
else
  printf '[INFO] No build-time WiFi provisioning. M3 will expose the open setup AP first.\n'
fi

echo '[3/8] Verifying injected M4.1 payload...'
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
  "$POLISH_STAGE_DST/files/ywd-info-wrapper.sh"
  "$POLISH_STAGE_DST/files/ywd-logs.sh"
  "$POLISH_STAGE_DST/files/issue"
  "$POLISH_STAGE_DST/files/ywd-env.sh"
  "$POLISH_STAGE_DST/files/ywd-prompt.sh"
  "$POLISH_STAGE_DST/files/ywd-motd.sh"
  "$RUNTIME_APP/pins.env"
  "$RUNTIME_APP/VERSION"
  "$RUNTIME_APP/lib/dashboard.py"
  "$RUNTIME_APP/lib/setup_server.py"
  "$RUNTIME_APP/lib/setup_admin.py"
  "$RUNTIME_APP/lib/setup_entry.sh"
  "$RUNTIME_APP/lib/admin_dispatch.sh"
  "$RUNTIME_APP/lib/generate-config.py"
  "$RUNTIME_APP/systemd/ywd-dashboard.service"
  "$RUNTIME_APP/systemd/ywd-setup.service"
  "$RUNTIME_APP/sudoers/ywd-hotspot"
  "$RUNTIME_APP/web/index.html"
  "$RUNTIME_APP/assets/branding/ywd-hotspot-badge-256.webp"
)
for f in "${required_payload[@]}"; do
  [[ -f "$f" ]] || { echo "ERROR: injected M4.1 payload is incomplete: $f" >&2; exit 1; }
done

python3 -m py_compile \
  "$HEADLESS_STAGE_DST/files/ywd-headless-oled.py" \
  "$NETWORK_STAGE_DST/files/ywd-network-manager.py" \
  "$RUNTIME_APP/lib/dashboard.py" \
  "$RUNTIME_APP/lib/setup_server.py" \
  "$RUNTIME_APP/lib/setup_admin.py" \
  "$POLISH_STAGE_DST/files/ywd-system-info.py"

bash -n \
  "$RUNTIME_APP/lib/setup_entry.sh" \
  "$RUNTIME_APP/lib/admin_dispatch.sh" \
  "$FIRSTBOOT_STAGE_DST/01-run.sh" \
  "$POLISH_STAGE_DST/01-run.sh" \
  "$POLISH_STAGE_DST/files/ywd-info-wrapper.sh" \
  "$POLISH_STAGE_DST/files/ywd-logs.sh" \
  "$POLISH_STAGE_DST/files/ywd-env.sh" \
  "$POLISH_STAGE_DST/files/ywd-prompt.sh" \
  "$POLISH_STAGE_DST/files/ywd-motd.sh"
printf '[OK] M4.1 payload staged and syntax preflight passed; app version %s\n' "$(tr -d '\r\n' < "$RUNTIME_APP/VERSION")"

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
PI_GEN_RELEASE='YWD-Hotspot OS M4.1 console polish development image'
RELEASE='trixie'
ARCH='armhf'
TARGET_HOSTNAME='ywd-hotspot'
LOCALE_DEFAULT='en_US.UTF-8'
KEYBOARD_KEYMAP='us'
KEYBOARD_LAYOUT='English (US)'
TIMEZONE_DEFAULT='America/Los_Angeles'
WPA_COUNTRY='US'
ENABLE_SSH=1
PUBKEY_ONLY_SSH=1
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

echo '[6/8] Building Raspberry Pi OS Lite + YWD-Hotspot M4.1...'
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
  (( ${#files[@]} > 0 )) || { echo 'ERROR: pi-gen completed but no M4.1 deploy image was found.' >&2; exit 1; }
  sha256sum "${files[@]}" > "$CHECKSUM_FILE"
)
M41_XZ="$(find "$DEPLOY_DIR" -maxdepth 1 -type f -name "*${IMG_NAME}*.img.xz" -print -quit)"
if [[ -n "$M41_XZ" ]]; then
  xz -t "$M41_XZ"
  echo '[OK] XZ integrity test passed.'
fi

echo '[8/8] Build artifacts ready.'
printf '\n==================================================\n M4.1 BUILD COMPLETE\n==================================================\n'
find "$DEPLOY_DIR" -maxdepth 1 -type f \( -name "*${IMG_NAME}*" -o -name "$CHECKSUM_FILE" \) -printf '  %f\n' | sort
printf '\nFirst boot flow remains M4:\n'
printf '  1. No WiFi -> open YWD-Hotspot-xxxx AP -> http://10.42.0.1/\n'
printf '  2. WiFi handoff -> OLED displays six-digit setup code\n'
printf '  3. Browse https://ywd-hotspot.local:8443/\n'
printf '  4. Finish wizard -> normal dashboard at http://ywd-hotspot.local:8080/\n'
printf '\nConsole polish:\n'
printf '  ywd-info | ywd-services | ywd-build | ywd-logs\n'
printf 'SSH: ssh -i %s ywd@ywd-hotspot.local\n' "$DEV_KEY"
printf 'RF safety behavior is unchanged from M4.\n'
