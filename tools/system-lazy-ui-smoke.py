#!/usr/bin/env python3
"""Source-only regression for the recovered Pi Zero dashboard startup path.

The vocoder manager must remain isolated from global dashboard startup. This
smoke performs no HTTP requests, service actions, RF operations, or writes.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app_path = ROOT / "web/app.js"
app = app_path.read_text(encoding="utf-8")
vocoder = (ROOT / "web/vocoder-manager.js").read_text(encoding="utf-8")
modem = (ROOT / "web/modem-ui.js").read_text(encoding="utf-8")
update = (ROOT / "lib/dashboard_update.py").read_text(encoding="utf-8")
core = (ROOT / "lib/dashboard_core.py").read_text(encoding="utf-8")
css = (ROOT / "web/vocoder-manager.css").read_text(encoding="utf-8")


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


# Hardware recovery gate: this is the exact app.js blob from the accepted fast
# pre-vocoder dashboard baseline. Vocoder work may not modify this file.
assert git_blob_sha(app_path) == "6934acc74f4489cdfe2536407de50e73516ed521"
assert "load('/app-core.js'" in app
assert "load('/instrumentation.js?v=alpha12.1'" in app
assert "load('/system-ui.js?v=dashboard1'" in app
assert "load('/ssh-key-export.js?v=rc1-system2'" in app
assert "setTimeout(() => closeStartup(true), 12000)" in app
assert "startupReleaseReady" not in app
assert "startupSystemReady" not in app
assert "startupHeroReady" not in app
assert "legacy-ui-bundle" not in update
assert "_LEGACY_UI_COMPONENTS" not in update
assert "_patch_app_js" not in update
assert "link.rel = 'preload'" not in update
assert "readiness_js =" not in update
assert "body += readiness_js" not in update

# Release-only assets may be tracked, but they must all be requested immediately
# rather than awaited serially. This is the post-recovery behavior that loaded
# acceptably on the reference Pi Zero.
assert "window.__YWD_RELEASE_UI_READY = false" in update
assert "window.__YWD_RELEASE_UI_PROGRESS" in update
assert "window.__YWD_RELEASE_UI_READY = progress.failed === 0" in update
assert "sources.forEach(src =>" in update
assert "for (const src of sources)" not in update
assert "await loadReleaseUi" not in update
assert "/update-branch.js?v=rc3-wire1" in update
assert "/modem-ui.js?v=rc3-wire1" in update
assert "/vocoder-manager.js?v=rc4-vocoder-foundation3" in update
assert "/tgif-control.js?v=rc4-tgif1" in update

# System inventory/status stays lazy. The scripts may mount cards after System UI
# exists, but expensive modem/vocoder API work cannot run while Status is active.
assert "function systemVisible()" in vocoder
assert "function activateWhenVisible()" in vocoder
assert "if (!systemVisible()" in vocoder
assert "Status loads when the System page is opened" in vocoder
assert "function systemVisible()" in modem
assert "function activateWhenVisible()" in modem
assert "if (systemVisible() && !loadedOnce) load(false);" in modem
assert "Inventory loads when the System page is opened." in modem

# Job feedback remains local to the System card and retains visible background
# activity without becoming a dashboard-startup dependency.
assert "if (systemVisible()) await loadStatus();" in vocoder
assert "launchPending || jobActive || maintenanceActive ? 1500 : 30000" in vocoder
assert "launchedJobId" in vocoder and "launchPending" in vocoder
assert "launchedTerminal" in vocoder
assert ".vocoder-state.busy::before" in css
assert "ywdVocoderBadgePulse" in css
assert "prefers-reduced-motion:reduce" in css

assert "ThreadingHTTPServer" in core
assert 'cache="no-cache"' in core

print("[OK] exact recovered Pi Zero dashboard startup blob remains frozen")
print("[OK] dependency-ordered legacy loader and bounded 12-second splash fallback remain intact")
print("[OK] preload/bundle/readiness interception experiments remain absent")
print("[OK] RC4 release extensions are tracked without serializing network startup")
print("[OK] MMDVM and vocoder inventory remain lazy off the initial Status page")
print("[OK] vocoder job feedback remains isolated to the System card")
print("[OK] dashboard serving remains threaded with revalidated first-party assets")
