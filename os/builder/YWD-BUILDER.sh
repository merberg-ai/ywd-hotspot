#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILDER_DIR="$ROOT_DIR/os/builder"
CLI=(python3 "$BUILDER_DIR/PROFILE-CLI.py")
SSH_KEYS=(python3 "$BUILDER_DIR/SSH-KEYS.py")

if [[ -t 1 && -z "${NO_COLOR:-}" && "${TERM:-}" != "dumb" ]]; then
  RESET=$'\033[0m'; BOLD=$'\033[1m'; CYAN=$'\033[38;5;51m'; BLUE=$'\033[38;5;75m'
  MAGENTA=$'\033[38;5;213m'; GREEN=$'\033[38;5;84m'; YELLOW=$'\033[38;5;220m'
  RED=$'\033[38;5;203m'; DIM=$'\033[2m'
else
  RESET='' BOLD='' CYAN='' BLUE='' MAGENTA='' GREEN='' YELLOW='' RED='' DIM=''
fi

clear_screen() { [[ -t 1 ]] && printf '\033[2J\033[H' || true; }
pause() { printf '\n'; read -r -p 'Press Enter to continue...' _ || true; }
line() { printf '%s\n' '------------------------------------------------------------'; }

header() {
  clear_screen
  printf '%s%s============================================================%s\n' "$CYAN" "$BOLD" "$RESET"
  printf '%s%s  YWD-HOTSPOT OS BUILDER%s\n' "$CYAN" "$BOLD" "$RESET"
  printf '%s  dev-builder / interactive appliance image forge%s\n' "$BLUE" "$RESET"
  printf '%s%s============================================================%s\n' "$CYAN" "$BOLD" "$RESET"
  printf '%s  ASCII/SSH-safe interface - RF-safe by default%s\n\n' "$DIM" "$RESET"
  local status
  if status="$("${CLI[@]}" status 2>/dev/null)"; then
    printf '%sSTATUS%s  %s\n' "$MAGENTA" "$RESET" "$status"
  else
    printf '%sSTATUS%s  profile needs attention\n' "$RED" "$RESET"
  fi
  line
}

getv() { "${CLI[@]}" get "$1"; }
# Send edited values over stdin rather than argv. Besides being simpler for
# spaces/shell metacharacters, this keeps passwords and API keys out of ps.
setv() { printf '%s' "$3" | "${CLI[@]}" set-stdin "$1" "$2"; }

rf_autostart_on() {
  [[ "$(getv config.maintenance.rf_autostart 2>/dev/null || printf 'no')" == "yes" ]]
}

rf_warning() {
  if rf_autostart_on; then
    printf '\n%s%s!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!%s\n' "$RED" "$BOLD" "$RESET"
    printf '%s%s  WARNING: RF AUTOSTART IS ENABLED%s\n' "$RED" "$BOLD" "$RESET"
    printf '%s  After successful first-boot setup/restore, the RF stack may%s\n' "$YELLOW" "$RESET"
    printf '%s  start automatically and the hotspot can transmit RF.%s\n' "$YELLOW" "$RESET"
    printf '%s  Set Web / Maintenance -> Enable RF on first boot = no%s\n' "$YELLOW" "$RESET"
    printf '%s  if you want the new image to remain RF-gated after setup.%s\n' "$YELLOW" "$RESET"
    printf '%s%s!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!%s\n' "$RED" "$BOLD" "$RESET"
  fi
}

prompt_text() {
  local path="$1" label="$2" current answer
  current="$(getv "$path")"
  printf '\n%s%s%s\nCurrent: %s\n' "$CYAN" "$label" "$RESET" "${current:-<blank>}"
  printf '%sEnter = keep current, /clear = blank%s\n' "$DIM" "$RESET"
  read -r -p '> ' answer
  [[ -z "$answer" ]] && return 0
  [[ "$answer" == '/clear' ]] && answer=''
  setv "$path" str "$answer" || { printf '%sValue rejected; previous value kept.%s\n' "$RED" "$RESET"; pause; }
}

