#!/usr/bin/env python3
"""Preserve TGIF watchlist-scanner runtime intent across application updates.

This helper is deliberately independent of dashboard sessions and network secrets.
It captures only scanner runtime intent, stops the scanner before live application
replacement, and restores scanning afterward when the installed target still
supports the scanner and TGIF remains enabled.
"""
from __future__ import annotations

import argparse
import grp
import json
import os
import subprocess
import time
from pathlib import Path

SERVICE = "ywd-tgif-scanner.service"
CFG = Path("/etc/ywd-hotspot/config.json")
PREFS = Path("/var/lib/ywd-hotspot/tgif-control.json")
RUNTIME = Path("/run/ywd-hotspot/tgif-scanner.json")
RESTORE_HINT = Path("/run/ywd-hotspot/tgif-scanner-restore.json")
TARGET_APP = Path("/opt/ywd-hotspot/app")


def run(args, timeout=20):
    return subprocess.run(
        args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, check=False,
    )


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def atomic_json(path: Path, doc: dict, mode=0o600, group=False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, mode)
    if group:
        try:
            os.chown(tmp, 0, grp.getgrnam("ywd-hotspot").gr_gid)
        except Exception:
            pass
    os.replace(tmp, path)


def service_active() -> bool:
    return run(["systemctl", "is-active", "--quiet", SERVICE], 5).returncode == 0


def clean_state(value) -> str:
    state = str(value or "stopped").strip().lower()
    allowed = {"starting", "scanning", "holding", "stopped", "idle", "disabled", "tuned", "disconnected", "error"}
    return state if state in allowed else "unknown"


def valid_tg(value):
    try:
        tg = int(value)
    except Exception:
        return None
    return tg if 1 <= tg <= 999999 and tg != 4000 else None


def normalized_slot(*values) -> int:
    for value in values:
        try:
            return 1 if int(value) == 1 else 2
        except Exception:
            continue
    return 2


def capture_doc() -> dict:
    cfg = read_json(CFG, {})
    tgif = cfg.get("tgif") if isinstance(cfg, dict) and isinstance(cfg.get("tgif"), dict) else {}
    runtime = read_json(RUNTIME, {})
    if not isinstance(runtime, dict):
        runtime = {}
    prefs = read_json(PREFS, {})
    if not isinstance(prefs, dict):
        prefs = {}
    watch = prefs.get("watchlist") if isinstance(prefs.get("watchlist"), list) else []
    enabled_watch = [row for row in watch if isinstance(row, dict) and row.get("enabled", True)]
    state = clean_state(runtime.get("state"))
    hold_reason = str(runtime.get("hold_reason") or "").strip().lower()
    return {
        "schema": 1,
        "captured_at": time.time(),
        "service_active": service_active(),
        "state": state,
        "current_tg": valid_tg(runtime.get("current_tg")),
        "slot": normalized_slot(runtime.get("slot"), prefs.get("slot")),
        "manual_hold": bool(runtime.get("manual_hold")) or (state == "holding" and hold_reason == "manual"),
        "hold_reason": hold_reason or None,
        "tgif_enabled": bool(tgif.get("enabled", False)),
        "watch_count": len(enabled_watch),
    }


def describe(doc: dict) -> str:
    state = str(doc.get("state") or "stopped").upper()
    tg = doc.get("current_tg")
    suffix = f" TG {tg}" if tg else ""
    return f"{state}{suffix}"


def capture(snapshot: Path) -> dict:
    doc = capture_doc()
    atomic_json(snapshot, doc, 0o600, group=False)
    activity = "active" if doc.get("service_active") else "inactive"
    print(f"TGIF scanner snapshot: {activity} · {describe(doc)}")
    return doc


def quiesce(snapshot: Path) -> dict:
    doc = read_json(snapshot, {})
    if not isinstance(doc, dict):
        raise RuntimeError("TGIF scanner update snapshot is invalid")
    if not doc.get("service_active"):
        print("TGIF scanner quiesce: not needed (scanner was not active).")
        return {"ok": True, "quiesced": False}
    p = run(["systemctl", "stop", SERVICE], 20)
    if p.returncode != 0 or service_active():
        detail = (p.stderr or p.stdout or "scanner remained active").strip()[-500:]
        raise RuntimeError(f"could not quiesce TGIF scanner before update: {detail}")
    print("TGIF scanner quiesced for application update.")
    return {"ok": True, "quiesced": True}


def target_supports_scanner() -> bool:
    return (
        (TARGET_APP / "lib/tgif_scanner.py").is_file()
        and (TARGET_APP / "lib/tgif_scanner_admin.py").is_file()
        and (TARGET_APP / "systemd/ywd-tgif-scanner.service").is_file()
    )


