#!/usr/bin/env python3
"""Fast SSH runtime controller for the authenticated YWD-Hotspot dashboard.

The key/export helper owns host-key generation and policy validation. This
controller deliberately avoids `systemctl enable --now`, which can hold an HTTP
request open for too long on a Pi Zero. Enablement and startup are split; startup
is queued non-blocking and then polled briefly for a definitive state.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ssh_keys_admin as keys

SSH_UNIT = "ssh.service"


def run(args, timeout=8, check=False):
    try:
        proc = subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        if check:
            raise RuntimeError(f"command timed out after {timeout}s: {args[0]}") from exc
        return subprocess.CompletedProcess(args, 124, stdout="", stderr=f"timed out after {timeout}s")
    if check and proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"command failed: {args[0]}").strip()[:800])
    return proc


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


def service_state() -> str:
    proc = run(["systemctl", "is-active", SSH_UNIT], 4)
    return (proc.stdout or "").strip() or "unknown"


def failure_detail() -> str:
    show = run([
        "systemctl", "show", SSH_UNIT,
        "--property=ActiveState,SubState,Result",
        "--no-pager",
    ], 5)
    journal = run([
        "journalctl", "-u", SSH_UNIT, "-n", "12", "--no-pager", "-o", "cat",
    ], 6)
    bits = []
    if show.stdout.strip():
        bits.append(show.stdout.strip().replace("\n", "; "))
    if journal.stdout.strip():
        bits.append(journal.stdout.strip().replace("\n", " | "))
    return " · ".join(bits)[-1200:]


def configure(data: dict) -> dict:
    if os.geteuid() != 0:
        raise PermissionError("root required")
    enabled = data.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be true or false")

    if enabled:
        # This writes the public-key-only drop-in, creates unique host identity
        # keys when absent, and validates sshd configuration before systemd is
        # asked to expose port 22.
        keys._install_public_key_policy()

        # Keep enable separate from start. `enable --now` can remain attached to
        # the systemd start job long enough to exceed a dashboard request on a
        # Pi Zero even when sshd eventually starts successfully.
        run(["systemctl", "enable", SSH_UNIT], 8, check=True)
        run(["systemctl", "start", "--no-block", SSH_UNIT], 8, check=True)

        deadline = time.monotonic() + 18
        while time.monotonic() < deadline:
            state = service_state()
            if state == "active":
                out = keys.ssh_status()
                out.update({
                    "changed": True,
                    "message": "SSH enabled in public-key-only mode",
                })
                return out
            if state in {"failed", "inactive"}:
                # Give a newly queued job one small grace interval before
                # declaring it failed; systemd can briefly report inactive.
                time.sleep(0.5)
                state2 = service_state()
                if state2 == "active":
                    continue
                if state2 == "failed":
                    break
            time.sleep(0.5)

        detail = failure_detail()
        raise RuntimeError("SSH was enabled but did not become active" + (f": {detail}" if detail else ""))

    # Disable boot activation immediately, then queue the stop without waiting
    # for every sshd child/session to unwind inside the dashboard request.
    run(["systemctl", "disable", SSH_UNIT], 8, check=False)
    run(["systemctl", "stop", "--no-block", SSH_UNIT], 8, check=False)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if service_state() != "active":
            break
        time.sleep(0.4)

    out = keys.ssh_status()
    out.update({
        "changed": True,
        "message": "SSH disabled; saved keys were preserved",
    })
    return out


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    data = payload()
    if action == "ssh-status":
        out = keys.ssh_status()
    elif action == "ssh-configure":
        out = configure(data)
    else:
        raise SystemExit("usage: ssh_runtime_admin.py {ssh-status|ssh-configure}")
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:1400]}, separators=(",", ":")))
        raise SystemExit(1)
