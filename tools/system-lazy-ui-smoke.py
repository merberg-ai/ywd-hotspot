#!/usr/bin/env python3
"""Source-only regression for Pi Zero dashboard startup/System lazy loading.

This smoke performs no HTTP requests, service actions, RF operations, or writes.
It prevents System-only MMDVM/vocoder inventory from creeping back into the
initial Status-page load, prevents fixed-deadline extension mount races, and
keeps the startup splash visible until the assembled dashboard is actually
ready.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
vocoder = (ROOT / "web" / "vocoder-manager.js").read_text(encoding="utf-8")
modem = (ROOT / "web" / "modem-ui.js").read_text(encoding="utf-8")
readiness = (ROOT / "web" / "startup-readiness.js").read_text(encoding="utf-8")
update = (ROOT / "lib" / "dashboard_update.py").read_text(encoding="utf-8")
core = (ROOT / "lib" / "dashboard_core.py").read_text(encoding="utf-8")
css = (ROOT / "web" / "vocoder-manager.css").read_text(encoding="utf-8")

# The authoritative System transformation creates hostPowerCard late in the
# legacy serial loader. Extensions must wait for that final anchor with no
# arbitrary 12-second deadline.
assert "hostPowerCard" in vocoder
assert "hostPowerCard" in modem
assert "tries >=" not in vocoder
assert "tries >=" not in modem
assert "setInterval" in vocoder and "setInterval" in modem

# Neither System-only inventory path should run merely because the Status page
# is starting. Their first automatic read belongs behind System visibility.
assert "function systemVisible()" in vocoder
assert "function activateWhenVisible()" in vocoder
assert "if (!systemVisible()" in vocoder
assert "Status loads when the System page is opened" in vocoder
assert "function systemVisible()" in modem
assert "function activateWhenVisible()" in modem
assert "if (systemVisible() && !loadedOnce) load(false);" in modem
assert "Inventory loads when the System page is opened." in modem

# RC4 keeps the splash until the functional dashboard is assembled. The old
# app.js dependency chain must be observable and may not silently terminate on
# a single static-file request failure. Modules are preloaded up front to avoid
# paying seventeen serial network round trips on a Pi Zero; execution order is
# still owned by app.js.
assert "startup-readiness.js" in update
assert "readiness_js + b\"\\n;\\n\" + app_js" in update
assert "_patch_app_js" in update
assert "__YWD_LEGACY_UI_PROGRESS" in update
assert "failedSources" in update
assert "finish(false)" in update
assert "LEGACY_MODULES" in readiness
assert "link.rel = 'preload'" in readiness
assert "__YWD_LEGACY_UI_PROGRESS" in readiness
assert "Loading dashboard modules…" in readiness
assert "Dashboard module failed to load:" in readiness
assert "ywd:legacy-ui-progress" in readiness

# Release UI modules have their own tracked loader. A failed release module is
# never reported as ready.
assert "window.__YWD_RELEASE_UI_READY = false" in update
assert "window.__YWD_RELEASE_UI_READY = ok" in update
assert "window.__YWD_RELEASE_UI_PROGRESS" in update
assert "failed:0" in update and ".failed += 1" in update

# The hero/banner is a late cosmetic transform. If present its image must load,
# but absence alone cannot deadlock the appliance UI. A short settle window
# gives normal final transforms time to land before the splash leaves.
assert "systemExtensionsMounted" in readiness
assert "structuralReady" in readiness
assert "SETTLE_MS = 500" in readiness
assert "hero.complete && hero.naturalWidth > 0" in readiness
assert "Finalizing dashboard interface" in readiness
assert "hostPowerCard" in readiness
assert "__YWD_RELEASE_UI_READY" in readiness
assert "__YWD_RELEASE_UI_PROGRESS" in readiness
assert "RC4 interface module load failed" in readiness
assert "Element.prototype.remove" in readiness
assert "45000" in readiness and "CONTINUE" in readiness
assert "fullyReady()" in readiness
assert "document.createElement('style')" not in readiness
assert 'document.createElement("style")' not in readiness
assert "#ywdStartupOverlay.ywd-startup-held" in css

# The browser server is threaded and static release assets are explicitly
# revalidated, so this strategy does not depend on stale browser cache or
# serial request handling for correctness.
assert "ThreadingHTTPServer" in core
assert 'cache="no-cache"' in core

# Vocoder status polling remains scoped to a visible System page. Once a
# readiness job is accepted, a client-side job-id latch keeps the action
# disabled until the matching terminal state is observed from the server.
assert "if (systemVisible()) await loadStatus();" in vocoder
assert "launchPending || jobActive || maintenanceActive ? 1500 : 30000" in vocoder
assert "launchedJobId" in vocoder and "launchPending" in vocoder
assert "launchedTerminal" in vocoder
assert "check.textContent = 'CHECKING…'" in vocoder
assert "renderLaunch(out);" in vocoder

# Busy job state must be visible even when the console is not being watched.
assert ".vocoder-state.busy::before" in css
assert "ywdVocoderBadgePulse" in css
assert "prefers-reduced-motion:reduce" in css

print("[OK] System extensions wait for the completed System layout without a fixed mount deadline")
print("[OK] MMDVM and vocoder inventory are lazy and do not burden initial Status-page startup")
print("[OK] legacy dashboard modules are preloaded and expose exact startup progress")
print("[OK] a failed legacy module advances and is reported instead of silently freezing startup")
print("[OK] startup splash waits for functional dashboard structure and release/System modules")
print("[OK] failed release UI modules keep the splash covered instead of reporting false readiness")
print("[OK] late hero artwork is allowed to settle but cannot deadlock dashboard startup")
print("[OK] slow startup offers manual CONTINUE instead of auto-exposing a partial dashboard")
print("[OK] startup readiness styling remains CSP-safe")
print("[OK] vocoder readiness action stays disabled until its matching job reaches a terminal state")
print("[OK] vocoder CHECKING state has motion plus reduced-motion fallback")
print("[OK] dashboard static assets are revalidated and HTTP serving remains threaded")
