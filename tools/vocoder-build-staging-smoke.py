#!/usr/bin/env python3
"""Source-only regression for the RC4 staged vocoder build gate.

This test performs no network access, compilation, package changes, service
changes, or RF actions. The real candidate build remains a hardware gate.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


# Freeze the known-good dashboard startup file recovered on real Pi Zero
# hardware. Vocoder maintenance must not modify global dashboard startup again.
assert git_blob_sha(ROOT / "web/app.js") == "6934acc74f4489cdfe2536407de50e73516ed521"

adapter = text("lib/vocoder_mbelib_adapter.cpp")
builder = text("lib/vocoder_backend_build.py")
runner = text("lib/vocoder_job_runner.py")
admin = text("lib/vocoder_job_admin.py")
dash = text("lib/dashboard_vocoder_manager.py")
ui = text("web/vocoder-manager.js")
dispatch = text("lib/admin_dispatch.sh")
sudoers = text("sudoers/ywd-hotspot")
unit = text("systemd/ywd-vocoder-job.service")

# YWD ships only its protocol adapter/build recipe; mbelib remains an approved
# pinned external source fetched at operator request.
assert "mbe_processAmbe2450Data" in adapter
assert "YVCP" not in adapter  # magic is intentionally emitted byte-wise
assert "h[0] = 'Y'; h[1] = 'V'; h[2] = 'C'; h[3] = 'P'" in adapter
assert "--self-test" in adapter
assert "pcm_bytes" in adapter and "3200" not in adapter  # computed from constants
assert "APPROVED_SOURCE" in builder and "APPROVED_MBELIB_COMMIT" in builder
assert '"fetch", "--depth", "1", "origin", commit' in builder
assert "CMAKE_BUILD_TYPE=Release" in builder and '"-j1"' in builder
assert "vocoder_mbelib_adapter.cpp" in builder
assert "validate_candidate" in builder and "candidate self-test" in builder
assert "PREPARED" in builder and "build-cache" in builder
assert "MAX_CANDIDATES = 2" in builder

# Preparation runs as the existing unprivileged worker and may only stage/cache.
assert 'User=ywd-hotspot' in unit and 'Group=ywd-hotspot' in unit
assert 'NoNewPrivileges=true' in unit and 'ProtectSystem=strict' in unit
assert 'ReadWritePaths=/var/lib/ywd-hotspot' in unit
for forbidden in ("apt-get install", "systemctl stop", "systemctl restart", "/usr/local/libexec/ywd-vocoder-mbelib"):
    assert forbidden not in runner
    assert forbidden not in builder
assert 'operation not in {"preflight", "prepare"}' in runner
assert 'run_prepare' in runner and 'prepare_candidate' in runner
assert 'live backend/runtime unchanged' in runner
assert 'SIGTERM' in runner and 'BuildCancelled' in runner

# Root/browser authority stays narrow: fixed actions, matching job-id cancel,
# dashboard unlock enforcement, and no browser-controlled source/build options.
for action in ("vocoder-preflight-start", "vocoder-prepare-start", "vocoder-job-cancel"):
    assert action in admin and action in dispatch and action in sudoers
assert 'set(payload) != {"job_id"}' in admin
assert '--kill-who=main' in admin and '--signal=SIGTERM' in admin
assert 'lease.get("cancellable")' in admin
assert 'self.require_control()' in dash
assert '"/api/system/vocoder/prepare"' in dash
assert '"/api/system/vocoder/cancel"' in dash

# System UI exposes build-only language and the matching cancel surface without
# moving any of this work into global dashboard startup.
assert "PREPARE VOCODER CANDIDATE" in ui
assert "/api/system/vocoder/prepare" in ui
assert "/api/system/vocoder/cancel" in ui
assert "Live MMDVMHost, DMRGateway, vocoder socket and installed backend remain untouched." in ui
assert "currentJobCancellable" in ui
assert "CANCEL JOB" in ui

print("[OK] known-good Pi Zero dashboard startup file remains frozen")
print("[OK] YWD-owned Protocol v1 adapter source is present without bundling mbelib")
print("[OK] staged builder pins/fetches/builds/caches/self-tests only under YWD state")
print("[OK] staged prepare worker cannot install packages or modify live RF/backend services")
print("[OK] prepare/cancel authority is fixed, dashboard-locked, and job-id bounded")
print("[OK] vocoder System UI exposes staged preparation without entering dashboard startup")
