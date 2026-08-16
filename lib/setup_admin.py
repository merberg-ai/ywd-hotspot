#!/usr/bin/env python3
"""Single-purpose privileged finalizer for YWD-Hotspot OS M4 first boot."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = Path(os.environ.get("YWD_APP", "/opt/ywd-hotspot/app"))
for p in (HERE, APP / "lib"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import admin as core_admin
import config_model
import web_auth

VAR = Path(os.environ.get("YWD_VAR", "/var/lib/ywd-hotspot"))
SETUP_STATE = VAR / "setup-state.json"
BMKEY = Path(os.environ.get("YWD_BM_API_KEY", "/etc/ywd-hotspot/bm-api.key"))


def payload():
    raw = sys.stdin.buffer.read(131072)
    if not raw:
        raise ValueError("missing setup payload")
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("invalid JSON payload")
    if not isinstance(obj, dict):
        raise ValueError("setup payload must be an object")
    return obj


def complete():
    try:
        d = json.loads(SETUP_STATE.read_text())
        return isinstance(d, dict) and d.get("state") == "complete"
    except Exception:
        return False


def validate(data):
    raw_cfg = data.get("config")
    if not isinstance(raw_cfg, dict):
        raise ValueError("config must be an object")
    web_password = str(data.get("web_password", ""))
    if len(web_password) < 8 or len(web_password) > 256:
        raise ValueError("dashboard password must be 8-256 characters")
    hotspot_password = str(data.get("hotspot_password", ""))
    if any(ch in hotspot_password for ch in ('"', "\n", "\r")) or len(hotspot_password) > 128:
        raise ValueError("Hotspot Security password format is invalid")
    api_key = str(data.get("bm_api_key", "")).strip()
    if api_key and (len(api_key) < 12 or len(api_key) > 4096 or "\n" in api_key or "\r" in api_key):
        raise ValueError("BrandMeister API key format is invalid")
    enable_rf = bool(data.get("enable_rf", False))

    candidate = json.loads(json.dumps(raw_cfg))
    candidate.setdefault("brandmeister", {})["password"] = hotspot_password
    candidate.setdefault("maintenance", {})["rf_autostart"] = enable_rf
    candidate = config_model.normalize(candidate)
    if candidate["station"]["callsign"] == "NOCALL" or candidate["station"]["base_dmr_id"] == "00000":
        raise ValueError("real callsign and DMR ID are required")
    if candidate["brandmeister"].get("enabled") and not hotspot_password:
        raise ValueError("Hotspot Security password is required when BrandMeister is enabled")
    return candidate, web_password, api_key, enable_rf


def finish(data):
    if complete():
        raise ValueError("appliance is already provisioned")
    candidate, web_password, api_key, enable_rf = validate(data)

    # Safety gate first. No setup error is allowed to leave RF running.
    core_admin.run(["systemctl", "disable", "--now", "ywd-dmrgateway.service", "ywd-mmdvmhost.service"], 20)

    old = core_admin.current()
    changed = config_model.diff_paths(old, candidate)
    snap = core_admin.backup_config("pre-first-boot", changed)
    core_admin.write_config(candidate)

    # Generate/install canonical INIs and record applied state before completing ownership.
    applied = core_admin.config_apply({})

    # Permanent control credential is created only after the configuration validates/applies.
    web_auth.set_password_value(web_password)
    if api_key:
        core_admin.set_bm_key({"key": api_key})
    else:
        try:
            BMKEY.unlink()
        except FileNotFoundError:
            pass

    state = {
        "schema": 1,
        "state": "complete",
        "completed_at": core_admin.now_iso(),
        "config_hash": config_model.hash_config(candidate, include_secrets=False),
        "callsign": candidate["station"]["callsign"],
        "hotspot_id": candidate["station"]["hotspot_id"],
        "rf_requested": enable_rf,
    }
    core_admin.atomic_json(SETUP_STATE, state, mode=0o640, group=True)
    core_admin.audit("first-boot-setup-complete", {
        "changed": changed, "snapshot": snap, "rf_requested": enable_rf,
        "callsign": candidate["station"]["callsign"],
    })

    rf_started = False
    rf_error = None
    if enable_rf:
        try:
            core_admin.run(["systemctl", "enable", "ywd-mmdvmhost.service", "ywd-dmrgateway.service"], 15, check=True)
            core_admin.rf_action("rf-start")
            rf_started = True
        except Exception as exc:
            rf_error = str(exc)[:500]
            core_admin.run(["systemctl", "stop", "ywd-dmrgateway.service", "ywd-mmdvmhost.service"], 15)
    else:
        core_admin.run(["systemctl", "disable", "ywd-dmrgateway.service", "ywd-mmdvmhost.service"], 15)

    return {
        "ok": True,
        "complete": True,
        "callsign": candidate["station"]["callsign"],
        "hotspot_id": candidate["station"]["hotspot_id"],
        "changed": changed,
        "apply": applied,
        "rf_started": rf_started,
        "rf_error": rf_error,
        "dashboard": f"http://ywd-hotspot.local:{candidate['web']['port']}/",
    }


def main():
    if os.geteuid() != 0:
        raise SystemExit("ywd-hotspot-setup-admin must run as root")
    if len(sys.argv) != 2 or sys.argv[1] != "setup-finish":
        raise SystemExit("usage: ywd-hotspot-setup-admin setup-finish")
    print(json.dumps(finish(payload()), separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:800]}, separators=(",", ":")))
        raise SystemExit(1)
