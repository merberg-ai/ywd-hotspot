#!/usr/bin/env python3
"""YWD-Hotspot dashboard extension wrapper for Talkgroup Manager and UI polish."""
from __future__ import annotations

import json
import threading
import time
from urllib.parse import parse_qs, urlparse

import dashboard_core as core

TG_CACHE = core.VAR / "talkgroup-directory.json"
SETUP_STATE = core.VAR / "setup-state.json"
M4_GATE = core.Path("/etc/ywd-hotspot/m4-safety.txt")
TG_TTL = 24 * 3600
TG_LOCK = threading.Lock()
TG_MEM = {"rows": None, "cached_at": 0.0, "stale": True, "error": None}


def setup_required():
    if not M4_GATE.is_file():
        return False
    try:
        doc = json.loads(SETUP_STATE.read_text())
        return not (isinstance(doc, dict) and doc.get("state") == "complete")
    except Exception:
        return True


def _tg_id(value):
    try:
        n = int(value)
    except Exception:
        return None
    return n if 1 <= n <= 16777215 else None


def _tg_name(obj, fallback=""):
    if isinstance(obj, str):
        return obj.strip()[:120]
    if isinstance(obj, dict):
        for key in ("name", "label", "description", "title"):
            val = obj.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()[:120]
    return str(fallback or "").strip()[:120]


def normalize_talkgroups(payload):
    """Normalize BrandMeister v2 talkgroup directory shapes into id/name rows."""
    rows = {}

    def add(ident, name=""):
        tid = _tg_id(ident)
        if tid is None:
            return
        text = _tg_name(name)
        old = rows.get(tid, "")
        if text or not old:
            rows[tid] = text

    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        nested = None
        for key in ("talkgroups", "groups", "data", "results"):
            if isinstance(payload.get(key), list):
                nested = payload[key]
                break
        if nested is not None:
            items = nested
        else:
            items = None
            for key, value in payload.items():
                if str(key).isdigit():
                    add(key, value)
                elif isinstance(value, dict):
                    ident = value.get("id", value.get("talkgroup", value.get("group", value.get("tg"))))
                    if ident is not None:
                        add(ident, value)
            if rows:
                return [{"id": k, "name": rows[k]} for k in sorted(rows)]
    else:
        items = None

    if items is not None:
        for item in items:
            if isinstance(item, dict):
                ident = item.get("id", item.get("talkgroup", item.get("group", item.get("tg"))))
                add(ident, item)
            elif isinstance(item, (list, tuple)) and item:
                add(item[0], item[1] if len(item) > 1 else "")
    return [{"id": k, "name": rows[k]} for k in sorted(rows)]


def _read_disk_cache():
    try:
        doc = json.loads(TG_CACHE.read_text(encoding="utf-8"))
        rows = doc.get("rows", []) if isinstance(doc, dict) else []
        cached_at = float(doc.get("cached_at", 0)) if isinstance(doc, dict) else 0.0
        clean = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            tid = _tg_id(row.get("id"))
            if tid is not None:
                clean.append({"id": tid, "name": str(row.get("name") or "")[:120]})
        return clean, cached_at
    except Exception:
        return [], 0.0


def _write_disk_cache(rows, cached_at):
    try:
        core.write_var_json(TG_CACHE, {"cached_at": cached_at, "rows": rows})
    except Exception:
        pass


