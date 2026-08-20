#!/usr/bin/env python3
"""Bounded normalization/correlation for sanitized MMDVM DMR events."""
from __future__ import annotations

from copy import deepcopy

MAX_RECENT = 12
START_ACTIONS = {"start", "late_entry"}
TERMINAL_ACTIONS = {"end", "lost", "timeout", "rejected", "invalid"}


def initial_sessions():
    return {"schema": 1, "active": [], "last": None, "recent": []}


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except Exception:
        return None


def _integer(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _group(value):
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"yes", "true", "1", "group"}:
        return True
    if text in {"no", "false", "0", "private"}:
        return False
    return None


def _direction(source):
    source = str(source or "").strip().lower()
    if source == "rf":
        return "rf_to_network"
    if source == "network":
        return "network_to_rf"
    return "unknown"


def _call_type(event):
    if event.get("frames") is not None:
        return "data"
    if any(event.get(key) is not None for key in ("src_id", "dst_id", "src_info")):
        return "voice"
    return "unknown"


def _metrics(event):
    rssi = event.get("rssi") if isinstance(event.get("rssi"), dict) else {}
    normalized_rssi = {
        "min": _number(rssi.get("min")),
        "max": _number(rssi.get("max")),
        "avg": _number(rssi.get("ave") if "ave" in rssi else rssi.get("avg")),
    }
    if all(value is None for value in normalized_rssi.values()):
        normalized_rssi = None
    return {
        "duration_s": _number(event.get("duration")),
        "ber_pct": _number(event.get("ber")),
        "packet_loss_pct": _number(event.get("loss")),
        "rssi_dbm": normalized_rssi,
    }


def _session_id(event):
    slot = _integer(event.get("slot"))
    try:
        stamp = int(float(event.get("received_at")) * 1000.0)
    except Exception:
        stamp = 0
    return f"dmr-{slot if slot is not None else 'x'}-{stamp}"


def _new_session(event):
    source = str(event.get("source") or "").strip().lower() or None
    group = _group(event.get("group"))
    return {
        "session_id": _session_id(event),
        "protocol": "DMR",
        "state": "active",
        "result": None,
        "correlation": "open",
        "call_type": _call_type(event),
        "late_entry": str(event.get("action") or "") == "late_entry",
        "slot": _integer(event.get("slot")),
        "source": source,
        "direction": _direction(source),
        "src_id": _integer(event.get("src_id")),
        "src_info": event.get("src_info"),
        "dst_id": _integer(event.get("dst_id")),
        "group": group,
        "destination_type": "group" if group is True else "private" if group is False else "unknown",
        "frames": _integer(event.get("frames")),
        "started_at": event.get("timestamp"),
        "ended_at": None,
        "started_received_at": _number(event.get("received_at")),
        "ended_received_at": None,
        "last_action": str(event.get("action") or "start"),
        "last_event_at": event.get("timestamp"),
        "event_count": 1,
        "metrics": _metrics(event),
    }


def _merge_identity(session, event):
    for key in ("src_info",):
        if not session.get(key) and event.get(key):
            session[key] = event.get(key)
    for key in ("src_id", "dst_id", "frames"):
        value = _integer(event.get(key))
        if session.get(key) is None and value is not None:
            session[key] = value
    if session.get("group") is None:
        group = _group(event.get("group"))
        if group is not None:
            session["group"] = group
            session["destination_type"] = "group" if group else "private"
    if not session.get("source") and event.get("source"):
        source = str(event.get("source") or "").strip().lower() or None
        session["source"] = source
        session["direction"] = _direction(source)


def _merge_metrics(session, event):
    incoming = _metrics(event)
    metrics = session.get("metrics") if isinstance(session.get("metrics"), dict) else {}
    for key in ("duration_s", "ber_pct", "packet_loss_pct", "rssi_dbm"):
        if incoming.get(key) is not None:
            metrics[key] = incoming[key]
        elif key not in metrics:
            metrics[key] = None
    session["metrics"] = metrics


def _finish(session, event, correlation="matched"):
    result = str(event.get("action") or "end")
    _merge_identity(session, event)
    _merge_metrics(session, event)
    session["state"] = "completed" if result == "end" else result
    session["result"] = result
    session["correlation"] = correlation
    session["ended_at"] = event.get("timestamp")
    session["ended_received_at"] = _number(event.get("received_at"))
    session["last_action"] = result
    session["last_event_at"] = event.get("timestamp")
    session["event_count"] = int(session.get("event_count") or 0) + 1
    return session


