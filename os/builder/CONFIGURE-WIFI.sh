#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOCAL_DIR="$ROOT_DIR/os/local"
ENV_FILE="$LOCAL_DIR/provision.env"

mkdir -p "$LOCAL_DIR"
chmod 0700 "$LOCAL_DIR"

printf '==================================================\n'
printf ' YWD-Hotspot OS M1.1 WiFi Provisioning\n'
printf '==================================================\n\n'
printf 'This writes WiFi credentials only to:\n  %s\n\n' "$ENV_FILE"
printf 'The os/local directory is ignored by Git and must never be committed.\n\n'

current="$(nmcli -t -f ACTIVE,SSID dev wifi 2>/dev/null | awk -F: '$1=="yes"{sub(/^yes:/,""); print; exit}' || true)"
if [[ -n "$current" ]]; then
  printf 'Current builder WiFi SSID: %s\n' "$current"
fi

read -r -p "WiFi SSID${current:+ [$current]}: " ssid
ssid="${ssid:-$current}"

if [[ -z "$ssid" ]]; then
  echo 'No SSID supplied; removing local WiFi provisioning file.'
  rm -f "$ENV_FILE"
  exit 0
fi

read -r -s -p 'WiFi password (blank for an open network): ' password
printf '\n'

{
  printf 'WIFI_SSID=%q\n' "$ssid"
  printf 'WIFI_PASSWORD=%q\n' "$password"
} > "$ENV_FILE"
chmod 0600 "$ENV_FILE"

printf '\nSaved local build-only WiFi provisioning.\n'
printf 'Run: bash os/builder/BUILD.sh\n'
