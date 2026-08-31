#!/usr/bin/env python3
"""Persistent appliance-wide maintenance coordination for YWD-Hotspot.

This module is deliberately small and operation-agnostic. Privileged mutating
jobs claim one persistent lease before changing appliance state. The lease is
serialized with flock so two processes cannot both win a claim. Read-only
status never mutates the lease.

The RC4 vocoder-manager foundation consumes this status first. Updater/channel,
plugin-package and runtime activation paths will be migrated onto the same
coordinator in later controlled slices.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

VAR = Path(os.environ.get("YWD_VAR", "/var/lib/ywd-hotspot"))
LEASE = Path(os.environ.get("YWD_MAINTENANCE_LEASE", str(VAR / "maintenance-lease.json")))
LOCK = Path(os.environ.get("YWD_MAINTENANCE_LOCK", str(VAR / "maintenance-lease.lock")))
LAST = Path(os.environ.get("YWD_MAINTENANCE_LAST", str(VAR / "maintenance-last.json")))
BOOT_ID = Path(os.environ.get("YWD_BOOT_ID_PATH", "/proc/sys/kernel/random/boot_id"))
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
TYPE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
PHASE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class MaintenanceBusy(RuntimeError):
    def __init__(self, lease: dict):
        self.lease = public_status(lease)
        owner = self.lease.get("job_type") or "maintenance"
        job_id = self.lease.get("job_id") or "unknown"
        super().__init__(f"appliance maintenance is busy: {owner} ({job_id})")


class MaintenanceOwnershipError(RuntimeError):
    pass


def _now() -> int:
    return int(time.time())


def _boot_id() -> str:
    try:
        return BOOT_ID.read_text(encoding="utf-8").strip()[:96]
    except Exception:
        return "unknown"


def _read(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def _atomic(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o640)
    try:
        os.chown(tmp, 0, os.stat(path.parent).st_gid)
    except Exception:
        pass
    os.replace(tmp, path)


def _pid_alive(pid: int) -> bool:
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _validate(job_id: str, job_type: str, phase: str) -> tuple[str, str, str]:
    job_id = str(job_id or "").strip()
    job_type = str(job_type or "").strip().lower()
    phase = str(phase or "").strip().lower()
    if not ID_RE.fullmatch(job_id):
        raise ValueError("invalid maintenance job id")
    if not TYPE_RE.fullmatch(job_type):
        raise ValueError("invalid maintenance job type")
    if not PHASE_RE.fullmatch(phase):
        raise ValueError("invalid maintenance phase")
    return job_id, job_type, phase


def _stale_reason(doc: dict) -> str | None:
    if not doc:
        return None
    lease_boot = str(doc.get("boot_id") or "")
    current_boot = _boot_id()
    if lease_boot and current_boot != "unknown" and lease_boot != current_boot:
        return "previous-boot"
    pid = doc.get("owner_pid")
    if not _pid_alive(pid):
        return "owner-not-running"
    return None


def inspect() -> dict:
    """Return authoritative lease state without modifying persistent files."""
    doc = _read(LEASE)
    if not doc:
        return {"active": False, "stale": False}
    stale_reason = _stale_reason(doc)
    out = dict(doc)
    out["active"] = stale_reason is None
    out["stale"] = stale_reason is not None
    if stale_reason:
        out["stale_reason"] = stale_reason
    return out


def public_status(doc: dict | None = None) -> dict:
    """Return only bounded non-secret maintenance metadata for status surfaces."""
    src = inspect() if doc is None else dict(doc or {})
    allowed = {
        "active", "stale", "stale_reason", "job_id", "job_type", "owner_pid",
        "service", "started_at", "updated_at", "phase", "cancellable",
    }
    out = {k: src.get(k) for k in allowed if k in src}
    out.setdefault("active", False)
    out.setdefault("stale", False)
    for key in ("job_id", "job_type", "service", "phase", "stale_reason"):
        if out.get(key) is not None:
            out[key] = str(out[key])[:120]
    return out


@contextmanager
def _locked():
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(LOCK, os.O_RDWR | os.O_CREAT, 0o640)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def recover_stale() -> dict:
    """Remove only a positively stale lease; live ownership is never stolen."""
    with _locked():
        doc = _read(LEASE)
        reason = _stale_reason(doc)
        if not doc:
            return {"ok": True, "recovered": False, "reason": "no-lease"}
        if reason is None:
            raise MaintenanceBusy(doc)
        archived = dict(doc)
        archived.update({"active": False, "stale": True, "stale_reason": reason, "recovered_at": _now()})
        _atomic(LAST, archived)
        try:
            LEASE.unlink()
        except FileNotFoundError:
            pass
        return {"ok": True, "recovered": True, "reason": reason, "previous": public_status(archived)}


def claim(
    job_id: str,
    job_type: str,
    phase: str = "preparing",
    *,
    cancellable: bool = True,
    owner_pid: int | None = None,
    service: str | None = None,
) -> dict:
    """Atomically claim the appliance maintenance lease for one managed job."""
    job_id, job_type, phase = _validate(job_id, job_type, phase)
    pid = int(owner_pid or os.getpid())
    service = str(service or "")[:120] or None
    now = _now()
    with _locked():
        existing = _read(LEASE)
        reason = _stale_reason(existing)
        if existing and reason is None:
            if str(existing.get("job_id")) == job_id and int(existing.get("owner_pid") or -1) == pid:
                existing["phase"] = phase
                existing["updated_at"] = now
                existing["cancellable"] = bool(cancellable)
                if service is not None:
                    existing["service"] = service
                _atomic(LEASE, existing)
                return public_status({**existing, "active": True, "stale": False})
            raise MaintenanceBusy(existing)
        if existing:
            archived = dict(existing)
            archived.update({"active": False, "stale": True, "stale_reason": reason or "unknown", "recovered_at": now})
            _atomic(LAST, archived)
        doc = {
            "schema": 1,
            "job_id": job_id,
            "job_type": job_type,
            "owner_pid": pid,
            "service": service,
            "boot_id": _boot_id(),
            "started_at": now,
            "updated_at": now,
            "phase": phase,
            "cancellable": bool(cancellable),
        }
        _atomic(LEASE, doc)
        return public_status({**doc, "active": True, "stale": False})


def _owned(existing: dict, job_id: str, owner_pid: int | None) -> None:
    if not existing:
        raise MaintenanceOwnershipError("maintenance lease is not active")
    if str(existing.get("job_id")) != str(job_id):
        raise MaintenanceOwnershipError("maintenance lease belongs to a different job")
    if owner_pid is not None and int(existing.get("owner_pid") or -1) != int(owner_pid):
        raise MaintenanceOwnershipError("maintenance lease belongs to a different process")


def update(job_id: str, *, phase: str, cancellable: bool | None = None, owner_pid: int | None = None) -> dict:
    job_id = str(job_id or "").strip()
    phase = str(phase or "").strip().lower()
    if not ID_RE.fullmatch(job_id) or not PHASE_RE.fullmatch(phase):
        raise ValueError("invalid maintenance lease update")
    with _locked():
        existing = _read(LEASE)
        _owned(existing, job_id, owner_pid)
        reason = _stale_reason(existing)
        if reason is not None:
            raise MaintenanceOwnershipError(f"maintenance lease is stale: {reason}")
        existing["phase"] = phase
        existing["updated_at"] = _now()
        if cancellable is not None:
            existing["cancellable"] = bool(cancellable)
        _atomic(LEASE, existing)
        return public_status({**existing, "active": True, "stale": False})


def release(job_id: str, *, outcome: str = "complete", owner_pid: int | None = None) -> dict:
    job_id = str(job_id or "").strip()
    outcome = str(outcome or "complete").strip().lower()[:64]
    if not ID_RE.fullmatch(job_id):
        raise ValueError("invalid maintenance job id")
    with _locked():
        existing = _read(LEASE)
        _owned(existing, job_id, owner_pid)
        finished = dict(existing)
        finished.update({
            "active": False,
            "stale": False,
            "outcome": outcome,
            "completed_at": _now(),
            "updated_at": _now(),
        })
        _atomic(LAST, finished)
        try:
            LEASE.unlink()
        except FileNotFoundError:
            pass
        return public_status(finished)
