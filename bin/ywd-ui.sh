#!/usr/bin/env bash
# Shared terminal presentation helpers for YWD-Hotspot.
# ANSI color is used only on a real terminal and can always be disabled with NO_COLOR=1.

YWD_COLOR=0
if [[ -t 1 && -z "${NO_COLOR:-}" && "${TERM:-dumb}" != "dumb" ]]; then YWD_COLOR=1; fi

if (( YWD_COLOR )); then
  YWD_RESET=$'\033[0m'; YWD_BOLD=$'\033[1m'; YWD_DIM=$'\033[2m'
  YWD_CYAN=$'\033[96m'; YWD_BLUE=$'\033[94m'; YWD_MAGENTA=$'\033[95m'
  YWD_GREEN=$'\033[92m'; YWD_YELLOW=$'\033[93m'; YWD_RED=$'\033[91m'; YWD_WHITE=$'\033[97m'
else
  YWD_RESET=''; YWD_BOLD=''; YWD_DIM=''; YWD_CYAN=''; YWD_BLUE=''; YWD_MAGENTA=''
  YWD_GREEN=''; YWD_YELLOW=''; YWD_RED=''; YWD_WHITE=''
fi

_ywd_p(){ printf '%b\n' "$*"; }
ywd_rule(){ _ywd_p "${YWD_BLUE}--------------------------------------------------------------------------${YWD_RESET}"; }
ywd_section(){ printf '\n%b:: %s%b\n' "${YWD_CYAN}${YWD_BOLD}" "$*" "$YWD_RESET"; }
ywd_info(){ _ywd_p "${YWD_BLUE}[i]${YWD_RESET} $*"; }
ywd_step(){ _ywd_p "${YWD_CYAN}[>]${YWD_RESET} $*"; }
ywd_ok(){ _ywd_p "${YWD_GREEN}[+]${YWD_RESET} $*"; }
ywd_warn(){ _ywd_p "${YWD_YELLOW}[!]${YWD_RESET} $*"; }
ywd_fail(){ _ywd_p "${YWD_RED}[x]${YWD_RESET} $*" >&2; }
ywd_kv(){ printf '%b%-18s%b %s\n' "${YWD_DIM}" "$1" "$YWD_RESET" "${2:-}"; }

ywd_banner(){
  local mode="${1:-CONTROL CONSOLE}" version="${2:-unknown}"
  printf '\n%b' "${YWD_CYAN}${YWD_BOLD}"
  cat <<'EOF'
__   __ __        __ ____        _   _  ___  _____ ____  ____   ___  _____
\ \ / / \ \      / /|  _ \ ___ | | | |/ _ \|_   _/ ___||  _ \ / _ \|_   _|
 \ V /   \ \ /\ / / | | | |___|| |_| | | | | | | \___ \| |_) | | | | | |
  | |     \ V  V /  | |_| |    |  _  | |_| | | |  ___) |  __/| |_| | | |
  |_|      \_/\_/   |____/     |_| |_|\___/  |_| |____/|_|    \___/  |_|
EOF
  printf '%b' "$YWD_RESET"
  printf ' %bRaspberry Pi DMR Hotspot Appliance%b\n' "${YWD_MAGENTA}${YWD_BOLD}" "$YWD_RESET"
  printf ' %bBrandMeister + TGIF%b\n' "${YWD_WHITE}" "$YWD_RESET"
  ywd_rule
  printf ' %b%-18s%b %s\n' "${YWD_CYAN}${YWD_BOLD}" "$mode" "$YWD_RESET" "$version"
  ywd_rule
}

ywd_colorize_stream(){
  if (( ! YWD_COLOR )); then cat; return; fi
  sed -u \
    -e "s/^\(\[FAIL\].*\)$/${YWD_RED}\1${YWD_RESET}/" \
    -e "s/^\(\[WARN\].*\)$/${YWD_YELLOW}\1${YWD_RESET}/" \
    -e "s/^\(\[ OK \].*\)$/${YWD_GREEN}\1${YWD_RESET}/" \
    -e "s/^\(Candidate validation: OK.*\)$/${YWD_GREEN}\1${YWD_RESET}/" \
    -e "s/^\(Status    : up to date.*\)$/${YWD_GREEN}\1${YWD_RESET}/" \
    -e "s/^\(Status    : update available.*\)$/${YWD_MAGENTA}${YWD_BOLD}\1${YWD_RESET}/" \
    -e "s/^\(Updated to .*\)$/${YWD_GREEN}${YWD_BOLD}\1${YWD_RESET}/" \
    -e "s/^\(Migration complete.*\)$/${YWD_GREEN}${YWD_BOLD}\1${YWD_RESET}/" \
    -e "s/^\(Protected pre-update backup:.*\)$/${YWD_BLUE}\1${YWD_RESET}/" \
    -e "s/^\(============================================================\)$/${YWD_BLUE}\1${YWD_RESET}/"
}

ywd_run_colored(){
  if (( ! YWD_COLOR )); then "$@"; return $?; fi
  set +e
  "$@" | ywd_colorize_stream
  local rc=${PIPESTATUS[0]}
  set -e
  return "$rc"
}

ywd_color_line(){
  local line="$1"
  case "$line" in
    *"[FAIL]"*|*"Permission denied"*|*" DOWN"*|*"inactive"*) _ywd_p "${YWD_RED}${line}${YWD_RESET}";;
    *"[WARN]"*|*"pending"*|*"update available"*|*"Provisional"*) _ywd_p "${YWD_YELLOW}${line}${YWD_RESET}";;
    *"active"*|*"connected"*|*"enabled"*|*"up to date"*|*"Recommended"*|*"clean"*) _ywd_p "${YWD_GREEN}${line}${YWD_RESET}";;
    "YWD Hotspot "*|"YWD-Hotspot "*|"YWD-Hotspot source"*) _ywd_p "${YWD_CYAN}${YWD_BOLD}${line}${YWD_RESET}";;
    *) printf '%s\n' "$line";;
  esac
}

ywd_pretty_capture(){
  local out rc
  set +e; out="$("$@" 2>&1)"; rc=$?; set -e
  while IFS= read -r line; do ywd_color_line "$line"; done <<< "$out"
  return "$rc"
}
