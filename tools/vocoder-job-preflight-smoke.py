#!/usr/bin/env python3
"""Offline/source-only regression for the guarded vocoder readiness job.

The smoke injects synthetic preflight facts, so it performs no network access,
package operation, source checkout, compiler invocation, service restart, live
activation, or RF mutation.
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
import vocoder_backend_build as build
import vocoder_job_runner as runner


def facts(**overrides):
    base = {
        "architecture": "armv6l",
        "architecture_supported": True,
        "runtime_ready": True,
        "runtime_variant": "ywd-extended",
        "runtime_in_sync": True,
        "runtime_verification": "exact-installed-runtime",
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
assert low_disk["ready"] is False and any("disk" in row for row in low_disk["hard_failures"])
apt_busy = runner.evaluate_preflight(facts(apt_busy=["dpkg"]))
assert apt_busy["ready"] is False and any("package manager" in row for row in apt_busy["temporary_blockers"])
hot = runner.evaluate_preflight(facts(thermal_c=82.0))
assert hot["ready"] is False and any("temperature" in row for row in hot["temporary_blockers"])
source_down = runner.evaluate_preflight(facts(source_reachable=False))
assert source_down["ready"] is False and any("source" in row for row in source_down["hard_failures"])

with tempfile.TemporaryDirectory(prefix="ywd-vocoder-job-smoke-") as td:
    root = Path(td)
    old_runner = (runner.VAR, runner.STATE_DIR, runner.REQUEST, runner.JOB_STATE, runner.JOB_LOG, runner.JOBS_DIR, runner.collect_facts)
    old_mc = (mc.VAR, mc.LEASE, mc.LOCK, mc.LAST, mc.BOOT_ID)
    old_prepare = build.prepare_candidate
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

        reserved = mc.reserve_launch("vocoder-reserved", "vocoder-preflight", "ywd-vocoder-job.service")
        assert reserved["active"] is True and reserved["phase"] == "launching" and reserved["owner_pid"] == 1
        try:
            mc.claim("competing-job", "channel-switch", "preparing", owner_pid=os.getpid())
        except mc.MaintenanceBusy:
            pass
        else:
            raise AssertionError("launch reservation must reject competing maintenance")
        adopted = mc.claim(
            "vocoder-reserved", "vocoder-preflight", "checking",
            owner_pid=os.getpid(), service="ywd-vocoder-job.service",
        )
        assert adopted["owner_pid"] == os.getpid() and adopted["phase"] == "checking"
        mc.release("vocoder-reserved", owner_pid=os.getpid())

        build.prepare_candidate = lambda *a, **k: (_ for _ in ()).throw(AssertionError("preflight must not build"))
        runner.collect_facts = lambda: facts()
        job = {"job_id": "vocoder-smoke-pass", "job_type": "vocoder-preflight", "operation": "preflight", "started_at": 1}
        assert runner.run_preflight(job) == 0
        state = json.loads(runner.JOB_STATE.read_text(encoding="utf-8"))
        assert state["state"] == "COMPLETE" and state["progress"] == 100
        assert not mc.LEASE.exists()
        report = runner.JOBS_DIR / job["job_id"] / "preflight.json"
        report_doc = json.loads(report.read_text(encoding="utf-8"))
        assert report_doc["result"]["ready"] is True
        assert report_doc["facts"]["runtime_verification"] == "exact-installed-runtime"
        assert runner.JOB_LOG.stat().st_size <= runner.MAX_LOG_BYTES
        assert len(state.get("log_tail") or []) <= runner.MAX_LOG_LINES

        runner.collect_facts = lambda: facts(source_reachable=False, source_detail="offline")
        failed_job = {"job_id": "vocoder-smoke-fail", "job_type": "vocoder-preflight", "operation": "preflight", "started_at": 2}
        assert runner.run_preflight(failed_job) == 3
        failed = json.loads(runner.JOB_STATE.read_text(encoding="utf-8"))
        assert failed["state"] == "FAILED_SAFE"
        assert not mc.LEASE.exists()
    finally:
        build.prepare_candidate = old_prepare
        runner.VAR, runner.STATE_DIR, runner.REQUEST, runner.JOB_STATE, runner.JOB_LOG, runner.JOBS_DIR, runner.collect_facts = old_runner
        mc.VAR, mc.LEASE, mc.LOCK, mc.LAST, mc.BOOT_ID = old_mc

runner_src = (LIB / "vocoder_job_runner.py").read_text(encoding="utf-8")
admin_src = (LIB / "vocoder_job_admin.py").read_text(encoding="utf-8")
dashboard_src = (LIB / "dashboard_vocoder_manager.py").read_text(encoding="utf-8")
dispatch_src = (LIB / "admin_dispatch.sh").read_text(encoding="utf-8")
sudoers_src = (ROOT / "sudoers/ywd-hotspot").read_text(encoding="utf-8")
unit_src = (ROOT / "systemd" / "ywd-vocoder-job.service").read_text(encoding="utf-8")
ui_src = (ROOT / "web" / "vocoder-manager.js").read_text(encoding="utf-8")

assert 'operation not in {"preflight", "prepare"}' in runner_src
assert "runtime = vocoder_manager.verified_runtime()" in runner_src
assert "Verifying exact installed YWD Extended runtime identity" in runner_src
assert "vocoder job runner must not run as root" in runner_src
assert "MAX_LOG_BYTES = 64 * 1024" in runner_src and "MAX_LOG_LINES = 80" in runner_src
assert '"preflight": "vocoder-preflight"' in admin_src
assert "maintenance_coordinator.reserve_launch(job_id, job_type, SERVICE)" in admin_src
assert '"/api/system/vocoder/preflight"' in dashboard_src and "self.require_control()" in dashboard_src
assert "vocoder-preflight-start" in dispatch_src and "vocoder-preflight-start" in sudoers_src
assert "User=ywd-hotspot" in unit_src and "User=root" not in unit_src
assert "NoNewPrivileges=true" in unit_src and "ProtectSystem=strict" in unit_src
assert "ReadWritePaths=/var/lib/ywd-hotspot" in unit_src and "SuccessExitStatus=0 2 3" in unit_src
assert "CHECK INSTALL READINESS" in ui_src and "/api/system/vocoder/preflight" in ui_src
assert "launchPending || jobActive || maintenanceActive ? 1200 : 30000" in ui_src
assert "launchedTerminal" in ui_src
assert "ACTIVATE PREPARED CANDIDATE" in ui_src  # activation is separate from this read-only preflight worker

print("[OK] readiness evaluation distinguishes hard failures, temporary blockers, and YWD Extended prerequisite")
print("[OK] launch reservation blocks competing maintenance before worker adoption")
print("[OK] persistent preflight completes/failed-safes with lease release and bounded transcript")
print("[OK] preflight owns exact-runtime verification but cannot invoke the staged builder")
print("[OK] readiness worker remains unprivileged/read-only even after vocoder-only activation is enabled")
print("[OK] readiness API remains dashboard-authenticated and background job polling stays bounded")
