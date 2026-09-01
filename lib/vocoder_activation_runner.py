#!/usr/bin/env python3
"""Root-only transactional activation/recovery for managed vocoder candidates.

This worker may replace only the prepared vocoder backend and its dedicated
systemd units. It never rebuilds or replaces MMDVMHost/DMRGateway and never
changes BrandMeister/TGIF/scanner state.
"""
from __future__ import annotations

import fcntl
import grp
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import maintenance_coordinator
import vocoder_manager

APP = Path("/opt/ywd-hotspot/app")
VAR = Path("/var/lib/ywd-hotspot")
STATE_DIR = VAR / "vocoder"
PRIVATE = VAR / "private"
REQUEST = PRIVATE / "vocoder-activation-request.json"
JOURNAL = PRIVATE / "vocoder-activation-journal.json"
JOB_STATE = STATE_DIR / "job.json"
JOB_LOG = STATE_DIR / "job.log"
PREPARED = STATE_DIR / "prepared.json"
PROVENANCE = STATE_DIR / "installed.json"
BACKUP_ROOT = Path("/var/backups/ywd-hotspot/vocoder")
UPDATE_LOCK = Path("/run/ywd-hotspot-update.lock")

LIVE_BINARY = Path("/usr/local/libexec/ywd-vocoder-mbelib")
SERVICE_PATH = Path("/etc/systemd/system/ywd-vocoder-mbelib.service")
SOCKET_PATH = Path("/etc/systemd/system/ywd-vocoder-mbelib.socket")
DROPIN_PATH = Path("/etc/systemd/system/ywd-vocoder-mbelib.service.d/20-ywd-hotspot-normal-priority.conf")
SERVICE_UNIT = "ywd-vocoder-mbelib.service"
SOCKET_UNIT = "ywd-vocoder-mbelib.socket"
ACTIVATION_SERVICE = "ywd-vocoder-activation.service"

TEMPLATE_DIR = APP / "lib" / "vocoder_units"
TEMPLATE_SERVICE = TEMPLATE_DIR / "ywd-vocoder-mbelib.service"
TEMPLATE_SOCKET = TEMPLATE_DIR / "ywd-vocoder-mbelib.socket"
TEMPLATE_DROPIN = TEMPLATE_DIR / "20-ywd-hotspot-normal-priority.conf"

MAX_LOG_BYTES = 64 * 1024
MAX_LOG_LINES = 80
MAX_BACKUPS = 3


def _now() -> int:
    return int(time.time())


def _gid() -> int:
    try:
        return grp.getgrnam("ywd-hotspot").gr_gid
    except Exception:
        return 0


def _read_json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def _atomic_json(path: Path, doc: dict, mode: int = 0o640, gid: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, mode)
    try:
        os.chown(tmp, 0, _gid() if gid is None else int(gid))
    except Exception:
        pass
    os.replace(tmp, path)


def _tail() -> list[str]:
    try:
        data = JOB_LOG.read_bytes()
    except Exception:
        return []
    if len(data) > MAX_LOG_BYTES:
        data = data[-MAX_LOG_BYTES:]
        nl = data.find(b"\n")
        if nl >= 0:
            data = data[nl + 1 :]
    return [line[:500] for line in data.decode("utf-8", "replace").replace("\x00", "").splitlines()[-MAX_LOG_LINES:]]


def _prune_log() -> None:
    try:
        data = JOB_LOG.read_bytes()
    except Exception:
        return
    if len(data) <= MAX_LOG_BYTES:
        return
    data = data[-MAX_LOG_BYTES:]
    nl = data.find(b"\n")
    if nl >= 0:
        data = data[nl + 1 :]
    tmp = JOB_LOG.with_name(JOB_LOG.name + ".tmp")
    tmp.write_bytes(data)
    os.chmod(tmp, 0o640)
    try:
        os.chown(tmp, 0, _gid())
    except Exception:
        pass
    os.replace(tmp, JOB_LOG)


