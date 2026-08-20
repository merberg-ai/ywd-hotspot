#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

from profile_model import PROFILE_PATH, load_profile, save_profile

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "os" / "local" / "generated"
SYSTEM_ENV = GENERATED / "system.env"
ZONEINFO = Path("/usr/share/zoneinfo")

HOST_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9._+@/-]+$")
KEYMAP_RE = re.compile(r"^[A-Za-z0-9._+-]+$")


def defaults() -> dict[str, Any]:
    return {
        "hostname": "ywd-hotspot",
        "timezone": "America/Los_Angeles",
        "locale": "en_US.UTF-8",
        "keyboard_keymap": "us",
        "keyboard_layout": "English (US)",
        "wifi_country": "US",
        "update_channel": "dev",
        "ssh_policy": "key-only",
    }


def system_settings(profile: dict[str, Any]) -> dict[str, Any]:
    out = defaults()
    incoming = profile.get("system")
    if isinstance(incoming, dict):
        for key in out:
            if key in incoming:
                out[key] = incoming[key]
    return validate(out)


def validate(raw: dict[str, Any]) -> dict[str, Any]:
    s = {k: str(raw.get(k, v) or "").strip() for k, v in defaults().items()}

    s["hostname"] = s["hostname"].lower()
    if not HOST_RE.fullmatch(s["hostname"]):
        raise ValueError("hostname must be a single DNS label: lowercase letters, digits, dash; max 63 characters")

    timezone = s["timezone"]
    if not timezone or timezone.startswith("/") or ".." in timezone.split("/") or not TOKEN_RE.fullmatch(timezone):
        raise ValueError("timezone must be a safe IANA timezone name, for example America/Los_Angeles")
    zone_path = ZONEINFO / timezone
    if ZONEINFO.is_dir() and not zone_path.exists():
        raise ValueError(f"timezone is not installed on this builder: {timezone}")

    locale = s["locale"]
    if not locale or len(locale) > 64 or not re.fullmatch(r"[A-Za-z0-9_.@-]+", locale):
        raise ValueError("locale contains unsupported characters")

    keymap = s["keyboard_keymap"]
    if not keymap or len(keymap) > 32 or not KEYMAP_RE.fullmatch(keymap):
        raise ValueError("keyboard keymap contains unsupported characters")

    layout = s["keyboard_layout"]
    if not layout or len(layout) > 64 or any(ch in layout for ch in "\r\n'"):
        raise ValueError("keyboard layout must be a single safe text value")

    country = s["wifi_country"].upper()
    if not re.fullmatch(r"[A-Z]{2}", country):
        raise ValueError("Wi-Fi country must be a two-letter country code, for example US")
    s["wifi_country"] = country

    if s["update_channel"] not in {"main", "dev"}:
        raise ValueError("update channel must be main or dev")

    if s["ssh_policy"] not in {"key-only", "disabled"}:
        raise ValueError("SSH policy must be key-only or disabled")

    return s


def save_system(profile: dict[str, Any], settings: dict[str, Any]) -> None:
    profile["system"] = validate(settings)
    save_profile(profile)


def get_value(settings: dict[str, Any], key: str) -> str:
    if key not in defaults():
        raise ValueError(f"unknown System / OS setting: {key}")
    return str(settings[key])


def set_value(profile: dict[str, Any], key: str, value: str) -> None:
    current = system_settings(profile)
    if key not in current:
        raise ValueError(f"unknown System / OS setting: {key}")
    current[key] = value
    save_system(profile, current)


def review(settings: dict[str, Any]) -> str:
    ssh = "enabled / public-key only" if settings["ssh_policy"] == "key-only" else "disabled"
    return "\n".join([
        "SYSTEM / OS",
        "-----------",
        f"Hostname:               {settings['hostname']}",
        f"mDNS name:              {settings['hostname']}.local",
        f"Timezone:               {settings['timezone']}",
        f"Locale:                 {settings['locale']}",
        f"Keyboard keymap:        {settings['keyboard_keymap']}",
        f"Keyboard layout:        {settings['keyboard_layout']}",
        f"Wi-Fi country:          {settings['wifi_country']}",
        f"Update channel:         {settings['update_channel']}",
        f"SSH:                    {ssh}",
        "Linux login user:       ywd (fixed appliance identity)",
    ])


def status(settings: dict[str, Any]) -> str:
    ssh = "key-only" if settings["ssh_policy"] == "key-only" else "off"
    return f"HOST={settings['hostname']} | TZ={settings['timezone']} | UPDATE={settings['update_channel']} | SSH={ssh}"


def write_env(settings: dict[str, Any]) -> Path:
    GENERATED.mkdir(parents=True, exist_ok=True)
    os.chmod(GENERATED, 0o700)
    ssh_enabled = "1" if settings["ssh_policy"] == "key-only" else "0"
    values = {
        "YWD_TARGET_HOSTNAME": settings["hostname"],
        "YWD_TIMEZONE": settings["timezone"],
        "YWD_LOCALE": settings["locale"],
        "YWD_KEYBOARD_KEYMAP": settings["keyboard_keymap"],
        "YWD_KEYBOARD_LAYOUT": settings["keyboard_layout"],
        "YWD_WIFI_COUNTRY": settings["wifi_country"],
        "YWD_UPDATE_CHANNEL": settings["update_channel"],
        "YWD_ENABLE_SSH": ssh_enabled,
        "YWD_PUBKEY_ONLY_SSH": "1",
    }
    text = "".join(f"{key}={shlex.quote(value)}\n" for key, value in values.items())
    tmp = SYSTEM_ENV.with_suffix(".env.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, SYSTEM_ENV)
    return SYSTEM_ENV


def main() -> int:
    ap = argparse.ArgumentParser(description="YWD-Hotspot OS builder System / OS profile helper")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("get")
    g.add_argument("key")

    s = sub.add_parser("set-stdin")
    s.add_argument("key")

    sub.add_parser("review")
    sub.add_parser("validate")
    sub.add_parser("status")
    sub.add_parser("write-env")
    sub.add_parser("reset")

    args = ap.parse_args()
    profile = load_profile()
    settings = system_settings(profile)

    if args.cmd == "get":
        print(get_value(settings, args.key))
    elif args.cmd == "set-stdin":
        set_value(profile, args.key, sys.stdin.read())
    elif args.cmd == "review":
        print(review(settings))
    elif args.cmd == "validate":
        print("VALID")
        print(status(settings))
    elif args.cmd == "status":
        print(status(settings))
    elif args.cmd == "write-env":
        print(write_env(settings))
    elif args.cmd == "reset":
        profile["system"] = defaults()
        save_profile(profile)
        print(f"Reset System / OS settings in {PROFILE_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
