#!/usr/bin/env python3
"""TGIF-aware dashboard presentation and read-only directory helpers.

This module interprets existing DMRGateway/MMDVM state and may fetch TGIF's
public talkgroup directory for names/search. It does not own DMR routing, modem
control, credentials, or network-session control.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request

import dashboard_core as core

TGIF_RF_BASE = 5_000_000
TGIF_RF_RANGE = 999_999
TGIF_RF_FIRST = TGIF_RF_BASE + 1
TGIF_RF_LAST = TGIF_RF_BASE + TGIF_RF_RANGE
TGIF_KNOWN_TG = {9990: "Parrot"}
TGIF_DIRECTORY_URL = "https://api.tgif.network/dmr/talkgroups/json"
TGIF_DIRECTORY_CACHE = core.VAR / "tgif-talkgroup-directory.json"
TGIF_DIRECTORY_TTL = 24 * 3600
TGIF_DIRECTORY_LOCK = threading.Lock()
TGIF_DIRECTORY_MEM = {"rows": None, "cached_at": 0.0, "stale": True, "error": None}
TGIF_NAME_MEM = {"mtime": None, "names": dict(TGIF_KNOWN_TG)}

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


def _tgif_id(value):
    try:
        ident = int(value)
    except Exception:
        return None
    return ident if 1 <= ident <= 16_777_215 else None


def _tgif_name(value) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())[:160]


def normalize_tgif_talkgroups(payload):
    """Normalize TGIF directory JSON into small id/name metadata rows.

    The current TGIF endpoint returns an array containing id/name fields. The
    defensive shapes below keep the dashboard tolerant of harmless API format
    changes without accepting arbitrary nested data into the appliance cache.
    """
    if isinstance(payload, dict):
        items = None
        for key in ("talkgroups", "groups", "data", "results"):
            if isinstance(payload.get(key), list):
                items = payload[key]
                break
        if items is None:
            items = []
            for key, value in payload.items():
                if isinstance(value, dict):
                    row = dict(value)
                    row.setdefault("id", key)
                    items.append(row)
    elif isinstance(payload, list):
        items = payload
    else:
        items = []

    rows = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = _tgif_id(item.get("id", item.get("talkgroup", item.get("tg", item.get("number")))))
        if ident is None:
            continue
        name = _tgif_name(item.get("name", item.get("label", item.get("title", ""))))
        if not name:
            name = f"TG {ident}"
        row = {
            "id": ident,
            "name": name,
            "supported": ident <= TGIF_RF_RANGE,
            "rf_talkgroup": TGIF_RF_BASE + ident if ident <= TGIF_RF_RANGE else None,
        }
        for key in ("country", "language", "website"):
            value = _tgif_name(item.get(key, ""))
            if value:
                row[key] = value
        rows[ident] = row
    return [rows[k] for k in sorted(rows)]


def _read_directory_cache():
    try:
        doc = json.loads(TGIF_DIRECTORY_CACHE.read_text(encoding="utf-8"))
        rows = normalize_tgif_talkgroups(doc.get("rows", [])) if isinstance(doc, dict) else []
        cached_at = float(doc.get("cached_at", 0)) if isinstance(doc, dict) else 0.0
        return rows, cached_at
    except Exception:
        return [], 0.0


def _write_directory_cache(rows, cached_at):
    core.write_var_json(TGIF_DIRECTORY_CACHE, {
        "cached_at": cached_at,
        "source": TGIF_DIRECTORY_URL,
        "rows": rows,
    })
    TGIF_NAME_MEM["mtime"] = None


def _fetch_directory():
    req = urllib.request.Request(
        TGIF_DIRECTORY_URL,
        headers={
            "User-Agent": f"YWD-Hotspot/{core.VERSION}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"TGIF directory request failed: {exc}")
    if len(raw) > 8 * 1024 * 1024:
        raise RuntimeError("TGIF directory response is unexpectedly large")
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except Exception as exc:
        raise RuntimeError("TGIF directory returned invalid JSON") from exc
    rows = normalize_tgif_talkgroups(payload)
    if not rows:
        raise RuntimeError("TGIF directory returned no recognized talkgroups")
    return rows


def tgif_directory(force=False):
    now = time.time()
    with TGIF_DIRECTORY_LOCK:
        mem_rows = TGIF_DIRECTORY_MEM.get("rows")
        mem_at = float(TGIF_DIRECTORY_MEM.get("cached_at") or 0)
        if mem_rows is not None and not force and now - mem_at < TGIF_DIRECTORY_TTL:
            return mem_rows, mem_at, False, TGIF_DIRECTORY_MEM.get("error")

        disk_rows, disk_at = _read_directory_cache()
        if disk_rows and not force and now - disk_at < TGIF_DIRECTORY_TTL:
            TGIF_DIRECTORY_MEM.update(rows=disk_rows, cached_at=disk_at, stale=False, error=None)
            return disk_rows, disk_at, False, None

        try:
            rows = _fetch_directory()
            cached_at = now
            _write_directory_cache(rows, cached_at)
            TGIF_DIRECTORY_MEM.update(rows=rows, cached_at=cached_at, stale=False, error=None)
            return rows, cached_at, False, None
        except Exception as exc:
            fallback = disk_rows or mem_rows or []
            fallback_at = disk_at or mem_at
            if fallback:
                error = str(exc)[:300]
                TGIF_DIRECTORY_MEM.update(rows=fallback, cached_at=fallback_at, stale=True, error=error)
                return fallback, fallback_at, True, error
            raise


def search_tgif_talkgroups(query="", ids=None, limit=50, force=False):
    rows, cached_at, stale, error = tgif_directory(force=force)
    ids = ids or []
    idset = {_tgif_id(value) for value in ids}
    idset.discard(None)
    q = " ".join(str(query or "").lower().split())[:80]
    terms = q.split()

    def matches(row):
        ident = int(row["id"])
        if idset:
            return ident in idset
        if not terms:
            return False
        hay = f"{ident} {row.get('name', '')} {row.get('country', '')} {row.get('language', '')}".lower()
        return all(term in hay for term in terms)

    found = [dict(row) for row in rows if matches(row)]
    if idset:
        found.sort(key=lambda row: int(row["id"]))
    else:
        def score(row):
            sid = str(row["id"])
            name = str(row.get("name") or "").lower()
            return (
                0 if sid == q else
                1 if name == q else
                2 if sid.startswith(q) else
                3 if name.startswith(q) else 4,
                len(name), int(row["id"]),
            )
        found.sort(key=score)
    found = found[:max(1, min(int(limit), 100))]
    return {
        "ok": True,
        "results": found,
        "directory_count": len(rows),
        "cached_at": cached_at,
        "stale": stale,
        "error": error,
        "source": TGIF_DIRECTORY_URL,
        "rf_base": TGIF_RF_BASE,
        "rf_max_network_tg": TGIF_RF_RANGE,
    }


def _directory_names():
    names = dict(TGIF_KNOWN_TG)
    try:
        mtime = TGIF_DIRECTORY_CACHE.stat().st_mtime_ns
    except Exception:
        mtime = None
    if mtime is not None and TGIF_NAME_MEM.get("mtime") == mtime:
        return TGIF_NAME_MEM.get("names", names)
    rows, _ = _read_directory_cache()
    for row in rows:
        ident = _tgif_id(row.get("id"))
        name = _tgif_name(row.get("name"))
        if ident is not None and name:
            names[ident] = name
    TGIF_NAME_MEM["mtime"] = mtime
    TGIF_NAME_MEM["names"] = names
    return names


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
        name = _directory_names().get(network_id) or core.KNOWN_TG.get(network_id)
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
