#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OS_DIR="$ROOT_DIR/os"
PIN_FILE="$OS_DIR/pi-gen/PI-GEN-COMMIT"
PI_GEN_DIR="$OS_DIR/.pi-gen"
WORK_DIR="$OS_DIR/work"
DEPLOY_DIR="$OS_DIR/deploy"

if [[ ! -f "$PIN_FILE" ]]; then
  echo "ERROR: missing $PIN_FILE" >&2
  exit 1
fi

PI_GEN_COMMIT="$(tr -d '[:space:]' < "$PIN_FILE")"
if [[ ! "$PI_GEN_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: invalid pi-gen commit in $PIN_FILE" >&2
  exit 1
fi

printf '==================================================\n'
printf ' YWD-Hotspot OS Image Builder - Milestone 1\n'
printf '==================================================\n\n'
printf 'Source repo:        merberg-ai/ywd-hotspot\n'
printf 'Source branch:      %s\n' "$(git -C "$ROOT_DIR" branch --show-current 2>/dev/null || echo unknown)"
printf 'Source commit:      %s\n' "$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
printf 'Target:             Raspberry Pi Zero W / Zero WH\n'
printf 'Architecture:       armhf\n'
printf 'Base:               Raspberry Pi OS Lite / trixie\n'
printf 'pi-gen commit:      %s\n' "$PI_GEN_COMMIT"
printf 'Work directory:     %s\n' "$WORK_DIR"
printf 'Deploy directory:   %s\n\n' "$DEPLOY_DIR"
printf 'This build DOES NOT install YWD-Hotspot and DOES NOT modify\n'
printf 'the builder host\047s installed YWD-Hotspot configuration.\n\n'

mkdir -p "$OS_DIR" "$WORK_DIR" "$DEPLOY_DIR"

if [[ ! -d "$PI_GEN_DIR/.git" ]]; then
  echo '[1/5] Cloning upstream pi-gen...'
  git clone https://github.com/RPi-Distro/pi-gen.git "$PI_GEN_DIR"
else
  echo '[1/5] Reusing local pi-gen checkout...'
fi

echo '[2/5] Fetching and checking out pinned pi-gen revision...'
git -C "$PI_GEN_DIR" fetch --quiet origin master
git -C "$PI_GEN_DIR" checkout --quiet --detach "$PI_GEN_COMMIT"
git -C "$PI_GEN_DIR" reset --hard --quiet "$PI_GEN_COMMIT"
git -C "$PI_GEN_DIR" clean -fdx --quiet

cat > "$PI_GEN_DIR/config" <<EOF
IMG_NAME='ywd-hotspot-os-m1-vanilla'
PI_GEN_RELEASE='YWD-Hotspot OS development base'
RELEASE='trixie'
ARCH='armhf'
TARGET_HOSTNAME='ywd-hotspot'
LOCALE_DEFAULT='en_US.UTF-8'
KEYBOARD_KEYMAP='us'
KEYBOARD_LAYOUT='English (US)'
TIMEZONE_DEFAULT='America/Los_Angeles'
WPA_COUNTRY='US'
ENABLE_SSH=0
FIRST_USER_NAME='ywd'
DISABLE_FIRST_BOOT_USER_RENAME=0
PASSWORDLESS_SUDO=0
DEPLOY_COMPRESSION='xz'
COMPRESSION_LEVEL=6
WORK_DIR='$WORK_DIR'
DEPLOY_DIR='$DEPLOY_DIR'
# Milestone 1 intentionally builds only the Lite path. Explicitly limiting
# STAGE_LIST is safer than placing SKIP files in later stages because pi-gen
# registers EXPORT_IMAGE before evaluating SKIP. A skipped stage4 can therefore
# still try to export a nonexistent stage4/rootfs.
STAGE_LIST="\$BASE_DIR/stage0 \$BASE_DIR/stage1 \$BASE_DIR/stage2"
EOF

echo '[3/5] Running builder doctor...'
bash "$OS_DIR/builder/DOCTOR.sh"

echo '[4/5] Building Raspberry Pi OS Lite image...'
if [[ "$EUID" -eq 0 ]]; then
  (cd "$PI_GEN_DIR" && ./build.sh)
else
  (cd "$PI_GEN_DIR" && sudo ./build.sh)
fi

echo '[5/5] Generating SHA-256 checksums...'
(
  cd "$DEPLOY_DIR"
  shopt -s nullglob
  files=( *.img *.img.xz *.img.gz *.zip )
  if (( ${#files[@]} == 0 )); then
    echo 'ERROR: pi-gen completed but no deploy image was found.' >&2
    exit 1
  fi
  sha256sum "${files[@]}" > SHA256SUMS
)

printf '\n==================================================\n'
printf ' BUILD COMPLETE\n'
printf '==================================================\n'
printf 'Artifacts:\n'
find "$DEPLOY_DIR" -maxdepth 1 -type f -printf '  %f\n' | sort
printf '\nNext milestone: flash and boot-test this vanilla image on\n'
printf 'the reference Raspberry Pi Zero W before adding YWD-Hotspot.\n'
