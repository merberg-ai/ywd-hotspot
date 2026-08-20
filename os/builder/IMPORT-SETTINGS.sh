#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLI=(python3 "$ROOT_DIR/os/builder/PROFILE-CLI.py")

path="${1:-}"
if [[ -z "$path" ]]; then
  read -r -p 'Dashboard .ywdsettings path: ' path
fi
if [[ "$path" == '~/'* ]]; then
  path="$HOME/${path:2}"
fi
[[ -f "$path" ]] || { echo "ERROR: backup not found: $path" >&2; exit 1; }

read -r -s -p 'Backup passphrase: ' passphrase
printf '\n'
printf '%s' "$passphrase" | "${CLI[@]}" import-settings "$path"
unset passphrase

printf '\nImported backup into the local builder profile.\n'
printf 'Review with: bash os/builder/YWD-BUILDER.sh\n'