prompt_secret() {
  local path="$1" label="$2" current answer
  current="$(getv "$path")"
  printf '\n%s%s%s\nCurrent: %s\n' "$CYAN" "$label" "$RESET" "$([[ -n "$current" ]] && echo '[configured]' || echo '[blank]')"
  printf '%sEnter = keep current, /clear = blank. Input is hidden.%s\n' "$DIM" "$RESET"
  read -r -s -p '> ' answer; printf '\n'
  [[ -z "$answer" ]] && return 0
  [[ "$answer" == '/clear' ]] && answer=''
  setv "$path" str "$answer" || { printf '%sValue rejected; previous value kept.%s\n' "$RED" "$RESET"; pause; }
}

prompt_int() {
  local path="$1" label="$2" current answer
  current="$(getv "$path")"
  printf '\n%s%s%s\nCurrent: %s\n' "$CYAN" "$label" "$RESET" "$current"
  read -r -p 'New value [Enter = keep]: ' answer
  [[ -z "$answer" ]] && return 0
  setv "$path" int "$answer" || { printf '%sValue rejected; previous value kept.%s\n' "$RED" "$RESET"; pause; }
}

prompt_float() {
  local path="$1" label="$2" current answer
  current="$(getv "$path")"
  printf '\n%s%s%s\nCurrent: %s\n' "$CYAN" "$label" "$RESET" "$current"
  read -r -p 'New value [Enter = keep]: ' answer
  [[ -z "$answer" ]] && return 0
  setv "$path" float "$answer" || { printf '%sValue rejected; previous value kept.%s\n' "$RED" "$RESET"; pause; }
}

prompt_bool() {
  local path="$1" label="$2" current answer
  current="$(getv "$path")"
  printf '\n%s%s%s\nCurrent: %s\n' "$CYAN" "$label" "$RESET" "$current"
  read -r -p 'yes/no [Enter = keep]: ' answer
  [[ -z "$answer" ]] && return 0
  setv "$path" bool "$answer" || { printf '%sValue rejected; previous value kept.%s\n' "$RED" "$RESET"; pause; }
}

prompt_choice() {
  local path="$1" label="$2" choices="$3" current answer
  current="$(getv "$path")"
  printf '\n%s%s%s\nCurrent: %s\nChoices: %s\n' "$CYAN" "$label" "$RESET" "$current" "$choices"
  read -r -p 'New value [Enter = keep]: ' answer
  [[ -z "$answer" ]] && return 0
  setv "$path" str "$answer" || { printf '%sValue rejected; previous value kept.%s\n' "$RED" "$RESET"; pause; }
}

section_banner() {
  header
  printf '%s%s%s%s\n' "$BOLD" "$CYAN" "$1" "$RESET"
  printf '%sSkip anything you want; Enter keeps the current/default value.%s\n' "$DIM" "$RESET"
  line
}

edit_image_wifi() {
  section_banner 'IMAGE / WI-FI'
  prompt_text image.image_name 'Image name'
  prompt_text image.os_version 'OS identity / build label'
  prompt_text wifi.ssid 'Wi-Fi SSID (blank = setup AP)'
  prompt_secret wifi.password 'Wi-Fi password (blank valid for open network)'
  prompt_bool wifi.hidden 'Hidden Wi-Fi'
}

edit_station() {
  section_banner 'STATION / DMR IDENTITY'
  prompt_text config.station.callsign 'Callsign'
  prompt_text config.station.base_dmr_id 'Base DMR ID'
  prompt_text config.station.essid 'ESSID (01-99 or blank)'
  prompt_text config.station.location 'Location'
  prompt_text config.station.description 'Description'
  prompt_float config.station.latitude 'Latitude'
  prompt_float config.station.longitude 'Longitude'
  prompt_int config.station.height 'Antenna height (m)'
  prompt_text config.station.url 'Station URL'
}

edit_radio() {
  section_banner 'MMDVM / RF'
  prompt_choice config.radio.mode 'HAT mode' 'simplex | duplex'
  prompt_int config.radio.frequency_hz 'Simplex frequency (Hz)'
  prompt_int config.radio.rx_frequency_hz 'Duplex hotspot RX frequency (Hz)'
  prompt_int config.radio.tx_frequency_hz 'Duplex hotspot TX frequency (Hz)'
  prompt_int config.radio.color_code 'DMR color code'
  prompt_int config.radio.rx_offset 'RX offset'
  prompt_int config.radio.tx_offset 'TX offset'
  prompt_int config.radio.tx_invert 'TX invert (0/1)'
  prompt_int config.radio.rx_invert 'RX invert (0/1)'
  prompt_int config.radio.rx_level 'RX level (0-100)'
  prompt_int config.radio.tx_level 'TX level (0-100)'
  prompt_int config.radio.rf_level 'RF level (0-100)'
  prompt_int config.radio.jitter_ms 'DMR jitter (ms)'
  prompt_int config.radio.call_hang_s 'Call hang (s)'
  prompt_int config.radio.tx_hang_s 'TX hang (s)'
  prompt_int config.radio.timeout_s 'RF timeout (s)'
  prompt_text config.radio.uart 'MMDVM UART path'
  prompt_int config.radio.uart_speed 'UART speed'
}

