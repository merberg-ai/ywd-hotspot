#!/usr/bin/env python3
"""Privileged SSH identity/client-key helper for the locked WebUI.

Server identity export reads only OpenSSH host identity files from /etc/ssh.
Client enrollment creates a fresh Ed25519 login key for one existing normal
local user, installs only the public key into that user's authorized_keys, and
returns the private/public pair once. The generated private client key is never
stored persistently on the hotspot.
"""
from __future__ import annotations

import base64
import io
import json
import os
import pwd
import re
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SSH_DIR = Path("/etc/ssh")
HOME_ROOT = Path("/home")
HOST_PRIVATE_RE = re.compile(r"^ssh_host_[A-Za-z0-9_-]+_key$")
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
MAX_FILE = 128 * 1024
MAX_TOTAL = 512 * 1024
MAX_AUTHORIZED_KEYS = 1024 * 1024


def _safe_file(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"SSH key is not a regular file: {path.name}")
    size = path.stat().st_size
    if size <= 0 or size > MAX_FILE:
        raise ValueError(f"SSH key has an invalid size: {path.name}")
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


def _archive(filename: str, readme_name: str, readme: bytes, rows: list[tuple[str, bytes, int, int]]) -> dict:
    total = len(readme) + sum(len(data) for _name, data, _mode, _mtime in rows)
    if total > MAX_TOTAL:
        raise ValueError("SSH key export exceeds the safety size limit")
    buf = io.BytesIO()
    now = int(datetime.now(timezone.utc).timestamp())
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        _add_bytes(tf, readme_name, readme, 0o600, now)
        for name, data, mode, mtime in rows:
            _add_bytes(tf, name, data, mode, mtime)
    archive = buf.getvalue()
    if not archive or len(archive) > MAX_TOTAL:
        raise ValueError("SSH key archive exceeds the safety size limit")
    return {
        "ok": True,
        "filename": filename,
        "archive_b64": base64.b64encode(archive).decode("ascii"),
    }


def export_host_keys() -> dict:
    if os.geteuid() != 0:
        raise PermissionError("root required")
    if not SSH_DIR.is_dir():
        raise ValueError("/etc/ssh is unavailable")

    rows: list[tuple[str, bytes, int, int]] = []
    for private in sorted(SSH_DIR.iterdir(), key=lambda p: p.name):
        if not HOST_PRIVATE_RE.fullmatch(private.name):
            continue
        rows.append((f"etc/ssh/{private.name}", _safe_file(private), 0o600, int(private.stat().st_mtime)))
        public = SSH_DIR / f"{private.name}.pub"
        if public.exists():
            rows.append((f"etc/ssh/{public.name}", _safe_file(public), 0o644, int(public.stat().st_mtime)))

    if not rows:
        raise ValueError("no SSH server identity keys were found")

    created = datetime.now(timezone.utc).replace(microsecond=0)
    hostname = re.sub(r"[^A-Za-z0-9._-]+", "-", socket.gethostname()).strip("-") or "ywd-hotspot"
    stamp = created.strftime("%Y%m%d-%H%M%S")
    exported_names = [Path(name).name for name, _data, _mode, _mtime in rows]
    readme = (
        "YWD-Hotspot SSH SERVER IDENTITY key export\n"
        f"Created: {created.isoformat().replace('+00:00', 'Z')}\n"
        f"Hostname: {socket.gethostname()}\n\n"
        "RECOVERY ONLY: these are the SSH SERVER'S identity keys.\n"
        "They preserve the hotspot's SSH server fingerprint after a rebuild.\n"
        "They CANNOT be used by andFTP, Termux, PuTTY, or another SSH client to log in.\n\n"
        "CONFIDENTIAL: this archive contains private server identity keys.\n"
        "Possession of these files can be used to impersonate this SSH server.\n"
        "Keep the archive private and do not publish or attach it to diagnostics.\n\n"
        "To restore on a replacement system:\n"
        "  1. stop the SSH service\n"
        "  2. copy the ssh_host_* files into /etc/ssh/ as root\n"
        "  3. set private key mode 0600 and .pub mode 0644\n"
        "  4. ensure owner/group are root:root\n"
        "  5. start/restart SSH and verify fingerprints\n\n"
        "Exported files:\n  - " + "\n  - ".join(exported_names) + "\n"
    ).encode("utf-8")
    out = _archive(
        f"{hostname}-ssh-server-identity-{stamp}.tar.gz",
        "README-SSH-SERVER-IDENTITY.txt",
        readme,
        rows,
    )
    out.update({
        "files": exported_names,
        "contains_private_keys": True,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "kind": "server-identity",
    })
    return out


def _normal_user(username: str):
    username = str(username or "").strip()
    if not USER_RE.fullmatch(username):
        raise ValueError("enter a valid local Linux username")
    try:
        entry = pwd.getpwnam(username)
    except KeyError:
        raise ValueError(f"local user '{username}' does not exist")
    if entry.pw_uid < 1000:
        raise ValueError("client keys may only be enrolled for normal local users")
    shell = Path(entry.pw_shell or "").name
    if shell in {"false", "nologin"}:
        raise ValueError("selected local user does not have an interactive login shell")
    home = Path(entry.pw_dir).resolve()
    root = HOME_ROOT.resolve()
    if home.parent != root or not home.is_dir():
        raise ValueError("selected user's home directory is outside /home or unavailable")
    return entry, home


