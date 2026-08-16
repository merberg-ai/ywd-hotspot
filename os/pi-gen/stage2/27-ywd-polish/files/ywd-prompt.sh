# YWD-Hotspot OS interactive shell prompt
case "$-" in *i*) ;; *) return ;; esac
[ -n "${BASH_VERSION:-}" ] || return
[ -z "${YWD_KEEP_PROMPT:-}" ] || return

__ywd_set_prompt() {
  if [ "$(id -u)" -eq 0 ]; then
    PS1='\[\e[1;35m\][YWD]\[\e[0m\] \u@\h \w # '
  else
    PS1='\[\e[1;36m\][YWD]\[\e[0m\] \u@\h \w $ '
  fi
}

__ywd_set_prompt
case ";${PROMPT_COMMAND:-};" in
  *';__ywd_set_prompt;'*) ;;
  ';;') PROMPT_COMMAND='__ywd_set_prompt' ;;
  *) PROMPT_COMMAND="__ywd_set_prompt;${PROMPT_COMMAND}" ;;
esac
