#!/usr/bin/env python3
"""Read-only helpers for locally observed DMR station history."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB = Path(os.environ.get("YWD_DMR_OBSERVATIONS", "/var/lib/ywd-hotspot/contact-observations.sqlite3"))
MAX_BATCH = 64


def _dmr_id(value) -> int | None:
    try:
        ident = int(str(value).strip())
    except Exception:
        return None
    return ident if 1 <= ident <= 16_777_215 else None


def _callsign(value) -> str | None:
    text = str(value or "").strip().upper()[:24]
    if not text or any(not (ch.isalnum() or ch in {"/", "-"}) for ch in text):
        return None
    return text


def database_meta() -> dict:
    try:
        stat = DB.stat()
        return {
            "present": True,
            "updated_at": float(stat.st_mtime),
            "size_bytes": int(stat.st_size),
        }
    except OSError:
        return {"present": False, "updated_at": None, "size_bytes": None}


def lookup(ids=None, callsigns=None) -> dict:
    """Return bounded aggregate observation records for requested identities."""
    ordered_ids = []
    seen_ids = set()
    for value in list(ids or [])[:MAX_BATCH]:
        ident = _dmr_id(value)
        if ident is not None and ident not in seen_ids:
            seen_ids.add(ident)
            ordered_ids.append(ident)

    ordered_calls = []
    seen_calls = set()
    for value in list(callsigns or [])[:MAX_BATCH]:
        call = _callsign(value)
        if call is not None and call not in seen_calls:
            seen_calls.add(call)
            ordered_calls.append(call)

    meta = database_meta()
    if not ordered_ids and not ordered_calls:
        return {"ok": True, "database": meta, "results": []}
    if not meta["present"]:
        return {"ok": True, "database": meta, "results": []}

    clauses = []
    params = []
    if ordered_ids:
        clauses.append("dmr_id IN (%s)" % ",".join("?" for _ in ordered_ids))
        params.extend(ordered_ids)
    if ordered_calls:
        clauses.append("callsign IN (%s)" % ",".join("?" for _ in ordered_calls))
        params.extend(ordered_calls)

    rows = []
    try:
        uri = f"file:{DB}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=0.75) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT identity_key, dmr_id, callsign, first_seen, last_seen, qso_count, "
                "rf_count, network_count, total_duration_s, last_destination, last_group, "
                "last_path, last_slot FROM station_observations WHERE " + " OR ".join(clauses),
                params,
            ).fetchall()
    except (sqlite3.Error, OSError):
        return {"ok": True, "database": database_meta(), "results": []}

    # An identity may historically have appeared once as a numeric ID and once
    # as a callsign. Aggregate matching rows so the plugin gets one useful
    # station-level record instead of exposing storage-key implementation detail.
    groups: dict[str, dict] = {}
    for row in rows:
        ident = _dmr_id(row["dmr_id"])
        call = _callsign(row["callsign"])
        key = f"id:{ident}" if ident is not None else f"call:{call or row['identity_key']}"
        if ident is not None and call in seen_calls:
            key = f"call:{call}"
        item = groups.setdefault(key, {
            "dmr_id": ident,
            "callsign": call,
            "first_seen": None,
            "last_seen": None,
            "qso_count": 0,
            "rf_count": 0,
            "network_count": 0,
            "total_duration_s": 0.0,
            "last_destination": None,
            "last_group": False,
            "last_path": None,
            "last_slot": None,
        })
        if item["dmr_id"] is None and ident is not None:
            item["dmr_id"] = ident
        if not item["callsign"] and call:
            item["callsign"] = call
        first = float(row["first_seen"] or 0.0)
        last = float(row["last_seen"] or 0.0)
        if first > 0 and (item["first_seen"] is None or first < item["first_seen"]):
            item["first_seen"] = first
        if last >= float(item["last_seen"] or 0.0):
            item["last_seen"] = last or item["last_seen"]
            item["last_destination"] = row["last_destination"]
            item["last_group"] = bool(row["last_group"])
            item["last_path"] = str(row["last_path"] or "")[:12] or None
            item["last_slot"] = int(row["last_slot"]) if row["last_slot"] is not None else None
        item["qso_count"] += int(row["qso_count"] or 0)
        item["rf_count"] += int(row["rf_count"] or 0)
        item["network_count"] += int(row["network_count"] or 0)
        item["total_duration_s"] += float(row["total_duration_s"] or 0.0)

    results = []
    for item in groups.values():
        item["total_duration_s"] = round(float(item["total_duration_s"] or 0.0), 1)
        item["found"] = bool(item["qso_count"])
        results.append(item)
    results.sort(key=lambda item: float(item.get("last_seen") or 0.0), reverse=True)
    return {"ok": True, "database": database_meta(), "results": results[:MAX_BATCH]}
