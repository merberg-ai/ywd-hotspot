#!/usr/bin/env python3
"""Read-only dashboard bridge for the RC4 DMR Audio Vocoder manager foundation."""
from __future__ import annotations

import threading
import time
from urllib.parse import urlparse

import vocoder_manager

_CACHE_LOCK = threading.Lock()
_CACHE = {"at": 0.0, "doc": None}
_CACHE_TTL = 8.0


def cached_status(force: bool = False) -> dict:
    now = time.monotonic()
    with _CACHE_LOCK:
        if not force and _CACHE["doc"] is not None and now - float(_CACHE["at"] or 0) < _CACHE_TTL:
            return _CACHE["doc"]
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

    VocoderManagerHandler.__name__ = f"VocoderManager{base.__name__}"
    return VocoderManagerHandler
