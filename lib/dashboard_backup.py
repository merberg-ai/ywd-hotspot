#!/usr/bin/env python3
"""Locked dashboard routes for .ywdsettings export/preview/restore."""
from __future__ import annotations

import json
from urllib.parse import urlparse

import dashboard_core as core


def wrap_handler(base):
    class BackupHandler(base):
        def _large_json(self, limit=2050000):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except Exception:
                raise ValueError("invalid Content-Length")
            if length < 0 or length > limit:
                raise ValueError("settings backup request is too large")
            raw = self.rfile.read(length)
            try:
                obj = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                raise ValueError("invalid JSON body")
            if not isinstance(obj, dict):
                raise ValueError("JSON body must be an object")
            return obj

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/backup-restore.js":
                self.serve_static("backup-restore.js", "application/javascript; charset=utf-8")
                return
            if path == "/backup-restore.css":
                self.serve_static("backup-restore.css", "text/css; charset=utf-8")
                return
            super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            routes = {
                "/api/settings/export": "settings-export",
                "/api/settings/preview": "settings-preview",
                "/api/settings/import": "settings-import",
            }
            if path not in routes:
                super().do_POST()
                return
            if not self.require_control():
                return
            try:
                body = self._large_json()
                out = core.admin_call(routes[path], body, 150)
                self.send_json(out)
            except ValueError as exc:
                self.send_json({"error": str(exc)[:800]}, 400)
            except Exception as exc:
                self.send_json({"error": str(exc)[:1000]}, 502)

    BackupHandler.__name__ = f"Backup{base.__name__}"
    return BackupHandler
