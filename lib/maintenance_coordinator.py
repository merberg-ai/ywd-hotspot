#!/usr/bin/env python3
"""Persistent appliance-wide maintenance coordination for YWD-Hotspot.

State-changing jobs serialize through one persistent lease. Root launch/recovery
helpers and unprivileged workers share one flock inode. Background jobs use a
short systemd-owned launch reservation before the worker atomically adopts the
lease, closing the request/start race without granting browser-controlled
process or path authority.
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
LAUNCH_TIMEOUT_S = 60


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
    if pid <= 0:
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

    phase = str(doc.get("phase") or "").lower()
    try:
        pid = int(doc.get("owner_pid") or 0)
    except Exception:
        pid = 0
    if phase == "launching" and pid == 1:
        try:
            age = max(0, _now() - int(doc.get("updated_at") or doc.get("started_at") or 0))
        except Exception:
            age = LAUNCH_TIMEOUT_S + 1
        if age > LAUNCH_TIMEOUT_S:
            return "launch-timeout"
        return None

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
    fd = os.open(LOCK, os.O_RDWR | os.O_CREAT, 0o660)
    try:
        try:
            os.fchmod(fd, 0o660)
            if os.geteuid() == 0:
                os.fchown(fd, 0, os.stat(LOCK.parent).st_gid)
        except Exception:
            pass
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
    """Atomically claim or adopt the appliance maintenance lease."""
    job_id, job_type, phase = _validate(job_id, job_type, phase)
    pid = int(owner_pid or os.getpid())
    service = str(service or "")[:120] or None
    now = _now()
    with _locked():
        existing = _read(LEASE)
        reason = _stale_reason(existing)
        if existing and reason is None:
            same_job = str(existing.get("job_id")) == job_id and str(existing.get("job_type")) == job_type
            same_service = service is None or str(existing.get("service") or "") == service
            if (
                same_job
                and same_service
                and str(existing.get("phase") or "") == "launching"
                and int(existing.get("owner_pid") or -1) == 1
            ):
                existing["owner_pid"] = pid
                existing["phase"] = phase
                existing["updated_at"] = now
                existing["cancellable"] = bool(cancellable)
                existing["boot_id"] = _boot_id()
                _atomic(LEASE, existing)
                return public_status({**existing, "active": True, "stale": False})
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


def reserve_launch(job_id: str, job_type: str, service: str) -> dict:
    """Reserve maintenance for a systemd-managed worker before it is queued."""
    return claim(
        job_id,
        job_type,
        "launching",
        cancellable=True,
        owner_pid=1,
        service=service,
    )


def adopt(job_id: str, job_type: str, *, owner_pid: int | None = None, service: str | None = None,
          phase: str = "checking", cancellable: bool = True) -> dict:
    """Explicitly transfer a live systemd launch reservation to its worker."""
    job_id, job_type, phase = _validate(job_id, job_type, phase)
    pid = int(owner_pid or os.getpid())
    service = str(service or "")[:120] or None
    with _locked():
        existing = _read(LEASE)
        if not existing:
            raise MaintenanceOwnershipError("maintenance launch reservation is missing")
        reason = _stale_reason(existing)
        if reason is not None:
            raise MaintenanceOwnershipError(f"maintenance launch reservation is stale: {reason}")
        if str(existing.get("job_id")) != job_id or str(existing.get("job_type")) != job_type:
            raise MaintenanceOwnershipError("maintenance launch reservation belongs to a different job")
        if str(existing.get("phase") or "") != "launching" or int(existing.get("owner_pid") or -1) != 1:
            raise MaintenanceOwnershipError("maintenance lease is not an adoptable launch reservation")
        if service is not None and str(existing.get("service") or "") != service:
            raise MaintenanceOwnershipError("maintenance launch reservation belongs to a different service")
        existing["owner_pid"] = pid
        existing["phase"] = phase
        existing["updated_at"] = _now()
        existing["cancellable"] = bool(cancellable)
        existing["boot_id"] = _boot_id()
        _atomic(LEASE, existing)
        return public_status({**existing, "active": True, "stale": False})


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