def talkgroup_directory(force=False):
    now = time.time()
    with TG_LOCK:
        mem_rows = TG_MEM.get("rows")
        mem_at = float(TG_MEM.get("cached_at") or 0)
        if mem_rows is not None and not force and now - mem_at < TG_TTL:
            return mem_rows, mem_at, False, TG_MEM.get("error")

        disk_rows, disk_at = _read_disk_cache()
        if disk_rows and not force and now - disk_at < TG_TTL:
            TG_MEM.update(rows=disk_rows, cached_at=disk_at, stale=False, error=None)
            return disk_rows, disk_at, False, None

        try:
            payload = core.brandmeister.talkgroups()
            rows = normalize_talkgroups(payload)
            if not rows:
                raise RuntimeError("BrandMeister returned an empty or unrecognized talkgroup directory")
            cached_at = now
            _write_disk_cache(rows, cached_at)
            TG_MEM.update(rows=rows, cached_at=cached_at, stale=False, error=None)
            return rows, cached_at, False, None
        except Exception as exc:
            fallback = disk_rows or mem_rows or []
            fallback_at = disk_at or mem_at
            if fallback:
                msg = str(exc)[:300]
                TG_MEM.update(rows=fallback, cached_at=fallback_at, stale=True, error=msg)
                return fallback, fallback_at, True, msg
            raise


def search_talkgroups(query="", ids=None, limit=40, force=False):
    rows, cached_at, stale, error = talkgroup_directory(force=force)
    ids = ids or []
    idset = {_tg_id(x) for x in ids}
    idset.discard(None)
    q = " ".join(str(query or "").lower().split())[:80]
    terms = q.split()

    def match(row):
        tid = int(row["id"])
        if idset:
            return tid in idset
        if not terms:
            return False
        hay = f"{tid} {row.get('name', '')}".lower()
        return all(term in hay for term in terms)

    found = [r for r in rows if match(r)]
    if not idset:
        def score(row):
            sid = str(row["id"])
            name = str(row.get("name") or "").lower()
            return (
                0 if sid == q else
                1 if name == q else
                2 if sid.startswith(q) else
                3 if name.startswith(q) else 4,
                len(name), int(row["id"])
            )
        found.sort(key=score)
    else:
        found.sort(key=lambda r: int(r["id"]))
    found = found[:max(1, min(int(limit), 100))]
    return {
        "ok": True,
        "results": found,
        "directory_count": len(rows),
        "cached_at": cached_at,
        "stale": stale,
        "error": error,
    }


class H(core.H):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html") and setup_required():
            self.send_response(302)
            self.send_header("Location", "https://ywd-hotspot.local:8443/")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path == "/app-core.js":
            self.serve_static("app-core.js", "application/javascript; charset=utf-8")
            return
        if path == "/talkgroups.js":
            self.serve_static("talkgroups.js", "application/javascript; charset=utf-8")
            return
        if path == "/ui-polish.js":
            self.serve_static("ui-polish.js", "application/javascript; charset=utf-8")
            return
        if path == "/ui-polish.css":
            self.serve_static("ui-polish.css", "text/css; charset=utf-8")
            return
        if path == "/api/talkgroups/search":
            qs = parse_qs(parsed.query, keep_blank_values=False)
            query = str((qs.get("q") or [""])[0])[:80]
            ids_raw = str((qs.get("ids") or [""])[0])[:1200]
            ids = [x for x in ids_raw.split(",") if x.strip()][:100]
            try:
                limit = int((qs.get("limit") or [40])[0])
            except Exception:
                limit = 40
            force = str((qs.get("refresh") or ["0"])[0]).lower() in {"1", "true", "yes"}
            if force and not core.authenticated(self.headers):
                self.send_json({"error": "Unlock control mode before forcing a BrandMeister directory refresh"}, 401)
                return
            if not query and not ids:
                self.send_json({"error": "Provide q or ids"}, 400)
                return
            try:
                self.send_json(search_talkgroups(query=query, ids=ids, limit=limit, force=force))
            except Exception as exc:
                self.send_json({"error": str(exc)[:500]}, 502)
            return
        super().do_GET()


def main():
    c = core.canonical_cfg()
    w = c.get("web", {})
    bind = w.get("bind", "0.0.0.0")
    port = int(w.get("port", 8080))
    print(f"YWD dashboard {core.VERSION} + Talkgroup Manager listening on {bind}:{port}", flush=True)
    core.ThreadingHTTPServer((bind, port), H).serve_forever()


if __name__ == "__main__":
    main()
