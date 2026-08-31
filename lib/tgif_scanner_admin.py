#!/usr/bin/env python3
"""Validated privileged controls for the YWD TGIF watchlist scanner."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

APP = Path(os.environ.get("YWD_APP", "/opt/ywd-hotspot/app"))
LIB = APP / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import admin as core_admin
import tgif_scanner

MAX_INPUT = 262144
SERVICE = "ywd-tgif-scanner.service"


def payload() -> dict:
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise ValueError("TGIF scanner request is too large")
    if not raw:
        return {}
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("invalid JSON payload")
    if not isinstance(obj, dict):
        raise ValueError("payload must be an object")
    return obj


def service_active() -> bool:
    p = core_admin.run(["systemctl", "is-active", "--quiet", SERVICE], 5)
    return p.returncode == 0


def scanner_context():
    cfg = core_admin.current()
    tg = cfg.get("tgif") if isinstance(cfg.get("tgif"), dict) else {}
    radio = cfg.get("radio") if isinstance(cfg.get("radio"), dict) else {}
    station = cfg.get("station") if isinstance(cfg.get("station"), dict) else {}
    prefs = tgif_scanner.normalize_preferences(
        core_admin.read_json(tgif_scanner.PREFS, {}),
        str(radio.get("mode") or "simplex"),
    )
    return cfg, tg, radio, station, prefs


def write_preferences(prefs: dict) -> dict:
    cfg, _tg, radio, _station, _old = scanner_context()
    normalized = tgif_scanner.normalize_preferences(prefs, str(radio.get("mode") or "simplex"))
    core_admin.atomic_json(tgif_scanner.PREFS, normalized, mode=0o640, group=True)
    core_admin.audit("tgif-scanner-preferences", {
        "watch_count": len(normalized.get("watchlist", [])),
        "favorite_count": len(normalized.get("favorites", [])),
        "dwell_s": normalized.get("dwell_s"),
        "hold_s": normalized.get("hold_s"),
        "slot": normalized.get("slot"),
    })
    return normalized


def public_status() -> dict:
    cfg, tg, radio, station, prefs = scanner_context()
    runtime = core_admin.read_json(tgif_scanner.RUNTIME, {})
    if not isinstance(runtime, dict):
        runtime = {}
    active = service_active()
    if not active and runtime.get("active"):
        runtime = dict(runtime)
        runtime["active"] = False
        runtime["state"] = "stopped"
    return {
        "ok": True,
        "available": bool(tg.get("enabled")),
        "tgif_enabled": bool(tg.get("enabled")),
        "tgif_state": "configured" if tg.get("enabled") else "disabled",
        "master": tg.get("master", "tgif.network"),
        "hotspot_id": station.get("hotspot_id"),
        "radio_mode": str(radio.get("mode") or "simplex"),
        "service_active": active,
        "preferences": prefs,
        "runtime": runtime,
        "rf_base": tgif_scanner.RF_BASE,
        "rf_max_network_tg": tgif_scanner.RF_MAX_NETWORK_TG,
        "max_watchlist": 10,
        "session_control": "TGIF public session-update API",
        "session_control_generates_rf": False,
    }


def require_tgif() -> tuple:
    cfg, tg, radio, station, prefs = scanner_context()
    if not tg.get("enabled"):
        raise RuntimeError("Enable TGIF in Settings before using TGIF scanner controls")
    if not core_admin.active("ywd-dmrgateway.service"):
        raise RuntimeError("DMRGateway must be running before TGIF session controls can be used")
    tgif_scanner.network_identity(cfg)
    return cfg, tg, radio, station, prefs


def write_command(operation: str) -> dict:
    if not service_active():
        raise RuntimeError("TGIF scanner is not running")
    if operation not in {"hold", "resume", "next"}:
        raise ValueError("unsupported TGIF scanner command")
    core_admin.atomic_json(
        tgif_scanner.COMMAND,
        {"operation": operation, "issued_at": time.time()},
        mode=0o640,
        group=True,
    )
    core_admin.audit(f"tgif-scanner-{operation}")
    return {"ok": True, "command": operation}


def stop_service() -> None:
    core_admin.run(["systemctl", "stop", SERVICE], 15, check=False)


def perform(data: dict) -> dict:
    op = str(data.get("operation") or "status").strip().lower()

    if op == "status":
        return public_status()

    if op == "save":
        prefs = data.get("preferences")
        if not isinstance(prefs, dict):
            raise ValueError("preferences must be an object")
        saved = write_preferences(prefs)
        return {"ok": True, "preferences": saved, "service_active": service_active()}

    if op == "start":
        _cfg, _tg, _radio, _station, prefs = require_tgif()
        if not tgif_scanner.enabled_watchlist(prefs):
            raise ValueError("Add at least one enabled TGIF talkgroup to the watchlist before starting scan")
        try:
            tgif_scanner.COMMAND.unlink()
        except FileNotFoundError:
            pass
        core_admin.run(["systemctl", "start", SERVICE], 15, check=True)
        core_admin.audit("tgif-scanner-start", {
            "watch_count": len(tgif_scanner.enabled_watchlist(prefs)),
            "slot": prefs.get("slot"),
        })
        time.sleep(0.15)
        return public_status()

    if op == "stop":
        stop_service()
        core_admin.audit("tgif-scanner-stop", {"session_left_on_current_tg": True})
        return public_status()

    if op in {"hold", "resume", "next"}:
        require_tgif()
        return write_command(op)

    if op == "tune":
        cfg, _tg, radio, _station, prefs = require_tgif()
        talkgroup = tgif_scanner.valid_tg(data.get("talkgroup"))
        if talkgroup is None:
            raise ValueError("Talkgroup must be 1-999999 and cannot be TG 4000")
        slot = prefs.get("slot", 2)
        if str(radio.get("mode") or "simplex").lower() != "duplex":
            slot = 2
        stop_service()
        out = tgif_scanner.session_update(tgif_scanner.network_identity(cfg), int(slot), talkgroup)
        core_admin.audit("tgif-tune", {"talkgroup": talkgroup, "slot": int(slot), "rf_keyup": False})
        return {"ok": True, "tuned": talkgroup, "rf_talkgroup": tgif_scanner.RF_BASE + talkgroup, "slot": int(slot), "result": out}

    if op == "disconnect":
        cfg, _tg, radio, _station, prefs = require_tgif()
        slot = prefs.get("slot", 2)
        if str(radio.get("mode") or "simplex").lower() != "duplex":
            slot = 2
        stop_service()
        out = tgif_scanner.session_update(
            tgif_scanner.network_identity(cfg), int(slot), tgif_scanner.DISCONNECT_TG
        )
        core_admin.audit("tgif-disconnect", {"talkgroup": 4000, "slot": int(slot), "rf_keyup": False})
        return {"ok": True, "disconnected": True, "slot": int(slot), "result": out}

    raise ValueError("unsupported TGIF scanner operation")


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("ywd-hotspot TGIF scanner admin must run as root")
    if len(sys.argv) != 2 or sys.argv[1] != "tgif-control":
        raise SystemExit("usage: tgif_scanner_admin.py tgif-control")
    out = perform(payload())
    print(json.dumps(out, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:1000]}, separators=(",", ":")))
        raise SystemExit(1)
