#!/usr/bin/env python3
"""Small, dependency-free system health collector for YWD-Hotspot."""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

UNITS = [
    "ywd-mmdvmhost.service", "ywd-dmrgateway.service", "ywd-dashboard.service",
    "ywd-headless-oled.service", "ywd-oled.service", "ywd-activity.service",
    "ywd-mqtt.service", "ssh.service", "ywd-dmrid-update.timer",
]


def run(args, timeout=2):
    try:
        p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=timeout, check=False)
        return p.stdout.strip()
    except Exception:
        return ""


def _read(path, default=""):
    try:
        return Path(path).read_text().strip()
    except Exception:
        return default


def boot_id():
    return _read("/proc/sys/kernel/random/boot_id", "unknown")


def boot_time_epoch():
    try:
        up = float(_read("/proc/uptime", "0").split()[0])
        return time.time() - up
    except Exception:
        return None


def previous_boot():
    txt = run(["journalctl", "--list-boots", "--no-pager"], 2)
    lines = [x for x in txt.splitlines() if x.strip()]
    if len(lines) < 2:
        return {"available": False, "shutdown": "unknown", "last_lines": []}
    prev = run(["journalctl", "-b", "-1", "-n", "60", "--no-pager", "-o", "cat"], 3)
    pl = [x for x in prev.splitlines() if x.strip()]
    low = "\n".join(pl).lower()
    clean_markers = ("reached target system power off", "powering off", "systemd-shutdown", "shutting down")
    clean = any(x in low for x in clean_markers)
    return {"available": True, "shutdown": "clean" if clean else "unclean-or-hard-reset", "last_lines": pl[-8:]}


def throttled():
    out = run(["vcgencmd", "get_throttled"], 1)
    m = re.search(r"0x([0-9a-fA-F]+)", out)
    val = int(m.group(1), 16) if m else None
    if val is None:
        return {"raw": out or "unavailable", "value": None, "current_under_voltage": None, "history": []}
    flags = []
    names = {
        0: "under-voltage now", 1: "frequency capped now", 2: "throttled now", 3: "soft temperature limit now",
        16: "under-voltage occurred", 17: "frequency capping occurred", 18: "throttling occurred", 19: "soft temperature limit occurred",
    }
    for bit, name in names.items():
        if val & (1 << bit): flags.append(name)
    return {"raw": out, "value": val, "current_under_voltage": bool(val & 1), "history": flags}


def temp_c():
    try: return round(int(_read("/sys/class/thermal/thermal_zone0/temp", "0")) / 1000, 1)
    except Exception: return None


def memory():
    vals = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            p = line.split(); vals[p[0].rstrip(":")] = int(p[1])
        total, avail = vals.get("MemTotal", 0), vals.get("MemAvailable", 0)
        swap_total, swap_free = vals.get("SwapTotal", 0), vals.get("SwapFree", 0)
        return {
            "total_mb": round(total/1024, 1), "used_mb": round((total-avail)/1024, 1),
            "available_mb": round(avail/1024, 1), "swap_used_mb": round((swap_total-swap_free)/1024, 1),
        }
    except Exception:
        return {}


def disk(path="/"):
    try:
        u = shutil.disk_usage(path)
        return {"total_gb": round(u.total/2**30,2), "used_gb": round(u.used/2**30,2),
                "free_gb": round(u.free/2**30,2), "used_pct": round(u.used*100/u.total,1)}
    except Exception:
        return {}


def wifi():
    out = {"interface": "wlan0", "ssid": None, "signal_dbm": None, "connected": False,
           "rx_errors": None, "tx_errors": None, "ip": None, "gateway": None}
    link = run(["iw", "dev", "wlan0", "link"], 2) if shutil.which("iw") else ""
    if link:
        out["connected"] = "Connected to" in link
        m = re.search(r"SSID:\s*(.+)", link); out["ssid"] = m.group(1).strip() if m else None
        m = re.search(r"signal:\s*(-?[0-9.]+)\s*dBm", link)
        out["signal_dbm"] = round(float(m.group(1)),1) if m else None
    else:
        try:
            for ln in Path("/proc/net/wireless").read_text().splitlines():
                if "wlan0:" in ln:
                    parts = ln.replace(".", " ").split()
                    if len(parts) >= 5:
                        out["connected"] = True
                        out["signal_dbm"] = float(parts[3])
        except Exception:
            pass
    ip = run(["ip", "-4", "-o", "addr", "show", "dev", "wlan0"], 1)
    m = re.search(r"inet\s+([0-9.]+)/", ip); out["ip"] = m.group(1) if m else None
    route = run(["ip", "route", "show", "default"], 1)
    m = re.search(r"default via ([0-9.]+).*dev wlan0", route); out["gateway"] = m.group(1) if m else None
    stats = run(["ip", "-s", "link", "show", "wlan0"], 1)
    lines = stats.splitlines()
    try:
        for i, ln in enumerate(lines):
            if "RX:" in ln and i + 1 < len(lines):
                p = lines[i+1].split(); out["rx_errors"] = int(p[2]); out["rx_dropped"] = int(p[3])
            if "TX:" in ln and i + 1 < len(lines):
                p = lines[i+1].split(); out["tx_errors"] = int(p[2]); out["tx_dropped"] = int(p[3])
    except Exception:
        pass
    return out


def services():
    result = {}
    states = run(["systemctl", "is-active", *UNITS], 2).splitlines()
    enabled = run(["systemctl", "is-enabled", *UNITS], 2).splitlines()
    for i, unit in enumerate(UNITS):
        restarts = run(["systemctl", "show", unit, "-p", "NRestarts", "--value"], 1)
        result[unit] = {
            "active": states[i].strip() if i < len(states) else "unknown",
            "enabled": enabled[i].strip() if i < len(enabled) else "unknown",
            "restarts": int(restarts) if restarts.isdigit() else None,
        }
    return result


def kernel_warnings():
    txt = run(["journalctl", "-k", "-p", "warning..alert", "--since", "-6 hours", "--no-pager", "-o", "cat"], 3)
    lines = [x for x in txt.splitlines() if x.strip()]
    hot = []
    pattern = re.compile(r"mmc|ext4|i/o error|under.?voltage|watchdog|panic|oom|out of memory|hung|lockup|brcm|wlan", re.I)
    for ln in lines:
        if pattern.search(ln): hot.append(ln[-260:])
    return hot[-20:]


def journal_disk():
    out = run(["journalctl", "--disk-usage"], 2)
    return out


def collect(include_previous=True):
    try: load = [float(x) for x in _read("/proc/loadavg", "0 0 0").split()[:3]]
    except Exception: load = [0,0,0]
    try: uptime = float(_read("/proc/uptime", "0").split()[0])
    except Exception: uptime = 0
    return {
        "hostname": socket.gethostname(), "boot_id": boot_id(), "boot_time": boot_time_epoch(),
        "uptime_s": uptime, "temperature_c": temp_c(), "load": load,
        "memory": memory(), "disk": disk("/"), "wifi": wifi(), "throttled": throttled(),
        "services": services(), "journal_disk": journal_disk(), "kernel_warnings": kernel_warnings(),
        "previous_boot": previous_boot() if include_previous else None,
    }


if __name__ == "__main__":
    print(json.dumps(collect(), indent=2))
