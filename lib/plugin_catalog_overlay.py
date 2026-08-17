#!/usr/bin/env python3
"""Persistent uploaded-package overlay for the YWD-Hotspot plugin catalogs.

Built-in packages continue to live under /opt/ywd-hotspot/app/lib. Uploaded
.ywdplugin packages live under /var/lib/ywd-hotspot/plugin-packages and are
added to discovery without modifying the deployed application tree.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

LOCAL_ROOT = Path(os.environ.get("YWD_LOCAL_PLUGIN_ROOT", "/var/lib/ywd-hotspot/plugin-packages"))
META_NAME = ".ywd-package-meta.json"
_INSTALLED = False


def _json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def local_dirs(kind):
    rows = []
    if not LOCAL_ROOT.is_dir():
        return rows
    for directory in sorted((p for p in LOCAL_ROOT.iterdir() if p.is_dir()), key=lambda p: p.name):
        raw = _json(directory / "plugin.json")
        if isinstance(raw, dict) and str(raw.get("kind") or "") == kind:
            rows.append(directory)
    return rows


def package_meta(ident):
    from plugin_manifest import ID_RE
    ident = str(ident or "")
    if not ID_RE.fullmatch(ident):
        return None
    path = LOCAL_ROOT / ident / META_NAME
    raw = _json(path)
    return raw if isinstance(raw, dict) else None


def package_origin(ident, directory=None):
    directory = Path(directory) if directory is not None else None
    try:
        if directory is not None and directory.resolve().is_relative_to(LOCAL_ROOT.resolve()):
            return "uploaded"
    except Exception:
        pass
    return "uploaded" if package_meta(ident) else "builtin"


def decorate_snapshot(snapshot):
    out = snapshot if isinstance(snapshot, dict) else {}
    for item in out.get("plugins", []) if isinstance(out.get("plugins"), list) else []:
        ident = str(item.get("id") or "")
        meta = package_meta(ident)
        if meta:
            item["package_origin"] = "uploaded"
            item["package_filename"] = str(meta.get("filename") or "")[:160]
            item["signature"] = {
                "status": str(meta.get("signature_status") or "unknown")[:40],
                "key_id": str(meta.get("key_id") or "")[:80] or None,
                "algorithm": str(meta.get("algorithm") or "")[:40] or None,
            }
        else:
            item["package_origin"] = "builtin"
            item["signature"] = {"status": "builtin", "key_id": "ywd-core", "algorithm": None}
    return out


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    import plugin_manager
    import plugin_service_manager

    builtin_decl = plugin_manager.discover
    builtin_service = plugin_service_manager.discover

    def decl_discover():
        rows = list(builtin_decl())
        seen = {str(x.get("manifest", {}).get("id") or "") for x in rows}
        for directory in local_dirs("declarative"):
            manifest_path = directory / "plugin.json"
            try:
                manifest = plugin_manager.validate_manifest(manifest_path)
                ident = manifest["id"]
                if ident in seen:
                    continue
                rows.append({"valid": True, "manifest": manifest, "error": None})
                seen.add(ident)
            except Exception as exc:
                ident = directory.name if plugin_manager.ID_RE.fullmatch(directory.name) else "invalid-package"
                if ident not in seen:
                    rows.append({"valid": False, "manifest": {"id": ident, "name": directory.name, "version": "unknown", "directory": directory}, "error": str(exc)[:500]})
                    seen.add(ident)
        return rows

    plugin_manager.discover = decl_discover

    def service_discover():
        rows = list(builtin_service())
        seen = {str(x.get("manifest", {}).get("id") or "") for x in rows}
        for directory in local_dirs("service"):
            manifest_path = directory / "plugin.json"
            try:
                manifest = plugin_service_manager.validate_manifest(manifest_path)
                ident = manifest["id"]
                if ident in seen:
                    continue
                rows.append({"valid": True, "manifest": manifest, "error": None})
                seen.add(ident)
            except Exception as exc:
                ident = directory.name if plugin_manager.ID_RE.fullmatch(directory.name) else "invalid-package"
                if ident not in seen:
                    rows.append({"valid": False, "manifest": {"id": ident, "name": directory.name, "version": "unknown", "directory": directory}, "error": str(exc)[:500]})
                    seen.add(ident)
        return rows

    plugin_service_manager.discover = service_discover
    _INSTALLED = True
