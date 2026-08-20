#!/usr/bin/env python3
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import secrets
import shlex
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
LOCAL = ROOT / "os" / "local"
PROFILE_PATH = LOCAL / "builder-profile.json"
GENERATED = LOCAL / "generated"

if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import config_model
import settings_backup


def default_profile() -> dict[str, Any]:
    cfg = config_model.defaults()
    cfg["station"]["callsign"] = ""
    cfg["station"]["base_dmr_id"] = ""
    cfg["station"]["hotspot_id"] = 0
    cfg["brandmeister"]["password"] = ""
    return {
        "schema": 1,
        "image": {
            "image_name": "ywd-hotspot-os",
            "os_version": "M5-builder-dev",
        },
        "wifi": {
            "ssid": "",
            "password": "",
            "hidden": False,
        },
        "credentials": {
            "dashboard_password": "",
            "hotspot_password": "",
            "bm_api_key": "",
        },
        "config": cfg,
        "imported_backup": None,
    }


def deep_merge(base: Any, incoming: Any) -> Any:
    if isinstance(base, dict) and isinstance(incoming, dict):
        out = copy.deepcopy(base)
        for key, value in incoming.items():
            out[key] = deep_merge(out[key], value) if key in out else copy.deepcopy(value)
        return out
    return copy.deepcopy(incoming)


def load_profile(path: Path = PROFILE_PATH) -> dict[str, Any]:
    if not path.exists():
        return default_profile()
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError("builder profile must be a JSON object")
    return deep_merge(default_profile(), raw)


def atomic_write(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def save_profile(profile: dict[str, Any], path: Path = PROFILE_PATH) -> None:
    atomic_write(path, json.dumps(profile, indent=2) + "\n", 0o600)


def _valid_web_auth(record: Any) -> bool:
    return (
        isinstance(record, dict)
        and record.get("scheme") == "scrypt"
        and all(k in record for k in ("salt", "hash", "n", "r", "p"))
    )


def _make_web_auth(password: str) -> dict[str, Any]:
    if not 8 <= len(password) <= 256:
        raise ValueError("dashboard password must be 8-256 characters")
    n = 1 << 14
    r = 8
    p = 1
    dklen = 32
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen)
    return {
        "scheme": "scrypt",
        "n": n,
        "r": r,
        "p": p,
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
    }


def imported_payload(profile: dict[str, Any]) -> dict[str, Any] | None:
    info = profile.get("imported_backup")
    if not isinstance(info, dict):
        return None
    payload = info.get("payload")
    if not isinstance(payload, dict):
        return None
    return settings_backup.validate_payload(payload)


