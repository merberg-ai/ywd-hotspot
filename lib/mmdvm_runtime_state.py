#!/usr/bin/env python3
"""Read/refresh MMDVM runtime identity without rebuilding or restarting RF.

The persisted runtime state is used for plugin compatibility checks. This
helper derives capabilities from the exact installed binary/patch identity so
an older YWD extension with the same API number cannot accidentally satisfy a
newer capability requirement.

Known legacy YWD Extended patch generations remain positively identifiable.
They keep only the capabilities they actually implement and advertise an
explicit runtime-refresh path instead of being misclassified as unknown.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

LIB = Path(__file__).resolve().parent
APP = LIB.parent
PINS = APP / "pins.env"
RUNTIME_STATE = Path(os.environ.get("YWD_MMDVM_RUNTIME_STATE", "/etc/ywd-hotspot/mmdvm-runtime.json"))
VOICE_MARKER = Path(os.environ.get("YWD_MMDVM_VOICE_MARKER", "/var/lib/ywd-hotspot/mmdvm-voice-tap.json"))

YWD_EXTENDED_CAPABILITIES = [
    "passive-dmr-voice",
    "plugin-rx-monitor",
    "demand-gated-dmr-voice",
]
LEGACY_YWD_EXTENDED_CAPABILITIES = [
    "passive-dmr-voice",
    "plugin-rx-monitor",
]

# Immutable accepted RC1/RC2 YWD Extended patch identity. It publishes the
# same DMRVoice envelope/API used by current core, but it predates the cached
# YWD_DMR_VOICE_TAP demand gate and therefore must never satisfy the newer
# demand-gated capability token.
LEGACY_YWD_EXTENDED_PATCHES = {
    "f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a": {
        "label": "0.2.0-rc1/rc2",
        "extension_api": 2,
        "capabilities": LEGACY_YWD_EXTENDED_CAPABILITIES,
    },
}

RUNTIME_REFRESH_COMMAND = (
    "sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py "
    "install --mmdvm-variant ywd-extended"
)


def _read_json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def _pins() -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in PINS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _helper_status(name: str) -> dict:
    p = subprocess.run(
        [sys.executable, str(LIB / name), "status"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    try:
        doc = json.loads(p.stdout or "{}")
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def _as_int(value):
    try:
        return int(value)
    except Exception:
        return None


def classify_runtime(pins: dict, ywd: dict, upstream: dict) -> dict:
    """Classify helper status into one exact runtime/capability identity."""
    expected_patch = str(pins.get("MMDVM_YWD_PATCH_SHA256") or "").lower()
    expected_upstream = str(pins.get("MMDVM_HOST_COMMIT") or "")

    # Current exact YWD Extended generation.
    if (
        ywd.get("installed") is True
        and str(ywd.get("patch_sha256") or "").lower() == expected_patch
        and str(ywd.get("upstream_commit") or "") == expected_upstream
    ):
        return {
            "variant": "ywd-extended",
            "installed": True,
            "upstream_commit": ywd.get("upstream_commit"),
            "binary_sha256": ywd.get("binary_sha256"),
            "extension_api": _as_int(ywd.get("api")),
            "patch_sha256": ywd.get("patch_sha256"),
            "capabilities": list(YWD_EXTENDED_CAPABILITIES),
            "marker_status": ywd.get("marker_status"),
            "runtime_generation": "current",
            "upgrade_required": False,
        }

    # mmdvm_voice_build.py intentionally reports installed=false when its
    # marker describes a different patch than the current pin. Inspect that
    # marker only for an explicitly allowlisted historical patch, and require
    # it to bind to the exact installed binary SHA before trusting it.
    marker = ywd.get("marker") if isinstance(ywd.get("marker"), dict) else {}
    marker_patch = str(marker.get("patch_sha256") or "").lower()
    legacy = LEGACY_YWD_EXTENDED_PATCHES.get(marker_patch)
    binary_sha = str(ywd.get("binary_sha256") or "")
    marker_binary_sha = str(marker.get("binary_sha256") or "")
    marker_api = _as_int(marker.get("api"))
    if (
        legacy is not None
        and bool(binary_sha)
        and marker_binary_sha == binary_sha
        and str(marker.get("upstream_commit") or "") == expected_upstream
        and marker.get("status") in {"installed", "active"}
        and marker_api == int(legacy["extension_api"])
    ):
        capabilities = list(legacy["capabilities"])
        return {
            "variant": "ywd-extended",
            "installed": True,
            "upstream_commit": marker.get("upstream_commit"),
            "binary_sha256": binary_sha,
            "extension_api": marker_api,
            "patch_sha256": marker_patch,
            "capabilities": capabilities,
            "marker_status": marker.get("status"),
            "runtime_generation": "legacy",
            "legacy_release": legacy["label"],
            "upgrade_required": True,
            "upgrade_reason": (
                "installed YWD Extended runtime predates demand-gated DMR voice; "
                "normal DMR/passive voice compatibility is retained, but the "
                "demand-gated RX Monitor capability requires an explicit runtime refresh"
            ),
            "missing_current_capabilities": sorted(
                set(YWD_EXTENDED_CAPABILITIES) - set(capabilities)
            ),
            "current_patch_sha256": expected_patch,
            "upgrade_command": RUNTIME_REFRESH_COMMAND,
        }

    if upstream.get("installed") is True:
        return {
            "variant": "upstream",
            "installed": True,
            "upstream_commit": upstream.get("upstream_commit"),
            "binary_sha256": upstream.get("binary_sha256"),
            "extension_api": None,
            "patch_sha256": None,
            "capabilities": [],
            "runtime_generation": "current",
            "upgrade_required": False,
        }

    return {
        "variant": "unknown",
        "installed": False,
        "upstream_commit": None,
        "binary_sha256": binary_sha or None,
        "extension_api": None,
        "patch_sha256": marker_patch or None,
        "capabilities": [],
        "runtime_generation": "unknown",
        "upgrade_required": False,
        "error": "installed MMDVM runtime identity could not be verified",
    }


def observed_runtime() -> dict:
    """Return runtime identity derived from the currently installed binary."""
    pins = _pins()
    ywd = _helper_status("mmdvm_voice_build.py")
    # mmdvm_voice_build.py status intentionally summarizes marker metadata and
    # may omit the full historical marker. Read the same root-owned marker
    # directly so an exact allowlisted RC1/RC2 runtime can still be positively
    # identified without trusting persisted capability state or rebuilding RF.
    if not isinstance(ywd.get("marker"), dict) or not ywd.get("marker"):
        ywd["marker"] = _read_json(VOICE_MARKER)
    upstream = _helper_status("mmdvm_upstream_build.py")
    observed = classify_runtime(pins, ywd, upstream)
    if observed.get("installed"):
        return observed

    old = _read_json(RUNTIME_STATE)
    observed["variant"] = str(old.get("variant") or "unknown")
    return observed


def persisted_state() -> dict:
    return _read_json(RUNTIME_STATE)


def refresh() -> dict:
    if os.geteuid() != 0:
        raise RuntimeError("MMDVM runtime state refresh must run as root")
    observed = observed_runtime()
    if not observed.get("installed"):
        raise RuntimeError(observed.get("error") or "installed MMDVM runtime could not be verified")
    doc = {
        "schema": 1,
        "variant": observed["variant"],
        "selected_at": int(time.time()),
        "upstream_commit": observed.get("upstream_commit"),
        "binary_sha256": observed.get("binary_sha256"),
        "extension_api": observed.get("extension_api"),
        "patch_sha256": observed.get("patch_sha256"),
        "capabilities": observed.get("capabilities", []),
        "runtime_generation": observed.get("runtime_generation", "unknown"),
        "upgrade_required": bool(observed.get("upgrade_required", False)),
    }
    if observed.get("legacy_release"):
        doc["legacy_release"] = observed["legacy_release"]
    if observed.get("upgrade_reason"):
        doc["upgrade_reason"] = observed["upgrade_reason"]
    if observed.get("upgrade_command"):
        doc["upgrade_command"] = observed["upgrade_command"]

    RUNTIME_STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = RUNTIME_STATE.with_name(RUNTIME_STATE.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, RUNTIME_STATE)
    return doc


def status() -> dict:
    observed = observed_runtime()
    persisted = persisted_state()
    return {
        "runtime_state": str(RUNTIME_STATE),
        "observed": observed,
        "persisted": persisted,
        "in_sync": bool(
            persisted.get("variant") == observed.get("variant")
            and persisted.get("upstream_commit") == observed.get("upstream_commit")
            and persisted.get("binary_sha256") == observed.get("binary_sha256")
            and persisted.get("extension_api") == observed.get("extension_api")
            and persisted.get("patch_sha256") == observed.get("patch_sha256")
            and persisted.get("capabilities") == observed.get("capabilities")
        ),
        "upgrade_required": bool(observed.get("upgrade_required", False)),
        "upgrade_command": observed.get("upgrade_command"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Inspect or refresh YWD MMDVM runtime identity")
    ap.add_argument("command", nargs="?", choices=("status", "refresh"), default="status")
    args = ap.parse_args()
    try:
        out = refresh() if args.command == "refresh" else status()
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
