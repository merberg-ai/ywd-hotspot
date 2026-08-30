#!/usr/bin/env python3
"""Privileged TGIF configuration helper for the experimental dev-tgif branch.

The dashboard never receives or writes the stored TGIF password through the
ordinary public configuration document. This helper owns TGIF-specific secret
mutations and intercepts the normal config-save action so non-secret TGIF
settings participate in the same Settings transaction as the rest of YWD.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP = Path("/opt/ywd-hotspot/app")
LIB = APP / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import admin as core_admin
import config_model

MAX_INPUT = 131072
TGIF_BROWSER_KEYS = {"enabled", "master", "port"}
TGIF_SECRET_KEYS = {"password", "password_configured"}


def payload() -> dict:
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise ValueError("TGIF request is too large")
    if not raw:
        return {}
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("invalid JSON payload")
    if not isinstance(obj, dict):
        raise ValueError("payload must be an object")
    return obj


def _apply_and_reconcile() -> dict:
    """Apply canonical config without ever creating a partial RF stack."""
    rf_was_running = core_admin.active("ywd-mmdvmhost.service")
    out = core_admin.config_apply({})

    cfg = core_admin.current()
    any_network = bool(cfg.get("brandmeister", {}).get("enabled", True)) or bool(
        cfg.get("tgif", {}).get("enabled", False)
    )
    gateway_running = core_admin.active("ywd-dmrgateway.service")

    if rf_was_running and any_network and not gateway_running:
        core_admin.run(["systemctl", "start", "ywd-dmrgateway.service"], 15, check=True)
        out.setdefault("restarted", []).append("DMRGateway")
        out["dmr_network_reconciled"] = "started"
    elif (not any_network or not rf_was_running) and gateway_running:
        core_admin.run(["systemctl", "stop", "ywd-dmrgateway.service"], 15, check=False)
        out["dmr_network_reconciled"] = "stopped"

    return out


def config_save(data: dict) -> dict:
    """Merge browser TGIF fields into the ordinary Settings save transaction.

    The core merger remains authoritative for every pre-existing settings
    section. TGIF gets only enabled/master/port here; browser-visible secret
    placeholders are ignored so the stored TGIF credential is preserved.
    """
    incoming = data.get("config", data)
    if not isinstance(incoming, dict):
        raise ValueError("config must be an object")

    old, candidate = core_admin.merge_browser_config(data)
    tg_in = incoming.get("tgif")
    if tg_in is not None:
        if not isinstance(tg_in, dict):
            raise ValueError("tgif must be an object")
        for key, value in tg_in.items():
            if key in TGIF_SECRET_KEYS:
                continue
            if key not in TGIF_BROWSER_KEYS:
                raise ValueError(f"unsupported TGIF browser setting: {key}")
            candidate.setdefault("tgif", {})[key] = value

    new = config_model.normalize(candidate)
    changed = config_model.diff_paths(old, new)
    if not changed:
        return {
            "ok": True,
            "changed": [],
            "hints": config_model.classify_changes([]),
            "message": "No changes",
        }

    snap = core_admin.backup_config("pre-save", changed)
    core_admin.write_config(new)
    core_admin.audit("config-save", {"changed": changed, "snapshot": snap})
    return {
        "ok": True,
        "changed": changed,
        "hints": config_model.classify_changes(changed),
        "snapshot": snap,
    }


def configure(data: dict) -> dict:
    """Compatibility endpoint for older dev-tgif dashboard revisions."""
    old = core_admin.current()
    candidate = json.loads(json.dumps(old))
    tg = candidate.setdefault("tgif", {})

    if "enabled" in data:
        tg["enabled"] = bool(data.get("enabled"))
    if "master" in data:
        tg["master"] = str(data.get("master") or "").strip()
    if "port" in data:
        tg["port"] = data.get("port")

    new = config_model.normalize(candidate)
    changed = config_model.diff_paths(old, new)
    if not changed:
        return {
            "ok": True,
            "changed": [],
            "message": "No TGIF changes",
            "tgif": config_model.public(new).get("tgif", {}),
        }

    snap = core_admin.backup_config("pre-tgif-config", changed)
    core_admin.write_config(new)
    core_admin.audit("tgif-config-save", {
        "changed": changed,
        "snapshot": snap,
        "enabled": bool(new["tgif"].get("enabled")),
        "master": new["tgif"].get("master"),
        "port": new["tgif"].get("port"),
    })

    out = {
        "ok": True,
        "changed": changed,
        "snapshot": snap,
        "tgif": config_model.public(new).get("tgif", {}),
    }
    if data.get("apply", True):
        out["apply"] = _apply_and_reconcile()
    return out


def set_password(data: dict) -> dict:
    pw = str(data.get("password", ""))
    if not pw:
        raise ValueError("TGIF security password cannot be empty")

    old = core_admin.current()
    candidate = json.loads(json.dumps(old))
    candidate.setdefault("tgif", {})["password"] = pw
    new = config_model.normalize(candidate)
    changed = config_model.diff_paths(old, new)
    if not changed:
        return {"ok": True, "saved": True, "message": "TGIF password unchanged"}

    snap = core_admin.backup_config("pre-tgif-password", ["tgif.password"])
    core_admin.write_config(new)
    core_admin.audit("tgif-security-password-change", {"snapshot": snap})

    out = {"ok": True, "saved": True, "snapshot": snap}
    # Saving a credential while TGIF is disabled should not bounce a healthy BM
    # connection. Once TGIF is enabled, a credential change must reconnect.
    should_apply = bool(new["tgif"].get("enabled")) and bool(data.get("apply", True))
    if should_apply:
        out["apply"] = _apply_and_reconcile()
    return out


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("ywd-hotspot TGIF admin must run as root")
    if len(sys.argv) != 2:
        raise SystemExit("usage: tgif_admin.py ACTION")
    action = sys.argv[1]
    data = payload()
    if action == "config-save":
        out = config_save(data)
    elif action == "tgif-configure":
        out = configure(data)
    elif action == "set-tgif-password":
        out = set_password(data)
    else:
        raise ValueError("unsupported TGIF admin action")
    print(json.dumps(out, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:800]}, separators=(",", ":")))
        raise SystemExit(1)
