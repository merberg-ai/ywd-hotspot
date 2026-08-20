#!/usr/bin/env python3
"""Install/uninstall/data-removal actions for first-party YWD-Hotspot plugin packages."""
from __future__ import annotations

import shutil

import plugin_manager
import plugin_package_manager
import plugin_service_manager
from plugin_admin_common import atomic_json, available_ids, requirement_failure, resolve_available_plugin, stop_plugin_service, write_package_map


def install_package(data):
    ident = str(data.get("id") or "")
    plugin, kind = resolve_available_plugin(ident)
    checks, failure = requirement_failure(plugin)
    if failure:
        raise ValueError(f"cannot install {ident}: {failure}")
    packages = plugin_package_manager.package_map(available_ids())
    already = bool(packages.get(ident, False))
    if kind == "service":
        stop_plugin_service(plugin, disable=True)
        runtime = plugin_service_manager.runtime_state(plugin["service"])
        if runtime["state"] == "active" or runtime["boot"] != "disabled":
            raise RuntimeError("service could not be made inactive/disabled before install")
    state = plugin_manager.read_state()
    state.setdefault("plugins", {})[ident] = {"enabled": False}
    atomic_json(plugin_manager.STATE, state)
    packages[ident] = True
    write_package_map(packages)
    return {
        "ok": True,
        "id": ident, "installed": True, "already_installed": already,
        "enabled": False, "requirements": checks,
    }


def uninstall_package(data):
    ident = str(data.get("id") or "")
    plugin, kind = resolve_available_plugin(ident)
    packages = plugin_package_manager.package_map(available_ids())
    was_installed = bool(packages.get(ident, False))
    if kind == "service":
        stop_plugin_service(plugin, disable=True)
        runtime = plugin_service_manager.runtime_state(plugin["service"])
        if runtime["state"] == "active" or runtime["boot"] != "disabled":
            raise RuntimeError("service could not be stopped/disabled; package remains installed")
    state = plugin_manager.read_state()
    state.setdefault("plugins", {})[ident] = {"enabled": False}
    atomic_json(plugin_manager.STATE, state)
    packages[ident] = False
    write_package_map(packages)
    return {
        "ok": True, "id": ident, "installed": False, "was_installed": was_installed,
        "config_preserved": plugin_manager.config_path(ident).exists(),
        "data_preserved": plugin_package_manager.data_path(ident).exists(),
    }


def remove_plugin_data(data):
    ident = str(data.get("id") or "")
    plugin, kind = resolve_available_plugin(ident)
    state = plugin_manager.read_state()
    if bool((state.get("plugins", {}).get(ident) or {}).get("enabled", False)):
        raise ValueError("disable the plugin before removing its data")
    if kind == "service":
        runtime = plugin_service_manager.runtime_state(plugin["service"])
        if runtime["state"] == "active" or runtime["boot"] != "disabled":
            raise ValueError("stop and disable the plugin service before removing its data")
    removed = []
    config = plugin_manager.config_path(ident)
    if config.exists() or config.is_symlink():
        config.unlink()
        removed.append(str(config))
    path = plugin_package_manager.data_path(ident)
    if path.is_symlink() or path.is_file():
        path.unlink()
        removed.append(str(path))
    elif path.is_dir():
        shutil.rmtree(path)
        removed.append(str(path))
    return {"ok": True, "id": ident, "removed": removed, "nothing_to_remove": not removed}
