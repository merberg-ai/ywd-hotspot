#!/usr/bin/env python3
"""Reconcile trusted core feature runtimes demanded by enabled plugins.

Plugins declare capabilities; they never control core services directly.  This
module translates the aggregate enabled+installed plugin capability set into the
minimum trusted runtime required by the appliance.

For ``read:dmr-voice`` the contract is deliberately demand-gated:

* no demanding plugin -> voice bridge disabled, MMDVM voice env absent
* one or more demanding plugins -> voice bridge enabled, MMDVM voice env on

MMDVM-Host caches the environment gate at process start, so a guarded RF restart
is performed only when the running gate differs from the desired gate.  Merely
canonicalizing the env file or service boot state does not bounce RF.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import plugin_manager
import plugin_package_manager
import plugin_service_manager
import plugin_ui_manager

VOICE_CAPABILITY = "read:dmr-voice"
VOICE_ENV = Path("/etc/ywd-hotspot/mmdvm-voice.env")
VOICE_ENV_TEXT = "YWD_DMR_VOICE_TAP=1\n"
VOICE_SERVICE = "ywd-mmdvm-voice.service"
MMDVM_SERVICE = "ywd-mmdvmhost.service"
GATEWAY_SERVICE = "ywd-dmrgateway.service"


def _run(args, *, check=True, timeout=35):
    p = subprocess.run(
        [str(x) for x in args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    if check and p.returncode != 0:
        detail = (p.stdout or "").strip()[-900:]
        raise RuntimeError(detail or f"command failed: {' '.join(str(x) for x in args)}")
    return p


def _systemctl(*args, check=True, timeout=35):
    return _run(["systemctl", *args], check=check, timeout=timeout)


def _active(unit: str) -> bool:
    return _systemctl("is-active", "--quiet", unit, check=False).returncode == 0


def _enabled(unit: str) -> bool:
    return _systemctl("is-enabled", "--quiet", unit, check=False).returncode == 0


def _all_entries():
    return (
        list(plugin_manager.discover())
        + list(plugin_service_manager.discover())
        + list(plugin_ui_manager.discover())
    )


def demanding_plugins(capability: str = VOICE_CAPABILITY) -> list[str]:
    """Return enabled+installed valid plugin IDs demanding ``capability``."""
    state = plugin_manager.read_state()
    if not bool(state.get("enabled", False)):
        return []

    desired = state.get("plugins", {})
    found = set()
    for entry in _all_entries():
        if not entry.get("valid"):
            continue
        manifest = entry.get("manifest") or {}
        ident = str(manifest.get("id") or "")
        if not ident or not plugin_package_manager.is_installed(ident):
            continue
        if not bool((desired.get(ident) or {}).get("enabled", False)):
            continue
        capabilities = manifest.get("capabilities") or []
        if isinstance(capabilities, list) and capability in capabilities:
            found.add(ident)
    return sorted(found)


def _env_file_enabled() -> bool:
    try:
        return VOICE_ENV.read_text(encoding="utf-8") == VOICE_ENV_TEXT
    except Exception:
        return False


def _write_gate(enabled: bool) -> None:
    VOICE_ENV.parent.mkdir(parents=True, exist_ok=True)
    if enabled:
        if _env_file_enabled():
            return
        tmp = VOICE_ENV.with_name(VOICE_ENV.name + ".tmp")
        tmp.write_text(VOICE_ENV_TEXT, encoding="utf-8")
        os.chmod(tmp, 0o644)
        try:
            os.chown(tmp, 0, 0)
        except Exception:
            pass
        os.replace(tmp, VOICE_ENV)
    else:
        try:
            VOICE_ENV.unlink()
        except FileNotFoundError:
            pass


def _main_pid() -> int:
    p = _systemctl("show", "-p", "MainPID", "--value", MMDVM_SERVICE, check=False)
    try:
        return int((p.stdout or "0").strip())
    except Exception:
        return 0


def running_voice_gate() -> bool:
    """Read the gate actually inherited by the live MMDVM-Host process."""
    pid = _main_pid()
    if pid <= 0:
        return False
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except Exception:
        return False
    return b"YWD_DMR_VOICE_TAP=1" in raw.split(b"\0")


def _guarded_mmdvm_restart(expected_gate: bool) -> bool:
    """Restart MMDVM while preserving the pre-existing Gateway runtime policy."""
    if not _active(MMDVM_SERVICE):
        return False

    gateway_was_active = _active(GATEWAY_SERVICE)
    if gateway_was_active:
        _systemctl("stop", GATEWAY_SERVICE, check=False)

    _systemctl("restart", MMDVM_SERVICE, check=False)
    time.sleep(3)
    if not _active(MMDVM_SERVICE):
        # One explicit recovery attempt.  It reads the now-canonical gate file.
        _systemctl("start", MMDVM_SERVICE, check=False)
        time.sleep(3)

    mmdvm_ok = _active(MMDVM_SERVICE)
    if gateway_was_active and mmdvm_ok:
        _systemctl("start", GATEWAY_SERVICE, check=False)
        time.sleep(2)

    if not mmdvm_ok:
        raise RuntimeError("MMDVM-Host did not recover during plugin feature reconciliation")
    if running_voice_gate() != expected_gate:
        raise RuntimeError("MMDVM-Host restarted but inherited the wrong DMR voice gate state")
    if gateway_was_active and not _active(GATEWAY_SERVICE):
        raise RuntimeError("DMRGateway did not return active after plugin feature reconciliation")
    return True


def _snapshot(demand=None) -> dict:
    """Read one runtime snapshot without repeating identical systemd queries."""
    if demand is None:
        demand = demanding_plugins()
    mmdvm_active = _active(MMDVM_SERVICE)
    running_gate = running_voice_gate() if mmdvm_active else False
    return {
        "capability": VOICE_CAPABILITY,
        "demanded_by": list(demand),
        "desired": bool(demand),
        "env_file": str(VOICE_ENV),
        "env_enabled": _env_file_enabled(),
        "running_gate": running_gate,
        "bridge_enabled": _enabled(VOICE_SERVICE),
        "bridge_active": _active(VOICE_SERVICE),
        "mmdvm_active": mmdvm_active,
        "gateway_active": _active(GATEWAY_SERVICE),
    }


def status() -> dict:
    return _snapshot()


def reconcile() -> dict:
    if os.geteuid() != 0:
        raise RuntimeError("plugin feature reconciliation must run as root")

    demand = demanding_plugins()
    desired = bool(demand)
    mmdvm_was_active = _active(MMDVM_SERVICE)
    running_before = running_voice_gate() if mmdvm_was_active else False
    env_before = _env_file_enabled()
    bridge_before = {"enabled": _enabled(VOICE_SERVICE), "active": _active(VOICE_SERVICE)}
    previous = {
        "env_enabled": env_before,
        "running_gate": running_before,
        "bridge_enabled": bridge_before["enabled"],
        "bridge_active": bridge_before["active"],
    }

    # UI-only plugin package updates are common and do not change systemd unit
    # files.  On a Pi Zero, systemctl daemon-reload can take well over ten
    # seconds, so never do it as part of a per-request capability reconcile.
    # Unit-file installation/update paths are responsible for daemon-reload.
    #
    # More importantly, if the trusted runtime is already exactly converged,
    # return immediately.  This keeps same-capability plugin updates cheap and
    # prevents a successful state mutation from outliving the dashboard's HTTP
    # request timeout merely because systemd queries are slow on small SBCs.
    converged = (
        env_before == desired
        and bridge_before["enabled"] == desired
        and bridge_before["active"] == desired
        and (not mmdvm_was_active or running_before == desired)
    )
    if converged:
        result = {
            "capability": VOICE_CAPABILITY,
            "demanded_by": demand,
            "desired": desired,
            "env_file": str(VOICE_ENV),
            "env_enabled": env_before,
            "running_gate": running_before,
            "bridge_enabled": bridge_before["enabled"],
            "bridge_active": bridge_before["active"],
            "mmdvm_active": mmdvm_was_active,
            "gateway_active": _active(GATEWAY_SERVICE),
            "ok": True,
            "rf_restarted": False,
            "reconcile_noop": True,
            "previous": previous,
        }
        return result

    if desired:
        # Persist the gate first, but do not bounce RF unless the running process
        # actually needs a state transition.  If bridge startup fails while the
        # old live gate was off, remove the new env file so an unrelated later
        # MMDVM restart cannot unexpectedly publish high-rate voice frames.
        _write_gate(True)
        try:
            if not bridge_before["enabled"] or not bridge_before["active"]:
                _systemctl("enable", "--now", VOICE_SERVICE)
            if not _active(VOICE_SERVICE):
                raise RuntimeError("trusted DMR voice bridge is not active")
        except Exception:
            if not running_before and not env_before:
                _write_gate(False)
            raise
    else:
        # Stop high-rate userspace work before changing/restarting MMDVM.  Skip
        # the systemctl mutation entirely when the bridge is already down.
        if bridge_before["enabled"] or bridge_before["active"]:
            _systemctl("disable", "--now", VOICE_SERVICE)
        if _active(VOICE_SERVICE):
            raise RuntimeError("trusted DMR voice bridge remained active after disable")
        _write_gate(False)

    restarted = False
    if mmdvm_was_active and running_before != desired:
        restarted = _guarded_mmdvm_restart(desired)

    result = _snapshot(demand)
    result.update({
        "ok": True,
        "rf_restarted": restarted,
        "reconcile_noop": False,
        "previous": previous,
    })

    if result["desired"]:
        if not result["env_enabled"] or not result["bridge_enabled"] or not result["bridge_active"]:
            raise RuntimeError("DMR voice feature runtime did not converge to enabled state")
        if result["mmdvm_active"] and not result["running_gate"]:
            raise RuntimeError("live MMDVM-Host voice gate did not converge to enabled state")
    else:
        if result["env_enabled"] or result["bridge_enabled"] or result["bridge_active"]:
            raise RuntimeError("DMR voice feature runtime did not converge to disabled state")
        if result["mmdvm_active"] and result["running_gate"]:
            raise RuntimeError("live MMDVM-Host voice gate did not converge to disabled state")

    return result


def main() -> int:
    command = sys.argv[1] if len(sys.argv) == 2 else "status"
    if command not in {"status", "reconcile"}:
        raise SystemExit("usage: plugin_feature_runtime.py [status|reconcile]")
    doc = reconcile() if command == "reconcile" else status()
    print(json.dumps(doc, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] plugin feature runtime: {exc}", file=sys.stderr)
        raise SystemExit(1)
