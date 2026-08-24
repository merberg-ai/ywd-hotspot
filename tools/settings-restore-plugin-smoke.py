#!/usr/bin/env python3
"""Source smoke for settings-restore plugin inventory/runtime completeness.

The portable settings restore must use the same complete package inventory as
normal plugin administration. Uploaded UI-only packages (for example DMR RX
Monitor) otherwise look missing and can have their installed registration
rewritten to false during restore. Restored plugin state must also reconcile
trusted aggregate feature runtimes just like normal plugin mutations do.
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
    restore = function_source(SETTINGS, "restore_settings")
    rollback_reconcile = function_source(SETTINGS, "_reconcile_restored_plugin_runtime")
    inventory = function_source(COMMON, "all_entries")

    assert "plugin_admin_common.all_entries()" in available, (
        "settings restore does not use the canonical complete plugin inventory"
    )
    assert "plugin_ui_manager.discover()" in inventory, (
        "canonical plugin inventory does not include UI plugins"
    )
    assert "plugin_manager.discover()" in inventory
    assert "plugin_service_manager.discover()" in inventory
    assert "plugin_feature_runtime.reconcile()" in restore, (
        "successful settings restore does not reconcile trusted plugin feature runtime"
    )
    assert "plugin_feature_runtime.reconcile()" in rollback_reconcile, (
        "settings-restore rollback does not reconcile restored plugin feature runtime"
    )

    print("[OK] settings restore uses canonical complete plugin inventory")
    print("[OK] canonical inventory includes declarative, service, and UI plugins")
    print("[OK] uploaded UI packages cannot be omitted by restore inventory")
    print("[OK] successful restore reconciles trusted plugin feature runtime")
    print("[OK] restore rollback reconciles trusted plugin feature runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
