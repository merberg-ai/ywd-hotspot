#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OS_DIR="$ROOT_DIR/os"
PIN_FILE="$OS_DIR/pi-gen/PI-GEN-COMMIT"
PI_GEN_DIR="$OS_DIR/.pi-gen"
WORK_DIR="$OS_DIR/work/m2-runtime"
DEPLOY_DIR="$OS_DIR/deploy"
LOCAL_DIR="$OS_DIR/local"
LOCAL_WIFI="$LOCAL_DIR/provision.env"
DEV_KEY="$LOCAL_DIR/ywd-os-dev_ed25519"
HEADLESS_STAGE_SRC="$OS_DIR/pi-gen/stage2/10-ywd-headless"
HEADLESS_STAGE_DST="$PI_GEN_DIR/stage2/10-ywd-headless"
RUNTIME_STAGE_SRC="$OS_DIR/pi-gen/stage2/20-ywd-runtime"
RUNTIME_STAGE_DST="$PI_GEN_DIR/stage2/20-ywd-runtime"
IMG_NAME='ywd-hotspot-os-m2-runtime'

if [[ ! -f "$PIN_FILE" ]]; then
  echo "ERROR: missing $PIN_FILE" >&2
  exit 1
fi

PI_GEN_COMMIT="$(tr -d '[:space:]' < "$PIN_FILE")"
if [[ ! "$PI_GEN_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: invalid pi-gen commit in $PIN_FILE" >&2
  exit 1
fi

for stage in "$HEADLESS_STAGE_SRC" "$RUNTIME_STAGE_SRC"; do
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
printf ' YWD-Hotspot OS Image Builder - Milestone 2\n'
printf ' Hotspot Runtime / RF Safe by Default\n'
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
printf 'M2 includes:\n'
printf '  - M1.1 OLED, WiFi provisioning, mDNS and key-only SSH\n'
printf '  - current YWD-Hotspot app and WebUI\n'
printf '  - pinned MMDVM-Host and DMRGateway armhf binaries\n'
printf '  - Pi Zero W PL011 UART configuration\n'
printf '  - diagnostics, updater plumbing and persistent journal\n'
printf '\nSAFETY: MMDVM-Host and DMRGateway are DISABLED at boot.\n'
printf '        BrandMeister is disabled in the placeholder config.\n\n'

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

# Recreate our custom stage destinations from scratch after cleaning the pinned
# upstream tree. Copy directory CONTENTS (SRC/.) instead of relying on cp's
# destination-directory semantics, which can accidentally create nested stages
# when a destination exists from an interrupted run.
rm -rf "$HEADLESS_STAGE_DST" "$RUNTIME_STAGE_DST"
mkdir -p "$HEADLESS_STAGE_DST" "$RUNTIME_STAGE_DST"
cp -a "$HEADLESS_STAGE_SRC/." "$HEADLESS_STAGE_DST/"
cp -a "$RUNTIME_STAGE_SRC/." "$RUNTIME_STAGE_DST/"
chmod +x "$HEADLESS_STAGE_DST/01-run.sh"
chmod +x "$HEADLESS_STAGE_DST/files/ywd-headless-oled.py"
chmod +x "$HEADLESS_STAGE_DST/files/ywd-headless-provision.sh"
chmod +x "$RUNTIME_STAGE_DST/01-run.sh"

# Build the M2 appliance payload from the exact current YWD-Hotspot source tree.
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

# The runtime stage sources this metadata and records it in build-info.json.
{
  printf 'YWD_GIT_BRANCH=%q\n' "$SOURCE_BRANCH"
  printf 'YWD_GIT_COMMIT=%q\n' "$SOURCE_COMMIT"
  printf 'YWD_GIT_COMMIT_DATE=%q\n' "$SOURCE_COMMIT_DATE"
} > "$RUNTIME_STAGE_DST/files/build.env"
chmod 0644 "$RUNTIME_STAGE_DST/files/build.env"

if [[ -f "$LOCAL_WIFI" ]]; then
  # shellcheck disable=SC1090
  source "$LOCAL_WIFI"
  if [[ -n "${WIFI_SSID:-}" ]]; then
    install -m 0600 "$LOCAL_WIFI" "$HEADLESS_STAGE_DST/files/provision.env"
    printf '[INFO] WiFi provisioning: %s\n' "$WIFI_SSID"
  else
    printf '[INFO] WiFi provisioning file exists but has no SSID; skipping.\n'
  fi
else
  printf '[INFO] No local WiFi provisioning configured. OLED will show WIFI NO CONFIG.\n'
  printf '       Optional setup: bash os/builder/CONFIGURE-WIFI.sh\n'
fi

# Verify the exact files the M2 stage requires BEFORE spending time inside
# pi-gen. This also makes an interrupted/nested custom-stage copy obvious.
echo '[3/8] Verifying injected M2 payload...'
required_payload=(
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
    echo "ERROR: injected M2 payload is incomplete: $f" >&2
    echo "Runtime stage contents:" >&2
    find "$RUNTIME_STAGE_DST" -maxdepth 4 -type f -printf '  %P\n' | sort >&2 || true
    exit 1
  fi
done
printf '[OK] M2 payload staged: %s files, app version %s\n' \
  "$(find "$RUNTIME_APP" -type f | wc -l)" "$(tr -d '\r\n' < "$RUNTIME_APP/VERSION")"

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
# pi-gen requires a password when retaining a fixed first user. Generate a
# per-build random value, then disable password SSH completely below.
DEV_PASS="$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"

cat > "$PI_GEN_DIR/config" <<EOF
IMG_NAME='$IMG_NAME'
PI_GEN_RELEASE='YWD-Hotspot OS M2 runtime development image'
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
# M2 is still a Lite appliance image. Explicitly limiting STAGE_LIST prevents
# desktop/full image exporters from being registered.
STAGE_LIST="\$BASE_DIR/stage0 \$BASE_DIR/stage1 \$BASE_DIR/stage2"
EOF
chmod 0600 "$PI_GEN_DIR/config"

# Do not mix a failed/partial M2 export with this run. M1/M1.1 artifacts remain.
find "$DEPLOY_DIR" -maxdepth 1 -type f -name "*${IMG_NAME}*" -delete
rm -f "$DEPLOY_DIR/SHA256SUMS-M2"

echo '[5/8] Running builder doctor...'
bash "$OS_DIR/builder/DOCTOR.sh"

echo '[6/8] Building Raspberry Pi OS Lite + YWD-Hotspot runtime...'
echo '      The MMDVM-Host/DMRGateway compile step may be quiet for a while.'
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
    echo 'ERROR: pi-gen completed but no M2 deploy image was found.' >&2
    exit 1
  fi
  sha256sum "${files[@]}" > SHA256SUMS-M2
)
M2_XZ="$(find "$DEPLOY_DIR" -maxdepth 1 -type f -name "*${IMG_NAME}*.img.xz" -print -quit)"
if [[ -n "$M2_XZ" ]]; then
  xz -t "$M2_XZ"
  echo '[OK] XZ integrity test passed.'
else
  echo '[INFO] No .img.xz artifact found; skipping xz integrity test.'
fi

echo '[8/8] Build artifacts ready.'
printf '\n==================================================\n'
printf ' M2 BUILD COMPLETE\n'
printf '==================================================\n'
printf 'Artifacts:\n'
find "$DEPLOY_DIR" -maxdepth 1 -type f \( -name "*${IMG_NAME}*" -o -name 'SHA256SUMS-M2' \) -printf '  %f\n' | sort
printf '\nAfter flashing and booting:\n'
printf '  WebUI: http://ywd-hotspot.local:8080/\n'
printf '  SSH:   ssh -i %s ywd@ywd-hotspot.local\n' "$DEV_KEY"
printf '\nExpected safety state:\n'
printf '  ywd-dashboard.service   active\n'
printf '  ywd-activity.service    active\n'
printf '  ywd-mmdvmhost.service  disabled/inactive\n'
printf '  ywd-dmrgateway.service  disabled/inactive\n'
printf '\nDo not enable RF until the real station/DMR/radio configuration has been applied.\n'
