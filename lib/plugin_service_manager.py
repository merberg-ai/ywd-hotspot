#!/usr/bin/env python3
"""Sandboxed service-plugin discovery/status for YWD-Hotspot."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import mmdvm_telemetry
import plugin_manager
import plugin_package_manager

API_VERSION = 1
LIB = Path(__file__).resolve().parent
CATALOG = Path(os.environ.get("YWD_SERVICE_PLUGIN_CATALOG", str(LIB / "service_plugin_packages")))
ALLOWED_TRUST = {"first-party", "experimental"}
ALLOWED_KINDS = {"service"}
ALLOWED_CAPABILITIES = {"service:lifecycle", "read:journal", "read:mmdvm-telemetry"}
ALLOWED_PROVIDERS = {"sandboxed-service", "mmdvm-telemetry"}
MANIFEST_KEYS = {
    "api", "id", "name", "version", "description", "trust", "kind", "provider",
    "capabilities", "rf_mode", "entrypoint", "config_schema", "dependencies", "hardware",
}
ENTRY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}\.py$")


class ServicePluginError(plugin_manager.PluginError):
    pass


def _read_json(path):
    try: return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception: return None


def _text(value, field, limit):
    text = str(value or "").strip()
    if not text: raise ServicePluginError(f"manifest {field} is required")
    if len(text) > limit: raise ServicePluginError(f"manifest {field} is too long")
    return text


def unit_name(ident):
    ident = str(ident or "")
    if not plugin_manager.ID_RE.fullmatch(ident): raise ServicePluginError("invalid service plugin id")
    return f"ywd-plugin@{ident}.service"


def validate_manifest(path):
    path = Path(path); directory = path.parent; raw = _read_json(path)
    if not isinstance(raw, dict): raise ServicePluginError("service plugin manifest is not valid JSON")
    unknown = set(raw) - MANIFEST_KEYS
    if unknown: raise ServicePluginError(f"service manifest has unknown keys: {', '.join(sorted(unknown))}")
    if raw.get("api") != API_VERSION: raise ServicePluginError(f"service plugin API must be {API_VERSION}")
    ident = str(raw.get("id") or "")
    if not plugin_manager.ID_RE.fullmatch(ident) or directory.name != ident: raise ServicePluginError("service plugin id must match its directory")
    for entry in plugin_manager.discover():
        if entry.get("manifest", {}).get("id") == ident: raise ServicePluginError("plugin id collides with a declarative plugin")
    name = _text(raw.get("name"), "name", 80); version = _text(raw.get("version"), "version", 40); description = _text(raw.get("description"), "description", 500)
    trust = str(raw.get("trust") or ""); kind = str(raw.get("kind") or "")
    if trust not in ALLOWED_TRUST: raise ServicePluginError("unsupported service-plugin trust level")
    if kind not in ALLOWED_KINDS: raise ServicePluginError("service plugin kind must be 'service'")
    if bool(raw.get("rf_mode", False)): raise ServicePluginError("RF-mode ownership is not permitted in the service-plugin phase")
    caps = raw.get("capabilities")
    if not isinstance(caps, list) or any(str(x) not in ALLOWED_CAPABILITIES for x in caps): raise ServicePluginError("service manifest contains an unsupported capability")
    caps = list(dict.fromkeys(str(x) for x in caps))
    provider = str(raw.get("provider") or "sandboxed-service")
    if provider not in ALLOWED_PROVIDERS: raise ServicePluginError("unsupported service-plugin provider")
    if provider == "mmdvm-telemetry" and "read:mmdvm-telemetry" not in caps: raise ServicePluginError("mmdvm-telemetry provider requires read:mmdvm-telemetry capability")
    try: dependencies, hardware = plugin_package_manager.validate_requirements(raw.get("dependencies", []), raw.get("hardware", []))
    except plugin_package_manager.PackageStateError as exc: raise ServicePluginError(str(exc))
    entrypoint = str(raw.get("entrypoint") or "")
    if not ENTRY_RE.fullmatch(entrypoint) or Path(entrypoint).name != entrypoint: raise ServicePluginError("service entrypoint must be a simple .py filename")
    entry_path = directory / entrypoint
    if not entry_path.is_file() or entry_path.stat().st_size > 131072: raise ServicePluginError("service entrypoint is missing or too large")
    schema_name = str(raw.get("config_schema") or ""); schema = plugin_manager.validate_schema(directory, schema_name)
    return {"api":API_VERSION,"id":ident,"name":name,"version":version,"description":description,"trust":trust,"kind":kind,"provider":provider,"capabilities":caps,"rf_mode":False,"service":unit_name(ident),"entrypoint":entrypoint,"dependencies":dependencies,"hardware":hardware,"config_schema":schema_name,"schema":schema,"directory":directory}


def discover():
    rows = []
    if not CATALOG.is_dir(): return rows
    for directory in sorted((p for p in CATALOG.iterdir() if p.is_dir()), key=lambda p: p.name):
        manifest_path = directory / "plugin.json"
        if not manifest_path.is_file(): continue
        try: rows.append({"valid":True,"manifest":validate_manifest(manifest_path),"error":None})
        except Exception as exc:
            ident = directory.name if plugin_manager.ID_RE.fullmatch(directory.name) else "invalid-package"
            rows.append({"valid":False,"manifest":{"id":ident,"name":directory.name,"version":"unknown","directory":directory},"error":str(exc)[:500]})
    return rows


def get_available_plugin(ident):
    ident = str(ident or "")
    if not plugin_manager.ID_RE.fullmatch(ident): raise ServicePluginError("invalid service plugin id")
    for entry in discover():
        if entry.get("manifest", {}).get("id") == ident:
            if not entry.get("valid"): raise ServicePluginError(entry.get("error") or "service plugin is invalid")
            return entry["manifest"]
    raise ServicePluginError("service plugin package is not available")


def get_plugin(ident):
    plugin = get_available_plugin(ident)
    if not plugin_package_manager.is_installed(plugin["id"]): raise ServicePluginError("service plugin is not installed")
    return plugin


def _run(args, timeout=4):
    try:
        p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
        return (p.stdout or "").strip()
    except Exception: return ""


def runtime_state(unit):
    return {"state":_run(["systemctl","is-active",unit],3) or "unknown","boot":_run(["systemctl","is-enabled",unit],3) or "disabled"}


def normalize_config(plugin, incoming=None): return plugin_manager.normalize_config(plugin, incoming)
def public_config(plugin, config): return plugin_manager.public_config(plugin, config)


def _provider_data(manifest, config):
    if manifest.get("provider") == "mmdvm-telemetry":
        return mmdvm_telemetry.public_snapshot(config.get("stale_after_s", 8) if isinstance(config, dict) else 8)
    return None


def snapshot():
    state = plugin_manager.read_state(); packages = []
    for entry in discover():
        manifest = entry["manifest"]; ident = manifest.get("id", "invalid-package")
        installed = bool(entry.get("valid") and plugin_package_manager.is_installed(ident))
        desired = bool(installed and (state.get("plugins", {}).get(ident) or {}).get("enabled", False))
        effective = bool(installed and state.get("enabled") and desired and entry.get("valid"))
        item = {"id":ident,"name":manifest.get("name",ident),"version":manifest.get("version","unknown"),"available":True,"installed":installed,"valid":bool(entry.get("valid")),"error":entry.get("error"),"enabled":desired,"effective_enabled":effective,"config_present":plugin_manager.config_path(ident).is_file() if plugin_manager.ID_RE.fullmatch(str(ident)) else False,"data_present":plugin_package_manager.data_path(ident).exists() if plugin_manager.ID_RE.fullmatch(str(ident)) else False,"health":"error" if not entry.get("valid") else ("available" if not installed else "disabled")}
        if entry.get("valid"):
            runtime = runtime_state(manifest["service"]); checks = plugin_package_manager.check_requirements(manifest)
            orphaned = not installed and (runtime["state"] == "active" or runtime["boot"] != "disabled")
            if orphaned: item["health"]="error"; item["error"]="uninstalled service still has runtime/boot state; disable or repair it before continuing"
            config_error = None; config = None
            if installed:
                try: config = normalize_config(manifest)
                except Exception as exc: config = normalize_config(manifest, {}); config_error = str(exc)[:400]
            if installed and effective: item["health"] = "active" if runtime["state"] == "active" else "stopped"
            if config_error: item["health"] = "error"
            item.update({"description":manifest["description"],"trust":manifest["trust"],"kind":manifest["kind"],"provider":manifest.get("provider","sandboxed-service"),"capabilities":manifest["capabilities"],"rf_mode":False,"service":manifest["service"],"dependencies":manifest["dependencies"],"hardware":manifest["hardware"],"requirements":checks,"schema":manifest["schema"],"config_error":config_error,"runtime":runtime})
            if config is not None:
                item["config"] = public_config(manifest, config)
                if effective:
                    data = _provider_data(manifest, config)
                    if data is not None: item["data"] = data
        packages.append(item)
    return packages


def test_plugin(ident):
    state = plugin_manager.read_state(); plugin = get_plugin(ident)
    desired = bool((state.get("plugins", {}).get(plugin["id"]) or {}).get("enabled", False))
    if not state.get("enabled"): raise ServicePluginError("plugin subsystem is disabled")
    if not desired: raise ServicePluginError("service plugin is disabled")
    runtime = runtime_state(plugin["service"])
    if runtime["state"] != "active": raise ServicePluginError(f"service is {runtime['state']}")
    data = {"service":plugin["service"], **runtime}
    message = "Sandboxed service is active under the shared YWD plugin unit template."
    if plugin.get("provider") == "mmdvm-telemetry":
        config = normalize_config(plugin)
        telemetry = _provider_data(plugin, config)
        data["telemetry"] = telemetry
        message = f"Telemetry adapter active; trusted bridge is {telemetry.get('bridge',{}).get('status','unknown')}."
    return {"ok":True,"id":plugin["id"],"health":"pass","message":message,"data":data}
