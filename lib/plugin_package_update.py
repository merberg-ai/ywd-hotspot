#!/usr/bin/env python3
"""Transactional review/apply path for uploaded YWD-Hotspot plugin packages.

Uploads are re-verified on apply. Existing uploaded packages may be replaced only
by the same plugin id + kind. Built-in/core package ids remain immutable.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
import time
from pathlib import Path

import plugin_catalog_overlay
import plugin_manager
import plugin_package_archive
import plugin_package_manager
import plugin_service_manager
import plugin_ui_manager

from plugin_admin_common import (
    atomic_json,
    requirement_failure,
    resolve_available_plugin,
    run_systemctl,
    stop_plugin_service,
)

LOCAL_ROOT = plugin_catalog_overlay.LOCAL_ROOT
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class PluginUpdateError(ValueError):
    pass


def _read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


_ORIGINAL_EXISTING_IDS = plugin_package_archive._existing_ids
_INSPECT_TLS = threading.local()


def _thread_safe_existing_ids():
    ids = set(_ORIGINAL_EXISTING_IDS())
    if getattr(_INSPECT_TLS, "allow_uploaded", False):
        ids = {ident for ident in ids if not plugin_catalog_overlay.package_meta(ident)}
    return ids


# Keep the canonical archive verifier as the authority. The wrapper only changes
# same-thread collision policy during explicit update review/apply calls.
plugin_package_archive._existing_ids = _thread_safe_existing_ids


def _inspect_allow_uploaded(blob: bytes, filename: str):
    """Use the canonical archive verifier while allowing uploaded-package updates.

    Built-in IDs remain visible to the verifier and can never be shadowed.
    Thread-local policy avoids weakening concurrent normal upload validation.
    """
    previous = getattr(_INSPECT_TLS, "allow_uploaded", False)
    _INSPECT_TLS.allow_uploaded = True
    try:
        return plugin_package_archive.inspect_archive(blob, filename)
    finally:
        _INSPECT_TLS.allow_uploaded = previous


def _write_candidate(info, root: Path):
    stage = Path(root) / info["id"]
    stage.mkdir(mode=0o755)
    for name in info["files"]:
        path = stage / name
        path.write_bytes(info["payloads"][name])
        os.chmod(path, 0o644)
    return stage


def _validate_candidate(info, stage: Path):
    kind = info["kind"]
    path = stage / "plugin.json"
    if kind == "declarative":
        return plugin_manager.validate_manifest(path)
    if kind == "service":
        return plugin_service_manager.validate_manifest(path)
    if kind == "ui":
        return plugin_ui_manager.validate_manifest(path)
    raise PluginUpdateError("unsupported plugin kind")


def _semver(value):
    text = str(value or "")
    match = SEMVER_RE.fullmatch(text)
    if not match:
        return None
    pre = match.group(4)
    parts = []
    if pre is not None:
        for token in pre.split("."):
            parts.append(int(token) if token.isdigit() else token)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)), parts if pre is not None else None)


def _compare_semver(current, candidate):
    a, b = _semver(current), _semver(candidate)
    if a is None or b is None:
        return "unordered"
    if a[:3] != b[:3]:
        return "newer" if b[:3] > a[:3] else "older"
    apre, bpre = a[3], b[3]
    if apre is None and bpre is None:
        return "same"
    if apre is None:
        return "older"
    if bpre is None:
        return "newer"
    for left, right in zip(apre, bpre):
        if left == right:
            continue
        if isinstance(left, int) and isinstance(right, int):
            return "newer" if right > left else "older"
        if isinstance(left, int) != isinstance(right, int):
            return "newer" if isinstance(left, int) else "older"
        return "newer" if str(right) > str(left) else "older"
    if len(apre) == len(bpre):
        return "same"
    return "newer" if len(bpre) > len(apre) else "older"


def _public_manifest(manifest):
    return {
        "id": manifest["id"],
        "name": manifest["name"],
        "version": manifest["version"],
        "description": manifest["description"],
        "kind": manifest["kind"],
        "trust": manifest["trust"],
        "provider": manifest.get("provider"),
        "capabilities": list(manifest.get("capabilities") or []),
        "rf_mode": bool(manifest.get("rf_mode", False)),
        "service": manifest.get("service"),
        "dependencies": list(manifest.get("dependencies") or []),
        "hardware": list(manifest.get("hardware") or []),
    }


def _config_plan(manifest):
    path = plugin_manager.config_path(manifest["id"])
    if not path.is_file():
        return {
            "present": False,
            "compatible": True,
            "migration_required": False,
            "added_keys": [],
            "dropped_keys": [],
            "reset_keys": [],
            "clean": None,
        }
    raw = _read_json(path, {})
    if not isinstance(raw, dict):
        raw = {}
    fields = manifest["schema"]["fields"]
    allowed = {field["key"] for field in fields}
    migrated = {}
    reset = []
    added = []
    for field in fields:
        key = field["key"]
        if key not in raw:
            added.append(key)
            migrated[key] = field.get("default")
            continue
        try:
            probe = plugin_manager.normalize_config(manifest, {key: raw[key]})
            migrated[key] = probe[key]
        except Exception:
            migrated[key] = field.get("default")
            reset.append(key)
    dropped = sorted(set(raw) - allowed)
    clean = plugin_manager.normalize_config(manifest, migrated)
    return {
        "present": True,
        "compatible": True,
        "migration_required": bool(added or dropped or reset or clean != raw),
        "added_keys": sorted(added),
        "dropped_keys": dropped,
        "reset_keys": sorted(reset),
        "clean": clean,
    }


def _existing_state(ident):
    meta = plugin_catalog_overlay.package_meta(ident)
    if not meta:
        return None
    try:
        manifest, kind = resolve_available_plugin(ident)
    except Exception:
        manifest = None
        kind = str(meta.get("kind") or "")
    state = plugin_manager.read_state()
    installed = plugin_package_manager.is_installed(ident)
    enabled = bool((state.get("plugins", {}).get(ident) or {}).get("enabled", False))
    return {
        "meta": meta,
        "manifest": manifest,
        "kind": kind,
        "version": str((manifest or {}).get("version") or meta.get("version") or "unknown"),
        "installed": installed,
        "enabled": enabled,
        "system_enabled": bool(state.get("enabled", False)),
        "config_present": plugin_manager.config_path(ident).is_file(),
        "data_present": plugin_package_manager.data_path(ident).exists(),
    }


def review_archive(blob: bytes, filename="upload.ywdplugin"):
    plugin_catalog_overlay.install()
    info = _inspect_allow_uploaded(blob, filename)
    ident = info["id"]
    existing = _existing_state(ident)
    if existing:
        old_key = str(existing["meta"].get("key_id") or "")
        new_key = str(info.get("signature", {}).get("key_id") or "")
        if old_key and new_key != old_key:
            raise PluginUpdateError(
                f"plugin signing key changed ({old_key} -> {new_key or 'unsigned'}); "
                "remove/reinstall explicitly to change publisher trust"
            )

    with tempfile.TemporaryDirectory(prefix="ywd-plugin-review-") as td:
        stage = _write_candidate(info, Path(td))
        candidate = _validate_candidate(info, stage)
        checks, failure = requirement_failure(candidate)
        config = _config_plan(candidate) if existing else {
            "present": False, "compatible": True, "migration_required": False,
            "added_keys": [], "dropped_keys": [], "reset_keys": [], "clean": None,
        }

    if existing and existing["kind"] != candidate["kind"]:
        raise PluginUpdateError(
            f"plugin kind cannot change during update: {existing['kind']} -> {candidate['kind']}"
        )

    current_caps = list((existing or {}).get("manifest", {}).get("capabilities") or [])
    candidate_caps = list(candidate.get("capabilities") or [])
    added_caps = sorted(set(candidate_caps) - set(current_caps))
    removed_caps = sorted(set(current_caps) - set(candidate_caps))

    if not existing:
        relation = "new"
        operation = "install"
    else:
        relation = _compare_semver(existing["version"], candidate["version"])
        operation = {
            "newer": "update",
            "same": "reinstall",
            "older": "downgrade",
            "unordered": "replace",
        }[relation]

    return {
        "ok": True,
        "id": ident,
        "operation": operation,
        "version_relation": relation,
        "candidate": _public_manifest(candidate),
        "current": None if not existing else {
            "version": existing["version"],
            "kind": existing["kind"],
            "installed": existing["installed"],
            "enabled": existing["enabled"],
            "system_enabled": existing["system_enabled"],
            "config_present": existing["config_present"],
            "data_present": existing["data_present"],
            "capabilities": current_caps,
        },
        "signature": info["signature"],
        "requirements": checks,
        "requirements_ok": failure is None,
        "requirements_error": failure,
        "capability_changes": {"added": added_caps, "removed": removed_caps},
        "configuration": {key: value for key, value in config.items() if key != "clean"},
        "source": "uploaded",
    }


def _package_meta(info, manifest):
    return {
        "schema": 1,
        "format": plugin_package_archive.FORMAT,
        "format_version": plugin_package_archive.FORMAT_VERSION,
        "id": info["id"],
        "kind": info["kind"],
        "version": manifest.get("version"),
        "filename": info["filename"],
        "publisher": str(info["package"].get("publisher") or "")[:120],
        "signature_status": info["signature"]["status"],
        "key_id": info["signature"].get("key_id"),
        "algorithm": info["signature"].get("algorithm"),
        "uploaded_at": int(time.time()),
        "files": info["files"],
    }


def _write_meta(stage, info, manifest):
    path = stage / plugin_catalog_overlay.META_NAME
    path.write_text(json.dumps(_package_meta(info, manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o644)


def _restore_service_runtime(manifest, runtime):
    if not manifest or not manifest.get("service") or not runtime:
        return
    unit = manifest["service"]
    boot = str(runtime.get("boot") or "disabled")
    active = str(runtime.get("state") or "inactive") == "active"
    try:
        if boot == "enabled":
            run_systemctl("enable", unit)
        else:
            run_systemctl("disable", unit)
        if active:
            run_systemctl("start", unit)
        else:
            run_systemctl("stop", unit)
    except Exception:
        pass


def apply_archive(blob: bytes, filename="upload.ywdplugin"):
    plugin_catalog_overlay.install()
    review = review_archive(blob, filename)
    if not review["requirements_ok"]:
        raise PluginUpdateError(review["requirements_error"] or "plugin requirements are not satisfied")

    info = _inspect_allow_uploaded(blob, filename)
    ident = info["id"]
    existing = _existing_state(ident)
    if (existing is None) != (review["current"] is None):
        raise PluginUpdateError("plugin package state changed after review; upload/review the package again")

    LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
    os.chmod(LOCAL_ROOT, 0o755)
    work_root = Path(tempfile.mkdtemp(prefix=f".{ident}.apply-", dir=str(LOCAL_ROOT.parent)))
    stage = _write_candidate(info, work_root)
    candidate = _validate_candidate(info, stage)
    _write_meta(stage, info, candidate)

    target = LOCAL_ROOT / ident
    backup = work_root / f"{ident}.previous"
    config_path = plugin_manager.config_path(ident)
    old_config = config_path.read_bytes() if config_path.is_file() else None
    old_state = plugin_manager.read_state()
    old_packages = plugin_package_manager.read_state()
    old_manifest = (existing or {}).get("manifest")
    old_kind = (existing or {}).get("kind")
    old_runtime = None
    if existing and old_kind == "service" and old_manifest:
        old_runtime = plugin_service_manager.runtime_state(old_manifest["service"])

    config_plan = _config_plan(candidate) if existing else {
        "present": False, "clean": None, "migration_required": False,
        "added_keys": [], "dropped_keys": [], "reset_keys": [],
    }

    swapped = False
    try:
        # Quiesce only the plugin being replaced. Core RF/DMR services are untouched.
        if existing:
            temp_state = plugin_manager.read_state()
            temp_state.setdefault("plugins", {})[ident] = {"enabled": False}
            atomic_json(plugin_manager.STATE, temp_state)
            if old_kind == "service" and old_manifest:
                stop_plugin_service(old_manifest, disable=True)
            if not target.exists() or target.is_symlink():
                raise PluginUpdateError("existing uploaded package directory is missing or invalid")
            os.replace(target, backup)

        os.replace(stage, target)
        swapped = True

        packages = dict(old_packages.get("installed") or {}) if old_packages.get("valid") else {}
        packages[ident] = bool(existing["installed"]) if existing else True
        atomic_json(
            plugin_package_manager.PACKAGE_STATE,
            {"schema": 1, "installed": {k: bool(v) for k, v in sorted(packages.items())}},
        )

        if existing and config_plan.get("present") and config_plan.get("clean") is not None:
            atomic_json(config_path, config_plan["clean"])

        final_state = plugin_manager.read_state()
        final_state.setdefault("plugins", {})[ident] = {
            "enabled": bool(existing["enabled"]) if existing else False
        }
        atomic_json(plugin_manager.STATE, final_state)

        if existing and existing["installed"] and existing["enabled"] and existing["system_enabled"] and candidate["kind"] == "service":
            run_systemctl("enable", "--now", candidate["service"])

        if backup.exists():
            shutil.rmtree(backup)

        return {
            **review,
            "applied": True,
            "installed": True if not existing else bool(existing["installed"]),
            "enabled": False if not existing else bool(existing["enabled"]),
            "configuration_migrated": bool(config_plan.get("migration_required")),
        }
    except Exception:
        try:
            if candidate.get("service"):
                stop_plugin_service(candidate, disable=True)
        except Exception:
            pass
        try:
            if swapped and target.exists():
                shutil.rmtree(target)
            if backup.exists():
                os.replace(backup, target)
        except Exception:
            pass
        try:
            atomic_json(plugin_package_manager.PACKAGE_STATE, {"schema": 1, "installed": dict(old_packages.get("installed") or {})})
            atomic_json(plugin_manager.STATE, old_state)
        except Exception:
            pass
        try:
            if old_config is None:
                if config_path.exists():
                    config_path.unlink()
            else:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = config_path.with_name(config_path.name + ".rollback")
                tmp.write_bytes(old_config)
                os.chmod(tmp, 0o640)
                os.replace(tmp, config_path)
        except Exception:
            pass
        _restore_service_runtime(old_manifest, old_runtime)
        raise
    finally:
        shutil.rmtree(work_root, ignore_errors=True)
