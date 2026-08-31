#!/usr/bin/env python3
"""Software-update and optional UI extension routes for YWD-Hotspot."""
from __future__ import annotations

import json
from urllib.parse import urlparse

import dashboard_backup
import dashboard_core as core
import dashboard_plugin_audio_stream
import dashboard_plugin_upload
import dashboard_plugin_vocoder
import dashboard_plugin_wasm
import dashboard_plugins

STATUS = core.VAR / "update-status.json"
SETUP_STATE = core.VAR / "setup-state.json"
M4_GATE = core.Path("/etc/ywd-hotspot/m4-safety.txt")
PUBLIC_KEYS = {
    "state", "phase", "progress", "message",
    "installed_version", "current_commit", "target_version",
    "target_commit", "target_date", "channel", "available", "up_to_date",
    "validated", "started_at", "completed_at", "updated_at", "backup", "error",
}
_LOADING_THEMES = {
    "rf_sweep", "radar_scan", "packet_burst", "digital_waterfall", "rf_orbit",
    "boot_telemetry", "signal_lock", "vfo_tuning", "dmr_frame",
}
_RELEASE_UI_BOOTSTRAP = b"""
;(() => {
  const loadReleaseUi = src => {
    const script = document.createElement('script');
    script.src = src;
    script.async = false;
    script.onerror = () => console.error(`YWD-Hotspot failed to load ${src}`);
    document.head.appendChild(script);
  };
  loadReleaseUi('/update-branch.js?v=rc3-wire1');
  loadReleaseUi('/modem-ui.js?v=rc3-wire1');
  loadReleaseUi('/tgif-ui.js?v=dev-tgif4');
  loadReleaseUi('/tgif-control.js?v=rc4-tgif1');
  loadReleaseUi('/tgif-polish.js?v=rc4-tgif-polish1');
})();
"""


def setup_required():
    """Mirror the base dashboard's first-run gate before it can emit a stale URL."""
    if not M4_GATE.is_file():
        return False
    try:
        doc = json.loads(SETUP_STATE.read_text(encoding="utf-8"))
        return not (isinstance(doc, dict) and doc.get("state") == "complete")
    except Exception:
        return True


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


def startup_theme():
    """Return the validated presentation-only startup theme for first paint."""
    try:
        value = str(core.canonical_cfg().get("web", {}).get("loading_animation", "digital_waterfall"))
    except Exception:
        value = "digital_waterfall"
    return value if value in _LOADING_THEMES else "digital_waterfall"


def _asset_bytes(name, limit=512 * 1024):
    path = core.WEB / name
    if not path.is_file():
        return b""
    data = path.read_bytes()
    return data if len(data) <= limit else b""


