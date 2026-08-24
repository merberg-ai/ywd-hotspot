#!/usr/bin/env python3
"""Source-only regression check for the private YWD telemetry bus config."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

spec = importlib.util.spec_from_file_location("ywd_generate_config", LIB / "generate-config.py")
if spec is None or spec.loader is None:
    raise SystemExit("[FAIL] unable to load generate-config.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

config = {
    "station": {
        "hotspot_id": 319610401,
        "callsign": "TEST",
        "latitude": 0.0,
        "longitude": 0.0,
    },
    "radio": {
        "frequency_hz": 446_500_000,
        "color_code": 1,
    },
    "brandmeister": {
        "master": "3103.master.brandmeister.network",
        "enabled": True,
    },
}

mmdvm, gateway, _ = mod.render(config)


def section(text: str, name: str) -> dict[str, str]:
    marker = f"[{name}]\n"
    if marker not in text:
        raise AssertionError(f"missing [{name}] section")
    block = text.split(marker, 1)[1].split("\n[", 1)[0]
    out: dict[str, str] = {}
    for raw in block.splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        out[key.strip()] = value.strip()
    return out


mmdvm_mqtt = section(mmdvm, "MQTT")
gateway_mqtt = section(gateway, "MQTT")

assert mmdvm_mqtt.get("Host") == "127.0.0.1", mmdvm_mqtt
assert gateway_mqtt.get("Address") == "127.0.0.1", gateway_mqtt
assert mmdvm_mqtt.get("Port") == "18883", mmdvm_mqtt
assert gateway_mqtt.get("Port") == "18883", gateway_mqtt

print("[OK] MMDVM-Host uses private MQTT 127.0.0.1:18883")
print("[OK] DMRGateway uses private MQTT 127.0.0.1:18883")
print("[OK] telemetry publishers share the YWD loopback broker")
