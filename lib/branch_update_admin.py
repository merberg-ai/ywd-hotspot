#!/usr/bin/env python3
"""Authenticated WebUI software-channel inventory and guarded branch switch.

Only first-party appliance channels are exposed here.  Release/checkpoint refs
remain an engineering CLI capability and are deliberately not accepted from the
browser.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import admin as core_admin
import branch_update_runner
import update_admin
import update_runner as base

CHANNELS = ("main", "dev", "dev-plugins")
CHANNEL_META = {
    "main": {
        "label": "STABLE",
        "description": "Primary supported release channel.",
    },
    "dev": {
        "label": "DEVELOPMENT",
        "description": "Active YWD-Hotspot development channel; may change frequently.",
    },
    "dev-plugins": {
        "label": "PLUGIN DEVELOPMENT",
        "description": "Plugin/runtime integration development channel; may carry experimental plugin changes.",
    },
}


def payload() -> dict:
    raw = sys.stdin.buffer.read(131072)
    if not raw:
        return {}
    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON payload") from exc
    if not isinstance(doc, dict):
        raise ValueError("payload must be an object")
    return doc


def branch_name(data: dict) -> str:
    value = str(data.get("branch") or "").strip()
    if value not in CHANNELS:
        raise ValueError("Dashboard software channel must be main, dev, or dev-plugins")
    return value


def run(argv, timeout=30):
    return subprocess.run(
        [str(x) for x in argv], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout, check=False,
    )


def git_ok(*args, timeout=20) -> tuple[bool, str]:
    p = run(["git", "-C", str(base.REPO), *args], timeout)
    return p.returncode == 0, (p.stdout or "").strip()


def git(*args, timeout=20) -> str:
    ok, out = git_ok(*args, timeout=timeout)
    if not ok:
        raise RuntimeError(out or f"git {' '.join(args)} failed")
    return out


def fetch_channels() -> None:
    base.ensure_source()
    p = run(["git", "-C", str(base.REPO), "fetch", "--quiet", "--prune", "origin"], 90)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "could not fetch GitHub branches").strip()[-900:])


def saved_channel() -> str:
    try:
        value = base.CHANNEL.read_text(encoding="utf-8").strip()
    except Exception:
        value = ""
    if value in CHANNELS:
        return value
    build = base.read_json(base.BUILD, {})
    value = str(build.get("update_channel") or "")
    return value if value in CHANNELS else "unknown"


def relation(installed: str, target: str) -> str:
    if not installed or installed == "unknown":
        return "unknown"
    if installed == target:
        return "current"
    have, _ = git_ok("cat-file", "-e", f"{installed}^{{commit}}")
    if not have:
        return "unknown"
    forward, _ = git_ok("merge-base", "--is-ancestor", installed, target)
    if forward:
        return "forward"
    backward, _ = git_ok("merge-base", "--is-ancestor", target, installed)
    if backward:
        return "backward"
    return "diverged"


def target_schema(sha: str):
    ok, text = git_ok("show", f"{sha}:lib/config_model.py")
    if not ok:
        return None
    m = re.search(r"^SCHEMA\s*=\s*(\d+)\s*$", text, re.M)
    return int(m.group(1)) if m else None


def target_has_plugins(sha: str) -> bool:
    ok, _ = git_ok("cat-file", "-e", f"{sha}:lib/plugin_manager.py")
    return ok


def branch_doc(branch: str, installed_commit: str, current_version: str) -> dict:
    ref = f"refs/remotes/origin/{branch}"
    sha = git("rev-parse", f"{ref}^{{commit}}")
    version = git("show", f"{sha}:VERSION").strip() or "unknown"
    date = git("show", "-s", "--format=%cI", sha)
    subject = git("show", "-s", "--format=%s", sha)[:240]
    rel = relation(installed_commit, sha)
    meta = CHANNEL_META[branch]
    return {
        "branch": branch,
        "label": meta["label"],
        "description": meta["description"],
        "commit": sha,
        "commit_short": sha[:10],
        "version": version,
        "date": date,
        "subject": subject,
        "relation": rel,
        "same_installed_commit": sha == installed_commit,
        "same_installed_version": version == current_version,
        "config_schema": target_schema(sha),
        "plugin_runtime": target_has_plugins(sha),
    }


def inventory() -> dict:
    fetch_channels()
    build = base.read_json(base.BUILD, {})
    installed_commit = str(build.get("commit") or "unknown")
    installed_version = str(build.get("version") or "") or (
        (base.APP / "VERSION").read_text(encoding="utf-8").strip()
        if (base.APP / "VERSION").is_file() else "unknown"
    )
    checkout = git("branch", "--show-current") or "detached"
    saved = saved_channel()
    branches = [branch_doc(name, installed_commit, installed_version) for name in CHANNELS]
    return {
        "ok": True,
        "allowed": list(CHANNELS),
        "installed_version": installed_version,
        "installed_commit": installed_commit,
        "installed_commit_short": installed_commit[:10] if installed_commit != "unknown" else "unknown",
        "saved_channel": saved,
        "checkout_branch": checkout,
        "source": build.get("source") or "unknown",
        "source_state": build.get("source_state") or "unknown",
        "branches": branches,
    }


def branch_check(data: dict) -> dict:
    branch = branch_name(data)
    info = branch_update_runner.check_branch(branch, live_progress=False)
    inv = inventory()
    selected = next((row for row in inv["branches"] if row["branch"] == branch), {})
    return {
        "ok": True,
        **info,
        "selected": selected,
        "saved_channel": inv["saved_channel"],
        "checkout_branch": inv["checkout_branch"],
        "pending_config": update_admin.pending_config(),
    }


def write_channel(branch: str) -> None:
    base.CHANNEL.parent.mkdir(parents=True, exist_ok=True)
    tmp = base.CHANNEL.with_name(base.CHANNEL.name + ".tmp")
    tmp.write_text(branch + "\n", encoding="utf-8")
    os.chmod(tmp, 0o644)
    try:
        os.chown(tmp, 0, 0)
    except Exception:
        pass
    os.replace(tmp, base.CHANNEL)


def write_build_channel(branch: str) -> dict:
    doc = base.read_json(base.BUILD, {})
    if not isinstance(doc, dict):
        doc = {}
    doc = dict(doc)
    doc["branch"] = branch
    doc["update_channel"] = branch
    doc["source"] = "github"
    doc["source_state"] = "clean"
    tmp = base.BUILD.with_name(base.BUILD.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o644)
    try:
        os.chown(tmp, 0, 0)
    except Exception:
        pass
    os.replace(tmp, base.BUILD)
    return doc


def adopt_exact_branch(branch: str, selected: dict) -> dict:
    git("checkout", "--quiet", "-B", branch, f"origin/{branch}")
    git_ok("branch", "--set-upstream-to", f"origin/{branch}", branch)
    write_channel(branch)
    build = write_build_channel(branch)
    base.write_status(
        state="complete", phase="channel-adopted", progress=100,
        message=f"Software channel changed to {branch}; installed files already match its branch head.",
        installed_version=build.get("version") or selected.get("version"),
        current_commit=build.get("commit") or selected.get("commit"),
        target_version=selected.get("version"), target_commit=selected.get("commit_short"),
        target_date=selected.get("date"), channel=branch,
        available=False, up_to_date=True, validated=True,
        started_at=core_admin.now_iso(), completed_at=core_admin.now_iso(), error=None,
    )
    core_admin.audit("software-channel-adopt", {
        "channel": branch,
        "commit": selected.get("commit"),
        "version": selected.get("version"),
    })
    return {
        "ok": True, "started": False, "adopted": True,
        "channel": branch, "target_commit": selected.get("commit"),
        "target_version": selected.get("version"),
    }


def branch_job_running() -> bool:
    p = run([
        "systemctl", "list-units", "--type=service", "--state=running",
        "--no-legend", "ywd-branch-update-*.service",
    ], 6)
    return bool((p.stdout or "").strip())


def branch_switch(data: dict) -> dict:
    branch = branch_name(data)
    if update_admin.service_active() or branch_job_running():
        raise ValueError("a software update or branch switch is already running")
    if update_admin.pending_config():
        raise ValueError("Configuration has saved-but-not-applied changes; apply or revert them before switching channels")

    inv = inventory()
    selected = next((row for row in inv["branches"] if row["branch"] == branch), None)
    if not selected:
        raise RuntimeError("selected branch metadata is unavailable")

    if selected.get("same_installed_commit"):
        return adopt_exact_branch(branch, selected)

    # Full candidate validation happens while the current application and RF
    # stack remain untouched. The detached runner re-validates again immediately
    # before the live transition.
    checked = branch_update_runner.check_branch(branch, live_progress=False)
    if not checked.get("validated"):
        raise RuntimeError("selected branch did not pass candidate validation")

    base.write_status(
        state="running", phase="queued", progress=3,
        message=f"Starting protected switch to {branch}.",
        installed_version=checked.get("installed_version"),
        current_commit=checked.get("current_commit"),
        target_version=checked.get("target_version"),
        target_commit=checked.get("target_commit"),
        target_date=checked.get("target_date"), channel=branch,
        available=True, up_to_date=False, validated=True,
        started_at=core_admin.now_iso(), completed_at=None, error=None,
    )

    if not shutil.which("systemd-run"):
        raise RuntimeError("systemd-run is unavailable; cannot detach branch switch safely")
    unit = f"ywd-branch-update-{int(time.time())}-{os.getpid()}"
    p = run([
        "systemd-run", "--quiet", "--collect", f"--unit={unit}",
        "--property=Type=oneshot", "--property=TimeoutStartSec=45min",
        "--property=Nice=5",
        "/usr/bin/python3", str(HERE / "branch_update_runner.py"), branch,
    ], 15)
    if p.returncode != 0:
        base.write_status(
            state="failed", phase="start-failed", progress=0,
            message="Could not start detached branch switch.",
            error=(p.stderr or p.stdout or "systemd-run failed").strip()[-1000:],
            completed_at=core_admin.now_iso(), channel=branch,
        )
        raise RuntimeError((p.stderr or p.stdout or "could not start branch switch").strip()[-900:])

    core_admin.audit("software-channel-switch-start", {
        "from_channel": inv.get("saved_channel"),
        "to_channel": branch,
        "relation": selected.get("relation"),
        "target_commit": selected.get("commit"),
        "target_version": selected.get("version"),
    })
    return {
        "ok": True, "started": True, "adopted": False,
        "channel": branch, "relation": selected.get("relation"),
        "target_commit": selected.get("commit"),
        "target_version": selected.get("version"),
    }


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("branch update admin helper must run as root")
    if len(sys.argv) != 2:
        raise SystemExit("usage: branch_update_admin.py ACTION")
    action = sys.argv[1]
    data = payload()
    if action == "update-branches":
        out = inventory()
    elif action == "update-branch-check":
        out = branch_check(data)
    elif action == "update-branch-switch":
        out = branch_switch(data)
    else:
        raise ValueError("unsupported branch update action")
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:1000]}, separators=(",", ":")))
        raise SystemExit(1)
