#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from typing import Any

from profile_model import (
    PROFILE_PATH,
    compile_profile,
    default_profile,
    get_path,
    load_profile,
    save_profile,
    set_path,
)


def parse_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if v in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    raise ValueError("expected yes/no")


def typed(value: str, kind: str) -> Any:
    if kind == "str":
        return value
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    if kind == "bool":
        return parse_bool(value)
    raise ValueError(f"unsupported type: {kind}")


def store(profile: dict[str, Any], path: str, kind: str, value: str) -> None:
    set_path(profile, path, typed(value, kind))
    # Validate the whole profile before saving. A rejected edit never replaces
    # the last usable persistent builder profile.
    compile_profile(profile)
    save_profile(profile)


def redacted_review(profile: dict[str, Any]) -> str:
    compiled = compile_profile(profile)
    cfg = compiled["config"]
    wifi = compiled["wifi"]
    creds = profile.get("credentials") or {}
    image = compiled["image"]

    def secret_state(key: str) -> str:
        return "configured" if str(creds.get(key) or "") else "blank"

    lines = [
        "YWD-HOTSPOT OS BUILDER - PROFILE REVIEW",
        "========================================",
        f"Image name:             {image['image_name']}",
        f"OS identity:            {image['os_version']}",
        f"Wi-Fi SSID:             {wifi['ssid'] or 'deferred to setup AP'}",
        f"Wi-Fi password:         {'configured' if wifi['password'] else 'blank/open'}",
        "",
        f"Callsign:               {cfg['station']['callsign']}",
        f"Base DMR ID:            {cfg['station']['base_dmr_id']}",
        f"Hotspot ID:             {cfg['station']['hotspot_id']}",
        f"Location:               {cfg['station']['location']}",
        f"Radio mode:             {cfg['radio']['mode']}",
        f"Simplex frequency:      {cfg['radio']['frequency_hz']} Hz",
        f"Duplex hotspot RX:      {cfg['radio']['rx_frequency_hz']} Hz",
        f"Duplex hotspot TX:      {cfg['radio']['tx_frequency_hz']} Hz",
        f"Color code:             {cfg['radio']['color_code']}",
        "",
        f"BrandMeister:           {'enabled' if cfg['brandmeister']['enabled'] else 'disabled'}",
        f"BrandMeister master:    {cfg['brandmeister']['master']}:{cfg['brandmeister']['port']}",
        f"Hotspot Security pass:  {secret_state('hotspot_password')}",
        f"BrandMeister API key:   {secret_state('bm_api_key')}",
        f"Dashboard password:     {secret_state('dashboard_password')}",
        "",
        f"OLED:                   {'enabled' if cfg['display']['enabled'] else 'disabled'}",
        f"OLED runtime mode:      {cfg['display']['runtime_mode']}",
        f"Instrumentation:        {'enabled' if cfg['display']['instrumentation']['enabled'] else 'disabled'}",
        f"Dashboard:              {cfg['web']['bind']}:{cfg['web']['port']}",
        f"Persistent journal:     {'yes' if cfg['maintenance']['persistent_journal'] else 'no'}",
        f"RF on first boot:       {'YES' if cfg['maintenance']['rf_autostart'] else 'no'}",
        "",
        f"Hotspot preconfigured:  {'YES - wizard will be skipped' if compiled['complete'] else 'NO - wizard will run'}",
    ]
    if not compiled["complete"]:
        lines.append("Deferred requirements:   " + ", ".join(compiled["missing"]))
    return "\n".join(lines)


def status_line(profile: dict[str, Any]) -> str:
    compiled = compile_profile(profile)
    wifi = "preconfigured" if compiled["wifi"]["ssid"] else "setup AP"
    setup = "PRECONFIGURED" if compiled["complete"] else "FIRST-BOOT WIZARD"
    rf = "ON" if compiled["config"]["maintenance"]["rf_autostart"] else "OFF"
    return f"SETUP={setup} | WIFI={wifi} | RF={rf}"


def main() -> None:
    p = argparse.ArgumentParser(description="YWD-Hotspot OS builder profile helper")
    sp = p.add_subparsers(dest="cmd", required=True)

    g = sp.add_parser("get")
    g.add_argument("path")

    s = sp.add_parser("set")
    s.add_argument("path")
    s.add_argument("kind", choices=["str", "int", "float", "bool"])
    s.add_argument("value")

    ss = sp.add_parser("set-stdin")
    ss.add_argument("path")
    ss.add_argument("kind", choices=["str", "int", "float", "bool"])

    sp.add_parser("validate")
    sp.add_parser("review")
    sp.add_parser("status")
    sp.add_parser("reset")
    sp.add_parser("path")

    args = p.parse_args()
    profile = load_profile()

    if args.cmd == "get":
        value = get_path(profile, args.path, "")
        if isinstance(value, bool):
            print("yes" if value else "no")
        elif value is None:
            print("")
        else:
            print(value)
        return

    if args.cmd == "set":
        store(profile, args.path, args.kind, args.value)
        return

    if args.cmd == "set-stdin":
        # Intended for passwords/API keys so the secret never appears in argv
        # or a process listing. The shell frontend writes exactly the entered
        # bytes to stdin without a trailing newline.
        store(profile, args.path, args.kind, sys.stdin.read())
        return

    if args.cmd == "validate":
        compiled = compile_profile(profile)
        print("VALID")
        if compiled["complete"]:
            print("Hotspot configuration is complete; first-boot hotspot wizard will be skipped.")
        else:
            print("Hotspot configuration is partial; first-boot hotspot wizard will run.")
            print("Deferred: " + ", ".join(compiled["missing"]))
        print("Wi-Fi: " + (compiled["wifi"]["ssid"] or "blank - setup AP will be used"))
        print("RF first boot: " + ("ON" if compiled["config"]["maintenance"]["rf_autostart"] else "OFF"))
        return

    if args.cmd == "review":
        print(redacted_review(profile))
        return

    if args.cmd == "status":
        print(status_line(profile))
        return

    if args.cmd == "reset":
        save_profile(default_profile())
        print(f"Reset builder profile: {PROFILE_PATH}")
        return

    if args.cmd == "path":
        print(PROFILE_PATH)
        return


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
