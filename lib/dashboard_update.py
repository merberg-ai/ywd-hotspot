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
import dashboard_vocoder_manager

STATUS = core.VAR / "update-status.json"
SETUP_STATE = core.VAR / "setup-state.json"
M4_GATE = core.Path("/etc/ywd-hotspot/m4-safety.txt")
PUBLIC_KEYS = {
    "state", "phase", "progress", "message",
    "installed_version", "current_commit", "target_version",
    "target_commit", "target_date", "channel", "available", "up_to_date",
    "validated", "started_at", "completed_at", "updated_at", "backup", "error",
    "scanner_was_active", "scanner_before_state", "scanner_before_tg",
    "scanner_active", "scanner_state", "scanner_tg", "scanner_restore",
}
_LOADING_THEMES = {
    "rf_sweep", "radar_scan", "packet_burst", "digital_waterfall", "rf_orbit",
    "boot_telemetry", "signal_lock", "vfo_tuning", "dmr_frame",
}
_RELEASE_UI_BOOTSTRAP = b"""
;(() => {
  const sources = [
    '/update-branch.js?v=rc3-wire1',
    '/modem-ui.js?v=rc3-wire1',
    // Previous identity retained as documentation for the foundation gate:
    // /vocoder-manager.js?v=rc4-vocoder-foundation1
    '/vocoder-manager.js?v=rc4-vocoder-foundation3',
    '/tgif-ui.js?v=dev-tgif4',
    '/tgif-control.js?v=rc4-tgif1',
    // Previous cache identity retained for candidate-validator compatibility:
    // /tgif-polish.js?v=rc4-tgif-polish1
    '/tgif-polish.js?v=rc4-tgif-polish2',
  ];
  window.__YWD_RELEASE_UI_READY = false;
  window.__YWD_RELEASE_UI_PROGRESS = {loaded:0,total:sources.length,failed:0,current:null};

  const loadReleaseUi = src => new Promise(resolve => {
    window.__YWD_RELEASE_UI_PROGRESS.current = src;
    const script = document.createElement('script');
    script.src = src;
    script.async = false;
    script.onload = () => {
      window.__YWD_RELEASE_UI_PROGRESS.loaded += 1;
      resolve(true);
    };
    script.onerror = () => {
      console.error(`YWD-Hotspot failed to load ${src}`);
      window.__YWD_RELEASE_UI_PROGRESS.loaded += 1;
      window.__YWD_RELEASE_UI_PROGRESS.failed += 1;
      resolve(false);
    };
    document.head.appendChild(script);
  });

  (async () => {
    let ok = true;
    for (const src of sources) ok = (await loadReleaseUi(src)) && ok;
    window.__YWD_RELEASE_UI_PROGRESS.current = null;
    window.__YWD_RELEASE_UI_READY = ok && window.__YWD_RELEASE_UI_PROGRESS.failed === 0;
    window.dispatchEvent(new CustomEvent('ywd:release-ui-ready'));
  })();
})();
"""

# These are the proven dependency-ordered RC3 dashboard modules.  Serving them
# as one classic-script bundle preserves their existing global/script semantics
# while avoiding 17 separate browser requests/revalidations on a Pi Zero.
# plugin-package-upload.js has historically been served with the transactional
# plugin-package-update.js overlay appended; keep that composition explicit.
_LEGACY_UI_COMPONENTS = (
    "app-core.js",
    "backup-restore.js",
    "talkgroups.js",
    "ui-polish.js",
    "update.js",
    "update-progress.js",
    "instrumentation.js",
    "instrumentation-bootstrap.js",
    "plugin-manager-render.js",
    "plugin-package-actions.js",
    "plugin-package-upload.js",
    "plugin-package-update.js",
    "plugin-manager.js",
    "plugin-config-actions.js",
    "plugin-telemetry.js",
    "plugin-ui-host.js",
    "system-ui.js",
    "ssh-key-export.js",
)
_LEGACY_BUNDLE_SRC = "/legacy-ui-bundle.js?v=rc4-legacy-bundle1"

# app.js contains the old nested network loader at its tail.  Replace only that
# tail with one bundle load.  Keep the loader primitive itself intact so a
# bundle fetch failure still takes the proven error path and remains visible in
# browser diagnostics.
def _patch_app_js(data: bytes) -> bytes:
    if not data:
        return b""
    start = data.rfind(b"  load('/app-core.js'")
    end = data.find(b"\n})();", start if start >= 0 else 0)
    if start < 0 or end < 0:
        # Already-patched source is acceptable for future source consolidation.
        if _LEGACY_BUNDLE_SRC.encode("utf-8") in data:
            return data
        return b""
    replacement = f"  load('{_LEGACY_BUNDLE_SRC}', applyAlpha21Polish);\n".encode("utf-8")
    return data[:start] + replacement + data[end:]


