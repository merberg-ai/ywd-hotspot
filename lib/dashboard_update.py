#!/usr/bin/env python3
"""Software-update and optional UI extension routes for YWD-Hotspot."""
from __future__ import annotations

import json
from urllib.parse import urlparse

import dashboard_backup
import dashboard_core as core
import dashboard_plugin_upload
import dashboard_plugins

STATUS = core.VAR / "update-status.json"
PUBLIC_KEYS = {
    "state", "phase", "progress", "message",
    "installed_version", "current_commit", "target_version",
    "target_commit", "target_date", "channel", "available", "up_to_date",
    "validated", "started_at", "completed_at", "updated_at", "backup", "error",
}


def public_status():
    try:
        doc = json.loads(STATUS.read_text())
    except Exception:
        doc = {"state": "idle", "phase": "idle", "progress": 0}
    if not isinstance(doc, dict):
        doc = {"state": "idle", "phase": "idle", "progress": 0}
    out = {k: doc.get(k) for k in PUBLIC_KEYS if k in doc}
    out.setdefault("state", "idle")
    out.setdefault("phase", "idle")
    out.setdefault("progress", 0)
    try:
        out["progress"] = max(0, min(100, int(out.get("progress") or 0)))
    except Exception:
        out["progress"] = 0
    if out.get("message"):
        out["message"] = str(out["message"])[:300]
    if out.get("error"):
        out["error"] = str(out["error"])[-1200:]
    return out


def wrap_handler(base):
    class UpdateHandler(base):
        def do_GET(self):
            path = urlparse(self.path).path
            static = {
                "/update.js": ("update.js", "application/javascript; charset=utf-8"),
                "/update-progress.js": ("update-progress.js", "application/javascript; charset=utf-8"),
                "/update.css": ("update.css", "text/css; charset=utf-8"),
                "/instrumentation.js": ("instrumentation.js", "application/javascript; charset=utf-8"),
                "/instrumentation-bootstrap.js": ("instrumentation-bootstrap.js", "application/javascript; charset=utf-8"),
                "/instrumentation.css": ("instrumentation.css", "text/css; charset=utf-8"),
            }
            if path in static:
                name, mime = static[path]
                self.serve_static(name, mime)
                return
            if path == "/api/update/status":
                # Deliberately public and sanitized: a successful update restarts
                # the dashboard, which destroys the in-memory control session.
                # The browser still needs to report completion/reconnect state.
                self.send_json({"ok": True, "update": public_status()})
                return
            super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in {"/api/update/check", "/api/update/start"}:
                super().do_POST()
                return
            if not self.require_control():
                return
            try:
                if path == "/api/update/check":
                    out = core.admin_call("update-check", {}, 220)
                else:
                    out = core.admin_call("update-start", {}, 240)
                self.send_json(out)
            except Exception as exc:
                self.send_json({"error": str(exc)[:800]}, 502)

    UpdateHandler.__name__ = f"Update{base.__name__}"
    handler = dashboard_plugins.wrap_handler(UpdateHandler)
    handler = dashboard_plugin_upload.wrap_handler(handler)
    handler = dashboard_backup.wrap_handler(handler)
    return handler