def import_dashboard_backup(
    backup_path: Path,
    passphrase: str,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    backup_path = backup_path.expanduser().resolve()
    blob = backup_path.read_bytes()
    doc = settings_backup.decrypt_payload(blob, passphrase)

    out = copy.deepcopy(profile if profile is not None else load_profile())
    out["config"] = copy.deepcopy(doc["config"])

    hotspot_password = str(out["config"].setdefault("brandmeister", {}).get("password") or "")
    out["config"]["brandmeister"]["password"] = ""

    creds = out.setdefault("credentials", {})
    creds["dashboard_password"] = ""
    creds["hotspot_password"] = hotspot_password
    creds["bm_api_key"] = str(doc.get("secrets", {}).get("bm_api_key") or "")

    wifi = doc.get("wifi")
    if isinstance(wifi, dict) and wifi.get("ssid"):
        out["wifi"] = {
            "ssid": str(wifi.get("ssid") or ""),
            "password": str(wifi.get("psk") or ""),
            "hidden": False,
        }

    out["imported_backup"] = {
        "source_file": backup_path.name,
        "payload": doc,
    }

    compile_profile(out)
    save_profile(out)
    return out


def compile_profile(profile: dict[str, Any]) -> dict[str, Any]:
    defaults = config_model.defaults()
    raw_cfg = deep_merge(defaults, profile.get("config") or {})

    st = raw_cfg.setdefault("station", {})
    st["callsign"] = str(st.get("callsign") or "").strip().upper() or "NOCALL"
    st["base_dmr_id"] = str(st.get("base_dmr_id") or "").strip() or "00000"
    st["essid"] = str(st.get("essid") if st.get("essid") is not None else "01").strip()

    creds = profile.get("credentials") or {}
    hotspot_password = str(creds.get("hotspot_password") or "")
    dashboard_password = str(creds.get("dashboard_password") or "")
    bm_api_key = str(creds.get("bm_api_key") or "").strip()
    raw_cfg.setdefault("brandmeister", {})["password"] = ""

    canonical = config_model.normalize(raw_cfg)
    imported = imported_payload(profile)
    imported_web_auth = imported.get("secrets", {}).get("web_auth") if imported else None

    real_identity = canonical["station"]["callsign"] != "NOCALL" and canonical["station"]["base_dmr_id"] != "00000"
    web_ready = 8 <= len(dashboard_password) <= 256 or _valid_web_auth(imported_web_auth)
    bm_enabled = bool(canonical["brandmeister"].get("enabled", True))
    bm_ready = (not bm_enabled) or bool(hotspot_password)
    complete = bool(real_identity and web_ready and bm_ready)

    reasons: list[str] = []
    if not real_identity:
        reasons.append("callsign + base DMR ID")
    if not web_ready:
        reasons.append("dashboard password or imported dashboard credential")
    if not bm_ready:
        reasons.append("BrandMeister Hotspot Security password")

    if complete:
        canonical["brandmeister"]["password"] = hotspot_password
        canonical = config_model.normalize(canonical)

    wifi = profile.get("wifi") or {}
    ssid = str(wifi.get("ssid") or "").strip()
    wifi_password = str(wifi.get("password") or "")
    hidden = bool(wifi.get("hidden", False))
    if len(ssid.encode("utf-8")) > 32:
        raise ValueError("Wi-Fi SSID must be 32 bytes or fewer")
    if len(wifi_password) > 63:
        raise ValueError("Wi-Fi password must be 63 characters or fewer")

    image = profile.get("image") or {}
    image_name = str(image.get("image_name") or "ywd-hotspot-os").strip() or "ywd-hotspot-os"
    os_version = str(image.get("os_version") or "M5-builder-dev").strip() or "M5-builder-dev"
    if any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for ch in image_name):
        raise ValueError("image name may contain only letters, digits, dot, underscore, and dash")
    if len(os_version) > 64:
        raise ValueError("OS version label is too long")

    provision = None
    if complete and imported is None:
        provision = {
            "config": canonical,
            "web_password": dashboard_password,
            "hotspot_password": hotspot_password,
            "bm_api_key": bm_api_key,
            "enable_rf": bool(canonical.get("maintenance", {}).get("rf_autostart", False)),
        }

    return {
        "complete": complete,
        "missing": reasons,
        "config": canonical,
        "factory_provision": provision,
        "wifi": {"ssid": ssid, "password": wifi_password, "hidden": hidden},
        "image": {"image_name": image_name, "os_version": os_version},
        "dashboard_password": dashboard_password,
        "bm_api_key": bm_api_key,
        "imported_backup": imported,
        "imported_source_file": str((profile.get("imported_backup") or {}).get("source_file") or ""),
    }


def _restore_document(compiled: dict[str, Any]) -> dict[str, Any]:
    imported = compiled.get("imported_backup")
    if not isinstance(imported, dict):
        raise ValueError("no imported dashboard backup is available")
    doc = copy.deepcopy(imported)
    doc["config"] = copy.deepcopy(compiled["config"])

    secrets_doc = doc.setdefault("secrets", {})
    secrets_doc["bm_api_key"] = compiled.get("bm_api_key", "")
    dashboard_password = str(compiled.get("dashboard_password") or "")
    if dashboard_password:
        secrets_doc["web_auth"] = _make_web_auth(dashboard_password)
    elif not _valid_web_auth(secrets_doc.get("web_auth")):
        raise ValueError("imported dashboard backup has no reusable dashboard credential")

    wifi = compiled["wifi"]
    if wifi["ssid"]:
        doc["wifi"] = {
            "ssid": wifi["ssid"],
            "psk": wifi["password"],
            "key_mgmt": "wpa-psk" if wifi["password"] else "",
            "profile": "YWD Builder WiFi",
        }
    else:
        doc["wifi"] = None

    return settings_backup.validate_payload(doc)


