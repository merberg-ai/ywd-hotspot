#!/usr/bin/env python3
"""Source-only regression for TGIF scanner-aware update preservation."""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import tgif_scanner_update_safety as safety


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def require(rel: str, *markers: str) -> None:
    data = text(rel)
    for marker in markers:
        assert marker in data, f"{rel}: missing marker {marker!r}"


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ywd-tgif-update-smoke-") as tmpdir:
        tmp = Path(tmpdir)
        safety.CFG = tmp / "config.json"
        safety.PREFS = tmp / "tgif-control.json"
        safety.RUNTIME = tmp / "run" / "tgif-scanner.json"
        safety.RESTORE_HINT = tmp / "run" / "tgif-scanner-restore.json"
        safety.TARGET_APP = tmp / "app"

        write(safety.CFG, {"tgif": {"enabled": True}})
        write(safety.PREFS, {
            "slot": 2,
            "watchlist": [
                {"id": 31665, "name": "TGIF The Mothership", "enabled": True},
                {"id": 9990, "name": "Parrot", "enabled": True},
            ],
        })
        write(safety.RUNTIME, {
            "state": "holding",
            "active": True,
            "current_tg": 9990,
            "slot": 2,
            "manual_hold": True,
            "hold_reason": "manual",
            "updated_at": time.time(),
        })

        active = {"value": True}
        original_run = safety.run
        original_active = safety.service_active

        safety.service_active = lambda: active["value"]
        doc = safety.capture_doc()
        assert doc["service_active"] is True
        assert doc["state"] == "holding"
        assert doc["current_tg"] == 9990
        assert doc["manual_hold"] is True
        assert doc["watch_count"] == 2

        snapshot = tmp / "snapshot.json"
        safety.capture(snapshot)

        def fake_run(args, timeout=20):
            if args[:2] == ["systemctl", "stop"]:
                active["value"] = False
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            if args[:2] == ["systemctl", "start"]:
                active["value"] = True
                write(safety.RUNTIME, {
                    "state": "holding",
                    "active": True,
                    "current_tg": 9990,
                    "slot": 2,
                    "manual_hold": True,
                    "hold_reason": "manual",
                    "updated_at": time.time() + 0.01,
                })
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        safety.run = fake_run
        out = safety.quiesce(snapshot)
        assert out["quiesced"] is True
        assert active["value"] is False
        print("[OK] active TGIF scanner is captured and quiesced before live replacement")

        for rel in ("lib/tgif_scanner.py", "lib/tgif_scanner_admin.py", "systemd/ywd-tgif-scanner.service"):
            path = safety.TARGET_APP / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("test\n", encoding="utf-8")

        restored = safety.restore(snapshot)
        assert restored["restored"] is True
        assert restored["current_tg"] == 9990
        assert restored["manual_hold"] is True
        hint = json.loads(safety.RESTORE_HINT.read_text(encoding="utf-8"))
        assert hint["talkgroup"] == 9990
        assert hint["manual_hold"] is True
        assert hint["reason"] == "application-update-restore"
        print("[OK] scanner restore preserves the current TG and explicit manual HOLD intent")

        safety.TARGET_APP = tmp / "unsupported-target"
        active["value"] = False
        skipped = safety.restore(snapshot)
        assert skipped["restored"] is False
        assert skipped["reason"] == "target-unsupported"
        print("[OK] scanner restore fails soft when a selected target has no scanner runtime")

        safety.run = original_run
        safety.service_active = original_active

    require(
        "lib/tgif_scanner.py",
        "RESTORE_HINT = Path",
        "def read_restore_hint():",
        "application update can stop the daemon",
        'manual_hold = bool(hint.get("manual_hold"))',
    )
    print("[OK] scanner daemon consumes a one-shot update restore hint before normal rotation")

    require(
        "UPDATE.sh",
        "YWD_TGIF_SCANNER_OUTER",
        "tgif_scanner_update_safety.py\" capture",
        "tgif_scanner_update_safety.py\" quiesce",
        "tgif_scanner_update_safety.py\" restore",
    )
    require(
        "GITHUB-UPDATE-core.sh",
        ".ywd-tgif-scanner-update-safety.py",
        "scanner_transition_snapshot",
        "YWD_TGIF_SCANNER_OUTER=1",
        "Reconciling TGIF scanner runtime with installed target",
    )
    print("[OK] direct and GitHub/channel update paths share scanner preservation ownership")

    require(
        "lib/update_runner.py",
        '"scanner-paused"',
        '"scanner-restored"',
        '"scanner_was_active"',
        '"scanner_restore"',
    )
    require(
        "lib/dashboard_update.py",
        '"scanner_was_active"',
        '"scanner_before_state"',
        '"scanner_restore"',
    )
    require(
        "web/update.js",
        "TGIF scanner will pause only during live replacement and resume automatically",
        "Manual HOLD is preserved",
        "TGIF scanner runtime was restored automatically",
    )
    require(
        "web/update-branch.js",
        "If the TGIF watchlist scanner is active",
        "paused for live replacement and restored when supported by the target",
    )
    print("[OK] dashboard update/check/channel UI explains and reports scanner preservation")

    require(
        "GITHUB-UPDATE.sh",
        "TGIF scanner is ACTIVE",
        "TGIF scanner runtime intent is preserved across supported updates",
    )
    require(
        "lib/console/ywd-system-info.py",
        "TGIF Scanner",
        "SCANNING  TG",
    )
    print("[OK] terminal updater/login surfaces are scanner-aware")

    print("\nTGIF update safety smoke: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] {exc}")
        raise SystemExit(1)
