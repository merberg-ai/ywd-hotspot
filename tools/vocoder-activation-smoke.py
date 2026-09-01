#!/usr/bin/env python3
"""Source-only regression for transactional vocoder activation.

No live service, backend binary, updater lock, RF runtime, package manager, or
system configuration is changed by this smoke. Snapshot/rollback is exercised
only inside a temporary directory with systemd calls stubbed out.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

import vocoder_activation_runner as activation
import vocoder_prepared as prepared


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


assert blob_sha(ROOT / "web/app.js") == "6934acc74f4489cdfe2536407de50e73516ed521"

# Prepared status validates confinement, identity, SHA and self-test metadata.
with tempfile.TemporaryDirectory(prefix="ywd-vocoder-prepared-smoke-") as td:
    root = Path(td)
    candidates = root / "build-cache" / "candidates" / "candidate-a"
    candidates.mkdir(parents=True)
    binary = candidates / "ywd-vocoder-mbelib"
    binary.write_bytes(b"candidate-smoke\n")
    sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    manifest = root / "prepared.json"
    manifest.write_text(json.dumps({
        "binary": str(binary),
        "binary_sha256": sha,
        "cache_key": "candidate-a",
        "prepared_at": 1,
        "identity": {
            "recipe": prepared.vocoder_manager.BACKEND_RECIPE,
            "recipe_version": prepared.vocoder_manager.BACKEND_RECIPE_VERSION,
            "protocol_version": prepared.vocoder_manager.PROTOCOL_VERSION,
            "mbelib_commit": prepared.vocoder_manager.APPROVED_MBELIB_COMMIT,
            "architecture": platform.machine().strip().lower() or "unknown",
        },
        "self_test": {"ok": True, "protocol": prepared.vocoder_manager.PROTOCOL_VERSION, "frames": 10, "pcm_bytes": 3200},
    }), encoding="utf-8")
    old = (prepared.STATE_DIR, prepared.PREPARED, prepared.CANDIDATE_ROOT)
    try:
        prepared.STATE_DIR = root
        prepared.PREPARED = manifest
        prepared.CANDIDATE_ROOT = root / "build-cache" / "candidates"
        assert prepared.status()["valid"] is True
        binary.write_bytes(b"tampered\n")
        bad = prepared.status()
        assert bad["available"] is True and bad["valid"] is False
        assert "SHA-256" in bad["reason"]
    finally:
        prepared.STATE_DIR, prepared.PREPARED, prepared.CANDIDATE_ROOT = old

# Exercise the real protected snapshot/rollback filesystem functions in a temp
# tree. This proves old files are restored byte-for-byte and files introduced by
# the failed activation are removed. No real systemd command is executed.
with tempfile.TemporaryDirectory(prefix="ywd-vocoder-rollback-smoke-") as td:
    root = Path(td)
    live = root / "usr/local/libexec/ywd-vocoder-mbelib"
    service = root / "etc/systemd/system/ywd-vocoder-mbelib.service"
    socket = root / "etc/systemd/system/ywd-vocoder-mbelib.socket"
    dropin = root / "etc/systemd/system/ywd-vocoder-mbelib.service.d/20-ywd-hotspot-normal-priority.conf"
    provenance = root / "var/lib/ywd-hotspot/vocoder/installed.json"
    backup_root = root / "var/backups/ywd-hotspot/vocoder"
    for path in (live, service, socket, dropin):
        path.parent.mkdir(parents=True, exist_ok=True)
    live.write_bytes(b"old-live-binary\n")
    service.write_text("old-service\n", encoding="utf-8")
    socket.write_text("old-socket\n", encoding="utf-8")
    dropin.write_text("old-policy\n", encoding="utf-8")
    old_bytes = {p: p.read_bytes() for p in (live, service, socket, dropin)}

    saved = (
        activation.LIVE_BINARY, activation.SERVICE_PATH, activation.SOCKET_PATH,
        activation.DROPIN_PATH, activation.PROVENANCE, activation.BACKUP_ROOT,
        activation._unit_state, activation._run, activation._must,
        activation._restore_unit_policy,
    )
    try:
        activation.LIVE_BINARY = live
        activation.SERVICE_PATH = service
        activation.SOCKET_PATH = socket
        activation.DROPIN_PATH = dropin
        activation.PROVENANCE = provenance
        activation.BACKUP_ROOT = backup_root
        activation._unit_state = lambda unit: {"active": "active" if "socket" in unit else "inactive", "enabled": "enabled" if "socket" in unit else "disabled"}
        activation._run = lambda args, timeout=30: subprocess.CompletedProcess(args, 0, "")
        activation._must = lambda args, timeout=30: ""
        activation._restore_unit_policy = lambda manifest: None

        snap = activation._snapshot({"job_id": "rollback-smoke"})
        live.write_bytes(b"new-live-binary\n")
        service.write_text("new-service\n", encoding="utf-8")
        socket.write_text("new-socket\n", encoding="utf-8")
        dropin.write_text("new-policy\n", encoding="utf-8")
        provenance.parent.mkdir(parents=True, exist_ok=True)
        provenance.write_text("new-provenance\n", encoding="utf-8")

        activation._rollback({"backup": snap})
        for path, wanted in old_bytes.items():
            assert path.read_bytes() == wanted, f"rollback did not restore {path}"
        assert not provenance.exists(), "rollback must remove provenance that did not exist before activation"
    finally:
        (
            activation.LIVE_BINARY, activation.SERVICE_PATH, activation.SOCKET_PATH,
            activation.DROPIN_PATH, activation.PROVENANCE, activation.BACKUP_ROOT,
            activation._unit_state, activation._run, activation._must,
            activation._restore_unit_policy,
        ) = saved

runner = text("lib/vocoder_activation_runner.py")
admin = text("lib/vocoder_activation_admin.py")
dash = text("lib/dashboard_vocoder_manager.py")
ui = text("web/vocoder-manager.js")
plugin = text("lib/plugin_admin.py")
dispatch = text("lib/admin_dispatch.sh")
sudoers = text("sudoers/ywd-hotspot")
activate_unit = text("systemd/ywd-vocoder-activation.service")
recovery_unit = text("systemd/ywd-vocoder-recovery.service")
backend_service = text("lib/vocoder_units/ywd-vocoder-mbelib.service")
backend_socket = text("lib/vocoder_units/ywd-vocoder-mbelib.socket")
backend_policy = text("lib/vocoder_units/20-ywd-hotspot-normal-priority.conf")

assert 'UPDATE_LOCK = Path("/run/ywd-hotspot-update.lock")' in runner
assert 'fcntl.LOCK_EX | fcntl.LOCK_NB' in runner
assert 'maintenance_coordinator.adopt(' in runner
assert 'vocoder_manager.verified_runtime()' in runner
assert 'JOURNAL = PRIVATE / "vocoder-activation-journal.json"' in runner
assert 'BACKUP_ROOT = Path("/var/backups/ywd-hotspot/vocoder")' in runner
assert '_snapshot(job)' in runner and '_rollback(journal)' in runner
assert 'state="ROLLING_BACK"' in runner and 'state="FAILED_SAFE"' in runner
assert 'boot-recovered' in runner

assert 'def _run_ywd(' in runner
assert '_must_ywd([candidate["binary"], "--self-test"]' in runner
assert 'getattr(os, "O_NOFOLLOW", 0)' in runner
assert 'activation copy SHA-256 mismatch' in runner
assert '_atomic_install(Path(candidate["binary"]), LIVE_BINARY, 0o755, str(candidate["binary_sha256"]))' in runner
assert '"sudo", "-u", "ywd-hotspot"' not in runner

for forbidden in (
    '["systemctl", "stop", "ywd-mmdvmhost.service"',
    '["systemctl", "restart", "ywd-mmdvmhost.service"',
    '["systemctl", "stop", "ywd-dmrgateway.service"',
    '["systemctl", "restart", "ywd-dmrgateway.service"',
    'apt-get install',
):
    assert forbidden not in runner
assert '["systemctl", "stop", SERVICE_UNIT]' in runner
assert '["systemctl", "stop", SOCKET_UNIT]' in runner
assert 'vocoder_client.py' in runner and 'decode-test' in runner

assert admin.index('systemctl", "enable", RECOVERY_SERVICE') < admin.index('reserve_launch(job_id, "vocoder-activate"')
assert 'BACKUP_ROOT.mkdir(parents=True, exist_ok=True)' in admin
assert 'User=root' in activate_unit and 'ProtectSystem=strict' in activate_unit
assert 'SuccessExitStatus=0 3' in activate_unit
assert 'OnFailure=ywd-vocoder-recovery.service' in activate_unit
assert 'ConditionPathExists=/var/lib/ywd-hotspot/private/vocoder-activation-journal.json' in recovery_unit
assert 'Before=ywd-dashboard.service' in recovery_unit and 'ProtectSystem=strict' in recovery_unit

assert not (ROOT / "systemd" / "ywd-vocoder-mbelib.service").exists()
assert not (ROOT / "systemd" / "ywd-vocoder-mbelib.socket").exists()
assert 'ExecStart=/usr/local/libexec/ywd-vocoder-mbelib' in backend_service
assert 'User=ywd-hotspot' in backend_service and 'CPUWeight=200' in backend_service
assert 'ListenStream=/run/ywd-vocoder.sock' in backend_socket
assert 'SocketMode=0660' in backend_socket and 'WantedBy=sockets.target' in backend_socket
assert 'Nice=0' in backend_policy and 'CPUWeight=200' in backend_policy

assert '"/api/system/vocoder/activate": ("vocoder-activate-start", False)' in dash
assert '_apply_managed_integrity' in dash and 'managed-binary-sha-mismatch' in dash
assert 'vocoder-activate-start)' in dispatch
assert '/usr/local/libexec/ywd-hotspot-admin vocoder-activate-start' in sudoers
assert 'id="vocoderActivate"' in ui and '/api/system/vocoder/activate' in ui
assert 'ACTIVATE PREPARED CANDIDATE' in ui
assert 'Protected backup + power-loss journal are armed before live replacement' in ui
assert '<button class="btn" id="vocoderPreflight"' in ui
assert '<button class="btn" id="vocoderPrepare"' in ui
assert '<button class="btn primary" id="vocoderActivate"' in ui
assert 'class="btn ctl" id="vocoder' not in ui

assert 'MAINTENANCE_ACTIONS' in plugin
assert 'maintenance_coordinator.claim(' in plugin
assert '"plugin-package-install"' in plugin and '"plugin-package-uninstall"' in plugin
assert '"plugin-runtime"' in plugin and '"plugin-config-save"' in plugin

print("[OK] known-good Pi Zero dashboard startup file remains frozen")
print("[OK] prepared candidate projection rejects stale/tampered candidate content")
print("[OK] real protected snapshot/rollback functions restore old files in a synthetic transaction")
print("[OK] activation is serialized against updater/channel and live plugin mutations")
print("[OK] staged code never executes as root and atomic live copy is no-follow/SHA-verified")
print("[OK] protected backup, power-loss journal, live verification and automatic rollback are wired")
print("[OK] activation crash triggers same-boot recovery and boot recovery remains armed")
print("[OK] activation cannot restart MMDVMHost/DMRGateway or install packages")
print("[OK] managed backend unit templates are install-on-activation, not normal update payload")
print("[OK] managed binary integrity drift is surfaced as repair-required")
print("[OK] dashboard activation is unlocked/fixed-action only and job controls own their busy state")
