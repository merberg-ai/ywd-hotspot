#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -r "$SELF/bin/ywd-ui.sh" ]] && source "$SELF/bin/ywd-ui.sh"
VERSION="$(cat "$SELF/VERSION" 2>/dev/null || cat /opt/ywd-hotspot/app/VERSION 2>/dev/null || echo unknown)"
if [[ $EUID -ne 0 ]]; then exec sudo "$0" "$@"; fi

# Early OS images cloned only dev-os with --single-branch. Once an appliance is
# adopted onto the normal app channel, widen only a verified canonical checkout
# so main/dev/dev-os can all be fetched. The core updater still performs its own
# origin/clean-tree checks before changing the live application.
REPO_DIR=/opt/ywd-hotspot/repo
if [[ -d "$REPO_DIR/.git" ]]; then
  origin="$(git -C "$REPO_DIR" remote get-url origin 2>/dev/null || true)"
  case "$origin" in
    https://github.com/merberg-ai/ywd-hotspot.git|https://github.com/merberg-ai/ywd-hotspot|git@github.com:merberg-ai/ywd-hotspot.git)
      git -C "$REPO_DIR" config --replace-all remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
      ;;
  esac
fi

if declare -F ywd_banner >/dev/null; then
  ywd_banner "GITHUB UPDATE" "$VERSION"
  ywd_info "Integrated networks: BrandMeister + TGIF."
  ywd_info "Fetch + validation happen before the live RF stack is touched."
  if systemctl is-active --quiet ywd-tgif-scanner.service 2>/dev/null; then
    ywd_info "TGIF scanner is ACTIVE; it will pause only for live replacement and resume afterward."
  else
    ywd_info "TGIF scanner runtime intent is preserved across supported updates."
  fi
fi
CORE="$SELF/GITHUB-UPDATE-core.sh"
[[ -f "$CORE" ]] || CORE="/opt/ywd-hotspot/repo/GITHUB-UPDATE-core.sh"
[[ -f "$CORE" ]] || { echo "[FAIL] GitHub updater core not found." >&2; exit 1; }
if declare -F ywd_run_colored >/dev/null; then ywd_run_colored bash "$CORE" "$@"; else exec bash "$CORE" "$@"; fi
