#!/usr/bin/env python3
"""Activation/config/runtime mutations for installed YWD-Hotspot plugins."""
from __future__ import annotations

import plugin_manager
import plugin_service_manager
from plugin_admin_common import atomic_json, all_entries, requirement_failure, resolve_plugin, run_systemctl, stop_plugin_service


def set_system(data):
    enabled = data.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be true or false")
    state = plugin_manager.read_state()
    disabled_plugins = []
    if not enabled:
        for entry in all_entries():
            if not entry.get("valid"):
                continue
            manifest = entry["manifest"]
            ident = manifest.get("id")
            desired = bool((state.get("plugins", {}).get(ident) or {}).get("enabled", False))
            if desired:
                disabled_plugins.append(ident)
            if manifest.get("service"):
                stop_plugin_service(manifest, disable=True)
        for ident in list(state.setdefault("plugins", {})):
            state["plugins"][ident] = {"enabled": False}
    state["enabled"] = enabled
    atomic_json(plugin_manager.STATE, state)
    return {"ok": True, "enabled": enabled, "disabled_plugins": disabled_plugins}


def set_plugin(data):
    ident = str(data.get("id") or "")
    enabled = data.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be true or false")
    plugin, kind = resolve_plugin(ident)
    state = plugin_manager.read_state()
    if enabled and not state.get("enabled"):
        raise ValueError("enable the plugin subsystem first")
    if enabled:
        _checks, failure = requirement_failure(plugin)
        if failure:
            raise ValueError(failure)
    if kind == "service":
        if enabled:
            run_systemctl("enable", "--now", plugin["service"])
        else:
            stop_plugin_service(plugin, disable=True)
    state.setdefault("plugins", {})[ident] = {"enabled": enabled}
    atomic_json(plugin_manager.STATE, state)
    return {"ok": True, "id": ident, "enabled": enabled, "service": plugin.get("service")}


def save_config(data):
    ident = str(data.get("id") or "")
    plugin, kind = resolve_plugin(ident)
    config = data.get("config")
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    clean = plugin_manager.normalize_config(plugin, config)
    atomic_json(plugin_manager.config_path(ident), clean)
    restart_required = False
    if kind == "service":
        restart_required = plugin_service_manager.runtime_state(plugin["service"]).get("state") == "active"
    return {
        "ok": True,
        "id": ident,
        "config": plugin_manager.public_config(plugin, clean),
        "restart_required": restart_required,
    }


def runtime_action(data):
    ident = str(data.get("id") or "")
    action = str(data.get("action") or "")
    if action not in {"start", "stop", "restart"}:
        raise ValueError("runtime action must be start, stop, or restart")
    plugin = plugin_service_manager.get_plugin(ident)
    state = plugin_manager.read_state()
    if not state.get("enabled"):
        raise ValueError("plugin subsystem is disabled")
    if not bool((state.get("plugins", {}).get(ident) or {}).get("enabled", False)):
        raise ValueError("enable the service plugin first")
    if action in {"start", "restart"}:
        _checks, failure = requirement_failure(plugin)
        if failure:
            raise ValueError(failure)
    run_systemctl(action, plugin["service"])
    return {
        "ok": True,
        "id": ident,
        "action": action,
        "service": plugin["service"],
        "runtime": plugin_service_manager.runtime_state(plugin["service"]),
    }
