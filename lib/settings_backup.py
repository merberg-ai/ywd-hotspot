#!/usr/bin/env python3
"""Portable authenticated encrypted YWD-Hotspot settings backups."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import config_model
import plugin_manager
import plugin_package_manager

FORMAT = "ywdsettings"
FORMAT_VERSION = 1
KDF_N = 1 << 14
KDF_R = 8
KDF_P = 1
MAX_ENVELOPE = 1536 * 1024
CFG = Path(os.environ.get("YWD_CONFIG", "/etc/ywd-hotspot/config.json"))
ETC = CFG.parent
VAR = Path(os.environ.get("YWD_VAR", "/var/lib/ywd-hotspot"))
BMKEY = Path(os.environ.get("YWD_BM_API_KEY", "/etc/ywd-hotspot/bm-api.key"))
WEB_AUTH = Path(os.environ.get("YWD_WEB_AUTH", "/etc/ywd-hotspot/web-auth.json"))
BUILD_INFO = ETC / "build-info.json"
CAL_BASELINE = VAR / "private" / "calibration-baseline.json"
PLUGIN_STATE = Path(os.environ.get("YWD_PLUGIN_STATE", "/etc/ywd-hotspot/plugin-state.json"))
PACKAGE_STATE = Path(os.environ.get("YWD_PLUGIN_PACKAGE_STATE", "/etc/ywd-hotspot/plugin-packages.json"))
PLUGIN_CONFIG_DIR = Path(os.environ.get("YWD_PLUGIN_CONFIG_DIR", "/etc/ywd-hotspot/plugins"))
TRUST_DIR = Path(os.environ.get("YWD_PLUGIN_TRUST_DIR", "/etc/ywd-hotspot/plugin-trust.d"))


class SettingsBackupError(ValueError):
    pass


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _derive(passphrase, salt):
    if not isinstance(passphrase, str) or len(passphrase) < 10 or len(passphrase) > 256:
        raise SettingsBackupError("backup passphrase must be 10-256 characters")
    raw = hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, n=KDF_N, r=KDF_R, p=KDF_P, dklen=64)
    return raw[:32], raw[32:]


def _openssl(data, key, iv, decrypt=False):
    cmd = ["openssl", "enc", "-aes-256-cbc", "-nosalt", "-K", key.hex(), "-iv", iv.hex()]
    if decrypt:
        cmd.append("-d")
    p = subprocess.run(cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    if p.returncode != 0:
        if decrypt:
            raise SettingsBackupError("backup decryption failed")
        raise SettingsBackupError("OpenSSL could not encrypt the settings backup")
    return p.stdout


def _header_bytes(header):
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")


def encrypt_payload(payload, passphrase):
    plain = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    salt = os.urandom(16)
    iv = os.urandom(16)
    enc_key, mac_key = _derive(passphrase, salt)
    ciphertext = _openssl(plain, enc_key, iv, decrypt=False)
    header = {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "cipher": "AES-256-CBC",
        "auth": "HMAC-SHA256",
        "kdf": {"name": "scrypt", "n": KDF_N, "r": KDF_R, "p": KDF_P, "salt": base64.b64encode(salt).decode("ascii")},
        "iv": base64.b64encode(iv).decode("ascii"),
    }
    tag = hmac.new(mac_key, _header_bytes(header) + b"\x00" + ciphertext, hashlib.sha256).hexdigest()
    envelope = {**header, "ciphertext": base64.b64encode(ciphertext).decode("ascii"), "hmac": tag}
    raw = (json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(raw) > MAX_ENVELOPE:
        raise SettingsBackupError("settings backup exceeds the portable backup size limit")
    return raw


def decrypt_payload(blob, passphrase):
    if not isinstance(blob, (bytes, bytearray)) or not blob or len(blob) > MAX_ENVELOPE:
        raise SettingsBackupError("settings backup is empty or too large")
    try:
        env = json.loads(bytes(blob).decode("utf-8"))
    except Exception:
        raise SettingsBackupError("file is not a valid .ywdsettings envelope")
    if not isinstance(env, dict) or env.get("format") != FORMAT or env.get("version") != FORMAT_VERSION:
        raise SettingsBackupError("unsupported .ywdsettings format/version")
    if env.get("cipher") != "AES-256-CBC" or env.get("auth") != "HMAC-SHA256":
        raise SettingsBackupError("unsupported backup encryption/authentication scheme")
    kdf = env.get("kdf")
    if not isinstance(kdf, dict) or kdf.get("name") != "scrypt":
        raise SettingsBackupError("unsupported backup KDF")
    if (int(kdf.get("n", 0)), int(kdf.get("r", 0)), int(kdf.get("p", 0))) != (KDF_N, KDF_R, KDF_P):
        raise SettingsBackupError("unsupported backup KDF parameters")
    try:
        salt = base64.b64decode(kdf["salt"], validate=True)
        iv = base64.b64decode(env["iv"], validate=True)
        ciphertext = base64.b64decode(env["ciphertext"], validate=True)
    except Exception:
        raise SettingsBackupError("backup envelope contains invalid base64")
    if len(salt) != 16 or len(iv) != 16 or not ciphertext:
        raise SettingsBackupError("backup envelope parameters are invalid")
    enc_key, mac_key = _derive(passphrase, salt)
    header = {k: env[k] for k in ("format", "version", "cipher", "auth", "kdf", "iv")}
    expected = hmac.new(mac_key, _header_bytes(header) + b"\x00" + ciphertext, hashlib.sha256).hexdigest()
    supplied = str(env.get("hmac") or "")
    if not hmac.compare_digest(expected, supplied):
        raise SettingsBackupError("backup authentication failed: wrong passphrase or modified file")
    plain = _openssl(ciphertext, enc_key, iv, decrypt=True)
    try:
        payload = json.loads(plain.decode("utf-8"))
    except Exception:
        raise SettingsBackupError("decrypted backup payload is invalid")
    return validate_payload(payload)


def _wifi_snapshot():
    def out(args):
        try:
            p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=8, check=False)
            return (p.stdout or "").strip() if p.returncode == 0 else ""
        except Exception:
            return ""
    profile = out(["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", "wlan0"])
    if not profile or profile in {"--", "YWD Setup AP"}:
        return None
    ssid = out(["nmcli", "-g", "802-11-wireless.ssid", "connection", "show", profile])
    psk = out(["nmcli", "--show-secrets", "-g", "802-11-wireless-security.psk", "connection", "show", profile])
    keymgmt = out(["nmcli", "-g", "802-11-wireless-security.key-mgmt", "connection", "show", profile])
    if not ssid:
        return None
    return {"ssid": ssid[:128], "psk": psk[:256], "key_mgmt": keymgmt[:64], "profile": profile[:128]}


def collect(include_wifi=False):
    cfg = config_model.normalize(json.loads(CFG.read_text(encoding="utf-8")))
    build = read_json(BUILD_INFO, {})
    plugin_configs = {}
    if PLUGIN_CONFIG_DIR.is_dir():
        for path in sorted(PLUGIN_CONFIG_DIR.glob("*.json")):
            ident = path.stem
            if plugin_manager.ID_RE.fullmatch(ident) and path.stat().st_size <= 131072:
                doc = read_json(path)
                if isinstance(doc, dict):
                    plugin_configs[ident] = doc
    trust = {}
    if TRUST_DIR.is_dir():
        for path in sorted(TRUST_DIR.glob("*.pem")):
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", path.stem) and path.stat().st_size <= 16384:
                try:
                    trust[path.stem] = path.read_text(encoding="utf-8")
                except Exception:
                    pass
    package_state = plugin_package_manager.read_state()
    installed = package_state.get("installed") if isinstance(package_state, dict) else {}
    installed = installed if isinstance(installed, dict) else {}
    clean_installed = {str(ident): bool(value) for ident, value in installed.items() if plugin_manager.ID_RE.fullmatch(str(ident)) and isinstance(value, bool)}
    return {
        "schema": 1,
        "created_at": now_iso(),
        "source": {
            "version": str(build.get("version") or "unknown")[:80],
            "branch": str(build.get("branch") or "unknown")[:80],
            "commit": str(build.get("commit") or "unknown")[:80],
            "hostname": os.uname().nodename[:128],
        },
        "config": cfg,
        "secrets": {
            "bm_api_key": BMKEY.read_text(encoding="utf-8").strip()[:4096] if BMKEY.is_file() else "",
            "web_auth": read_json(WEB_AUTH, None) if WEB_AUTH.is_file() else None,
        },
        "calibration_baseline": read_json(CAL_BASELINE, None),
        "plugins": {
            "state": read_json(PLUGIN_STATE, {"schema": 1, "enabled": False, "plugins": {}}),
            "packages": {"schema": 1, "installed": clean_installed},
            "configs": plugin_configs,
            "trust_keys": trust,
        },
        "wifi": _wifi_snapshot() if include_wifi else None,
    }


def validate_payload(payload):
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        raise SettingsBackupError("unsupported backup payload schema")
    raw_cfg = payload.get("config")
    if not isinstance(raw_cfg, dict):
        raise SettingsBackupError("backup does not contain a canonical configuration")
    try:
        cfg = config_model.normalize(raw_cfg)
    except Exception as exc:
        raise SettingsBackupError(f"backup configuration is invalid: {exc}")
    secrets = payload.get("secrets") if isinstance(payload.get("secrets"), dict) else {}
    api_key = str(secrets.get("bm_api_key") or "")
    if len(api_key) > 4096 or "\n" in api_key or "\r" in api_key:
        raise SettingsBackupError("backup BrandMeister API key is invalid")
    web_auth = secrets.get("web_auth")
    if web_auth is not None:
        if not isinstance(web_auth, dict) or web_auth.get("scheme") != "scrypt" or not all(k in web_auth for k in ("salt", "hash", "n", "r", "p")):
            raise SettingsBackupError("backup WebUI authentication record is invalid")
    plugins = payload.get("plugins") if isinstance(payload.get("plugins"), dict) else {}
    configs = plugins.get("configs") if isinstance(plugins.get("configs"), dict) else {}
    clean_configs = {}
    for ident, doc in configs.items():
        if plugin_manager.ID_RE.fullmatch(str(ident)) and isinstance(doc, dict):
            clean_configs[str(ident)] = doc
    package_doc = plugins.get("packages") if isinstance(plugins.get("packages"), dict) else {}
    raw_installed = package_doc.get("installed") if isinstance(package_doc.get("installed"), dict) else {}
    clean_installed = {}
    for ident, value in raw_installed.items():
        if plugin_manager.ID_RE.fullmatch(str(ident)) and isinstance(value, bool):
            clean_installed[str(ident)] = value
    trust = plugins.get("trust_keys") if isinstance(plugins.get("trust_keys"), dict) else {}
    clean_trust = {}
    for key_id, pem in trust.items():
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", str(key_id)) and isinstance(pem, str) and len(pem) <= 16384 and "PUBLIC KEY" in pem:
            clean_trust[str(key_id)] = pem
    wifi = payload.get("wifi") if isinstance(payload.get("wifi"), dict) else None
    if wifi:
        ssid = str(wifi.get("ssid") or "")
        psk = str(wifi.get("psk") or "")
        if not 1 <= len(ssid) <= 128 or len(psk) > 256:
            raise SettingsBackupError("backup Wi-Fi profile is invalid")
        wifi = {"ssid": ssid, "psk": psk, "key_mgmt": str(wifi.get("key_mgmt") or "")[:64], "profile": str(wifi.get("profile") or "")[:128]}
    return {
        "schema": 1,
        "created_at": str(payload.get("created_at") or "")[:80],
        "source": payload.get("source") if isinstance(payload.get("source"), dict) else {},
        "config": cfg,
        "secrets": {"bm_api_key": api_key, "web_auth": web_auth},
        "calibration_baseline": payload.get("calibration_baseline") if isinstance(payload.get("calibration_baseline"), dict) else None,
        "plugins": {
            "state": plugins.get("state") if isinstance(plugins.get("state"), dict) else {"schema": 1, "enabled": False, "plugins": {}},
            "packages": {"schema": 1, "installed": clean_installed},
            "configs": clean_configs,
            "trust_keys": clean_trust,
        },
        "wifi": wifi,
    }


def preview(payload):
    payload = validate_payload(payload)
    cfg = payload["config"]
    pstate = payload["plugins"]["state"]
    packages = payload["plugins"]["packages"]
    installed = packages.get("installed", {})
    enabled = pstate.get("plugins", {}) if isinstance(pstate.get("plugins"), dict) else {}
    return {
        "schema": payload["schema"],
        "created_at": payload["created_at"],
        "source": payload["source"],
        "callsign": cfg["station"]["callsign"],
        "dmr_id": cfg["station"]["base_dmr_id"],
        "frequency_mhz": round(int(cfg["radio"]["frequency_hz"]) / 1e6, 6),
        "color_code": cfg["radio"]["color_code"],
        "brandmeister_master": cfg["brandmeister"]["master"],
        "hotspot_password_configured": bool(cfg["brandmeister"].get("password")),
        "bm_api_key_configured": bool(payload["secrets"]["bm_api_key"]),
        "web_password_configured": bool(payload["secrets"]["web_auth"]),
        "rf_autostart": bool(cfg["maintenance"].get("rf_autostart")),
        "plugin_master_enabled": bool(pstate.get("enabled")),
        "plugins_installed": sum(1 for v in installed.values() if v is True),
        "plugins_enabled": sum(1 for v in enabled.values() if isinstance(v, dict) and v.get("enabled") is True),
        "plugin_configs": len(payload["plugins"]["configs"]),
        "trust_keys": len(payload["plugins"]["trust_keys"]),
        "wifi_included": bool(payload.get("wifi")),
        "wifi_ssid": payload.get("wifi", {}).get("ssid") if payload.get("wifi") else None,
    }
