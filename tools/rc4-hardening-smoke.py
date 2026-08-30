#!/usr/bin/env python3
"""Run the offline/source-only RC4 hardening regression set.

This intentionally performs no RF transmission, network mutation, service
restart, package installation, or live configuration write. It is suitable for
a source checkout on the Pi or a development host.
"""
from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PY_SOURCES = (
    "lib/generate-config.py",
    "lib/oled.py",
    "lib/health.py",
    "tools/telemetry-config-smoke.py",
    "tools/source-oled-install-smoke.py",
    "tools/oled-health-smoke.py",
    "tools/tgif-routing-smoke.py",
    "tools/tgif-ui-smoke.py",
    "tools/tgif-status-smoke.py",
    "tools/tgif-directory-smoke.py",
    "tools/settings-restore-plugin-smoke.py",
    "tools/plugin-feature-runtime-smoke.py",
)

SHELL_SOURCES = (
    "INSTALL.sh",
    "INSTALL-core.sh",
    "UPDATE.sh",
    "UPDATE-core.sh",
    "GITHUB-UPDATE.sh",
    "GITHUB-UPDATE-core.sh",
    "lib/oled_owner.sh",
)

SMOKES = (
    "tools/telemetry-config-smoke.py",
    "tools/source-oled-install-smoke.py",
    "tools/oled-health-smoke.py",
    "tools/tgif-routing-smoke.py",
    "tools/tgif-ui-smoke.py",
    "tools/tgif-status-smoke.py",
    "tools/tgif-directory-smoke.py",
    "tools/settings-restore-plugin-smoke.py",
    "tools/plugin-feature-runtime-smoke.py",
)


def run(args: list[str]) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    print("===== RC4 HARDENING: PYTHON SYNTAX =====", flush=True)
    for rel in PY_SOURCES:
        path = ROOT / rel
        if not path.is_file():
            raise AssertionError(f"missing source: {rel}")
        py_compile.compile(str(path), doraise=True)
        print(f"[OK] {rel}")

    print("\n===== RC4 HARDENING: SHELL SYNTAX =====", flush=True)
    for rel in SHELL_SOURCES:
        path = ROOT / rel
        if not path.is_file():
            raise AssertionError(f"missing source: {rel}")
        run(["bash", "-n", str(path)])
        print(f"[OK] {rel}")

    print("\n===== RC4 HARDENING: REGRESSION SMOKES =====", flush=True)
    for rel in SMOKES:
        run([sys.executable, str(ROOT / rel)])

    print("\n===== RC4 HARDENING: PASS =====")
    print("[OK] persistent RSSI mapping path")
    print("[OK] source-install I2C/OLED policy")
    print("[OK] truthful OLED device health projection")
    print("[OK] TGIF routing/UI/status/directory regressions")
    print("[OK] plugin settings/runtime regressions")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"\n[FAIL] command exited {exc.returncode}: {' '.join(str(x) for x in exc.cmd)}", file=sys.stderr)
        raise SystemExit(exc.returncode or 1)
    except Exception as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
