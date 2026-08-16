# YWD-Hotspot OS dynamic login banner
case "$-" in *i*) ;; *) return ;; esac
[ -t 1 ] || return
[ -z "${YWD_MOTD_SHOWN:-}" ] || return
export YWD_MOTD_SHOWN=1
if command -v ywd-info >/dev/null 2>&1; then
  ywd-info --motd 2>/dev/null || true
fi
