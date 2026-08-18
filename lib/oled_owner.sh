#!/usr/bin/env bash
set -euo pipefail

APP="${2:-/opt/ywd-hotspot/app}"
ACTION="${1:-install}"
DROPIN_DIR=/etc/systemd/system/ywd-headless-oled.service.d
DROPIN="$DROPIN_DIR/50-ywd-unified-renderer.conf"
CONFIG="${YWD_CONFIG:-/etc/ywd-hotspot/config.json}"

headless_exists(){ systemctl cat ywd-headless-oled.service >/dev/null 2>&1; }

display_enabled(){
  python3 - "$CONFIG" <<'PY'
import json,sys
try:
    cfg=json.load(open(sys.argv[1]))
    print('1' if cfg.get('display',{}).get('enabled',True) else '0')
except Exception:
    # Preserve historical fail-open display behavior if config is temporarily
    # unreadable; core config validation owns malformed-config handling.
    print('1')
PY
}

install_owner(){
  # Generic installs continue to use ywd-oled.service. YWD-Hotspot OS already
  # owns the physical SSD1306 with ywd-headless-oled.service; point that sole
  # owner at the unified renderer and explicitly keep the duplicate app unit off.
  if ! headless_exists; then
    return 0
  fi
  install -d -m 0755 "$DROPIN_DIR"
  cat >"$DROPIN" <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/python3 ${APP}/lib/oled.py --os-owner
EOF
  chmod 0644 "$DROPIN"
  systemctl disable --now ywd-oled.service >/dev/null 2>&1 || true
  systemctl daemon-reload

  if [[ "$(display_enabled)" == "1" ]]; then
    # Alpha18.2.1: START is not enough here. Persist the canonical
    # display.enabled intent into systemd so the physical owner survives reboot.
    systemctl enable ywd-headless-oled.service >/dev/null
    if systemctl is-active --quiet ywd-headless-oled.service; then
      systemctl restart ywd-headless-oled.service
    else
      systemctl start ywd-headless-oled.service
    fi
  else
    systemctl disable --now ywd-headless-oled.service >/dev/null 2>&1 || true
  fi
}

restore_owner(){
  if [[ -f "$DROPIN" ]]; then
    rm -f "$DROPIN"
    rmdir "$DROPIN_DIR" 2>/dev/null || true
    systemctl daemon-reload
    if headless_exists; then
      systemctl restart ywd-headless-oled.service >/dev/null 2>&1 || true
    fi
  fi
}

case "$ACTION" in
  install) install_owner ;;
  restore) restore_owner ;;
  *) echo "usage: oled_owner.sh install|restore [APP]" >&2; exit 2 ;;
esac