edit_brandmeister() {
  section_banner 'BRANDMEISTER / SECURITY'
  prompt_bool config.brandmeister.enabled 'BrandMeister enabled'
  prompt_text config.brandmeister.master 'BrandMeister master'
  prompt_int config.brandmeister.port 'BrandMeister port'
  prompt_secret credentials.hotspot_password 'BrandMeister Hotspot Security password'
  prompt_secret credentials.bm_api_key 'BrandMeister API key'
  prompt_secret credentials.dashboard_password 'Dashboard control password'
}

edit_oled() {
  section_banner 'OLED / DISPLAY'
  prompt_bool config.display.enabled 'OLED enabled'
  prompt_int config.display.i2c_bus 'I2C bus'
  prompt_text config.display.address 'I2C address'
  prompt_int config.display.brightness 'Brightness (1-255)'
  prompt_int config.display.idle_timeout_s 'Idle timeout (s)'
  prompt_int config.display.rotation 'Rotation (0/180)'
  prompt_choice config.display.runtime_mode 'Runtime mode' 'basic | enhanced | minimal'
  prompt_bool config.display.large_callsign 'Large callsign'
  prompt_choice config.display.callsign_size 'Callsign size' 'auto | normal | large | huge'
  prompt_bool config.display.show_talkgroup 'Show talkgroup'
  prompt_choice config.display.talkgroup_format 'Talkgroup format' 'number | name | name_number'
  prompt_bool config.display.show_slot 'Show timeslot'
  prompt_bool config.display.show_elapsed 'Show elapsed time'
  prompt_bool config.display.show_ber 'Show BER'
  prompt_bool config.display.show_rssi 'Show RSSI'
  prompt_bool config.display.show_loss 'Show packet loss'
  prompt_int config.display.post_call_hold_s 'Post-call hold (s)'
  prompt_bool config.display.idle_cycle 'Idle page cycle'
  prompt_int config.display.idle_cycle_s 'Idle cycle interval (s)'
}

edit_instrumentation() {
  section_banner 'INSTRUMENTATION / METERS'
  prompt_bool config.display.instrumentation.enabled 'Instrumentation enabled'
  prompt_choice config.display.instrumentation.preset 'Preset' 'basic | balanced | instrument | maximum | custom'
  prompt_bool config.display.instrumentation.signal_meter 'Signal meter'
  prompt_choice config.display.instrumentation.signal_style 'Signal style' 'segmented | smooth'
  prompt_int config.display.instrumentation.signal_segments 'Signal segments'
  prompt_int config.display.instrumentation.rssi_min_dbm 'RSSI minimum (dBm)'
  prompt_int config.display.instrumentation.rssi_max_dbm 'RSSI maximum (dBm)'
  prompt_bool config.display.instrumentation.peak_hold 'Peak hold'
  prompt_int config.display.instrumentation.peak_hold_ms 'Peak hold (ms)'
  prompt_bool config.display.instrumentation.quality_meter 'Quality meter'
  prompt_float config.display.instrumentation.ber_excellent 'BER excellent (%)'
  prompt_float config.display.instrumentation.ber_good 'BER good (%)'
  prompt_float config.display.instrumentation.ber_fair 'BER fair (%)'
  prompt_bool config.display.instrumentation.tx_meter 'TX meter'
  prompt_int config.display.instrumentation.measurement_hold_s 'Measurement hold (s)'
  prompt_bool config.display.instrumentation.history_rssi 'RSSI history'
  prompt_bool config.display.instrumentation.history_ber 'BER history'
  prompt_choice config.display.instrumentation.history_mode 'History mode' 'samples | time'
  prompt_int config.display.instrumentation.history_samples 'History samples'
  prompt_int config.display.instrumentation.history_max_age_s 'History max age (s)'
  prompt_int config.display.instrumentation.history_seconds 'History seconds'
  prompt_int config.display.instrumentation.render_fps 'Render FPS (5/10/20)'
  prompt_choice config.display.instrumentation.animation 'Animation' 'off | subtle | normal | high'
  prompt_bool config.display.instrumentation.idle_animation 'Idle animation'
  prompt_bool config.display.instrumentation.live_status_strip 'Live status strip'
  prompt_bool config.display.instrumentation.show_numeric_values 'Show numeric values'
  prompt_choice config.display.instrumentation.meter_labels 'Meter labels' 'compact | full'
  prompt_choice config.display.instrumentation.reduced_motion 'Reduced motion' 'system | reduce | full'
}

