#!/usr/bin/env python3
"""Privileged SSH runtime/key helper for the locked YWD-Hotspot WebUI.

Public YWD-Hotspot OS images intentionally ship with the SSH server disabled.
The authenticated dashboard may explicitly enable/disable SSH after first boot,
but YWD always enforces public-key-only authentication: no SSH passwords and no
root SSH login. Client enrollment creates a fresh Ed25519 key for one existing
normal local user, installs only the public key into that user's authorized_keys,
and returns the private/public pair once. The generated private client key is
never stored persistently on the hotspot.
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
SSHD_DROPIN_DIR = SSH_DIR / "sshd_config.d"
SSHD_DROPIN = SSHD_DROPIN_DIR / "90-ywd-hotspot.conf"
HOME_ROOT = Path("/home")
HOST_PRIVATE_RE = re.compile(r"^ssh_host_[A-Za-z0-9_-]+_key$")
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
MAX_FILE = 128 * 1024
MAX_TOTAL = 512 * 1024
MAX_AUTHORIZED_KEYS = 1024 * 1024
SSH_UNIT = "ssh.service"
SSH_PORT = 22

YWD_SSH_POLICY = """# Managed by YWD-Hotspot. Local edits may be replaced.
# SSH remains public-key only whenever enabled from the YWD dashboard.
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PermitEmptyPasswords no
PermitRootLogin no
AuthenticationMethods publickey
"""


def _run(args, timeout=20, check=False):
    proc = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"command failed: {args[0]}").strip()[:800])
    return proc


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


def _service_state() -> tuple[bool, bool]:
    active = _run(["systemctl", "is-active", "--quiet", SSH_UNIT], 5).returncode == 0
    enabled = _run(["systemctl", "is-enabled", "--quiet", SSH_UNIT], 5).returncode == 0
    return active, enabled


def _authorized_key_count(username: str = "ywd") -> int:
    try:
        entry = pwd.getpwnam(username)
    except KeyError:
        return 0
    auth = Path(entry.pw_dir) / ".ssh" / "authorized_keys"
    if not auth.is_file() or auth.is_symlink() or auth.stat().st_size > MAX_AUTHORIZED_KEYS:
        return 0
    try:
        return sum(1 for line in auth.read_text(encoding="utf-8", errors="replace").splitlines()
                   if line.strip() and not line.lstrip().startswith("#"))
    except Exception:
        return 0


def ssh_status() -> dict:
    active, enabled = _service_state()
    installed = bool(shutil.which("sshd")) and SSH_DIR.is_dir()
    policy_managed = False
    try:
        policy_managed = SSHD_DROPIN.is_file() and SSHD_DROPIN.read_text(encoding="utf-8") == YWD_SSH_POLICY
    except Exception:
        policy_managed = False
    host_keys = 0
    if SSH_DIR.is_dir():
        try:
            host_keys = sum(1 for p in SSH_DIR.iterdir() if HOST_PRIVATE_RE.fullmatch(p.name) and p.is_file())
        except Exception:
            pass
    return {
        "ok": True,
        "installed": installed,
        "active": active,
        "enabled_at_boot": enabled,
        "port": SSH_PORT,
        "authentication": "public-key-only",
        "password_authentication": False,
        "root_login": False,
        "policy_managed": policy_managed,
        "host_key_count": host_keys,
        "login_user": "ywd",
        "authorized_key_count": _authorized_key_count("ywd"),
    }


def _install_public_key_policy() -> None:
    if os.geteuid() != 0:
        raise PermissionError("root required")
    if not shutil.which("sshd"):
        raise ValueError("OpenSSH server is not installed")
    SSHD_DROPIN_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(SSHD_DROPIN_DIR, 0o755)
    tmp = SSHD_DROPIN.with_name(SSHD_DROPIN.name + ".tmp")
    tmp.write_text(YWD_SSH_POLICY, encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.chown(tmp, 0, 0)
    os.replace(tmp, SSHD_DROPIN)
    _run(["/usr/sbin/sshd", "-t"], 10, check=True)


def configure_ssh(payload: dict) -> dict:
    if os.geteuid() != 0:
        raise PermissionError("root required")
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be true or false")

    if enabled:
        _install_public_key_policy()
        _run(["systemctl", "enable", "--now", SSH_UNIT], 20, check=True)
    else:
        # Keep host identity and authorized_keys intact. Disabling SSH closes the
        # listener and boot activation without destroying credentials the user
        # may want to re-enable later.
        _run(["systemctl", "disable", "--now", SSH_UNIT], 20, check=False)

    out = ssh_status()
    out["changed"] = True
    out["message"] = (
        "SSH enabled in public-key-only mode" if enabled
        else "SSH disabled; saved keys were preserved"
    )
    return out


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
            "If SSH is disabled in Settings, enable SSH Access before connecting.\n\n"
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
        "ssh": ssh_status(),
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
    if action == "ssh-status":
        out = ssh_status()
    elif action == "ssh-configure":
        out = configure_ssh(payload)
    elif action == "ssh-keys-export":
        out = export_host_keys()
    elif action == "ssh-client-key-create":
        out = create_client_key(payload)
    else:
        raise SystemExit(
            "usage: ssh_keys_admin.py {ssh-status|ssh-configure|ssh-keys-export|ssh-client-key-create}"
        )
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:800]}, separators=(",", ":")))
        raise SystemExit(1)
