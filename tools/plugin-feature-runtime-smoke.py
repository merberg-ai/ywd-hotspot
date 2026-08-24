#!/usr/bin/env python3
"""Non-mutating RC3 smoke checks for plugin feature-runtime recovery policy."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import dashboard_plugins
import plugin_feature_runtime as runtime


def exercise_gateway_restore_on_gate_failure() -> None:
    states = {
        runtime.MMDVM_SERVICE: True,
        runtime.GATEWAY_SERVICE: True,
    }
    calls: list[tuple[str, ...]] = []

    old_active = runtime._active
    old_systemctl = runtime._systemctl
    old_gate = runtime.running_voice_gate
    old_sleep = runtime.time.sleep

    def active(unit: str) -> bool:
        return bool(states.get(unit, False))

    def systemctl(*args, check=True, timeout=35):
        calls.append(tuple(str(x) for x in args))
        action = str(args[0]) if args else ""
        unit = str(args[-1]) if args else ""
        if action == "stop":
            states[unit] = False
        elif action in {"start", "restart"}:
            states[unit] = True
        return SimpleNamespace(returncode=0, stdout="")

    try:
        runtime._active = active
        runtime._systemctl = systemctl
        runtime.running_voice_gate = lambda: True  # wrong for expected_gate=False
        runtime.time.sleep = lambda _seconds: None

        try:
            runtime._guarded_mmdvm_restart(False)
        except RuntimeError as exc:
            assert "wrong DMR voice gate" in str(exc), exc
        else:
            raise AssertionError("guarded restart unexpectedly accepted the wrong gate")

        assert states[runtime.MMDVM_SERVICE] is True, states
        assert states[runtime.GATEWAY_SERVICE] is True, states
        assert ("stop", runtime.GATEWAY_SERVICE) in calls, calls
        assert ("start", runtime.GATEWAY_SERVICE) in calls, calls
    finally:
        runtime._active = old_active
        runtime._systemctl = old_systemctl
        runtime.running_voice_gate = old_gate
        runtime.time.sleep = old_sleep


def main() -> int:
    assert dashboard_plugins._PLUGIN_MUTATION_TIMEOUT >= 90
    exercise_gateway_restore_on_gate_failure()
    print("[OK] plugin lifecycle WebUI timeout permits Pi Zero reconcile completion")
    print("[OK] guarded MMDVM gate failure restores pre-existing DMRGateway runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
