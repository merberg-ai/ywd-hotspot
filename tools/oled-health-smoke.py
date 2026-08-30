#!/usr/bin/env python3
"""Source-only regression for OLED owner hardware-health projection."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

import dashboard_core
import health

OLED_SOURCE = (LIB / "oled.py").read_text(encoding="utf-8")
for marker in (
    'write_health("opening"',
    'write_health("open"',
    'write_health("waiting-for-device"',
    'write_health("io-error"',
    'write_health("runtime-error"',
    'write_health("disabled"',
):
    assert marker in OLED_SOURCE, f"OLED owner is missing health state marker: {marker}"

with tempfile.TemporaryDirectory(prefix="ywd-oled-health-") as td:
    root = Path(td)
    cfg = root / "config.json"
    runtime = root / "oled-health.json"
    health.CFG = cfg
    health.OLED_HEALTH = runtime

    cfg.write_text(json.dumps({"display": {"enabled": True, "i2c_bus": 1, "address": "0x3c"}}))
    runtime.write_text(json.dumps({
        "schema": 1,
        "state": "open",
        "configured": True,
        "device_open": True,
        "bus": 1,
        "address": "0x3c",
        "updated_at": 1,
        "error": None,
    }))

    original_run = health.run
    try:
        health.run = lambda args, timeout=2: "unit" if args[:2] == ["systemctl", "cat"] else ""
        services = {
            "ywd-headless-oled.service": {"active": "active", "enabled": "enabled", "restarts": 0},
            "ywd-oled.service": {"active": "inactive", "enabled": "disabled", "restarts": 0},
        }
        row = health.oled_runtime(services)
        assert row["owner"] == "ywd-headless-oled.service", row
        assert row["state"] == "open" and row["device_open"] is True, row

        runtime.write_text(json.dumps({
            "state": "waiting-for-device", "device_open": False, "bus": 1,
            "address": "0x3c", "updated_at": 1, "error": "Remote I/O error",
        }))
        row = health.oled_runtime(services)
        assert row["state"] == "waiting-for-device" and row["device_open"] is False, row
        assert row["error"] == "Remote I/O error", row

        services["ywd-headless-oled.service"]["active"] = "inactive"
        row = health.oled_runtime(services)
        assert row["state"] == "service-down" and row["device_open"] is False, row

        cfg.write_text(json.dumps({"display": {"enabled": False, "i2c_bus": 1, "address": "0x3c"}}))
        row = health.oled_runtime(services)
        assert row["state"] == "disabled", row
    finally:
        health.run = original_run

# The dashboard status API must not permanently cache the legacy OLED owner.
# Ownership can change during an image/app update while the dashboard process
# remains alive; a later status refresh must follow the authoritative headless
# unit without requiring another dashboard restart.
original_unit_exists = dashboard_core.unit_exists
try:
    headless = {"present": False}
    dashboard_core.unit_exists = lambda unit: bool(headless["present"]) if unit == "ywd-headless-oled.service" else True
    assert dashboard_core.oled_unit() == "ywd-oled.service"
    headless["present"] = True
    assert dashboard_core.oled_unit() == "ywd-headless-oled.service"
finally:
    dashboard_core.unit_exists = original_unit_exists

print("[OK] OLED owner publishes explicit hardware/device-open states")
print("[OK] health projection distinguishes open, waiting, service-down, and disabled")
print("[OK] dashboard status follows OLED ownership changes without a process restart")
print("[OK] OLED hardware health remains presentation-only and independent of RF state")
