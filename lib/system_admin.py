#!/usr/bin/env python3
"""Narrow privileged host-power actions for YWD-Hotspot."""
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


def shutdown():
    admin.audit("shutdown-request")
    unit = f"ywd-shutdown-{int(time.time())}"
    admin.run(
        ["systemd-run", "--unit", unit, "--on-active=3s", "/bin/systemctl", "poweroff"],
        5,
        check=True,
    )
    return {"ok": True, "scheduled_in_s": 3}


def main():
    if os.geteuid() != 0:
        raise SystemExit("ywd-hotspot system admin must run as root")
    if len(sys.argv) != 2 or sys.argv[1] != "shutdown":
        raise SystemExit("usage: system_admin.py shutdown")
    print(json.dumps(shutdown(), separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:800]}))
        raise SystemExit(1)
