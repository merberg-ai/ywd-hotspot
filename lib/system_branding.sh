#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-install}"
SOURCE_ROOT="${2:-/opt/ywd-hotspot/app}"
STATE_DIR="/var/lib/ywd-hotspot/private/system-branding"
EXEC_LIST="$STATE_DIR/update-motd-exec.list"
BRANDING_DIR="$SOURCE_ROOT/lib/branding"
CONSOLE_DIR="$SOURCE_ROOT/lib/console"

need_root() {
  if [[ $EUID -ne 0 ]]; then
    exec sudo bash "$0" "$MODE" "$SOURCE_ROOT"
  fi
}

save_originals_once() {
  install -d -o root -g root -m 0700 "$STATE_DIR"
  if [[ ! -f "$STATE_DIR/saved" ]]; then
    for name in issue issue.net motd; do
      if [[ -e "/etc/$name" ]]; then
        cp -a "/etc/$name" "$STATE_DIR/$name.original"
      fi
    done
    : > "$EXEC_LIST"
    if [[ -d /etc/update-motd.d ]]; then
      for f in /etc/update-motd.d/*; do
        [[ -f "$f" && -x "$f" ]] || continue
        basename "$f" >> "$EXEC_LIST"
      done
    fi
    chmod 0600 "$EXEC_LIST"
    printf '%s\n' "saved" > "$STATE_DIR/saved"
    chmod 0600 "$STATE_DIR/saved"
  fi
}

install_console() {
  for f in ywd-system-info.py ywd-info-wrapper.sh ywd-logs.sh ywd-env.sh ywd-prompt.sh ywd-motd.sh; do
    [[ -f "$CONSOLE_DIR/$f" ]] || { echo "[FAIL] Missing $CONSOLE_DIR/$f" >&2; exit 1; }
  done

  install -d -o root -g root -m 0755 /usr/local/libexec /usr/local/bin /etc/profile.d
  install -o root -g root -m 0755 "$CONSOLE_DIR/ywd-system-info.py" /usr/local/libexec/ywd-system-info
  install -o root -g root -m 0755 "$CONSOLE_DIR/ywd-info-wrapper.sh" /usr/local/bin/ywd-info
  ln -sfn ywd-info /usr/local/bin/ywd-services
  ln -sfn ywd-info /usr/local/bin/ywd-build
  install -o root -g root -m 0755 "$CONSOLE_DIR/ywd-logs.sh" /usr/local/bin/ywd-logs

  install -o root -g root -m 0644 "$CONSOLE_DIR/ywd-env.sh" /etc/profile.d/90-ywd-hotspot-env.sh
  install -o root -g root -m 0644 "$CONSOLE_DIR/ywd-prompt.sh" /etc/profile.d/91-ywd-hotspot-prompt.sh
  install -o root -g root -m 0644 "$CONSOLE_DIR/ywd-motd.sh" /etc/profile.d/92-ywd-hotspot-motd.sh

  cat > /etc/ywd-hotspot/console-help.txt <<'EOF'
YWD-Hotspot quick commands

  ywd-info              live appliance summary
  ywd-info --all        summary + services + build provenance
  ywd-info --network    Wi-Fi/IP summary
  ywd-services          compact systemd service status
  ywd-build             app/OS/Git/radio build provenance
  ywd-logs              follow YWD logs
  ywd-logs network      network manager only
  ywd-logs web          dashboard only
  ywd-logs setup        first-boot wizard only
  ywd-logs rf           MMDVM-Host + DMRGateway
  ywd-logs oled         OLED service(s)

Set YWD_KEEP_PROMPT=1 before login to keep your own Bash prompt.
WebUI:  http://ywd-hotspot.local:8080/
GitHub: https://github.com/merberg-ai/ywd-hotspot
EOF
  chmod 0644 /etc/ywd-hotspot/console-help.txt
}

install_branding() {
  [[ -f "$BRANDING_DIR/issue" ]] || { echo "[FAIL] Missing $BRANDING_DIR/issue" >&2; exit 1; }
  [[ -f "$BRANDING_DIR/motd" ]] || { echo "[FAIL] Missing $BRANDING_DIR/motd" >&2; exit 1; }
  save_originals_once

  install -o root -g root -m 0644 "$BRANDING_DIR/issue" /etc/issue
  install -o root -g root -m 0644 "$BRANDING_DIR/issue" /etc/issue.net
  install -o root -g root -m 0644 "$BRANDING_DIR/motd" /etc/motd

  # Suppress distro-generated MOTD fragments so SSH/local logins show the YWD
  # appliance identity instead of a second Debian/Raspberry Pi banner. Original
  # executable state is recorded above and restored by uninstall/restore mode.
  if [[ -d /etc/update-motd.d ]]; then
    find /etc/update-motd.d -maxdepth 1 -type f -exec chmod -x {} + 2>/dev/null || true
  fi
  : > /run/motd.dynamic 2>/dev/null || true
  install_console
}

restore_branding() {
  if [[ -d "$STATE_DIR" ]]; then
    for name in issue issue.net motd; do
      if [[ -e "$STATE_DIR/$name.original" ]]; then
        cp -a "$STATE_DIR/$name.original" "/etc/$name"
      fi
    done

    if [[ -d /etc/update-motd.d ]]; then
      find /etc/update-motd.d -maxdepth 1 -type f -exec chmod -x {} + 2>/dev/null || true
      if [[ -f "$EXEC_LIST" ]]; then
        while IFS= read -r name; do
          [[ -n "$name" && -f "/etc/update-motd.d/$name" ]] || continue
          chmod +x "/etc/update-motd.d/$name"
        done < "$EXEC_LIST"
      fi
      if command -v run-parts >/dev/null 2>&1; then
        run-parts /etc/update-motd.d > /run/motd.dynamic 2>/dev/null || true
      fi
    fi
  fi

  rm -f \
    /usr/local/libexec/ywd-system-info \
    /usr/local/bin/ywd-info /usr/local/bin/ywd-services /usr/local/bin/ywd-build /usr/local/bin/ywd-logs \
    /etc/profile.d/90-ywd-hotspot-env.sh \
    /etc/profile.d/91-ywd-hotspot-prompt.sh \
    /etc/profile.d/92-ywd-hotspot-motd.sh \
    /etc/ywd-hotspot/console-help.txt
}

need_root
case "$MODE" in
  install) install_branding ;;
  restore) restore_branding ;;
  *) echo "usage: system_branding.sh [install|restore] [source-root]" >&2; exit 2 ;;
esac
