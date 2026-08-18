#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-install}"
APP="${YWD_LIVE_APP:-/opt/ywd-hotspot/app}"
DROPIN_DIR=/etc/systemd/system/ywd-headless-oled.service.d
DROPIN="$DROPIN_DIR/50-ywd-unified-renderer.conf"
CONFIG="${YWD_CONFIG:-/etc/ywd-hotspot/config.json}"
LEGACY_UNIT=/etc/systemd/system/ywd-oled.service
DESIRED_EXEC='ExecStart=/usr/bin/python3 /opt/ywd-hotspot/app/lib/oled.py --os-owner'

headless_exists(){ systemctl cat ywd-headless-oled.service >/dev/null 2>&1; }

display_enabled(){
  python3 - "$CONFIG" <<'PY'
import json,sys
try:
    cfg=json.load(open(sys.argv[1]))
    print('1' if cfg.get('display',{}).get('enabled',True) else '0')
except Exception:
    print('1')
PY
}

retire_legacy(){
  local changed=0
  # Only touch the legacy unit if it actually exists. Normal Settings applies on
  # a migrated YWD-Hotspot OS should not pay for a second daemon-reload.
  if [[ -e "$LEGACY_UNIT" || -L "$LEGACY_UNIT" ]]; then
    systemctl disable ywd-oled.service >/dev/null 2>&1 || true
    systemctl stop --no-block ywd-oled.service >/dev/null 2>&1 || true
    sleep 0.10
    systemctl kill --kill-who=all --signal=KILL ywd-oled.service >/dev/null 2>&1 || true
    systemctl reset-failed ywd-oled.service >/dev/null 2>&1 || true
    rm -f "$LEGACY_UNIT"
    changed=1
  fi
  return "$changed"
}

stop_headless_fast(){
  systemctl stop --no-block ywd-headless-oled.service >/dev/null 2>&1 || true
  sleep 0.10
  systemctl kill --kill-who=all --signal=KILL ywd-headless-oled.service >/dev/null 2>&1 || true
  systemctl reset-failed ywd-headless-oled.service >/dev/null 2>&1 || true
}

install_owner(){
  if ! headless_exists; then
    return 0
  fi
  [[ -f "$APP/lib/oled.py" ]] || {
    echo "canonical OLED renderer is missing: $APP/lib/oled.py" >&2
    exit 1
  }

  local reload_needed=0
  local desired
  desired=$'[Service]\nExecStart=\n'"$DESIRED_EXEC"$'\n'

  # Install/reload the owner wiring only when it actually changed. daemon-reload
  # is comparatively expensive on a Pi Zero and must not run twice on every OLED
  # presentation change.
  if [[ ! -f "$DROPIN" ]] || [[ "$(cat "$DROPIN" 2>/dev/null || true)"$'\n' != "$desired" ]]; then
    install -d -m 0755 "$DROPIN_DIR"
    printf '%s' "$desired" >"$DROPIN"
    chmod 0644 "$DROPIN"
    reload_needed=1
  fi

  if [[ -e "$LEGACY_UNIT" || -L "$LEGACY_UNIT" ]]; then
    retire_legacy || true
    reload_needed=1
  fi

  if (( reload_needed )); then
    systemctl daemon-reload
  fi

  if [[ "$(display_enabled)" == "1" ]]; then
    systemctl enable ywd-headless-oled.service >/dev/null 2>&1 || true
    stop_headless_fast
    systemctl start --no-block ywd-headless-oled.service >/dev/null
  else
    systemctl disable ywd-headless-oled.service >/dev/null 2>&1 || true
    stop_headless_fast
  fi
}

restore_owner(){
  if [[ -f "$DROPIN" ]]; then
    rm -f "$DROPIN"
    rmdir "$DROPIN_DIR" 2>/dev/null || true
    systemctl daemon-reload
    if headless_exists; then
      stop_headless_fast
      systemctl start --no-block ywd-headless-oled.service >/dev/null 2>&1 || true
    fi
  fi
}

case "$ACTION" in
  install) install_owner ;;
  restore) restore_owner ;;
  retire-legacy)
    if [[ -e "$LEGACY_UNIT" || -L "$LEGACY_UNIT" ]]; then
      retire_legacy || true
      systemctl daemon-reload
    fi
    ;;
  *) echo "usage: oled_owner.sh install|restore|retire-legacy" >&2; exit 2 ;;
esac