edit_maintenance() {
  section_banner 'WEB / MAINTENANCE'
  prompt_text config.web.bind 'Dashboard bind address'
  prompt_int config.web.port 'Dashboard port'
  printf '\n%sRF AUTOSTART IS A SAFETY-SENSITIVE OPTION.%s\n' "$YELLOW" "$RESET"
  prompt_bool config.maintenance.rf_autostart 'Enable RF on first boot'
  prompt_bool config.maintenance.persistent_journal 'Persistent journal'
  prompt_int config.maintenance.journal_max_mb 'Journal maximum (MB)'
  prompt_int config.maintenance.dmrid_update_days 'DMR ID update interval (days)'
  prompt_int config.maintenance.config_history_keep 'Config history snapshots'
}

import_dashboard_settings() {
  header
  printf '%s%sIMPORT DASHBOARD SETTINGS%s\n\n' "$BOLD" "$CYAN" "$RESET"
  printf 'Import an encrypted .ywdsettings export from an existing YWD-Hotspot.\n'
  printf 'Canonical hotspot settings and supported saved state become the builder baseline.\n'
  printf '%sThe dashboard password itself is never recovered; its existing credential hash is preserved.%s\n\n' "$DIM" "$RESET"

  local path passphrase
  read -r -p 'Backup path: ' path
  [[ -z "$path" ]] && return 0
  if [[ "$path" == '~/'* ]]; then
    path="$HOME/${path:2}"
  fi
  if [[ ! -f "$path" ]]; then
    printf '%sBackup not found: %s%s\n' "$RED" "$path" "$RESET"
    pause
    return 0
  fi

  read -r -s -p 'Backup passphrase: ' passphrase
  printf '\n\n'
  if printf '%s' "$passphrase" | "${CLI[@]}" import-settings "$path"; then
    printf '\n%sImport succeeded. Review or edit any values before building.%s\n' "$GREEN" "$RESET"
  else
    printf '\n%sImport failed. Existing builder profile was not replaced.%s\n' "$RED" "$RESET"
  fi
  unset passphrase
  pause
}

ssh_keys_menu() {
  while true; do
    header
    printf '%s%sSSH ACCESS / KEY EXPORT%s\n\n' "$BOLD" "$CYAN" "$RESET"
    printf 'The builder uses one Ed25519 CLIENT LOGIN key for the ywd account.\n'
    printf 'Exporting it before the build gives you the exact private key needed\n'
    printf 'to SSH/SFTP into the freshly flashed hotspot.\n\n'
    printf '%sServer identity keys (ssh_host_*) are different: they identify the%s\n' "$DIM" "$RESET"
    printf '%sserver and do not permit login. They should be unique per device and%s\n' "$DIM" "$RESET"
    printf '%scan be exported from the dashboard after first boot for recovery.%s\n\n' "$DIM" "$RESET"
    printf '%s  1%s  Generate / export SSH login key bundle\n' "$CYAN" "$RESET"
    printf '%s  2%s  Show SSH login key status / fingerprint\n' "$CYAN" "$RESET"
    printf '%s  B%s  Back\n\n' "$MAGENTA" "$RESET"
    local choice
    read -r -p 'Select: ' choice
    case "${choice,,}" in
      1)
        printf '\n'
        if "${SSH_KEYS[@]}" export; then
          printf '\n%sKeep that archive private; it contains an unencrypted login key.%s\n' "$YELLOW" "$RESET"
        fi
        pause
        ;;
      2)
        printf '\n'
        "${SSH_KEYS[@]}" status || true
        pause
        ;;
      b|'') return 0 ;;
      *) printf '%sUnknown selection.%s\n' "$RED" "$RESET"; sleep 1 ;;
    esac
  done
}

