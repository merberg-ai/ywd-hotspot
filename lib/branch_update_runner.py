#!/usr/bin/env python3
"""Detached runner for authenticated WebUI branch switches.

This intentionally reuses the canonical GitHub updater and the existing shared
update-status document. The dashboard may select only the approved appliance
channels, while engineering/release CLI workflows remain free to target release
branches explicitly.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import update_runner as base

CHANNELS = {"main", "dev", "dev-plugins"}


def validate_branch(value: str) -> str:
    branch = str(value or "").strip()
    if branch not in CHANNELS:
        raise ValueError("WebUI branch must be main, dev, or dev-plugins")
    return branch


def check_branch(branch: str, *, live_progress: bool = False) -> dict:
    branch = validate_branch(branch)
    if live_progress:
        base.progress(8, "source", f"Checking managed Git source for {branch}…")
    base.ensure_source()
    if not base.UPDATER.is_file():
        raise RuntimeError("GitHub updater is missing")
    if live_progress:
        base.progress(18, "fetching", f"Fetching and validating {branch} from GitHub…")
    p = base.run(["bash", str(base.UPDATER), "--dry-run", "--branch", branch], timeout=210)
    info = base.parse_check(p.stdout)
    info["channel"] = branch
    info.update(base.scanner_before())
    if p.returncode != 0:
        lines = base.clean(p.stdout).strip().splitlines()
        raise RuntimeError((lines[-1] if lines else "branch candidate check failed")[:900])
    if not info.get("validated") and not info.get("up_to_date"):
        raise RuntimeError("selected branch candidate did not pass validation")
    if live_progress:
        base.progress(35, "validated", f"{branch} candidate validation passed.", **info)
    return info


def stream_branch_update(info: dict, branch: str) -> tuple[int, str]:
    proc = subprocess.Popen(
        ["bash", str(base.UPDATER), "--branch", branch],
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    if proc.stdin:
        proc.stdin.write("y\n")
        proc.stdin.flush()
        proc.stdin.close()

    lines: list[str] = []
    milestones = [
        ("Fetching YWD-Hotspot from GitHub", 42, "fetching", f"Refreshing {branch} from GitHub…"),
        ("Candidate validation: OK", 52, "validated", "Live candidate re-validation passed."),
        ("TGIF scanner quiesced", 56, "scanner-paused", "TGIF scanner paused for protected channel replacement…"),
        ("Applying validated candidate", 58, "starting", f"Starting protected switch to {branch}…"),
        ("Protected pre-update backup:", 66, "backup", "Protected rollback backup created."),
        ("Installing ", 74, "installing", "Installing the selected branch…"),
        ("Persistent journal:", 84, "services", "Runtime files installed. Restoring service policy…"),
        ("Updated to ", 91, "restarting", "Branch installed. Restarting and verifying services…"),
        ("TGIF scanner restored", 95, "scanner-restored", "TGIF scanner runtime restored after channel switch."),
        ("GitHub source checkout updated successfully", 97, "finalizing", "Finalizing managed Git branch state…"),
    ]
    seen = set()
    if proc.stdout:
        for raw in proc.stdout:
            line = base.clean(raw.rstrip("\n"))
            lines.append(line)
            if len(lines) > 400:
                lines = lines[-400:]
            for marker, pct, phase, message in milestones:
                key = (marker, pct)
                if key not in seen and marker in line:
                    seen.add(key)
                    base.progress(pct, phase, message, **info)
                    break
    rc = proc.wait()
    return rc, "\n".join(lines)


def install_branch(branch: str) -> int:
    branch = validate_branch(branch)
    try:
        base.write_status(
            state="running", phase="starting", progress=3,
            message=f"Branch switch to {branch} started.", error=None,
            started_at=base.now_iso(), completed_at=None, channel=branch,
        )
        info = check_branch(branch, live_progress=True)
        if info.get("up_to_date") or not info.get("available"):
            raise RuntimeError(
                f"{branch} now matches the installed build; reopen Change Channel and retry adoption"
            )

        base.progress(38, "queued", f"Launching validated switch to {branch}…", **info)
        rc, output = stream_branch_update(info, branch)
        text = base.clean(output)
        tail = "\n".join(text.strip().splitlines()[-24:])[-5000:]
        if rc != 0:
            after = base.scanner_current()
            base.write_status(
                state="failed", phase="failed", progress=100,
                message=f"Switch to {branch} failed; rollback handling completed or is in progress.",
                error=(tail or "branch switch failed")[-1200:], completed_at=base.now_iso(),
                output_tail=tail, **info, **after,
                scanner_restore=base.scanner_restore_result(info, after),
            )
            return rc or 1

        built = base.read_json(base.BUILD, {})
        backup = None
        matches = re.findall(r"Backup retained:\s*(\S+)", text)
        if matches:
            backup = matches[-1]
        after = base.scanner_current()
        base.write_status(
            state="complete", phase="branch-switched", progress=100,
            message=f"Software channel switched to {branch}.", error=None,
            completed_at=base.now_iso(),
            installed_version=built.get("version") or info.get("target_version"),
            current_commit=built.get("commit") or info.get("target_commit"),
            target_version=info.get("target_version"),
            target_commit=info.get("target_commit"),
            target_date=info.get("target_date"),
            channel=built.get("update_channel") or branch,
            available=False, up_to_date=True, validated=True,
            backup=backup, output_tail=tail,
            **{k: v for k, v in info.items() if k.startswith("scanner_before_") or k == "scanner_was_active"},
            **after, scanner_restore=base.scanner_restore_result(info, after),
        )
        return 0
    except Exception as exc:
        base.write_status(
            state="failed", phase="branch-switch-failed", progress=100,
            message=f"Switch to {branch} failed.", error=str(exc)[:1200],
            completed_at=base.now_iso(), channel=branch, **base.scanner_current(),
        )
        return 1


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("branch update runner must run as root")
    if len(sys.argv) != 2:
        raise SystemExit("usage: branch_update_runner.py main|dev|dev-plugins")
    raise SystemExit(install_branch(sys.argv[1]))


if __name__ == "__main__":
    main()
