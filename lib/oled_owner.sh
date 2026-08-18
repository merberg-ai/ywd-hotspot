#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-install}"
# The physical OS owner must always execute the deployed live application.
# Never persist a GitHub update staging path in a systemd drop-in.
APP="${YWD_LIVE_APP:-/opt/ywd-hotspot/app}"
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

retire_legacy(){
  # ywd-oled.service is never the physical owner on YWD-Hotspot OS. Do not use
  # `disable --now` here: an I2C-stuck Python process can make systemctl wait for
  # the unit stop timeout and abort a WebUI Settings apply. Disable boot policy,
  # queue a non-blocking stop, then forcibly release the legacy process/I2C fd.
  systemctl disable ywd-oled.service >/dev/null 2>&1 || true
  systemctl stop --no-block ywd-oled.service >/dev/null 2>&1 || true
  sleep 0.10
  systemctl kill --kill-who=all --signal=KILL ywd-oled.service >/dev/null 2>&1 || true
  systemctl reset-failed ywd-oled.service >/dev/null 2>&1 || true
}

stop_headless_fast(){
  systemctl stop --no-block ywd-headless-oled.service >/dev/null 2>&1 || true
  sleep 0.10
  systemctl kill --kill-who=all --signal=KILL ywd-headless-oled.service >/dev/null 2>&1 || true
  systemctl reset-failed ywd-headless-oled.service >/dev/null 2>&1 || true
}

install_owner(){
  # Generic installs continue to use ywd-oled.service. YWD-Hotspot OS already
  # owns the physical SSD1306 with ywd-headless-oled.service; point that sole
  # owner at the deployed canonical renderer and keep the duplicate app unit off.
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

  # Reload the corrected live path BEFORE touching either process. Even if a
  # legacy renderer is wedged, systemd now knows the authoritative ExecStart.
  systemctl daemon-reload
  retire_legacy

  if [[ "$(display_enabled)" == "1" ]]; then
    systemctl enable ywd-headless-oled.service >/dev/null
    # Avoid a blocking restart if the old renderer is stuck in an I2C syscall.
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
