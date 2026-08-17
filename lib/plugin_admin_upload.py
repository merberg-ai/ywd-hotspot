#!/usr/bin/env python3
"""Privileged upload/removal actions for persistent .ywdplugin packages."""
from __future__ import annotations

import base64

import plugin_catalog_overlay
import plugin_package_archive
import plugin_service_manager
from plugin_admin_common import resolve_available_plugin, stop_plugin_service


def upload_package(data):
    filename = str(data.get("filename") or "upload.ywdplugin")[:180]
    raw_b64 = data.get("archive_b64")
    if not isinstance(raw_b64, str) or len(raw_b64) > 1500000:
        raise ValueError("plugin archive payload is missing or too large")
    try:
        blob = base64.b64decode(raw_b64, validate=True)
    except Exception:
        raise ValueError("plugin archive payload is not valid base64")
    return plugin_package_archive.install_archive(blob, filename)


def remove_package(data):
    plugin_catalog_overlay.install()
    ident = str(data.get("id") or "")
    plugin, kind = resolve_available_plugin(ident)
    meta = plugin_catalog_overlay.package_meta(ident)
    if not meta:
        raise ValueError("bundled YWD packages cannot be removed from the application; uninstall them instead")
    if kind == "service":
        stop_plugin_service(plugin, disable=True)
        runtime = plugin_service_manager.runtime_state(plugin["service"])
        if runtime["state"] == "active" or runtime["boot"] != "disabled":
            raise RuntimeError("service could not be made inactive/disabled before package removal")
    return plugin_package_archive.remove_archive(ident)
