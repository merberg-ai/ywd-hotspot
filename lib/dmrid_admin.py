#!/usr/bin/env python3
"""Privileged DMR ID database status and maintenance actions for YWD-Hotspot."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import admin

CFG = Path(os.environ.get("YWD_CONFIG", "/etc/ywd-hotspot/config.json"))
DB = Path(os.environ.get("YWD_DMRID_FILE", "/var/lib/ywd-hotspot/DMRIds.dat"))
META = Path(os.environ.get("YWD_DMRID_META", "/var/lib/ywd-hotspot/dmrid-status.json"))
UPDATER = HERE / "id-update.py"
SOURCE = "RadioID.net"


def interval_days() -> int:
    try:
        cfg = json.loads(CFG.read_text(encoding="utf-8"))
        value = int(cfg.get("maintenance", {}).get("dmrid_update_days", 7))
        return max(1, min(30, value))
    except Exception:
        return 7


def unit_value(unit: str, prop: str) -> str:
    p = admin.run(["systemctl", "show", unit, f"--property={prop}", "--value"], 5)
    return (p.stdout or "").strip() if p.returncode == 0 else ""


def unit_state(unit: str) -> str:
    p = admin.run(["systemctl", "is-active", unit], 5)
    value = (p.stdout or "").strip()
    return value or "unknown"


def unit_enabled(unit: str) -> str:
    p = admin.run(["systemctl", "is-enabled", unit], 5)
    value = (p.stdout or "").strip()
    return value or "unknown"


def record_count(stat) -> int | None:
    """Count non-empty records once per database revision and cache the result."""
    signature = {"size_bytes": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)}
    try:
        cached = json.loads(META.read_text(encoding="utf-8"))
        if (
            isinstance(cached, dict)
            and cached.get("size_bytes") == signature["size_bytes"]
            and cached.get("mtime_ns") == signature["mtime_ns"]
            and isinstance(cached.get("records"), int)
            and cached["records"] >= 0
        ):
            return int(cached["records"])
    except Exception:
        pass

    try:
        with DB.open("rb") as handle:
            count = sum(1 for line in handle if line.strip())
    except Exception:
        return None

    try:
        admin.atomic_json(META, {**signature, "records": count, "counted_at": time.time()})
    except Exception:
        pass
    return count


def status(include_units: bool = False) -> dict:
    now = time.time()
    days = interval_days()
    present = DB.is_file()
    updated = None
    age = None
    next_due = None
    due = True
    size = None
    records = None
    usable = False
    if present:
        stat = DB.stat()
        updated = float(stat.st_mtime)
        size = int(stat.st_size)
        age = max(0.0, now - updated)
        next_due = updated + days * 86400
        records = record_count(stat)
        usable = size > 0 and records is not None and records > 0
        due = (not usable) or age >= days * 86400

    if include_units:
        service_result = unit_value("ywd-dmrid-update.service", "Result") or "unknown"
        exit_status = unit_value("ywd-dmrid-update.service", "ExecMainStatus") or "unknown"
        timer_active = unit_state("ywd-dmrid-update.timer")
        timer_enabled = unit_enabled("ywd-dmrid-update.timer")
    else:
        # Automatic WebUI status polling stays entirely in the cheap data
        # plane: filesystem/config metadata only, with no systemctl subprocesses.
        service_result = "unknown"
        exit_status = "unknown"
        timer_active = "unknown"
        timer_enabled = "unknown"
    if not present:
        state = "missing"
    elif not usable:
        state = "empty"
    elif service_result not in {"success", "unknown"}:
        state = "warning"
    elif due:
        state = "due"
    else:
        state = "current"

    return {
        "ok": True,
        "database": {
            "source": SOURCE,
            "path": str(DB),
            "present": present,
            "usable": usable,
            "records": records,
            "size_bytes": size,
            "last_updated": updated,
            "age_s": age,
            "interval_days": days,
            "next_due": next_due,
            "due": due,
            "state": state,
        },
        "timer": {
            "active": timer_active,
            "enabled": timer_enabled,
        },
        "service": {
            "result": service_result,
            "exit_status": exit_status,
        },
    }


def run_update(force: bool) -> dict:
    if not UPDATER.is_file():
        raise RuntimeError(f"DMR ID updater is missing: {UPDATER}")
    action = "dmrid-update-force" if force else "dmrid-update-check"
    admin.audit(action)
    args = ["/usr/bin/python3", str(UPDATER)]
    if force:
        args.append("--force")
    p = admin.run(args, 90, check=False)
    message = ((p.stdout or "") + ("\n" + p.stderr if p.stderr else "")).strip()
    if p.returncode != 0:
        raise RuntimeError(message or f"DMR ID updater failed ({p.returncode})")
    out = status(include_units=True)
    out["action"] = "update" if force else "check"
    out["message"] = message or "DMR ID database check completed."
    return out


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("ywd-hotspot DMR ID admin must run as root")
    if len(sys.argv) != 2:
        raise SystemExit("usage: dmrid_admin.py dmrid-status|dmrid-check|dmrid-update")
    action = sys.argv[1]
    if action == "dmrid-status":
        out = status()
    elif action == "dmrid-check":
        out = run_update(False)
    elif action == "dmrid-update":
        out = run_update(True)
    else:
        raise SystemExit("usage: dmrid_admin.py dmrid-status|dmrid-check|dmrid-update")
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:800]}))
        raise SystemExit(1)