def _terminal_only(event):
    session = _new_session(event)
    session["started_at"] = None
    session["started_received_at"] = None
    session["state"] = "active"
    session["event_count"] = 0
    return _finish(session, event, "orphan")


def _append_recent(state, session):
    recent = state.get("recent") if isinstance(state.get("recent"), list) else []
    recent.insert(0, deepcopy(session))
    state["recent"] = recent[:MAX_RECENT]
    state["last"] = deepcopy(session)


def observe(state, event):
    """Apply one sanitized DMR event and return a normalized bounded state."""
    if not isinstance(state, dict) or state.get("schema") != 1:
        state = initial_sessions()
    else:
        state = deepcopy(state)
        state.setdefault("active", [])
        state.setdefault("recent", [])
        state.setdefault("last", None)

    if not isinstance(event, dict):
        return state
    action = str(event.get("action") or "").strip().lower()
    if action not in START_ACTIONS | TERMINAL_ACTIONS:
        return state

    slot = _integer(event.get("slot"))
    active = [item for item in state.get("active", []) if isinstance(item, dict)]

    if action in START_ACTIONS:
        survivors = []
        for current in active:
            if slot is not None and _integer(current.get("slot")) == slot:
                synthetic = {
                    "action": "superseded",
                    "slot": slot,
                    "timestamp": event.get("timestamp"),
                    "received_at": event.get("received_at"),
                }
                _append_recent(state, _finish(current, synthetic, "superseded"))
            else:
                survivors.append(current)
        survivors.append(_new_session(event))
        state["active"] = sorted(survivors, key=lambda item: (_integer(item.get("slot")) or 99))
        return state

    match = None
    survivors = []
    for current in active:
        if match is None and slot is not None and _integer(current.get("slot")) == slot:
            match = current
        else:
            survivors.append(current)
    state["active"] = survivors

    completed = _finish(match, event, "matched") if match is not None else _terminal_only(event)
    _append_recent(state, completed)
    return state


def public_session(raw, now=None):
    """Whitelist the normalized session contract for WebUI/plugin consumers."""
    if not isinstance(raw, dict):
        return None
    metrics = raw.get("metrics") if isinstance(raw.get("metrics"), dict) else {}
    rssi = metrics.get("rssi_dbm") if isinstance(metrics.get("rssi_dbm"), dict) else None
    out = {
        "session_id": str(raw.get("session_id") or "")[:80],
        "protocol": "DMR",
        "state": str(raw.get("state") or "unknown")[:20],
        "result": str(raw.get("result") or "")[:20] or None,
        "correlation": str(raw.get("correlation") or "unknown")[:20],
        "call_type": str(raw.get("call_type") or "unknown")[:20],
        "late_entry": bool(raw.get("late_entry")),
        "slot": _integer(raw.get("slot")),
        "source": str(raw.get("source") or "")[:20] or None,
        "direction": str(raw.get("direction") or "unknown")[:30],
        "src_id": _integer(raw.get("src_id")),
        "src_info": str(raw.get("src_info") or "")[:160] or None,
        "dst_id": _integer(raw.get("dst_id")),
        "group": raw.get("group") if isinstance(raw.get("group"), bool) else None,
        "destination_type": str(raw.get("destination_type") or "unknown")[:20],
        "frames": _integer(raw.get("frames")),
        "started_at": str(raw.get("started_at") or "")[:64] or None,
        "ended_at": str(raw.get("ended_at") or "")[:64] or None,
        "last_action": str(raw.get("last_action") or "")[:20],
        "event_count": max(0, _integer(raw.get("event_count")) or 0),
        "metrics": {
            "duration_s": _number(metrics.get("duration_s")),
            "ber_pct": _number(metrics.get("ber_pct")),
            "packet_loss_pct": _number(metrics.get("packet_loss_pct")),
            "rssi_dbm": {
                "min": _number(rssi.get("min")),
                "max": _number(rssi.get("max")),
                "avg": _number(rssi.get("avg")),
            } if rssi else None,
        },
    }
    if now is not None:
        stamp = raw.get("ended_received_at") if raw.get("ended_received_at") is not None else raw.get("started_received_at")
        try:
            out["age_s"] = max(0.0, float(now) - float(stamp))
        except Exception:
            out["age_s"] = None
    return out
