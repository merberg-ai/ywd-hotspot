#!/usr/bin/env python3
"""Trusted WebUI routes for the YWD-Hotspot Plugin Manager."""
from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

import dashboard_core as core
import mmdvm_telemetry
import plugin_manager
import plugin_package_manager
import plugin_service_manager

# These were framework proof fixtures during Alpha13-16. They remain bundled for
# updater compatibility, but are retired from the operator-facing catalog.
RETIRED_REFERENCE_IDS = frozenset({"system-info", "service-heartbeat"})
_RETIRE_RETRY_AT = 0.0


def _retire_reference_packages():
    """Best-effort one-time migration of the old proof plugins to uninstalled.

    The update lock can still be held while the dashboard process is restarting,
    so this is retried (at most once per 10 seconds) from Plugin Manager reads
    until the old packages are actually uninstalled. Config/data are preserved by
    the normal package lifecycle; the heartbeat service is stopped/boot-disabled.
    """
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
            # Fail soft during an in-progress update/older dispatcher. The next
            # Plugin Manager refresh retries after the throttle window.
            pass


def current_snapshot():
    _retire_reference_packages()
    base = plugin_manager.snapshot(core.brief_health())
    service_rows = plugin_service_manager.snapshot()
    plugins = [
        p for p in list(base.get("plugins", [])) + service_rows
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
        "health": "disabled" if not enabled else ("error" if package_state_error or any(p.get("health") == "error" for p in plugins) else "good"),
        "execution_model": "package lifecycle + declarative + sandboxed services",
        "service_api": plugin_service_manager.API_VERSION,
    })
    return {"api": base.get("api", 1), "system": system, "plugins": plugins}


def test_plugin(ident):
    try: plugin_manager.get_plugin(ident)
    except plugin_manager.PluginError: return plugin_service_manager.test_plugin(ident)
    return plugin_manager.test_plugin(ident, core.brief_health(force=True))


def available_plugin(ident):
    try: return plugin_manager.get_available_plugin(ident)
    except plugin_manager.PluginError as declarative_error:
        try: return plugin_service_manager.get_available_plugin(ident)
        except plugin_manager.PluginError: raise declarative_error


def check_plugin(ident, kind="all"):
    if kind not in {"all", "dependencies", "hardware"}: raise ValueError("check kind must be dependencies, hardware, or all")
    plugin = available_plugin(ident); checks = plugin_package_manager.check_requirements(plugin)
    result = {"ok":checks["ok"] if kind == "all" else checks[kind]["ok"],"id":plugin["id"],"name":plugin["name"],"kind":kind}
    result["requirements" if kind == "all" else kind] = checks if kind == "all" else checks[kind]
    return result


def telemetry_for(ident):
    plugin = plugin_service_manager.get_plugin(ident)
    if plugin.get("provider") != "mmdvm-telemetry": raise ValueError("plugin does not provide MMDVM telemetry")
    state = plugin_manager.read_state()
    if not state.get("enabled") or not bool((state.get("plugins", {}).get(ident) or {}).get("enabled", False)):
        raise ValueError("telemetry plugin is disabled")
    try: config = plugin_service_manager.normalize_config(plugin)
    except Exception: config = plugin_service_manager.normalize_config(plugin, {})
    return mmdvm_telemetry.public_snapshot(config.get("stale_after_s", 8))


def wrap_handler(base):
    class PluginHandler(base):
        def do_GET(self):
            parsed = urlparse(self.path); path = parsed.path
            static = {
                "/plugin-manager-render.js": ("plugin-manager-render.js", "application/javascript; charset=utf-8"),
                "/plugin-package-actions.js": ("plugin-package-actions.js", "application/javascript; charset=utf-8"),
                "/plugin-telemetry.js": ("plugin-telemetry.js", "application/javascript; charset=utf-8"),
                "/plugin-manager.js": ("plugin-manager.js", "application/javascript; charset=utf-8"),
                "/plugin-config-actions.js": ("plugin-config-actions.js", "application/javascript; charset=utf-8"),
                "/plugin-manager.css": ("plugin-manager.css", "text/css; charset=utf-8"),
            }
            if path in static:
                name, mime = static[path]; self.serve_static(name, mime); return
            if path == "/api/plugins":
                try: self.send_json({"ok": True, **current_snapshot()})
                except Exception as exc: self.send_json({"error": str(exc)[:800]}, 500)
                return
            if path == "/api/plugins/telemetry":
                qs = parse_qs(parsed.query, keep_blank_values=False); ident = str((qs.get("id") or [""])[0])[:80]
                try: self.send_json({"ok":True,"id":ident,"telemetry":telemetry_for(ident)})
                except ValueError as exc: self.send_json({"error":str(exc)[:800]}, 409)
                except Exception as exc: self.send_json({"error":str(exc)[:800]}, 502)
                return
            if path == "/api/plugins/logs":
                if not self.require_control(): return
                qs = parse_qs(parsed.query, keep_blank_values=False); ident = str((qs.get("id") or [""])[0])[:80]
                try:
                    plugin = plugin_service_manager.get_plugin(ident)
                    self.send_json({"ok":True,"id":ident,"service":plugin["service"],"lines":core.journal(plugin["service"],120)})
                except ValueError as exc: self.send_json({"error":str(exc)[:800]},400)
                except Exception as exc: self.send_json({"error":str(exc)[:800]},502)
                return
            super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            routes = {"/api/plugins/system":"plugin-system-set","/api/plugins/enable":"plugin-set","/api/plugins/config":"plugin-config-save","/api/plugins/runtime":"plugin-runtime","/api/plugins/install":"plugin-package-install","/api/plugins/uninstall":"plugin-package-uninstall","/api/plugins/data-remove":"plugin-data-remove"}
            local_routes = {"/api/plugins/test", "/api/plugins/check"}
            if path not in set(routes) | local_routes: super().do_POST(); return
            if not self.require_control(): return
            try:
                body = self.body_json()
                if path == "/api/plugins/test": out = test_plugin(body.get("id"))
                elif path == "/api/plugins/check": out = check_plugin(body.get("id"), str(body.get("kind") or "all"))
                else: out = core.admin_call(routes[path], body, 40)
                self.send_json({**out, "plugins_state": current_snapshot()})
            except ValueError as exc: self.send_json({"error":str(exc)[:800]},400)
            except Exception as exc: self.send_json({"error":str(exc)[:800]},502)

    PluginHandler.__name__ = f"Plugin{base.__name__}"
    return PluginHandler
