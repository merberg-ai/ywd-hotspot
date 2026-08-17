#!/usr/bin/env python3
"""Build a strict .ywdplugin archive, optionally signed with Ed25519/OpenSSL."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
MAX_FILES = 30
MAX_FILE = 512 * 1024


def die(msg):
    raise SystemExit(msg)


def main():
    ap = argparse.ArgumentParser(description="Build a YWD-Hotspot .ywdplugin package")
    ap.add_argument("source", help="plugin source directory (flat files only)")
    ap.add_argument("output", help="output .ywdplugin path")
    ap.add_argument("--sign-key", help="Ed25519 private key PEM")
    ap.add_argument("--key-id", help="trusted key id corresponding to <key-id>.pem on hotspot")
    ap.add_argument("--publisher", default="", help="optional publisher display name")
    args = ap.parse_args()

    src = Path(args.source).resolve(); out = Path(args.output)
    if not src.is_dir(): die("source directory not found")
    if out.suffix.lower() != ".ywdplugin": die("output must end in .ywdplugin")
    plugin_path = src / "plugin.json"
    try: plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
    except Exception: die("plugin.json is missing or invalid")
    if not isinstance(plugin, dict): die("plugin.json must contain an object")
    ident = str(plugin.get("id") or ""); kind = str(plugin.get("kind") or "")
    if not ID_RE.fullmatch(ident): die("invalid plugin id")
    if kind not in {"declarative", "service"}: die("plugin kind must be declarative or service")
    if kind == "service" and not args.sign_key: die("service plugins must be signed")
    if bool(args.sign_key) != bool(args.key_id): die("--sign-key and --key-id must be supplied together")
    if args.key_id and not KEY_RE.fullmatch(args.key_id): die("invalid key id")

    files = []
    for path in sorted(src.iterdir(), key=lambda p: p.name):
        if path.is_dir() or path.is_symlink(): die("package v1 permits regular files at source root only")
        if path.name in {"ywdplugin.json", "signature.ed25519"}: die(f"reserved filename in source: {path.name}")
        if path.stat().st_size > MAX_FILE: die(f"file exceeds {MAX_FILE} bytes: {path.name}")
        files.append(path)
    if not files or len(files) > MAX_FILES: die(f"source must contain 1-{MAX_FILES} files")
    if "plugin.json" not in {p.name for p in files}: die("plugin.json is required")

    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    package = {"format":"ywdplugin","version":1,"id":ident,"files":hashes}
    if args.publisher: package["publisher"] = args.publisher[:120]
    if args.sign_key: package["signature"] = {"algorithm":"ed25519","key_id":args.key_id}
    manifest_raw = (json.dumps(package, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

    signature = None
    if args.sign_key:
        key = Path(args.sign_key)
        if not key.is_file(): die("signing key not found")
        with tempfile.TemporaryDirectory(prefix="ywdplugin-sign-") as td:
            m = Path(td) / "manifest"; s = Path(td) / "signature"
            m.write_bytes(manifest_raw)
            p = subprocess.run(["openssl","pkeyutl","-sign","-inkey",str(key),"-rawin","-in",str(m),"-out",str(s)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, check=False)
            if p.returncode != 0: die((p.stderr or p.stdout or "OpenSSL signing failed").strip())
            raw = s.read_bytes()
            if len(raw) != 64: die("unexpected Ed25519 signature length")
            signature = base64.b64encode(raw) + b"\n"

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("ywdplugin.json", manifest_raw)
        for path in files: zf.write(path, arcname=path.name)
        if signature is not None: zf.writestr("signature.ed25519", signature)
    print(f"Built {out} ({kind}, {'signed '+args.key_id if signature else 'unsigned'})")


if __name__ == "__main__": main()
