#!/usr/bin/env python3
"""Fail-closed declarative plugin catalog for YWD-Hotspot.

Plugin API v1 does not import or execute plugin Python/JavaScript. Repository
packages are first-party available source; Alpha16 adds a separate trusted
package-registration layer so available/installed/enabled/active are distinct.
"""
from __future__ import annotations

import os
from pathlib import Path

import plugin_package_manager
from plugin_manifest import API_VERSION, ID_RE, PluginError, _read_json, validate_manifest, validate_schema

LIB = Path(__file__).resolve().parent
CATALOG = Path(os.environ.get("YWD_PLUGIN_CATALOG", str(LIB / "plugin_packages")))
STATE = Path(os.environ.get("YWD_PLUGIN_STATE", "/etc/ywd-hotspot/plugin-state.json"))
CONFIG_DIR = Path(os.environ.get("YWD_PLUGIN_CONFIG_DIR", "/etc/ywd-hotspot/plugins"))


def default_state():
    return {"schema": 1, "enabled": False, "plugins": {}}


def read_state():
    raw = _read_json(STATE, {})
    if not isinstance(raw, dict):
        return default_state()
    system_enabled = bool(raw.get("enabled", False))
    plugins = raw.get("plugins") if isinstance(raw.get("plugins"), dict) else {}
    clean = {}
    for key, value in plugins.items():
        if ID_RE.fullmatch(str(key)) and isinstance(value, dict):
            clean[str(key)] = {"enabled": bool(value.get("enabled", False)) if system_enabled else False}
    return {"schema": 1, "enabled": system_enabled, "plugins": clean}


def discover():
    found = []
    if not CATALOG.is_dir():
        return found
    for directory in sorted((x for x in CATALOG.iterdir() if x.is_dir()), key=lambda x: x.name):
        manifest_path = directory / "plugin.json"
        if not manifest_path.is_file():
            continue
        try:
            found.append({"valid": True, "manifest": validate_manifest(manifest_path), "error": None})
        except Exception as exc:
            ident = directory.name if ID_RE.fullmatch(directory.name) else "invalid-package"
            found.append({
                "valid": False,
                "manifest": {"id": ident, "name": directory.name, "version": "unknown", "directory": directory},
                "error": str(exc)[:500],
            })
    return found


def get_available_plugin(ident):
    ident = str(ident or "")
    if not ID_RE.fullmatch(ident):
        raise PluginError("invalid plugin id")
    for entry in discover():
        if entry["manifest"].get("id") == ident:
            if not entry["valid"]:
                raise PluginError(entry["error"] or "plugin manifest is invalid")
            return entry["manifest"]
    raise PluginError("plugin package is not available")


def get_plugin(ident):
    plugin = get_available_plugin(ident)
    if not plugin_package_manager.is_installed(plugin["id"]):
        raise PluginError("plugin is not installed")
    return plugin


def config_path(ident):
    if not ID_RE.fullmatch(str(ident or "")):
        raise PluginError("invalid plugin id")
    return CONFIG_DIR / f"{ident}.json"


def normalize_config(plugin, incoming=None):
    schema = plugin["schema"]
    if incoming is None:
        incoming = _read_json(config_path(plugin["id"]), {})
    if not isinstance(incoming, dict):
        raise PluginError("plugin configuration must be an object")
    allowed = {field["key"] for field in schema["fields"]}
    unknown = set(incoming) - allowed
    if unknown:
        raise PluginError(f"unknown plugin configuration keys: {', '.join(sorted(unknown))}")
    out = {}
    for field in schema["fields"]:
        key = field["key"]
        value = incoming.get(key, field.get("default"))
        kind = field["type"]
        if kind == "boolean":
            if not isinstance(value, bool):
                raise PluginError(f"{key} must be true or false")
        elif kind == "integer":
            if isinstance(value, bool):
                raise PluginError(f"{key} must be an integer")
            try:
                value = int(value)
            except Exception:
                raise PluginError(f"{key} must be an integer")
            if not field["min"] <= value <= field["max"]:
                raise PluginError(f"{key} must be between {field['min']} and {field['max']}")
        elif kind == "select":
            value = str(value)
            if value not in field["options"]:
                raise PluginError(f"{key} is not an allowed option")
        else:
            value = str(value)
            if len(value) > field["max_length"]:
                raise PluginError(f"{key} must be {field['max_length']} characters or fewer")
        out[key] = value
    return out


