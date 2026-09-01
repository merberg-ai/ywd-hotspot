#!/usr/bin/env python3
"""Dashboard bridge for RC4 DMR Audio Vocoder status/background jobs."""
from __future__ import annotations

import threading
import time
from urllib.parse import urlparse

import dashboard_core as core
import vocoder_manager
import vocoder_prepared

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


def _apply_managed_integrity(doc: dict) -> dict:
    if not isinstance(doc, dict) or not bool(doc.get("managed")):
        return doc
    backend = doc.get("backend") if isinstance(doc.get("backend"), dict) else {}
    installed = doc.get("installed_provenance") if isinstance(doc.get("installed_provenance"), dict) else {}
    actual = str(backend.get("binary_sha256") or "").lower()
    expected = str(installed.get("binary_sha256") or "").lower()
    if expected and actual != expected:
        doc["state"] = {
            "state": "REPAIR_REQUIRED",
            "reason": "The managed vocoder binary no longer matches its recorded installed SHA-256.",
            "recommended_action": "REPAIR / REINSTALL",
        }
        doc["integrity"] = {"ok": False, "reason": "managed-binary-sha-mismatch"}
    else:
        doc["integrity"] = {"ok": bool(expected and actual == expected), "reason": "managed-binary-sha-match" if expected else "managed-sha-unrecorded"}
    return doc


def cached_status(force: bool = False) -> dict:
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE["doc"]
        if not force and cached is not None and now - float(_CACHE["at"] or 0) < _cache_ttl(cached):
            return cached
        doc = _apply_managed_integrity(vocoder_manager.status())
        doc["prepared"] = vocoder_prepared.status()
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
            actions = {
                "/api/system/vocoder/preflight": ("vocoder-preflight-start", False),
                "/api/system/vocoder/prepare": ("vocoder-prepare-start", False),
                "/api/system/vocoder/activate": ("vocoder-activate-start", False),
                "/api/system/vocoder/cancel": ("vocoder-job-cancel", True),
            }
            if path not in actions:
                super().do_POST()
                return
            if not self.require_control():
                return
            try:
                body = self.body_json()
                action, wants_job_id = actions[path]
                if wants_job_id:
                    if not isinstance(body, dict) or set(body) != {"job_id"} or not str(body.get("job_id") or "").strip():
                        raise ValueError("vocoder cancellation requires only job_id")
                    payload = {"job_id": str(body["job_id"])[:96]}
                else:
                    if body:
                        raise ValueError("vocoder background action accepts no options")
                    payload = {}
                out = core.admin_call(action, payload, 20)
                invalidate_status()
                self.send_json(out)
            except ValueError as exc:
                self.send_json({"ok": False, "error": str(exc)[:500]}, 400)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)[:800]}, 502)

    VocoderManagerHandler.__name__ = f"VocoderManager{base.__name__}"
    return VocoderManagerHandler
