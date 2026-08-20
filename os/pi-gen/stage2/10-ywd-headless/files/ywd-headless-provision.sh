#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=/etc/ywd-headless/provision.env
PROFILE_NAME='YWD Builder WiFi'

[[ -r "$ENV_FILE" ]] || exit 0
# shellcheck disable=SC1090
source "$ENV_FILE"

WIFI_SSID="${WIFI_SSID:-}"
WIFI_PASSWORD="${WIFI_PASSWORD:-}"
WIFI_HIDDEN="${WIFI_HIDDEN:-0}"

[[ -n "$WIFI_SSID" ]] || exit 0

nmcli radio wifi on || true

for attempt in $(seq 1 24); do
  if [[ "$WIFI_HIDDEN" == "1" ]]; then
    nmcli device wifi rescan ifname wlan0 ssid "$WIFI_SSID" >/dev/null 2>&1 || true
  else
    nmcli device wifi rescan ifname wlan0 >/dev/null 2>&1 || true
  fi

  # Remove only our temporary build-time profile before retrying. Never touch
  # other saved connections that may already exist on the image.
  nmcli connection delete "$PROFILE_NAME" >/dev/null 2>&1 || true

  args=(nmcli --wait 25 device wifi connect "$WIFI_SSID")
  if [[ -n "$WIFI_PASSWORD" ]]; then
    args+=(password "$WIFI_PASSWORD")
  fi
  args+=(ifname wlan0 name "$PROFILE_NAME")
  if [[ "$WIFI_HIDDEN" == "1" ]]; then
    args+=(hidden yes)
  fi

  if "${args[@]}" >/dev/null 2>&1; then
    rm -f "$ENV_FILE"
    exit 0
  fi

  sleep 5
done

exit 1
