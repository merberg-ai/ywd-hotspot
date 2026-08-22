#!/usr/bin/env python3
"""Read/refresh MMDVM runtime identity without rebuilding or restarting RF.

The persisted runtime state is used for plugin compatibility checks.  This
helper derives capabilities from the exact installed binary/patch identity so
an older YWD extension with the same API number cannot accidentally satisfy a
newer capability requirement.
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

YWD_EXTENDED_CAPABILITIES = [
    "passive-dmr-voice",
    "plugin-rx-monitor",
    "demand-gated-dmr-voice",
]


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


def observed_runtime() -> dict:
    """Return runtime identity derived from the currently installed binary."""
    pins = _pins()
    ywd = _helper_status("mmdvm_voice_build.py")
    expected_patch = str(pins.get("MMDVM_YWD_PATCH_SHA256") or "").lower()
    expected_upstream = str(pins.get("MMDVM_HOST_COMMIT") or "")

    if (
        ywd.get("installed") is True
        and str(ywd.get("patch_sha256") or "").lower() == expected_patch
        and str(ywd.get("upstream_commit") or "") == expected_upstream
    ):
        try:
            api = int(ywd.get("api"))
        except Exception:
            api = None
        return {
            "variant": "ywd-extended",
            "installed": True,
            "upstream_commit": ywd.get("upstream_commit"),
            "binary_sha256": ywd.get("binary_sha256"),
            "extension_api": api,
            "patch_sha256": ywd.get("patch_sha256"),
            "capabilities": list(YWD_EXTENDED_CAPABILITIES),
            "marker_status": ywd.get("marker_status"),
        }

    upstream = _helper_status("mmdvm_upstream_build.py")
    if upstream.get("installed") is True:
        return {
            "variant": "upstream",
            "installed": True,
            "upstream_commit": upstream.get("upstream_commit"),
            "binary_sha256": upstream.get("binary_sha256"),
            "extension_api": None,
            "patch_sha256": None,
            "capabilities": [],
        }

    old = _read_json(RUNTIME_STATE)
    return {
        "variant": str(old.get("variant") or "unknown"),
        "installed": False,
        "upstream_commit": None,
        "binary_sha256": None,
        "extension_api": None,
        "patch_sha256": None,
        "capabilities": [],
        "error": "installed MMDVM runtime identity could not be verified",
    }


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
    }
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
