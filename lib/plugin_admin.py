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

import plugin_catalog_overlay
plugin_catalog_overlay.install()

from plugin_admin_common import ensure_update_not_running, payload
from plugin_admin_packages import install_package, remove_plugin_data, uninstall_package
from plugin_admin_state import runtime_action, save_config, set_plugin, set_system
from plugin_admin_upload import remove_package, upload_package


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
        "plugin-package-remove": remove_package,
    }
    handler = handlers.get(action)
    if handler is None:
        raise ValueError("unsupported plugin admin action")
    print(json.dumps(handler(data), separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:800]}, separators=(",", ":")))
        raise SystemExit(1)
