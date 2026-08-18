#!/usr/bin/env python3
"""Privileged SSH host-key export helper for the locked WebUI.

This helper exports only OpenSSH host identity files from /etc/ssh. It does not
read user home directories, authorized_keys, client keys, plugin signing keys,
or arbitrary paths. The caller must already have passed the dashboard control
authentication gate before reaching this narrow sudo action.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import socket
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

SSH_DIR = Path("/etc/ssh")
PRIVATE_RE = re.compile(r"^ssh_host_[A-Za-z0-9_-]+_key$")
MAX_FILE = 128 * 1024
MAX_TOTAL = 512 * 1024


def _safe_file(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"SSH host key is not a regular file: {path.name}")
    size = path.stat().st_size
    if size <= 0 or size > MAX_FILE:
        raise ValueError(f"SSH host key has an invalid size: {path.name}")
    return path.read_bytes()


def _add_bytes(tf: tarfile.TarFile, name: str, data: bytes, mode: int, mtime: int) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    info.mode = mode
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = mtime
    tf.addfile(info, io.BytesIO(data))


def export_host_keys() -> dict:
    if os.geteuid() != 0:
        raise PermissionError("root required")
    if not SSH_DIR.is_dir():
        raise ValueError("/etc/ssh is unavailable")

    rows: list[tuple[str, bytes, int, int]] = []
    total = 0
    for private in sorted(SSH_DIR.iterdir(), key=lambda p: p.name):
        if not PRIVATE_RE.fullmatch(private.name):
            continue
        data = _safe_file(private)
        total += len(data)
        rows.append((private.name, data, 0o600, int(private.stat().st_mtime)))

        public = SSH_DIR / f"{private.name}.pub"
        if public.exists():
            public_data = _safe_file(public)
            total += len(public_data)
            rows.append((public.name, public_data, 0o644, int(public.stat().st_mtime)))

    if not rows:
        raise ValueError("no SSH host keys were found")
    if total > MAX_TOTAL:
        raise ValueError("SSH host-key export exceeds the safety size limit")

    created = datetime.now(timezone.utc).replace(microsecond=0)
    hostname = re.sub(r"[^A-Za-z0-9._-]+", "-", socket.gethostname()).strip("-") or "ywd-hotspot"
    stamp = created.strftime("%Y%m%d-%H%M%S")
    filename = f"{hostname}-ssh-host-keys-{stamp}.tar.gz"

    exported_names = [name for name, _data, _mode, _mtime in rows]
    restore_note = (
        "YWD-Hotspot SSH host key export\n"
        f"Created: {created.isoformat().replace('+00:00', 'Z')}\n"
        f"Hostname: {socket.gethostname()}\n\n"
        "CONFIDENTIAL: this archive contains SSH PRIVATE HOST KEYS.\n"
        "Possession of these files can be used to impersonate this SSH server.\n"
        "Keep the archive private and do not publish or attach it to diagnostics.\n\n"
        "Contents are stored under etc/ssh/. To restore on a replacement system:\n"
        "  1. stop the SSH service\n"
        "  2. copy the ssh_host_* files into /etc/ssh/ as root\n"
        "  3. set private key mode 0600 and .pub mode 0644\n"
        "  4. ensure owner/group are root:root\n"
        "  5. start/restart the SSH service and verify fingerprints\n\n"
        "Exported files:\n  - " + "\n  - ".join(exported_names) + "\n"
    ).encode("utf-8")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        now = int(created.timestamp())
        _add_bytes(tf, "README-SSH-HOST-KEYS.txt", restore_note, 0o600, now)
        for name, data, mode, mtime in rows:
            _add_bytes(tf, f"etc/ssh/{name}", data, mode, mtime)

    archive = buf.getvalue()
    if not archive or len(archive) > MAX_TOTAL:
        raise ValueError("SSH host-key archive exceeds the safety size limit")

    return {
        "ok": True,
        "filename": filename,
        "archive_b64": base64.b64encode(archive).decode("ascii"),
        "files": exported_names,
        "contains_private_keys": True,
        "created_at": created.isoformat().replace("+00:00", "Z"),
    }


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action != "ssh-keys-export":
        raise SystemExit("usage: ssh_keys_admin.py ssh-keys-export")
    # Consume a small JSON request body so the admin-call contract remains
    # consistent while deliberately ignoring arbitrary caller-supplied paths.
    raw = sys.stdin.buffer.read(4096)
    if raw:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ValueError("invalid JSON payload") from exc
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
    print(json.dumps(export_host_keys(), separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:800]}, separators=(",", ":")))
        raise SystemExit(1)
