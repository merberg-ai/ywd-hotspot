#!/usr/bin/env python3
"""Source-only regression for the TGIF Control Center/watchlist scanner.

The only socket opened by this test is a loopback HTTP server used to prove URL
construction. It never contacts TGIF, changes live config, starts services, or
keys RF.
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

import tgif_scanner


def ok(label, condition=True):
    if not condition:
        raise AssertionError(label)
    print(f"[OK] {label}")


def source(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


raw = {
    "dwell_s": 999,
    "hold_s": -4,
    "slot": 1,
    "favorites": [{"id": 31665, "name": "TGIF"}, {"id": 31665, "name": "duplicate"}, {"id": 4000}],
    "watchlist": [
        {"id": 4000, "name": "disconnect", "priority": 1, "enabled": True},
        *[
            {"id": i, "name": f"TG {i}", "priority": i + 1, "enabled": True}
            for i in range(1, 14)
        ],
    ],
}
simplex = tgif_scanner.normalize_preferences(raw, "simplex")
ok("simplex scanner is forced to TS2", simplex["slot"] == 2)
ok("dwell is bounded to 60 seconds", simplex["dwell_s"] == 60)
ok("post-call hold is bounded to zero", simplex["hold_s"] == 0)
ok("favorites are de-duplicated and TG4000 is excluded", [r["id"] for r in simplex["favorites"]] == [31665])
ok("watchlist is limited to ten entries", len(simplex["watchlist"]) == 10)
ok("TG4000 is rejected before watchlist truncation", all(r["id"] != 4000 for r in simplex["watchlist"]))

duplex = tgif_scanner.normalize_preferences({"slot":1,"watchlist":[{"id":31665}]}, "duplex")
ok("duplex scanner preserves explicit TS1", duplex["slot"] == 1)
ok("TGIF RF namespace math remains 5xxxxxx", tgif_scanner.RF_BASE + 31665 == 5031665)

captured = []
class H(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return
    def do_GET(self):
        captured.append(self.path)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"200")

server = ThreadingHTTPServer(("127.0.0.1", 0), H)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
old_api = tgif_scanner.SESSION_API
tgif_scanner.SESSION_API = f"http://127.0.0.1:{server.server_port}/api/sessions/update"
try:
    tgif_scanner.session_update(319610401, 2, 31665, timeout=2)
    tgif_scanner.session_update(319610401, 1, 9990, timeout=2)
finally:
    tgif_scanner.SESSION_API = old_api
    server.shutdown(); server.server_close(); thread.join(timeout=2)
ok("TS2 session update uses TGIF API slot 1", captured[0].endswith("/319610401/1/31665"))
ok("TS1 session update uses TGIF API slot 0", captured[1].endswith("/319610401/0/9990"))

with tempfile.TemporaryDirectory(prefix="ywd-tgif-scanner-smoke-") as td:
    path = Path(td) / "activity.json"
    old_activity = tgif_scanner.ACTIVITY
    tgif_scanner.ACTIVITY = path
    now = time.time()
    path.write_text(json.dumps({
        "current": {
            "active": True,
            "path": "NETWORK",
            "slot": 2,
            "started_at": now - 0.5,
            "destination": {"id": 5031665, "group": True},
        },
        "lastheard": [],
    }))
    holding, reason, until = tgif_scanner.traffic_hold(31665, 2, now - 1, 3, now=now)
    ok("active TGIF network traffic holds the matching scanner TG", holding and reason == "traffic" and until is None)

    path.write_text(json.dumps({
        "current": {"active": False},
        "lastheard": [{
            "active": False,
            "path": "NETWORK",
            "slot": 2,
            "started_at": now - 1.5,
            "ended_at": now - 1,
            "destination": {"id": 5031665, "group": True},
        }],
    }))
    holding, reason, until = tgif_scanner.traffic_hold(31665, 2, now - 2, 3, now=now)
    ok("completed TGIF traffic honors post-call hold", holding and reason == "post-call" and until > now)

    path.write_text(json.dumps({
        "current": {
            "active": True,
            "path": "RF",
            "slot": 2,
            "started_at": now - 0.5,
            "destination": {"id": 5031665, "group": True},
        },
        "lastheard": [],
    }))
    holding, _reason, _until = tgif_scanner.traffic_hold(31665, 2, now - 1, 3, now=now)
    ok("local RF transmission does not masquerade as scanner RX activity", not holding)
    tgif_scanner.ACTIVITY = old_activity

worker = source("lib/tgif_scanner.py")
admin = source("lib/tgif_scanner_admin.py")
ui = source("web/tgif-control.js")
css = source("web/tgif-control.css")
dashboard = source("lib/dashboard_backup.py")
status_projection = source("lib/dashboard_tgif_control.py")
dispatch = source("lib/admin_dispatch.sh")
sudoers = source("sudoers/ywd-hotspot")
unit = source("systemd/ywd-tgif-scanner.service")

ok("scanner uses TGIF session-update endpoint", "http://tgif.network:5040/api/sessions/update" in worker)
ok("scanner contains no RF start/restart action", "rf-start" not in worker and "rf-restart" not in worker)
ok("traffic is evaluated before an expired dwell can advance", "Traffic wins the dwell race" in worker and "holding and not force_next" in worker)
ok("scanner service runs unprivileged", "User=ywd-hotspot" in unit and "Group=ywd-hotspot" in unit)
ok("scanner service is runtime-only", "Restart=no" in unit and "WantedBy=" not in unit)
ok("scanner privileged bridge is one validated action", "tgif-control)" in dispatch and "ywd-hotspot-admin tgif-control" in sudoers)
ok("dashboard exposes read-only scanner status", 'path == "/api/tgif/control/status"' in dashboard)
ok("read-only scanner status bypasses sudo/admin mutation bridge", "dashboard_tgif_control.public_status()" in dashboard and "admin_call" not in status_projection)
for endpoint in ("save","start","stop","hold","resume","next","tune","disconnect"):
    ok(f"dashboard exposes authenticated scanner {endpoint}", f'"/api/tgif/control/{endpoint}"' in dashboard)
ok("TGIF tab is conditional on TGIF enablement", "tgifEnabled()" in ui and "tab.hidden = !enabled" in ui)
ok("Control Center states the no-RF session behavior", "without keying RF" in ui)
ok("Control Center exposes radio promiscuous/Open RX guidance", "Promiscuous" in ui and "Digital Monitor" in ui)
ok("Control Center exposes max-10 watchlist", "limited to 10 talkgroups" in ui and "max 10" in ui)
ok("dedicated Control Center owns TGIF directory/favorites presentation", "#tgifDirectoryCard,#tgifFavoritesCard" in css)
ok("Control Center styles are bundled separately", "TGIF Control Center" in css)

print("\nTGIF scanner smoke: PASS")
