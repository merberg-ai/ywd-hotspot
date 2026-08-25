#!/usr/bin/env python3
"""Read-only MMDVM HAT and MMDVM-Host runtime inventory for the System UI.

This module never opens the modem UART, rebuilds MMDVM-Host, writes runtime
markers, or restarts RF. Hardware identity is learned passively from the
existing MMDVMHost journal/activity state while host-runtime identity comes
from the same exact classifier used by plugin compatibility checks.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path

import config_model
import mmdvm_runtime_state

APP = Path(os.environ.get("YWD_APP", "/opt/ywd-hotspot/app"))
CFG = Path(os.environ.get("YWD_CONFIG", "/etc/ywd-hotspot/config.json"))
BUILD_PROVENANCE = Path(os.environ.get("YWD_MMDVM_BUILD_PROVENANCE", "/etc/ywd-hotspot/mmdvm-build.json"))
ACTIVITY = Path(os.environ.get("YWD_ACTIVITY_STATE", "/run/ywd-hotspot/activity.json"))
SOURCE = Path(os.environ.get("YWD_MMDVM_SOURCE", "/opt/ywd-hotspot/src/MMDVM-Host"))
BINARY = Path(os.environ.get("YWD_MMDVM_BINARY", "/usr/local/bin/MMDVM-Host"))
CACHE_ROOT = Path(os.environ.get("YWD_RUNTIME_BUILD_CACHE", "/var/cache/ywd-hotspot/runtime-build"))

PROTOCOL_RE = re.compile(r"MMDVM protocol version:\s*(?P<protocol>[^,]+),\s*description:\s*(?P<description>.+)$", re.I)
INTEREST_RE = re.compile(
    r"(?i)(?:MMDVM protocol version|description:|opening modem|opened modem|modem.*(?:firmware|version|revision|serial))"
)


def _run(args, timeout=4):
    try:
        return subprocess.run(
            [str(x) for x in args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return subprocess.CompletedProcess(args, 125, stdout="", stderr=str(exc))


def _json(path: Path, default=None):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else default
    except Exception:
        return default


def _sha256(path: Path):
    if not path.is_file():
        return None
    h = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _pins():
    out = {}
    try:
        for raw in (APP / "pins.env").read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


def _config():
    try:
        return config_model.normalize(json.loads(CFG.read_text(encoding="utf-8")))
    except Exception:
        return {}


def _serial(path_text: str):
    path = Path(path_text or "/dev/serial0")
    out = {"configured": str(path), "exists": path.exists() or path.is_symlink(), "resolved": None}
    try:
        out["resolved"] = str(path.resolve(strict=False))
    except Exception:
        pass
    try:
        st = path.stat()
        out.update({"mode": oct(st.st_mode & 0o7777), "uid": st.st_uid, "gid": st.st_gid})
    except Exception:
        pass
    return out


def _service():
    keys = ["LoadState", "ActiveState", "SubState", "UnitFileState", "MainPID", "NRestarts", "Result", "ExecMainStatus"]
    p = _run(["systemctl", "show", "ywd-mmdvmhost.service", *[f"--property={k}" for k in keys]], 4)
    doc = {}
    for line in (p.stdout or "").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            doc[key] = value
    for key in ("MainPID", "NRestarts", "ExecMainStatus"):
        try:
            doc[key] = int(doc.get(key) or 0)
        except Exception:
            pass
    return doc


def _journal_identity():
    p = _run(
        ["journalctl", "-u", "ywd-mmdvmhost.service", "-b", "0", "-n", "500", "--no-pager", "-o", "cat"],
        6,
    )
    lines = []
    protocol = None
    description = None
    for raw in (p.stdout or "").splitlines():
        line = raw.strip()
        m = PROTOCOL_RE.search(line)
        if m:
            protocol = m.group("protocol").strip()[:80]
            description = m.group("description").strip()[:300]
        if INTEREST_RE.search(line) and line not in lines:
            lines.append(line[-500:])
        if len(lines) >= 24:
            break
    activity = _json(ACTIVITY, {}) or {}
    activity_modem = activity.get("modem") if isinstance(activity.get("modem"), dict) else {}
    if not description:
        description = str(activity_modem.get("description") or "").strip()[:300] or None
    return {
        "protocol": protocol,
        "description": description,
        "activity_seen_at": activity_modem.get("seen_at"),
        "journal_lines": lines,
        "journal_readable": p.returncode == 0,
    }


def _binary():
    out = {"path": str(BINARY), "exists": BINARY.is_file(), "sha256": _sha256(BINARY)}
    try:
        st = BINARY.stat()
        out.update({"size": st.st_size, "mtime": st.st_mtime, "mode": oct(st.st_mode & 0o7777)})
    except Exception:
        pass
    if shutil.which("file") and BINARY.is_file():
        p = _run(["file", "-b", str(BINARY)], 4)
        out["format"] = (p.stdout or "").strip()[:500] or None
    return out


def _source():
    out = {"path": str(SOURCE), "present": (SOURCE / ".git").is_dir(), "head": None, "dirty": None}
    if not out["present"]:
        return out
    p = _run(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], 4)
    if p.returncode == 0:
        out["head"] = (p.stdout or "").strip()
    p = _run(["git", "-C", str(SOURCE), "status", "--porcelain"], 4)
    if p.returncode == 0:
        rows = [x for x in (p.stdout or "").splitlines() if x.strip()]
        out["dirty"] = bool(rows)
        out["changed_files"] = len(rows)
    return out


def _cache():
    rows = []
    for namespace in ("mmdvm-host", "mmdvm-host-upstream"):
        root = CACHE_ROOT / namespace
        entries = 0
        newest = None
        if root.is_dir():
            try:
                for item in root.iterdir():
                    if not item.is_dir():
                        continue
                    entries += 1
                    try:
                        mtime = item.stat().st_mtime
                        newest = mtime if newest is None else max(newest, mtime)
                    except Exception:
                        pass
            except Exception:
                pass
        rows.append({"namespace": namespace, "entries": entries, "newest_mtime": newest})
    return {"root": str(CACHE_ROOT), "namespaces": rows}


def _tools():
    result = {}
    for name in ("git", "make", "g++"):
        path = shutil.which(name)
        row = {"available": bool(path), "path": path}
        if path:
            p = _run([path, "--version"], 3)
            row["version"] = ((p.stdout or "").splitlines() or [""])[0][:300]
        result[name] = row
    return result


def snapshot():
    cfg = _config()
    radio = cfg.get("radio") if isinstance(cfg.get("radio"), dict) else {}
    pins = _pins()
    try:
        runtime = mmdvm_runtime_state.status()
    except Exception as exc:
        runtime = {"observed": {"variant": "unknown", "error": str(exc)[:500]}, "persisted": {}, "in_sync": False}
    provenance = _json(BUILD_PROVENANCE, {}) or {}
    binary = _binary()
    observed = runtime.get("observed") if isinstance(runtime.get("observed"), dict) else {}
    persisted = runtime.get("persisted") if isinstance(runtime.get("persisted"), dict) else {}

    return {
        "ok": True,
        "schema": 1,
        "collected_at": time.time(),
        "hat": _journal_identity(),
        "serial": _serial(str(radio.get("uart") or "/dev/serial0")),
        "configuration": {
            "rf_mode": radio.get("mode"),
            "uart_speed": radio.get("uart_speed"),
            "tx_invert": radio.get("tx_invert"),
            "rx_invert": radio.get("rx_invert"),
            "color_code": radio.get("color_code"),
        },
        "service": _service(),
        "runtime": {
            "variant": observed.get("variant", "unknown"),
            "installed": observed.get("installed", False),
            "runtime_generation": observed.get("runtime_generation", "unknown"),
            "extension_api": observed.get("extension_api"),
            "upstream_commit": observed.get("upstream_commit"),
            "patch_sha256": observed.get("patch_sha256"),
            "binary_sha256": observed.get("binary_sha256") or binary.get("sha256"),
            "capabilities": observed.get("capabilities") or [],
            "marker_status": observed.get("marker_status"),
            "in_sync": bool(runtime.get("in_sync")),
            "upgrade_required": bool(runtime.get("upgrade_required") or observed.get("upgrade_required")),
            "upgrade_reason": observed.get("upgrade_reason"),
            "legacy_release": observed.get("legacy_release"),
            "persisted_generation": persisted.get("runtime_generation"),
            "persisted_selected_at": persisted.get("selected_at"),
        },
        "binary": binary,
        "build": {
            "provenance": provenance,
            "pins": {
                "repository": pins.get("MMDVM_HOST_REPO"),
                "upstream_commit": pins.get("MMDVM_HOST_COMMIT"),
                "patch_api": pins.get("MMDVM_YWD_PATCH_API"),
                "patch_sha256": pins.get("MMDVM_YWD_PATCH_SHA256"),
                "patch": pins.get("MMDVM_YWD_PATCH"),
            },
            "source": _source(),
            "cache": _cache(),
            "tools": _tools(),
            "architecture": platform.machine() or "unknown",
        },
        "maintenance": {
            "host_runtime_refresh_supported": True,
            "host_runtime_build_ui_enabled": False,
            "hat_firmware_update_ui_enabled": False,
            "note": "Read-only inventory in RC3 UI polish; build/install and HAT firmware actions are intentionally not exposed yet.",
        },
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2, sort_keys=True))
