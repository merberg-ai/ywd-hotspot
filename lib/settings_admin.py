#!/usr/bin/env python3
"""Privileged portable settings export/preview/restore helper."""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

APP_LIB = Path("/opt/ywd-hotspot/app/lib")
if str(APP_LIB) not in sys.path:
    sys.path.insert(0, str(APP_LIB))

import admin as core_admin
import config_model
import plugin_admin_common
import plugin_admin_state
import plugin_catalog_overlay
import plugin_manager
import plugin_package_manager
import plugin_service_manager
import settings_backup

MAX_INPUT = 2100000
SETUP_STATE = core_admin.VAR / "setup-state.json"
BACKUP_ROOT = Path("/var/backups/ywd-hotspot")


def payload():
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise ValueError("settings request is too large")
    if not raw:
        return {}
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        raise ValueError("invalid JSON payload")
    if not isinstance(obj, dict):
        raise ValueError("payload must be an object")
    return obj


def _decode(data):
    raw = data.get("backup_b64")
    if not isinstance(raw, str) or len(raw) > 2000000:
        raise ValueError("settings backup payload is missing or too large")
    try:
        return base64.b64decode(raw, validate=True)
    except Exception:
        raise ValueError("settings backup payload is not valid base64")


def _atomic_text(path, text, mode=0o640, group=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".restore-tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, mode)
    if group:
        try:
            os.chown(tmp, 0, core_admin.gid())
        except Exception:
            pass
    os.replace(tmp, path)


def _snapshot():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = BACKUP_ROOT / f"pre-settings-restore-{stamp}"
    n = 1
    while root.exists():
        n += 1
        root = BACKUP_ROOT / f"pre-settings-restore-{stamp}-{n}"
    root.mkdir(parents=True, mode=0o700)
    os.chmod(BACKUP_ROOT, 0o700)
    os.chmod(root, 0o700)
    items = {
        "config": core_admin.CFG,
        "bm-api": core_admin.BMKEY,
        "web-auth": settings_backup.WEB_AUTH,
        "plugin-state": settings_backup.PLUGIN_STATE,
        "package-state": settings_backup.PACKAGE_STATE,
        "calibration-baseline": settings_backup.CAL_BASELINE,
        "setup-state": SETUP_STATE,
    }
    manifest = {"files": {}, "dirs": {}}
    for key, path in items.items():
        present = path.is_file()
        manifest["files"][key] = {"path": str(path), "present": present}
        if present:
            shutil.copy2(path, root / f"{key}.bak")
    for key, path in {"plugin-configs": settings_backup.PLUGIN_CONFIG_DIR, "plugin-trust": settings_backup.TRUST_DIR}.items():
        present = path.is_dir()
        manifest["dirs"][key] = {"path": str(path), "present": present}
        if present:
            shutil.copytree(path, root / key, symlinks=False)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.chmod(root / "manifest.json", 0o600)
    return root


def _rollback(root):
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for key, meta in manifest.get("files", {}).items():
        path = Path(meta["path"])
        if meta.get("present"):
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / f"{key}.bak", path)
        else:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
    for key, meta in manifest.get("dirs", {}).items():
        path = Path(meta["path"])
        if path.exists() or path.is_symlink():
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        if meta.get("present"):
            shutil.copytree(root / key, path, symlinks=False)
    try:
        core_admin.config_apply({})
    except Exception:
        pass


def _restore_wifi(wifi):
    if not isinstance(wifi, dict):
        return None
    ssid = str(wifi.get("ssid") or "")
    psk = str(wifi.get("psk") or "")
    if not ssid:
        return None
    name = "YWD Restored WiFi"
    subprocess.run(["nmcli", "connection", "delete", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
    p = subprocess.run(["nmcli", "connection", "add", "type", "wifi", "ifname", "wlan0", "con-name", name, "ssid", ssid], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15, check=False)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "could not create restored Wi-Fi profile").strip()[:600])
    args = ["nmcli", "connection", "modify", name, "connection.autoconnect", "yes"]
    if psk:
        args += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", psk]
    q = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15, check=False)
    if q.returncode != 0:
        raise RuntimeError((q.stderr or q.stdout or "could not configure restored Wi-Fi profile").strip()[:600])
    return {"profile": name, "ssid": ssid, "activated": False}


