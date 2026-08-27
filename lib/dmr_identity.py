#!/usr/bin/env python3
"""Bounded read-only lookup helpers for the local YWD-Hotspot DMR directory."""
from __future__ import annotations

import os
import sqlite3
import time
from collections import OrderedDict
from pathlib import Path

import dmr_observations

DB = Path(os.environ.get("YWD_DMRID_FILE", "/var/lib/ywd-hotspot/DMRIds.dat"))
RICH_DB = Path(os.environ.get("YWD_DMR_CONTACTS_FILE", "/var/lib/ywd-hotspot/DMRContacts.tsv"))
INDEX_DB = Path(os.environ.get("YWD_DMR_CONTACTS_DB", "/var/lib/ywd-hotspot/DMRContacts.sqlite3"))
SOURCE = "RadioID.net"
MAX_BATCH = 64
MAX_SEARCH = 25
CACHE_LIMIT = 512
_CACHE: OrderedDict[int, dict | None] = OrderedDict()
_CACHE_STAMP: tuple[str, int, int] | None = None


def _text_db() -> Path:
    return RICH_DB if RICH_DB.is_file() else DB


def _active_stamp_path() -> Path:
    return INDEX_DB if INDEX_DB.is_file() else _text_db()


def _stamp() -> tuple[str, int, int] | None:
    path = _active_stamp_path()
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


def _diagnostics(started: float, scanned: int, cache_hit: bool = False, indexed: bool = False) -> dict:
    return {
        "elapsed_ms": max(0, int(round((time.monotonic() - started) * 1000))),
        "scanned_records": max(0, int(scanned)),
        "cache_hit": bool(cache_hit),
        "indexed": bool(indexed),
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


def _sqlite_row(values):
    return _row(values[0], values[1], values[2], values[3], values[4], values[5])


def _indexed_lookup(ids):
    placeholders = ",".join("?" for _ in ids)
    with sqlite3.connect(f"file:{INDEX_DB}?mode=ro", uri=True, timeout=1.0) as conn:
        rows = conn.execute(
            f"SELECT dmr_id, callsign, name, city, state, country FROM contacts WHERE dmr_id IN ({placeholders})",
            tuple(ids),
        ).fetchall()
    return {_sqlite_row(values)["dmr_id"]: _sqlite_row(values) for values in rows}


def _indexed_search(q, limit):
    with sqlite3.connect(f"file:{INDEX_DB}?mode=ro", uri=True, timeout=1.0) as conn:
        exact = conn.execute(
            "SELECT dmr_id, callsign, name, city, state, country FROM contacts WHERE callsign=? ORDER BY dmr_id LIMIT 1",
            (q,),
        ).fetchone()
        if exact:
            return [_sqlite_row(exact)]
        rows = conn.execute(
            "SELECT dmr_id, callsign, name, city, state, country FROM contacts "
            "WHERE callsign>=? AND callsign<? ORDER BY callsign, dmr_id LIMIT ?",
            (q, q + "\uffff", int(limit)),
        ).fetchall()
    return [_sqlite_row(values) for values in rows]


def database_meta() -> dict:
    stamp = _sync_cache()
    path = _text_db()
    if stamp is None:
        return {
            "source": SOURCE, "present": False, "updated_at": None, "size_bytes": None,
            "rich_fields": False, "indexed": False,
        }
    indexed = INDEX_DB.is_file()
    try:
        source_path = INDEX_DB if indexed else path
        stat = source_path.stat()
        return {
            "source": SOURCE,
            "present": True,
            "updated_at": float(stat.st_mtime),
            "size_bytes": int(stat.st_size),
            "rich_fields": RICH_DB.is_file(),
            "indexed": indexed,
        }
    except OSError:
        return {
            "source": SOURCE, "present": False, "updated_at": None, "size_bytes": None,
            "rich_fields": False, "indexed": False,
        }


def lookup_ids(values) -> dict:
    """Resolve at most MAX_BATCH DMR IDs, preferring the indexed local directory."""
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
        return _with_observations({
            "ok": True, "database": meta, "results": [],
            "diagnostics": _diagnostics(started, scanned, indexed=meta.get("indexed", False)),
        })

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

    indexed_ok = False
    if pending and INDEX_DB.is_file():
        try:
            indexed_rows = _indexed_lookup(sorted(pending))
            for ident, row in indexed_rows.items():
                found[ident] = row
                _cache_put(ident, row)
                pending.discard(ident)
            # A successful indexed query is authoritative for missing IDs too.
            indexed_ok = True
            for ident in list(pending):
                found[ident] = None
                _cache_put(ident, None)
                pending.discard(ident)
        except (OSError, sqlite3.Error):
            indexed_ok = False

    if pending and meta["present"]:
        try:
            with _text_db().open("r", encoding="utf-8", errors="replace") as handle:
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
        "diagnostics": _diagnostics(
            started, scanned,
            cache_hit=bool(cache_hits and cache_hits == len(ordered)),
            indexed=indexed_ok or bool(meta.get("indexed", False)),
        ),
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
            "diagnostics": _diagnostics(started, 0, cache_hit=True, indexed=meta.get("indexed", False)),
        })

    if INDEX_DB.is_file():
        try:
            results = _indexed_search(q, lim)
            for row in results:
                _cache_put(int(row["dmr_id"]), dict(row))
            return _with_observations({
                "ok": True,
                "database": database_meta(),
                "query": q,
                "results": results,
                "diagnostics": _diagnostics(started, 0, indexed=True),
            })
        except (OSError, sqlite3.Error):
            pass

    rows = []
    exact = None
    if meta["present"]:
        try:
            with _text_db().open("r", encoding="utf-8", errors="replace") as handle:
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
