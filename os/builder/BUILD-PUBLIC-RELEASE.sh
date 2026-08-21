#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILDER="$ROOT_DIR/os/builder"
LOCAL="$ROOT_DIR/os/local"
PROFILE="$LOCAL/builder-profile.json"
VERSION="$(tr -d '\r\n' < "$ROOT_DIR/VERSION")"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$LOCAL/builder-profile.before-public-release.$STAMP.json"
HAD_PROFILE=0

if [[ "$VERSION" != "0.2.0-rc1" ]]; then
  echo "ERROR: public release wrapper expects VERSION 0.2.0-rc1, got $VERSION" >&2
  exit 1
fi

BRANCH="$(git -C "$ROOT_DIR" branch --show-current)"
if [[ "$BRANCH" != "release/0.2.0-rc1" ]]; then
  echo "ERROR: public release image must be built from release/0.2.0-rc1; current branch: $BRANCH" >&2
  exit 1
fi

if ! git -C "$ROOT_DIR" diff --quiet --ignore-submodules -- || ! git -C "$ROOT_DIR" diff --cached --quiet --ignore-submodules --; then
  echo "ERROR: tracked source changes are present; public image requires a clean checkout." >&2
  exit 1
fi

mkdir -p "$LOCAL"
chmod 0700 "$LOCAL"
if [[ -f "$PROFILE" ]]; then
  cp -p "$PROFILE" "$BACKUP"
  chmod 0600 "$BACKUP"
  HAD_PROFILE=1
  echo "[INFO] Saved current private builder profile: $BACKUP"
fi

restore_profile() {
  if [[ "$HAD_PROFILE" == "1" && -f "$BACKUP" ]]; then
    cp -p "$BACKUP" "$PROFILE"
    chmod 0600 "$PROFILE"
    echo "[INFO] Restored original builder profile: $PROFILE"
  else
    rm -f "$PROFILE"
  fi
}
trap restore_profile EXIT INT TERM

# Start from the application's canonical defaults, not the developer's current
# profile. Release identity and update/security policy are the only deliberate
# public-image overrides.
python3 "$BUILDER/PROFILE-CLI.py" reset
python3 "$BUILDER/SYSTEM-CLI.py" reset
python3 "$BUILDER/PROFILE-CLI.py" set image.image_name str "ywd-hotspot-0.2.0-rc1-pi-zero"
python3 "$BUILDER/PROFILE-CLI.py" set image.os_version str "YWD-Hotspot OS 0.2.0-rc1"
printf '%s' main | python3 "$BUILDER/SYSTEM-CLI.py" set-stdin update_channel
printf '%s' disabled | python3 "$BUILDER/SYSTEM-CLI.py" set-stdin ssh_policy

# Explicitly assert the safety-critical release defaults even though reset
# already provides them.
python3 "$BUILDER/PROFILE-CLI.py" set config.maintenance.rf_autostart bool no

printf '\n============================================================\n'
printf ' YWD-HOTSPOT %s PUBLIC FACTORY IMAGE\n' "$VERSION"
printf '============================================================\n'
python3 "$BUILDER/PROFILE-CLI.py" review
printf '\n'
python3 "$BUILDER/SYSTEM-CLI.py" review
printf '\n'
python3 "$BUILDER/PUBLIC-RELEASE-CHECK.py" profile

# Generate the exact first-boot payload once and validate the generated files
# before RUN-BUILD regenerates the same deterministic profile.
python3 "$BUILDER/PREPARE-PROFILE.py"
python3 "$BUILDER/PUBLIC-RELEASE-CHECK.py" generated

printf '\n[OK] Factory-image gate passed. Starting reproducible public build.\n\n'
export YWD_PUBLIC_RELEASE=1
bash "$BUILDER/RUN-BUILD.sh"

# RUN-BUILD prepares the profile again; verify that no forbidden payload was
# introduced during the actual build path.
python3 "$BUILDER/PUBLIC-RELEASE-CHECK.py" all

printf '\n[OK] Public release build completed from clean factory/default settings.\n'
printf '     Original private builder profile has not been included in the image.\n'
