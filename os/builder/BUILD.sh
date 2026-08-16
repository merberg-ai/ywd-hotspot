#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OS_DIR="$ROOT_DIR/os"
PIN_FILE="$OS_DIR/pi-gen/PI-GEN-COMMIT"
PI_GEN_DIR="$OS_DIR/.pi-gen"
WORK_DIR="$OS_DIR/work/m1.1-headless"
DEPLOY_DIR="$OS_DIR/deploy"
LOCAL_DIR="$OS_DIR/local"
LOCAL_WIFI="$LOCAL_DIR/provision.env"
DEV_KEY="$LOCAL_DIR/ywd-os-dev_ed25519"
CUSTOM_STAGE_SRC="$OS_DIR/pi-gen/stage2/10-ywd-headless"
CUSTOM_STAGE_DST="$PI_GEN_DIR/stage2/10-ywd-headless"
IMG_NAME='ywd-hotspot-os-m1.1-headless'

if [[ ! -f "$PIN_FILE" ]]; then
  echo "ERROR: missing $PIN_FILE" >&2
  exit 1
fi

PI_GEN_COMMIT="$(tr -d '[:space:]' < "$PIN_FILE")"
if [[ ! "$PI_GEN_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: invalid pi-gen commit in $PIN_FILE" >&2
  exit 1
fi

if [[ ! -d "$CUSTOM_STAGE_SRC" ]]; then
  echo "ERROR: missing custom headless stage: $CUSTOM_STAGE_SRC" >&2
  exit 1
fi

printf '==================================================\n'
printf ' YWD-Hotspot OS Image Builder - Milestone 1.1\n'
printf ' Headless Boot Validation\n'
printf '==================================================\n\n'
printf 'Source repo:        merberg-ai/ywd-hotspot\n'
printf 'Source branch:      %s\n' "$(git -C "$ROOT_DIR" branch --show-current 2>/dev/null || echo unknown)"
printf 'Source commit:      %s\n' "$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
printf 'Target:             Raspberry Pi Zero W / Zero WH\n'
printf 'Architecture:       armhf\n'
printf 'Base:               Raspberry Pi OS Lite / trixie\n'
printf 'Image:              %s\n' "$IMG_NAME"
printf 'pi-gen commit:      %s\n' "$PI_GEN_COMMIT"
printf 'Work directory:     %s\n' "$WORK_DIR"
printf 'Deploy directory:   %s\n\n' "$DEPLOY_DIR"
printf 'M1.1 adds only headless validation components:\n'
printf '  - SSD1306 OLED boot/network status\n'
printf '  - optional build-time WiFi provisioning\n'
printf '  - key-only SSH for the local builder test key\n'
printf 'It still DOES NOT install the full YWD-Hotspot RF stack.\n\n'

mkdir -p "$OS_DIR" "$WORK_DIR" "$DEPLOY_DIR" "$LOCAL_DIR"
chmod 0700 "$LOCAL_DIR"

if [[ ! -d "$PI_GEN_DIR/.git" ]]; then
  echo '[1/7] Cloning upstream pi-gen...'
  git clone https://github.com/RPi-Distro/pi-gen.git "$PI_GEN_DIR"
else
  echo '[1/7] Reusing local pi-gen checkout...'
fi

echo '[2/7] Fetching and checking out pinned pi-gen revision...'
git -C "$PI_GEN_DIR" fetch --quiet origin master
git -C "$PI_GEN_DIR" checkout --quiet --detach "$PI_GEN_COMMIT"
git -C "$PI_GEN_DIR" reset --hard --quiet "$PI_GEN_COMMIT"
git -C "$PI_GEN_DIR" clean -fdx --quiet

# Inject only our custom Stage 2 substage into the clean pinned pi-gen tree.
cp -a "$CUSTOM_STAGE_SRC" "$CUSTOM_STAGE_DST"
chmod +x "$CUSTOM_STAGE_DST/01-run.sh"
chmod +x "$CUSTOM_STAGE_DST/files/ywd-headless-oled.py"
chmod +x "$CUSTOM_STAGE_DST/files/ywd-headless-provision.sh"

if [[ -f "$LOCAL_WIFI" ]]; then
  # shellcheck disable=SC1090
  source "$LOCAL_WIFI"
  if [[ -n "${WIFI_SSID:-}" ]]; then
    install -m 0600 "$LOCAL_WIFI" "$CUSTOM_STAGE_DST/files/provision.env"
    printf '[INFO] WiFi provisioning: %s\n' "$WIFI_SSID"
  else
    printf '[INFO] WiFi provisioning file exists but has no SSID; skipping.\n'
  fi
else
  printf '[INFO] No local WiFi provisioning configured. OLED will show WIFI NO CONFIG.\n'
  printf '       Optional setup: bash os/builder/CONFIGURE-WIFI.sh\n'
fi

if ! command -v ssh-keygen >/dev/null 2>&1; then
  echo 'ERROR: ssh-keygen is required on the builder host (install openssh-client).' >&2
  exit 1
fi

if [[ ! -f "$DEV_KEY" ]]; then
  echo '[3/7] Generating local M1.1 SSH development key...'
  ssh-keygen -q -t ed25519 -N '' -C 'ywd-hotspot-os-m1.1-dev' -f "$DEV_KEY"
  chmod 0600 "$DEV_KEY"
  chmod 0644 "$DEV_KEY.pub"
else
  echo '[3/7] Reusing local M1.1 SSH development key...'
fi

PUBKEY="$(cat "$DEV_KEY.pub")"
# Satisfy pi-gen's fixed-user safety requirement with a per-build random local
# password. Password SSH authentication is disabled; this value is not printed
# or retained outside pi-gen's transient build config.
DEV_PASS="$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"

cat > "$PI_GEN_DIR/config" <<EOF
IMG_NAME='$IMG_NAME'
PI_GEN_RELEASE='YWD-Hotspot OS M1.1 headless validation'
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
# M1.1 intentionally builds only the Lite path. Explicitly limiting STAGE_LIST
# avoids later desktop EXPORT_IMAGE registrations and keeps the build target
# deterministic.
STAGE_LIST="\$BASE_DIR/stage0 \$BASE_DIR/stage1 \$BASE_DIR/stage2"
EOF
chmod 0600 "$PI_GEN_DIR/config"

# Do not mix a failed/partial M1.1 export with this run. Older M1 artifacts are
# deliberately left alone for comparison.
find "$DEPLOY_DIR" -maxdepth 1 -type f -name "*${IMG_NAME}*" -delete
rm -f "$DEPLOY_DIR/SHA256SUMS-M1.1"

echo '[4/7] Running builder doctor...'
bash "$OS_DIR/builder/DOCTOR.sh"

echo '[5/7] Building Raspberry Pi OS Lite headless-validation image...'
if [[ "$EUID" -eq 0 ]]; then
  (cd "$PI_GEN_DIR" && ./build.sh)
else
  (cd "$PI_GEN_DIR" && sudo ./build.sh)
fi

echo '[6/7] Generating SHA-256 checksum...'
(
  cd "$DEPLOY_DIR"
  shopt -s nullglob
  files=( *"$IMG_NAME"*.img *"$IMG_NAME"*.img.xz *"$IMG_NAME"*.img.gz *"$IMG_NAME"*.zip )
  if (( ${#files[@]} == 0 )); then
    echo 'ERROR: pi-gen completed but no M1.1 deploy image was found.' >&2
    exit 1
  fi
  sha256sum "${files[@]}" > SHA256SUMS-M1.1
)

echo '[7/7] Build artifacts ready.'
printf '\n==================================================\n'
printf ' M1.1 BUILD COMPLETE\n'
printf '==================================================\n'
printf 'Artifacts:\n'
find "$DEPLOY_DIR" -maxdepth 1 -type f \( -name "*${IMG_NAME}*" -o -name 'SHA256SUMS-M1.1' \) -printf '  %f\n' | sort
printf '\nHeadless validation after flashing:\n'
printf '  OLED should show: YWD HOTSPOT OS / M1.1 HEADLESS / BOOT OK\n'
printf '  If WiFi was configured, it should also show SSID and IPv4 address.\n'
printf '\nSSH from this Pi 5 after WiFi connects:\n'
printf '  ssh -i %s ywd@ywd-hotspot.local\n' "$DEV_KEY"
printf '\nThe development SSH private key remains only under os/local/ and is ignored by Git.\n'
