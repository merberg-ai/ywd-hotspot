#!/usr/bin/env python3
"""Write/read lightweight YWD-Hotspot build provenance metadata."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUT = Path("/etc/ywd-hotspot/build-info.json")
CHANNEL_FILE = Path("/etc/ywd-hotspot/update-channel")
REPOSITORY = "https://github.com/merberg-ai/ywd-hotspot"


def run_git(source: Path, *args: str) -> str:
    try:
        p = subprocess.run(
            ["git", "-C", str(source), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
        return p.stdout.strip() if p.returncode == 0 else ""
    except Exception:
        return ""


def read_channel(branch: str) -> str:
    env = os.environ.get("YWD_UPDATE_CHANNEL", "").strip()
    if env in {"main", "dev", "dev-plugins"}:
        return env
    try:
        value = CHANNEL_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    except Exception:
        pass
    if branch in {"main", "dev"}:
        return branch
    return "main"


def discover(source: Path) -> dict:
    version = "unknown"
    try:
        version = (source / "VERSION").read_text(encoding="utf-8").strip() or "unknown"
    except Exception:
        pass

    branch = os.environ.get("YWD_GIT_BRANCH", "").strip()
    commit = os.environ.get("YWD_GIT_COMMIT", "").strip()
    commit_date = os.environ.get("YWD_GIT_COMMIT_DATE", "").strip()
    source_type = os.environ.get("YWD_SOURCE_TYPE", "").strip()
    source_state = os.environ.get("YWD_SOURCE_STATE", "").strip()

    git_ok = (source / ".git").exists() or bool(run_git(source, "rev-parse", "--git-dir"))
    if git_ok:
        branch = branch or run_git(source, "branch", "--show-current") or "detached"
        commit = commit or run_git(source, "rev-parse", "HEAD")
        commit_date = commit_date or run_git(source, "show", "-s", "--format=%cI", "HEAD")
        if not source_state:
            source_state = "dirty" if run_git(source, "status", "--porcelain") else "clean"
        source_type = source_type or "github"
    else:
        branch = branch or "release"
        commit = commit or "unknown"
        commit_date = commit_date or "unknown"
        source_state = source_state or "packaged"
        source_type = source_type or "release-archive"

    return {
        "version": version,
        "repository": REPOSITORY,
        "branch": branch,
        "commit": commit,
        "commit_short": commit[:10] if commit and commit != "unknown" else "unknown",
        "commit_date": commit_date,
        "source": source_type,
        "source_state": source_state,
        "update_channel": read_channel(branch),
        "installed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def write_info(source: Path, out: Path) -> dict:
    info = discover(source)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o644)
    try:
        os.chown(tmp, 0, 0)
    except Exception:
        pass
    os.replace(tmp, out)
    return info


def read_info(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write")
    w.add_argument("--source-dir", default=".")
    w.add_argument("--output", default=str(DEFAULT_OUT))
    r = sub.add_parser("show")
    r.add_argument("--input", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    if args.cmd == "write":
        print(json.dumps(write_info(Path(args.source_dir).resolve(), Path(args.output)), indent=2))
    else:
        print(json.dumps(read_info(Path(args.input)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
