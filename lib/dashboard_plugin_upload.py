#!/usr/bin/env python3
"""Locked WebUI routes for persistent .ywdplugin upload/removal."""
from __future__ import annotations

import json
from urllib.parse import urlparse

import dashboard_core as core
import dashboard_plugins
import plugin_catalog_overlay

plugin_catalog_overlay.install()
_BASE_SNAPSHOT = dashboard_plugins.current_snapshot


def _decorated_snapshot():
    return plugin_catalog_overlay.decorate_snapshot(_BASE_SNAPSHOT())


# Existing plugin routes use current_snapshot dynamically, so decorate all
# responses without changing the proven lifecycle handlers themselves.
dashboard_plugins.current_snapshot = _decorated_snapshot


def wrap_handler(base):
    class PluginUploadHandler(base):
        def _large_json(self, limit=1600000):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except Exception:
                raise ValueError("invalid Content-Length")
            if length < 0 or length > limit:
                raise ValueError("plugin upload request is too large")
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
            if path == "/plugin-package-upload.js":
                self.serve_static("plugin-package-upload.js", "application/javascript; charset=utf-8")
                return
            if path == "/api/plugins":
                try:
                    self.send_json({"ok": True, **_decorated_snapshot()})
                except Exception as exc:
                    self.send_json({"error": str(exc)[:800]}, 500)
                return
            super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in {"/api/plugins/upload", "/api/plugins/package-remove"}:
                super().do_POST()
                return
            if not self.require_control():
                return
            try:
                body = self._large_json() if path == "/api/plugins/upload" else self.body_json()
                action = "plugin-package-upload" if path == "/api/plugins/upload" else "plugin-package-remove"
                out = core.admin_call(action, body, 90)
                self.send_json({**out, "plugins_state": _decorated_snapshot()})
            except ValueError as exc:
                self.send_json({"error": str(exc)[:800]}, 400)
            except Exception as exc:
                self.send_json({"error": str(exc)[:800]}, 502)

    PluginUploadHandler.__name__ = f"PluginUpload{base.__name__}"
    return PluginUploadHandler