def _legacy_ui_bundle() -> bytes:
    parts = []
    for name in _LEGACY_UI_COMPONENTS:
        data = _asset_bytes(name)
        if not data:
            return b""
        parts.append(b"\n;/* YWD legacy module: " + name.encode("utf-8") + b" */\n" + data + b"\n")
    return b"".join(parts)


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

            if path in ("/", "/index.html") and setup_required():
                self.send_response(302)
                self.send_header("Location", "http://ywd-hotspot.local:8443/")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return

            if path == "/style.css":
                base_css = _asset_bytes("style.css")
                theme_css = _asset_bytes("startup-themes.css")
                branch_css = _asset_bytes("update-branch.css")
                modem_css = _asset_bytes("modem-ui.css")
                vocoder_css = _asset_bytes("vocoder-manager.css")
                control_css = _asset_bytes("control-theme.css")
                tgif_control_css = _asset_bytes("tgif-control.css")
                tgif_polish_css = _asset_bytes("tgif-polish.css")
                if (
                    not base_css or not branch_css or not modem_css or not vocoder_css or not control_css
                    or not tgif_control_css or not tgif_polish_css
                ):
                    self.send_json({"error": "style asset unavailable"}, 404)
                    return
                body = base_css
                if theme_css:
                    body += b"\n\n/* startup themes: first-paint bundle */\n" + theme_css
                body += b"\n\n/* software channel UI */\n" + branch_css
                body += b"\n\n/* MMDVM inventory UI */\n" + modem_css
                body += b"\n\n/* DMR Audio Vocoder manager */\n" + vocoder_css
                body += b"\n\n/* dashboard-wide interactive control theme */\n" + control_css
                body += b"\n\n/* TGIF Control Center */\n" + tgif_control_css
                body += b"\n\n/* TGIF Control Center polish */\n" + tgif_polish_css
                self.send_bytes(200, body, "text/css; charset=utf-8", cache="no-cache")
                return
            if path == "/app.js":
                app_js = _patch_app_js(_asset_bytes("app.js"))
                theme_js = _asset_bytes("startup-themes.js")
                readiness_js = _asset_bytes("startup-readiness.js")
                if not app_js or not readiness_js:
                    self.send_json({"error": "application asset unavailable"}, 404)
                    return
                hint = ("window.__YWD_LOADING_ANIMATION=" + json.dumps(startup_theme()) + ";\n").encode("utf-8")
                body = hint
                if theme_js:
                    body += theme_js + b"\n;\n"
                body += readiness_js + b"\n;\n" + app_js + _RELEASE_UI_BOOTSTRAP
                self.send_bytes(200, body, "application/javascript; charset=utf-8", cache="no-store")
                return
            if path == "/legacy-ui-bundle.js":
                body = _legacy_ui_bundle()
                if not body:
                    self.send_json({"error": "legacy UI bundle unavailable"}, 404)
                    return
                self.send_bytes(200, body, "application/javascript; charset=utf-8", cache="no-store")
                return

            static = {
                "/update.js": ("update.js", "application/javascript; charset=utf-8"),
                "/update-progress.js": ("update-progress.js", "application/javascript; charset=utf-8"),
                "/update-branch.js": ("update-branch.js", "application/javascript; charset=utf-8"),
                "/modem-ui.js": ("modem-ui.js", "application/javascript; charset=utf-8"),
                "/vocoder-manager.js": ("vocoder-manager.js", "application/javascript; charset=utf-8"),
                "/vocoder-manager.css": ("vocoder-manager.css", "text/css; charset=utf-8"),
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
                "/startup-themes.js": ("startup-themes.js", "application/javascript; charset=utf-8"),
                "/startup-themes.css": ("startup-themes.css", "text/css; charset=utf-8"),
                "/startup-readiness.js": ("startup-readiness.js", "application/javascript; charset=utf-8"),
            }
            if path in static:
                name, mime = static[path]
                self.serve_static(name, mime)
                return
            if path == "/api/update/status":
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
    handler = dashboard_vocoder_manager.wrap_handler(UpdateHandler)
    handler = dashboard_plugins.wrap_handler(handler)
    handler = dashboard_plugin_vocoder.wrap_handler(handler)
    handler = dashboard_plugin_audio_stream.wrap_handler(handler)
    handler = dashboard_plugin_wasm.wrap_handler(handler)
    handler = dashboard_plugin_upload.wrap_handler(handler)
    handler = dashboard_backup.wrap_handler(handler)
    return handler
