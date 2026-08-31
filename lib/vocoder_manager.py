#!/usr/bin/env python3
"""Authoritative state model for the RC4 DMR Audio Vocoder manager.

Normal System-page polling is intentionally lightweight: it reads the persisted
YWD runtime identity plus passive systemd/file state and never wakes the decoder
or launches the expensive MMDVM helper verification path. Exact installed
binary/runtime verification remains available to guarded background jobs before
any future build or activation decision.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path

import maintenance_coordinator
import mmdvm_runtime_state
import vocoder_protocol

VAR = Path(os.environ.get("YWD_VAR", "/var/lib/ywd-hotspot"))
STATE_DIR = Path(os.environ.get("YWD_VOCODER_STATE_DIR", str(VAR / "vocoder")))
PROVENANCE = Path(os.environ.get("YWD_VOCODER_PROVENANCE", str(STATE_DIR / "installed.json")))
JOB_STATE = Path(os.environ.get("YWD_VOCODER_JOB_STATE", str(STATE_DIR / "job.json")))
BACKEND_BINARY = Path(os.environ.get("YWD_VOCODER_BINARY", "/usr/local/libexec/ywd-vocoder-mbelib"))
SOCKET_PATH = Path(os.environ.get("YWD_VOCODER_SOCKET", "/run/ywd-vocoder.sock"))
SERVICE_UNIT = "ywd-vocoder-mbelib.service"
SOCKET_UNIT = "ywd-vocoder-mbelib.socket"
POLICY_DROPIN = Path("/etc/systemd/system/ywd-vocoder-mbelib.service.d/20-ywd-hotspot-normal-priority.conf")

MANAGER_SCHEMA = 1
BACKEND_RECIPE = "mbelib-v1"
BACKEND_RECIPE_VERSION = 1
APPROVED_SOURCE = "https://github.com/szechyjs/mbelib.git"
APPROVED_MBELIB_COMMIT = "9a04ed5c78176a9965f3d43f7aa1b1f5330e771f"
PROTOCOL_VERSION = int(vocoder_protocol.VERSION)
REQUIRED_RUNTIME_CAPABILITIES = tuple(mmdvm_runtime_state.YWD_EXTENDED_CAPABILITIES)
SUPPORTED_ARCHITECTURES = {"armv6l", "armv7l", "aarch64", "x86_64"}
EXPECTED_NICE = 0
EXPECTED_CPU_WEIGHT = 200

IN_PROGRESS_STATES = {
    "CHECKING", "WAITING_FOR_APT", "DOWNLOADING", "BUILDING", "STAGING",
    "WAITING_FOR_RF_IDLE", "ACTIVATING", "VERIFYING", "ROLLING_BACK",
}
PHASE_STATE = {
    "checking": "CHECKING",
    "preparing": "CHECKING",
    "waiting-for-apt": "WAITING_FOR_APT",
    "downloading": "DOWNLOADING",
    "building": "BUILDING",
    "building-ywd-extended": "BUILDING",
    "building-vocoder": "BUILDING",
    "staging": "STAGING",
    "candidate-ready": "STAGING",
    "waiting-for-rf-idle": "WAITING_FOR_RF_IDLE",
    "activation-started": "ACTIVATING",
    "activating": "ACTIVATING",
    "verifying": "VERIFYING",
    "rolling-back": "ROLLING_BACK",
    "complete": "COMPLETE",
    "failed": "FAILED_SAFE",
    "failed-safe": "FAILED_SAFE",
}
PUBLIC_JOB_KEYS = {
    "job_id", "job_type", "state", "phase", "progress", "message",
    "started_at", "updated_at", "completed_at", "cancellable", "error",
    "log_tail",
}


def _read_json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def _run(args: list[str], timeout: int = 4) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return subprocess.CompletedProcess(args, 127, "", str(exc))


def _unit_exists(unit: str) -> bool:
    return _run(["systemctl", "cat", unit], 3).returncode == 0


def _unit_active(unit: str) -> str:
    p = _run(["systemctl", "is-active", unit], 3)
    text = (p.stdout or p.stderr or "unknown").strip().lower()
    return text or "unknown"


def _unit_enabled(unit: str) -> str:
    p = _run(["systemctl", "is-enabled", unit], 3)
    text = (p.stdout or p.stderr or "unknown").strip().lower()
    return text or "unknown"


def _effective_policy() -> dict:
    if not _unit_exists(SERVICE_UNIT):
        return {"available": False, "ok": False}
    p = _run([
        "systemctl", "show", SERVICE_UNIT,
        "-p", "Nice", "-p", "CPUWeight", "-p", "CPUSchedulingPolicy",
    ], 4)
    values = {}
    for raw in (p.stdout or "").splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key.strip()] = value.strip()
    try:
        nice = int(values.get("Nice", ""))
    except Exception:
        nice = None
    try:
        cpu_weight = int(values.get("CPUWeight", ""))
    except Exception:
        cpu_weight = None
    sched = str(values.get("CPUSchedulingPolicy") or "").strip().lower() or "other"
    ok = p.returncode == 0 and nice == EXPECTED_NICE and cpu_weight == EXPECTED_CPU_WEIGHT and sched in {"other", "0"}
    return {
        "available": p.returncode == 0,
        "nice": nice,
        "cpu_weight": cpu_weight,
        "scheduling_policy": sched,
        "expected_nice": EXPECTED_NICE,
        "expected_cpu_weight": EXPECTED_CPU_WEIGHT,
        "ok": bool(ok),
    }


def _sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(128 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _current_runtime_pins() -> dict:
    """Return only the pins needed to validate persisted YWD Extended identity."""
    try:
        pins = mmdvm_runtime_state._pins()
    except Exception:
        pins = {}
    return {
        "upstream_commit": str(pins.get("MMDVM_HOST_COMMIT") or ""),
        "patch_sha256": str(pins.get("MMDVM_YWD_PATCH_SHA256") or "").lower(),
    }


def _runtime() -> dict:
    """Fast dashboard projection from the last verified persisted runtime state.

    This deliberately does not invoke mmdvm_voice_build.py or the upstream build
    helper. It still binds the persisted identity to the *current* release pins,
    so a later app release that changes the accepted upstream/patch identity is
    shown as not ready until the runtime is explicitly refreshed.
    """
    try:
        persisted = mmdvm_runtime_state.persisted_state()
    except Exception as exc:
        persisted = {}
        error = str(exc)[:300]
    else:
        error = ""

    pins = _current_runtime_pins()
    caps = sorted({str(x) for x in (persisted.get("capabilities") or [])})
    missing = sorted(set(REQUIRED_RUNTIME_CAPABILITIES) - set(caps))
    variant = str(persisted.get("variant") or "unknown")
    expected_upstream = pins["upstream_commit"]
    expected_patch = pins["patch_sha256"]
    persisted_upstream = str(persisted.get("upstream_commit") or "")
    persisted_patch = str(persisted.get("patch_sha256") or "").lower()
    identity_matches = bool(
        variant == "ywd-extended"
        and persisted.get("binary_sha256")
        and expected_upstream
        and expected_patch
        and persisted_upstream == expected_upstream
        and persisted_patch == expected_patch
    )
    ready = bool(
        identity_matches
        and not missing
        and not bool(persisted.get("upgrade_required"))
        and str(persisted.get("runtime_generation") or "current") == "current"
    )
    out = {
        "ready": ready,
        "variant": variant,
        "runtime_generation": str(persisted.get("runtime_generation") or "unknown"),
        "in_sync": identity_matches,
        "extension_api": persisted.get("extension_api"),
        "capabilities": caps,
        "missing_capabilities": missing,
        "upgrade_required": bool(persisted.get("upgrade_required")),
        "binary_sha256": persisted.get("binary_sha256"),
        "verification": "persisted-current-pin-identity",
        "selected_at": persisted.get("selected_at"),
    }
    if error:
        out["error"] = error
    elif not persisted:
        out["error"] = "persisted MMDVM runtime identity is unavailable"
    elif variant == "ywd-extended" and not identity_matches:
        out["error"] = "persisted YWD Extended identity does not match the current release pins"
    return out


def verified_runtime() -> dict:
    """Perform the expensive exact installed-runtime verification for jobs/gates."""
    try:
        doc = mmdvm_runtime_state.status()
    except Exception as exc:
        return {
            "ready": False,
            "variant": "unknown",
            "in_sync": False,
            "capabilities": [],
            "missing_capabilities": list(REQUIRED_RUNTIME_CAPABILITIES),
            "verification": "exact-installed-runtime",
            "error": str(exc)[:300],
        }
    observed = doc.get("observed") if isinstance(doc.get("observed"), dict) else {}
    caps = sorted({str(x) for x in (observed.get("capabilities") or [])})
    missing = sorted(set(REQUIRED_RUNTIME_CAPABILITIES) - set(caps))
    ready = (
        observed.get("installed") is True
        and observed.get("variant") == "ywd-extended"
        and bool(doc.get("in_sync"))
        and not missing
        and not bool(observed.get("upgrade_required"))
    )
    return {
        "ready": bool(ready),
        "variant": str(observed.get("variant") or "unknown"),
        "runtime_generation": str(observed.get("runtime_generation") or "unknown"),
        "in_sync": bool(doc.get("in_sync")),
        "extension_api": observed.get("extension_api"),
        "capabilities": caps,
        "missing_capabilities": missing,
        "upgrade_required": bool(observed.get("upgrade_required")),
        "binary_sha256": observed.get("binary_sha256"),
        "verification": "exact-installed-runtime",
    }


def _public_job() -> dict:
    doc = _read_json(JOB_STATE)
    if not doc:
        return {"active": False, "state": "IDLE", "phase": "idle", "log_tail": []}
    out = {k: doc.get(k) for k in PUBLIC_JOB_KEYS if k in doc}
    phase = str(out.get("phase") or "").strip().lower()
    state = str(out.get("state") or PHASE_STATE.get(phase) or "IDLE").strip().upper()
    out["state"] = state[:40]
    out["phase"] = phase[:64] or "idle"
    try:
        out["progress"] = max(0, min(100, int(out.get("progress") or 0)))
    except Exception:
        out["progress"] = 0
    for key in ("job_id", "job_type", "message", "error"):
        if out.get(key) is not None:
            out[key] = str(out[key])[:1000 if key == "error" else 300]
    rows = out.get("log_tail")
    if not isinstance(rows, list):
        rows = []
    out["log_tail"] = [str(x).replace("\x00", "")[:500] for x in rows[-80:]]
    out["active"] = state in IN_PROGRESS_STATES
    return out


def passive_snapshot() -> dict:
    """Collect lightweight manager state without waking the decoder backend."""
    provenance = _read_json(PROVENANCE)
    runtime = _runtime()
    service_exists = _unit_exists(SERVICE_UNIT)
    socket_exists = _unit_exists(SOCKET_UNIT)
    socket_active = _unit_active(SOCKET_UNIT) if socket_exists else "not-found"
    socket_enabled = _unit_enabled(SOCKET_UNIT) if socket_exists else "not-found"
    service_active = _unit_active(SERVICE_UNIT) if service_exists else "not-found"
    binary_present = BACKEND_BINARY.is_file()
    policy = _effective_policy()
    binary_sha = _sha256(BACKEND_BINARY) if binary_present else None
    arch = platform.machine().strip().lower() or "unknown"
    job = _public_job()
    maintenance = maintenance_coordinator.public_status()

    return {
        "manager_schema": MANAGER_SCHEMA,
        "mutations_enabled": False,
        "architecture": arch,
        "architecture_supported": arch in SUPPORTED_ARCHITECTURES,
        "recipe": {
            "id": BACKEND_RECIPE,
            "version": BACKEND_RECIPE_VERSION,
            "protocol": PROTOCOL_VERSION,
            "mbelib_commit": APPROVED_MBELIB_COMMIT,
        },
        "backend": {
            "binary": str(BACKEND_BINARY),
            "binary_present": binary_present,
            "binary_sha256": binary_sha,
            "service_unit": SERVICE_UNIT,
            "service_exists": service_exists,
            "service_state": service_active,
            "socket_unit": SOCKET_UNIT,
            "socket_exists": socket_exists,
            "socket_state": socket_active,
            "socket_enabled": socket_enabled,
            "socket_path": str(SOCKET_PATH),
            "socket_path_present": SOCKET_PATH.exists(),
            "policy": policy,
        },
        "runtime": runtime,
        "provenance": provenance,
        "job": job,
        "maintenance": maintenance,
        "collected_at": int(time.time()),
    }


def classify_snapshot(snapshot: dict) -> dict:
    """Convert passive facts into one operator-facing authoritative state."""
    snap = dict(snapshot or {})
    backend = snap.get("backend") if isinstance(snap.get("backend"), dict) else {}
    runtime = snap.get("runtime") if isinstance(snap.get("runtime"), dict) else {}
    recipe = snap.get("recipe") if isinstance(snap.get("recipe"), dict) else {}
    provenance = snap.get("provenance") if isinstance(snap.get("provenance"), dict) else {}
    job = snap.get("job") if isinstance(snap.get("job"), dict) else {}

    job_state = str(job.get("state") or "").upper()
    if job.get("active") and job_state in IN_PROGRESS_STATES:
        return {"state": job_state, "reason": str(job.get("message") or "Managed vocoder maintenance is in progress")[:300]}

    installed_any = bool(backend.get("binary_present") or backend.get("service_exists") or backend.get("socket_exists"))
    if not installed_any:
        return {
            "state": "NOT_INSTALLED",
            "reason": "No managed/external mbelib vocoder backend is installed.",
            "recommended_action": "INSTALL VOCODER",
        }

    complete = bool(backend.get("binary_present") and backend.get("service_exists") and backend.get("socket_exists"))
    if not complete:
        return {
            "state": "REPAIR_REQUIRED",
            "reason": "The vocoder installation is incomplete: required binary or systemd units are missing.",
            "recommended_action": "REPAIR / REINSTALL",
        }

    if not bool(runtime.get("ready")):
        return {
            "state": "YWD_EXTENDED_REQUIRED",
            "reason": "Live DMR audio requires the current verified YWD Extended MMDVM runtime and demand-gated voice capabilities.",
            "recommended_action": "BUILD YWD EXTENDED",
        }

    policy = backend.get("policy") if isinstance(backend.get("policy"), dict) else {}
    if not bool(policy.get("ok")) or str(backend.get("socket_state") or "") in {"failed", "not-found"}:
        return {
            "state": "REPAIR_REQUIRED",
            "reason": "The backend files exist, but socket activation or the YWD scheduling policy needs repair.",
            "recommended_action": "REPAIR / REINSTALL",
        }

    if str(backend.get("socket_enabled") or "") not in {"enabled", "enabled-runtime", "static"}:
        return {
            "state": "DISABLED",
            "reason": "The vocoder backend is installed but socket activation is disabled.",
            "recommended_action": "ENABLE VOCODER",
        }

    if provenance:
        try:
            installed_recipe = int(provenance.get("recipe_version"))
        except Exception:
            installed_recipe = None
        try:
            installed_protocol = int(provenance.get("protocol_version"))
        except Exception:
            installed_protocol = None
        installed_commit = str(provenance.get("mbelib_commit") or "")
        if (
            installed_recipe != int(recipe.get("version") or BACKEND_RECIPE_VERSION)
            or installed_protocol != int(recipe.get("protocol") or PROTOCOL_VERSION)
            or installed_commit != str(recipe.get("mbelib_commit") or APPROVED_MBELIB_COMMIT)
        ):
            return {
                "state": "UPDATE_REQUIRED",
                "reason": "The installed managed backend does not match this YWD release's approved vocoder recipe/protocol/source pin.",
                "recommended_action": "UPDATE VOCODER",
            }

    process = str(backend.get("service_state") or "unknown")
    dormant = process in {"inactive", "dead", "deactivating"}
    return {
        "state": "READY",
        "reason": "Vocoder socket activation is available. A dormant decoder process is normal until audio is requested." if dormant else "Vocoder backend is available.",
        "process_mode": "DORMANT" if dormant else "ACTIVE" if process == "active" else process.upper(),
        "recommended_action": "TEST VOCODER",
        "managed_provenance": bool(provenance),
    }


def status() -> dict:
    snap = passive_snapshot()
    classification = classify_snapshot(snap)
    provenance = snap.get("provenance") if isinstance(snap.get("provenance"), dict) else {}
    last_test = provenance.get("last_self_test") if isinstance(provenance.get("last_self_test"), dict) else None
    return {
        "ok": True,
        "state": classification,
        "manager_schema": snap["manager_schema"],
        "mutations_enabled": False,
        "architecture": snap["architecture"],
        "architecture_supported": snap["architecture_supported"],
        "recipe": snap["recipe"],
        "backend": snap["backend"],
        "runtime": snap["runtime"],
        "managed": bool(provenance),
        "installed_provenance": {
            "recipe_version": provenance.get("recipe_version"),
            "protocol_version": provenance.get("protocol_version"),
            "mbelib_commit": provenance.get("mbelib_commit"),
            "architecture": provenance.get("architecture"),
            "compiler": provenance.get("compiler"),
            "binary_sha256": provenance.get("binary_sha256"),
            "installed_at": provenance.get("installed_at"),
        } if provenance else None,
        "last_self_test": last_test,
        "job": snap["job"],
        "maintenance": snap["maintenance"],
        "collected_at": snap["collected_at"],
    }


if __name__ == "__main__":
    print(json.dumps(status(), indent=2, sort_keys=True))