#!/usr/bin/env python3
"""Fail-closed validation for a public YWD-Hotspot release image profile.

A public image must contain only factory/default hotspot settings. Operator or
builder-specific identity, credentials, Wi-Fi, imported backups, RF autostart,
and SSH credentials are forbidden.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = ROOT / "os" / "local"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from profile_model import compile_profile, default_profile, load_profile


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def check_profile() -> list[str]:
    profile = load_profile()
    compiled = compile_profile(profile)
    baseline = default_profile()
    errors: list[str] = []

    wifi = profile.get("wifi") or {}
    if str(wifi.get("ssid") or ""):
        fail("Wi-Fi SSID is preconfigured", errors)
    if str(wifi.get("password") or ""):
        fail("Wi-Fi password is preconfigured", errors)
    if bool(wifi.get("hidden", False)):
        fail("hidden Wi-Fi flag is preconfigured", errors)

    creds = profile.get("credentials") or {}
    for key, label in (
        ("dashboard_password", "dashboard password"),
        ("hotspot_password", "BrandMeister Hotspot Security password"),
        ("bm_api_key", "BrandMeister API key"),
    ):
        if str(creds.get(key) or ""):
            fail(f"{label} is preconfigured", errors)

    if profile.get("imported_backup") is not None:
        fail("an imported settings backup is attached", errors)

    raw_cfg = profile.get("config") or {}
    expected_cfg = baseline["config"]
    if raw_cfg != expected_cfg:
        fail("hotspot config differs from factory defaults", errors)

    if compiled["complete"]:
        fail("profile is complete and would skip the first-boot wizard", errors)
    if compiled["config"]["maintenance"].get("rf_autostart"):
        fail("RF autostart is enabled", errors)
    if compiled["config"]["station"].get("callsign") != "NOCALL":
        fail("compiled callsign is not factory NOCALL", errors)
    if compiled["config"]["station"].get("base_dmr_id") != "00000":
        fail("compiled DMR ID is not the factory placeholder", errors)

    system = profile.get("system") or {}
    if str(system.get("hostname") or "ywd-hotspot") != "ywd-hotspot":
        fail("hostname differs from the factory default", errors)
    if str(system.get("ssh_policy") or "key-only") != "disabled":
        fail("SSH must be disabled in a public factory image", errors)
    if str(system.get("update_channel") or "dev") != "main":
        fail("public release update channel must be main", errors)

    return errors


def check_generated() -> list[str]:
    errors: list[str] = []
    gen = LOCAL / "generated"
    summary_path = gen / "summary.json"
    if not summary_path.is_file():
        return ["generated summary.json is missing; run PREPARE-PROFILE.py first"]
    try:
        summary = json.loads(summary_path.read_text())
    except Exception as exc:
        return [f"generated summary.json is invalid: {exc}"]

    forbidden = {
        "provision.env": "Wi-Fi provisioning payload",
        "factory-provision.json": "fully preconfigured first-boot payload",
        "factory-restore.json": "imported settings restore payload",
    }
    for name, label in forbidden.items():
        if (gen / name).exists():
            fail(f"{label} exists: {name}", errors)

    if summary.get("complete"):
        fail("generated profile is complete and would skip setup", errors)
    if summary.get("wifi_preconfigured"):
        fail("generated image has Wi-Fi preconfiguration", errors)
    if summary.get("dashboard_password_preconfigured"):
        fail("generated image has a dashboard credential", errors)
    if summary.get("bm_api_key_preconfigured"):
        fail("generated image has a BrandMeister API key", errors)
    if summary.get("dashboard_backup_imported"):
        fail("generated image contains an imported dashboard backup", errors)
    if summary.get("rf_autostart"):
        fail("generated image has RF autostart enabled", errors)
    if summary.get("callsign") != "NOCALL":
        fail("generated callsign is not NOCALL", errors)

    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("profile", "generated", "all"), nargs="?", default="all")
    args = ap.parse_args()

    errors: list[str] = []
    if args.mode in {"profile", "all"}:
        errors.extend(check_profile())
    if args.mode in {"generated", "all"}:
        errors.extend(check_generated())

    if errors:
        print("PUBLIC RELEASE PROFILE: REFUSED")
        for item in errors:
            print(f"[FAIL] {item}")
        return 1

    print("PUBLIC RELEASE PROFILE: CLEAN FACTORY STATE")
    print("Wi-Fi: none")
    print("Operator identity: none")
    print("Credentials/API keys: none")
    print("Imported settings: none")
    print("RF first boot: OFF")
    print("SSH: disabled / no operator credential allowed")
    print("Update channel: main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
