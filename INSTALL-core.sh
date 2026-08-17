#!/usr/bin/env bash
set -euo pipefail
umask 027
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(cat "$SELF/VERSION" 2>/dev/null || echo unknown)"
REPO_URL="https://github.com/merberg-ai/ywd-hotspot.git"
REPO_DIR="/opt/ywd-hotspot/repo"
source "$SELF/pins.env"
if [[ $EUID -ne 0 ]]; then exec sudo "$0" "$@"; fi

if [[ -f /etc/ywd-hotspot/config.json && -d /opt/ywd-hotspot/app ]] && [[ "${YWD_INSTALL_RECOVERY:-0}" != "1" ]]; then
  cat <<'EOF'
============================================================
 Existing YWD-Hotspot installation detected
============================================================
  1) Adopt existing installation and switch to GitHub updates
     - preserves configuration, credentials, calibration data and RF state
     - does NOT rebuild MMDVM-Host or DMRGateway

  2) Full/recovery installation
     - runs the complete installer and may rebuild pinned upstream binaries

  3) Cancel
EOF
  read -r -p "Selection [1-3]: " existing_choice
  case "$existing_choice" in
    1) exec "$SELF/MIGRATE-TO-GITHUB.sh";;
    2) echo "Continuing with full/recovery installation...";;
    *) echo "Cancelled."; exit 0;;
  esac
fi

cat <<EOF
============================================================
 YWD-Hotspot $VERSION installer
 GitHub Integration + About
============================================================
EOF
MODEL="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || true)"
echo "Hardware: ${MODEL:-unknown}"
echo "Kernel  : $(uname -a)"
if [[ "$MODEL" != *"Raspberry Pi"* ]]; then echo "[FAIL] Raspberry Pi hardware expected."; exit 1; fi
if [[ ! -e /dev/serial0 ]]; then echo "[FAIL] /dev/serial0 missing. Run lab/mmdvm-diag.sh first."; exit 1; fi
SERIAL_REAL="$(readlink -f /dev/serial0 || true)"; echo "UART    : /dev/serial0 -> $SERIAL_REAL"
if [[ "$MODEL" == *"Zero W"* && "$SERIAL_REAL" != "/dev/ttyAMA0" ]]; then echo "[FAIL] Zero W target expects PL011 /dev/ttyAMA0. Run sudo ./lab/mmdvm-diag.sh, option 5, reboot."; exit 1; fi

echo; echo "Read-only MMDVM GET_VERSION probe..."
python3 - <<'PY'
import os,termios,time,sys
dev='/dev/serial0'; fd=os.open(dev,os.O_RDWR|os.O_NOCTTY); a=termios.tcgetattr(fd); a[0]=a[1]=a[3]=0; a[2]=termios.CLOCAL|termios.CREAD|termios.CS8; a[4]=a[5]=termios.B115200; a[6][termios.VMIN]=0; a[6][termios.VTIME]=10; termios.tcsetattr(fd,termios.TCSANOW,a); termios.tcflush(fd,termios.TCIOFLUSH); os.write(fd,bytes([0xE0,0x03,0x00])); time.sleep(.25); data=os.read(fd,256); os.close(fd)
if b'MMDVM' not in data: print('[FAIL] Modem did not return recognizable MMDVM version.'); sys.exit(1)
print('[ OK ]',' '.join(data.decode('ascii','ignore').replace('\0',' ').split()))
PY

echo; echo "Installing build/runtime dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends build-essential git ca-certificates openssl libmosquitto-dev libmosquitto1 nlohmann-json3-dev python3 python3-smbus i2c-tools iw sudo
[[ -r /usr/include/nlohmann/json.hpp ]] || { echo "[FAIL] nlohmann/json.hpp missing."; exit 1; }
command -v openssl >/dev/null 2>&1 || { echo "[FAIL] openssl is required for YWD settings backups/plugin signatures."; exit 1; }

if ! id ywd-hotspot >/dev/null 2>&1; then useradd --system --home /var/lib/ywd-hotspot --create-home --shell /usr/sbin/nologin ywd-hotspot; fi
for g in dialout i2c systemd-journal; do getent group "$g" >/dev/null 2>&1 && usermod -a -G "$g" ywd-hotspot || true; done
install -d -m 0755 /opt/ywd-hotspot/src /opt/ywd-hotspot/app /usr/local/libexec
install -d -o root -g ywd-hotspot -m 0750 /etc/ywd-hotspot
install -d -o ywd-hotspot -g ywd-hotspot -m 0750 /var/lib/ywd-hotspot /var/lib/ywd-hotspot/diagnostics
install -d -o root -g root -m 0700 /var/lib/ywd-hotspot/private /var/lib/ywd-hotspot/private/config-history