def target_tgif_enabled() -> bool:
    cfg = read_json(CFG, {})
    tg = cfg.get("tgif") if isinstance(cfg, dict) and isinstance(cfg.get("tgif"), dict) else {}
    return bool(tg.get("enabled", False))


def target_watch_count() -> int:
    prefs = read_json(PREFS, {})
    rows = prefs.get("watchlist") if isinstance(prefs, dict) and isinstance(prefs.get("watchlist"), list) else []
    count = 0
    for row in rows:
        if not isinstance(row, dict) or not row.get("enabled", True):
            continue
        if valid_tg(row.get("id")) is not None:
            count += 1
    return count


def write_restore_hint(doc: dict) -> None:
    tg = valid_tg(doc.get("current_tg"))
    if tg is None:
        try:
            RESTORE_HINT.unlink()
        except FileNotFoundError:
            pass
        return
    atomic_json(
        RESTORE_HINT,
        {
            "schema": 1,
            "talkgroup": tg,
            "slot": normalized_slot(doc.get("slot")),
            "manual_hold": bool(doc.get("manual_hold")),
            "issued_at": time.time(),
            "reason": "application-update-restore",
        },
        0o640,
        group=True,
    )


def fresh_runtime_after(timestamp: float):
    runtime = read_json(RUNTIME, {})
    if not isinstance(runtime, dict):
        return None
    try:
        updated = float(runtime.get("updated_at") or 0)
    except Exception:
        updated = 0
    if updated < timestamp:
        return None
    if not runtime.get("active"):
        return None
    return runtime


def restore(snapshot: Path) -> dict:
    doc = read_json(snapshot, {})
    if not isinstance(doc, dict):
        raise RuntimeError("TGIF scanner update snapshot is invalid")
    if not doc.get("service_active"):
        print("TGIF scanner restore: not needed (scanner was not active before update).")
        return {"ok": True, "restored": False, "reason": "not-active-before-update"}
    if not target_supports_scanner():
        print("[WARN] TGIF scanner was active before update, but the installed target has no scanner runtime; scanner remains stopped.")
        return {"ok": True, "restored": False, "reason": "target-unsupported"}
    if not target_tgif_enabled():
        print("[WARN] TGIF scanner was active before update, but TGIF is disabled in the installed configuration; scanner remains stopped.")
        return {"ok": True, "restored": False, "reason": "tgif-disabled"}
    if target_watch_count() < 1:
        print("[WARN] TGIF scanner was active before update, but the installed watchlist is empty; scanner remains stopped.")
        return {"ok": True, "restored": False, "reason": "empty-watchlist"}

    restore_started = time.time()
    write_restore_hint(doc)
    p = run(["systemctl", "start", SERVICE], 20)
    if p.returncode != 0:
        try:
            RESTORE_HINT.unlink()
        except FileNotFoundError:
            pass
        detail = (p.stderr or p.stdout or "could not start scanner").strip()[-500:]
        raise RuntimeError(f"TGIF scanner restore failed: {detail}")

    runtime = None
    deadline = time.time() + 12.0
    while time.time() < deadline:
        if not service_active():
            raise RuntimeError("TGIF scanner restore failed: service exited during restart")
        runtime = fresh_runtime_after(restore_started)
        if runtime is not None:
            break
        time.sleep(0.4)
    if runtime is None:
        raise RuntimeError("TGIF scanner restore timed out waiting for fresh runtime state")

    state = clean_state(runtime.get("state"))
    tg = valid_tg(runtime.get("current_tg"))
    suffix = f" TG {tg}" if tg else ""
    manual = " with manual HOLD restored" if doc.get("manual_hold") else ""
    print(f"TGIF scanner restored after application update: {state.upper()}{suffix}{manual}.")
    return {"ok": True, "restored": True, "state": state, "current_tg": tg, "manual_hold": bool(doc.get("manual_hold"))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("capture", "quiesce", "restore", "status"))
    parser.add_argument("--snapshot", required=False)
    args = parser.parse_args()
    snapshot = Path(args.snapshot) if args.snapshot else None
    if args.operation in {"capture", "quiesce", "restore"} and snapshot is None:
        raise SystemExit("--snapshot is required")
    if args.operation == "capture":
        capture(snapshot)
    elif args.operation == "quiesce":
        quiesce(snapshot)
    elif args.operation == "restore":
        restore(snapshot)
    else:
        print(json.dumps(capture_doc(), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] {exc}")
        raise SystemExit(1)
