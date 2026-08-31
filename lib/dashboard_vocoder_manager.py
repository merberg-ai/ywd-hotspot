#!/usr/bin/env python3
"""Dashboard bridge for RC4 DMR Audio Vocoder status/readiness jobs."""
from __future__ import annotations

import threading
import time
from urllib.parse import urlparse

import dashboard_core as core
import vocoder_manager

_CACHE_LOCK = threading.Lock()
_CACHE = {"at": 0.0, "doc": None}
_IDLE_CACHE_TTL = 6.0
_ACTIVE_CACHE_TTL = 0.75


def invalidate_status() -> None:
    with _CACHE_LOCK:
        _CACHE.update(at=0.0, doc=None)


def _cache_ttl(doc: dict | None) -> float:
    if not isinstance(doc, dict):
        return _IDLE_CACHE_TTL
    job = doc.get("job") if isinstance(doc.get("job"), dict) else {}
    maintenance = doc.get("maintenance") if isinstance(doc.get("maintenance"), dict) else {}
    return _ACTIVE_CACHE_TTL if job.get("active") or maintenance.get("active") else _IDLE_CACHE_TTL


def cached_status(force: bool = False) -> dict:
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE["doc"]
        if not force and cached is not None and now - float(_CACHE["at"] or 0) < _cache_ttl(cached):
            return cached
        doc = vocoder_manager.status()
        _CACHE.update(at=now, doc=doc)
        return doc


def wrap_handler(base):
    class VocoderManagerHandler(base):
        def do_GET(self):
            path = urlparse(self.path).path
            if path != "/api/system/vocoder":
                super().do_GET()
                return
            try:
                self.send_json(cached_status())
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)[:800]}, 502)

        def do_POST(self):
            path = urlparse(self.path).path
            if path != "/api/system/vocoder/preflight":
                super().do_POST()
                return
            if not self.require_control():
                return
            try:
                body = self.body_json()
                if body:
                    raise ValueError("vocoder readiness check accepts no options")
                out = core.admin_call("vocoder-preflight-start", {}, 20)
                # Never let an idle cached snapshot hide the launch reservation.
                invalidate_status()
                self.send_json(out)
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)[:500]}, 400)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)[:800]}, 502)

    VocoderManagerHandler.__name__ = f"VocoderManager{base.__name__}"
    return VocoderManagerHandler
