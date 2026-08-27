#!/usr/bin/env python3
"""Privileged SSH policy/key/password helper for the locked YWD-Hotspot WebUI.

Factory images still ship with SSH disabled. Key-only remains the recommended
default; password-or-key authentication is an explicit operator opt-in. Root
SSH and keyboard-interactive authentication remain disabled.
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
SSHD = Path("/usr/sbin/sshd")
SSHD_DROPIN_DIR = SSH_DIR / "sshd_config.d"
SSHD_DROPIN = SSHD_DROPIN_DIR / "00-ywd-hotspot.conf"
LEGACY_SSHD_DROPIN = SSHD_DROPIN_DIR / "90-ywd-hotspot.conf"
HOME_ROOT = Path("/home")
HOST_PRIVATE_RE = re.compile(r"^ssh_host_[A-Za-z0-9_-]+_key$")
USER_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
POLICY_MODE_RE = re.compile(r"^# YWD-Auth-Mode: (key-only|password\+key)$", re.MULTILINE)
POLICY_USER_RE = re.compile(r"^# YWD-Login-User: ([a-z_][a-z0-9_-]{0,31})$", re.MULTILINE)
MAX_FILE = 128 * 1024
MAX_TOTAL = 512 * 1024
MAX_AUTHORIZED_KEYS = 1024 * 1024
SSH_UNIT = "ssh.service"
SSH_PORT = 22
AUTH_KEY_ONLY = "key-only"
AUTH_PASSWORD_KEY = "password+key"
AUTH_MODES = {AUTH_KEY_ONLY, AUTH_PASSWORD_KEY}
MIN_PASSWORD_LEN = 10
MAX_PASSWORD_LEN = 128

LEGACY_YWD_SSH_POLICY = """# Managed by YWD-Hotspot. Local edits may be replaced.
# SSH remains public-key only whenever enabled from the YWD dashboard.
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PermitEmptyPasswords no
PermitRootLogin no
AuthenticationMethods publickey
"""


def _run(args, timeout=20, check=False, input_text=None):
    proc = subprocess.run(
        args,
        input=input_text,
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
    return {"ok": True, "filename": filename, "archive_b64": base64.b64encode(archive).decode("ascii")}


def _host_key_paths() -> list[Path]:
    if not SSH_DIR.is_dir():
        return []
    try:
        return [p for p in SSH_DIR.iterdir() if HOST_PRIVATE_RE.fullmatch(p.name) and p.is_file() and not p.is_symlink()]
    except Exception:
        return []


def _service_state() -> tuple[bool, bool]:
    active = _run(["systemctl", "is-active", "--quiet", SSH_UNIT], 5).returncode == 0
    enabled = _run(["systemctl", "is-enabled", "--quiet", SSH_UNIT], 5).returncode == 0
    return active, enabled


def _is_normal_user_entry(entry) -> bool:
    if entry.pw_uid < 1000 or not USER_RE.fullmatch(entry.pw_name or ""):
        return False
    if Path(entry.pw_shell or "").name in {"false", "nologin"}:
        return False
    try:
        home = Path(entry.pw_dir).resolve()
        root = HOME_ROOT.resolve()
    except Exception:
        return False
    return home.parent == root and home.is_dir()


def eligible_login_users() -> list[str]:
    try:
        entries = pwd.getpwall()
    except Exception:
        entries = []
    rows = [entry.pw_name for entry in entries if _is_normal_user_entry(entry)]
    return sorted(set(rows), key=lambda name: (name != "ywd", name))


def suggested_login_user() -> str:
    users = eligible_login_users()
    return "ywd" if "ywd" in users else (users[0] if users else "ywd")


def _normal_user(username: str):
    username = str(username or "").strip()
    if not USER_RE.fullmatch(username):
        raise ValueError("enter a valid local Linux username")
    try:
        entry = pwd.getpwnam(username)
    except KeyError:
        raise ValueError(f"local user '{username}' does not exist")
    if not _is_normal_user_entry(entry):
        raise ValueError("selected SSH user must have UID 1000+, an interactive shell, and a home directory directly under /home")
    return entry, Path(entry.pw_dir).resolve()


def normalize_auth_mode(value) -> str:
    mode = str(value or AUTH_KEY_ONLY).strip().lower()
    if mode not in AUTH_MODES:
        raise ValueError("SSH authentication mode must be key-only or password+key")
    return mode


def _authorized_key_count(username: str = "ywd") -> int:
    try:
        entry = pwd.getpwnam(username)
    except KeyError:
        return 0
    auth = Path(entry.pw_dir) / ".ssh" / "authorized_keys"
    if not auth.is_file() or auth.is_symlink() or auth.stat().st_size > MAX_AUTHORIZED_KEYS:
        return 0
    try:
        return sum(1 for line in auth.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip() and not line.lstrip().startswith("#"))
    except Exception:
        return 0


def build_policy(auth_mode: str, username: str) -> str:
    mode = normalize_auth_mode(auth_mode)
    _normal_user(username)
    lines = [
        "# Managed by YWD-Hotspot. Local edits may be replaced.",
        f"# YWD-Auth-Mode: {mode}",
        f"# YWD-Login-User: {username}",
        "PubkeyAuthentication yes",
        f"PasswordAuthentication {'yes' if mode == AUTH_PASSWORD_KEY else 'no'}",
        "KbdInteractiveAuthentication no",
        "ChallengeResponseAuthentication no",
        "PermitEmptyPasswords no",
        "PermitRootLogin no",
        f"AllowUsers {username}",
    ]
    if mode == AUTH_KEY_ONLY:
        lines.append("AuthenticationMethods publickey")
    return "\n".join(lines) + "\n"


def _read_policy_file(path: Path):
    try:
        if path.is_file() and not path.is_symlink():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return None


def policy_state() -> dict:
    text = _read_policy_file(SSHD_DROPIN)
    if text is not None:
        mode_match = POLICY_MODE_RE.search(text)
        user_match = POLICY_USER_RE.search(text)
        if mode_match and user_match:
            return {"managed": True, "auth_mode": normalize_auth_mode(mode_match.group(1)), "login_user": user_match.group(1)}
    legacy = _read_policy_file(LEGACY_SSHD_DROPIN)
    if legacy == LEGACY_YWD_SSH_POLICY:
        return {"managed": True, "auth_mode": AUTH_KEY_ONLY, "login_user": "ywd"}
    return {"managed": False, "auth_mode": AUTH_KEY_ONLY, "login_user": suggested_login_user()}


def password_status(username: str) -> str:
    try:
        _normal_user(username)
    except Exception:
        return "missing"
    passwd = shutil.which("passwd")
    if not passwd:
        return "unknown"
    proc = _run([passwd, "-S", username], 5)
    fields = (proc.stdout or "").split()
    if proc.returncode != 0 or len(fields) < 2:
        return "unknown"
    code = fields[1].upper()
    if code == "P":
        return "set"
    if code in {"L", "LK"}:
        return "locked"
    if code in {"NP", "N"}:
        return "unset"
    return "unknown"


def ssh_status() -> dict:
    active, enabled = _service_state()
    policy = policy_state()
    users = eligible_login_users()
    username = policy["login_user"]
    exists = username in users
    mode = policy["auth_mode"]
    return {
        "ok": True,
        "installed": SSHD.is_file() and SSH_DIR.is_dir(),
        "active": active,
        "enabled_at_boot": enabled,
        "port": SSH_PORT,
        "authentication": "password+key" if mode == AUTH_PASSWORD_KEY else "public-key-only",
        "auth_mode": mode,
        "password_authentication": mode == AUTH_PASSWORD_KEY,
        "root_login": False,
        "policy_managed": bool(policy["managed"]),
        "host_key_count": len(_host_key_paths()),
        "login_user": username,
        "login_user_exists": exists,
        "suggested_login_user": username if exists else suggested_login_user(),
        "eligible_login_users": users,
        "authorized_key_count": _authorized_key_count(username) if exists else 0,
        "password_status": password_status(username),
    }


def _ensure_unique_host_keys() -> None:
    if _host_key_paths():
        return
    if not shutil.which("ssh-keygen"):
        raise ValueError("ssh-keygen is unavailable")
    _run(["ssh-keygen", "-A"], 30, check=True)
    if not _host_key_paths():
        raise RuntimeError("OpenSSH host-key generation completed without creating server identity keys")


def _effective_sshd() -> dict[str, str]:
    proc = _run([str(SSHD), "-T"], 10, check=True)
    values = {}
    for raw in (proc.stdout or "").splitlines():
        key, sep, value = raw.partition(" ")
        if sep:
            values[key.strip().lower()] = value.strip()
    return values


def _validate_effective_policy(auth_mode: str, username: str) -> None:
    values = _effective_sshd()
    required = {
        "pubkeyauthentication": "yes",
        "passwordauthentication": "yes" if auth_mode == AUTH_PASSWORD_KEY else "no",
        "kbdinteractiveauthentication": "no",
        "permitemptypasswords": "no",
        "permitrootlogin": "no",
    }
    bad = [f"{key}={values.get(key, 'missing')}" for key, wanted in required.items() if values.get(key) != wanted]
    if username not in values.get("allowusers", "").split():
        bad.append(f"allowusers={values.get('allowusers', 'missing')}")
    if auth_mode == AUTH_KEY_ONLY and "publickey" not in values.get("authenticationmethods", "").split():
        bad.append(f"authenticationmethods={values.get('authenticationmethods', 'missing')}")
    if bad:
        raise RuntimeError("effective sshd policy verification failed: " + ", ".join(bad))


def install_policy(auth_mode: str, username: str) -> None:
    if os.geteuid() != 0:
        raise PermissionError("root required")
    if not SSHD.is_file():
        raise ValueError("OpenSSH server is not installed")
    mode = normalize_auth_mode(auth_mode)
    _normal_user(username)
    text = build_policy(mode, username)
    SSHD_DROPIN_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(SSHD_DROPIN_DIR, 0o755)

    previous = _read_policy_file(SSHD_DROPIN)
    legacy = _read_policy_file(LEGACY_SSHD_DROPIN)
    tmp = SSHD_DROPIN.with_name(SSHD_DROPIN.name + ".tmp")
    try:
        if LEGACY_SSHD_DROPIN.exists():
            LEGACY_SSHD_DROPIN.unlink()
        tmp.write_text(text, encoding="utf-8")
        os.chmod(tmp, 0o644)
        os.chown(tmp, 0, 0)
        os.replace(tmp, SSHD_DROPIN)
        _ensure_unique_host_keys()
        _run([str(SSHD), "-t"], 10, check=True)
        _validate_effective_policy(mode, username)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
            if previous is None:
                if SSHD_DROPIN.exists():
                    SSHD_DROPIN.unlink()
            else:
                SSHD_DROPIN.write_text(previous, encoding="utf-8")
                os.chmod(SSHD_DROPIN, 0o644)
                os.chown(SSHD_DROPIN, 0, 0)
            if legacy is not None:
                LEGACY_SSHD_DROPIN.write_text(legacy, encoding="utf-8")
                os.chmod(LEGACY_SSHD_DROPIN, 0o644)
                os.chown(LEGACY_SSHD_DROPIN, 0, 0)
        except Exception:
            pass
        raise


def _install_public_key_policy() -> None:
    install_policy(AUTH_KEY_ONLY, suggested_login_user())


def configure_ssh(payload: dict) -> dict:
    if os.geteuid() != 0:
        raise PermissionError("root required")
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be true or false")
    if enabled:
        current = policy_state()
        mode = normalize_auth_mode(payload.get("auth_mode") or current["auth_mode"])
        username = str(payload.get("login_user") or current["login_user"] or suggested_login_user()).strip()
        install_policy(mode, username)
        _run(["systemctl", "enable", "--now", SSH_UNIT], 20, check=True)
    else:
        _run(["systemctl", "disable", "--now", SSH_UNIT], 20, check=False)
    out = ssh_status()
    out["changed"] = True
    out["message"] = (f"SSH enabled for {out['login_user']} with " + ("password or key authentication" if out["password_authentication"] else "key-only authentication")) if enabled else "SSH disabled; saved credentials and policy were preserved"
    return out


def set_login_password(payload: dict) -> dict:
    if os.geteuid() != 0:
        raise PermissionError("root required")
    username = str(payload.get("username") or "").strip()
    _normal_user(username)
    password = payload.get("password")
    if not isinstance(password, str):
        raise ValueError("password must be a string")
    if len(password) < MIN_PASSWORD_LEN:
        raise ValueError(f"SSH password must be at least {MIN_PASSWORD_LEN} characters")
    if len(password) > MAX_PASSWORD_LEN:
        raise ValueError(f"SSH password must be no more than {MAX_PASSWORD_LEN} characters")
    if any(ch in password for ch in "\r\n\0"):
        raise ValueError("SSH password cannot contain newline or NUL characters")
    chpasswd = shutil.which("chpasswd")
    if not chpasswd:
        raise ValueError("chpasswd is unavailable")
    proc = _run([chpasswd], 15, input_text=f"{username}:{password}\n")
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "could not set SSH login password").strip()[:500])
    return {"ok": True, "changed": True, "username": username, "password_status": password_status(username), "message": f"SSH login password updated for {username}"}


def export_host_keys() -> dict:
    if os.geteuid() != 0:
        raise PermissionError("root required")
    if not SSH_DIR.is_dir():
        raise ValueError("/etc/ssh is unavailable")
    rows = []
    for private in sorted(_host_key_paths(), key=lambda p: p.name):
        rows.append((f"etc/ssh/{private.name}", _safe_file(private), 0o600, int(private.stat().st_mtime)))
        public = SSH_DIR / f"{private.name}.pub"
        if public.exists():
            rows.append((f"etc/ssh/{public.name}", _safe_file(public), 0o644, int(public.stat().st_mtime)))
    if not rows:
        raise ValueError("no SSH server identity keys exist yet; enable SSH once before exporting server identity")
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
        "They CANNOT be used by an SSH/SFTP client as a login credential.\n\n"
        "CONFIDENTIAL: this archive contains private server identity keys.\n"
        "Possession of these files can be used to impersonate this SSH server.\n"
        "Keep the archive private and do not publish or attach it to diagnostics.\n\n"
        "To restore on a replacement system:\n"
        "  1. stop the SSH service\n  2. copy the ssh_host_* files into /etc/ssh/ as root\n"
        "  3. set private key mode 0600 and .pub mode 0644\n  4. ensure owner/group are root:root\n"
        "  5. start/restart SSH and verify fingerprints\n\nExported files:\n  - " + "\n  - ".join(exported_names) + "\n"
    ).encode("utf-8")
    out = _archive(f"{hostname}-ssh-server-identity-{stamp}.tar.gz", "README-SSH-SERVER-IDENTITY.txt", readme, rows)
    out.update({"files": exported_names, "contains_private_keys": True, "created_at": created.isoformat().replace("+00:00", "Z"), "kind": "server-identity"})
    return out


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
    username = str(payload.get("username") or suggested_login_user()).strip()
    entry, home = _normal_user(username)
    created = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = created.strftime("%Y%m%d-%H%M%S")
    hostname = re.sub(r"[^A-Za-z0-9._-]+", "-", socket.gethostname()).strip("-") or "ywd-hotspot"
    comment = f"ywd-hotspot-client:{hostname}:{username}:{stamp}"
    with tempfile.TemporaryDirectory(prefix="ywd-ssh-client-") as td:
        key_path = Path(td) / "ywd_hotspot_client_ed25519"
        proc = subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", comment, "-f", str(key_path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=False)
        if proc.returncode != 0:
            raise ValueError((proc.stderr or "ssh-keygen failed").strip()[:500])
        private = _safe_file(key_path)
        public = _safe_file(Path(str(key_path) + ".pub"))
        _install_authorized_key(entry, home, public.decode("utf-8", "strict").strip())
        fp = subprocess.run(["ssh-keygen", "-lf", str(key_path) + ".pub"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=False)
        fingerprint = (fp.stdout or "").strip()[:300]
        readme = (
            "YWD-Hotspot SSH CLIENT LOGIN key\n"
            f"Created: {created.isoformat().replace('+00:00', 'Z')}\nHotspot: {socket.gethostname()}\nLinux user: {username}\n"
            f"Fingerprint: {fingerprint or 'unavailable'}\n\nUSE THIS KEY TO LOG IN FROM AN SSH/SFTP CLIENT.\n"
            f"Set username to {username}, host to this hotspot, and port to 22.\n\n"
            f"The matching public key has already been added to:\n  {home}/.ssh/authorized_keys\n\n"
            "The private key is NOT retained by YWD-Hotspot after this response. Keep it private.\n\n"
            f"To revoke this key, remove the authorized_keys line ending with:\n  {comment}\n"
        ).encode("utf-8")
        rows = [("ywd_hotspot_client_ed25519", private, 0o600, int(created.timestamp())), ("ywd_hotspot_client_ed25519.pub", public, 0o644, int(created.timestamp()))]
        out = _archive(f"{hostname}-{username}-ssh-client-login-{stamp}.tar.gz", "README-SSH-CLIENT-LOGIN.txt", readme, rows)
    out.update({"username": username, "fingerprint": fingerprint, "authorized_key_comment": comment, "contains_private_keys": True, "private_key_retained": False, "created_at": created.isoformat().replace("+00:00", "Z"), "kind": "client-login", "ssh": ssh_status()})
    return out


def _payload() -> dict:
    raw = sys.stdin.buffer.read(16384)
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
    elif action == "ssh-password-set":
        out = set_login_password(payload)
    elif action == "ssh-keys-export":
        out = export_host_keys()
    elif action == "ssh-client-key-create":
        out = create_client_key(payload)
    else:
        raise SystemExit("usage: ssh_keys_admin.py {ssh-status|ssh-configure|ssh-password-set|ssh-keys-export|ssh-client-key-create}")
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:800]}, separators=(",", ":")))
        raise SystemExit(1)