def wrap_handler(base):
    class UpdateHandler(base):
        def do_GET(self):
            path = urlparse(self.path).path

            # The factory/setup portal is intentionally plain HTTP. Intercept the
            # first-run root request here before an older base-handler redirect can
            # point a browser back at the retired self-signed HTTPS listener.
            if path in ("/", "/index.html") and setup_required():
                self.send_response(302)
                self.send_header("Location", "http://ywd-hotspot.local:8443/")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return

            # First-paint startup presentation is bundled into the two assets the
            # base index already requests. This avoids a config round-trip and,
            # more importantly, avoids painting the historical spinner before the
            # selected startup theme is known. Late-RC3/RC4 extension modules are
            # bootstrapped explicitly so an unrelated bundle cannot orphan them.
            if path == "/style.css":
                base_css = _asset_bytes("style.css")
                theme_css = _asset_bytes("startup-themes.css")
                branch_css = _asset_bytes("update-branch.css")
                modem_css = _asset_bytes("modem-ui.css")
                control_css = _asset_bytes("control-theme.css")
                tgif_control_css = _asset_bytes("tgif-control.css")
                tgif_polish_css = _asset_bytes("tgif-polish.css")
                if (
                    not base_css or not branch_css or not modem_css or not control_css
                    or not tgif_control_css or not tgif_polish_css
                ):
                    self.send_json({"error": "style asset unavailable"}, 404)
                    return
                body = base_css
                if theme_css:
                    body += b"\n\n/* startup themes: first-paint bundle */\n" + theme_css
                body += b"\n\n/* software channel UI */\n" + branch_css
                body += b"\n\n/* MMDVM inventory UI */\n" + modem_css
                body += b"\n\n/* dashboard-wide interactive control theme */\n" + control_css
                body += b"\n\n/* TGIF Control Center */\n" + tgif_control_css
                body += b"\n\n/* TGIF Control Center polish */\n" + tgif_polish_css
                self.send_bytes(200, body, "text/css; charset=utf-8", cache="no-cache")
                return
            if path == "/app.js":
                app_js = _asset_bytes("app.js")
                theme_js = _asset_bytes("startup-themes.js")
                if not app_js:
                    self.send_json({"error": "application asset unavailable"}, 404)
                    return
                hint = ("window.__YWD_LOADING_ANIMATION=" + json.dumps(startup_theme()) + ";\n").encode("utf-8")
                body = hint + (theme_js + b"\n;\n" if theme_js else b"") + app_js + _RELEASE_UI_BOOTSTRAP
                # The response contains the current saved presentation preference,
                # so never let a stale cached app.js carry an old theme choice.
                self.send_bytes(200, body, "application/javascript; charset=utf-8", cache="no-store")
                return

            static = {
                "/update.js": ("update.js", "application/javascript; charset=utf-8"),
                "/update-progress.js": ("update-progress.js", "application/javascript; charset=utf-8"),
                "/update-branch.js": ("update-branch.js", "application/javascript; charset=utf-8"),
                "/modem-ui.js": ("modem-ui.js", "application/javascript; charset=utf-8"),
                "/tgif-ui.js": ("tgif-ui.js", "application/javascript; charset=utf-8"),
                "/tgif-control.js": ("tgif-control.js", "application/javascript; charset=utf-8"),
                "/tgif-polish.js": ("tgif-polish.js", "application/javascript; charset=utf-8"),
                "/tgif-control.css": ("tgif-control.css", "text/css; charset=utf-8"),
                "/tgif-polish.css": ("tgif-polish.css", "text/css; charset=utf-8"),
                "/control-theme.css": ("control-theme.css", "text/css; charset=utf-8"),
                "/update.css": ("update.css", "text/css; charset=utf-8"),
                "/update-branch.css": ("update-branch.css", "text/css; charset=utf-8"),
                "/modem-ui.css": ("modem-ui.css", "text/css; charset=utf-8"),
                "/instrumentation.js": ("instrumentation.js", "application/javascript; charset=utf-8"),
                "/instrumentation-bootstrap.js": ("instrumentation-bootstrap.js", "application/javascript; charset=utf-8"),
                "/instrumentation.css": ("instrumentation.css", "text/css; charset=utf-8"),
                "/startup-themes.js": ("startup-themes.js", "application/javascript; charset=utf-8"),
                "/startup-themes.css": ("startup-themes.css", "text/css; charset=utf-8"),
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
            branch_actions = {
                "/api/update/branches": ("update-branches", 120),
                "/api/update/branch/check": ("update-branch-check", 260),
                "/api/update/branch/switch": ("update-branch-switch", 360),
            }
            if path in branch_actions:
                if not self.require_control():
                    return
                try:
                    body = self.body_json()
                    action, timeout = branch_actions[path]
                    out = core.admin_call(action, body, timeout)
                    self.send_json(out)
                except ValueError as exc:
                    self.send_json({"error": str(exc)[:800]}, 400)
                except Exception as exc:
                    self.send_json({"error": str(exc)[:1000]}, 502)
                return

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
    handler = dashboard_plugin_vocoder.wrap_handler(handler)
    handler = dashboard_plugin_audio_stream.wrap_handler(handler)
    handler = dashboard_plugin_wasm.wrap_handler(handler)
    handler = dashboard_plugin_upload.wrap_handler(handler)
    handler = dashboard_backup.wrap_handler(handler)
    return handler
