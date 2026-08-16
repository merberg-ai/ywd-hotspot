#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OS_DIR="$ROOT_DIR/os"
PIN_FILE="$OS_DIR/pi-gen/PI-GEN-COMMIT"
PI_GEN_DIR="$OS_DIR/.pi-gen"
WORK_DIR="$OS_DIR/work/m3-network"
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
IMG_NAME='ywd-hotspot-os-m3-network'

if [[ ! -f "$PIN_FILE" ]]; then
  echo "ERROR: missing $PIN_FILE" >&2
  exit 1
fi

PI_GEN_COMMIT="$(tr -d '[:space:]' < "$PIN_FILE")"
if [[ ! "$PI_GEN_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: invalid pi-gen commit in $PIN_FILE" >&2
  exit 1
fi

for stage in "$HEADLESS_STAGE_SRC" "$NETWORK_STAGE_SRC" "$RUNTIME_STAGE_SRC"; do
  if [[ ! -d "$stage" ]]; then
    echo "ERROR: missing custom OS stage: $stage" >&2
    exit 1
  fi
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
printf ' YWD-Hotspot OS Image Builder - Milestone 3\n'
printf ' Network Recovery + Phone WiFi Setup\n'
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
printf 'M3 includes:\n'
printf '  - M2 YWD-Hotspot runtime with RF disabled\n'
printf '  - bounded saved-WiFi connection attempts\n'
printf '  - automatic setup/recovery AP at 10.42.0.1\n'
printf '  - per-device WPA setup password shown on OLED\n'
printf '  - phone WiFi setup page with visible/manual/hidden SSID support\n'
printf '  - automatic return to recovery AP after failed credentials\n'
printf '\nSAFETY: MMDVM-Host and DMRGateway remain DISABLED at boot.\n'
printf '        BrandMeister remains disabled in the placeholder config.\n\n'

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

# Recreate custom stages after cleaning the pinned upstream tree.
for pair in \
  "$HEADLESS_STAGE_SRC|$HEADLESS_STAGE_DST" \
  "$NETWORK_STAGE_SRC|$NETWORK_STAGE_DST" \
  "$RUNTIME_STAGE_SRC|$RUNTIME_STAGE_DST"; do
  src="${pair%%|*}"
  dst="${pair#*|}"
  rm -rf "$dst"
  mkdir -p "$dst"
  cp -a "$src/." "$dst/"
done
chmod +x "$HEADLESS_STAGE_DST/01-run.sh"
chmod +x "$HEADLESS_STAGE_DST/files/ywd-headless-oled.py"
chmod +x "$HEADLESS_STAGE_DST/files/ywd-headless-provision.sh"
chmod +x "$NETWORK_STAGE_DST/01-run.sh"
chmod +x "$NETWORK_STAGE_DST/files/ywd-network-manager.py"
chmod +x "$RUNTIME_STAGE_DST/01-run.sh"

# Build the appliance payload from this exact YWD-Hotspot source tree.
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
install -m 0644 "$ROOT_DIR/assets/branding/ywd-hotspot-badge-256.webp" \
  "$RUNTIME_APP/assets/branding/ywd-hotspot-badge-256.webp"

# Runtime provenance and OS milestone metadata.
{
  printf 'YWD_GIT_BRANCH=%q\n' "$SOURCE_BRANCH"
  printf 'YWD_GIT_COMMIT=%q\n' "$SOURCE_COMMIT"
  printf 'YWD_GIT_COMMIT_DATE=%q\n' "$SOURCE_COMMIT_DATE"
  printf 'YWD_OS_VERSION=%q\n' 'M3-network-dev'
} > "$RUNTIME_STAGE_DST/files/build.env"
chmod 0644 "$RUNTIME_STAGE_DST/files/build.env"

if [[ -f "$LOCAL_WIFI" ]]; then
  # shellcheck disable=SC1090
  source "$LOCAL_WIFI"
  if [[ -n "${WIFI_SSID:-}" ]]; then
    install -m 0600 "$LOCAL_WIFI" "$HEADLESS_STAGE_DST/files/provision.env"
    printf '[INFO] Initial WiFi provisioning: %s\n' "$WIFI_SSID"
  else
    printf '[INFO] WiFi provisioning file exists but has no SSID; M3 will enter setup AP.\n'
  fi
else
  printf '[INFO] No local WiFi provisioning configured. M3 will enter setup AP.\n'
  printf '       Optional build-time setup: bash os/builder/CONFIGURE-WIFI.sh\n'
fi

# Catch broken custom-stage wiring before the expensive pi-gen run.
echo '[3/8] Verifying injected M3 payload...'
required_payload=(
  "$HEADLESS_STAGE_DST/files/ywd-headless-oled.py"
  "$NETWORK_STAGE_DST/00-packages"
  "$NETWORK_STAGE_DST/01-run.sh"
  "$NETWORK_STAGE_DST/files/ywd-network-manager.py"
  "$NETWORK_STAGE_DST/files/ywd-network-manager.service"
  "$RUNTIME_STAGE_DST/01-run.sh"
  "$RUNTIME_STAGE_DST/files/build.env"
  "$RUNTIME_APP/pins.env"
  "$RUNTIME_APP/VERSION"
  "$RUNTIME_APP/lib/dashboard.py"
  "$RUNTIME_APP/lib/generate-config.py"
  "$RUNTIME_APP/web/index.html"
  "$RUNTIME_APP/systemd/ywd-dashboard.service"
  "$RUNTIME_APP/assets/branding/ywd-hotspot-badge-256.webp"
)
for f in "${required_payload[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: injected M3 payload is incomplete: $f" >&2
    exit 1
  fi
done
python3 -m py_compile \
  "$HEADLESS_STAGE_DST/files/ywd-headless-oled.py" \
  "$NETWORK_STAGE_DST/files/ywd-network-manager.py"
printf '[OK] M3 payload staged and Python preflight passed; app version %s\n' \
  "$(tr -d '\r\n' < "$RUNTIME_APP/VERSION")"

if ! command -v ssh-keygen >/dev/null 2>&1; then
  echo 'ERROR: ssh-keygen is required on the builder host (install openssh-client).' >&2
  exit 1
fi

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
PI_GEN_RELEASE='YWD-Hotspot OS M3 network recovery development image'
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

# Preserve older milestone artifacts while removing only stale M3 output.
find "$DEPLOY_DIR" -maxdepth 1 -type f -name "*${IMG_NAME}*" -delete
rm -f "$DEPLOY_DIR/SHA256SUMS-M3"

echo '[5/8] Running builder doctor...'
bash "$OS_DIR/builder/DOCTOR.sh"

echo '[6/8] Building Raspberry Pi OS Lite + YWD-Hotspot M3...'
echo '      MMDVM-Host/DMRGateway compilation and final xz compression may be quiet.'
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
  if (( ${#files[@]} == 0 )); then
    echo 'ERROR: pi-gen completed but no M3 deploy image was found.' >&2
    exit 1
  fi
  sha256sum "${files[@]}" > SHA256SUMS-M3
)
M3_XZ="$(find "$DEPLOY_DIR" -maxdepth 1 -type f -name "*${IMG_NAME}*.img.xz" -print -quit)"
if [[ -n "$M3_XZ" ]]; then
  xz -t "$M3_XZ"
  echo '[OK] XZ integrity test passed.'
else
  echo '[INFO] No .img.xz artifact found; skipping xz integrity test.'
fi

echo '[8/8] Build artifacts ready.'
printf '\n==================================================\n'
printf ' M3 BUILD COMPLETE\n'
printf '==================================================\n'
printf 'Artifacts:\n'
find "$DEPLOY_DIR" -maxdepth 1 -type f \( -name "*${IMG_NAME}*" -o -name 'SHA256SUMS-M3' \) -printf '  %f\n' | sort
printf '\nNormal connected mode:\n'
printf '  WebUI: http://ywd-hotspot.local:8080/\n'
printf '  SSH:   ssh -i %s ywd@ywd-hotspot.local\n' "$DEV_KEY"
printf '\nSetup/recovery mode when normal WiFi is unavailable:\n'
printf '  OLED shows SSID + per-device AP password\n'
printf '  Connect phone to YWD-Hotspot-xxxx\n'
printf '  Open http://10.42.0.1/\n'
printf '\nRF remains disabled until real station/radio configuration is explicitly applied.\n'