def _install_authorized_key(entry, home: Path, public_line: str) -> None:
    ssh_dir = home / ".ssh"
    if ssh_dir.exists() and (ssh_dir.is_symlink() or not ssh_dir.is_dir()):
        raise ValueError("user .ssh path is not a normal directory")
    if not ssh_dir.exists():
        ssh_dir.mkdir(mode=0o700)
    os.chmod(ssh_dir, 0o700)
    os.chown(ssh_dir, entry.pw_uid, entry.pw_gid)

    auth = ssh_dir / "authorized_keys"
    if auth.exists():
        if auth.is_symlink() or not auth.is_file():
            raise ValueError("authorized_keys is not a normal file")
        if auth.stat().st_size > MAX_AUTHORIZED_KEYS:
            raise ValueError("authorized_keys is unexpectedly large")
        existing = auth.read_text(encoding="utf-8", errors="replace")
    else:
        existing = ""

    pub = public_line.strip()
    if not pub.startswith("ssh-ed25519 "):
        raise ValueError("generated SSH public key is invalid")
    if pub not in {line.strip() for line in existing.splitlines()}:
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(auth, flags, 0o600)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise ValueError("authorized_keys is not a regular file")
            if existing and not existing.endswith("\n"):
                os.write(fd, b"\n")
            os.write(fd, (pub + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    os.chmod(auth, 0o600)
    os.chown(auth, entry.pw_uid, entry.pw_gid)


def create_client_key(payload: dict) -> dict:
    if os.geteuid() != 0:
        raise PermissionError("root required")
    if not shutil.which("ssh-keygen"):
        raise ValueError("ssh-keygen is unavailable")

    username = str(payload.get("username") or "").strip()
    entry, home = _normal_user(username)
    created = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = created.strftime("%Y%m%d-%H%M%S")
    hostname = re.sub(r"[^A-Za-z0-9._-]+", "-", socket.gethostname()).strip("-") or "ywd-hotspot"
    comment = f"ywd-hotspot-client:{hostname}:{username}:{stamp}"

    with tempfile.TemporaryDirectory(prefix="ywd-ssh-client-") as td:
        key_path = Path(td) / "ywd_hotspot_client_ed25519"
        proc = subprocess.run(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", comment, "-f", str(key_path)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=False,
        )
        if proc.returncode != 0:
            raise ValueError((proc.stderr or "ssh-keygen failed").strip()[:500])
        private = _safe_file(key_path)
        public = _safe_file(Path(str(key_path) + ".pub"))
        public_line = public.decode("utf-8", "strict").strip()
        _install_authorized_key(entry, home, public_line)

        fp = subprocess.run(
            ["ssh-keygen", "-lf", str(key_path) + ".pub"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=False,
        )
        fingerprint = (fp.stdout or "").strip()[:300]

        readme = (
            "YWD-Hotspot SSH CLIENT LOGIN key\n"
            f"Created: {created.isoformat().replace('+00:00', 'Z')}\n"
            f"Hotspot: {socket.gethostname()}\n"
            f"Linux user: {username}\n"
            f"Fingerprint: {fingerprint or 'unavailable'}\n\n"
            "USE THIS KEY TO LOG IN FROM AN SSH/SFTP CLIENT.\n"
            "For andFTP/SFTP select ywd_hotspot_client_ed25519 as the PRIVATE client key,\n"
            f"set username to {username}, host to this hotspot, and port to 22.\n\n"
            "The matching public key has already been added to:\n"
            f"  {home}/.ssh/authorized_keys\n\n"
            "The private key is NOT retained by YWD-Hotspot after this response.\n"
            "Keep it private. Anyone with this unencrypted private key can authenticate\n"
            f"as {username} while its matching public line remains authorized.\n\n"
            "To revoke this key, remove the authorized_keys line ending with:\n"
            f"  {comment}\n"
        ).encode("utf-8")

        rows = [
            ("ywd_hotspot_client_ed25519", private, 0o600, int(created.timestamp())),
            ("ywd_hotspot_client_ed25519.pub", public, 0o644, int(created.timestamp())),
        ]
        out = _archive(
            f"{hostname}-{username}-ssh-client-login-{stamp}.tar.gz",
            "README-SSH-CLIENT-LOGIN.txt",
            readme,
            rows,
        )

    out.update({
        "username": username,
        "fingerprint": fingerprint,
        "authorized_key_comment": comment,
        "contains_private_keys": True,
        "private_key_retained": False,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "kind": "client-login",
    })
    return out


def _payload() -> dict:
    raw = sys.stdin.buffer.read(4096)
    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON payload") from exc
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    return payload


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    payload = _payload()
    if action == "ssh-keys-export":
        out = export_host_keys()
    elif action == "ssh-client-key-create":
        out = create_client_key(payload)
    else:
        raise SystemExit("usage: ssh_keys_admin.py {ssh-keys-export|ssh-client-key-create}")
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:800]}, separators=(",", ":")))
        raise SystemExit(1)
