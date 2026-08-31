#!/usr/bin/env python3
"""Source-only regression for the RC4 vocoder-manager foundation.

No RF service, package manager, backend socket, compiler, systemd unit, or live
vocoder binary is modified by this smoke.
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
import vocoder_manager as vm


def expect_state(snapshot: dict, wanted: str) -> dict:
    got = vm.classify_snapshot(snapshot)
    assert got.get("state") == wanted, f"expected {wanted}, got {got}"
    return got


def complete_backend(*, enabled="enabled", service="inactive", policy_ok=True):
    return {
        "binary_present": True,
        "service_exists": True,
        "socket_exists": True,
        "service_state": service,
        "socket_state": "active",
        "socket_enabled": enabled,
        "policy": {"available": True, "ok": policy_ok},
    }


with tempfile.TemporaryDirectory(prefix="ywd-maint-smoke-") as td:
    root = Path(td)
    old = (mc.VAR, mc.LEASE, mc.LOCK, mc.LAST, mc.BOOT_ID)
    try:
        mc.VAR = root
        mc.LEASE = root / "maintenance-lease.json"
        mc.LOCK = root / "maintenance-lease.lock"
        mc.LAST = root / "maintenance-last.json"
        mc.BOOT_ID = root / "boot-id"
        mc.BOOT_ID.write_text("boot-smoke\n", encoding="utf-8")

        assert mc.inspect() == {"active": False, "stale": False}
        first = mc.claim("vocoder-smoke-1", "vocoder-install", "preparing", owner_pid=os.getpid())
        assert first["active"] is True and first["phase"] == "preparing"

        same = mc.claim("vocoder-smoke-1", "vocoder-install", "building", owner_pid=os.getpid())
        assert same["active"] is True and same["phase"] == "building"

        try:
            mc.claim("other-smoke-2", "channel-switch", "preparing", owner_pid=os.getpid())
        except mc.MaintenanceBusy as exc:
            assert exc.lease.get("job_id") == "vocoder-smoke-1"
        else:
            raise AssertionError("conflicting maintenance claim must be rejected")

        updated = mc.update("vocoder-smoke-1", phase="activation-started", cancellable=False, owner_pid=os.getpid())
        assert updated["phase"] == "activation-started" and updated["cancellable"] is False
        mc.release("vocoder-smoke-1", outcome="complete", owner_pid=os.getpid())
        assert mc.inspect() == {"active": False, "stale": False}
        assert mc.LAST.is_file()

        stale = {
            "schema": 1,
            "job_id": "stale-smoke",
            "job_type": "vocoder-install",
            "owner_pid": 99999999,
            "boot_id": "boot-smoke",
            "started_at": 1,
            "updated_at": 1,
            "phase": "building",
            "cancellable": True,
            "secret": "must-not-project",
        }
        mc.LEASE.write_text(json.dumps(stale), encoding="utf-8")
        seen = mc.inspect()
        assert seen["stale"] is True and seen["stale_reason"] == "owner-not-running"
        public = mc.public_status(seen)
        assert "secret" not in public
        recovered = mc.recover_stale()
        assert recovered["recovered"] is True
        assert not mc.LEASE.exists()
    finally:
        mc.VAR, mc.LEASE, mc.LOCK, mc.LAST, mc.BOOT_ID = old

# Normal dashboard runtime projection must never invoke the expensive exact
# runtime helper path. It binds the last verified persisted identity to current
# release pins instead.
old_persisted = vm.mmdvm_runtime_state.persisted_state
old_pins = vm.mmdvm_runtime_state._pins
old_status = vm.mmdvm_runtime_state.status
try:
    vm.mmdvm_runtime_state.persisted_state = lambda: {
        "variant": "ywd-extended",
        "upstream_commit": "upstream-smoke",
        "binary_sha256": "binary-smoke",
        "extension_api": 2,
        "patch_sha256": "patch-smoke",
        "capabilities": list(vm.REQUIRED_RUNTIME_CAPABILITIES),
        "runtime_generation": "current",
        "upgrade_required": False,
        "selected_at": 123,
    }
    vm.mmdvm_runtime_state._pins = lambda: {
        "MMDVM_HOST_COMMIT": "upstream-smoke",
        "MMDVM_YWD_PATCH_SHA256": "patch-smoke",
    }
    vm.mmdvm_runtime_state.status = lambda: (_ for _ in ()).throw(AssertionError("dashboard runtime projection called expensive verifier"))
    projected = vm._runtime()
    assert projected["ready"] is True
    assert projected["verification"] == "persisted-current-pin-identity"
finally:
    vm.mmdvm_runtime_state.persisted_state = old_persisted
    vm.mmdvm_runtime_state._pins = old_pins
    vm.mmdvm_runtime_state.status = old_status

recipe = {"id": vm.BACKEND_RECIPE, "version": vm.BACKEND_RECIPE_VERSION, "protocol": vm.PROTOCOL_VERSION, "mbelib_commit": vm.APPROVED_MBELIB_COMMIT}
ready_runtime = {
    "ready": True,
    "variant": "ywd-extended",
    "in_sync": True,
    "extension_api": 2,
    "capabilities": list(vm.REQUIRED_RUNTIME_CAPABILITIES),
    "missing_capabilities": [],
    "upgrade_required": False,
}
not_ready_runtime = {**ready_runtime, "ready": False, "variant": "upstream", "capabilities": [], "missing_capabilities": list(vm.REQUIRED_RUNTIME_CAPABILITIES)}
idle_job = {"active": False, "state": "IDLE", "phase": "idle"}

expect_state({"backend": {}, "runtime": ready_runtime, "recipe": recipe, "provenance": {}, "job": idle_job}, "NOT_INSTALLED")
expect_state({"backend": {"binary_present": True}, "runtime": ready_runtime, "recipe": recipe, "provenance": {}, "job": idle_job}, "REPAIR_REQUIRED")
expect_state({"backend": complete_backend(), "runtime": not_ready_runtime, "recipe": recipe, "provenance": {}, "job": idle_job}, "YWD_EXTENDED_REQUIRED")
expect_state({"backend": complete_backend(enabled="disabled"), "runtime": ready_runtime, "recipe": recipe, "provenance": {}, "job": idle_job}, "DISABLED")
expect_state({"backend": complete_backend(policy_ok=False), "runtime": ready_runtime, "recipe": recipe, "provenance": {}, "job": idle_job}, "REPAIR_REQUIRED")
expect_state({
    "backend": complete_backend(),
    "runtime": ready_runtime,
    "recipe": recipe,
    "provenance": {"recipe_version": vm.BACKEND_RECIPE_VERSION - 1, "protocol_version": vm.PROTOCOL_VERSION, "mbelib_commit": vm.APPROVED_MBELIB_COMMIT},
    "job": idle_job,
}, "UPDATE_REQUIRED")
ready = expect_state({"backend": complete_backend(service="inactive"), "runtime": ready_runtime, "recipe": recipe, "provenance": {}, "job": idle_job}, "READY")
assert ready.get("process_mode") == "DORMANT"
expect_state({"backend": {}, "runtime": ready_runtime, "recipe": recipe, "provenance": {}, "job": {"active": True, "state": "BUILDING", "phase": "building"}}, "BUILDING")

manager_src = (LIB / "vocoder_manager.py").read_text(encoding="utf-8")
dashboard_src = (LIB / "dashboard_vocoder_manager.py").read_text(encoding="utf-8")
update_src = (LIB / "dashboard_update.py").read_text(encoding="utf-8")
ui_src = (ROOT / "web" / "vocoder-manager.js").read_text(encoding="utf-8")
css_src = (ROOT / "web" / "vocoder-manager.css").read_text(encoding="utf-8")
modem_ui_src = (ROOT / "web" / "modem-ui.js").read_text(encoding="utf-8")

assert "import vocoder_client" not in manager_src
assert "vocoder_client.status" not in manager_src
assert '"mutations_enabled": False' in manager_src
assert "def verified_runtime()" in manager_src
assert '"persisted-current-pin-identity"' in manager_src
assert 'path != "/api/system/vocoder"' in dashboard_src
assert 'path != "/api/system/vocoder/preflight"' in dashboard_src
assert "require_control()" in dashboard_src
assert 'core.admin_call("vocoder-preflight-start", {}, 20)' in dashboard_src
assert "_ACTIVE_CACHE_TTL = 0.75" in dashboard_src
assert "invalidate_status()" in dashboard_src
assert "vocoder-manager.js?v=rc4-vocoder-foundation2" in update_src
assert '"/vocoder-manager.css"' in update_src
assert "DMR AUDIO VOCODER" in ui_src
assert "REFRESH STATUS" in ui_src
assert "CHECK INSTALL READINESS" in ui_src
assert "fetch('/api/system/vocoder'" in ui_src
assert "post('/api/system/vocoder/preflight', {})" in ui_src
assert "renderLaunch(out)" in ui_src
assert "JOB ACCEPTED · waiting for worker status" in ui_src
assert "INSTALL VOCODER" not in ui_src
assert "BUILD YWD EXTENDED" not in ui_src
assert "showButtonBusy" in ui_src
assert "if (button && showButtonBusy)" in ui_src
assert "jobActive || maintenanceActive ? 1500 : 30000" in ui_src
assert "check.disabled = !unlocked || maintenanceActive || jobActive || localBusy" in ui_src
assert "@media(max-width:620px)" in css_src
assert ".vocoder-actions .btn{width:100%;min-width:0}" in css_src
assert "BUILD / UPDATE YWD-EXTENDED" not in modem_ui_src
assert "HAT FIRMWARE TOOLS" not in modem_ui_src
assert "Inventory only. Guarded YWD Extended preparation for DMR audio is managed by the DMR Audio Vocoder section." in modem_ui_src

print("[OK] appliance maintenance lease rejects conflicting live jobs")
print("[OK] maintenance lease supports idempotent owner updates and stale recovery")
print("[OK] maintenance public status strips unapproved metadata")
print("[OK] vocoder manager classifies not-installed/repair/prerequisite/disabled/update/ready states")
print("[OK] dormant socket-activated backend is represented as READY / DORMANT")
print("[OK] passive System polling does not wake the vocoder Protocol backend")
print("[OK] dashboard runtime projection uses persisted current-pin identity without exact helper verification")
print("[OK] background polling is silent; only explicit refresh owns button busy feedback")
print("[OK] readiness launch renders immediate local feedback and uses a short active cache")
print("[OK] maintenance reservation immediately gates the readiness action")
print("[OK] MODEM / MMDVM remains passive inventory; guarded YWD Extended work belongs to Vocoder")
print("[OK] readiness launch is dashboard-authenticated while install/build/activation remain absent")
print("[OK] System card and mobile layout assets are wired into the dashboard")
