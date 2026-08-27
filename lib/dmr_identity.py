#!/usr/bin/env python3
"""Bounded read-only lookup helpers for the local YWD-Hotspot DMR directory."""
from __future__ import annotations

import os
import time
from collections import OrderedDict
from pathlib import Path

import dmr_observations

DB = Path(os.environ.get("YWD_DMRID_FILE", "/var/lib/ywd-hotspot/DMRIds.dat"))
RICH_DB = Path(os.environ.get("YWD_DMR_CONTACTS_FILE", "/var/lib/ywd-hotspot/DMRContacts.tsv"))
SOURCE = "RadioID.net"
MAX_BATCH = 64
MAX_SEARCH = 25
CACHE_LIMIT = 512
_CACHE: OrderedDict[int, dict | None] = OrderedDict()
_CACHE_STAMP: tuple[str, int, int] | None = None


def _active_db() -> Path:
    return RICH_DB if RICH_DB.is_file() else DB


def _stamp() -> tuple[str, int, int] | None:
    path = _active_db()
    try:
        stat = path.stat()
        return str(path), int(stat.st_mtime_ns), int(stat.st_size)
    except OSError:
        return None


def _sync_cache():
    global _CACHE_STAMP
    stamp = _stamp()
    if stamp != _CACHE_STAMP:
        _CACHE.clear()
        _CACHE_STAMP = stamp
    return stamp


def _cache_put(ident: int, row: dict | None) -> None:
    _CACHE[ident] = row
    _CACHE.move_to_end(ident)
    while len(_CACHE) > CACHE_LIMIT:
        _CACHE.popitem(last=False)


def _dmr_id(value) -> int | None:
    try:
        ident = int(str(value).strip())
    except Exception:
        return None
    return ident if 1 <= ident <= 16_777_215 else None


def _clean(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _row(ident, callsign, name="", city="", state="", country=""):
    call = _clean(callsign, 24).upper()
    return {
        "dmr_id": int(ident),
        "callsign": call or None,
        "name": _clean(name, 80) or None,
        "city": _clean(city, 64) or None,
        "state": _clean(state, 48) or None,
        "country": _clean(country, 48) or None,
        "found": bool(call),
    }


def _parse_line(line: str):
    parts = line.rstrip("\r\n").split("\t")
    if len(parts) < 2 or not parts[0].isdigit():
        return None
    ident = _dmr_id(parts[0])
    if ident is None:
        return None
    padded = parts + [""] * max(0, 6 - len(parts))
    return _row(ident, padded[1], padded[2], padded[3], padded[4], padded[5])


def _diagnostics(started: float, scanned: int, cache_hit: bool = False) -> dict:
    return {
        "elapsed_ms": max(0, int(round((time.monotonic() - started) * 1000))),
        "scanned_records": max(0, int(scanned)),
        "cache_hit": bool(cache_hit),
    }


def _with_observations(result: dict) -> dict:
    rows = result.get("results") if isinstance(result.get("results"), list) else []
    ids = [row.get("dmr_id") for row in rows if isinstance(row, dict) and row.get("dmr_id") is not None]
    calls = [row.get("callsign") for row in rows if isinstance(row, dict) and row.get("callsign")]
    try:
        result["observations"] = dmr_observations.lookup(ids, calls)
    except Exception:
        result["observations"] = {"ok": True, "database": dmr_observations.database_meta(), "results": []}
    return result


def database_meta() -> dict:
    stamp = _sync_cache()
    path = _active_db()
    if stamp is None:
        return {"source": SOURCE, "present": False, "updated_at": None, "size_bytes": None, "rich_fields": False}
    try:
        stat = path.stat()
        return {
            "source": SOURCE,
            "present": True,
            "updated_at": float(stat.st_mtime),
            "size_bytes": int(stat.st_size),
            "rich_fields": path == RICH_DB,
        }
    except OSError:
        return {"source": SOURCE, "present": False, "updated_at": None, "size_bytes": None, "rich_fields": False}


def lookup_ids(values) -> dict:
    """Resolve at most MAX_BATCH DMR IDs with one bounded sequential file scan."""
    started = time.monotonic()
    scanned = 0
    ordered = []
    seen = set()
    for value in list(values or [])[:MAX_BATCH]:
        ident = _dmr_id(value)
        if ident is not None and ident not in seen:
            seen.add(ident)
            ordered.append(ident)

    meta = database_meta()
    if not ordered:
        return _with_observations({"ok": True, "database": meta, "results": [], "diagnostics": _diagnostics(started, scanned)})

    pending = set()
    found = {}
    cache_hits = 0
    for ident in ordered:
        if ident in _CACHE:
            found[ident] = _CACHE[ident]
            _CACHE.move_to_end(ident)
            cache_hits += 1
        else:
            pending.add(ident)

    if pending and meta["present"]:
        try:
            with _active_db().open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not pending:
                        break
                    scanned += 1
                    parsed = _parse_line(line)
                    if not parsed or parsed["dmr_id"] not in pending:
                        continue
                    ident = parsed["dmr_id"]
                    found[ident] = parsed
                    _cache_put(ident, parsed)
                    pending.discard(ident)
        except OSError:
            pass

    for ident in pending:
        found[ident] = None
        _cache_put(ident, None)

    results = []
    for ident in ordered:
        row = found.get(ident)
        results.append(dict(row) if row else _row(ident, ""))
    return _with_observations({
        "ok": True,
        "database": database_meta(),
        "results": results,
        "diagnostics": _diagnostics(started, scanned, cache_hit=bool(cache_hits and cache_hits == len(ordered))),
    })


def search(query, limit=15) -> dict:
    """Search by exact/prefix callsign or DMR ID. Intended for user-triggered lookup."""
    started = time.monotonic()
    scanned = 0
    q = " ".join(str(query or "").upper().split())[:32]
    try:
        lim = max(1, min(MAX_SEARCH, int(limit)))
    except Exception:
        lim = 15
    if not q:
        raise ValueError("Enter a callsign or DMR ID")
    if q.isdigit():
        result = lookup_ids([q])
        result["query"] = q
        return result
    if len(q) < 2 or any(not (ch.isalnum() or ch in {"/", "-"}) for ch in q):
        raise ValueError("Enter at least 2 callsign characters")

    meta = database_meta()
    cached = [
        dict(row)
        for row in reversed(_CACHE.values())
        if row and row.get("callsign") == q
    ][:lim]
    if cached:
        return _with_observations({
            "ok": True,
            "database": meta,
            "query": q,
            "results": cached,
            "diagnostics": _diagnostics(started, 0, cache_hit=True),
        })

    rows = []
    exact = None
    if meta["present"]:
        try:
            with _active_db().open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    scanned += 1
                    parsed = _parse_line(line)
                    if not parsed:
                        continue
                    callsign = str(parsed.get("callsign") or "")
                    if not callsign.startswith(q):
                        continue
                    if callsign == q:
                        exact = parsed
                        break
                    rows.append(parsed)
                    if len(rows) >= lim:
                        break
        except OSError:
            pass

    results = ([exact] if exact else rows)[:lim]
    for row in results:
        _cache_put(int(row["dmr_id"]), dict(row))
    return _with_observations({
        "ok": True,
        "database": database_meta(),
        "query": q,
        "results": results,
        "diagnostics": _diagnostics(started, scanned),
    })