def _write_trust(keys):
    settings_backup.TRUST_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(settings_backup.TRUST_DIR, 0o750)
    for old in settings_backup.TRUST_DIR.glob("*.pem"):
        old.unlink()
    for key_id, pem in keys.items():
        _atomic_text(settings_backup.TRUST_DIR / f"{key_id}.pem", pem.rstrip() + "\n", 0o644, group=False)


def _available_map():
    plugin_catalog_overlay.install()
    result = {}
    for entry in list(plugin_manager.discover()) + list(plugin_service_manager.discover()):
        if entry.get("valid"):
            manifest = entry["manifest"]
            result[manifest["id"]] = manifest
    return result


def export_settings(data):
    passphrase = str(data.get("passphrase") or "")
    include_wifi = bool(data.get("include_wifi", False))
    doc = settings_backup.collect(include_wifi=include_wifi)
    encrypted = settings_backup.encrypt_payload(doc, passphrase)
    callsign = str(doc["config"]["station"].get("callsign") or "hotspot").upper()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"{callsign}-ywd-hotspot-{stamp}.ywdsettings"
    core_admin.audit("settings-export", {"include_wifi": include_wifi, "bytes": len(encrypted)})
    return {"ok": True, "filename": filename, "backup_b64": base64.b64encode(encrypted).decode("ascii"), "preview": settings_backup.preview(doc)}


def preview_settings(data):
    doc = settings_backup.decrypt_payload(_decode(data), str(data.get("passphrase") or ""))
    return {"ok": True, "preview": settings_backup.preview(doc)}


