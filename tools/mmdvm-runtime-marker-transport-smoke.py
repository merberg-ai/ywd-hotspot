#!/usr/bin/env python3
"""Regression smoke for legacy MMDVM marker transport during RC2 -> RC3 update.

The canonical MMDVM helper reports the current pinned patch identity even when
an older accepted YWD Extended binary is installed, and its public ``status``
output summarizes rather than exposes the full historical marker.  RC3 must
therefore read the root-owned marker directly before classifying an accepted
legacy runtime.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import mmdvm_runtime_state as runtime


def main() -> int:
    pins = runtime._pins()
    upstream_commit = pins["MMDVM_HOST_COMMIT"]
    current_patch = pins["MMDVM_YWD_PATCH_SHA256"].lower()
    legacy_patch = next(iter(runtime.LEGACY_YWD_EXTENDED_PATCHES))
    legacy_binary = "published-rc2-binary-fixture"

    old_marker_path = runtime.VOICE_MARKER
    old_helper_status = runtime._helper_status
    try:
        with tempfile.TemporaryDirectory() as td:
            marker_path = Path(td) / "mmdvm-voice-tap.json"
            marker_path.write_text(
                json.dumps(
                    {
                        "status": "installed",
                        "api": 2,
                        "upstream_commit": upstream_commit,
                        "patch_sha256": legacy_patch,
                        "binary_sha256": legacy_binary,
                    }
                ),
                encoding="utf-8",
            )
            runtime.VOICE_MARKER = marker_path

            def helper_status(name: str) -> dict:
                if name == "mmdvm_voice_build.py":
                    # Match the real helper transport seam: the helper knows
                    # the installed binary SHA and current pin, but does not
                    # include the full historical marker in status JSON.
                    return {
                        "installed": False,
                        "active": False,
                        "api": 2,
                        "upstream_commit": upstream_commit,
                        "patch_sha256": current_patch,
                        "binary_sha256": legacy_binary,
                        "marker_status": "installed",
                    }
                if name == "mmdvm_upstream_build.py":
                    return {
                        "installed": False,
                        "binary_sha256": legacy_binary,
                    }
                raise AssertionError(name)

            runtime._helper_status = helper_status
            observed = runtime.observed_runtime()

            assert observed["variant"] == "ywd-extended", observed
            assert observed["installed"] is True, observed
            assert observed["runtime_generation"] == "legacy", observed
            assert observed["upgrade_required"] is True, observed
            assert observed["patch_sha256"] == legacy_patch, observed
            assert observed["binary_sha256"] == legacy_binary, observed
            assert "passive-dmr-voice" in observed["capabilities"], observed
            assert "plugin-rx-monitor" in observed["capabilities"], observed
            assert "demand-gated-dmr-voice" not in observed["capabilities"], observed
            assert observed["upgrade_command"] == runtime.RUNTIME_REFRESH_COMMAND, observed
    finally:
        runtime.VOICE_MARKER = old_marker_path
        runtime._helper_status = old_helper_status

    print("[OK] helper status may omit the historical marker")
    print("[OK] root-owned RC1/RC2 marker is read directly for exact classification")
    print("[OK] accepted legacy Extended runtime requests explicit refresh")
    print("[OK] legacy runtime does not gain demand-gated capability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
