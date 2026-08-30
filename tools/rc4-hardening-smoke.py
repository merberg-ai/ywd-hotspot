#!/usr/bin/env python3
"""Run the offline/source-only RC4 hardening regression set.

This intentionally performs no RF transmission, network mutation, service
restart, package installation, live configuration write, or source-tree
bytecode write. It is safe to run against the root-owned managed checkout as a
normal user.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PY_SOURCES = (
    "lib/config_model.py",
    "lib/generate-config.py",
    "lib/settings_backup.py",
    "lib/setup_server.py",
    "lib/setup_restore_server.py",
    "lib/setup_admin.py",
    "lib/oled.py",
    "lib/health.py",
    "tools/telemetry-config-smoke.py",
    "tools/source-oled-install-smoke.py",
    "tools/oled-health-smoke.py",
    "tools/ssh-policy-smoke.py",
    "tools/settings-backup-tgif-smoke.py",
    "tools/rc4-ui-setup-smoke.py",
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
    "lib/system_branding.sh",
    "lib/oled_owner.sh",
)

SMOKES = (
    "tools/telemetry-config-smoke.py",
    "tools/source-oled-install-smoke.py",
    "tools/oled-health-smoke.py",
    "tools/ssh-policy-smoke.py",
    "tools/settings-backup-tgif-smoke.py",
    "tools/rc4-ui-setup-smoke.py",
    "tools/tgif-routing-smoke.py",
    "tools/tgif-ui-smoke.py",
    "tools/tgif-status-smoke.py",
    "tools/tgif-directory-smoke.py",
    "tools/settings-restore-plugin-smoke.py",
    "tools/plugin-feature-runtime-smoke.py",
)


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run(args: list[str]) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, env=child_env(), check=True)


def syntax_check(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec", dont_inherit=True)


def main() -> int:
    print("===== RC4 HARDENING: PYTHON SYNTAX =====", flush=True)
    for rel in PY_SOURCES:
        path = ROOT / rel
        if not path.is_file():
            raise AssertionError(f"missing source: {rel}")
        syntax_check(path)
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
    print("[OK] SSH key-only/password-or-key policy contract")
    print("[OK] encrypted TGIF/BrandMeister backup round trip + redacted preview")
    print("[OK] RC4 HTTP setup/TGIF presentation/default-waterfall policy")
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
