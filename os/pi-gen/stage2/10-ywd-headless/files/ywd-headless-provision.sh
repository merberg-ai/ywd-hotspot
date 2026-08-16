#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=/etc/ywd-headless/provision.env
PROFILE_NAME='YWD Builder WiFi'

[[ -r "$ENV_FILE" ]] || exit 0
# shellcheck disable=SC1090
source "$ENV_FILE"

WIFI_SSID="${WIFI_SSID:-}"
WIFI_PASSWORD="${WIFI_PASSWORD:-}"

[[ -n "$WIFI_SSID" ]] || exit 0

nmcli radio wifi on || true

for attempt in $(seq 1 24); do
  nmcli device wifi rescan ifname wlan0 >/dev/null 2>&1 || true

  # Remove only our temporary build-time profile before retrying. Never touch
  # other saved connections that may already exist on the image.
  nmcli connection delete "$PROFILE_NAME" >/dev/null 2>&1 || true

  if [[ -n "$WIFI_PASSWORD" ]]; then
    if nmcli --wait 25 device wifi connect "$WIFI_SSID" \
      password "$WIFI_PASSWORD" ifname wlan0 name "$PROFILE_NAME" >/dev/null 2>&1; then
      rm -f "$ENV_FILE"
      exit 0
    fi
  else
    if nmcli --wait 25 device wifi connect "$WIFI_SSID" \
      ifname wlan0 name "$PROFILE_NAME" >/dev/null 2>&1; then
      rm -f "$ENV_FILE"
      exit 0
    fi
  fi

  sleep 5
done

exit 1
