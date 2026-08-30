#!/usr/bin/env python3
"""Source-only regression gate for the RC4 presentation/setup/UI batch.

This test does not read or modify live appliance configuration and does not
start, stop, enable, or reload any service. It verifies source contracts for:
- integrated BrandMeister + TGIF appliance presentation;
- HTTP-only first-boot provisioning with the existing physical-access gate;
- optional TGIF first-boot configuration and redacted restore preview;
- Digital Waterfall as the fresh default while preserving explicit old choices.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

import config_model


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def require(haystack: str, needle: str, label: str) -> None:
    assert needle in haystack, f"{label}: missing {needle!r}"


def reject(haystack: str, needle: str, label: str) -> None:
    assert needle not in haystack, f"{label}: forbidden {needle!r}"


issue = text("lib/branding/issue")
motd = text("lib/branding/motd")
gh_update = text("GITHUB-UPDATE.sh")
branding = text("lib/system_branding.sh")
for name, body in (("issue", issue), ("motd", motd)):
    require(body, "BrandMeister", name)
    require(body, "TGIF", name)
require(gh_update, "Integrated networks: BrandMeister + TGIF.", "GitHub updater")
reject(branding, "secure first-boot wizard only", "console help")
require(branding, "first-boot wizard only", "console help")
print("[OK] login/update presentation identifies BrandMeister + TGIF")

setup = text("lib/setup_server.py")
restore = text("lib/setup_restore_server.py")
setup_admin = text("lib/setup_admin.py")
factory = text("os/pi-gen/stage2/25-ywd-firstboot/01-run.sh")
require(setup, '"url": f"http://ywd-hotspot.local:{PORT}/"', "setup runtime URL")
require(setup, 'p.scheme == "http"', "setup same-origin policy")
require(setup, "HttpOnly; SameSite=Strict", "setup session cookie")
reject(setup, "Secure; HttpOnly", "HTTP setup cookie")
reject(setup, "import ssl", "setup TLS")
reject(setup, "SSLContext", "setup TLS")
reject(setup, "https://ywd-hotspot.local", "setup URL")
reject(restore, "import ssl", "restore TLS")
reject(restore, "SSLContext", "restore TLS")
require(restore, "setup + restore HTTP listening", "restore listener")
reject(factory, "setup-tls", "factory first-boot image")
reject(factory, "secure HTTPS setup wizard", "factory safety text")
require(factory, "HTTP first-boot setup wizard starts on port 8443", "factory safety text")
require(factory, "http://ywd-hotspot.local:8443/", "factory safety URL")
print("[OK] first-boot setup, restore, and factory image are HTTP-only without a self-signed TLS gate")

for needle in ("tgifenabled", "tgifmaster", "tgifport", "tgifpw", "tgif_password"):
    require(setup, needle, "TGIF first-boot wizard")
require(setup, "TGIF security password is required when TGIF is enabled.", "TGIF browser validation")
require(setup_admin, 'candidate.setdefault("tgif", {})["password"] = tgif_password', "TGIF privileged setup")
require(setup_admin, 'candidate["tgif"].get("enabled") and not tgif_password', "TGIF privileged validation")
require(restore, "tgif_password_configured", "first-boot restore preview")
require(restore, "tgif_master", "first-boot restore preview")
require(restore, "tgif_port", "first-boot restore preview")
require(factory, "BrandMeister/TGIF state", "factory restore safety text")
print("[OK] first-boot setup exposes optional TGIF config with redacted password handling")

defaults = config_model.defaults()
assert defaults["web"]["loading_animation"] == "digital_waterfall", defaults["web"]
explicit = config_model.defaults()
explicit["station"].update({"callsign": "KJ6YWD", "base_dmr_id": "3196104"})
explicit["brandmeister"]["enabled"] = False
explicit["web"]["loading_animation"] = "rf_sweep"
normalized = config_model.normalize(explicit)
assert normalized["web"]["loading_animation"] == "rf_sweep", normalized["web"]
startup_js = text("web/startup-themes.js")
startup_css = text("web/startup-themes.css")
require(startup_js, "const DEFAULT_THEME = 'digital_waterfall';", "startup default")
require(startup_js, "STRONG SIGNAL LOCK", "waterfall markup")
require(startup_js, "ywd-waterfall-signal main", "waterfall center signal")
require(startup_css, ".ywd-waterfall-signal.main", "waterfall styling")
require(startup_css, "#fff28e", "waterfall hot core")
print("[OK] Digital Waterfall is the fresh default and explicit existing theme choices remain preserved")

backup_ui = text("web/backup-restore.js")
settings_backup = text("lib/settings_backup.py")
for needle in ("tgif_enabled", "tgif_master", "tgif_port", "tgif_password_configured"):
    require(settings_backup, needle, "settings backup preview")
    require(backup_ui, needle, "normal restore UI")
print("[OK] normal and first-boot restore confirmation surfaces include redacted TGIF intent")
