#!/usr/bin/env python3
"""Source-only regression for Pi Zero dashboard startup/System lazy loading.

This smoke performs no HTTP requests, service actions, RF operations, or writes.
It prevents System-only MMDVM/vocoder inventory from creeping back into the
initial Status-page load and prevents fixed-deadline extension mount races.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
vocoder = (ROOT / "web" / "vocoder-manager.js").read_text(encoding="utf-8")
modem = (ROOT / "web" / "modem-ui.js").read_text(encoding="utf-8")
core = (ROOT / "lib" / "dashboard_core.py").read_text(encoding="utf-8")

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

# The browser server is threaded and static release assets are explicitly
# revalidated, so this lazy strategy does not depend on stale browser cache or
# serial request handling for correctness.
assert "ThreadingHTTPServer" in core
assert 'cache="no-cache"' in core

# Vocoder status polling remains scoped to a visible System page, while an
# accepted background job can still poll quickly after the operator starts it.
assert "if (systemVisible()) await loadStatus();" in vocoder
assert "jobActive || maintenanceActive ? 1500 : 30000" in vocoder
assert "renderLaunch(out);" in vocoder

print("[OK] System extensions wait for the completed System layout without a fixed mount deadline")
print("[OK] MMDVM and vocoder inventory are lazy and do not burden initial Status-page startup")
print("[OK] vocoder job feedback/polling remains active after an operator-started readiness job")
print("[OK] dashboard static assets are revalidated and HTTP serving remains threaded")