build_repo(){
  local name="$1" repo="$2" pin="$3" binary="$4" dir="/opt/ywd-hotspot/src/$1"
  echo; echo "------------------------------------------------------------"; echo "Building $name @ $pin"
  if [[ -d "$dir/.git" ]] && [[ "$(git -C "$dir" rev-parse HEAD 2>/dev/null || true)" == "$pin" ]]; then echo "Reusing $dir"; else rm -rf "$dir"; git clone "$repo" "$dir"; git -C "$dir" checkout --detach "$pin"; fi
  (cd "$dir" && make -j1); install -m 0755 "$dir/$binary" "/usr/local/bin/$binary"
}
build_repo "MMDVM-Host" "$MMDVM_HOST_REPO" "$MMDVM_HOST_COMMIT" "MMDVM-Host"
build_repo "DMRGateway" "$DMR_GATEWAY_REPO" "$DMR_GATEWAY_COMMIT" "DMRGateway"

echo; echo "Installing YWD-Hotspot application..."
rm -rf /opt/ywd-hotspot/app
install -d -m 0755 /opt/ywd-hotspot/app
# Copy only appliance/runtime source. A Git checkout may contain a large .git
# database plus repository docs/artwork that do not belong in /opt. Keep each
# presentation wrapper next to its core implementation in the deployed app.
for item in \
  bin lib web systemd sudoers lab \
  INSTALL.sh INSTALL-core.sh UPDATE.sh UPDATE-core.sh UNINSTALL.sh \
  GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh \
  VERSION pins.env README.md MANIFEST.txt; do
  cp -a "$SELF/$item" /opt/ywd-hotspot/app/
done

# Ship only the small WebP badge to the appliance; keep the large master artwork
# in the repository rather than wasting Pi storage/runtime backups.
install -d -m 0755 /opt/ywd-hotspot/app/assets/branding
install -m 0644 "$SELF/assets/branding/ywd-hotspot-badge-256.webp" /opt/ywd-hotspot/app/assets/branding/ywd-hotspot-badge-256.webp