review_profile() {
  header
  "${CLI[@]}" review || true
  rf_warning
  pause
}

validate_profile() {
  header
  printf '%s%sVALIDATING PROFILE%s\n\n' "$BOLD" "$CYAN" "$RESET"
  "${CLI[@]}" validate && printf '\n%sValidation passed.%s\n' "$GREEN" "$RESET" || printf '\n%sValidation failed.%s\n' "$RED" "$RESET"
  rf_warning
  pause
}

run_doctor() { header; printf '%s%sBUILDER DOCTOR%s\n\n' "$BOLD" "$CYAN" "$RESET"; bash "$BUILDER_DIR/DOCTOR.sh" || true; pause; }

run_build() {
  header
  "${CLI[@]}" review || true
  rf_warning
  printf '\n%sThis starts a full Raspberry Pi OS image build.%s\n' "$YELLOW" "$RESET"
  local answer
  if rf_autostart_on; then
    printf '%sBecause RF autostart is ON, extra confirmation is required.%s\n' "$RED" "$RESET"
    read -r -p 'Type BUILD-RF-ON to continue: ' answer
    [[ "$answer" == 'BUILD-RF-ON' ]] || return 0
  else
    read -r -p 'Type BUILD to continue: ' answer
    [[ "$answer" == 'BUILD' ]] || return 0
  fi
  printf '\n'
  bash "$BUILDER_DIR/RUN-BUILD.sh"
  pause
}

reset_profile() {
  header
  printf '%sReset builder profile to defaults?%s\n' "$YELLOW" "$RESET"
  read -r -p 'Type RESET to confirm: ' answer
  [[ "$answer" == 'RESET' ]] && "${CLI[@]}" reset || true
  pause
}

main_menu() {
  while true; do
    header
    printf '%s  1%s  Image / Wi-Fi\n' "$CYAN" "$RESET"
    printf '%s  2%s  Station / DMR identity\n' "$CYAN" "$RESET"
    printf '%s  3%s  MMDVM / RF\n' "$CYAN" "$RESET"
    printf '%s  4%s  BrandMeister / Security\n' "$CYAN" "$RESET"
    printf '%s  5%s  OLED / Display\n' "$CYAN" "$RESET"
    printf '%s  6%s  Instrumentation / Meters\n' "$CYAN" "$RESET"
    printf '%s  7%s  Web / Maintenance\n' "$CYAN" "$RESET"
    line
    printf '%s  I%s  Import dashboard .ywdsettings\n' "$BLUE" "$RESET"
    printf '%s  K%s  SSH access / key export\n' "$BLUE" "$RESET"
    printf '%s  R%s  Review configuration\n' "$MAGENTA" "$RESET"
    printf '%s  V%s  Validate profile\n' "$MAGENTA" "$RESET"
    printf '%s  D%s  Builder doctor\n' "$MAGENTA" "$RESET"
    printf '%s  B%s  Build image\n' "$GREEN" "$RESET"
    printf '%s  X%s  Reset profile\n' "$YELLOW" "$RESET"
    printf '%s  Q%s  Quit\n\n' "$RED" "$RESET"
    read -r -p 'Select: ' choice
    case "${choice,,}" in
      1) edit_image_wifi ;;
      2) edit_station ;;
      3) edit_radio ;;
      4) edit_brandmeister ;;
      5) edit_oled ;;
      6) edit_instrumentation ;;
      7) edit_maintenance ;;
      i) import_dashboard_settings ;;
      k) ssh_keys_menu ;;
      r) review_profile ;;
      v) validate_profile ;;
      d) run_doctor ;;
      b) run_build ;;
      x) reset_profile ;;
      q) clear_screen; exit 0 ;;
      *) printf '%sUnknown selection.%s\n' "$RED" "$RESET"; sleep 1 ;;
    esac
  done
}

command -v python3 >/dev/null 2>&1 || { echo 'ERROR: python3 is required.' >&2; exit 1; }
[[ -f "$BUILDER_DIR/profile_model.py" ]] || { echo 'ERROR: builder profile engine is missing.' >&2; exit 1; }
[[ -f "$BUILDER_DIR/SSH-KEYS.py" ]] || { echo 'ERROR: builder SSH key helper is missing.' >&2; exit 1; }
main_menu
