#!/usr/bin/env python3
"""Fast SSH runtime controller for the authenticated YWD-Hotspot dashboard.

Factory images ship with SSH disabled. The dashboard prepares the strict
public-key-only sshd policy and unique host keys, manages boot persistence with
the native systemd wants symlink, then asks systemd only to start/stop the
service. This deliberately avoids `systemctl enable/disable`, which is slow
enough on a Pi Zero to exceed an interactive dashboard request.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ssh_keys_admin as keys

SSH_UNIT = "ssh.service"
SSH_PORT = 22
SSHD_PRIVSEP_DIR = Path("/run/sshd")
WANTS_DIR = Path("/etc/systemd/system/multi-user.target.wants")
UNIT_CANDIDATES = (
    Path("/lib/systemd/system/ssh.service"),
    Path("/usr/lib/systemd/system/ssh.service"),
)


def run(args, timeout=12):
    """Run a bounded command; timeout is returned as rc=124, not an exception."""
    try:
        return subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args, 124, stdout="", stderr=f"timed out after {timeout}s"
        )


def payload() -> dict:
    raw = sys.stdin.buffer.read(4096)
    if not raw:
        return {}
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON payload") from exc
    if not isinstance(obj, dict):
        raise ValueError("payload must be an object")
    return obj


def unit_fragment() -> Path:
    for candidate in UNIT_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise RuntimeError("native OpenSSH ssh.service unit was not found")


def boot_link() -> Path:
    return WANTS_DIR / SSH_UNIT


def boot_enabled() -> bool:
    link = boot_link()
    return link.is_symlink() and link.exists()


def set_boot_enabled(enabled: bool) -> None:
    """Manage the same wants symlink `systemctl enable ssh.service` would create."""
    link = boot_link()
    if enabled:
        target = unit_fragment()
        WANTS_DIR.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(link):
            if not link.is_symlink():
                raise RuntimeError(f"refusing to replace non-symlink boot entry: {link}")
            link.unlink()
        os.symlink(str(target), str(link))
        return
    if os.path.lexists(link):
        if not link.is_symlink():
            raise RuntimeError(f"refusing to remove non-symlink boot entry: {link}")
        link.unlink()


def ensure_privsep_dir() -> None:
    """Recreate OpenSSH's ephemeral privilege-separation directory when needed.

    Debian's ssh.service may remove /run/sshd when the service is stopped. YWD
    validates sshd configuration before asking systemd to start it, and `sshd -t`
    itself requires this directory to exist. Recreate it as the normal root-owned
    0755 runtime directory so disable -> enable works without a reboot.
    """
    if os.path.lexists(SSHD_PRIVSEP_DIR):
        if SSHD_PRIVSEP_DIR.is_symlink() or not SSHD_PRIVSEP_DIR.is_dir():
            raise RuntimeError(f"unsafe SSH privilege-separation path: {SSHD_PRIVSEP_DIR}")
    else:
        SSHD_PRIVSEP_DIR.mkdir(parents=True, mode=0o755)
    os.chmod(SSHD_PRIVSEP_DIR, 0o755)
    os.chown(SSHD_PRIVSEP_DIR, 0, 0)


def port_listening() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", SSH_PORT), timeout=0.25):
            return True
    except OSError:
        return False


def wait_port(wanted: bool, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if port_listening() is wanted:
            return True
        time.sleep(0.25)
    return port_listening() is wanted


def failure_detail() -> str:
    show = run([
        "systemctl", "show", SSH_UNIT,
        "--property=ActiveState,SubState,Result",
        "--no-pager",
    ], 6)
    journal = run([
        "journalctl", "-u", SSH_UNIT, "-n", "16", "--no-pager", "-o", "cat",
    ], 6)
    bits = []
    if (show.stdout or "").strip():
        bits.append(show.stdout.strip().replace("\n", "; "))
    if (journal.stdout or "").strip():
        bits.append(journal.stdout.strip().replace("\n", " | "))
    if show.returncode == 124:
        bits.append("systemctl status lookup timed out")
    return " · ".join(bits)[-1400:]


def status() -> dict:
    policy_managed = False
    try:
        policy_managed = (
            keys.SSHD_DROPIN.is_file()
            and keys.SSHD_DROPIN.read_text(encoding="utf-8") == keys.YWD_SSH_POLICY
        )
    except Exception:
        pass
    return {
        "ok": True,
        "installed": keys.SSHD.is_file() and keys.SSH_DIR.is_dir(),
        "active": port_listening(),
        "enabled_at_boot": boot_enabled(),
        "port": SSH_PORT,
        "authentication": "public-key-only",
        "password_authentication": False,
        "root_login": False,
        "policy_managed": policy_managed,
        "host_key_count": len(keys._host_key_paths()),
        "login_user": "ywd",
        "authorized_key_count": keys._authorized_key_count("ywd"),
    }


def configure(data: dict) -> dict:
    if os.geteuid() != 0:
        raise PermissionError("root required")
    enabled = data.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be true or false")

    if enabled:
        ensure_privsep_dir()
        keys._install_public_key_policy()
        set_boot_enabled(True)

        start = run(["systemctl", "start", "--no-block", SSH_UNIT], 12)
        if wait_port(True, 14):
            out = status()
            out.update({
                "changed": True,
                "message": "SSH enabled in public-key-only mode",
            })
            return out

        set_boot_enabled(False)
        detail = failure_detail()
        cmd = (start.stderr or start.stdout or "").strip()
        if cmd:
            detail = (cmd + (" · " + detail if detail else ""))[-1400:]
        raise RuntimeError(
            "SSH did not open port 22" + (f": {detail}" if detail else "")
        )

    set_boot_enabled(False)
    stop = run(["systemctl", "stop", "--no-block", SSH_UNIT], 12)
    closed = wait_port(False, 10)
    if not closed:
        detail = failure_detail()
        cmd = (stop.stderr or stop.stdout or "").strip()
        if cmd:
            detail = (cmd + (" · " + detail if detail else ""))[-1400:]
        raise RuntimeError(
            "SSH boot activation was disabled but port 22 did not close"
            + (f": {detail}" if detail else "")
        )

    out = status()
    out.update({
        "changed": True,
        "message": "SSH disabled; saved keys were preserved",
    })
    return out


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    data = payload()
    if action == "ssh-status":
        out = status()
    elif action == "ssh-configure":
        out = configure(data)
    else:
        raise SystemExit("usage: ssh_runtime_admin.py {ssh-status|ssh-configure}")
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:1600]}, separators=(",", ":")))
        raise SystemExit(1)