chmod +x \
  /opt/ywd-hotspot/app/INSTALL.sh /opt/ywd-hotspot/app/INSTALL-core.sh \
  /opt/ywd-hotspot/app/UPDATE.sh /opt/ywd-hotspot/app/UPDATE-core.sh /opt/ywd-hotspot/app/UNINSTALL.sh \
  /opt/ywd-hotspot/app/GITHUB-UPDATE.sh /opt/ywd-hotspot/app/GITHUB-UPDATE-core.sh \
  /opt/ywd-hotspot/app/MIGRATE-TO-GITHUB.sh /opt/ywd-hotspot/app/MIGRATE-TO-GITHUB-core.sh \
  /opt/ywd-hotspot/app/bin/ywd-hotspotctl /opt/ywd-hotspot/app/bin/ywd-hotspotctl-core \
  /opt/ywd-hotspot/app/bin/ywd-ui.sh /opt/ywd-hotspot/app/lib/*.py /opt/ywd-hotspot/app/lab/mmdvm-diag.sh
install -m 0755 /opt/ywd-hotspot/app/bin/ywd-hotspotctl /usr/local/sbin/ywd-hotspotctl
install -o root -g root -m 0755 /opt/ywd-hotspot/app/lib/admin.py /usr/local/libexec/ywd-hotspot-admin
install -o root -g root -m 0440 "$SELF/sudoers/ywd-hotspot" /etc/sudoers.d/ywd-hotspot
command -v visudo >/dev/null && visudo -cf /etc/sudoers.d/ywd-hotspot >/dev/null
for unit in "$SELF"/systemd/*.service "$SELF"/systemd/*.timer; do install -m 0644 "$unit" "/etc/systemd/system/$(basename "$unit")"; done
systemctl daemon-reload

if [[ ! -f /etc/ywd-hotspot/config.json ]]; then python3 /opt/ywd-hotspot/app/lib/configure.py; else
  python3 /opt/ywd-hotspot/app/lib/migrate.py
  read -r -p "Existing config found. Re-run configuration wizard? [y/N]: " a
  [[ "$a" =~ ^[Yy]$ ]] && python3 /opt/ywd-hotspot/app/lib/configure.py || python3 /opt/ywd-hotspot/app/lib/generate-config.py
fi

# Record provenance for the dashboard/About page.
python3 /opt/ywd-hotspot/app/lib/build_info.py write --source-dir "$SELF" >/dev/null

# A fresh install launched from a Git checkout becomes GitHub-managed
# automatically. The live runtime remains a clean copy in /opt/ywd-hotspot/app.
if git -C "$SELF" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  source_origin="$(git -C "$SELF" remote get-url origin 2>/dev/null || true)"
  case "$source_origin" in
    "$REPO_URL"|"https://github.com/merberg-ai/ywd-hotspot"|"git@github.com:merberg-ai/ywd-hotspot.git")
      if [[ ! -d "$REPO_DIR/.git" ]]; then
        rm -rf "$REPO_DIR"
        git clone --quiet "$REPO_URL" "$REPO_DIR"
      fi
      source_sha="$(git -C "$SELF" rev-parse HEAD)"
      source_branch="$(git -C "$SELF" branch --show-current)"
      [[ -n "$source_branch" ]] || source_branch=main
      if git -C "$REPO_DIR" cat-file -e "$source_sha^{commit}" 2>/dev/null; then
        git -C "$REPO_DIR" checkout --quiet -B "$source_branch" "$source_sha"
        git -C "$REPO_DIR" branch --set-upstream-to="origin/$source_branch" "$source_branch" >/dev/null 2>&1 || true
      fi
      ;;
  esac
fi

echo; echo "Initial DMR ID database update (non-fatal if offline)..."
python3 /opt/ywd-hotspot/app/lib/id-update.py --force || echo "[WARN] RadioID update failed; retry later."

# Persistent journal remains enabled by default so crash evidence survives hard resets.
read -r JOURNAL_ENABLED JOURNAL_MB < <(python3 - <<'PY'
import json
c=json.load(open('/etc/ywd-hotspot/config.json')); m=c.get('maintenance',{})
print(1 if m.get('persistent_journal',True) else 0, int(m.get('journal_max_mb',100)))
PY
)
if [[ "$JOURNAL_ENABLED" == 1 ]]; then
  install -d -m 0755 /var/log/journal /etc/systemd/journald.conf.d
  cat > /etc/systemd/journald.conf.d/10-ywd-hotspot-persistent.conf <<EOF
[Journal]
Storage=persistent
SystemMaxUse=${JOURNAL_MB}M
RuntimeMaxUse=50M
EOF
else
  install -d -m 0755 /etc/systemd/journald.conf.d
  cat > /etc/systemd/journald.conf.d/10-ywd-hotspot-persistent.conf <<'EOF'
[Journal]
Storage=volatile
RuntimeMaxUse=50M
EOF
fi
systemctl restart systemd-journald.service || true

systemctl enable --now ywd-activity.service ywd-dashboard.service ywd-dmrid-update.timer
OLED_ENABLED="$(python3 - <<'PY'
import json; print(1 if json.load(open('/etc/ywd-hotspot/config.json')).get('display',{}).get('enabled',True) else 0)
PY
)"
OLED_SCAN="$(i2cdetect -y 1 2>/dev/null || true)"
if [[ "$OLED_ENABLED" == 1 ]] && grep -Eq '(^|[[:space:]])3c([[:space:]]|$)' <<<"$OLED_SCAN"; then systemctl enable --now ywd-oled.service; else systemctl disable --now ywd-oled.service 2>/dev/null || true; fi

cat <<'EOF'
============================================================
 RF ENABLE CONFIRMATION
============================================================
Starting MMDVM-Host can transmit RF when network traffic arrives.
Attach a suitable antenna and verify the configured frequency.
EOF
read -r -p "Type ENABLE-RF to start AND enable RF at boot now: " rf
if [[ "$rf" == "ENABLE-RF" ]]; then
  python3 - <<'PY'
import json,os
from pathlib import Path
p=Path('/etc/ywd-hotspot/config.json'); c=json.load(open(p)); c.setdefault('maintenance',{})['rf_autostart']=True; t=p.with_suffix('.tmp'); t.write_text(json.dumps(c,indent=2)+'\n'); os.chmod(t,0o640)
try:
 import grp; os.chown(t,0,grp.getgrnam('ywd-hotspot').gr_gid)
except Exception: pass
os.replace(t,p)
PY
  systemctl enable --now ywd-mmdvmhost.service; sleep 2; systemctl enable --now ywd-dmrgateway.service
else
  systemctl disable --now ywd-dmrgateway.service ywd-mmdvmhost.service 2>/dev/null || true
  echo "RF path left stopped/disabled."
fi
python3 /opt/ywd-hotspot/app/lib/generate-config.py
/usr/local/libexec/ywd-hotspot-admin init-applied >/dev/null

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"; PORT="$(python3 -c "import json;print(json.load(open('/etc/ywd-hotspot/config.json'))['web']['port'])")"
cat <<EOF
============================================================
 Installation complete
============================================================
Dashboard : http://${IP:-PI-IP}:$PORT/
Control   : sudo ywd-hotspotctl
Status    : ywd-hotspotctl status
Source    : ywd-hotspotctl source
Updates   : sudo ywd-hotspotctl update --check

Web WRITE controls are locked until you set a local control password:
  sudo ywd-hotspotctl web-password
BrandMeister TG controls also require:
  sudo ywd-hotspotctl bm-api-key
EOF
ywd-hotspotctl status || true
