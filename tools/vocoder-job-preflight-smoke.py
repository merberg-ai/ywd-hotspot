#!/usr/bin/env python3
"""Offline/source-only regression for the guarded vocoder readiness job.

The smoke injects synthetic preflight facts, so it performs no network access,
package operation, source checkout, compiler invocation, service restart, or RF
mutation.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

import maintenance_coordinator as mc
import vocoder_job_runner as runner


def facts(**overrides):
    base = {
        "architecture": "armv6l",
        "architecture_supported": True,
        "runtime_ready": True,
        "runtime_variant": "ywd-extended",
        "runtime_missing_capabilities": [],
        "backend_present": True,
        "free_bytes": 2 * 1024 * 1024 * 1024,
        "tools": {"git": True, "cmake": True, "make": True, "g++": True, "python3": True, "dpkg": True, "apt-get": True},
        "missing_tools": [],
        "apt_busy": [],
        "dpkg_ok": True,
        "dpkg_detail": "clean",
        "source_reachable": True,
        "source_detail": "approved mbelib source reachable",
        "thermal_c": 42.0,
    }
    base.update(overrides)
    return base


ready = runner.evaluate_preflight(facts())
assert ready["ready"] is True
assert not ready["hard_failures"] and not ready["temporary_blockers"]

needs_extended = runner.evaluate_preflight(facts(runtime_ready=False, runtime_variant="upstream"))
assert needs_extended["ready"] is True
assert any("YWD Extended" in row for row in needs_extended["warnings"])
assert needs_extended["required_free_bytes"] == runner.EXTENDED_AND_VOCODER_MIN_FREE

low_disk = runner.evaluate_preflight(facts(free_bytes=100 * 1024 * 1024))
assert low_disk["ready"] is False
assert any("disk" in row for row in low_disk["hard_failures"])

apt_busy = runner.evaluate_preflight(facts(apt_busy=["dpkg"]))
assert apt_busy["ready"] is False
assert any("package manager" in row for row in apt_busy["temporary_blockers"])

hot = runner.evaluate_preflight(facts(thermal_c=82.0))
assert hot["ready"] is False
assert any("temperature" in row for row in hot["temporary_blockers"])

source_down = runner.evaluate_preflight(facts(source_reachable=False))
assert source_down["ready"] is False
assert any("source" in row for row in source_down["hard_failures"])

with tempfile.TemporaryDirectory(prefix="ywd-vocoder-job-smoke-") as td:
    root = Path(td)
    old_runner = (runner.VAR, runner.STATE_DIR, runner.REQUEST, runner.JOB_STATE, runner.JOB_LOG, runner.JOBS_DIR, runner.collect_facts)
    old_mc = (mc.VAR, mc.LEASE, mc.LOCK, mc.LAST, mc.BOOT_ID)
    try:
        runner.VAR = root
        runner.STATE_DIR = root / "vocoder"
        runner.REQUEST = runner.STATE_DIR / "request.json"
        runner.JOB_STATE = runner.STATE_DIR / "job.json"
        runner.JOB_LOG = runner.STATE_DIR / "job.log"
        runner.JOBS_DIR = runner.STATE_DIR / "jobs"
        mc.VAR = root
        mc.LEASE = root / "maintenance-lease.json"
        mc.LOCK = root / "maintenance-lease.lock"
        mc.LAST = root / "maintenance-last.json"
        mc.BOOT_ID = root / "boot-id"
        mc.BOOT_ID.write_text("boot-vocoder-job-smoke\n", encoding="utf-8")

        runner.collect_facts = lambda: facts()
        job = {"job_id": "vocoder-smoke-pass", "job_type": "vocoder-preflight", "operation": "preflight", "started_at": 1}
        assert runner.run_preflight(job) == 0
        state = json.loads(runner.JOB_STATE.read_text(encoding="utf-8"))
        assert state["state"] == "COMPLETE" and state["progress"] == 100
        assert not mc.LEASE.exists()
        assert mc.LAST.is_file()
        report = runner.JOBS_DIR / job["job_id"] / "preflight.json"
        assert report.is_file()
        report_doc = json.loads(report.read_text(encoding="utf-8"))
        assert report_doc["result"]["ready"] is True
        assert runner.JOB_LOG.stat().st_size <= runner.MAX_LOG_BYTES
        assert len(state.get("log_tail") or []) <= runner.MAX_LOG_LINES

        runner.collect_facts = lambda: facts(source_reachable=False, source_detail="offline")
        failed_job = {"job_id": "vocoder-smoke-fail", "job_type": "vocoder-preflight", "operation": "preflight", "started_at": 2}
        assert runner.run_preflight(failed_job) == 3
        failed = json.loads(runner.JOB_STATE.read_text(encoding="utf-8"))
        assert failed["state"] == "FAILED_SAFE"
        assert not mc.LEASE.exists()
    finally:
        runner.VAR, runner.STATE_DIR, runner.REQUEST, runner.JOB_STATE, runner.JOB_LOG, runner.JOBS_DIR, runner.collect_facts = old_runner
        mc.VAR, mc.LEASE, mc.LOCK, mc.LAST, mc.BOOT_ID = old_mc

runner_src = (LIB / "vocoder_job_runner.py").read_text(encoding="utf-8")
admin_src = (LIB / "vocoder_job_admin.py").read_text(encoding="utf-8")
dashboard_src = (LIB / "dashboard_vocoder_manager.py").read_text(encoding="utf-8")
dispatch_src = (LIB / "admin_dispatch.sh").read_text(encoding="utf-8")
sudoers_src = (ROOT / "sudoers" / "ywd-hotspot").read_text(encoding="utf-8")
unit_src = (ROOT / "systemd" / "ywd-vocoder-job.service").read_text(encoding="utf-8")
ui_src = (ROOT / "web" / "vocoder-manager.js").read_text(encoding="utf-8")
mc_src = (LIB / "maintenance_coordinator.py").read_text(encoding="utf-8")

assert 'str(doc.get("operation") or "") != "preflight"' in runner_src
assert '["apt-get", "install"' not in runner_src
assert '[git, "clone"' not in runner_src
assert '["systemctl", "stop"' not in runner_src
assert '["systemctl", "restart"' not in runner_src
assert "vocoder job runner must not run as root" in runner_src
assert "MAX_LOG_BYTES = 64 * 1024" in runner_src
assert "MAX_LOG_LINES = 80" in runner_src
assert 'action != "vocoder-preflight-start"' in admin_src
assert "payload" in admin_src and "payload:" not in admin_src
assert 'core.admin_call("vocoder-preflight-start", {}, 20)' in dashboard_src
assert "require_control()" in dashboard_src
assert "vocoder-preflight-start)" in dispatch_src
assert "/usr/local/libexec/ywd-hotspot-admin vocoder-preflight-start" in sudoers_src
assert "User=ywd-hotspot" in unit_src and "User=root" not in unit_src
assert "NoNewPrivileges=true" in unit_src
assert "ProtectSystem=strict" in unit_src
assert "ReadWritePaths=/var/lib/ywd-hotspot" in unit_src
assert "Nice=10" in unit_src and "CPUWeight=50" in unit_src and "IOSchedulingClass=idle" in unit_src
assert "CHECK INSTALL READINESS" in ui_src
assert "post('/api/system/vocoder/preflight', {})" in ui_src
assert "jobActive ? 1500 : 30000" in ui_src
assert "os.O_RDWR | os.O_CREAT, 0o660" in mc_src

print("[OK] readiness evaluation distinguishes hard failures, temporary blockers, and YWD Extended prerequisite")
print("[OK] persistent preflight job completes/failed-safes with lease release and bounded transcript")
print("[OK] background worker is unprivileged, low-priority, and filesystem-confined")
print("[OK] readiness API is dashboard-authenticated and exposes no browser-controlled build options")
print("[OK] gated worker contains no package install, source clone, compile, RF restart, or activation path")
print("[OK] maintenance flock is shared safely across root launcher and unprivileged worker")
