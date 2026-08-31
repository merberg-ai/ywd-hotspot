#!/usr/bin/env python3
"""Narrow root launcher for managed vocoder background jobs.

The dashboard can request only one fixed operation in this gated generation:
`vocoder-preflight-start`. This helper generates the job id itself, writes one
root-owned request for the unprivileged service, and starts that service without
waiting for the job to finish.
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
SERVICE = "ywd-vocoder-job.service"


def _json_out(doc: dict, rc: int = 0) -> int:
    print(json.dumps(doc, sort_keys=True))
    return rc


def _service_active() -> bool:
    p = subprocess.run(
        ["systemctl", "is-active", "--quiet", SERVICE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return p.returncode == 0


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


def start_preflight() -> dict:
    if _service_active():
        raise RuntimeError("a vocoder maintenance job is already running")

    lease = maintenance_coordinator.inspect()
    if lease.get("stale"):
        maintenance_coordinator.recover_stale()
        lease = maintenance_coordinator.inspect()
    if lease.get("active"):
        owner = str(lease.get("job_type") or "maintenance")
        raise RuntimeError(f"appliance maintenance is busy: {owner}")

    _uid, gid = _ensure_state_dir()
    job_id = f"vocoder-{int(time.time())}-{secrets.token_hex(4)}"
    request = {
        "schema": 1,
        "job_id": job_id,
        "job_type": "vocoder-preflight",
        "operation": "preflight",
        "requested_at": int(time.time()),
    }
    _atomic_request(request, gid)

    p = subprocess.run(
        ["systemctl", "start", "--no-block", SERVICE],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if p.returncode != 0:
        try:
            REQUEST.unlink()
        except FileNotFoundError:
            pass
        raise RuntimeError((p.stderr or p.stdout or "could not start vocoder job service").strip()[:500])
    return {
        "ok": True,
        "job_id": job_id,
        "state": "CHECKING",
        "message": "Vocoder install-readiness check started in the background",
    }


def main() -> int:
    if os.geteuid() != 0:
        return _json_out({"ok": False, "error": "vocoder job admin must run as root"}, 1)
    action = str(sys.argv[1] if len(sys.argv) > 1 else "")
    if action != "vocoder-preflight-start":
        return _json_out({"ok": False, "error": "unsupported vocoder job action"}, 2)
    try:
        # Consume and validate bounded JSON input even though this generation
        # deliberately accepts no browser-controlled options.
        raw = sys.stdin.read(131073)
        if len(raw) > 131072:
            raise ValueError("request too large")
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict) or payload:
            raise ValueError("vocoder preflight accepts no options")
        return _json_out(start_preflight())
    except Exception as exc:
        return _json_out({"ok": False, "error": str(exc)[:800]}, 1)


if __name__ == "__main__":
    raise SystemExit(main())
