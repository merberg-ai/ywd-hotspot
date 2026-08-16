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

PAGE_SIZE="$(getconf PAGE_SIZE 2>/dev/null || echo unknown)"
printf 'Host architecture: %s\n' "$(uname -m)"
printf 'Kernel:            %s\n' "$(uname -r)"
printf 'Kernel page size:  %s\n' "$PAGE_SIZE"
printf 'Working tree:      %s\n' "$ROOT_DIR"
printf 'Free space:        %s\n\n' "$(df -h "$ROOT_DIR" | awk 'NR==2 {print $4}')"

# Keep the core checks aligned with the pinned pi-gen `depends` file. M1.1 also
# needs ssh-keygen on the builder so each builder can create its own local-only
# development key instead of shipping a shared private key.
for cmd in git curl rsync xz debootstrap qemu-arm parted losetup mount umount sha256sum ssh-keygen; do
  check_cmd "$cmd"
done

if ! command -v qemu-arm >/dev/null 2>&1; then
  if command -v dpkg-query >/dev/null 2>&1 && \
     dpkg-query -W -f='${Status}' qemu-user-binfmt 2>/dev/null | grep -q 'install ok installed'; then
    printf '[INFO] qemu-user-binfmt is installed, but qemu-arm is not in PATH.\n'
    printf '       Install/repair the qemu-user package: sudo apt install qemu-user qemu-user-binfmt\n'
  fi
fi

# armhf image builds require a 4K-page kernel. Raspberry Pi 5 normally boots
# its Pi-5-specific 16K-page kernel, so detect that before pi-gen starts.
if [[ "$PAGE_SIZE" != "4096" ]]; then
  printf '[MISS] armhf builder requires a 4096-byte kernel page size (current: %s).\n' "$PAGE_SIZE"
  printf '[INFO] Raspberry Pi 5 normally uses the 16K-page kernel_2712.img.\n'
  printf '       For this builder host, switch to the common 4K-page kernel by adding:\n'
  printf '\n'
  printf '         kernel=kernel8.img\n'
  printf '         initramfs initramfs8 followkernel\n'
  printf '\n'
  printf '       to /boot/firmware/config.txt, then reboot and verify:\n'
  printf '         getconf PAGE_SIZE\n'
  printf '       Expected result: 4096\n'
  fail=1
else
  printf '[OK]   armhf-compatible 4K kernel page size\n'
fi

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
  printf 'Doctor found requirements that need attention.\n'
  printf 'For missing builder/pi-gen packages on Raspberry Pi OS / Debian, install:\n\n'
  printf '  sudo apt update\n'
  printf '  sudo apt install coreutils quilt parted qemu-user qemu-user-binfmt debootstrap zerofree zip \\\n    dosfstools e2fsprogs libarchive-tools libcap2-bin grep rsync xz-utils file git curl bc \\\n    gpg pigz xxd arch-test bmap-tools kmod openssh-client\n'
  exit 1
fi

printf 'Doctor checks passed.\n'
