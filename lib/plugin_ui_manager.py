#!/usr/bin/env python3
"""Signed browser-UI plugin discovery/status for YWD-Hotspot Plugin UI v1.

UI plugins contain browser-side assets only. They do not execute code on the Pi,
do not own services or devices, and are exposed only while installed + enabled
under the master plugin switch.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import plugin_catalog_overlay
import plugin_manager
import plugin_package_manager

API_VERSION = 1
LIB = Path(__file__).resolve().parent
CATALOG = Path(os.environ.get("YWD_UI_PLUGIN_CATALOG", str(LIB / "ui_plugin_packages")))
ALLOWED_TRUST = {"first-party", "experimental"}
ALLOWED_KINDS = {"ui"}
ALLOWED_PROVIDERS = {"browser-ui"}
ALLOWED_CAPABILITIES = {"ui:section", "read:dmr-voice", "use:vocoder"}
MANIFEST_KEYS = {
    "api", "id", "name", "version", "description", "trust", "kind", "provider",
    "capabilities", "rf_mode", "config_schema", "dependencies", "hardware", "ui",
}
UI_KEYS = {"api", "label", "script", "style"}
ASSET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,23}$")
MAX_SCRIPT = 256 * 1024
MAX_STYLE = 128 * 1024


class UiPluginError(plugin_manager.PluginError):
    pass


def _read_json(path):
    return plugin_manager._read_json(path)


def _text(value, field, limit):
    text = str(value or "").strip()
    if not text:
        raise UiPluginError(f"manifest {field} is required")
    if len(text) > limit:
        raise UiPluginError(f"manifest {field} is too long")
    return text


def _asset(directory, name, suffix, max_bytes):
    name = str(name or "")
    if not ASSET_RE.fullmatch(name) or Path(name).name != name or not name.lower().endswith(suffix):
        raise UiPluginError(f"UI {suffix} asset must be a simple {suffix} filename")
    path = directory / name
    if not path.is_file() or path.is_symlink():
        raise UiPluginError(f"UI asset is missing or invalid: {name}")
    if path.stat().st_size > max_bytes:
        raise UiPluginError(f"UI asset is too large: {name}")
    return name


def validate_manifest(path):
    path = Path(path)
    directory = path.parent
    raw = _read_json(path)
    if not isinstance(raw, dict):
        raise UiPluginError("UI plugin manifest is not valid JSON")
    unknown = set(raw) - MANIFEST_KEYS
    if unknown:
        raise UiPluginError(f"UI manifest has unknown keys: {', '.join(sorted(unknown))}")
    if raw.get("api") != API_VERSION:
        raise UiPluginError(f"UI plugin API must be {API_VERSION}")

    ident = str(raw.get("id") or "")
    if not plugin_manager.ID_RE.fullmatch(ident) or directory.name != ident:
        raise UiPluginError("UI plugin id must match its directory")

    # Keep IDs globally unique across all plugin execution models.
    for entry in plugin_manager.discover():
        if entry.get("manifest", {}).get("id") == ident:
            raise UiPluginError("plugin id collides with a declarative plugin")
    try:
        import plugin_service_manager
        for entry in plugin_service_manager.discover():
            if entry.get("manifest", {}).get("id") == ident:
                raise UiPluginError("plugin id collides with a service plugin")
    except ImportError:
        pass

    name = _text(raw.get("name"), "name", 80)
    version = _text(raw.get("version"), "version", 40)
    description = _text(raw.get("description"), "description", 500)
    trust = str(raw.get("trust") or "")
    kind = str(raw.get("kind") or "")
    provider = str(raw.get("provider") or "browser-ui")
    if trust not in ALLOWED_TRUST:
        raise UiPluginError("unsupported UI-plugin trust level")
    if kind not in ALLOWED_KINDS:
        raise UiPluginError("UI plugin kind must be 'ui'")
    if provider not in ALLOWED_PROVIDERS:
        raise UiPluginError("unsupported UI-plugin provider")
    if bool(raw.get("rf_mode", False)):
        raise UiPluginError("RF-mode ownership is not permitted for UI plugins")

    caps = raw.get("capabilities")
    if not isinstance(caps, list) or any(str(x) not in ALLOWED_CAPABILITIES for x in caps):
        raise UiPluginError("UI manifest contains an unsupported capability")
    caps = list(dict.fromkeys(str(x) for x in caps))
    if "ui:section" not in caps:
        raise UiPluginError("UI plugins require the ui:section capability")

    try:
        dependencies, hardware = plugin_package_manager.validate_requirements(
            raw.get("dependencies", []), raw.get("hardware", [])
        )
    except plugin_package_manager.PackageStateError as exc:
        raise UiPluginError(str(exc))

    ui = raw.get("ui")
    if not isinstance(ui, dict):
        raise UiPluginError("UI plugins must define a ui object")
    unknown_ui = set(ui) - UI_KEYS
    if unknown_ui:
        raise UiPluginError(f"UI definition has unknown keys: {', '.join(sorted(unknown_ui))}")
    if ui.get("api") != 1:
        raise UiPluginError("UI surface API must be 1")
    label = str(ui.get("label") or "").strip()
    if not LABEL_RE.fullmatch(label):
        raise UiPluginError("UI label must be 1-24 safe display characters")
    script = _asset(directory, ui.get("script"), ".js", MAX_SCRIPT)
    style = _asset(directory, ui.get("style"), ".css", MAX_STYLE)

    schema_name = str(raw.get("config_schema") or "")
    schema = plugin_manager.validate_schema(directory, schema_name)
    return {
        "api": API_VERSION,
        "id": ident,
        "name": name,
        "version": version,
        "description": description,
        "trust": trust,
        "kind": kind,
        "provider": provider,
        "capabilities": caps,
        "rf_mode": False,
        "service": None,
        "dependencies": dependencies,
        "hardware": hardware,
        "config_schema": schema_name,
        "schema": schema,
        "ui": {"api": 1, "label": label, "script": script, "style": style},
        "directory": directory,
    }


def discover():
    rows = []
    seen = set()
    directories = []
    if CATALOG.is_dir():
        directories.extend(sorted((p for p in CATALOG.iterdir() if p.is_dir()), key=lambda p: p.name))
    directories.extend(plugin_catalog_overlay.local_dirs("ui"))
    for directory in directories:
        if directory.name in seen:
            continue
        seen.add(directory.name)
        manifest_path = directory / "plugin.json"
        if not manifest_path.is_file():
            continue
        try:
            rows.append({"valid": True, "manifest": validate_manifest(manifest_path), "error": None})
        except Exception as exc:
            ident = directory.name if plugin_manager.ID_RE.fullmatch(directory.name) else "invalid-package"
            rows.append({
                "valid": False,
                "manifest": {"id": ident, "name": directory.name, "version": "unknown", "directory": directory},
                "error": str(exc)[:500],
            })
    return rows


def get_available_plugin(ident):
    ident = str(ident or "")
    if not plugin_manager.ID_RE.fullmatch(ident):
        raise UiPluginError("invalid UI plugin id")
    for entry in discover():
        if entry.get("manifest", {}).get("id") == ident:
            if not entry.get("valid"):
                raise UiPluginError(entry.get("error") or "UI plugin is invalid")
            return entry["manifest"]
    raise UiPluginError("UI plugin package is not available")


def get_plugin(ident):
    plugin = get_available_plugin(ident)
    if not plugin_package_manager.is_installed(plugin["id"]):
        raise UiPluginError("UI plugin is not installed")
    return plugin


def get_effective_plugin(ident):
    plugin = get_plugin(ident)
    state = plugin_manager.read_state()
    if not state.get("enabled"):
        raise UiPluginError("plugin subsystem is disabled")
    if not bool((state.get("plugins", {}).get(plugin["id"]) or {}).get("enabled", False)):
        raise UiPluginError("UI plugin is disabled")
    return plugin


def asset_path(ident, filename):
    plugin = get_effective_plugin(ident)
    filename = str(filename or "")
    allowed = {plugin["ui"]["script"], plugin["ui"]["style"]}
    if filename not in allowed or Path(filename).name != filename:
        raise UiPluginError("UI asset is not declared by this plugin")
    path = Path(plugin["directory"]) / filename
    if not path.is_file() or path.is_symlink():
        raise UiPluginError("UI asset is unavailable")
    return plugin, path


def snapshot():
    state = plugin_manager.read_state()
    packages = []
    for entry in discover():
        manifest = entry["manifest"]
        ident = manifest.get("id", "invalid-package")
        installed = bool(entry.get("valid") and plugin_package_manager.is_installed(ident))
        desired = bool(installed and (state.get("plugins", {}).get(ident) or {}).get("enabled", False))
        effective = bool(installed and state.get("enabled") and desired and entry.get("valid"))
        item = {
            "id": ident,
            "name": manifest.get("name", ident),
            "version": manifest.get("version", "unknown"),
            "available": True,
            "installed": installed,
            "valid": bool(entry.get("valid")),
            "error": entry.get("error"),
            "enabled": desired,
            "effective_enabled": effective,
            "config_present": plugin_manager.config_path(ident).is_file() if plugin_manager.ID_RE.fullmatch(str(ident)) else False,
            "data_present": plugin_package_manager.data_path(ident).exists() if plugin_manager.ID_RE.fullmatch(str(ident)) else False,
            "health": "error" if not entry.get("valid") else ("available" if not installed else ("active" if effective else "disabled")),
        }
        if entry.get("valid"):
            checks = plugin_package_manager.check_requirements(manifest)
            item.update({
                "description": manifest["description"],
                "trust": manifest["trust"],
                "kind": manifest["kind"],
                "provider": manifest["provider"],
                "capabilities": manifest["capabilities"],
                "rf_mode": False,
                "service": None,
                "dependencies": manifest["dependencies"],
                "hardware": manifest["hardware"],
                "requirements": checks,
                "schema": manifest["schema"],
                "ui": manifest["ui"],
            })
            if installed:
                try:
                    config = plugin_manager.normalize_config(manifest)
                    config_error = None
                except Exception as exc:
                    config = plugin_manager.normalize_config(manifest, {})
                    config_error = str(exc)[:400]
                    item["health"] = "error"
                item["config"] = plugin_manager.public_config(manifest, config)
                item["config_error"] = config_error
        packages.append(item)
    return packages


def test_plugin(ident):
    plugin = get_effective_plugin(ident)
    return {
        "ok": True,
        "id": plugin["id"],
        "health": "pass",
        "message": "Plugin UI v1 surface is enabled. Browser code executes only inside the sandboxed UI frame.",
        "data": {"ui": plugin["ui"], "capabilities": plugin["capabilities"]},
    }
