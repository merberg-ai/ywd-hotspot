#!/usr/bin/env python3
"""Read the trusted passive DMR voice runtime ring for capability-gated clients."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

STATE = Path(os.environ.get("YWD_MMDVM_VOICE_STATE", "/run/ywd-hotspot-voice/voice.json"))
MAX_PUBLIC = 64
_CACHE_LOCK = threading.Lock()
_CACHE_STAMP = None
_CACHE_DOC = None


def _empty(status="unavailable"):
    return {"schema": 1, "bridge": {"status": status}, "next_seq": 1, "frames": []}


def _stamp():
    st = STATE.stat()
    return (int(st.st_ino), int(st.st_mtime_ns), int(st.st_size))


def read_state():
    """Read one immutable snapshot, reparsing only when the atomic file changes."""
    global _CACHE_STAMP, _CACHE_DOC
    try:
        stamp = _stamp()
    except Exception:
        return _empty("unavailable")

    with _CACHE_LOCK:
        if _CACHE_DOC is not None and stamp == _CACHE_STAMP:
            return _CACHE_DOC
        try:
            doc = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            return _empty("unavailable")
        if not isinstance(doc, dict) or doc.get("schema") != 1:
            return _empty("invalid")
        _CACHE_STAMP = stamp
        _CACHE_DOC = doc
        return doc


def frames_after(after=0, limit=64):
    """Internal bounded cursor read used by diagnostics and streamed audio."""
    try:
        after = max(0, int(after))
    except Exception:
        after = 0
    try:
        limit = max(1, min(MAX_PUBLIC, int(limit)))
    except Exception:
        limit = MAX_PUBLIC

    doc = read_state()
    raw_frames = doc.get("frames") if isinstance(doc.get("frames"), list) else []
    frames = [frame for frame in raw_frames if isinstance(frame, dict) and isinstance(frame.get("seq"), int)]
    oldest = frames[0]["seq"] if frames else int(doc.get("next_seq") or 1)
    newest = frames[-1]["seq"] if frames else max(0, int(doc.get("next_seq") or 1) - 1)
    dropped = bool(after and frames and after < oldest - 1)
    selected = [frame for frame in frames if frame["seq"] > after][:limit]
    cursor = selected[-1]["seq"] if selected else max(after, newest if after == 0 and not frames else after)
    return {
        "doc": doc,
        "after": after,
        "cursor": cursor,
        "oldest_seq": oldest,
        "newest_seq": newest,
        "dropped": dropped,
        "frames": selected,
    }


def public_poll(after=0, limit=32):
    result = frames_after(after, limit)
    doc = result["doc"]
    bridge = doc.get("bridge") if isinstance(doc.get("bridge"), dict) else {}
    heartbeat = bridge.get("heartbeat_at")
    try:
        age = max(0.0, time.time() - float(heartbeat))
    except Exception:
        age = None

    def metric(name):
        try:
            return round(max(0.0, float(bridge.get(name) or 0.0)), 3)
        except Exception:
            return 0.0

    public_bridge = {
        "status": str(bridge.get("status") or "unknown")[:32],
        "heartbeat_age_s": round(age, 3) if age is not None else None,
        "messages": int(bridge.get("messages") or 0),
        "parse_errors": int(bridge.get("parse_errors") or 0),
        "capacity": int(bridge.get("capacity") or 0),
        "writer": str(bridge.get("writer") or "inline")[:24],
        "snapshot_write_ms": metric("snapshot_write_ms"),
        "snapshot_write_max_ms": metric("snapshot_write_max_ms"),
    }
    return {
        "schema": 1,
        "bridge": public_bridge,
        "after": result["after"],
        "cursor": result["cursor"],
        "oldest_seq": result["oldest_seq"],
        "newest_seq": result["newest_seq"],
        "dropped": result["dropped"],
        "frames": result["frames"],
    }
