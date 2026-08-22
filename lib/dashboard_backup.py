#!/usr/bin/env python3
"""Locked dashboard routes for settings backup/restore and SSH operations."""
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

        def _serve_backup_js(self):
            parts = []
            for name in ("backup-restore.js", "ssh-key-export.js"):
                path = core.WEB / name
                if not path.is_file():
                    self.send_json({"error": "not found"}, 404)
                    return
                data = path.read_bytes()
                if len(data) > 512 * 1024:
                    self.send_json({"error": "backup UI asset is too large"}, 500)
                    return
                parts.append(data)
            body = b"\n;\n".join(parts)
            self.send_bytes(200, body, "application/javascript; charset=utf-8", cache="no-cache")

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/backup-restore.js":
                self._serve_backup_js()
                return
            if path == "/ssh-key-export.js":
                self.serve_static("ssh-key-export.js", "application/javascript; charset=utf-8")
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
                "/api/ssh/status": "ssh-status",
                "/api/ssh/configure": "ssh-configure",
                "/api/ssh-keys/export": "ssh-keys-export",
                "/api/ssh-client-key/create": "ssh-client-key-create",
            }
            if path not in routes:
                super().do_POST()
                return
            # SSH/runtime and settings migration operations are unreachable until
            # the existing dashboard control session has been authenticated.
            if not self.require_control():
                return
            try:
                body = self._large_json()
                if path == "/api/ssh/configure":
                    timeout = 45
                elif path.startswith("/api/ssh"):
                    timeout = 30
                else:
                    timeout = 150
                out = core.admin_call(routes[path], body, timeout)
                self.send_json(out)
            except ValueError as exc:
                self.send_json({"error": str(exc)[:800]}, 400)
            except Exception as exc:
                self.send_json({"error": str(exc)[:1000]}, 502)

    BackupHandler.__name__ = f"Backup{base.__name__}"
    return BackupHandler
