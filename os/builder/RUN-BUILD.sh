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

clean_previous_work() {
  local work_dir work_root resolved root_resolved
  work_dir="${YWD_OS_WORK_DIR:-$OS_DIR/work/unified}"
  work_root="$OS_DIR/work"
  resolved="$(realpath -m -- "$work_dir")"
  root_resolved="$(realpath -m -- "$work_root")"

  case "$resolved" in
    "$root_resolved"/*) ;;
    *)
      printf 'ERROR: refusing privileged cleanup outside %s: %s\n' "$root_resolved" "$resolved" >&2
      printf '       Remove the custom YWD_OS_WORK_DIR manually, then retry.\n' >&2
      return 1
      ;;
  esac

  [[ -e "$resolved" ]] || return 0

  if command -v findmnt >/dev/null 2>&1; then
    if findmnt -rn -R "$resolved" 2>/dev/null | grep -q .; then
      printf 'ERROR: previous pi-gen work tree still contains mounted filesystems:\n' >&2
      findmnt -R "$resolved" >&2 || true
      printf '       Refusing to remove it. Unmount/clean the failed pi-gen run first.\n' >&2
      return 1
    fi
  fi

  if [[ "$EUID" -eq 0 ]]; then
    printf '[INFO] Removing previous pi-gen work tree as root: %s\n' "$resolved"
    rm -rf -- "$resolved"
  else
    printf '[INFO] Removing previous pi-gen work tree (pi-gen may have left root-owned files): %s\n' "$resolved"
    sudo rm -rf -- "$resolved"
  fi
}

mkdir -p "$LOCAL_DIR" "$GEN_DIR"
chmod 0700 "$LOCAL_DIR" "$GEN_DIR"

python3 "$BUILDER_DIR/PREPARE-PROFILE.py"
python3 "$BUILDER_DIR/SYSTEM-CLI.py" validate
SYSTEM_ENV="$(python3 "$BUILDER_DIR/SYSTEM-CLI.py" write-env)"
# System / OS values are validated before being exported into BUILD.sh.
set -a
# shellcheck disable=SC1090
source "$SYSTEM_ENV"
set +a
printf '[INFO] System profile: %s\n' "$(python3 "$BUILDER_DIR/SYSTEM-CLI.py" status)"

# Generate/reuse the exact Ed25519 client key BUILD.sh already consumes from
# os/local/ywd-os-dev_ed25519. Users can export this same key before or after
# the build with SSH-KEYS.py; the matching public key is what pi-gen bakes into
# the ywd account whenever SSH policy is key-only.
python3 "$BUILDER_DIR/SSH-KEYS.py" ensure >/dev/null
printf '[INFO] SSH login key: %s\n' "$(python3 "$BUILDER_DIR/SSH-KEYS.py" fingerprint)"

RF_AUTOSTART="$(python3 - "$GEN_DIR/summary.json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    print('1' if json.load(f).get('rf_autostart') else '0')
PY
)"
export YWD_RF_AUTOSTART="$RF_AUTOSTART"
if [[ "$RF_AUTOSTART" == "1" ]]; then
  printf '\n'
  printf '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n'
  printf ' WARNING: RF AUTOSTART IS ENABLED IN THIS IMAGE PROFILE\n'
  printf ' After successful first-boot setup/restore, the RF stack may\n'
  printf ' start automatically and the hotspot can transmit RF.\n'
  printf '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n'
fi

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

# pi-gen itself runs under sudo and therefore failed/interrupted builds leave
# root-owned files below os/work. Clean that tree safely before BUILD.sh reaches
# its normal unprivileged rm -rf step so repeated builds are reliable.
clean_previous_work

# shellcheck disable=SC1090
source "$GEN_DIR/build.env"
export YWD_IMG_NAME YWD_OS_VERSION

bash "$BUILDER_DIR/BUILD.sh"
