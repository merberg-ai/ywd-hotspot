#!/usr/bin/env python3
"""Source-only regression for transactional vocoder activation.

No live service, backend binary, updater lock, RF runtime, package manager, or
system configuration is changed by this smoke.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

import vocoder_prepared as prepared


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


# Never let vocoder work re-enter the dashboard startup experiment again.
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

# Root transaction worker has narrow authority and two independent exclusion
# mechanisms: persistent YWD maintenance + the updater's existing flock.
assert 'UPDATE_LOCK = Path("/run/ywd-hotspot-update.lock")' in runner
assert 'fcntl.LOCK_EX | fcntl.LOCK_NB' in runner
assert 'maintenance_coordinator.adopt(' in runner
assert 'vocoder_manager.verified_runtime()' in runner
assert 'JOURNAL = PRIVATE / "vocoder-activation-journal.json"' in runner
assert 'BACKUP_ROOT = Path("/var/backups/ywd-hotspot/vocoder")' in runner
assert '_snapshot(job)' in runner and '_rollback(journal)' in runner
assert 'state="ROLLING_BACK"' in runner and 'state="FAILED_SAFE"' in runner
assert 'boot-recovered' in runner

# Staged artifacts are never executed as root and copy-to-live is no-follow +
# SHA checked before atomic replacement.
assert 'def _run_ywd(' in runner
assert '_must_ywd([candidate["binary"], "--self-test"]' in runner
assert 'getattr(os, "O_NOFOLLOW", 0)' in runner
assert 'activation copy SHA-256 mismatch' in runner
assert '_atomic_install(Path(candidate["binary"]), LIVE_BINARY, 0o755, str(candidate["binary_sha256"]))' in runner
assert '"sudo", "-u", "ywd-hotspot"' not in runner

# Activation may touch only dedicated vocoder units/files. RF/network services
# are named in operator messages but never passed to systemctl.
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

# Recovery is armed before activation launch, with protected write sandboxes.
assert admin.index('systemctl", "enable", RECOVERY_SERVICE') < admin.index('reserve_launch(job_id, "vocoder-activate"')
assert 'BACKUP_ROOT.mkdir(parents=True, exist_ok=True)' in admin
assert 'User=root' in activate_unit and 'ProtectSystem=strict' in activate_unit
assert 'SuccessExitStatus=0 3' in activate_unit
assert 'ConditionPathExists=/var/lib/ywd-hotspot/private/vocoder-activation-journal.json' in recovery_unit
assert 'Before=ywd-dashboard.service' in recovery_unit and 'ProtectSystem=strict' in recovery_unit

# Live unit templates are install-on-activation only, not normal systemd payload
# files that UPDATE-core would automatically replace.
assert not (ROOT / "systemd" / "ywd-vocoder-mbelib.service").exists()
assert not (ROOT / "systemd" / "ywd-vocoder-mbelib.socket").exists()
assert 'ExecStart=/usr/local/libexec/ywd-vocoder-mbelib' in backend_service
assert 'User=ywd-hotspot' in backend_service and 'CPUWeight=200' in backend_service
assert 'ListenStream=/run/ywd-vocoder.sock' in backend_socket
assert 'SocketMode=0660' in backend_socket and 'WantedBy=sockets.target' in backend_socket
assert 'Nice=0' in backend_policy and 'CPUWeight=200' in backend_policy

# Dashboard authority is fixed/no-options and controls remain independent from
# generic .ctl refreshes while a transaction is active.
assert '"/api/system/vocoder/activate": ("vocoder-activate-start", False)' in dash
assert 'vocoder-activate-start)' in dispatch
assert '/usr/local/libexec/ywd-hotspot-admin vocoder-activate-start' in sudoers
assert 'id="vocoderActivate"' in ui and '/api/system/vocoder/activate' in ui
assert 'ACTIVATE PREPARED CANDIDATE' in ui
assert 'Protected backup + power-loss journal are armed before live replacement' in ui
assert '<button class="btn" id="vocoderPreflight"' in ui
assert '<button class="btn" id="vocoderPrepare"' in ui
assert '<button class="btn primary" id="vocoderActivate"' in ui
assert 'class="btn ctl" id="vocoder' not in ui

# Live plugin mutations use the same persistent maintenance lease; uploads and
# reviews remain staging/read-only relative to live capability state.
assert 'MAINTENANCE_ACTIONS' in plugin
assert 'maintenance_coordinator.claim(' in plugin
assert '"plugin-package-install"' in plugin and '"plugin-package-uninstall"' in plugin
assert '"plugin-runtime"' in plugin and '"plugin-config-save"' in plugin

print("[OK] known-good Pi Zero dashboard startup file remains frozen")
print("[OK] prepared candidate projection rejects stale/tampered candidate content")
print("[OK] activation is serialized against updater/channel and live plugin mutations")
print("[OK] staged code never executes as root and atomic live copy is no-follow/SHA-verified")
print("[OK] protected backup, power-loss journal, live verification and automatic rollback are wired")
print("[OK] activation cannot restart MMDVMHost/DMRGateway or install packages")
print("[OK] managed backend unit templates are install-on-activation, not normal update payload")
print("[OK] dashboard activation is unlocked/fixed-action only and job controls own their busy state")
