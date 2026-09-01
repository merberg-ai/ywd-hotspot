#!/usr/bin/env python3
"""Narrow root launcher for transactional managed vocoder activation."""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import maintenance_coordinator
import vocoder_manager
import vocoder_prepared

PRIVATE = Path("/var/lib/ywd-hotspot/private")
REQUEST = PRIVATE / "vocoder-activation-request.json"
JOURNAL = PRIVATE / "vocoder-activation-journal.json"
SERVICE = "ywd-vocoder-activation.service"
RECOVERY_SERVICE = "ywd-vocoder-recovery.service"


def _out(doc: dict, rc: int = 0) -> int:
    print(json.dumps(doc, sort_keys=True))
    return rc


def _read_payload() -> dict:
    raw = sys.stdin.read(131073)
    if len(raw) > 131072:
        raise ValueError("request too large")
    doc = json.loads(raw) if raw.strip() else {}
    if not isinstance(doc, dict):
        raise ValueError("request must be an object")
    return doc


def _service_busy() -> bool:
    p = subprocess.run(["systemctl", "is-active", SERVICE], text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, check=False)
    return (p.stdout or "").strip().lower() in {"active", "activating", "reloading", "deactivating"}


def _atomic_request(doc: dict) -> None:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    tmp = REQUEST.with_name(REQUEST.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.chown(tmp, 0, 0)
    os.replace(tmp, REQUEST)


def _candidate_ready() -> dict:
    # This is a lightweight pre-launch presentation check only. The root worker
    # independently revalidates path confinement, identity, SHA, self-test and
    # exact YWD Extended runtime before touching any live file.
    prepared = vocoder_prepared.status()
    if not prepared.get("valid"):
        raise RuntimeError(str(prepared.get("reason") or "no current verified prepared vocoder candidate is available"))
    runtime = vocoder_manager._runtime()
    if not runtime.get("ready"):
        raise RuntimeError("current persisted YWD Extended identity is not ready for vocoder activation")
    return prepared


def start_activation() -> dict:
    if _service_busy():
        raise RuntimeError("vocoder activation is already running")
    lease = maintenance_coordinator.inspect()
    if lease.get("stale"):
        maintenance_coordinator.recover_stale()
        lease = maintenance_coordinator.inspect()
    if lease.get("active"):
        raise RuntimeError(f"appliance maintenance is busy: {lease.get('job_type') or 'maintenance'}")
    if JOURNAL.exists():
        raise RuntimeError("an incomplete vocoder activation journal exists; reboot or run recovery before retrying")
    _candidate_ready()

    # Recovery must already be enabled before the activation worker can mutate
    # live backend files. If power is lost afterward, boot recovery is armed.
    p = subprocess.run(["systemctl", "enable", RECOVERY_SERVICE], text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if p.returncode != 0:
        raise RuntimeError((p.stdout or "could not enable vocoder recovery service").strip()[:600])

    job_id = f"vocoder-activate-{int(time.time())}-{secrets.token_hex(4)}"
    maintenance_coordinator.reserve_launch(job_id, "vocoder-activate", SERVICE)
    reserved = True
    try:
        _atomic_request({
            "schema": 1,
            "job_id": job_id,
            "job_type": "vocoder-activate",
            "operation": "activate",
            "requested_at": int(time.time()),
        })
        p = subprocess.run(["systemctl", "start", "--no-block", SERVICE], text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        if p.returncode != 0:
            raise RuntimeError((p.stdout or "could not start vocoder activation worker").strip()[:600])
        reserved = False
        return {
            "ok": True,
            "job_id": job_id,
            "operation": "activate",
            "state": "ACTIVATING",
            "message": "Transactional vocoder activation started in the background",
        }
    except Exception:
        try:
            REQUEST.unlink()
        except FileNotFoundError:
            pass
        if reserved:
            try:
                maintenance_coordinator.release(job_id, outcome="launch-failed", owner_pid=1)
            except Exception:
                pass
        raise


def main() -> int:
    if os.geteuid() != 0:
        return _out({"ok": False, "error": "vocoder activation admin must run as root"}, 1)
    action = str(sys.argv[1] if len(sys.argv) > 1 else "")
    try:
        payload = _read_payload()
        if action != "vocoder-activate-start":
            return _out({"ok": False, "error": "unsupported vocoder activation action"}, 2)
        if payload:
            raise ValueError("vocoder activation accepts no browser options")
        return _out(start_activation())
    except Exception as exc:
        return _out({"ok": False, "error": str(exc)[:800]}, 1)


if __name__ == "__main__":
    raise SystemExit(main())
