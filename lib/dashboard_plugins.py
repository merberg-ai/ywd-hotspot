#!/usr/bin/env python3
"""Trusted WebUI routes for the YWD-Hotspot Plugin Manager."""
from __future__ import annotations

import html
import time
from urllib.parse import parse_qs, quote, urlparse

import dashboard_core as core
import mmdvm_telemetry
import mmdvm_voice
import plugin_manager
import plugin_package_manager
import plugin_service_manager
import plugin_ui_manager

# These were framework proof fixtures during Alpha13-16. They remain bundled for
# updater compatibility, but are retired from the operator-facing catalog.
RETIRED_REFERENCE_IDS = frozenset({"system-info", "service-heartbeat"})
_RETIRE_RETRY_AT = 0.0


def _retire_reference_packages():
    """Best-effort one-time migration of the old proof plugins to uninstalled."""
    global _RETIRE_RETRY_AT
    now = time.monotonic()
    if now < _RETIRE_RETRY_AT:
        return
    _RETIRE_RETRY_AT = now + 10.0
    for ident in sorted(RETIRED_REFERENCE_IDS):
        try:
            installed = plugin_package_manager.is_installed(ident)
        except Exception:
            continue
        if not installed:
            continue
        try:
            core.admin_call("plugin-package-uninstall", {"id": ident}, 30)
        except Exception:
            pass


def current_snapshot():
    _retire_reference_packages()
    base = plugin_manager.snapshot(core.brief_health())
    service_rows = plugin_service_manager.snapshot()
    ui_rows = plugin_ui_manager.snapshot()
    plugins = [
        p for p in list(base.get("plugins", [])) + service_rows + ui_rows
        if str(p.get("id") or "") not in RETIRED_REFERENCE_IDS
    ]
    system = dict(base.get("system", {}))
    enabled = bool(system.get("enabled", False))
    package_state_error = system.get("package_state_error")
    system.update({
        "available": len(plugins),
        "installed": sum(1 for p in plugins if p.get("installed")),
        "enabled_plugins": sum(1 for p in plugins if p.get("enabled")),
        "active_plugins": sum(1 for p in plugins if p.get("health") == "active"),
        "health": "disabled" if not enabled else (
            "error" if package_state_error or any(p.get("health") == "error" for p in plugins) else "good"
        ),
        "execution_model": "package lifecycle + declarative + sandboxed services + sandboxed browser UI",
        "service_api": plugin_service_manager.API_VERSION,
        "ui_api": plugin_ui_manager.API_VERSION,
    })
    return {"api": base.get("api", 1), "system": system, "plugins": plugins}


def test_plugin(ident):
    try:
        plugin_manager.get_plugin(ident)
        return plugin_manager.test_plugin(ident, core.brief_health(force=True))
    except plugin_manager.PluginError:
        pass
    try:
        plugin_service_manager.get_plugin(ident)
        return plugin_service_manager.test_plugin(ident)
    except plugin_manager.PluginError:
        return plugin_ui_manager.test_plugin(ident)


def available_plugin(ident):
    try:
        return plugin_manager.get_available_plugin(ident)
    except plugin_manager.PluginError as declarative_error:
        try:
            return plugin_service_manager.get_available_plugin(ident)
        except plugin_manager.PluginError:
            try:
                return plugin_ui_manager.get_available_plugin(ident)
            except plugin_manager.PluginError:
                raise declarative_error


def check_plugin(ident, kind="all"):
    if kind not in {"all", "dependencies", "hardware"}:
        raise ValueError("check kind must be dependencies, hardware, or all")
    plugin = available_plugin(ident)
    checks = plugin_package_manager.check_requirements(plugin)
    result = {
        "ok": checks["ok"] if kind == "all" else checks[kind]["ok"],
        "id": plugin["id"],
        "name": plugin["name"],
        "kind": kind,
    }
    result["requirements" if kind == "all" else kind] = checks if kind == "all" else checks[kind]
    return result


