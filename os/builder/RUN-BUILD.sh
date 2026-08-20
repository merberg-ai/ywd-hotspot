#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OS_DIR="$ROOT_DIR/os"
BUILDER_DIR="$OS_DIR/builder"
LOCAL_DIR="$OS_DIR/local"
GEN_DIR="$LOCAL_DIR/generated"

HEADLESS_OVERLAY="$OS_DIR/pi-gen/stage2/10-ywd-headless/files/provision.env"
CONFIG_OVERLAY="$OS_DIR/pi-gen/stage2/25-ywd-firstboot/files/factory-config.json"
FIRSTBOOT_OVERLAY="$OS_DIR/pi-gen/stage2/25-ywd-firstboot/files/factory-provision.json"
RESTORE_OVERLAY="$OS_DIR/pi-gen/stage2/25-ywd-firstboot/files/factory-restore.json"
LEGACY_WIFI="$LOCAL_DIR/provision.env"

cleanup() {
  rm -f "$HEADLESS_OVERLAY" "$CONFIG_OVERLAY" "$FIRSTBOOT_OVERLAY" "$RESTORE_OVERLAY"
}
trap cleanup EXIT INT TERM
cleanup

mkdir -p "$LOCAL_DIR" "$GEN_DIR"
chmod 0700 "$LOCAL_DIR" "$GEN_DIR"

python3 "$BUILDER_DIR/PREPARE-PROFILE.py"

install -m 0600 "$GEN_DIR/factory-config.json" "$CONFIG_OVERLAY"

if [[ -f "$GEN_DIR/factory-restore.json" ]]; then
  install -m 0600 "$GEN_DIR/factory-restore.json" "$RESTORE_OVERLAY"
  echo '[INFO] Imported dashboard settings backup staged for native first-boot restore; secure hotspot setup wizard will be skipped after successful restore.'
elif [[ -f "$GEN_DIR/factory-provision.json" ]]; then
  install -m 0600 "$GEN_DIR/factory-provision.json" "$FIRSTBOOT_OVERLAY"
  echo '[INFO] Fully preconfigured hotspot payload staged; secure hotspot setup wizard will be skipped after successful first-boot apply.'
else
  echo '[INFO] Partial/default profile staged; secure hotspot setup wizard remains enabled.'
fi

if [[ -f "$GEN_DIR/provision.env" ]]; then
  install -m 0600 "$GEN_DIR/provision.env" "$HEADLESS_OVERLAY"
  install -m 0600 "$GEN_DIR/provision.env" "$LEGACY_WIFI"
  echo '[INFO] Wi-Fi preconfiguration staged.'
else
  rm -f "$LEGACY_WIFI"
  echo '[INFO] Wi-Fi left blank; first boot will use the YWD setup AP.'
fi

# shellcheck disable=SC1090
source "$GEN_DIR/build.env"
export YWD_IMG_NAME YWD_OS_VERSION

bash "$BUILDER_DIR/BUILD.sh"
