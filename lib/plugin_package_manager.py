#!/usr/bin/env python3
"""Trusted package-registration and requirement checks for YWD-Hotspot plugins.

Repository-bundled packages are *available* source. Installation is a separate
root-owned registration decision stored outside the canonical hotspot config.
This module never downloads packages, installs OS dependencies, or executes
plugin code.

MMDVM runtime requirements are declarative too. A plugin may require the YWD
Extended variant, extension API 2+, or a named runtime capability. Stock
Upstream remains fully supported, but incompatible plugins are refused cleanly.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

import mmdvm_runtime_state

PACKAGE_STATE = Path(os.environ.get("YWD_PLUGIN_PACKAGE_STATE", "/etc/ywd-hotspot/plugin-packages.json"))
DATA_DIR = Path(os.environ.get("YWD_PLUGIN_DATA_DIR", "/var/lib/ywd-hotspot/plugins"))
MMDVM_RUNTIME_STATE = Path(os.environ.get("YWD_MMDVM_RUNTIME_STATE", "/etc/ywd-hotspot/mmdvm-runtime.json"))
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")

ALLOWED_DEPENDENCIES = frozenset({
    "python3", "systemd", "journalctl", "mmdvm-host", "mosquitto-broker", "mosquitto-client",
    "mmdvm-ywd-extended", "mmdvm-extension-api-2", "mmdvm-cap-passive-dmr-voice",
    "mmdvm-cap-demand-gated-dmr-voice",
})
ALLOWED_HARDWARE = frozenset({"mmdvm-serial", "oled-i2c"})

DEPENDENCY_LABELS = {
    "python3": "Python 3 runtime",
    "systemd": "systemd service manager",
    "journalctl": "systemd journal tools",
    "mmdvm-host": "MMDVM-Host binary",
    "mosquitto-broker": "Mosquitto MQTT broker",
    "mosquitto-client": "Mosquitto subscriber client",
    "mmdvm-ywd-extended": "YWD Extended MMDVM runtime",
    "mmdvm-extension-api-2": "YWD MMDVM extension API 2 or newer",
    "mmdvm-cap-passive-dmr-voice": "passive DMR voice MMDVM capability",
    "mmdvm-cap-demand-gated-dmr-voice": "demand-gated DMR voice MMDVM capability",
}
HARDWARE_LABELS = {
    "mmdvm-serial": "MMDVM modem serial path",
    "oled-i2c": "I2C bus 1",
}


class PackageStateError(ValueError):
    pass


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def _valid_id(value):
    return bool(ID_RE.fullmatch(str(value or "")))


def read_state():
    if not PACKAGE_STATE.exists():
        return {"schema":1,"valid":True,"source":"default","installed":{},"error":None}
    raw = _read_json(PACKAGE_STATE)
    if not isinstance(raw, dict) or raw.get("schema") != 1 or not isinstance(raw.get("installed"), dict):
        return {"schema":1,"valid":False,"source":"invalid","installed":{},"error":"plugin package state is invalid; all packages are treated as uninstalled"}
    clean = {}
    for ident, installed in raw["installed"].items():
        if _valid_id(ident) and isinstance(installed, bool): clean[str(ident)] = installed
    return {"schema":1,"valid":True,"source":"file","installed":clean,"error":None}


def package_map(available_ids):
    state = read_state()
    return {str(ident): bool(state["installed"].get(str(ident), False)) for ident in sorted(set(str(x) for x in available_ids if _valid_id(x)))}


def is_installed(ident):
    ident = str(ident or "")
    return bool(_valid_id(ident) and read_state()["installed"].get(ident, False))


def data_path(ident):
    ident = str(ident or "")
    if not _valid_id(ident): raise PackageStateError("invalid plugin id")
    return DATA_DIR / ident


def validate_requirements(dependencies, hardware):
    dependencies = [] if dependencies is None else dependencies
    hardware = [] if hardware is None else hardware
    if not isinstance(dependencies, list) or len(dependencies) > 16:
        raise PackageStateError("plugin dependencies must be a list of at most 16 requirement IDs")
    if not isinstance(hardware, list) or len(hardware) > 16:
        raise PackageStateError("plugin hardware requirements must be a list of at most 16 requirement IDs")
    deps = []
    for item in dependencies:
        token = str(item or "")
        if token not in ALLOWED_DEPENDENCIES: raise PackageStateError(f"unsupported plugin dependency requirement: {token or '?'}")
        if token not in deps: deps.append(token)
    hw = []
    for item in hardware:
        token = str(item or "")
        if token not in ALLOWED_HARDWARE: raise PackageStateError(f"unsupported plugin hardware requirement: {token or '?'}")
        if token not in hw: hw.append(token)
    return deps, hw


def _mmdvm_runtime():
    raw = _read_json(MMDVM_RUNTIME_STATE)
    if not isinstance(raw, dict):
        return {"variant": "unknown", "extension_api": None, "capabilities": [], "patch_sha256": None}
    variant = str(raw.get("variant") or "unknown").strip().lower()
    try:
        extension_api = int(raw.get("extension_api")) if raw.get("extension_api") is not None else None
    except Exception:
        extension_api = None
    caps = raw.get("capabilities")
    if not isinstance(caps, list):
        caps = []
    caps = [str(x) for x in caps]
    patch_sha = str(raw.get("patch_sha256") or "").lower() or None

    # Older runtime_build.py revisions wrote the exact current patch identity
    # before they learned to persist the new demand-gated capability token.
    # The state file is root-owned and already trusted for the other capability
    # checks, so normalize that one known omission cheaply for UI snapshots.
    # Privileged install/enable/start operations still perform exact live
    # binary/marker verification through mmdvm_runtime_state.observed_runtime().
    try:
        expected_patch = str(mmdvm_runtime_state._pins().get("MMDVM_YWD_PATCH_SHA256") or "").lower()
    except Exception:
        expected_patch = ""
    if (
        variant == "ywd-extended"
        and patch_sha
        and patch_sha == expected_patch
        and "demand-gated-dmr-voice" not in caps
    ):
        caps.append("demand-gated-dmr-voice")

    return {
        "variant": variant,
        "extension_api": extension_api,
        "capabilities": caps,
        "patch_sha256": patch_sha,
    }


def _dependency_result(token, verify_runtime=False):
    if token == "python3":
        path = shutil.which("python3"); return bool(path), path or "python3 not found in PATH"
    if token == "systemd":
        path = shutil.which("systemctl"); runtime = Path("/run/systemd/system").is_dir(); ok = bool(path and runtime)
        return ok, path if ok else "systemctl or active systemd runtime is missing"
    if token == "journalctl":
        path = shutil.which("journalctl"); return bool(path), path or "journalctl not found in PATH"
    if token == "mmdvm-host":
        path = Path("/usr/local/bin/MMDVM-Host"); ok = path.is_file() and os.access(path, os.X_OK)
        return ok, str(path) if ok else "MMDVM-Host is not installed at /usr/local/bin/MMDVM-Host"
    if token == "mosquitto-broker":
        path = shutil.which("mosquitto"); return bool(path), path or "mosquitto broker is not installed"
    if token == "mosquitto-client":
        path = shutil.which("mosquitto_sub"); return bool(path), path or "mosquitto_sub is not installed"
    if token == "mmdvm-ywd-extended":
        state = _mmdvm_runtime(); ok = state["variant"] == "ywd-extended"
        return ok, f"current MMDVM runtime variant: {state['variant']}"
    if token == "mmdvm-extension-api-2":
        state = _mmdvm_runtime(); api = state["extension_api"]; ok = bool(api is not None and api >= 2)
        return ok, f"current YWD MMDVM extension API: {api if api is not None else 'unavailable'}"
    if token == "mmdvm-cap-passive-dmr-voice":
        state = _mmdvm_runtime(); ok = "passive-dmr-voice" in state["capabilities"]
        return ok, "available" if ok else f"capability unavailable on MMDVM runtime {state['variant']}"
    if token == "mmdvm-cap-demand-gated-dmr-voice":
        # Ordinary UI snapshots use the already-selected/persisted runtime
        # identity. Expensive exact binary/patch verification is reserved for
        # privileged lifecycle actions where compatibility is being changed.
        state = mmdvm_runtime_state.observed_runtime() if verify_runtime else _mmdvm_runtime()
        ok = "demand-gated-dmr-voice" in state.get("capabilities", [])
        if ok:
            return True, "available"
        if verify_runtime and state.get("upgrade_required"):
            release = str(state.get("legacy_release") or "legacy YWD Extended")
            command = str(state.get("upgrade_command") or mmdvm_runtime_state.RUNTIME_REFRESH_COMMAND)
            return False, f"{release} runtime recognized; explicit YWD Extended refresh required: {command}"
        mode = "verified" if verify_runtime else "selected"
        return False, f"capability unavailable on {mode} MMDVM runtime {state.get('variant', 'unknown')}"
    return False, "unsupported dependency"


def _hardware_result(token):
    if token == "mmdvm-serial":
        path = Path("/dev/serial0"); return path.exists(), str(path) if path.exists() else "/dev/serial0 is unavailable"
    if token == "oled-i2c":
        path = Path("/dev/i2c-1"); return path.exists(), str(path) if path.exists() else "/dev/i2c-1 is unavailable"
    return False, "unsupported hardware requirement"


def _section(tokens, labels, checker):
    items = []
    for token in tokens:
        ok, detail = checker(token)
        items.append({"id":token,"label":labels.get(token,token),"ok":bool(ok),"status":"pass" if ok else "missing","detail":str(detail)[:240]})
    return {"ok": all(item["ok"] for item in items), "items": items}


def check_requirements(manifest, verify_runtime=False):
    deps, hw = validate_requirements(manifest.get("dependencies", []), manifest.get("hardware", []))
    dependencies = _section(
        deps,
        DEPENDENCY_LABELS,
        lambda token: _dependency_result(token, verify_runtime=verify_runtime),
    )
    hardware = _section(hw, HARDWARE_LABELS, _hardware_result)
    return {"ok": dependencies["ok"] and hardware["ok"], "dependencies": dependencies, "hardware": hardware}


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "require-installed":
        ident = str(sys.argv[2] or "")
        if not _valid_id(ident): raise SystemExit(2)
        raise SystemExit(0 if is_installed(ident) else 1)
    raise SystemExit("usage: plugin_package_manager.py require-installed PLUGIN_ID")


if __name__ == "__main__": main()
