#!/usr/bin/env python3
"""Read-only dashboard projection for TGIF Control Center runtime state."""
from __future__ import annotations

import time

import dashboard_core as core
import tgif_scanner

_SERVICE_AT = 0.0
_SERVICE_ACTIVE = False


def _service_active(force=False):
    global _SERVICE_AT, _SERVICE_ACTIVE
    now = time.monotonic()
    if not force and now - _SERVICE_AT < 2.0:
        return _SERVICE_ACTIVE
    _SERVICE_ACTIVE = core.run(["systemctl", "is-active", "--quiet", "ywd-tgif-scanner.service"], 2) == ""
    # systemctl --quiet normally has no stdout whether active or not, so use the
    # ordinary text form for a truthful unprivileged status check.
    state = core.run(["systemctl", "is-active", "ywd-tgif-scanner.service"], 2).strip()
    _SERVICE_ACTIVE = state == "active"
    _SERVICE_AT = now
    return _SERVICE_ACTIVE


def public_status():
    cfg = core.canonical_cfg()
    tg = cfg.get("tgif") if isinstance(cfg.get("tgif"), dict) else {}
    radio = cfg.get("radio") if isinstance(cfg.get("radio"), dict) else {}
    station = cfg.get("station") if isinstance(cfg.get("station"), dict) else {}
    prefs = tgif_scanner.preferences(cfg)
    runtime = tgif_scanner._json(tgif_scanner.RUNTIME, {})
    if not isinstance(runtime, dict):
        runtime = {}
    active = _service_active()
    if not active and runtime.get("active"):
        runtime = dict(runtime)
        runtime["active"] = False
        runtime["state"] = "stopped"
    return {
        "ok": True,
        "available": bool(tg.get("enabled")),
        "tgif_enabled": bool(tg.get("enabled")),
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