def telemetry_for(ident):
    plugin = plugin_service_manager.get_plugin(ident)
    if plugin.get("provider") != "mmdvm-telemetry":
        raise ValueError("plugin does not provide MMDVM telemetry")
    state = plugin_manager.read_state()
    if not state.get("enabled") or not bool((state.get("plugins", {}).get(ident) or {}).get("enabled", False)):
        raise ValueError("telemetry plugin is disabled")
    try:
        config = plugin_service_manager.normalize_config(plugin)
    except Exception:
        config = plugin_service_manager.normalize_config(plugin, {})
    return mmdvm_telemetry.public_snapshot(config.get("stale_after_s", 8))


def voice_for(ident, after=0, limit=32):
    plugin = plugin_ui_manager.get_effective_plugin(ident)
    if "read:dmr-voice" not in set(plugin.get("capabilities") or []):
        raise ValueError("plugin is not permitted to read DMR voice frames")
    return mmdvm_voice.public_poll(after, limit)


def plugin_frame_html(plugin):
    ident = plugin["id"]
    ui = plugin["ui"]
    script = quote(ui["script"], safe="")
    style = quote(ui["style"], safe="")
    safe_id = html.escape(ident, quote=True)
    safe_name = html.escape(plugin["name"], quote=True)
    base = f"/api/plugins/ui/{quote(ident, safe='')}/asset"
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">"
        f"<title>{safe_name}</title><link rel=\"stylesheet\" href=\"{base}/{style}\"></head>"
        f"<body data-plugin-id=\"{safe_id}\"><div id=\"ywd-plugin-root\"></div>"
        "<script src=\"/plugin-ui-runtime.js\"></script>"
        f"<script src=\"{base}/{script}\"></script></body></html>"
    ).encode("utf-8")


