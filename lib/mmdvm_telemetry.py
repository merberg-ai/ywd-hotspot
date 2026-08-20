#!/usr/bin/env python3
"""Trusted read-only access to the sanitized MMDVM telemetry bridge snapshot."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import mmdvm_session

SNAPSHOT = Path(os.environ.get("YWD_MMDVM_TELEMETRY", "/run/ywd-hotspot-telemetry/telemetry.json"))


def _read():
    try:
        raw = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) and raw.get("schema") == 1 else {}
    except Exception:
        return {}


def _age(now, value):
    try:
        return max(0.0, now - float(value))
    except Exception:
        return None


def public_snapshot(stale_after=8):
    now = time.time()
    raw = _read()
    bridge = raw.get("bridge") if isinstance(raw.get("bridge"), dict) else {}
    heartbeat_age = _age(now, bridge.get("heartbeat_at"))
    online = bool(heartbeat_age is not None and heartbeat_age <= max(3, int(stale_after)))
    status = str(bridge.get("status") or ("offline" if not raw else "stale"))
    if not online:
        status = "stale" if raw else "offline"

    def sample(name):
        item = raw.get(name) if isinstance(raw.get(name), dict) else {}
        return {
            "timestamp": str(item.get("timestamp") or "")[:64],
            "mode": str(item.get("mode") or "")[:20],
            "slot": item.get("slot"),
            "value": item.get("value"),
            "age_s": _age(now, item.get("received_at")),
        }

    dmr = raw.get("dmr") if isinstance(raw.get("dmr"), dict) else {}
    active = dmr.get("active") if isinstance(dmr.get("active"), dict) else None
    last = dmr.get("last") if isinstance(dmr.get("last"), dict) else None
    mmdvm = raw.get("mmdvm") if isinstance(raw.get("mmdvm"), dict) else {}
    rssi = sample("rssi")
    ber = sample("ber")
    mode = str(mmdvm.get("mode") or rssi.get("mode") or ber.get("mode") or "idle")[:20]

    session_state = raw.get("sessions") if isinstance(raw.get("sessions"), dict) else {}
    active_sessions = [
        item for item in (
            mmdvm_session.public_session(entry, now)
            for entry in (session_state.get("active") if isinstance(session_state.get("active"), list) else [])
        ) if item is not None
    ]
    last_session = mmdvm_session.public_session(session_state.get("last"), now)
    recent_sessions = [
        item for item in (
            mmdvm_session.public_session(entry, now)
            for entry in (session_state.get("recent") if isinstance(session_state.get("recent"), list) else [])[:mmdvm_session.MAX_RECENT]
        ) if item is not None
    ]

    return {
        "bridge": {
            "status": status,
            "online": online,
            "heartbeat_age_s": heartbeat_age,
            "messages": int(bridge.get("messages") or 0),
            "parse_errors": int(bridge.get("parse_errors") or 0),
            "topic": str(bridge.get("topic") or "ywd-mmdvm/json")[:100],
        },
        "mode": mode,
        "rssi": rssi,
        "ber": ber,
        "active_call": active,
        "last_event": last,
        "active_session": active_sessions[0] if active_sessions else None,
        "last_session": last_session,
        "sessions": {
            "schema": 1,
            "active": active_sessions,
            "last": last_session,
            "recent": recent_sessions,
        },
        "last_payload_age_s": _age(now, raw.get("last_payload_at")),
    }