def restore_settings(data):
    doc = settings_backup.decrypt_payload(_decode(data), str(data.get("passphrase") or ""))
    start_rf = bool(data.get("start_rf", False))
    restore_wifi = bool(data.get("restore_wifi", False))
    first_boot = bool(data.get("first_boot", False))
    if first_boot and not doc["secrets"].get("web_auth"):
        raise ValueError("this backup has no WebUI control credential; use normal first-boot setup instead")

    previous_active = core_admin.active("ywd-mmdvmhost.service") or core_admin.active("ywd-dmrgateway.service")
    previous_enabled = core_admin.run(["systemctl", "is-enabled", "--quiet", "ywd-mmdvmhost.service"], 5).returncode == 0
    snap = _snapshot()
    warnings = []
    missing_plugins = []
    restored_plugins = []
    wifi_result = None
    try:
        core_admin.rf_action("rf-stop")
        plugin_catalog_overlay.install()
        try:
            plugin_admin_state.set_system({"enabled": False})
        except Exception as exc:
            warnings.append(f"plugin shutdown warning: {exc}")

        candidate = json.loads(json.dumps(doc["config"]))
        candidate.setdefault("maintenance", {})["rf_autostart"] = start_rf
        candidate = config_model.normalize(candidate)
        old = core_admin.current()
        changed = config_model.diff_paths(old, candidate)
        core_admin.write_config(candidate)

        api_key = doc["secrets"].get("bm_api_key") or ""
        if api_key:
            _atomic_text(core_admin.BMKEY, api_key + "\n", 0o640, group=True)
        else:
            try:
                core_admin.BMKEY.unlink()
            except FileNotFoundError:
                pass
        web_auth = doc["secrets"].get("web_auth")
        if web_auth:
            core_admin.atomic_json(settings_backup.WEB_AUTH, web_auth, mode=0o640, group=True)
        elif not first_boot:
            try:
                settings_backup.WEB_AUTH.unlink()
            except FileNotFoundError:
                pass

        baseline = doc.get("calibration_baseline")
        if baseline:
            core_admin.PRIVATE.mkdir(parents=True, exist_ok=True)
            os.chmod(core_admin.PRIVATE, 0o700)
            core_admin.atomic_json(settings_backup.CAL_BASELINE, baseline, mode=0o600, group=False)
            core_admin.atomic_json(core_admin.CAL_BASELINE_META, baseline, mode=0o640, group=True)

        _write_trust(doc["plugins"].get("trust_keys", {}))
        available = _available_map()
        settings_backup.PLUGIN_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        for ident, raw_cfg in doc["plugins"].get("configs", {}).items():
            clean = raw_cfg
            if ident in available:
                try:
                    clean = plugin_manager.normalize_config(available[ident], raw_cfg)
                except Exception as exc:
                    warnings.append(f"{ident} config preserved but did not validate: {exc}")
            else:
                missing_plugins.append(ident)
            plugin_admin_common.atomic_json(plugin_manager.config_path(ident), clean)

        backup_packages = doc["plugins"].get("packages") or {}
        installed_map = backup_packages.get("installed", {}) if isinstance(backup_packages, dict) and isinstance(backup_packages.get("installed"), dict) else {}
        desired_packages = {ident: bool(installed_map.get(ident, False)) for ident in available}
        plugin_admin_common.write_package_map(desired_packages)

        pstate = doc["plugins"].get("state") or {}
        desired_enabled = pstate.get("plugins", {}) if isinstance(pstate.get("plugins"), dict) else {}
        master = bool(pstate.get("enabled", False))
        if master:
            plugin_admin_state.set_system({"enabled": True})
            for ident, row in desired_enabled.items():
                if not isinstance(row, dict) or not row.get("enabled"):
                    continue
                if ident not in available or not desired_packages.get(ident):
                    if ident not in missing_plugins:
                        missing_plugins.append(ident)
                    continue
                try:
                    plugin_admin_state.set_plugin({"id": ident, "enabled": True})
                    restored_plugins.append(ident)
                except Exception as exc:
                    warnings.append(f"{ident} was not enabled: {exc}")

        applied = core_admin.config_apply({})
        if restore_wifi and doc.get("wifi"):
            try:
                wifi_result = _restore_wifi(doc["wifi"])
            except Exception as exc:
                warnings.append(f"Wi-Fi profile was not restored: {exc}")

        if first_boot:
            state = {
                "schema": 1,
                "state": "complete",
                "completed_at": core_admin.now_iso(),
                "config_hash": config_model.hash_config(candidate, include_secrets=False),
                "callsign": candidate["station"]["callsign"],
                "hotspot_id": candidate["station"]["hotspot_id"],
                "rf_requested": start_rf,
                "restored_from_backup": True,
            }
            core_admin.atomic_json(SETUP_STATE, state, mode=0o640, group=True)

        if start_rf:
            core_admin.run(["systemctl", "enable", "ywd-mmdvmhost.service", "ywd-dmrgateway.service"], 15, check=True)
            core_admin.rf_action("rf-start")
        else:
            core_admin.run(["systemctl", "disable", "ywd-dmrgateway.service", "ywd-mmdvmhost.service"], 15)

        core_admin.audit("settings-restore", {"snapshot": str(snap), "changed": changed, "start_rf": start_rf, "first_boot": first_boot, "missing_plugins": sorted(set(missing_plugins)), "warnings": warnings[:20]})
        return {
            "ok": True,
            "restored": True,
            "snapshot": str(snap),
            "changed": changed,
            "apply": applied,
            "start_rf": start_rf,
            "rf_active": core_admin.active("ywd-mmdvmhost.service"),
            "missing_plugins": sorted(set(missing_plugins)),
            "restored_plugins": sorted(set(restored_plugins)),
            "warnings": warnings,
            "wifi": wifi_result,
            "dashboard": f"http://ywd-hotspot.local:{candidate['web']['port']}/",
        }
    except Exception:
        try:
            plugin_admin_state.set_system({"enabled": False})
        except Exception:
            pass
        _rollback(snap)
        if previous_enabled:
            core_admin.run(["systemctl", "enable", "ywd-mmdvmhost.service", "ywd-dmrgateway.service"], 10)
        else:
            core_admin.run(["systemctl", "disable", "ywd-dmrgateway.service", "ywd-mmdvmhost.service"], 10)
        if previous_active:
            try:
                core_admin.rf_action("rf-start")
            except Exception:
                pass
        raise


def main():
    if os.geteuid() != 0:
        raise SystemExit("settings admin must run as root")
    if len(sys.argv) != 2:
        raise SystemExit("usage: settings_admin.py ACTION")
    action = sys.argv[1]
    data = payload()
    handlers = {
        "settings-export": export_settings,
        "settings-preview": preview_settings,
        "settings-import": restore_settings,
    }
    handler = handlers.get(action)
    if handler is None:
        raise ValueError("unsupported settings admin action")
    print(json.dumps(handler(data), separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:1200]}, separators=(",", ":")))
        raise SystemExit(1)
