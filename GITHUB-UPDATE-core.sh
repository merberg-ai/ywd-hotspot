#!/usr/bin/env bash
set -euo pipefail
umask 027

REPO_URL="https://github.com/merberg-ai/ywd-hotspot.git"
REPO_DIR="/opt/ywd-hotspot/repo"
BUILD_INFO="/etc/ywd-hotspot/build-info.json"
CHANNEL_FILE="/etc/ywd-hotspot/update-channel"
MODE="update"
BRANCH="main"
BRANCH_EXPLICIT=0
TAG=""

if [[ $EUID -ne 0 ]]; then exec sudo bash "$0" "$@"; fi

usage(){
  cat <<'EOF'
Usage: GITHUB-UPDATE.sh [--check|--dry-run] [--branch NAME|--tag TAG]

  --check       Fetch metadata and report whether an update is available.
  --dry-run     Fetch and validate the candidate without changing the live install.
  --branch NAME Update from a branch. A successful main/dev/dev-plugins update becomes the saved channel.
  --tag TAG     Update to a specific tag without changing the saved update channel.

With no --branch/--tag, the saved update channel is used. If no channel file
exists yet, the current managed-checkout branch is used, then main as fallback.
EOF
}

while (($#)); do
  case "$1" in
    --check) MODE="check";;
    --dry-run) MODE="dry-run";;
    --branch) shift; BRANCH="${1:-}"; [[ -n "$BRANCH" ]] || { echo "[FAIL] --branch requires a name"; exit 2; }; BRANCH_EXPLICIT=1; TAG="";;
    --tag) shift; TAG="${1:-}"; [[ -n "$TAG" ]] || { echo "[FAIL] --tag requires a tag"; exit 2; };;
    -h|--help) usage; exit 0;;
    *) echo "[FAIL] Unknown argument: $1"; usage; exit 2;;
  esac
  shift
done

command -v git >/dev/null 2>&1 || { echo "[FAIL] git is not installed."; exit 1; }
command -v flock >/dev/null 2>&1 || { echo "[FAIL] flock is unavailable (util-linux is required)."; exit 1; }
[[ -f /etc/ywd-hotspot/config.json ]] || { echo "[FAIL] No existing YWD-Hotspot installation found."; exit 1; }
[[ -d "$REPO_DIR/.git" ]] || {
  echo "[FAIL] GitHub-managed checkout not found at $REPO_DIR"
  echo "       Run MIGRATE-TO-GITHUB.sh once to adopt the existing installation."
  exit 1
}

exec 9>/run/ywd-hotspot-update.lock
flock -n 9 || { echo "[FAIL] Another YWD-Hotspot update is already running."; exit 1; }

origin="$(git -C "$REPO_DIR" remote get-url origin 2>/dev/null || true)"
case "$origin" in
  "$REPO_URL"|"https://github.com/merberg-ai/ywd-hotspot"|"git@github.com:merberg-ai/ywd-hotspot.git") ;;
  *) echo "[FAIL] Refusing update: unexpected origin '$origin'"; exit 1;;
esac

git -C "$REPO_DIR" config core.fileMode false
if [[ -n "$(git -C "$REPO_DIR" status --porcelain 2>/dev/null)" ]]; then
  echo "[FAIL] $REPO_DIR has local content modifications. Refusing to overwrite them."
  git -C "$REPO_DIR" status --short
  exit 1
fi

saved_channel=""
if [[ -r "$CHANNEL_FILE" ]]; then
  saved_channel="$(tr -d '[:space:]' < "$CHANNEL_FILE" 2>/dev/null || true)"
  case "$saved_channel" in main|dev|dev-plugins) ;; *) saved_channel="";; esac
fi
checkout_branch="$(git -C "$REPO_DIR" branch --show-current 2>/dev/null || true)"
case "$checkout_branch" in main|dev|dev-plugins) ;; *) checkout_branch="";; esac
if [[ -z "$TAG" && "$BRANCH_EXPLICIT" == 0 ]]; then
  BRANCH="${saved_channel:-${checkout_branch:-main}}"
fi
channel_display="${saved_channel:-${checkout_branch:-main}}"

echo "Fetching YWD-Hotspot from GitHub while the live hotspot remains running..."
git -C "$REPO_DIR" fetch --quiet --prune --tags origin

