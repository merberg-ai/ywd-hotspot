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
  # This renderer is presentation-only and has no state to flush. Keep the
  # Settings-driven stop window short so its normal system-shutdown splash
  # cannot linger during a display restart/disable.
  sleep 0.03
  systemctl kill --kill-who=all --signal=KILL ywd-headless-oled.service >/dev/null 2>&1 || true
  systemctl reset-failed ywd-headless-oled.service >/dev/null 2>&1 || true
}

power_off_panel(){
  # Guarantee SSD1306 display-off after a Settings-driven disable. This sends
  # only the display-off command (0xAE); it does not initialize or redraw the
  # panel, so the shutdown screen cannot remain visible after the service dies.
  python3 - "$CONFIG" <<'PY' >/dev/null 2>&1 || true
import json,sys
try:
    import smbus
    cfg=json.load(open(sys.argv[1]))
    d=cfg.get('display',{}) if isinstance(cfg,dict) else {}
    bus=int(d.get('i2c_bus',1))
    addr=int(str(d.get('address','0x3c')),0)
    dev=smbus.SMBus(bus)
    dev.write_byte_data(addr,0x00,0xAE)
except Exception:
    pass
PY
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
    power_off_panel
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
