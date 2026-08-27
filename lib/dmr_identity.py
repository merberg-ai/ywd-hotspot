#!/usr/bin/env python3
"""Bounded read-only lookup helpers for the local YWD-Hotspot DMR ID database."""
from __future__ import annotations

import os
from collections import OrderedDict
from pathlib import Path

DB = Path(os.environ.get("YWD_DMRID_FILE", "/var/lib/ywd-hotspot/DMRIds.dat"))
SOURCE = "RadioID.net"
MAX_BATCH = 64
MAX_SEARCH = 25
CACHE_LIMIT = 512
_CACHE: OrderedDict[int, str | None] = OrderedDict()
_CACHE_STAMP: tuple[int, int] | None = None


def _stamp() -> tuple[int, int] | None:
    try:
        stat = DB.stat()
        return int(stat.st_mtime_ns), int(stat.st_size)
    except OSError:
        return None


def _sync_cache() -> tuple[int, int] | None:
    global _CACHE_STAMP
    stamp = _stamp()
    if stamp != _CACHE_STAMP:
        _CACHE.clear()
        _CACHE_STAMP = stamp
    return stamp


def _cache_put(ident: int, callsign: str | None) -> None:
    _CACHE[ident] = callsign
    _CACHE.move_to_end(ident)
    while len(_CACHE) > CACHE_LIMIT:
        _CACHE.popitem(last=False)


def _dmr_id(value) -> int | None:
    try:
        ident = int(str(value).strip())
    except Exception:
        return None
    return ident if 1 <= ident <= 16_777_215 else None


def database_meta() -> dict:
    stamp = _sync_cache()
    if stamp is None:
        return {"source": SOURCE, "present": False, "updated_at": None, "size_bytes": None}
    try:
        stat = DB.stat()
        return {
            "source": SOURCE,
            "present": True,
            "updated_at": float(stat.st_mtime),
            "size_bytes": int(stat.st_size),
        }
    except OSError:
        return {"source": SOURCE, "present": False, "updated_at": None, "size_bytes": None}


def lookup_ids(values) -> dict:
    """Resolve at most MAX_BATCH DMR IDs with one bounded sequential file scan."""
    ordered: list[int] = []
    seen = set()
    for value in list(values or [])[:MAX_BATCH]:
        ident = _dmr_id(value)
        if ident is not None and ident not in seen:
            seen.add(ident)
            ordered.append(ident)

    meta = database_meta()
    if not ordered:
        return {"ok": True, "database": meta, "results": []}

    pending = set()
    found: dict[int, str | None] = {}
    for ident in ordered:
        if ident in _CACHE:
            found[ident] = _CACHE[ident]
            _CACHE.move_to_end(ident)
        else:
            pending.add(ident)

    if pending and meta["present"]:
        try:
            with DB.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not pending:
                        break
                    rid, sep, call = line.partition("\t")
                    if not sep or not rid.isdigit():
                        continue
                    ident = int(rid)
                    if ident not in pending:
                        continue
                    callsign = call.strip().upper()[:24] or None
                    found[ident] = callsign
                    _cache_put(ident, callsign)
                    pending.discard(ident)
        except OSError:
            pass

    for ident in pending:
        found[ident] = None
        _cache_put(ident, None)

    return {
        "ok": True,
        "database": database_meta(),
        "results": [
            {"dmr_id": ident, "callsign": found.get(ident), "found": bool(found.get(ident))}
            for ident in ordered
        ],
    }


def search(query, limit=15) -> dict:
    """Search by exact/prefix callsign or DMR ID. Intended for user-triggered lookup."""
    q = " ".join(str(query or "").upper().split())[:32]
    try:
        lim = max(1, min(MAX_SEARCH, int(limit)))
    except Exception:
        lim = 15
    if not q:
        raise ValueError("Enter a callsign or DMR ID")
    if q.isdigit():
        return lookup_ids([q])
    if len(q) < 2 or any(not (ch.isalnum() or ch in {"/", "-"}) for ch in q):
        raise ValueError("Enter at least 2 callsign characters")

    meta = database_meta()
    rows = []
    exact = []
    if meta["present"]:
        try:
            with DB.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    rid, sep, call = line.partition("\t")
                    if not sep or not rid.isdigit():
                        continue
                    callsign = call.strip().upper()[:24]
                    if not callsign or not callsign.startswith(q):
                        continue
                    row = {"dmr_id": int(rid), "callsign": callsign, "found": True}
                    if callsign == q:
                        exact.append(row)
                    elif len(rows) < lim:
                        rows.append(row)
        except OSError:
            pass
    results = (exact + rows)[:lim]
    for row in results:
        _cache_put(int(row["dmr_id"]), str(row["callsign"]))
    return {"ok": True, "database": database_meta(), "query": q, "results": results}
