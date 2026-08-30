#!/usr/bin/env python3
"""TGIF-aware dashboard presentation helpers for the dev-tgif branch.

This module deliberately interprets existing DMRGateway/MMDVM state only. It
must not own routing, modem control, credentials, or network sockets.
"""
from __future__ import annotations

import re

import dashboard_core as core

TGIF_RF_BASE = 5_000_000
TGIF_RF_RANGE = 999_999
TGIF_RF_FIRST = TGIF_RF_BASE + 1
TGIF_RF_LAST = TGIF_RF_BASE + TGIF_RF_RANGE
TGIF_KNOWN_TG = {9990: "Parrot"}

_INSTALLED = False
_BASE_SNAPSHOT = None
_LAST_STATE = {
    "brandmeister": {"state": "connecting", "detail": ""},
    "tgif": {"state": "connecting", "detail": ""},
}


def _bm_network_name(cfg: dict) -> str:
    master = str((cfg.get("brandmeister") or {}).get("master") or "")
    head = master.split(".")[0]
    return "BM_" + re.sub(r"[^A-Za-z0-9_-]+", "_", head)


def _network_state_from_lines(lines, name: str, enabled: bool, gateway_active: bool, previous=None):
    if not enabled:
        return "disabled", "Network disabled"
    if not gateway_active:
        return "offline", "DMRGateway is not active"

    needle = str(name or "").lower()
    for line in reversed(list(lines or [])):
        text = str(line)
        low = text.lower()
        if needle and needle not in low:
            continue
        detail = text[-220:]
        if "logged into the master successfully" in low or "login successful" in low:
            return "connected", detail
        if "could not lookup the address of the master" in low:
            return "dns-failed", detail
        if (
            "failed login" in low
            or "wrong-password" in low
            or ("authorisation" in low and ("fail" in low or "nak" in low))
            or ("authentication" in low and "fail" in low)
        ):
            return "auth-failed", detail
        if "not replying" in low or "timeout" in low or "timed out" in low:
            return "master-unreachable", detail
        if "closing dmr network" in low or "socket has failed" in low:
            return "disconnected", detail
        if "opening dmr network" in low or "sending authorisation" in low or "sending configuration" in low:
            return "connecting", detail

    if isinstance(previous, dict) and previous.get("state") not in {None, "disabled", "offline"}:
        return str(previous.get("state")), str(previous.get("detail") or "")
    return "connecting", "Waiting for DMRGateway network login state"


def _decorate_destination(destination: dict) -> None:
    if not isinstance(destination, dict):
        return
    raw = destination.get("id")
    try:
        raw = int(raw) if raw is not None else None
    except Exception:
        raw = None
    if raw is None:
        return

    destination["rf_id"] = raw
    if destination.get("group") and TGIF_RF_FIRST <= raw <= TGIF_RF_LAST:
        network_id = raw - TGIF_RF_BASE
        name = TGIF_KNOWN_TG.get(network_id) or core.KNOWN_TG.get(network_id)
        destination.update(
            network="tgif",
            network_label="TGIF",
            network_id=network_id,
            name=name,
            label=f"TGIF · TG {network_id}" + (f" · {name}" if name else ""),
        )
        return

    if destination.get("group"):
        name = core.KNOWN_TG.get(raw)
        destination.update(
            network="brandmeister",
            network_label="BM",
            network_id=raw,
            name=name,
            label=f"BM · TG {raw}" + (f" · {name}" if name else ""),
        )
    else:
        destination.update(
            network="brandmeister",
            network_label="BM",
            network_id=raw,
            name=None,
            label=f"BM · PRIVATE {raw}",
        )


def annotate_activity(activity):
    if not isinstance(activity, dict):
        return activity
    current = activity.get("current")
    if isinstance(current, dict):
        _decorate_destination(current.get("destination"))
    rows = activity.get("lastheard")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                _decorate_destination(row.get("destination"))
    return activity


def snapshot(headers=None):
    base = _BASE_SNAPSHOT(headers)
    cfg = base.get("config") if isinstance(base.get("config"), dict) else {}
    bm_cfg = cfg.get("brandmeister") if isinstance(cfg.get("brandmeister"), dict) else {}
    tg_cfg = cfg.get("tgif") if isinstance(cfg.get("tgif"), dict) else {}
    states = core.service_states()
    gateway_active = states.get("ywd-dmrgateway.service") == "active"
    lines = core.gateway_lines()

    bm_state, bm_detail = _network_state_from_lines(
        lines,
        _bm_network_name(cfg),
        bool(bm_cfg.get("enabled", True)),
        gateway_active,
        _LAST_STATE.get("brandmeister"),
    )
    tg_state, tg_detail = _network_state_from_lines(
        lines,
        "TGIF_Network",
        bool(tg_cfg.get("enabled", False)),
        gateway_active,
        _LAST_STATE.get("tgif"),
    )
    _LAST_STATE["brandmeister"] = {"state": bm_state, "detail": bm_detail}
    _LAST_STATE["tgif"] = {"state": tg_state, "detail": tg_detail}

    bm = base.setdefault("brandmeister", {})
    bm["state"] = bm_state
    bm["detail"] = bm_detail
    bm["enabled"] = bool(bm_cfg.get("enabled", True))

    base["tgif"] = {
        "enabled": bool(tg_cfg.get("enabled", False)),
        "state": tg_state,
        "detail": tg_detail,
        "master": tg_cfg.get("master", "tgif.network"),
        "port": tg_cfg.get("port", 62031),
        "password_configured": bool(tg_cfg.get("password_configured")),
        "rf_prefix": 5,
        "rf_first": TGIF_RF_FIRST,
        "rf_last": TGIF_RF_LAST,
    }
    annotate_activity(base.get("activity"))
    return base


def install(core_module=core):
    global _INSTALLED, _BASE_SNAPSHOT
    if _INSTALLED:
        return
    _BASE_SNAPSHOT = core_module.snapshot
    core_module.snapshot = snapshot
    _INSTALLED = True


if __name__ == "__main__":
    raise SystemExit("dashboard_tgif.py is a dashboard extension module")