def public_config(plugin, config):
    out = {}
    for field in plugin["schema"]["fields"]:
        key = field["key"]
        if field.get("secret"):
            out[key] = {"configured": bool(config.get(key))}
        else:
            out[key] = config.get(key, field.get("default"))
    return out


def provider_data(plugin, config, system_summary=None):
    if plugin.get("provider") != "system-summary":
        return {}
    system = system_summary if isinstance(system_summary, dict) else {}
    out = {"label": config.get("label", "Framework online"), "hostname": system.get("hostname")}
    if config.get("show_uptime", True):
        out["uptime_s"] = system.get("uptime_s")
    if config.get("show_temperature", True):
        out["temperature_c"] = system.get("temperature_c")
    if config.get("show_load", False):
        out["load"] = system.get("load")
    return out


def snapshot(system_summary=None):
    state = read_state()
    package_state = plugin_package_manager.read_state()
    packages = []
    active = 0
    enabled_count = 0
    installed_count = 0
    for entry in discover():
        manifest = entry["manifest"]
        ident = manifest.get("id", "invalid-package")
        installed = bool(entry["valid"] and plugin_package_manager.is_installed(ident))
        if installed:
            installed_count += 1
        desired = bool(installed and (state.get("plugins", {}).get(ident) or {}).get("enabled", False))
        if desired:
            enabled_count += 1
        effective = bool(installed and state["enabled"] and desired and entry["valid"])
        if effective:
            active += 1
        item = {
            "id": ident,
            "name": manifest.get("name", ident),
            "version": manifest.get("version", "unknown"),
            "available": True,
            "installed": installed,
            "valid": bool(entry["valid"]),
            "error": entry.get("error"),
            "enabled": desired,
            "effective_enabled": effective,
            "config_present": config_path(ident).is_file() if ID_RE.fullmatch(str(ident)) else False,
            "data_present": plugin_package_manager.data_path(ident).exists() if ID_RE.fullmatch(str(ident)) else False,
            "health": "error" if not entry["valid"] else ("available" if not installed else ("active" if effective else "disabled")),
        }
        if entry["valid"]:
            checks = plugin_package_manager.check_requirements(manifest)
            item["requirements"] = checks
            item.update({
                "description": manifest["description"],
                "trust": manifest["trust"],
                "kind": manifest["kind"],
                "provider": manifest["provider"],
                "capabilities": manifest["capabilities"],
                "rf_mode": manifest["rf_mode"],
                "service": manifest["service"],
                "dependencies": manifest["dependencies"],
                "hardware": manifest["hardware"],
                "schema": manifest["schema"],
            })
            if installed:
                try:
                    config = normalize_config(manifest)
                    config_error = None
                except Exception as exc:
                    config = normalize_config(manifest, {})
                    config_error = str(exc)[:400]
                    item["health"] = "error"
                item.update({
                    "config": public_config(manifest, config),
                    "config_error": config_error,
                })
                if effective and not config_error:
                    item["data"] = provider_data(manifest, config, system_summary)
        packages.append(item)
    health = "disabled" if not state["enabled"] else (
        "error" if (not package_state["valid"] or any(item["health"] == "error" for item in packages)) else "good"
    )
    return {
        "api": API_VERSION,
        "system": {
            "enabled": state["enabled"],
            "health": health,
            "available": len(packages),
            "installed": installed_count,
            "enabled_plugins": enabled_count,
            "active_plugins": active,
            "execution_model": "declarative-only",
            "package_state": package_state["source"],
            "package_state_valid": package_state["valid"],
            "package_state_error": package_state.get("error"),
        },
        "plugins": packages,
    }


def test_plugin(ident, system_summary=None):
    state = read_state()
    plugin = get_plugin(ident)
    desired = bool((state.get("plugins", {}).get(plugin["id"]) or {}).get("enabled", False))
    if not state["enabled"]:
        raise PluginError("plugin subsystem is disabled")
    if not desired:
        raise PluginError("plugin is disabled")
    config = normalize_config(plugin)
    return {
        "ok": True,
        "id": plugin["id"],
        "health": "pass",
        "message": "Declarative provider test passed; no plugin code was executed.",
        "data": provider_data(plugin, config, system_summary),
    }


def managed_services():
    return []
