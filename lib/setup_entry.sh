#!/usr/bin/env bash
set -euo pipefail

# M3 owns network onboarding. Do not expose the M4 appliance wizard until wlan0
# has handed off from the temporary 10.42.0.1 setup AP to a normal station IP.
while true; do
  ip="$(ip -4 -o addr show dev wlan0 scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1 || true)"
  if [[ -n "$ip" && "$ip" != "10.42.0.1" ]]; then
    break
  fi
  sleep 3
done

exec /usr/bin/python3 /opt/ywd-hotspot/app/lib/setup_server.py
