# YWD-Hotspot OS interactive shell prompt
case "$-" in *i*) ;; *) return ;; esac
[ -n "${BASH_VERSION:-}" ] || return
[ -z "${YWD_KEEP_PROMPT:-}" ] || return
if [ "$(id -u)" -eq 0 ]; then
  PS1='\[\e[1;35m\][YWD]\[\e[0m\] \u@\h \w # '
else
  PS1='\[\e[1;36m\][YWD]\[\e[0m\] \u@\h \w $ '
fi
