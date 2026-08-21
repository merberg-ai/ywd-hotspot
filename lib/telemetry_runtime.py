#!/usr/bin/env python3
"""Install/activate the passive YWD MMDVM telemetry runtime.

Normal app updates never rebuild MMDVM-Host. This helper only adds the local
Mosquitto broker/client packages when missing and activates the low-rate
telemetry services. High-rate DMR voice infrastructure is intentionally not
owned here; RX Monitor lifecycle controls it separately.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

POLICY = Path("/usr/sbin/policy-rc.d")


def run(args, check=True, quiet=False):
    return subprocess.run(args, check=check, text=True,
                          stdout=subprocess.DEVNULL if quiet else None,
                          stderr=subprocess.DEVNULL if quiet else None)


def active(unit):
    return run(["systemctl", "is-active", "--quiet", unit], check=False, quiet=True).returncode == 0


def ensure_packages():
    need_broker = shutil.which("mosquitto") is None
    need_client = shutil.which("mosquitto_sub") is None
    if not (need_broker or need_client):
        return False

    made_policy = False
    try:
        if not POLICY.exists():
            POLICY.write_text("#!/bin/sh\nexit 101\n", encoding="utf-8")
            os.chmod(POLICY, 0o755)
            made_policy = True
        print("Installing local telemetry broker/client dependencies...")
        run(["apt-get", "update"])
        run(["apt-get", "install", "-y", "--no-install-recommends", "mosquitto", "mosquitto-clients"])
    finally:
        if made_policy:
            try:
                POLICY.unlink()
            except FileNotFoundError:
                pass

    # Only disable the distro unit when the broker itself did not exist before
    # this helper ran. Never take ownership of an operator's pre-existing broker.
    if need_broker:
        run(["systemctl", "disable", "--now", "mosquitto.service"], check=False, quiet=True)
    return True


def ensure_runtime():
    if os.geteuid() != 0:
        raise SystemExit("telemetry_runtime.py must run as root")
    packages_changed = ensure_packages()
    if shutil.which("mosquitto") is None or shutil.which("mosquitto_sub") is None:
        raise RuntimeError("mosquitto broker/client commands are unavailable")

    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", "ywd-mqtt.service"])

    # Application updates replace the bridge Python on disk while an already
    # running process would otherwise keep executing the previous build from
    # memory. Enable it for boot, then restart an existing bridge so the live
    # process always matches the newly installed application tree. First-time
    # installs simply start it. Session history is intentionally runtime-only.
    telemetry_was_active = active("ywd-mmdvm-telemetry.service")
    run(["systemctl", "enable", "ywd-mmdvm-telemetry.service"])
    if telemetry_was_active:
        run(["systemctl", "restart", "ywd-mmdvm-telemetry.service"])
    else:
        run(["systemctl", "start", "ywd-mmdvm-telemetry.service"])
    if not active("ywd-mmdvm-telemetry.service"):
        raise RuntimeError("YWD MMDVM telemetry bridge is not active after reconciliation")

    # MMDVM-Host opens MQTT only during startup. If RF is already running,
    # perform one controlled restart now that the broker is available. If the
    # restart command itself fails, explicitly attempt to recover MMDVM-Host
    # before restoring DMRGateway so passive telemetry cannot casually strand RF.
    mmdvm_was_active = active("ywd-mmdvmhost.service")
    gateway_was_active = active("ywd-dmrgateway.service")
    if mmdvm_was_active:
        if gateway_was_active:
            run(["systemctl", "stop", "ywd-dmrgateway.service"], check=False)
        restart_error = None
        try:
            run(["systemctl", "restart", "ywd-mmdvmhost.service"])
        except Exception as exc:
            restart_error = exc
            run(["systemctl", "start", "ywd-mmdvmhost.service"], check=False)
        finally:
            if gateway_was_active:
                time.sleep(2)
                run(["systemctl", "start", "ywd-dmrgateway.service"], check=False)
        if not active("ywd-mmdvmhost.service"):
            raise RuntimeError(f"MMDVM-Host did not recover after telemetry restart: {restart_error or 'inactive'}")
        if restart_error is not None:
            print(f"[WARN] Initial MMDVM-Host restart failed but the service recovered: {restart_error}")

    print("YWD MMDVM telemetry runtime ready on loopback MQTT 127.0.0.1:18883")
    if packages_changed:
        print("Mosquitto broker/client package set was completed for the telemetry bus.")


def main():
    if len(sys.argv) != 2 or sys.argv[1] != "ensure":
        raise SystemExit("usage: telemetry_runtime.py ensure")
    ensure_runtime()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[FAIL] telemetry runtime: {exc}", file=sys.stderr)
        raise SystemExit(1)