if [[ -n "$TAG" ]]; then
  target_ref="refs/tags/$TAG"
  label="tag:$TAG"
  git -C "$REPO_DIR" show-ref --verify --quiet "$target_ref" || { echo "[FAIL] Tag '$TAG' not found."; exit 1; }
else
  target_ref="refs/remotes/origin/$BRANCH"
  label="$BRANCH"
  git -C "$REPO_DIR" show-ref --verify --quiet "$target_ref" || { echo "[FAIL] Branch '$BRANCH' not found on origin."; exit 1; }
fi

target_sha="$(git -C "$REPO_DIR" rev-parse "$target_ref^{commit}")"
target_short="${target_sha:0:10}"
target_date="$(git -C "$REPO_DIR" show -s --format=%cI "$target_sha")"
target_version="$(git -C "$REPO_DIR" show "$target_sha:VERSION" 2>/dev/null | tr -d '\r\n' || true)"
installed_version="$(cat /opt/ywd-hotspot/app/VERSION 2>/dev/null || echo unknown)"
installed_sha="$(python3 - "$BUILD_INFO" <<'PY'
import json,sys
try: print(json.load(open(sys.argv[1])).get('commit','unknown'))
except Exception: print('unknown')
PY
)"
installed_short="${installed_sha:0:10}"
[[ "$installed_sha" == "unknown" || -z "$installed_sha" ]] && installed_short="unknown"

cat <<EOF
Installed : $installed_version
Commit    : $installed_short
Target    : ${target_version:-unknown}
Source    : $label @ $target_short
Channel   : $channel_display
Date      : $target_date
EOF

if [[ "$installed_sha" == "$target_sha" && "$installed_version" == "$target_version" ]]; then
  echo "Status    : up to date"
  exit 0
fi

echo "Status    : update available"
[[ "$MODE" == "check" ]] && exit 0

stage="$(mktemp -d /opt/ywd-hotspot/.update-stage.XXXXXX)"
cleanup(){ rm -rf "$stage"; }
trap cleanup EXIT

git -C "$REPO_DIR" archive "$target_sha" | tar -x -C "$stage"

required=(
  VERSION INSTALL.sh INSTALL-core.sh UPDATE.sh UPDATE-core.sh UNINSTALL.sh
  GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh
  bin/ywd-hotspotctl bin/ywd-hotspotctl-core bin/ywd-ui.sh lab/mmdvm-diag.sh
  lib/dashboard.py lib/dashboard_core.py lib/dashboard_update.py lib/admin.py lib/update_admin.py lib/update_runner.py
  lib/build_info.py lib/generate-config.py lib/migrate.py lib/config_model.py lib/oled.py lib/oled_owner.sh
  web/index.html web/app.js web/app-core.js web/talkgroups.js web/ui-polish.js web/ui-polish.css web/style.css
  web/update.js web/update.css web/update-progress.js
  web/instrumentation.js web/instrumentation-bootstrap.js web/instrumentation.css
  sudoers/ywd-hotspot systemd/ywd-mmdvmhost.service systemd/ywd-dmrgateway.service
  systemd/ywd-dashboard.service systemd/ywd-activity.service systemd/ywd-oled.service systemd/ywd-update.service
  assets/branding/ywd-hotspot-badge-256.webp
)
plugin_target=0
if [[ -z "$TAG" && "$BRANCH" == "dev-plugins" ]]; then
  plugin_target=1
  required+=(
    lib/dashboard_plugins.py lib/dashboard_plugin_upload.py lib/dashboard_backup.py
    lib/plugin_admin.py lib/plugin_admin_common.py lib/plugin_admin_upload.py lib/admin_dispatch.sh
    lib/plugin_manifest.py lib/plugin_manager.py lib/plugin_package_manager.py lib/plugin_package_archive.py
    lib/plugin_catalog_overlay.py lib/plugin_service_manager.py lib/plugin_service_runner.py lib/plugin_update_safety.py
    lib/settings_backup.py lib/settings_admin.py lib/setup_restore_server.py lib/setup_entry.sh
    lib/plugin_packages/system-info/plugin.json lib/plugin_packages/system-info/config.schema.json
    lib/service_plugin_packages/service-heartbeat/plugin.json
    lib/service_plugin_packages/service-heartbeat/config.schema.json
    lib/service_plugin_packages/service-heartbeat/service.py
    web/plugin-manager-render.js web/plugin-package-actions.js web/plugin-package-upload.js
    web/plugin-manager.js web/plugin-manager.css web/plugin-config-actions.js
    web/backup-restore.js web/backup-restore.css systemd/ywd-plugin@.service
  )
