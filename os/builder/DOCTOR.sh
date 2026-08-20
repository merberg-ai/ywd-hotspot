#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PIN_FILE="$ROOT_DIR/os/pi-gen/PI-GEN-COMMIT"
RUNTIME_PINS="$ROOT_DIR/pins.env"
RUNTIME_CACHE="$ROOT_DIR/os/local/build-cache/runtime"
fail=0

check_cmd() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then printf '[OK]   %s\n' "$cmd"; else printf '[MISS] %s\n' "$cmd"; fail=1; fi
}

printf '==================================================\n'
printf ' YWD-Hotspot OS Builder Doctor\n'
printf '==================================================\n\n'

PAGE_SIZE="$(getconf PAGE_SIZE 2>/dev/null || echo unknown)"
BRANCH="$(git -C "$ROOT_DIR" branch --show-current 2>/dev/null || echo unknown)"
COMMIT="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
VERSION="$(tr -d '\r\n' < "$ROOT_DIR/VERSION" 2>/dev/null || echo unknown)"
printf 'Host architecture: %s\n' "$(uname -m)"
printf 'Kernel:            %s\n' "$(uname -r)"
printf 'Kernel page size:  %s\n' "$PAGE_SIZE"
printf 'Working tree:      %s\n' "$ROOT_DIR"
printf 'Source:            %s @ %s\n' "$BRANCH" "$COMMIT"
printf 'Application:       %s\n' "$VERSION"
printf 'Free space:        %s\n\n' "$(df -h "$ROOT_DIR" | awk 'NR==2 {print $4}')"

for cmd in git curl rsync xz openssl debootstrap qemu-arm parted losetup mount umount sha256sum ssh-keygen file; do check_cmd "$cmd"; done

if [[ "$PAGE_SIZE" != "4096" ]]; then
  printf '[MISS] armhf builder requires a 4096-byte kernel page size (current: %s).\n' "$PAGE_SIZE"
  printf '[INFO] On a Raspberry Pi 5 builder, use the common 4K-page kernel, reboot, then verify `getconf PAGE_SIZE` returns 4096.\n'
  fail=1
else
  printf '[OK]   armhf-compatible 4K kernel page size\n'
fi

if [[ -f "$PIN_FILE" ]] && [[ -s "$PIN_FILE" ]]; then
  PIN="$(tr -d '[:space:]' < "$PIN_FILE")"
  if [[ "$PIN" =~ ^[0-9a-f]{40}$ ]]; then printf '[OK]   pi-gen pin: %s\n' "$PIN"; else printf '[MISS] invalid pi-gen pin: %s\n' "$PIN"; fail=1; fi
else
  printf '[MISS] pi-gen pin file: %s\n' "$PIN_FILE"; fail=1
fi

for path in \
  os/builder/SYSTEM-CLI.py \
  os/builder/SSH-KEYS.py \
  os/pi-gen/stage2/10-ywd-headless \
  os/pi-gen/stage2/15-ywd-network \
  os/pi-gen/stage2/20-ywd-runtime \
  os/pi-gen/stage2/25-ywd-firstboot \
  os/pi-gen/stage2/27-ywd-polish \
  lib/runtime_build.py lib/mmdvm_voice_build.py lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch \
  lib/oled.py lib/config_model.py lib/settings_backup.py lib/settings_admin.py lib/update_runner.py lib/update_admin.py \
  systemd/ywd-update.service web/update.js web/instrumentation.js; do
  if [[ -e "$ROOT_DIR/$path" ]]; then printf '[OK]   source %s\n' "$path"; else printf '[MISS] source %s\n' "$path"; fail=1; fi
done

