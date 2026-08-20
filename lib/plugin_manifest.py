#!/usr/bin/env python3
"""Strict declarative manifest/schema validation for YWD-Hotspot plugins."""
from __future__ import annotations

import json
import re
from pathlib import Path

import plugin_package_manager

API_VERSION = 1
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
SERVICE_RE = re.compile(r"^ywd-plugin-[a-z0-9][a-z0-9-]{0,39}\.service$")
ALLOWED_TRUST = {"first-party", "experimental"}
ALLOWED_KINDS = {"declarative"}
ALLOWED_PROVIDERS = {"system-summary"}
ALLOWED_CAPABILITIES = {"read:system-summary"}
ALLOWED_FIELD_TYPES = {"string", "boolean", "integer", "select"}
MANIFEST_KEYS = {
    "api", "id", "name", "version", "description", "trust", "kind", "provider",
    "capabilities", "rf_mode", "service", "config_schema", "dependencies", "hardware",
}
FIELD_KEYS = {"key", "type", "label", "default", "min", "max", "max_length", "options", "help", "secret"}

class PluginError(ValueError):
    pass


def _read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _clean_text(value, field, limit, required=True):
    text = str(value or "").strip()
    if required and not text:
        raise PluginError(f"manifest {field} is required")
    if len(text) > limit:
        raise PluginError(f"manifest {field} is too long")
    return text


def _safe_child(directory, filename):
    name = str(filename or "")
    if not name or Path(name).name != name:
        raise PluginError("plugin file reference must be a simple filename")
    return directory / name


def validate_schema(plugin_dir, filename):
    path = _safe_child(plugin_dir, filename)
    raw = _read_json(path)
    if not isinstance(raw, dict):
        raise PluginError(f"invalid configuration schema: {filename}")
    if raw.get("schema") != 1:
        raise PluginError("configuration schema must be version 1")
    fields = raw.get("fields")
    if not isinstance(fields, list) or len(fields) > 40:
        raise PluginError("configuration schema fields must be a list of at most 40 entries")
    out = []
    seen = set()
    for item in fields:
        if not isinstance(item, dict):
            raise PluginError("configuration field must be an object")
        unknown = set(item) - FIELD_KEYS
        if unknown:
            raise PluginError(f"configuration field has unknown keys: {', '.join(sorted(unknown))}")
        key = str(item.get("key") or "")
        if not FIELD_RE.fullmatch(key) or key in seen:
            raise PluginError(f"invalid or duplicate configuration field: {key or '?'}")
        seen.add(key)
        kind = str(item.get("type") or "")
        if kind not in ALLOWED_FIELD_TYPES:
            raise PluginError(f"unsupported configuration field type: {kind or '?'}")
        label = _clean_text(item.get("label"), "configuration label", 80)
        field = {"key": key, "type": kind, "label": label, "secret": bool(item.get("secret", False))}
        help_text = str(item.get("help") or "").strip()
        if help_text:
            field["help"] = help_text[:240]
        if kind == "string":
            maximum = int(item.get("max_length", 120))
            if not 1 <= maximum <= 500:
                raise PluginError(f"invalid max_length for {key}")
            field["max_length"] = maximum
            field["default"] = str(item.get("default", ""))[:maximum]
        elif kind == "boolean":
            field["default"] = bool(item.get("default", False))
        elif kind == "integer":
            minimum = int(item.get("min", -2147483648))
            maximum = int(item.get("max", 2147483647))
            if minimum > maximum:
                raise PluginError(f"invalid integer range for {key}")
            default = int(item.get("default", minimum if minimum > 0 else 0))
            if not minimum <= default <= maximum:
                raise PluginError(f"default for {key} is outside its range")
            field.update({"min": minimum, "max": maximum, "default": default})
        else:
            options = item.get("options")
            if not isinstance(options, list) or not 1 <= len(options) <= 20:
                raise PluginError(f"select field {key} must define 1-20 options")
            clean_options = []
            for option in options:
                text = str(option).strip()
                if not text or len(text) > 80:
                    raise PluginError(f"invalid option in {key}")
                clean_options.append(text)
            default = str(item.get("default", clean_options[0]))
            if default not in clean_options:
                raise PluginError(f"default for {key} is not an allowed option")
            field.update({"options": clean_options, "default": default})
        out.append(field)
    return {"schema": 1, "fields": out}


def validate_manifest(path):
    plugin_dir = Path(path).parent
    raw = _read_json(path)
    if not isinstance(raw, dict):
        raise PluginError("plugin manifest is not valid JSON")
    unknown = set(raw) - MANIFEST_KEYS
    if unknown:
        raise PluginError(f"manifest has unknown keys: {', '.join(sorted(unknown))}")
    if raw.get("api") != API_VERSION:
        raise PluginError(f"plugin API must be {API_VERSION}")
    ident = str(raw.get("id") or "")
    if not ID_RE.fullmatch(ident) or plugin_dir.name != ident:
        raise PluginError("plugin id must match its directory and contain only lowercase letters, numbers, and hyphens")
    name = _clean_text(raw.get("name"), "name", 80)
    version = _clean_text(raw.get("version"), "version", 40)
    description = _clean_text(raw.get("description"), "description", 500)
    trust = str(raw.get("trust") or "")
    kind = str(raw.get("kind") or "")
    provider = str(raw.get("provider") or "")
    if trust not in ALLOWED_TRUST:
        raise PluginError("unsupported plugin trust level")
    if kind not in ALLOWED_KINDS:
        raise PluginError("Plugin API v1 only permits declarative plugins")
    if provider not in ALLOWED_PROVIDERS:
        raise PluginError("unsupported declarative provider")
    caps = raw.get("capabilities")
    if not isinstance(caps, list) or any(str(x) not in ALLOWED_CAPABILITIES for x in caps):
        raise PluginError("manifest contains an unsupported capability")
    caps = list(dict.fromkeys(str(x) for x in caps))
    rf_mode = bool(raw.get("rf_mode", False))
    if rf_mode:
        raise PluginError("RF-mode plugins are not permitted by Plugin API v1")
    service = raw.get("service")
    if service is not None:
        service = str(service)
        if not SERVICE_RE.fullmatch(service) or service != f"ywd-plugin-{ident}.service":
            raise PluginError("plugin service must use the ywd-plugin-<id>.service naming contract")
        raise PluginError("service-backed plugins are not enabled in Plugin API v1")
    try:
        dependencies, hardware = plugin_package_manager.validate_requirements(
            raw.get("dependencies", []), raw.get("hardware", [])
        )
    except plugin_package_manager.PackageStateError as exc:
        raise PluginError(str(exc))
    schema_name = str(raw.get("config_schema") or "")
    schema = validate_schema(plugin_dir, schema_name)
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
        "rf_mode": rf_mode,
        "service": None,
        "dependencies": dependencies,
        "hardware": hardware,
        "config_schema": schema_name,
        "schema": schema,
        "directory": plugin_dir,
    }
