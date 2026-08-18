#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-install}"
# The physical OS owner must always execute the deployed live application.
# Never persist a GitHub update staging path in a systemd drop-in.
APP="${YWD_LIVE_APP:-/opt/ywd-hotspot/app}"
DROPIN_DIR=/etc/systemd/system/ywd-headless-oled.service.d
DROPIN="$DROPIN_DIR/50-ywd-unified-renderer.conf"
CONFIG="${YWD_CONFIG:-/etc/ywd-hotspot/config.json}"
LEGACY_UNIT=/etc/systemd/system/ywd-oled.service

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
  # ywd-oled.service is never the physical owner on YWD-Hotspot OS. Never let
  # an I2C-stuck legacy process block Settings or update completion.
  systemctl disable ywd-oled.service >/dev/null 2>&1 || true
  systemctl stop --no-block ywd-oled.service >/dev/null 2>&1 || true
  sleep 0.10
  systemctl kill --kill-who=all --signal=KILL ywd-oled.service >/dev/null 2>&1 || true
  systemctl reset-failed ywd-oled.service >/dev/null 2>&1 || true

  # On the appliance OS the legacy unit is not merely disabled: remove the live
  # installed unit so obsolete cleanup paths fail immediately instead of ever
  # waiting on it. Generic installs never enter this helper because they have no
  # ywd-headless-oled.service and continue to use ywd-oled.service normally.
  rm -f "$LEGACY_UNIT"
  systemctl daemon-reload
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

  install -d -m 0755 "$DROPIN_DIR"
  cat >"$DROPIN" <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/python3 /opt/ywd-hotspot/app/lib/oled.py --os-owner
EOF
  chmod 0644 "$DROPIN"

  # Reload the corrected live path before touching either process.
  systemctl daemon-reload
  retire_legacy

  if [[ "$(display_enabled)" == "1" ]]; then
    systemctl enable ywd-headless-oled.service >/dev/null
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
  retire-legacy) retire_legacy ;;
  *) echo "usage: oled_owner.sh install|restore|retire-legacy" >&2; exit 2 ;;
esac
