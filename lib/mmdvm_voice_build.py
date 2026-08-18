#!/usr/bin/env python3
"""Build and install the YWD passive DMR voice-frame tap for pinned MMDVM-Host.

This helper is trusted appliance infrastructure. It never runs as plugin code.
The normal upstream MMDVM-Host binary remains the fallback: `ensure` restores an
existing binary and returns success if the experimental tap cannot be built.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

LIB = Path(__file__).resolve().parent
APP = LIB.parent
PINS = APP / "pins.env"
PATCH = LIB / "mmdvm_patches" / "0001-ywd-dmr-voice-mqtt.patch"
SOURCE = Path(os.environ.get("YWD_MMDVM_SOURCE", "/opt/ywd-hotspot/src/MMDVM-Host"))
BINARY = Path(os.environ.get("YWD_MMDVM_BINARY", "/usr/local/bin/MMDVM-Host"))
MARKER = Path(os.environ.get("YWD_MMDVM_VOICE_MARKER", "/var/lib/ywd-hotspot/mmdvm-voice-tap.json"))
PATCH_API = 1


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(argv, *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    printable = " ".join(str(x) for x in argv)
    print(f"+ {printable}", flush=True)
    return subprocess.run([str(x) for x in argv], cwd=str(cwd) if cwd else None, check=check)


def read_pins() -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in PINS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    repo = out.get("MMDVM_HOST_REPO", "")
    commit = out.get("MMDVM_HOST_COMMIT", "")
    if not repo or len(commit) < 12:
        raise RuntimeError("pins.env does not contain a valid MMDVM-Host repository/commit")
    return out


def read_marker() -> dict:
    try:
        value = json.loads(MARKER.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def write_marker(doc: dict) -> None:
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    tmp = MARKER.with_name(MARKER.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, MARKER)


def identity() -> dict[str, str | int]:
    pins = read_pins()
    if not PATCH.is_file():
        raise RuntimeError(f"voice tap patch is missing: {PATCH}")
    return {
        "api": PATCH_API,
        "upstream_commit": pins["MMDVM_HOST_COMMIT"],
        "patch_sha256": sha256(PATCH),
    }


def current_status() -> dict:
    ident = identity()
    marker = read_marker()
    binary_sha = sha256(BINARY) if BINARY.is_file() else None
    active = bool(
        binary_sha
        and marker.get("status") == "active"
        and marker.get("api") == ident["api"]
        and marker.get("upstream_commit") == ident["upstream_commit"]
        and marker.get("patch_sha256") == ident["patch_sha256"]
        and marker.get("binary_sha256") == binary_sha
    )
    return {**ident, "active": active, "binary_sha256": binary_sha, "marker": marker}


def ensure_source(repo_url: str, commit: str) -> None:
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    if not (SOURCE / ".git").is_dir():
        if SOURCE.exists():
            shutil.rmtree(SOURCE)
        run(["git", "clone", repo_url, SOURCE])

    # Restore the exact pinned upstream tree before every patched build. This
    # makes patching idempotent and prevents a prior experimental edit from
    # silently entering the appliance binary.
    run(["git", "-C", SOURCE, "reset", "--hard"], check=False)
    run(["git", "-C", SOURCE, "clean", "-fdx"], check=False)

    have = subprocess.run(
        ["git", "-C", str(SOURCE), "cat-file", "-e", f"{commit}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    if not have:
        run(["git", "-C", SOURCE, "fetch", "origin", commit])

    run(["git", "-C", SOURCE, "checkout", "--detach", commit])
    run(["git", "-C", SOURCE, "reset", "--hard", commit])
    run(["git", "-C", SOURCE, "clean", "-fdx"])


def build_strict() -> dict:
    if os.geteuid() != 0:
        raise RuntimeError("MMDVM voice tap build must run as root")
    for command in ("git", "make"):
        if shutil.which(command) is None:
            raise RuntimeError(f"required build command is missing: {command}")

    pins = read_pins()
    ident = identity()
    ensure_source(pins["MMDVM_HOST_REPO"], pins["MMDVM_HOST_COMMIT"])

    run(["git", "-C", SOURCE, "apply", "--check", PATCH])
    run(["git", "-C", SOURCE, "apply", PATCH])
    run(["make", "-j1"], cwd=SOURCE)

    candidate = SOURCE / "MMDVM-Host"
    if not candidate.is_file() or candidate.stat().st_size < 100_000:
        raise RuntimeError("patched MMDVM-Host build did not produce a plausible binary")

    BINARY.parent.mkdir(parents=True, exist_ok=True)
    staged = BINARY.with_name(".MMDVM-Host.ywd-voice-new")
    shutil.copy2(candidate, staged)
    os.chmod(staged, 0o755)
    os.replace(staged, BINARY)

    doc = {
        **ident,
        "status": "active",
        "binary_sha256": sha256(BINARY),
        "built_at": int(time.time()),
        "source": str(SOURCE),
        "topic": "ywd-mmdvm/voice",
    }
    write_marker(doc)
    return doc


def ensure() -> int:
    state = current_status()
    if state["active"]:
        print("YWD MMDVM DMR voice tap already active.", flush=True)
        return 0

    backup = None
    if BINARY.is_file():
        backup = BINARY.with_name(".MMDVM-Host.ywd-voice-fallback")
        shutil.copy2(BINARY, backup)
        os.chmod(backup, 0o755)

    print("YWD MMDVM DMR voice tap needs build; preparing pinned source...", flush=True)
    try:
        doc = build_strict()
        print(
            f"YWD MMDVM DMR voice tap installed: {doc['upstream_commit'][:12]} "
            f"patch={doc['patch_sha256'][:12]}",
            flush=True,
        )
        if backup and backup.exists():
            backup.unlink()
        return 0
    except Exception as exc:
        print(f"WARNING: DMR voice tap build failed: {exc}", file=sys.stderr, flush=True)
        if backup and backup.exists():
            try:
                os.replace(backup, BINARY)
                print("Restored previous MMDVM-Host binary; normal hotspot operation may continue.", file=sys.stderr, flush=True)
                write_marker({
                    **identity(),
                    "status": "failed-fallback",
                    "binary_sha256": sha256(BINARY),
                    "failed_at": int(time.time()),
                    "error": str(exc)[:500],
                })
                return 0
            except Exception as restore_exc:
                print(f"ERROR: could not restore previous MMDVM-Host binary: {restore_exc}", file=sys.stderr, flush=True)
        return 1


def show_status() -> int:
    state = current_status()
    marker = state.pop("marker")
    print(json.dumps({**state, "marker_status": marker.get("status"), "topic": marker.get("topic")}, indent=2, sort_keys=True))
    return 0 if state["active"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/verify the YWD passive MMDVM DMR voice tap")
    parser.add_argument("command", nargs="?", choices=("ensure", "build", "status"), default="ensure")
    args = parser.parse_args()
    if args.command == "status":
        return show_status()
    if args.command == "build":
        build_strict()
        return 0
    return ensure()


if __name__ == "__main__":
    raise SystemExit(main())
