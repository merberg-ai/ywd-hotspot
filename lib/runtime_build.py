#!/usr/bin/env python3
"""Canonical YWD runtime binary build/install helper.

Both the Raspberry Pi OS image builder and normal GitHub full/fresh installation
use this entry point.  MMDVM-Host is always the exact pinned upstream revision
plus the pinned YWD passive DMR voice-tap patch.  DMRGateway remains pinned
upstream.  Both expensive binaries use the same conservative persistent cache
scheme.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

LIB = Path(__file__).resolve().parent
APP = LIB.parent
PINS = APP / "pins.env"
SOURCE_ROOT = Path(os.environ.get("YWD_RUNTIME_SOURCE_ROOT", "/opt/ywd-hotspot/src"))
CACHE_ROOT = Path(os.environ.get("YWD_RUNTIME_BUILD_CACHE", "/var/cache/ywd-hotspot/runtime-build"))
DMR_SOURCE = SOURCE_ROOT / "DMRGateway"
DMR_BINARY = Path(os.environ.get("YWD_DMRGATEWAY_BINARY", "/usr/local/bin/DMRGateway"))
DMR_PROVENANCE = Path(os.environ.get("YWD_DMRGATEWAY_BUILD_PROVENANCE", "/etc/ywd-hotspot/dmrgateway-build.json"))
CACHE_SCHEMA = 1


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def probe(argv, *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(x) for x in argv],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def run(argv, *, cwd: Path | None = None) -> None:
    print("+ " + " ".join(str(x) for x in argv), flush=True)
    subprocess.run([str(x) for x in argv], cwd=str(cwd) if cwd else None, check=True)


def read_pins() -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in PINS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("DMR_GATEWAY_REPO", "DMR_GATEWAY_COMMIT", "MMDVM_HOST_REPO", "MMDVM_HOST_COMMIT", "MMDVM_YWD_PATCH_SHA256"):
        if not out.get(key):
            raise RuntimeError(f"pins.env is missing {key}")
    if len(out["DMR_GATEWAY_COMMIT"]) != 40:
        raise RuntimeError("invalid DMRGateway pinned commit")
    return out


def build_jobs() -> int:
    try:
        value = int(os.environ.get("YWD_BUILD_JOBS", "1"))
    except Exception:
        value = 1
    return max(1, min(value, 4))


def target_architecture() -> str:
    p = probe(["dpkg", "--print-architecture"])
    value = (p.stdout or "").strip() if p.returncode == 0 else ""
    return value or platform.machine() or "unknown"


def compiler_identity() -> str:
    p = probe(["g++", "--version"])
    if p.returncode != 0:
        raise RuntimeError("g++ is required to build/identify runtime binaries")
    return ((p.stdout or "").splitlines() or ["unknown"])[0].strip()


def build_flags_identity() -> dict[str, str]:
    return {name: os.environ.get(name, "") for name in ("CPPFLAGS", "CXXFLAGS", "LDFLAGS")}


def atomic_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def plausible_binary(path: Path, architecture: str, minimum_size: int = 50_000) -> bool:
    if not path.is_file() or path.stat().st_size < minimum_size:
        return False
    file_cmd = shutil.which("file")
    if file_cmd:
        p = probe([file_cmd, "-b", path])
        if architecture == "armhf" and "ARM" not in (p.stdout or ""):
            return False
    return True


def dmr_signature() -> dict:
    pins = read_pins()
    return {
        "cache_schema": CACHE_SCHEMA,
        "component": "dmrgateway",
        "upstream_commit": pins["DMR_GATEWAY_COMMIT"],
        "architecture": target_architecture(),
        "compiler": compiler_identity(),
        "flags": build_flags_identity(),
    }


def signature_key(signature: dict) -> str:
    packed = json.dumps(signature, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()


def dmr_cache_entry(signature: dict) -> Path:
    return CACHE_ROOT / "dmrgateway" / signature_key(signature)


def install_dmr_cache(signature: dict) -> dict | None:
    if os.environ.get("YWD_RUNTIME_CACHE_BYPASS", "0") == "1":
        print("[CACHE BYPASS] DMRGateway requested", flush=True)
        return None
    entry = dmr_cache_entry(signature)
    binary = entry / "DMRGateway"
    manifest = entry / "manifest.json"
    try:
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        if doc.get("signature") != signature:
            return None
        expected = str(doc.get("binary_sha256") or "")
        if not expected or sha256(binary) != expected:
            return None
        if not plausible_binary(binary, str(signature["architecture"])):
            return None
    except Exception:
        return None

    DMR_BINARY.parent.mkdir(parents=True, exist_ok=True)
    tmp = DMR_BINARY.with_name(".DMRGateway.ywd-cache-new")
    shutil.copy2(binary, tmp)
    os.chmod(tmp, 0o755)
    os.replace(tmp, DMR_BINARY)
    result = {
        "status": "installed",
        "component": "DMRGateway",
        "upstream_commit": signature["upstream_commit"],
        "binary_sha256": expected,
        "built_at": doc.get("built_at"),
        "installed_at": int(time.time()),
        "cached": True,
        "cache_key": signature_key(signature),
        "build_signature": signature,
    }
    atomic_json(DMR_PROVENANCE, result)
    print(f"[CACHE HIT] DMRGateway {result['cache_key'][:12]}", flush=True)
    return result


def save_dmr_cache(signature: dict, built_at: int) -> dict:
    entry = dmr_cache_entry(signature)
    entry.mkdir(parents=True, exist_ok=True)
    cached_binary = entry / "DMRGateway"
    tmp = entry / ".DMRGateway.tmp"
    shutil.copy2(DMR_BINARY, tmp)
    os.chmod(tmp, 0o755)
    os.replace(tmp, cached_binary)
    digest = sha256(cached_binary)
    atomic_json(entry / "manifest.json", {
        "signature": signature,
        "binary_sha256": digest,
        "built_at": built_at,
    })
    checksum = entry / "SHA256"
    checksum.write_text(digest + "  DMRGateway\n", encoding="utf-8")
    os.chmod(checksum, 0o644)
    print(f"[CACHE SAVE] DMRGateway {signature_key(signature)[:12]}", flush=True)
    return {"cache_key": signature_key(signature), "binary_sha256": digest, "build_signature": signature}


def ensure_dmr_checkout(repo: str, commit: str) -> None:
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    good = False
    if (DMR_SOURCE / ".git").is_dir():
        p = probe(["git", "-C", DMR_SOURCE, "remote", "get-url", "origin"])
        good = p.returncode == 0 and (p.stdout or "").strip() == repo
    if not good:
        if DMR_SOURCE.exists():
            shutil.rmtree(DMR_SOURCE)
        run(["git", "clone", repo, DMR_SOURCE])
    have = probe(["git", "-C", DMR_SOURCE, "cat-file", "-e", f"{commit}^{{commit}}"])
    if have.returncode != 0:
        run(["git", "-C", DMR_SOURCE, "fetch", "origin", commit])
    run(["git", "-C", DMR_SOURCE, "reset", "--hard"], cwd=None)
    run(["git", "-C", DMR_SOURCE, "clean", "-fdx"])
    run(["git", "-C", DMR_SOURCE, "checkout", "--detach", commit])
    run(["git", "-C", DMR_SOURCE, "reset", "--hard", commit])
    run(["git", "-C", DMR_SOURCE, "clean", "-fdx"])


def install_dmrgateway() -> dict:
    if os.geteuid() != 0:
        raise RuntimeError("runtime binary installation must run as root")
    for command in ("git", "make", "g++"):
        if shutil.which(command) is None:
            raise RuntimeError(f"required build command is missing: {command}")
    pins = read_pins()
    signature = dmr_signature()
    cached = install_dmr_cache(signature)
    if cached is not None:
        return cached

    print(f"[CACHE MISS] DMRGateway {signature_key(signature)[:12]} - compiling", flush=True)
    ensure_dmr_checkout(pins["DMR_GATEWAY_REPO"], pins["DMR_GATEWAY_COMMIT"])
    run(["make", f"-j{build_jobs()}"], cwd=DMR_SOURCE)
    candidate = DMR_SOURCE / "DMRGateway"
    if not plausible_binary(candidate, str(signature["architecture"])):
        raise RuntimeError("DMRGateway build did not produce a plausible target binary")
    DMR_BINARY.parent.mkdir(parents=True, exist_ok=True)
    tmp = DMR_BINARY.with_name(".DMRGateway.ywd-new")
    shutil.copy2(candidate, tmp)
    os.chmod(tmp, 0o755)
    os.replace(tmp, DMR_BINARY)
    built_at = int(time.time())
    cache = save_dmr_cache(signature, built_at)
    result = {
        "status": "installed",
        "component": "DMRGateway",
        "upstream_commit": pins["DMR_GATEWAY_COMMIT"],
        "binary_sha256": sha256(DMR_BINARY),
        "built_at": built_at,
        "cached": False,
        **cache,
    }
    atomic_json(DMR_PROVENANCE, result)
    return result


def run_mmdvm_canonical() -> None:
    env = os.environ.copy()
    env.setdefault("YWD_RUNTIME_BUILD_CACHE", str(CACHE_ROOT))
    cmd = [sys.executable, str(LIB / "mmdvm_voice_build.py"), "canonical"]
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, env=env, check=True)


def mmdvm_status() -> dict:
    p = subprocess.run(
        [sys.executable, str(LIB / "mmdvm_voice_build.py"), "status"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    try:
        return json.loads(p.stdout or "{}")
    except Exception:
        return {"installed": False, "error": "status unavailable"}


def dmrgateway_status() -> dict:
    try:
        doc = json.loads(DMR_PROVENANCE.read_text(encoding="utf-8"))
    except Exception:
        doc = {}
    if not DMR_BINARY.is_file():
        return {"installed": False, "provenance": doc}
    digest = sha256(DMR_BINARY)
    signature = dmr_signature()
    installed = bool(
        doc.get("status") == "installed"
        and doc.get("upstream_commit") == signature["upstream_commit"]
        and doc.get("binary_sha256") == digest
        and doc.get("build_signature") == signature
    )
    return {"installed": installed, "binary_sha256": digest, "provenance": doc}


def install_all() -> int:
    if os.geteuid() != 0:
        print("ERROR: canonical runtime binary installation must run as root", file=sys.stderr)
        return 1
    print("============================================================", flush=True)
    print(" YWD canonical runtime binary installation", flush=True)
    print("============================================================", flush=True)
    run_mmdvm_canonical()
    dmr = install_dmrgateway()
    print(
        f"[OK] DMRGateway verified: upstream={dmr['upstream_commit'][:12]} "
        f"binary={dmr['binary_sha256'][:12]} cache={'hit' if dmr.get('cached') else 'miss'}",
        flush=True,
    )
    return 0


def show_status() -> int:
    state = {"mmdvm_host": mmdvm_status(), "dmrgateway": dmrgateway_status(), "cache_root": str(CACHE_ROOT)}
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0 if state["mmdvm_host"].get("installed") and state["dmrgateway"].get("installed") else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/verify canonical YWD runtime binaries")
    ap.add_argument("command", nargs="?", choices=("install", "status"), default="install")
    args = ap.parse_args()
    try:
        if args.command == "status":
            return show_status()
        return install_all()
    except Exception as exc:
        print(f"ERROR: runtime binary installation failed: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