def log(message: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    clean = " ".join(str(message or "").replace("\x00", "").splitlines()).strip()[:1200]
    stamp = time.strftime("%H:%M:%S", time.localtime())
    with JOB_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {clean}\n")
    os.chmod(JOB_LOG, 0o640)
    try:
        os.chown(JOB_LOG, 0, _gid())
    except Exception:
        pass
    _prune_log()


def write_state(job: dict, *, state: str, phase: str, progress: int, message: str,
                error: str | None = None, completed: bool = False) -> None:
    now = _now()
    doc = {
        "schema": 1,
        "job_id": str(job.get("job_id") or "")[:96],
        "job_type": "vocoder-activate",
        "operation": "activate",
        "state": str(state or "ACTIVATING").upper()[:40],
        "phase": str(phase or "activating").lower()[:64],
        "progress": max(0, min(100, int(progress))),
        "message": str(message or "")[:300],
        "started_at": int(job.get("started_at") or now),
        "updated_at": now,
        "cancellable": False,
        "log_tail": _tail(),
    }
    if error:
        doc["error"] = str(error)[-1000:]
    if completed:
        doc["completed_at"] = now
    _atomic_json(JOB_STATE, doc)


def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
            env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"},
        )
    except Exception as exc:
        return subprocess.CompletedProcess(args, 127, str(exc))


