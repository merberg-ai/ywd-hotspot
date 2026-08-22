#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-install}"
APP="${2:-${YWD_LIVE_APP:-/opt/ywd-hotspot/app}}"
DROPIN_DIR=/etc/systemd/system/ywd-headless-oled.service.d
DROPIN="$DROPIN_DIR/50-ywd-unified-renderer.conf"
CONFIG="${YWD_CONFIG:-/etc/ywd-hotspot/config.json}"
LEGACY_UNIT=/etc/systemd/system/ywd-oled.service
DESIRED_EXEC='ExecStart=/usr/bin/python3 /opt/ywd-hotspot/app/lib/oled.py --os-owner'

headless_exists(){ timeout 5s systemctl cat ywd-headless-oled.service >/dev/null 2>&1; }

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

power_off_panel(){
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

queue_reconcile(){
  local enabled="$1"
  local unit="ywd-oled-reconcile-$(date +%s)-$$"
  local script

  if [[ "$enabled" == "1" ]]; then
    script='set -e
systemctl daemon-reload
systemctl disable ywd-oled.service >/dev/null 2>&1 || true
systemctl stop --no-block ywd-oled.service >/dev/null 2>&1 || true
systemctl kill --kill-who=all --signal=KILL ywd-oled.service >/dev/null 2>&1 || true
systemctl enable ywd-headless-oled.service >/dev/null 2>&1 || true
systemctl stop --no-block ywd-headless-oled.service >/dev/null 2>&1 || true
sleep 0.05
systemctl kill --kill-who=all --signal=KILL ywd-headless-oled.service >/dev/null 2>&1 || true
systemctl reset-failed ywd-headless-oled.service >/dev/null 2>&1 || true
systemctl start --no-block ywd-headless-oled.service >/dev/null 2>&1 || true'
  else
    script='set -e
systemctl daemon-reload
systemctl disable ywd-oled.service >/dev/null 2>&1 || true
systemctl stop --no-block ywd-oled.service >/dev/null 2>&1 || true
systemctl kill --kill-who=all --signal=KILL ywd-oled.service >/dev/null 2>&1 || true
systemctl disable ywd-headless-oled.service >/dev/null 2>&1 || true
systemctl stop --no-block ywd-headless-oled.service >/dev/null 2>&1 || true
sleep 0.05
systemctl kill --kill-who=all --signal=KILL ywd-headless-oled.service >/dev/null 2>&1 || true
systemctl reset-failed ywd-headless-oled.service >/dev/null 2>&1 || true'
  fi

  # Presentation-only service reconciliation must never hold a settings/restore
  # HTTP request open on a Pi Zero. Queue it as a transient root job and return.
  timeout 8s systemd-run \
    --quiet --collect --no-block \
    --unit "$unit" \
    /bin/bash -c "$script" >/dev/null
}

install_owner(){
  if ! headless_exists; then
    return 0
  fi
  [[ -f "$APP/lib/oled.py" ]] || {
    echo "canonical OLED renderer is missing: $APP/lib/oled.py" >&2
    exit 1
  }

  local desired
  desired=$'[Service]\nExecStart=\n'"$DESIRED_EXEC"$'\n'

  install -d -m 0755 "$DROPIN_DIR"
  if [[ ! -f "$DROPIN" ]] || [[ "$(cat "$DROPIN" 2>/dev/null || true)"$'\n' != "$desired" ]]; then
    printf '%s' "$desired" >"$DROPIN"
    chmod 0644 "$DROPIN"
  fi

  # Remove the legacy unit file immediately so a later daemon-reload cannot
  # resurrect a second OLED owner. Any running legacy process is killed by the
  # detached reconcile job.
  rm -f "$LEGACY_UNIT"

  local enabled
  enabled="$(display_enabled)"
  queue_reconcile "$enabled"
  if [[ "$enabled" != "1" ]]; then
    power_off_panel
  fi
}

restore_owner(){
  rm -f "$DROPIN"
  rmdir "$DROPIN_DIR" 2>/dev/null || true
  if headless_exists; then
    queue_reconcile 1
  fi
}

retire_legacy(){
  rm -f "$LEGACY_UNIT"
  if headless_exists; then
    queue_reconcile "$(display_enabled)"
  fi
}

case "$ACTION" in
  install) install_owner ;;
  restore) restore_owner ;;
  retire-legacy) retire_legacy ;;
  *) echo "usage: oled_owner.sh install|restore|retire-legacy" >&2; exit 2 ;;
esac