def write_generated(compiled: dict[str, Any]) -> dict[str, Path]:
    GENERATED.mkdir(parents=True, exist_ok=True)
    os.chmod(GENERATED, 0o700)
    for old in GENERATED.iterdir():
        if old.is_file():
            old.unlink()

    paths: dict[str, Path] = {}
    cfg_path = GENERATED / "factory-config.json"
    atomic_write(cfg_path, json.dumps(compiled["config"], indent=2) + "\n")
    paths["config"] = cfg_path

    imported = compiled.get("imported_backup")
    if compiled["complete"] and isinstance(imported, dict):
        restore_doc = _restore_document(compiled)
        one_time_passphrase = secrets.token_urlsafe(36)
        encrypted = settings_backup.encrypt_payload(restore_doc, one_time_passphrase)
        request = {
            "backup_b64": base64.b64encode(encrypted).decode("ascii"),
            "passphrase": one_time_passphrase,
            "start_rf": bool(compiled["config"]["maintenance"]["rf_autostart"]),
            "restore_wifi": False,
            "first_boot": True,
        }
        p = GENERATED / "factory-restore.json"
        atomic_write(p, json.dumps(request, separators=(",", ":")) + "\n")
        paths["restore"] = p
    elif compiled.get("factory_provision") is not None:
        p = GENERATED / "factory-provision.json"
        atomic_write(p, json.dumps(compiled["factory_provision"], indent=2) + "\n")
        paths["provision"] = p

    wifi = compiled["wifi"]
    if wifi["ssid"]:
        p = GENERATED / "provision.env"
        text = (
            f"WIFI_SSID={shlex.quote(wifi['ssid'])}\n"
            f"WIFI_PASSWORD={shlex.quote(wifi['password'])}\n"
            f"WIFI_HIDDEN={'1' if wifi['hidden'] else '0'}\n"
        )
        atomic_write(p, text)
        paths["wifi"] = p

    env_path = GENERATED / "build.env"
    env_text = (
        f"YWD_IMG_NAME={shlex.quote(compiled['image']['image_name'])}\n"
        f"YWD_OS_VERSION={shlex.quote(compiled['image']['os_version'])}\n"
    )
    atomic_write(env_path, env_text)
    paths["env"] = env_path

    summary = {
        "schema": 1,
        "complete": compiled["complete"],
        "first_boot_wizard": not compiled["complete"],
        "missing": compiled["missing"],
        "wifi_preconfigured": bool(wifi["ssid"]),
        "callsign": compiled["config"]["station"]["callsign"],
        "hotspot_id": compiled["config"]["station"]["hotspot_id"],
        "radio_mode": compiled["config"]["radio"]["mode"],
        "brandmeister_enabled": compiled["config"]["brandmeister"]["enabled"],
        "dashboard_password_preconfigured": bool(
            compiled.get("dashboard_password")
            or (
                isinstance(compiled.get("imported_backup"), dict)
                and _valid_web_auth(compiled["imported_backup"].get("secrets", {}).get("web_auth"))
            )
        ),
        "bm_api_key_preconfigured": bool(compiled.get("bm_api_key")),
        "rf_autostart": compiled["config"]["maintenance"]["rf_autostart"],
        "dashboard_backup_imported": bool(compiled.get("imported_backup")),
        "dashboard_backup_source": compiled.get("imported_source_file", ""),
        "image": compiled["image"],
    }
    summary_path = GENERATED / "summary.json"
    atomic_write(summary_path, json.dumps(summary, indent=2) + "\n")
    paths["summary"] = summary_path
    return paths


def get_path(obj: dict[str, Any], path: str, default: Any = "") -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def set_path(obj: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur: dict[str, Any] = obj
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value