def _must(args: list[str], timeout: int = 30) -> str:
    p = _run(args, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stdout or "command failed").strip()[-1200:])
    return (p.stdout or "").strip()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(128 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _unit_state(unit: str) -> dict:
    active = _run(["systemctl", "is-active", unit], 5)
    enabled = _run(["systemctl", "is-enabled", unit], 5)
    return {
        "active": (active.stdout or "").strip().lower() or "unknown",
        "enabled": (enabled.stdout or "").strip().lower() or "unknown",
    }


def _acquire_update_lock() -> int:
    UPDATE_LOCK.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(UPDATE_LOCK, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise RuntimeError("a YWD-Hotspot update/channel switch is already running") from exc
    return fd


def _prepared_candidate() -> dict:
    doc = _read_json(PREPARED)
    if not doc:
        raise RuntimeError("no prepared vocoder candidate is available")
    binary_text = str(doc.get("binary") or "")
    if not binary_text:
        raise RuntimeError("prepared candidate has no binary path")
    binary = Path(binary_text)
    root = (STATE_DIR / "build-cache" / "candidates").resolve()
    try:
        resolved = binary.resolve(strict=True)
        resolved.relative_to(root)
    except Exception as exc:
        raise RuntimeError("prepared candidate path is outside the managed candidate cache") from exc
    if not resolved.is_file() or resolved.is_symlink():
        raise RuntimeError("prepared candidate binary is not a regular managed file")
    expected_sha = str(doc.get("binary_sha256") or "").lower()
    actual_sha = _sha256(resolved)
    if len(expected_sha) != 64 or actual_sha != expected_sha:
        raise RuntimeError("prepared candidate SHA-256 does not match its manifest")
    identity = doc.get("identity") if isinstance(doc.get("identity"), dict) else {}
    self_test = doc.get("self_test") if isinstance(doc.get("self_test"), dict) else {}
    expected = {
        "recipe": vocoder_manager.BACKEND_RECIPE,
        "recipe_version": vocoder_manager.BACKEND_RECIPE_VERSION,
        "protocol_version": vocoder_manager.PROTOCOL_VERSION,
        "mbelib_commit": vocoder_manager.APPROVED_MBELIB_COMMIT,
        "architecture": platform.machine().strip().lower() or "unknown",
    }
    for key, value in expected.items():
        if identity.get(key) != value:
            raise RuntimeError(f"prepared candidate identity mismatch: {key}")
    if self_test.get("ok") is not True or int(self_test.get("protocol") or 0) != vocoder_manager.PROTOCOL_VERSION:
        raise RuntimeError("prepared candidate self-test metadata is not valid for this release")
    return {**doc, "binary": str(resolved), "binary_sha256": actual_sha}


def _copy_backup(path: Path, backup_dir: Path, label: str) -> dict:
    entry = {"path": str(path), "label": label, "existed": path.exists() or path.is_symlink()}
    if not entry["existed"]:
        return entry
    st = path.lstat()
    entry.update({"mode": st.st_mode & 0o7777, "uid": st.st_uid, "gid": st.st_gid})
    if path.is_symlink():
        entry["symlink"] = os.readlink(path)
        return entry
    if not path.is_file():
        raise RuntimeError(f"cannot protect non-file activation target: {path}")
    dst = backup_dir / label
    shutil.copy2(path, dst)
    entry["backup"] = str(dst)
    entry["sha256"] = _sha256(path)
    return entry


def _snapshot(job: dict) -> dict:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    backup_dir = BACKUP_ROOT / f"{stamp}-{str(job['job_id'])[:40]}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    os.chmod(backup_dir, 0o700)
    files = [
        _copy_backup(LIVE_BINARY, backup_dir, "live-binary"),
        _copy_backup(SERVICE_PATH, backup_dir, "service-unit"),
        _copy_backup(SOCKET_PATH, backup_dir, "socket-unit"),
        _copy_backup(DROPIN_PATH, backup_dir, "policy-dropin"),
        _copy_backup(PROVENANCE, backup_dir, "installed-provenance"),
    ]
    manifest = {
        "schema": 1,
        "job_id": job["job_id"],
        "created_at": _now(),
        "backup_dir": str(backup_dir),
        "files": files,
        "socket_state": _unit_state(SOCKET_UNIT),
        "service_state": _unit_state(SERVICE_UNIT),
    }
    _atomic_json(backup_dir / "manifest.json", manifest, mode=0o600, gid=0)
    return manifest


def _atomic_install(src: Path, dst: Path, mode: int) -> None:
    if not src.is_file():
        raise RuntimeError(f"required activation source is missing: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".ywd-new")
    shutil.copyfile(src, tmp)
    os.chmod(tmp, mode)
    os.chown(tmp, 0, 0)
    os.replace(tmp, dst)


def _restore_file(entry: dict) -> None:
    path = Path(str(entry.get("path") or ""))
    if not path.is_absolute():
        raise RuntimeError("invalid rollback path in protected manifest")
    if not bool(entry.get("existed")):
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        except FileNotFoundError:
            pass
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if entry.get("symlink") is not None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        os.symlink(str(entry["symlink"]), path)
        return
    backup = Path(str(entry.get("backup") or ""))
    if not backup.is_file():
        raise RuntimeError(f"protected rollback file is missing: {backup}")
    tmp = path.with_name(path.name + ".ywd-rollback")
    shutil.copyfile(backup, tmp)
    os.chmod(tmp, int(entry.get("mode") or 0o644))
    os.chown(tmp, int(entry.get("uid") or 0), int(entry.get("gid") or 0))
    os.replace(tmp, path)
    expected = str(entry.get("sha256") or "")
    if expected and _sha256(path) != expected:
        raise RuntimeError(f"rollback SHA verification failed for {path}")


def _restore_unit_policy(manifest: dict) -> None:
    socket_state = manifest.get("socket_state") if isinstance(manifest.get("socket_state"), dict) else {}
    service_state = manifest.get("service_state") if isinstance(manifest.get("service_state"), dict) else {}
    socket_enabled = str(socket_state.get("enabled") or "unknown")
    if socket_enabled in {"enabled", "enabled-runtime"}:
        _run(["systemctl", "enable", SOCKET_UNIT], 15)
    elif socket_enabled not in {"static", "indirect", "generated", "alias"}:
        _run(["systemctl", "disable", SOCKET_UNIT], 15)
    if str(socket_state.get("active") or "") == "active":
        _must(["systemctl", "start", SOCKET_UNIT], 20)
    else:
        _run(["systemctl", "stop", SOCKET_UNIT], 20)
    if str(service_state.get("active") or "") == "active":
        _must(["systemctl", "start", SERVICE_UNIT], 20)
    elif str(service_state.get("active") or "") not in {"activating", "reloading"}:
        _run(["systemctl", "stop", SERVICE_UNIT], 20)


def _rollback(journal: dict) -> None:
    manifest = journal.get("backup") if isinstance(journal.get("backup"), dict) else {}
    if not manifest:
        raise RuntimeError("activation journal has no protected backup manifest")
    _run(["systemctl", "stop", SERVICE_UNIT], 20)
    _run(["systemctl", "stop", SOCKET_UNIT], 20)
    for entry in manifest.get("files") or []:
        if isinstance(entry, dict):
            _restore_file(entry)
    _must(["systemctl", "daemon-reload"], 20)
    _restore_unit_policy(manifest)


def _write_journal(doc: dict) -> None:
    _atomic_json(JOURNAL, doc, mode=0o600, gid=0)


def _finish_journal(journal: dict, outcome: str) -> None:
    journal = dict(journal)
    journal["outcome"] = outcome
    journal["completed_at"] = _now()
    backup = journal.get("backup") if isinstance(journal.get("backup"), dict) else {}
    backup_dir = Path(str(backup.get("backup_dir") or ""))
    if backup_dir.is_dir():
        _atomic_json(backup_dir / "transaction.json", journal, mode=0o600, gid=0)
    try:
        JOURNAL.unlink()
    except FileNotFoundError:
        pass


def _prune_backups() -> None:
    try:
        rows = [p for p in BACKUP_ROOT.iterdir() if p.is_dir()]
    except Exception:
        return
    rows.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for path in rows[MAX_BACKUPS:]:
        shutil.rmtree(path, ignore_errors=True)


def _verify_live(candidate: dict) -> dict:
    if _sha256(LIVE_BINARY) != str(candidate["binary_sha256"]):
        raise RuntimeError("activated backend SHA-256 does not match the prepared candidate")
    if _run(["systemctl", "is-active", "--quiet", SOCKET_UNIT], 8).returncode != 0:
        raise RuntimeError("managed vocoder socket did not become active")
    enabled = (_run(["systemctl", "is-enabled", SOCKET_UNIT], 8).stdout or "").strip().lower()
    if enabled not in {"enabled", "enabled-runtime", "static"}:
        raise RuntimeError(f"managed vocoder socket enablement is unexpected: {enabled or 'unknown'}")
    policy = vocoder_manager._effective_policy()
    if not policy.get("ok"):
        raise RuntimeError(f"managed vocoder scheduling policy verification failed: {policy}")
    status = _must([
        "sudo", "-u", "ywd-hotspot", "--", "python3", str(APP / "lib" / "vocoder_client.py"), "status"
    ], 25)
    decode = _must([
        "sudo", "-u", "ywd-hotspot", "--", "python3", str(APP / "lib" / "vocoder_client.py"), "decode-test", "--frames", "10"
    ], 25)
    try:
        status_doc = json.loads(status)
        decode_doc = json.loads(decode)
    except Exception as exc:
        raise RuntimeError("live Protocol verification did not return valid JSON") from exc
    if status_doc.get("available") is not True or int(status_doc.get("protocol") or 0) != vocoder_manager.PROTOCOL_VERSION:
        raise RuntimeError("live vocoder STATUS verification failed")
    if int(decode_doc.get("pcm_bytes") or 0) != 3200 or int(decode_doc.get("protocol") or 0) != vocoder_manager.PROTOCOL_VERSION:
        raise RuntimeError("live 10-frame decode verification failed")
    return {"status": status_doc, "decode": {k: decode_doc.get(k) for k in ("protocol", "codec", "sample_rate", "samples_per_frame", "channels", "frames", "pcm_bytes", "pcm_sha256") if k in decode_doc}}


def _install_managed(candidate: dict) -> None:
    _atomic_install(Path(candidate["binary"]), LIVE_BINARY, 0o755)
    _atomic_install(TEMPLATE_SERVICE, SERVICE_PATH, 0o644)
    _atomic_install(TEMPLATE_SOCKET, SOCKET_PATH, 0o644)
    _atomic_install(TEMPLATE_DROPIN, DROPIN_PATH, 0o644)
    _must(["systemctl", "daemon-reload"], 20)
    _must(["systemctl", "enable", SOCKET_UNIT], 20)
    _must(["systemctl", "start", SOCKET_UNIT], 20)


def _write_provenance(candidate: dict, verification: dict, backup_dir: str) -> None:
    identity = candidate.get("identity") if isinstance(candidate.get("identity"), dict) else {}
    doc = {
        "schema": 1,
        "managed_by": "ywd-hotspot",
        "recipe": identity.get("recipe"),
        "recipe_version": identity.get("recipe_version"),
        "protocol_version": identity.get("protocol_version"),
        "mbelib_commit": identity.get("mbelib_commit"),
        "mbelib_source": identity.get("mbelib_source"),
        "architecture": identity.get("architecture"),
        "compiler": identity.get("compiler"),
        "adapter_sha256": identity.get("adapter_sha256"),
        "binary_sha256": candidate.get("binary_sha256"),
        "installed_at": _now(),
        "protected_backup": backup_dir,
        "last_self_test": {
            "ok": True,
            "completed_at": _now(),
            "protocol": vocoder_manager.PROTOCOL_VERSION,
            "frames": 10,
            "pcm_bytes": 3200,
            "pcm_sha256": ((verification.get("decode") or {}).get("pcm_sha256")),
        },
    }
    _atomic_json(PROVENANCE, doc, mode=0o640)


def _read_request() -> dict:
    doc = _read_json(REQUEST)
    if not doc or str(doc.get("operation") or "") != "activate" or not doc.get("job_id"):
        raise RuntimeError("vocoder activation request is missing or invalid")
    try:
        REQUEST.unlink()
    except FileNotFoundError:
        pass
    return doc


def _recover_existing_journal() -> None:
    journal = _read_json(JOURNAL)
    if not journal:
        return
    log("Found an incomplete prior vocoder activation journal; restoring its protected snapshot first")
    _rollback(journal)
    _finish_journal(journal, "recovered-before-new-activation")
    log("Previous incomplete vocoder activation was rolled back successfully")


def activate() -> int:
    if os.geteuid() != 0:
        raise SystemExit("vocoder activation runner must run as root")
    request = _read_request()
    job = {**request, "started_at": int(request.get("requested_at") or _now())}
    job_id = str(job["job_id"])
    lease_claimed = False
    update_fd = -1
    journal = {}
    mutated = False
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    JOB_LOG.write_text("", encoding="utf-8")
    os.chmod(JOB_LOG, 0o640)
    try:
        os.chown(JOB_LOG, 0, _gid())
    except Exception:
        pass
    try:
        maintenance_coordinator.adopt(
            job_id, "vocoder-activate", owner_pid=os.getpid(), service=ACTIVATION_SERVICE,
            phase="backing-up", cancellable=False,
        )
        lease_claimed = True
        update_fd = _acquire_update_lock()
        log("Starting transactional activation of the prepared DMR Audio Vocoder candidate")
        log("MMDVMHost, DMRGateway, BrandMeister, TGIF and scanner state will remain untouched")
        write_state(job, state="ACTIVATING", phase="backing-up", progress=8,
                    message="Validating prepared candidate and protected rollback state")

        _recover_existing_journal()
        candidate = _prepared_candidate()
        log(f"Prepared candidate verified: {candidate['binary_sha256']}")
        runtime = vocoder_manager.verified_runtime()
        if not runtime.get("ready"):
            raise RuntimeError("current exact YWD Extended runtime verification failed; refusing vocoder activation")
        log("Exact YWD Extended prerequisite verified")
        direct_test = _must([candidate["binary"], "--self-test"], 20)
        log("Prepared candidate self-test re-check PASS: " + direct_test[:240])

        manifest = _snapshot(job)
        backup_dir = str(manifest["backup_dir"])
        log(f"Protected live vocoder snapshot: {backup_dir}")
        journal = {
            "schema": 1,
            "job_id": job_id,
            "started_at": _now(),
            "phase": "backup-complete",
            "candidate_sha256": candidate["binary_sha256"],
            "backup": manifest,
            "mutated": False,
        }
        _write_journal(journal)

        maintenance_coordinator.update(job_id, phase="activating", cancellable=False, owner_pid=os.getpid())
        write_state(job, state="ACTIVATING", phase="activating", progress=38,
                    message="Briefly replacing only the vocoder backend/socket transaction")
        _run(["systemctl", "stop", SERVICE_UNIT], 20)
        _run(["systemctl", "stop", SOCKET_UNIT], 20)
        journal["phase"] = "live-replacement-started"
        journal["mutated"] = True
        mutated = True
        _write_journal(journal)
        _install_managed(candidate)
        log("Managed vocoder binary and dedicated socket/service units activated")

        maintenance_coordinator.update(job_id, phase="verifying", cancellable=False, owner_pid=os.getpid())
        write_state(job, state="VERIFYING", phase="verifying", progress=72,
                    message="Verifying socket activation, policy and live Protocol/decode path")
        journal["phase"] = "verifying"
        _write_journal(journal)
        verification = _verify_live(candidate)
        log("Live Protocol v1 STATUS verification PASS")
        log("Live 10-frame decode verification PASS")
        _write_provenance(candidate, verification, backup_dir)
        journal["phase"] = "complete"
        _write_journal(journal)
        _finish_journal(journal, "complete")
        _prune_backups()
        log("Transactional vocoder activation COMPLETE; protected rollback snapshot retained")
        write_state(job, state="COMPLETE", phase="complete", progress=100,
                    message="Managed vocoder candidate activated and verified", completed=True)
        return 0
    except Exception as exc:
        error = str(exc)[:1000]
        log("Activation error: " + error)
        if mutated and journal:
            try:
                maintenance_coordinator.update(job_id, phase="rolling-back", cancellable=False, owner_pid=os.getpid())
            except Exception:
                pass
            write_state(job, state="ROLLING_BACK", phase="rolling-back", progress=86,
                        message="Activation verification failed; restoring protected vocoder snapshot", error=error)
            try:
                _rollback(journal)
                _finish_journal(journal, "rolled-back")
                log("Automatic rollback PASS; previous vocoder files and service policy restored")
                write_state(job, state="FAILED_SAFE", phase="failed-safe", progress=100,
                            message="Activation failed safely; previous vocoder backend was restored",
                            error=error, completed=True)
                return 3
            except Exception as rollback_exc:
                rollback_error = f"{error}; rollback failed: {rollback_exc}"[:1000]
                log("CRITICAL rollback failure: " + str(rollback_exc)[:800])
                if journal:
                    journal["phase"] = "rollback-failed"
                    journal["rollback_error"] = str(rollback_exc)[:1000]
                    try:
                        _write_journal(journal)
                    except Exception:
                        pass
                write_state(job, state="ERROR", phase="rollback-failed", progress=100,
                            message="Vocoder activation and rollback failed; recovery journal retained",
                            error=rollback_error, completed=True)
                return 5
        write_state(job, state="FAILED_SAFE", phase="failed-safe", progress=100,
                    message="Vocoder activation was refused before live replacement",
                    error=error, completed=True)
        return 3
    finally:
        if update_fd >= 0:
            try:
                fcntl.flock(update_fd, fcntl.LOCK_UN)
            except Exception:
                pass
            os.close(update_fd)
        if lease_claimed:
            try:
                state = _read_json(JOB_STATE)
                outcome = "complete" if state.get("state") == "COMPLETE" else "failed-safe" if state.get("state") == "FAILED_SAFE" else "error"
                maintenance_coordinator.release(job_id, outcome=outcome, owner_pid=os.getpid())
            except Exception:
                pass


def recover() -> int:
    if os.geteuid() != 0:
        raise SystemExit("vocoder recovery must run as root")
    journal = _read_json(JOURNAL)
    if not journal:
        return 0
    update_fd = -1
    lease_claimed = False
    job_id = f"vocoder-recovery-{_now()}-{os.getpid()}"
    try:
        lease = maintenance_coordinator.inspect()
        if lease.get("stale"):
            maintenance_coordinator.recover_stale()
        elif lease.get("active"):
            raise RuntimeError("live appliance maintenance is active; vocoder recovery will retry later")
        maintenance_coordinator.claim(job_id, "vocoder-recovery", "rolling-back", cancellable=False, owner_pid=os.getpid(), service="ywd-vocoder-recovery.service")
        lease_claimed = True
        update_fd = _acquire_update_lock()
        _rollback(journal)
        _finish_journal(journal, "boot-recovered")
        return 0
    except Exception as exc:
        try:
            journal["phase"] = "recovery-failed"
            journal["recovery_error"] = str(exc)[:1000]
            _write_journal(journal)
        except Exception:
            pass
        return 1
    finally:
        if update_fd >= 0:
            try:
                fcntl.flock(update_fd, fcntl.LOCK_UN)
            except Exception:
                pass
            os.close(update_fd)
        if lease_claimed:
            try:
                maintenance_coordinator.release(job_id, outcome="recovered", owner_pid=os.getpid())
            except Exception:
                pass


def main() -> int:
    action = str(sys.argv[1] if len(sys.argv) > 1 else "activate")
    if action == "activate":
        return activate()
    if action == "recover":
        return recover()
    raise SystemExit("usage: vocoder_activation_runner.py [activate|recover]")


if __name__ == "__main__":
    raise SystemExit(main())
