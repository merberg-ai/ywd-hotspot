#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import os
import shlex
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "os" / "local"
PROFILE_PATH = LOCAL / "builder-profile.json"
GENERATED = LOCAL / "generated"


def _load_config_model():
    path = ROOT / "lib" / "config_model.py"
    spec = importlib.util.spec_from_file_location("ywd_config_model", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


config_model = _load_config_model()


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

    real_identity = canonical["station"]["callsign"] != "NOCALL" and canonical["station"]["base_dmr_id"] != "00000"
    web_ready = 8 <= len(dashboard_password) <= 256
    bm_enabled = bool(canonical["brandmeister"].get("enabled", True))
    bm_ready = (not bm_enabled) or bool(hotspot_password)
    complete = bool(real_identity and web_ready and bm_ready)

    reasons: list[str] = []
    if not real_identity:
        reasons.append("callsign + base DMR ID")
    if not web_ready:
        reasons.append("dashboard password (8+ chars)")
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
    if complete:
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
    }


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

    if compiled.get("factory_provision") is not None:
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
        "dashboard_password_preconfigured": compiled["complete"],
        "bm_api_key_preconfigured": bool(compiled.get("factory_provision") and compiled["factory_provision"].get("bm_api_key")),
        "rf_autostart": compiled["config"]["maintenance"]["rf_autostart"],
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
