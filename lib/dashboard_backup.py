#!/usr/bin/env python3
"""Locked dashboard routes for settings backup/restore, diagnostics, SSH, modem inventory, and software channels."""
from __future__ import annotations

import json
from urllib.parse import urlparse

import dashboard_core as core
import dashboard_tgif

dashboard_tgif.install(core)


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
            path = core.WEB / "backup-restore.js"
            if not path.is_file():
                self.send_json({"error": "not found"}, 404)
                return
            data = path.read_bytes()
            if len(data) > 512 * 1024:
                self.send_json({"error": "backup UI asset is too large"}, 500)
                return
            self.send_bytes(200, data, "application/javascript; charset=utf-8", cache="no-cache")

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/backup-restore.js":
                self._serve_backup_js(); return
            if path == "/ssh-key-export.js":
                self.serve_static("ssh-key-export.js", "application/javascript; charset=utf-8"); return
            if path == "/modem-ui.js":
                self.serve_static("modem-ui.js", "application/javascript; charset=utf-8"); return
            if path == "/update-branch.js":
                self.serve_static("update-branch.js", "application/javascript; charset=utf-8"); return
            if path == "/backup-restore.css":
                self.serve_static("backup-restore.css", "text/css; charset=utf-8"); return
            if path == "/instrumentation-layout.css":
                self.serve_static("instrumentation-layout.css", "text/css; charset=utf-8"); return
            if path == "/api/system/modem":
                try:
                    self.send_json(core.admin_call("mmdvm-system-info", {}, 30))
                except Exception as exc:
                    self.send_json({"error": str(exc)[:1000]}, 502)
                return
            super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            routes = {
                "/api/settings/export": ("settings-export", 150),
                "/api/settings/preview": ("settings-preview", 150),
                "/api/settings/import": ("settings-import", 150),
                "/api/ssh/status": ("ssh-status", 30),
                "/api/ssh/configure": ("ssh-configure", 45),
                "/api/ssh/password": ("ssh-password-set", 30),
                "/api/ssh-keys/export": ("ssh-keys-export", 30),
                "/api/ssh-client-key/create": ("ssh-client-key-create", 30),
                "/api/tgif/configure": ("tgif-configure", 60),
                "/api/tgif/password": ("set-tgif-password", 60),
                "/api/diagnostics/create": ("diagnostics", 150),
                "/api/update/branches": ("update-branches", 120),
                "/api/update/branch/check": ("update-branch-check", 260),
                "/api/update/branch/switch": ("update-branch-switch", 360),
            }
            route = routes.get(path)
            if route is None:
                super().do_POST(); return
            if not self.require_control():
                return
            try:
                body = self._large_json()
                action, timeout = route
                self.send_json(core.admin_call(action, body, timeout))
            except ValueError as exc:
                self.send_json({"error": str(exc)[:800]}, 400)
            except Exception as exc:
                self.send_json({"error": str(exc)[:1000]}, 502)

    BackupHandler.__name__ = f"Backup{base.__name__}"
    return BackupHandler
