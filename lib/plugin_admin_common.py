#!/usr/bin/env python3
"""Shared trusted helpers for YWD-Hotspot plugin administration."""
from __future__ import annotations

import fcntl
import grp
import json
import os
import subprocess
import sys
from pathlib import Path

APP_LIB = Path("/opt/ywd-hotspot/app/lib")
UPDATE_LOCK = Path("/run/ywd-hotspot-update.lock")
if str(APP_LIB) not in sys.path:
    sys.path.insert(0, str(APP_LIB))

import plugin_manager
import plugin_package_manager
import plugin_service_manager


def payload(max_bytes=65536):
    limit = max(1024, min(int(max_bytes), 2 * 1024 * 1024))
    raw = sys.stdin.buffer.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("plugin admin payload is too large")
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON payload") from exc
    if not isinstance(data, dict):
        raise ValueError("payload must be an object")
    return data


def ensure_update_not_running():
    """Refuse plugin mutations while the application updater owns state."""
    UPDATE_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with UPDATE_LOCK.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("YWD-Hotspot update is in progress; plugin controls are temporarily locked") from exc
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass


def ywd_gid():
    try:
        return grp.getgrnam("ywd-hotspot").gr_gid
    except Exception:
        return 0


def atomic_json(path, data, mode=0o640):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o750)
    try:
        os.chown(path.parent, 0, ywd_gid())
    except Exception:
        pass
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, mode)
    try:
        os.chown(tmp, 0, ywd_gid())
    except Exception:
        pass
    os.replace(tmp, path)


def run(args, timeout=25):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=timeout, check=False)


def run_systemctl(*args, timeout=25):
    p = run(["systemctl", *args], timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stdout or f"systemctl {' '.join(args)} failed").strip()[-700:])
    return (p.stdout or "").strip()


def all_entries():
    return list(plugin_manager.discover()) + list(plugin_service_manager.discover())


def available_ids():
    ids = set()
    for entry in all_entries():
        ident = str(entry.get("manifest", {}).get("id") or "")
        if entry.get("valid") and plugin_manager.ID_RE.fullmatch(ident):
            ids.add(ident)
    return ids


def resolve_available_plugin(ident):
    ident = str(ident or "")
    try:
        return plugin_manager.get_available_plugin(ident), "declarative"
    except plugin_manager.PluginError as declarative_error:
        try:
            return plugin_service_manager.get_available_plugin(ident), "service"
        except plugin_manager.PluginError:
            raise declarative_error


def resolve_plugin(ident):
    plugin, kind = resolve_available_plugin(ident)
    if not plugin_package_manager.is_installed(plugin["id"]):
        raise ValueError("plugin is not installed")
    return plugin, kind


def stop_plugin_service(plugin, disable=True):
    service = plugin.get("service")
    if not service:
        return
    action = ["disable", "--now", service] if disable else ["stop", service]
    run_systemctl(*action)


def requirement_failure(plugin):
    checks = plugin_package_manager.check_requirements(plugin)
    if checks["ok"]:
        return checks, None
    missing = []
    for section in ("dependencies", "hardware"):
        for item in checks[section]["items"]:
            if not item["ok"]:
                missing.append(item["label"])
    return checks, "missing requirements: " + ", ".join(missing)


def write_package_map(values):
    clean = {ident: bool(values.get(ident, False)) for ident in sorted(available_ids())}
    atomic_json(plugin_package_manager.PACKAGE_STATE, {"schema": 1, "installed": clean})
    return clean
