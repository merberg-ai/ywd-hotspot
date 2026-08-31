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

# The old splash owns a 12-second force-close timer. The first-paint readiness
# gate is intentionally loaded before app.js and intercepts that removal until
# base data, hero image, final System layout, release scripts, and System cards
# have all assembled. A 45-second slow-path offers CONTINUE but never
# automatically exposes a half-built dashboard.
assert "startup-readiness.js" in update
assert "readiness_js + b\"\\n;\\n\" + app_js" in update
assert "window.__YWD_RELEASE_UI_READY = true" in update
assert "window.__YWD_RELEASE_UI_PROGRESS" in update
assert "systemExtensionsMounted" in readiness
assert "hero.complete && hero.naturalWidth > 0" in readiness
assert "hostPowerCard" in readiness
assert "__YWD_RELEASE_UI_READY" in readiness
assert "Element.prototype.remove" in readiness
assert "45000" in readiness and "CONTINUE" in readiness
assert "fullyReady()" in readiness

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
print("[OK] startup splash stays up until base data, hero, System layout, release modules, and System cards are assembled")
print("[OK] slow startup offers manual CONTINUE instead of auto-exposing a partial dashboard")
print("[OK] vocoder readiness action stays disabled until its matching job reaches a terminal state")
print("[OK] vocoder CHECKING state has motion plus reduced-motion fallback")
print("[OK] dashboard static assets are revalidated and HTTP serving remains threaded")
