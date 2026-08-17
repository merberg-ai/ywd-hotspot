#!/usr/bin/env python3
"""Validate and persist uploaded .ywdplugin archives.

The archive format is intentionally small and strict. Package files are flat,
listed by SHA-256 in ywdplugin.json, and extracted by trusted core rather than
zipfile.extractall(). Service code is accepted only when an Ed25519 signature
verifies against an operator-trusted public key.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

import plugin_catalog_overlay
import plugin_manager
import plugin_package_manager
import plugin_service_manager

FORMAT = "ywdplugin"
FORMAT_VERSION = 1
MAX_ARCHIVE = 1024 * 1024
MAX_UNPACKED = 2 * 1024 * 1024
MAX_FILES = 32
MAX_FILE = 512 * 1024
LOCAL_ROOT = plugin_catalog_overlay.LOCAL_ROOT
TRUST_DIR = Path(os.environ.get("YWD_PLUGIN_TRUST_DIR", "/etc/ywd-hotspot/plugin-trust.d"))
KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class PackageArchiveError(ValueError):
    pass


def _read_json(raw, label):
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        raise PackageArchiveError(f"{label} is not valid UTF-8 JSON")
    if not isinstance(obj, dict):
        raise PackageArchiveError(f"{label} must contain a JSON object")
    return obj


def _safe_name(name):
    name = str(name or "")
    if not name or len(name) > 120 or Path(name).name != name or "/" in name or "\\" in name or "\x00" in name:
        raise PackageArchiveError(f"unsafe package filename: {name or '?'}")
    return name


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _existing_ids():
    plugin_catalog_overlay.install()
    ids = set()
    for entry in list(plugin_manager.discover()) + list(plugin_service_manager.discover()):
        ident = str(entry.get("manifest", {}).get("id") or "")
        if plugin_manager.ID_RE.fullmatch(ident):
            ids.add(ident)
    return ids


def _verify_signature(manifest_raw, manifest):
    sigdoc = manifest.get("signature")
    if sigdoc is None:
        return {"status": "unsigned", "key_id": None, "algorithm": None}
    if not isinstance(sigdoc, dict) or set(sigdoc) != {"algorithm", "key_id"}:
        raise PackageArchiveError("signature metadata must contain only algorithm and key_id")
    algorithm = str(sigdoc.get("algorithm") or "").lower()
    key_id = str(sigdoc.get("key_id") or "")
    if algorithm != "ed25519":
        raise PackageArchiveError("only Ed25519 plugin signatures are supported")
    if not KEY_RE.fullmatch(key_id):
        raise PackageArchiveError("invalid plugin signing key id")
    key = TRUST_DIR / f"{key_id}.pem"
    if not key.is_file() or key.is_symlink() or key.stat().st_size > 16384:
        raise PackageArchiveError(f"plugin signing key is not trusted on this hotspot: {key_id}")
    return {"status": "needs-signature", "key_id": key_id, "algorithm": algorithm, "key": key}


def inspect_archive(blob: bytes, filename="upload.ywdplugin"):
    if not isinstance(blob, (bytes, bytearray)) or not blob:
        raise PackageArchiveError("plugin archive is empty")
    if len(blob) > MAX_ARCHIVE:
        raise PackageArchiveError("plugin archive exceeds the 1 MiB upload limit")
    if not str(filename).lower().endswith(".ywdplugin"):
        raise PackageArchiveError("plugin filename must end in .ywdplugin")
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob), "r")
    except Exception:
        raise PackageArchiveError("plugin archive is not a valid ZIP container")
    with zf:
        infos = zf.infolist()
        if not 1 <= len(infos) <= MAX_FILES:
            raise PackageArchiveError(f"plugin archive must contain 1-{MAX_FILES} files")
        names = []
        total = 0
        payloads = {}
        for info in infos:
            name = _safe_name(info.filename)
            if name in names:
                raise PackageArchiveError(f"duplicate package filename: {name}")
            names.append(name)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise PackageArchiveError("plugin archives may not contain symbolic links")
            if info.is_dir():
                raise PackageArchiveError("plugin archive v1 uses files at archive root only")
            if info.flag_bits & 0x1:
                raise PackageArchiveError("encrypted ZIP entries are not supported")
            if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise PackageArchiveError(f"unsupported ZIP compression method for {name}")
            if info.file_size < 0 or info.file_size > MAX_FILE:
                raise PackageArchiveError(f"package file is too large: {name}")
            total += info.file_size
            if total > MAX_UNPACKED:
                raise PackageArchiveError("plugin archive expands beyond the 2 MiB limit")
            # Bound the decompressor itself rather than trusting only the ZIP
            # central-directory size. This keeps a malformed compressed stream
            # from allocating an unbounded output before our size check runs.
            try:
                with zf.open(info, "r") as stream:
                    raw = stream.read(MAX_FILE + 1)
            except Exception as exc:
                raise PackageArchiveError(f"could not safely read package file {name}: {exc}")
            if len(raw) > MAX_FILE:
                raise PackageArchiveError(f"package file expands beyond the {MAX_FILE}-byte limit: {name}")
            if len(raw) != info.file_size:
                raise PackageArchiveError(f"package file size mismatch: {name}")
            payloads[name] = raw

    if "ywdplugin.json" not in payloads or "plugin.json" not in payloads:
        raise PackageArchiveError("archive must contain ywdplugin.json and plugin.json")
    pkg_raw = payloads["ywdplugin.json"]
    package = _read_json(pkg_raw, "ywdplugin.json")
    allowed_keys = {"format", "version", "id", "files", "signature", "publisher"}
    unknown = set(package) - allowed_keys
    if unknown:
        raise PackageArchiveError(f"ywdplugin.json has unknown keys: {', '.join(sorted(unknown))}")
    if package.get("format") != FORMAT or package.get("version") != FORMAT_VERSION:
        raise PackageArchiveError("unsupported .ywdplugin format/version")
    ident = str(package.get("id") or "")
    if not plugin_manager.ID_RE.fullmatch(ident):
        raise PackageArchiveError("invalid package id")
    plugin_raw = _read_json(payloads["plugin.json"], "plugin.json")
    if str(plugin_raw.get("id") or "") != ident:
        raise PackageArchiveError("package id does not match plugin.json")
    kind = str(plugin_raw.get("kind") or "")
    if kind not in {"declarative", "service"}:
        raise PackageArchiveError("uploaded plugin kind must be declarative or service")
    if str(plugin_raw.get("trust") or "") != "experimental":
        raise PackageArchiveError("uploaded plugins must declare trust as experimental")

    files = package.get("files")
    if not isinstance(files, dict) or not files or len(files) > MAX_FILES - 1:
        raise PackageArchiveError("ywdplugin.json files must be a non-empty hash map")
    clean_files = {}
    for raw_name, raw_hash in files.items():
        name = _safe_name(raw_name)
        digest = str(raw_hash or "").lower().removeprefix("sha256:")
        if not HEX_RE.fullmatch(digest):
            raise PackageArchiveError(f"invalid SHA-256 for {name}")
        if name in {"ywdplugin.json", "signature.ed25519"}:
            raise PackageArchiveError(f"{name} is package metadata and must not appear in files")
        if name not in payloads:
            raise PackageArchiveError(f"listed package file is missing: {name}")
        actual = _digest(payloads[name])
        if actual != digest:
            raise PackageArchiveError(f"SHA-256 mismatch for {name}")
        clean_files[name] = digest
    extras = set(payloads) - set(clean_files) - {"ywdplugin.json", "signature.ed25519"}
    if extras:
        raise PackageArchiveError(f"archive contains unlisted files: {', '.join(sorted(extras))}")
    if "plugin.json" not in clean_files:
        raise PackageArchiveError("plugin.json must be hash-listed")

    signature = _verify_signature(pkg_raw, package)
    if signature["status"] == "needs-signature":
        sig_raw = payloads.get("signature.ed25519")
        if not sig_raw:
            raise PackageArchiveError("signed package is missing signature.ed25519")
        try:
            sig = base64.b64decode(sig_raw.strip(), validate=True)
        except Exception:
            raise PackageArchiveError("signature.ed25519 is not valid base64")
        if len(sig) != 64:
            raise PackageArchiveError("Ed25519 signature must be 64 bytes")
        with tempfile.TemporaryDirectory(prefix="ywd-plugin-sign-") as td:
            data_path = Path(td) / "manifest"
            sig_path = Path(td) / "signature"
            data_path.write_bytes(pkg_raw)
            sig_path.write_bytes(sig)
            p = subprocess.run([
                "openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(signature["key"]),
                "-rawin", "-in", str(data_path), "-sigfile", str(sig_path),
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, check=False)
        if p.returncode != 0:
            raise PackageArchiveError("plugin signature verification failed")
        signature = {"status": "verified", "key_id": signature["key_id"], "algorithm": "ed25519"}
    elif "signature.ed25519" in payloads:
        raise PackageArchiveError("signature.ed25519 is present but ywdplugin.json has no signature metadata")

    if kind == "service" and signature["status"] != "verified":
        raise PackageArchiveError("uploaded service plugins require a trusted Ed25519 signature")
    if ident in _existing_ids():
        raise PackageArchiveError(f"plugin id is already available: {ident}")

    return {
        "id": ident,
        "kind": kind,
        "package": package,
        "plugin": plugin_raw,
        "payloads": payloads,
        "files": clean_files,
        "signature": signature,
        "filename": Path(str(filename)).name[:160],
    }


def install_archive(blob: bytes, filename="upload.ywdplugin"):
    info = inspect_archive(blob, filename)
    ident = info["id"]
    LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
    os.chmod(LOCAL_ROOT, 0o755)
    with tempfile.TemporaryDirectory(prefix="ywd-plugin-stage-", dir=str(LOCAL_ROOT.parent)) as td:
        stage = Path(td) / ident
        stage.mkdir(mode=0o755)
        for name in info["files"]:
            raw = info["payloads"][name]
            path = stage / name
            path.write_bytes(raw)
            os.chmod(path, 0o644)
        plugin_catalog_overlay.install()
        if info["kind"] == "declarative":
            manifest = plugin_manager.validate_manifest(stage / "plugin.json")
        else:
            manifest = plugin_service_manager.validate_manifest(stage / "plugin.json")
        meta = {
            "schema": 1,
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "id": ident,
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
        (stage / plugin_catalog_overlay.META_NAME).write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(stage / plugin_catalog_overlay.META_NAME, 0o644)
        target = LOCAL_ROOT / ident
        if target.exists() or target.is_symlink():
            raise PackageArchiveError("target plugin package already exists")
        os.replace(stage, target)
    return {"ok": True, "id": ident, "kind": info["kind"], "installed": False, "signature": info["signature"], "source": "uploaded"}


def remove_archive(ident):
    ident = str(ident or "")
    if not plugin_manager.ID_RE.fullmatch(ident):
        raise PackageArchiveError("invalid plugin id")
    if plugin_package_manager.is_installed(ident):
        raise PackageArchiveError("uninstall the plugin before removing its package")
    target = LOCAL_ROOT / ident
    try:
        resolved = target.resolve(strict=True)
    except FileNotFoundError:
        raise PackageArchiveError("uploaded plugin package is not present")
    try:
        if resolved.parent != LOCAL_ROOT.resolve():
            raise PackageArchiveError("refusing to remove a package outside the local plugin catalog")
    except PackageArchiveError:
        raise
    except Exception:
        raise PackageArchiveError("invalid local plugin package path")
    shutil.rmtree(resolved)
    return {"ok": True, "id": ident, "removed": True}
