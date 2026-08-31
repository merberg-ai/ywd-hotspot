#!/usr/bin/env python3
"""Persistent unprivileged job runner for RC4 vocoder maintenance.

This first gated generation supports only the non-destructive `preflight`
operation. It may inspect local/system/network readiness and write bounded state,
logs, and staging reports under /var/lib/ywd-hotspot. It does not install
packages, clone/build source, stop/restart RF, or activate runtime/backend files.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import maintenance_coordinator
import vocoder_manager

VAR = Path(os.environ.get("YWD_VAR", "/var/lib/ywd-hotspot"))
STATE_DIR = Path(os.environ.get("YWD_VOCODER_STATE_DIR", str(VAR / "vocoder")))
REQUEST = Path(os.environ.get("YWD_VOCODER_JOB_REQUEST", str(STATE_DIR / "request.json")))
JOB_STATE = Path(os.environ.get("YWD_VOCODER_JOB_STATE", str(STATE_DIR / "job.json")))
JOB_LOG = Path(os.environ.get("YWD_VOCODER_JOB_LOG", str(STATE_DIR / "job.log")))
JOBS_DIR = Path(os.environ.get("YWD_VOCODER_JOBS_DIR", str(STATE_DIR / "jobs")))
MAX_LOG_BYTES = 64 * 1024
MAX_LOG_LINES = 80
VOCODER_ONLY_MIN_FREE = 768 * 1024 * 1024
EXTENDED_AND_VOCODER_MIN_FREE = 1536 * 1024 * 1024


def _now() -> int:
    return int(time.time())


def _atomic_json(path: Path, doc: dict, mode: int = 0o640) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, mode)
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
    text = data.decode("utf-8", "replace").replace("\x00", "")
    return [line[:500] for line in text.splitlines()[-MAX_LOG_LINES:]]


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
    os.replace(tmp, JOB_LOG)


def log(message: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    clean = " ".join(str(message or "").replace("\x00", "").splitlines()).strip()[:1200]
    stamp = time.strftime("%H:%M:%S", time.localtime())
    with JOB_LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {clean}\n")
    os.chmod(JOB_LOG, 0o640)
    _prune_log()


def write_state(job: dict, *, state: str, phase: str, progress: int, message: str,
                cancellable: bool = True, error: str | None = None,
                completed: bool = False) -> dict:
    now = _now()
    doc = {
        "schema": 1,
        "job_id": str(job.get("job_id") or "")[:96],
        "job_type": str(job.get("job_type") or "vocoder-preflight")[:64],
        "operation": str(job.get("operation") or "preflight")[:32],
        "state": str(state or "CHECKING").upper()[:40],
        "phase": str(phase or "checking").lower()[:64],
        "progress": max(0, min(100, int(progress))),
        "message": str(message or "")[:300],
        "started_at": int(job.get("started_at") or now),
        "updated_at": now,
        "cancellable": bool(cancellable),
        "log_tail": _tail(),
    }
    if error:
        doc["error"] = str(error)[-1000:]
    if completed:
        doc["completed_at"] = now
    _atomic_json(JOB_STATE, doc)
    return doc


def _run(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C"},
        )
    except Exception as exc:
        return subprocess.CompletedProcess(args, 127, "", str(exc))


def _apt_busy() -> list[str]:
    busy = []
    proc = Path("/proc")
    for entry in proc.iterdir() if proc.is_dir() else []:
        if not entry.name.isdigit():
            continue
        try:
            name = (entry / "comm").read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if name in {"apt", "apt-get", "dpkg", "unattended-upgr"}:
            busy.append(name)
    return sorted(set(busy))


def _thermal_c() -> float | None:
    path = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        raw = float(path.read_text(encoding="utf-8").strip())
        return raw / 1000.0 if raw > 200 else raw
    except Exception:
        return None


def _source_reachable() -> tuple[bool, str]:
    try:
        with socket.create_connection(("github.com", 443), timeout=5):
            pass
    except Exception as exc:
        return False, f"GitHub network check failed: {exc}"
    git = shutil.which("git")
    if not git:
        return True, "GitHub reachable; git is not installed yet"
    p = _run([git, "ls-remote", vocoder_manager.APPROVED_SOURCE, "HEAD"], timeout=15)
    if p.returncode != 0:
        return False, (p.stderr or p.stdout or "approved source check failed").strip()[:240]
    return True, "approved mbelib source reachable"


def collect_facts() -> dict:
    snapshot = vocoder_manager.passive_snapshot()
    runtime = snapshot.get("runtime") if isinstance(snapshot.get("runtime"), dict) else {}
    usage = shutil.disk_usage(VAR)
    tools = {name: bool(shutil.which(name)) for name in ("git", "cmake", "make", "g++", "python3", "dpkg", "apt-get")}
    dpkg = _run(["dpkg", "--audit"], timeout=12) if tools.get("dpkg") else subprocess.CompletedProcess([], 127, "", "dpkg missing")
    source_ok, source_detail = _source_reachable()
    return {
        "architecture": platform.machine().strip().lower() or "unknown",
        "architecture_supported": bool(snapshot.get("architecture_supported")),
        "runtime_ready": bool(runtime.get("ready")),
        "runtime_variant": str(runtime.get("variant") or "unknown"),
        "runtime_missing_capabilities": list(runtime.get("missing_capabilities") or []),
        "backend_present": bool((snapshot.get("backend") or {}).get("binary_present")),
        "free_bytes": int(usage.free),
        "tools": tools,
        "missing_tools": sorted(name for name, present in tools.items() if not present),
        "apt_busy": _apt_busy(),
        "dpkg_ok": bool(dpkg.returncode == 0 and not (dpkg.stdout or "").strip()),
        "dpkg_detail": (dpkg.stdout or dpkg.stderr or "clean").strip()[:300],
        "source_reachable": bool(source_ok),
        "source_detail": source_detail,
        "thermal_c": _thermal_c(),
    }


def evaluate_preflight(facts: dict) -> dict:
    runtime_ready = bool(facts.get("runtime_ready"))
    required_free = VOCODER_ONLY_MIN_FREE if runtime_ready else EXTENDED_AND_VOCODER_MIN_FREE
    hard_failures = []
    temporary_blockers = []
    warnings = []

    if not facts.get("architecture_supported"):
        hard_failures.append(f"unsupported architecture: {facts.get('architecture') or 'unknown'}")
    if int(facts.get("free_bytes") or 0) < required_free:
        hard_failures.append(f"insufficient free disk space; need at least {required_free // (1024 * 1024)} MiB")
    if not facts.get("dpkg_ok"):
        hard_failures.append("dpkg reports an inconsistent package state")
    if not facts.get("source_reachable"):
        hard_failures.append("approved mbelib source is not reachable")
    if facts.get("apt_busy"):
        temporary_blockers.append("package manager is currently busy: " + ", ".join(facts.get("apt_busy") or []))

    missing = list(facts.get("missing_tools") or [])
    if missing:
        if "apt-get" in missing or "dpkg" in missing or "python3" in missing:
            hard_failures.append("required base package tools are missing: " + ", ".join(missing))
        else:
            warnings.append("build tools will need installation: " + ", ".join(missing))

    thermal = facts.get("thermal_c")
    try:
        if thermal is not None and float(thermal) >= 78.0:
            temporary_blockers.append(f"system temperature is high ({float(thermal):.1f} C); wait before compiling")
    except Exception:
        pass

    if not runtime_ready:
        warnings.append("YWD Extended must be prepared before vocoder installation")

    ready = not hard_failures and not temporary_blockers
    return {
        "ready": ready,
        "required_free_bytes": required_free,
        "hard_failures": hard_failures,
        "temporary_blockers": temporary_blockers,
        "warnings": warnings,
    }


def _read_request() -> dict:
    try:
        doc = json.loads(REQUEST.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"vocoder job request unavailable: {exc}") from exc
    if not isinstance(doc, dict):
        raise RuntimeError("vocoder job request is invalid")
    if str(doc.get("operation") or "") != "preflight":
        raise RuntimeError("this gated job runner accepts only preflight")
    if not doc.get("job_id"):
        raise RuntimeError("vocoder job request has no job id")
    try:
        REQUEST.unlink()
    except FileNotFoundError:
        pass
    return doc


def run_preflight(job: dict) -> int:
    job = dict(job)
    job.setdefault("job_type", "vocoder-preflight")
    job.setdefault("started_at", _now())
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    JOB_LOG.write_text("", encoding="utf-8")
    os.chmod(JOB_LOG, 0o640)

    lease_claimed = False
    try:
        maintenance_coordinator.claim(
            str(job["job_id"]), "vocoder-preflight", "checking",
            cancellable=True, owner_pid=os.getpid(), service="ywd-vocoder-job.service",
        )
        lease_claimed = True
        log("Starting DMR Audio Vocoder install-readiness preflight")
        log("This gated job does not install packages, download source, compile, or restart RF")
        write_state(job, state="CHECKING", phase="checking", progress=8,
                    message="Checking appliance and vocoder prerequisites")

        facts = collect_facts()
        log(f"Architecture: {facts['architecture']} ({'supported' if facts['architecture_supported'] else 'unsupported'})")
        log(f"Free disk: {facts['free_bytes'] // (1024 * 1024)} MiB")
        log(f"YWD Extended: {'ready' if facts['runtime_ready'] else 'required'} ({facts['runtime_variant']})")
        if facts["runtime_missing_capabilities"]:
            log("Missing runtime capabilities: " + ", ".join(facts["runtime_missing_capabilities"]))
        log("Build tools present: " + ", ".join(name for name, ok in facts["tools"].items() if ok))
        if facts["missing_tools"]:
            log("Build tools missing: " + ", ".join(facts["missing_tools"]))
        log("Package manager: " + ("busy: " + ", ".join(facts["apt_busy"]) if facts["apt_busy"] else "idle"))
        log("dpkg state: " + ("clean" if facts["dpkg_ok"] else facts["dpkg_detail"] or "check required"))
        log("Source access: " + facts["source_detail"])
        if facts["thermal_c"] is not None:
            log(f"System temperature: {facts['thermal_c']:.1f} C")

        result = evaluate_preflight(facts)
        report = {
            "schema": 1,
            "job_id": job["job_id"],
            "checked_at": _now(),
            "facts": facts,
            "result": result,
        }
        job_dir = JOBS_DIR / str(job["job_id"])
        job_dir.mkdir(parents=True, exist_ok=True)
        _atomic_json(job_dir / "preflight.json", report)

        for warning in result["warnings"]:
            log("WARN: " + warning)
        for blocker in result["temporary_blockers"]:
            log("WAIT: " + blocker)
        for failure in result["hard_failures"]:
            log("FAIL: " + failure)

        if result["ready"]:
            log("Preflight PASS: appliance is ready for the later prepare/build stage")
            write_state(job, state="COMPLETE", phase="complete", progress=100,
                        message="Install readiness check passed; no live runtime changes were made",
                        cancellable=False, completed=True)
            maintenance_coordinator.release(str(job["job_id"]), outcome="complete", owner_pid=os.getpid())
            lease_claimed = False
            return 0

        if result["hard_failures"]:
            message = "Install readiness check found blockers; no live runtime changes were made"
        else:
            message = "Install readiness check found temporary conditions to resolve before building"
        log(message)
        write_state(job, state="FAILED_SAFE", phase="failed-safe", progress=100,
                    message=message, error="; ".join(result["hard_failures"] + result["temporary_blockers"]),
                    cancellable=False, completed=True)
        maintenance_coordinator.release(str(job["job_id"]), outcome="failed-safe", owner_pid=os.getpid())
        lease_claimed = False
        return 3
    except Exception as exc:
        log(f"FAILED SAFE: {exc}")
        try:
            write_state(job, state="FAILED_SAFE", phase="failed-safe", progress=100,
                        message="Readiness job failed safely; no live runtime changes were made",
                        error=str(exc), cancellable=False, completed=True)
        except Exception:
            pass
        if lease_claimed:
            try:
                maintenance_coordinator.release(str(job["job_id"]), outcome="failed-safe", owner_pid=os.getpid())
            except Exception:
                pass
        return 2


def main() -> int:
    if os.geteuid() == 0:
        print("vocoder job runner must not run as root", file=sys.stderr)
        return 2
    try:
        request = _read_request()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return run_preflight(request)


if __name__ == "__main__":
    raise SystemExit(main())