if [[ -f "$RUNTIME_PINS" ]]; then
  # shellcheck disable=SC1090
  source "$RUNTIME_PINS"
  PATCH_PATH="$ROOT_DIR/${MMDVM_YWD_PATCH:-}"
  if [[ -n "${MMDVM_HOST_COMMIT:-}" && "$MMDVM_HOST_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
    printf '[OK]   MMDVM upstream pin: %s\n' "$MMDVM_HOST_COMMIT"
  else
    printf '[MISS] invalid MMDVM upstream pin in pins.env\n'; fail=1
  fi
  if [[ -n "${DMR_GATEWAY_COMMIT:-}" && "$DMR_GATEWAY_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
    printf '[OK]   DMRGateway upstream pin: %s\n' "$DMR_GATEWAY_COMMIT"
  else
    printf '[MISS] invalid DMRGateway upstream pin in pins.env\n'; fail=1
  fi
  if [[ -f "$PATCH_PATH" && "${MMDVM_YWD_PATCH_SHA256:-}" =~ ^[0-9a-f]{64}$ ]]; then
    ACTUAL_PATCH_SHA="$(sha256sum "$PATCH_PATH" | awk '{print $1}')"
    if [[ "$ACTUAL_PATCH_SHA" == "$MMDVM_YWD_PATCH_SHA256" ]]; then
      printf '[OK]   canonical YWD MMDVM patch SHA-256: %s\n' "$ACTUAL_PATCH_SHA"
    else
      printf '[MISS] canonical YWD MMDVM patch hash mismatch\n'
      printf '       expected: %s\n' "$MMDVM_YWD_PATCH_SHA256"
      printf '       actual:   %s\n' "$ACTUAL_PATCH_SHA"
      fail=1
    fi
  else
    printf '[MISS] canonical YWD MMDVM patch metadata/path is invalid\n'; fail=1
  fi
  if [[ "${MMDVM_YWD_PATCH_API:-}" =~ ^[0-9]+$ ]]; then
    printf '[OK]   canonical YWD MMDVM patch API: %s\n' "$MMDVM_YWD_PATCH_API"
  else
    printf '[MISS] canonical YWD MMDVM patch API is invalid\n'; fail=1
  fi
else
  printf '[MISS] runtime pins file: %s\n' "$RUNTIME_PINS"; fail=1
fi

if python3 "$ROOT_DIR/os/builder/SYSTEM-CLI.py" validate >/dev/null 2>&1; then
  printf '[OK]   System / OS builder profile\n'
else
  printf '[MISS] System / OS builder profile is invalid\n'
  python3 "$ROOT_DIR/os/builder/SYSTEM-CLI.py" validate || true
  fail=1
fi

if [[ -d "$RUNTIME_CACHE" ]]; then
  CACHE_BYTES="$(du -sh "$RUNTIME_CACHE" 2>/dev/null | awk '{print $1}')"
  CACHE_FILES="$(find "$RUNTIME_CACHE" -type f 2>/dev/null | wc -l | tr -d ' ')"
  printf '[INFO] Persistent runtime cache: %s (%s files)\n' "${CACHE_BYTES:-0}" "$CACHE_FILES"
else
  printf '[INFO] Persistent runtime cache: empty (first canonical build will populate it)\n'
fi

if ! git -C "$ROOT_DIR" diff --quiet --ignore-submodules -- || ! git -C "$ROOT_DIR" diff --cached --quiet --ignore-submodules --; then
  printf '[MISS] tracked source is dirty; commit/stash changes before building.\n'
  fail=1
else
  printf '[OK]   tracked source tree is clean\n'
fi

if [[ "$EUID" -eq 0 ]]; then printf '[INFO] Running as root. BUILD.sh may invoke pi-gen directly.\n'; else printf '[INFO] Running as non-root. BUILD.sh will require sudo for pi-gen.\n'; fi

printf '\n'
if [[ "$fail" -ne 0 ]]; then
  printf 'Doctor found requirements that need attention.\n'
  printf 'For missing builder/pi-gen packages on Debian/Ubuntu/Raspberry Pi OS:\n\n'
  printf '  sudo apt update\n'
  printf '  sudo apt install coreutils quilt parted qemu-user qemu-user-binfmt debootstrap zerofree zip \\\n    dosfstools e2fsprogs libarchive-tools libcap2-bin grep rsync xz-utils file git curl bc \\\n    gpg pigz xxd arch-test bmap-tools kmod openssh-client openssl\n'
  exit 1
fi

printf 'Doctor checks passed.\n'
