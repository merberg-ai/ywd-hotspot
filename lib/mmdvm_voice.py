#!/usr/bin/env python3
"""Read the trusted passive DMR voice runtime ring for capability-gated clients."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

STATE = Path(os.environ.get("YWD_MMDVM_VOICE_STATE", "/run/ywd-hotspot-voice/voice.json"))
MAX_PUBLIC = 64


def read_state():
    try:
        doc = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": 1, "bridge": {"status": "unavailable"}, "next_seq": 1, "frames": []}
    if not isinstance(doc, dict) or doc.get("schema") != 1:
        return {"schema": 1, "bridge": {"status": "invalid"}, "next_seq": 1, "frames": []}
    return doc


def public_poll(after=0, limit=32):
    try:
        after = max(0, int(after))
    except Exception:
        after = 0
    try:
        limit = max(1, min(MAX_PUBLIC, int(limit)))
    except Exception:
        limit = 32

    doc = read_state()
    raw_frames = doc.get("frames") if isinstance(doc.get("frames"), list) else []
    frames = [frame for frame in raw_frames if isinstance(frame, dict) and isinstance(frame.get("seq"), int)]
    oldest = frames[0]["seq"] if frames else int(doc.get("next_seq") or 1)
    newest = frames[-1]["seq"] if frames else max(0, int(doc.get("next_seq") or 1) - 1)
    dropped = bool(after and frames and after < oldest - 1)
    selected = [frame for frame in frames if frame["seq"] > after][:limit]
    cursor = selected[-1]["seq"] if selected else max(after, newest if after == 0 and not frames else after)

    bridge = doc.get("bridge") if isinstance(doc.get("bridge"), dict) else {}
    heartbeat = bridge.get("heartbeat_at")
    try:
        age = max(0.0, time.time() - float(heartbeat))
    except Exception:
        age = None
    public_bridge = {
        "status": str(bridge.get("status") or "unknown")[:32],
        "heartbeat_age_s": round(age, 3) if age is not None else None,
        "messages": int(bridge.get("messages") or 0),
        "parse_errors": int(bridge.get("parse_errors") or 0),
        "capacity": int(bridge.get("capacity") or 0),
    }
    return {
        "schema": 1,
        "bridge": public_bridge,
        "after": after,
        "cursor": cursor,
        "oldest_seq": oldest,
        "newest_seq": newest,
        "dropped": dropped,
        "frames": selected,
    }