fi
for f in "${required[@]}"; do
  [[ -e "$stage/$f" ]] || { echo "[FAIL] Candidate is missing required file: $f"; exit 1; }
done

for f in UPDATE.sh UPDATE-core.sh INSTALL.sh INSTALL-core.sh GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh UNINSTALL.sh bin/ywd-hotspotctl bin/ywd-hotspotctl-core bin/ywd-ui.sh lab/mmdvm-diag.sh lib/oled_owner.sh; do
  [[ -f "$stage/$f" ]] && bash -n "$stage/$f"
done
if (( plugin_target )); then
  bash -n "$stage/lib/admin_dispatch.sh" "$stage/lib/setup_entry.sh"
fi
python3 -m py_compile "$stage"/lib/*.py

plugin_runtime_target=0
if [[ -f "$stage/lib/plugin_update_safety.py" && -f "$stage/lib/plugin_service_manager.py" && -f "$stage/systemd/ywd-plugin@.service" ]]; then
  plugin_runtime_target=1
fi
if (( plugin_target )); then
  (( plugin_runtime_target )) || { echo "[FAIL] dev-plugins candidate lacks service/update safety runtime"; exit 1; }
  PYTHONPATH="$stage/lib" \
  YWD_PLUGIN_CATALOG="$stage/lib/plugin_packages" \
  YWD_SERVICE_PLUGIN_CATALOG="$stage/lib/service_plugin_packages" \
  YWD_LOCAL_PLUGIN_ROOT="$stage/.plugin-local-does-not-exist" \
  YWD_PLUGIN_TRUST_DIR="$stage/.plugin-trust-does-not-exist" \
  YWD_PLUGIN_STATE="$stage/.plugin-state-does-not-exist" \
  YWD_PLUGIN_CONFIG_DIR="$stage/.plugin-config-does-not-exist" \
  python3 - <<'PY'
import dashboard_backup, dashboard_plugin_upload, dashboard_update
import plugin_catalog_overlay, plugin_package_archive, plugin_service_runner
import plugin_manager, plugin_service_manager, settings_backup, settings_admin
snapshot = plugin_manager.snapshot({"hostname":"candidate","uptime_s":1,"temperature_c":25,"load":[0,0,0]})
assert snapshot["api"] == 1
rows = [p for p in snapshot["plugins"] if p.get("id") == "system-info"]
assert len(rows) == 1 and rows[0].get("valid") is True, rows
assert snapshot["system"].get("enabled") is False
services = plugin_service_manager.discover()
assert any(e.get("valid") and e.get("manifest",{}).get("id") == "service-heartbeat" for e in services), services
PY
fi

echo "Candidate validation: OK"
if [[ "$MODE" == "dry-run" ]]; then
  echo "Dry run complete. The live installation and service state were not changed."
  exit 0
fi

echo
read -r -p "Apply $target_version from $label @ $target_short? [y/N]: " answer
[[ "$answer" =~ ^[Yy]$ ]] || { echo "Cancelled."; exit 0; }

repair_live_admin_bridge(){
  local live=/opt/ywd-hotspot/app
  [[ -f "$live/lib/admin_dispatch.sh" && -f "$live/lib/admin.py" ]] || return 0
  install -o root -g root -m 0755 "$live/lib/admin.py" /usr/local/libexec/ywd-hotspot-admin-core
  [[ -f "$live/lib/setup_admin.py" ]] && install -o root -g root -m 0755 "$live/lib/setup_admin.py" /usr/local/libexec/ywd-hotspot-setup-admin
  [[ -f "$live/lib/update_admin.py" ]] && install -o root -g root -m 0755 "$live/lib/update_admin.py" /usr/local/libexec/ywd-hotspot-update-admin
  [[ -f "$live/lib/update_runner.py" ]] && install -o root -g root -m 0755 "$live/lib/update_runner.py" /usr/local/libexec/ywd-update-runner
  install -o root -g root -m 0755 "$live/lib/admin_dispatch.sh" /usr/local/libexec/ywd-hotspot-admin
  [[ -f "$live/sudoers/ywd-hotspot" ]] && install -o root -g root -m 0440 "$live/sudoers/ywd-hotspot" /etc/sudoers.d/ywd-hotspot
  if command -v visudo >/dev/null 2>&1 && [[ -f /etc/sudoers.d/ywd-hotspot ]]; then
    visudo -cf /etc/sudoers.d/ywd-hotspot >/dev/null
  fi
  systemctl daemon-reload
}

# When leaving a plugin-aware runtime for a target that has no plugin runtime,
# the currently installed updater owns the transition. The stable target stays
# plugin-unaware while plugin services are stopped before handoff.
transition_helper=""
transition_snapshot=""
if (( ! plugin_runtime_target )) && [[ -f /opt/ywd-hotspot/app/lib/plugin_update_safety.py ]]; then
  transition_helper="$stage/.ywd-plugin-update-safety.py"
  transition_snapshot="$stage/.ywd-plugin-transition.json"
  cp /opt/ywd-hotspot/app/lib/plugin_update_safety.py "$transition_helper"
  chmod 0700 "$transition_helper"
  python3 "$transition_helper" capture --snapshot "$transition_snapshot" --lib /opt/ywd-hotspot/app/lib >/dev/null
  python3 "$transition_helper" quiesce --snapshot "$transition_snapshot" --lib /opt/ywd-hotspot/app/lib >/dev/null
  echo "Plugin services quiesced before leaving the plugin runtime."
fi

echo "Applying validated candidate. UPDATE.sh will preserve the current RF/service policy..."
next_channel="$channel_display"
[[ -z "$TAG" ]] && next_channel="$BRANCH"
set +e
YWD_SOURCE_TYPE=github \
YWD_SOURCE_STATE=clean \
YWD_GIT_BRANCH="$label" \
YWD_GIT_COMMIT="$target_sha" \
YWD_GIT_COMMIT_DATE="$target_date" \
YWD_UPDATE_CHANNEL="$next_channel" \
  bash "$stage/UPDATE.sh"
update_rc=$?
set -e

if (( update_rc != 0 )); then
  if [[ -n "$transition_helper" && -f "$transition_snapshot" ]]; then
    echo "Repairing restored admin bridge after target rollback..."
    repair_live_admin_bridge || echo "[WARN] Restored admin bridge needs manual review."
    echo "Restoring plugin runtime after target rollback..."
    python3 "$transition_helper" restore --snapshot "$transition_snapshot" --lib /opt/ywd-hotspot/app/lib || \
      echo "[WARN] Plugin runtime restore needs manual review."
  fi
  exit "$update_rc"
fi

if [[ -n "$transition_helper" && -f "$transition_snapshot" ]]; then
  echo "Finalizing transition to plugin-free target..."
  python3 "$transition_helper" stable-cleanup --snapshot "$transition_snapshot" --lib /opt/ywd-hotspot/app/lib
fi

if [[ -n "$TAG" ]]; then
  git -C "$REPO_DIR" checkout --quiet --detach "$target_sha"
else
  git -C "$REPO_DIR" checkout --quiet -B "$BRANCH" "$target_sha"
  git -C "$REPO_DIR" branch --set-upstream-to="origin/$BRANCH" "$BRANCH" >/dev/null 2>&1 || true
  if [[ "$BRANCH" == "main" || "$BRANCH" == "dev" || "$BRANCH" == "dev-plugins" ]]; then
    tmp_channel="${CHANNEL_FILE}.tmp"
    printf '%s\n' "$BRANCH" > "$tmp_channel"
    chmod 0644 "$tmp_channel"
    chown root:root "$tmp_channel" 2>/dev/null || true
    mv -f "$tmp_channel" "$CHANNEL_FILE"
    channel_display="$BRANCH"
  fi
fi

echo
echo "GitHub source checkout updated successfully."
echo "Update channel: $channel_display"
/usr/local/sbin/ywd-hotspotctl source 2>/dev/null || true
