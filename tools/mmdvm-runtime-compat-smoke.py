#!/usr/bin/env python3
"""Non-mutating RC3 MMDVM runtime identity compatibility smoke test."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import mmdvm_runtime_state as runtime


def main() -> int:
    pins = runtime._pins()
    current_patch = pins["MMDVM_YWD_PATCH_SHA256"].lower()
    upstream_commit = pins["MMDVM_HOST_COMMIT"]
    legacy_patch = next(iter(runtime.LEGACY_YWD_EXTENDED_PATCHES))

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

    print("[OK] current YWD Extended grants demand-gated capability")
    print("[OK] accepted RC1/RC2 YWD Extended is recognized as legacy-compatible")
    print("[OK] legacy runtime does not grant demand-gated capability")
    print("[OK] stale legacy marker cannot authenticate a different binary")
    print("[OK] stock upstream remains separately recognized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
