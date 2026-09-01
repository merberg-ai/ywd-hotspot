#!/usr/bin/env python3
"""Narrow privileged dispatcher for YWD-Hotspot plugin administration."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_LIB = Path("/opt/ywd-hotspot/app/lib")
if str(APP_LIB) not in sys.path:
    sys.path.insert(0, str(APP_LIB))

import maintenance_coordinator
import plugin_catalog_overlay
plugin_catalog_overlay.install()

import plugin_feature_runtime
from plugin_admin_common import ensure_update_not_running, payload
from plugin_admin_packages import install_package, remove_plugin_data, uninstall_package
from plugin_admin_state import runtime_action, save_config, set_plugin, set_system
from plugin_admin_upload import apply_package, remove_package, review_package, upload_package

# These actions can change the aggregate enabled+installed capability set.  The
# trusted core reconciler runs only after the mutation succeeds; plugins never
# receive direct systemd or RF control.
FEATURE_RECONCILE_ACTIONS = frozenset({
    "plugin-system-set",
    "plugin-set",
    "plugin-package-install",
    "plugin-package-uninstall",
    "plugin-package-apply",
    "plugin-package-remove",
})

# Live/service/data mutations serialize with appliance maintenance so a future
# vocoder activation cannot race plugin replacement or runtime reconciliation.
MAINTENANCE_ACTIONS = frozenset({
    *FEATURE_RECONCILE_ACTIONS,
    "plugin-config-save",
    "plugin-runtime",
    "plugin-data-remove",
})


def _claim(action: str) -> str | None:
    if action not in MAINTENANCE_ACTIONS:
        return None
    lease = maintenance_coordinator.inspect()
    if lease.get("stale"):
        maintenance_coordinator.recover_stale()
        lease = maintenance_coordinator.inspect()
    if lease.get("active"):
        raise RuntimeError(f"appliance maintenance is busy: {lease.get('job_type') or 'maintenance'}")
    job_id = f"plugin-{os.getpid()}-{action}"
    maintenance_coordinator.claim(
        job_id, "plugin-mutation", "plugin-mutation",
        cancellable=False, owner_pid=os.getpid(), service="plugin-admin",
    )
    return job_id


def main():
    if os.geteuid() != 0:
        raise SystemExit("ywd-hotspot plugin admin must run as root")
    if len(sys.argv) != 2:
        raise SystemExit("usage: plugin_admin.py ACTION")
    ensure_update_not_running()
    action = sys.argv[1]
    data = payload(max_bytes=1800000)
    handlers = {
        "plugin-system-set": set_system,
        "plugin-set": set_plugin,
        "plugin-config-save": save_config,
        "plugin-runtime": runtime_action,
        "plugin-package-install": install_package,
        "plugin-package-uninstall": uninstall_package,
        "plugin-data-remove": remove_plugin_data,
        "plugin-package-upload": upload_package,
        "plugin-package-review": review_package,
        "plugin-package-apply": apply_package,
        "plugin-package-remove": remove_package,
    }
    handler = handlers.get(action)
    if handler is None:
        raise ValueError("unsupported plugin admin action")

    lease_job = _claim(action)
    try:
        result = handler(data)
        if action in FEATURE_RECONCILE_ACTIONS:
            result["feature_runtime"] = plugin_feature_runtime.reconcile()
        return result
    finally:
        if lease_job:
            try:
                maintenance_coordinator.release(lease_job, outcome="complete", owner_pid=os.getpid())
            except Exception:
                pass


if __name__ == "__main__":
    try:
        result = main()
        if result is not None:
            print(json.dumps(result, separators=(",", ":")))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:800]}, separators=(",", ":")))
        raise SystemExit(1)
