#!/usr/bin/env python3
"""Narrow WebAssembly CSP allowance for passive DMR voice UI plugins.

The ordinary Plugin UI v1 frame remains script-src 'self' only.  A signed,
installed, enabled UI plugin that already holds the trusted read:dmr-voice
capability may additionally compile WebAssembly in its sandboxed browser frame.
This is used for browser-side AMBE decoding; it does not grant network, device,
filesystem, same-origin, form, popup, or Pi-side execution privileges.
"""
from __future__ import annotations

from urllib.parse import urlparse

import dashboard_plugins
import plugin_ui_manager

WASM_CAPABILITY = "read:dmr-voice"


def _frame_path(path):
    parts = str(path or "").strip("/").split("/")
    if len(parts) == 5 and parts[:3] == ["api", "plugins", "ui"] and parts[4] == "frame":
        return parts[3]
    return None


def wrap_handler(base):
    class PluginWasmHandler(base):
        def send_wasm_plugin_frame(self, plugin):
            data = dashboard_plugins.plugin_frame_html(plugin)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Permissions-Policy",
                "camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=()",
            )
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'self'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'none'; "
                "img-src 'self' data:; media-src 'none'; font-src 'none'; object-src 'none'; "
                "frame-src 'none'; child-src 'none'; form-action 'none'; base-uri 'none'; frame-ancestors 'self'",
            )
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            ident = _frame_path(urlparse(self.path).path)
            if not ident:
                super().do_GET()
                return
            try:
                plugin = plugin_ui_manager.get_effective_plugin(ident)
                capabilities = set(plugin.get("capabilities") or [])
                if WASM_CAPABILITY not in capabilities:
                    super().do_GET()
                    return
                self.send_wasm_plugin_frame(plugin)
            except ValueError as exc:
                self.send_json({"error": str(exc)[:800]}, 409)
            except Exception as exc:
                self.send_json({"error": str(exc)[:800]}, 500)

    PluginWasmHandler.__name__ = f"PluginWasm{base.__name__}"
    return PluginWasmHandler
