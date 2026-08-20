#!/usr/bin/env python3
"""Resolve and exec an installed YWD service plugin inside the shared sandbox."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import plugin_catalog_overlay
import plugin_service_manager


def resolve(ident):
    plugin_catalog_overlay.install()
    plugin = plugin_service_manager.get_plugin(ident)
    entry = Path(plugin["directory"]) / plugin["entrypoint"]
    if not entry.is_file() or entry.is_symlink() or entry.stat().st_size > 131072:
        raise ValueError("service plugin entrypoint is unavailable or invalid")
    return plugin, entry


def main():
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("usage: plugin_service_runner.py [--check] PLUGIN_ID")
    check = len(sys.argv) == 3 and sys.argv[1] == "--check"
    ident = sys.argv[2] if check else sys.argv[1]
    _plugin, entry = resolve(ident)
    if check:
        return
    os.execv(sys.executable, [sys.executable, str(entry)])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"YWD plugin runner: {exc}", file=sys.stderr)
        raise SystemExit(1)