def wrap_handler(base):
    class PluginHandler(base):
        def send_plugin_ui_bytes(self, status, data, ctype, cache="no-store"):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            # Deliberately omit Cross-Origin-Resource-Policy: same-origin here.
            # The iframe omits allow-same-origin and therefore has an opaque
            # origin; CORP same-origin would block its own signed JS/CSS assets.
            self.send_header(
                "Permissions-Policy",
                "camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=()",
            )
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'none'; "
                "img-src 'self' data:; media-src 'none'; font-src 'none'; object-src 'none'; "
                "frame-src 'none'; child-src 'none'; form-action 'none'; base-uri 'none'; frame-ancestors 'self'",
            )
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            static = {
                "/plugin-manager-render.js": ("plugin-manager-render.js", "application/javascript; charset=utf-8"),
                "/plugin-package-actions.js": ("plugin-package-actions.js", "application/javascript; charset=utf-8"),
                "/plugin-telemetry.js": ("plugin-telemetry.js", "application/javascript; charset=utf-8"),
                "/plugin-manager.js": ("plugin-manager.js", "application/javascript; charset=utf-8"),
                "/plugin-config-actions.js": ("plugin-config-actions.js", "application/javascript; charset=utf-8"),
                "/plugin-manager.css": ("plugin-manager.css", "text/css; charset=utf-8"),
                "/plugin-ui-runtime.js": ("plugin-ui-runtime.js", "application/javascript; charset=utf-8"),
                "/plugin-ui-host.js": ("plugin-ui-host.js", "application/javascript; charset=utf-8"),
                "/plugin-ui.css": ("plugin-ui.css", "text/css; charset=utf-8"),
            }
            if path in static:
                name, mime = static[path]
                self.serve_static(name, mime)
                return

            parts = path.strip("/").split("/")
            if len(parts) >= 5 and parts[:3] == ["api", "plugins", "ui"]:
                ident = parts[3]
                try:
                    if len(parts) == 5 and parts[4] == "frame":
                        plugin = plugin_ui_manager.get_effective_plugin(ident)
                        self.send_plugin_ui_bytes(200, plugin_frame_html(plugin), "text/html; charset=utf-8")
                        return
                    if len(parts) == 5 and parts[4] == "dmr-voice":
                        # Raw DMR voice-frame access is intentionally stronger
                        # than ordinary status/UI access. Require the dashboard
                        # control session as well as the signed plugin capability.
                        if not self.require_control():
                            return
                        qs = parse_qs(parsed.query, keep_blank_values=False)
                        after = str((qs.get("after") or ["0"])[0])[:32]
                        limit = str((qs.get("limit") or ["32"])[0])[:8]
                        self.send_json({"ok": True, "id": ident, "voice": voice_for(ident, after, limit)})
                        return
                    if len(parts) == 6 and parts[4] == "asset":
                        plugin, asset = plugin_ui_manager.asset_path(ident, parts[5])
                        if parts[5] == plugin["ui"]["script"]:
                            mime = "application/javascript; charset=utf-8"
                        elif parts[5] == plugin["ui"]["style"]:
                            mime = "text/css; charset=utf-8"
                        else:
                            raise ValueError("undeclared UI asset")
                        self.send_plugin_ui_bytes(200, asset.read_bytes(), mime, cache="no-cache")
                        return
                except ValueError as exc:
                    self.send_json({"error": str(exc)[:800]}, 409)
                    return
                except Exception as exc:
                    self.send_json({"error": str(exc)[:800]}, 500)
                    return

            if path == "/api/plugins":
                try:
                    self.send_json({"ok": True, **current_snapshot()})
                except Exception as exc:
                    self.send_json({"error": str(exc)[:800]}, 500)
                return
            if path == "/api/plugins/telemetry":
                qs = parse_qs(parsed.query, keep_blank_values=False)
                ident = str((qs.get("id") or [""])[0])[:80]
                try:
                    self.send_json({"ok": True, "id": ident, "telemetry": telemetry_for(ident)})
                except ValueError as exc:
                    self.send_json({"error": str(exc)[:800]}, 409)
                except Exception as exc:
                    self.send_json({"error": str(exc)[:800]}, 502)
                return
            if path == "/api/plugins/logs":
                if not self.require_control():
                    return
                qs = parse_qs(parsed.query, keep_blank_values=False)
                ident = str((qs.get("id") or [""])[0])[:80]
                try:
                    plugin = plugin_service_manager.get_plugin(ident)
                    self.send_json({
                        "ok": True,
                        "id": ident,
                        "service": plugin["service"],
                        "lines": core.journal(plugin["service"], 120),
                    })
                except ValueError as exc:
                    self.send_json({"error": str(exc)[:800]}, 400)
                except Exception as exc:
                    self.send_json({"error": str(exc)[:800]}, 502)
                return
            super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            routes = {
                "/api/plugins/system": "plugin-system-set",
                "/api/plugins/enable": "plugin-set",
                "/api/plugins/config": "plugin-config-save",
                "/api/plugins/runtime": "plugin-runtime",
                "/api/plugins/install": "plugin-package-install",
                "/api/plugins/uninstall": "plugin-package-uninstall",
                "/api/plugins/data-remove": "plugin-data-remove",
            }
            local_routes = {"/api/plugins/test", "/api/plugins/check"}
            if path not in set(routes) | local_routes:
                super().do_POST()
                return
            if not self.require_control():
                return
            try:
                body = self.body_json()
                if path == "/api/plugins/test":
                    out = test_plugin(body.get("id"))
                elif path == "/api/plugins/check":
                    out = check_plugin(body.get("id"), str(body.get("kind") or "all"))
                else:
                    out = core.admin_call(routes[path], body, 40)
                self.send_json({**out, "plugins_state": current_snapshot()})
            except ValueError as exc:
                self.send_json({"error": str(exc)[:800]}, 400)
            except Exception as exc:
                self.send_json({"error": str(exc)[:800]}, 502)

    PluginHandler.__name__ = f"Plugin{base.__name__}"
    return PluginHandler
