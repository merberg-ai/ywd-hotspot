#!/usr/bin/env python3
"""Source smoke for settings-restore plugin inventory completeness.

The portable settings restore must use the same complete package inventory as
normal plugin administration. Uploaded UI-only packages (for example DMR RX
Monitor) otherwise look missing and can have their installed registration
rewritten to false during restore.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "lib" / "settings_admin.py"
COMMON = ROOT / "lib" / "plugin_admin_common.py"


def function_source(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            end = getattr(node, "end_lineno", None)
            if end is None:
                raise AssertionError(f"cannot determine end of {name} in {path}")
            return "\n".join(lines[node.lineno - 1:end])
    raise AssertionError(f"missing function {name} in {path}")


def main() -> int:
    available = function_source(SETTINGS, "_available_map")
    inventory = function_source(COMMON, "all_entries")

    assert "plugin_admin_common.all_entries()" in available, (
        "settings restore does not use the canonical complete plugin inventory"
    )
    assert "plugin_ui_manager.discover()" in inventory, (
        "canonical plugin inventory does not include UI plugins"
    )
    assert "plugin_manager.discover()" in inventory
    assert "plugin_service_manager.discover()" in inventory

    print("[OK] settings restore uses canonical complete plugin inventory")
    print("[OK] canonical inventory includes declarative, service, and UI plugins")
    print("[OK] uploaded UI packages cannot be omitted by restore inventory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
