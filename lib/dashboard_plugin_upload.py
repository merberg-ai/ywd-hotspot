#!/usr/bin/env python3
"""Locked WebUI routes for persistent .ywdplugin upload/review/apply/removal."""
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

        def _serve_plugin_package_ui(self):
            """Serve legacy upload UI plus the transactional package overlay."""
            base_path = core.WEB / "plugin-package-upload.js"
            update_path = core.WEB / "plugin-package-update.js"
            try:
                body = base_path.read_bytes()
                if update_path.is_file():
                    body += b"\n\n" + update_path.read_bytes()
            except Exception:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/plugin-package-upload.js":
                self._serve_plugin_package_ui()
                return
            if path == "/ywd-hotspot-banner.webp":
                self.serve_static("ywd-hotspot-banner.webp", "image/webp")
                return
            if path == "/favicon.ico":
                self.serve_asset(core.BRANDING / "ywd-hotspot-badge-256.webp", "image/webp")
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
            actions = {
                "/api/plugins/upload": "plugin-package-upload",
                "/api/plugins/package-review": "plugin-package-review",
                "/api/plugins/package-apply": "plugin-package-apply",
                "/api/plugins/package-remove": "plugin-package-remove",
            }
            action = actions.get(path)
            if action is None:
                super().do_POST()
                return
            if not self.require_control():
                return
            try:
                body = self._large_json() if action in {
                    "plugin-package-upload", "plugin-package-review", "plugin-package-apply"
                } else self.body_json()
                timeout = 120 if action == "plugin-package-apply" else 90
                out = core.admin_call(action, body, timeout)
                self.send_json({**out, "plugins_state": _decorated_snapshot()})
            except ValueError as exc:
                self.send_json({"error": str(exc)[:800]}, 400)
            except Exception as exc:
                self.send_json({"error": str(exc)[:800]}, 502)

    PluginUploadHandler.__name__ = f"PluginUpload{base.__name__}"
    return PluginUploadHandler
