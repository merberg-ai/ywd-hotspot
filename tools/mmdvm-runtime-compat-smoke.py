#!/usr/bin/env python3
"""Non-mutating RC3 MMDVM runtime identity compatibility smoke test."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import mmdvm_runtime_state as runtime
import plugin_package_manager
import runtime_build


def main() -> int:
    pins = runtime._pins()
    current_patch = pins["MMDVM_YWD_PATCH_SHA256"].lower()
    upstream_commit = pins["MMDVM_HOST_COMMIT"]
    legacy_patch = next(iter(runtime.LEGACY_YWD_EXTENDED_PATCHES))

    assert runtime_build.YWD_EXTENDED_CAPABILITIES == runtime.YWD_EXTENDED_CAPABILITIES, (
        runtime_build.YWD_EXTENDED_CAPABILITIES,
        runtime.YWD_EXTENDED_CAPABILITIES,
    )

    current = runtime.classify_runtime(
        pins,
        {
            "installed": True,
            "patch_sha256": current_patch,
            "upstream_commit": upstream_commit,
            "binary_sha256": "current-binary",
            "api": 2,
            "marker_status": "installed",
        },
        {},
    )
    assert current["variant"] == "ywd-extended", current
    assert current["installed"] is True, current
    assert current["runtime_generation"] == "current", current
    assert current["upgrade_required"] is False, current
    assert "demand-gated-dmr-voice" in current["capabilities"], current

    legacy = runtime.classify_runtime(
        pins,
        {
            "installed": False,
            "patch_sha256": current_patch,
            "upstream_commit": upstream_commit,
            "binary_sha256": "legacy-binary",
            "api": 2,
            "marker": {
                "status": "installed",
                "api": 2,
                "upstream_commit": upstream_commit,
                "patch_sha256": legacy_patch,
                "binary_sha256": "legacy-binary",
            },
        },
        {},
    )
    assert legacy["variant"] == "ywd-extended", legacy
    assert legacy["installed"] is True, legacy
    assert legacy["runtime_generation"] == "legacy", legacy
    assert legacy["upgrade_required"] is True, legacy
    assert "passive-dmr-voice" in legacy["capabilities"], legacy
    assert "demand-gated-dmr-voice" not in legacy["capabilities"], legacy
    assert legacy["upgrade_command"] == runtime.RUNTIME_REFRESH_COMMAND, legacy

    stale_marker = runtime.classify_runtime(
        pins,
        {
            "installed": False,
            "binary_sha256": "different-binary",
            "marker": {
                "status": "installed",
                "api": 2,
                "upstream_commit": upstream_commit,
                "patch_sha256": legacy_patch,
                "binary_sha256": "legacy-binary",
            },
        },
        {},
    )
    assert stale_marker["installed"] is False, stale_marker
    assert stale_marker["variant"] == "unknown", stale_marker

    upstream = runtime.classify_runtime(
        pins,
        {"installed": False, "binary_sha256": "stock-binary", "marker": {}},
        {
            "installed": True,
            "upstream_commit": upstream_commit,
            "binary_sha256": "stock-binary",
        },
    )
    assert upstream["variant"] == "upstream", upstream
    assert upstream["installed"] is True, upstream
    assert upstream["capabilities"] == [], upstream

    # Transitional state written by older current-dev runtime_build.py builds
    # can contain the exact current patch SHA while omitting the new token.
    # Cheap UI snapshots must normalize that trusted root-owned state, while a
    # legacy RC2 patch must not be upgraded by inference.
    old_state_path = plugin_package_manager.MMDVM_RUNTIME_STATE
    try:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "mmdvm-runtime.json"
            plugin_package_manager.MMDVM_RUNTIME_STATE = path

            path.write_text(
                json.dumps({
                    "variant": "ywd-extended",
                    "extension_api": 2,
                    "patch_sha256": current_patch,
                    "capabilities": ["passive-dmr-voice", "plugin-rx-monitor"],
                }),
                encoding="utf-8",
            )
            selected_current = plugin_package_manager._mmdvm_runtime()
            assert "demand-gated-dmr-voice" in selected_current["capabilities"], selected_current

            path.write_text(
                json.dumps({
                    "variant": "ywd-extended",
                    "extension_api": 2,
                    "patch_sha256": legacy_patch,
                    "capabilities": ["passive-dmr-voice", "plugin-rx-monitor"],
                }),
                encoding="utf-8",
            )
            selected_legacy = plugin_package_manager._mmdvm_runtime()
            assert "demand-gated-dmr-voice" not in selected_legacy["capabilities"], selected_legacy
    finally:
        plugin_package_manager.MMDVM_RUNTIME_STATE = old_state_path

    original_observed = plugin_package_manager.mmdvm_runtime_state.observed_runtime
    try:
        plugin_package_manager.mmdvm_runtime_state.observed_runtime = lambda: legacy
        ok, detail = plugin_package_manager._dependency_result(
            "mmdvm-cap-demand-gated-dmr-voice",
            verify_runtime=True,
        )
        assert ok is False, (ok, detail)
        assert "runtime recognized" in detail, detail
        assert "explicit YWD Extended refresh required" in detail, detail
        assert runtime.RUNTIME_REFRESH_COMMAND in detail, detail
    finally:
        plugin_package_manager.mmdvm_runtime_state.observed_runtime = original_observed

    print("[OK] canonical runtime writer and exact classifier share current capabilities")
    print("[OK] current YWD Extended grants demand-gated capability")
    print("[OK] accepted RC1/RC2 YWD Extended is recognized as legacy-compatible")
    print("[OK] legacy runtime does not grant demand-gated capability")
    print("[OK] stale legacy marker cannot authenticate a different binary")
    print("[OK] persisted current-patch state normalizes the transitional missing token")
    print("[OK] legacy plugin requirement failure includes explicit refresh guidance")
    print("[OK] stock upstream remains separately recognized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
