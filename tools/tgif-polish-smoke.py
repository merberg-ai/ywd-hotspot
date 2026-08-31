#!/usr/bin/env python3
"""Source-only regression for TGIF Control Center presentation polish."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        raise AssertionError(f"missing source: {rel}")
    return path.read_text(encoding="utf-8")


def require(rel: str, *markers: str) -> None:
    data = source(rel)
    for marker in markers:
        if marker not in data:
            raise AssertionError(f"{rel}: missing marker {marker!r}")


def ok(label: str) -> None:
    print(f"[OK] {label}")


js = source("web/tgif-polish.js")
css = source("web/tgif-polish.css")
update = source("lib/dashboard_update.py")
scanner = source("lib/tgif_scanner.py")

require(
    "web/tgif-polish.js",
    "BM TALKGROUPS",
    "BrandMeister Talkgroups",
    "tgifCcSave",
    "SAVING…",
    "tgifCcStart",
    "STARTING…",
    "tgifCcHoldBtn",
    "HOLDING…",
    "tgifCcResume",
    "RESUMING…",
    "tgifCcNext",
    "NEXT…",
    "tgifCcStop",
    "STOPPING…",
    "tgifCcDisconnect",
    "DISCONNECTING…",
    "tgif-action-spinner",
    "__ywdTgifPolishWrapped",
    "/api/tgif/control/status",
    "tgifScannerStatusCard",
    "TGIF SCANNER",
    "Traffic detected · holding this talkgroup",
    "Post-call hold before scanning resumes",
    "Manual hold · press RESUME to continue",
    "dwell remaining",
    "current_tg",
    "current_rf_tg",
    "current_name",
    "setInterval(pollStatus, 1200)",
    "document.hidden",
)
ok("TGIF action buttons get immediate busy labels and spinner feedback")
ok("BrandMeister talkgroup tab is renamed without changing manager ownership")
ok("Status page receives a read-only live TGIF scanner projection")
ok("Status polling is visibility-gated and modest for Pi Zero")

require(
    "web/tgif-polish.css",
    "@keyframes tgif-action-spin",
    "@keyframes tgif-scope-sweep",
    "@keyframes tgif-lock-pulse",
    ".tgif-status-scanner.is-holding",
    ".tgif-status-sweep",
    ".tgif-status-lock",
    "prefers-reduced-motion:reduce",
)
ok("scanner sweep/hold animations and reduced-motion fallback are styled")

require(
    "lib/dashboard_update.py",
    "loadReleaseUi('/tgif-polish.js?v=rc4-tgif-polish1')",
    'tgif_polish_css = _asset_bytes("tgif-polish.css")',
    'body += b"\\n\\n/* TGIF Control Center polish */\\n" + tgif_polish_css',
    '"/tgif-polish.js": ("tgif-polish.js"',
    '"/tgif-polish.css": ("tgif-polish.css"',
)
ok("dashboard bundles and serves the TGIF polish layer")

# The polish slice must not modify scanner/network semantics. It is allowed to
# read the already-proven status endpoint and observe existing control requests,
# but it must not contain session-update URLs, RF actions, or privileged helpers.
for forbidden in (
    "tgif.network:5040",
    "api/sessions/update",
    "ywd-hotspot-admin",
    "rf-start",
    "rf-restart",
):
    if forbidden in js:
        raise AssertionError(f"web/tgif-polish.js unexpectedly owns runtime marker {forbidden!r}")
ok("TGIF polish remains presentation-only and outside scanner/RF ownership")

# Keep a source-level reminder that the proven worker itself still owns the
# session update and traffic-hold behavior.
if "http://tgif.network:5040/api/sessions/update" not in scanner or "traffic_hold(" not in scanner:
    raise AssertionError("hardware-proven scanner ownership moved unexpectedly")
ok("hardware-proven scanner/session ownership remains in tgif_scanner.py")

print("\nTGIF polish smoke: PASS")
