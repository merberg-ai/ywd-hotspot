#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PIN_FILE="$ROOT_DIR/os/pi-gen/PI-GEN-COMMIT"

fail=0

check_cmd() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    printf '[OK]   %s\n' "$cmd"
  else
    printf '[MISS] %s\n' "$cmd"
    fail=1
  fi
}

printf '==================================================\n'
printf ' YWD-Hotspot OS Builder Doctor\n'
printf '==================================================\n\n'

printf 'Host architecture: %s\n' "$(uname -m)"
printf 'Kernel:            %s\n' "$(uname -r)"
printf 'Working tree:      %s\n' "$ROOT_DIR"
printf 'Free space:        %s\n\n' "$(df -h "$ROOT_DIR" | awk 'NR==2 {print $4}')"

for cmd in git curl rsync xz debootstrap qemu-arm-static parted losetup mount umount sha256sum; do
  check_cmd "$cmd"
done

if [[ -f "$PIN_FILE" ]] && [[ -s "$PIN_FILE" ]]; then
  printf '[OK]   pi-gen pin: %s\n' "$(tr -d '[:space:]' < "$PIN_FILE")"
else
  printf '[MISS] pi-gen pin file: %s\n' "$PIN_FILE"
  fail=1
fi

if [[ "$EUID" -eq 0 ]]; then
  printf '[INFO] Running as root. BUILD.sh may invoke pi-gen directly.\n'
else
  printf '[INFO] Running as non-root. BUILD.sh will require sudo for pi-gen.\n'
fi

printf '\n'
if [[ "$fail" -ne 0 ]]; then
  printf 'Doctor found missing requirements.\n'
  printf 'On Raspberry Pi OS / Debian, install pi-gen dependencies with:\n\n'
  printf '  sudo apt update\n'
  printf '  sudo apt install coreutils quilt parted qemu-user-binfmt debootstrap zerofree zip \\\n    dosfstools e2fsprogs libarchive-tools libcap2-bin grep rsync xz-utils file git curl bc \\\n    gpg pigz xxd arch-test bmap-tools kmod\n'
  exit 1
fi

printf 'Doctor checks passed.\n'
