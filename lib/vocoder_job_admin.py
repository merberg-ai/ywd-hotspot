#!/usr/bin/env python3
"""Narrow root launcher/canceller for managed vocoder background jobs.

The browser can request only fixed YWD-owned operations. This helper generates
job IDs, reserves the appliance maintenance lease before systemd launch, writes
one validated request for the unprivileged worker, and can signal only the
currently matching/cancellable vocoder job.
"""
from __future__ import annotations

import grp
import json
import os
import pwd
import secrets
import subprocess
import sys
import time
from pathlib import Path

import maintenance_coordinator

VAR = Path(os.environ.get("YWD_VAR", "/var/lib/ywd-hotspot"))
STATE_DIR = Path(os.environ.get("YWD_VOCODER_STATE_DIR", str(VAR / "vocoder")))
REQUEST = Path(os.environ.get("YWD_VOCODER_JOB_REQUEST", str(STATE_DIR / "request.json")))
JOB_STATE = Path(os.environ.get("YWD_VOCODER_JOB_STATE", str(STATE_DIR / "job.json")))
SERVICE = "ywd-vocoder-job.service"
OPERATIONS = {
    "preflight": "vocoder-preflight",
    "prepare": "vocoder-prepare",
}


def _json_out(doc: dict, rc: int = 0) -> int:
    print(json.dumps(doc, sort_keys=True))
    return rc


def _service_busy() -> bool:
    p = subprocess.run(
        ["systemctl", "is-active", SERVICE], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    return (p.stdout or "").strip().lower() in {"active", "activating", "reloading", "deactivating"}


def _ensure_state_dir() -> tuple[int, int]:
    user = pwd.getpwnam("ywd-hotspot")
    group = grp.getgrnam("ywd-hotspot")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    os.chown(STATE_DIR, user.pw_uid, group.gr_gid)
    os.chmod(STATE_DIR, 0o750)
    return user.pw_uid, group.gr_gid


def _atomic_request(doc: dict, gid: int) -> None:
    tmp = REQUEST.with_name(REQUEST.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chown(tmp, 0, gid)
    os.chmod(tmp, 0o640)
    os.replace(tmp, REQUEST)


def _read_json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def start_job(operation: str) -> dict:
    operation = str(operation or "").strip().lower()
    if operation not in OPERATIONS:
        raise ValueError("unsupported vocoder job operation")
    _uid, gid = _ensure_state_dir()
    if _service_busy():
        raise RuntimeError("a vocoder maintenance job is already running")

    lease = maintenance_coordinator.inspect()
    if lease.get("stale"):
        maintenance_coordinator.recover_stale()
        lease = maintenance_coordinator.inspect()
    if lease.get("active"):
        owner = str(lease.get("job_type") or "maintenance")
        raise RuntimeError(f"appliance maintenance is busy: {owner}")

    job_type = OPERATIONS[operation]
    job_id = f"vocoder-{int(time.time())}-{secrets.token_hex(4)}"
    maintenance_coordinator.reserve_launch(job_id, job_type, SERVICE)
    reserved = True
    try:
        request = {
            "schema": 1,
            "job_id": job_id,
            "job_type": job_type,
            "operation": operation,
            "requested_at": int(time.time()),
        }
        _atomic_request(request, gid)
        p = subprocess.run(
            ["systemctl", "start", "--no-block", SERVICE], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if p.returncode != 0:
            raise RuntimeError((p.stderr or p.stdout or "could not start vocoder job service").strip()[:500])
        reserved = False
        return {
            "ok": True,
            "job_id": job_id,
            "state": "CHECKING",
            "operation": operation,
            "message": "Vocoder install-readiness check started in the background" if operation == "preflight"
                       else "Vocoder candidate preparation started in the background",
        }
    except Exception:
        try: REQUEST.unlink()
        except FileNotFoundError: pass
        if reserved:
            try: maintenance_coordinator.release(job_id, outcome="launch-failed", owner_pid=1)
            except Exception: pass
        raise


def cancel_job(job_id: str) -> dict:
    job_id = str(job_id or "").strip()
    if not job_id:
        raise ValueError("job_id is required")
    lease = maintenance_coordinator.inspect()
    if not lease.get("active"):
        raise RuntimeError("no active maintenance job")
    if str(lease.get("job_id") or "") != job_id:
        raise RuntimeError("active maintenance belongs to a different job")
    if str(lease.get("job_type") or "") not in set(OPERATIONS.values()):
        raise RuntimeError("active maintenance is not a vocoder job")
    if not bool(lease.get("cancellable")):
        raise RuntimeError("the active vocoder phase cannot be canceled safely")

    state = _read_json(JOB_STATE)
    if state and str(state.get("job_id") or "") == job_id and not bool(state.get("cancellable", True)):
        raise RuntimeError("the active vocoder phase cannot be canceled safely")
    if not _service_busy():
        raise RuntimeError("vocoder worker is not running; reload status before retrying")

    p = subprocess.run(
        ["systemctl", "kill", "--kill-who=main", "--signal=SIGTERM", SERVICE],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "could not request vocoder job cancellation").strip()[:500])
    return {"ok": True, "job_id": job_id, "state": "CANCELING", "message": "Safe cancellation requested"}


def _payload() -> dict:
    raw = sys.stdin.read(131073)
    if len(raw) > 131072:
        raise ValueError("request too large")
    payload = json.loads(raw) if raw.strip() else {}
    if not isinstance(payload, dict):
        raise ValueError("request must be an object")
    return payload


def main() -> int:
    if os.geteuid() != 0:
        return _json_out({"ok": False, "error": "vocoder job admin must run as root"}, 1)
    action = str(sys.argv[1] if len(sys.argv) > 1 else "")
    try:
        payload = _payload()
        if action == "vocoder-preflight-start":
            if payload: raise ValueError("vocoder preflight accepts no options")
            return _json_out(start_job("preflight"))
        if action == "vocoder-prepare-start":
            if payload: raise ValueError("vocoder preparation accepts no options")
            return _json_out(start_job("prepare"))
        if action == "vocoder-job-cancel":
            if set(payload) != {"job_id"}: raise ValueError("vocoder cancellation accepts only job_id")
            return _json_out(cancel_job(payload.get("job_id")))
        return _json_out({"ok": False, "error": "unsupported vocoder job action"}, 2)
    except Exception as exc:
        return _json_out({"ok": False, "error": str(exc)[:800]}, 1)


if __name__ == "__main__":
    raise SystemExit(main())
