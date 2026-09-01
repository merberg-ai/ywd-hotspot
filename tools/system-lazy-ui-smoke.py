#!/usr/bin/env python3
"""Source-only regression for Pi Zero dashboard startup/System lazy loading.

This smoke performs no HTTP requests, service actions, RF operations, or writes.
It protects the proven dependency-ordered dashboard loader while keeping the
new MMDVM/vocoder inventory lazy. In particular, it forbids the RC4 preload /
legacy-bundle experiments that caused dashboard startup regressions on Pi Zero.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
vocoder = (ROOT / "web" / "vocoder-manager.js").read_text(encoding="utf-8")
modem = (ROOT / "web" / "modem-ui.js").read_text(encoding="utf-8")
update = (ROOT / "lib" / "dashboard_update.py").read_text(encoding="utf-8")
core = (ROOT / "lib" / "dashboard_core.py").read_text(encoding="utf-8")
css = (ROOT / "web" / "vocoder-manager.css").read_text(encoding="utf-8")

# Restore and preserve the proven dashboard dependency chain. The browser must
# not be forced through the RC4 preload experiment or a generated legacy bundle.
assert "load('/app-core.js'" in app
assert "load('/instrumentation.js?v=alpha12.1'" in app
assert "load('/system-ui.js?v=dashboard1'" in app
assert "load('/ssh-key-export.js?v=rc1-system2'" in app
assert "legacy-ui-bundle" not in update
assert "_LEGACY_UI_COMPONENTS" not in update
assert "_patch_app_js" not in update
assert "readiness_js +" not in update
assert "link.rel = 'preload'" not in update

# Release-only modules are still explicit first-party assets. Their loader is
# tracked so a future splash refinement can observe completion without changing
# the proven base loader itself.
assert "window.__YWD_RELEASE_UI_READY = false" in update
assert "window.__YWD_RELEASE_UI_PROGRESS" in update
assert "window.__YWD_RELEASE_UI_READY = ok" in update
assert "/update-branch.js?v=rc3-wire1" in update
assert "/modem-ui.js?v=rc3-wire1" in update
assert "/vocoder-manager.js?v=rc4-vocoder-foundation3" in update
assert "/tgif-control.js?v=rc4-tgif1" in update

# System-only inventory must remain lazy. Adding the vocoder manager must not
# make initial Status-page startup perform MMDVM/vocoder verification work.
assert "function systemVisible()" in vocoder
assert "function activateWhenVisible()" in vocoder
assert "if (!systemVisible()" in vocoder
assert "Status loads when the System page is opened" in vocoder
assert "function systemVisible()" in modem
assert "function activateWhenVisible()" in modem
assert "if (systemVisible() && !loadedOnce) load(false);" in modem
assert "Inventory loads when the System page is opened." in modem

# Vocoder readiness jobs retain the accepted full-job busy latch and visible
# checking animation; this is independent of dashboard startup.
assert "if (systemVisible()) await loadStatus();" in vocoder
assert "launchPending || jobActive || maintenanceActive ? 1500 : 30000" in vocoder
assert "launchedJobId" in vocoder and "launchPending" in vocoder
assert "launchedTerminal" in vocoder
assert "check.textContent = 'CHECKING…'" in vocoder
assert "renderLaunch(out);" in vocoder
assert ".vocoder-state.busy::before" in css
assert "ywdVocoderBadgePulse" in css
assert "prefers-reduced-motion:reduce" in css

# The dashboard server remains threaded and first-party static JS is revalidated.
assert "ThreadingHTTPServer" in core
assert 'cache="no-cache"' in core

print("[OK] proven dependency-ordered dashboard loader is restored")
print("[OK] preload and generated legacy-bundle startup experiments are absent")
print("[OK] release-only RC4 modules retain tracked first-party loading")
print("[OK] MMDVM and vocoder inventory remain lazy off the initial Status page")
print("[OK] vocoder readiness action keeps full-job busy feedback")
print("[OK] dashboard serving remains threaded with revalidated first-party assets")
