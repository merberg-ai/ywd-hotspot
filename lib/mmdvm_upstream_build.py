#!/usr/bin/env python3
"""Build/install/verify the exact pinned upstream MMDVM-Host variant.

This is the explicit opt-out from YWD MMDVM extensions. It intentionally does
not apply the YWD passive DMR voice/plugin patch. Its cache namespace and
signature are distinct from the YWD Extended variant so the two binaries can
never be confused or substituted for one another.
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
SOURCE = Path(os.environ.get("YWD_MMDVM_SOURCE", "/opt/ywd-hotspot/src/MMDVM-Host"))
BINARY = Path(os.environ.get("YWD_MMDVM_BINARY", "/usr/local/bin/MMDVM-Host"))
PROVENANCE = Path(os.environ.get("YWD_MMDVM_BUILD_PROVENANCE", "/etc/ywd-hotspot/mmdvm-build.json"))
VOICE_MARKER = Path(os.environ.get("YWD_MMDVM_VOICE_MARKER", "/var/lib/ywd-hotspot/mmdvm-voice-tap.json"))
CACHE_ROOT = Path(os.environ.get("YWD_RUNTIME_BUILD_CACHE", "/var/cache/ywd-hotspot/runtime-build"))
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
    if not out.get("MMDVM_HOST_REPO") or len(out.get("MMDVM_HOST_COMMIT", "")) != 40:
        raise RuntimeError("pins.env does not contain a valid MMDVM-Host repository/commit")
    return out


def target_architecture() -> str:
    p = probe(["dpkg", "--print-architecture"])
    value = (p.stdout or "").strip() if p.returncode == 0 else ""
    return value or platform.machine() or "unknown"


def compiler_identity() -> str:
    p = probe(["g++", "--version"])
    if p.returncode != 0:
        raise RuntimeError("g++ is required to build/identify MMDVM-Host")
    return ((p.stdout or "").splitlines() or ["unknown"])[0].strip()


def build_jobs() -> int:
    try:
        value = int(os.environ.get("YWD_BUILD_JOBS", "1"))
    except Exception:
        value = 1
    return max(1, min(value, 4))


def build_flags_identity() -> dict[str, str]:
    return {name: os.environ.get(name, "") for name in ("CPPFLAGS", "CXXFLAGS", "LDFLAGS")}


def signature() -> dict:
    pins = read_pins()
    return {
        "cache_schema": CACHE_SCHEMA,
        "component": "mmdvm-host",
        "variant": "upstream",
        "upstream_commit": pins["MMDVM_HOST_COMMIT"],
        "architecture": target_architecture(),
        "compiler": compiler_identity(),
        "flags": build_flags_identity(),
    }


def cache_key(sig: dict | None = None) -> str:
    sig = sig or signature()
    packed = json.dumps(sig, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()


def cache_dir(sig: dict | None = None) -> Path:
    sig = sig or signature()
    return CACHE_ROOT / "mmdvm-host-upstream" / cache_key(sig)


def atomic_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def plausible_binary(path: Path, architecture: str) -> bool:
    if not path.is_file() or path.stat().st_size < 100_000:
        return False
    file_cmd = shutil.which("file")
    if file_cmd:
        p = probe([file_cmd, "-b", path])
        if architecture == "armhf" and "ARM" not in (p.stdout or ""):
            return False
    return True


def clean_voice_marker() -> None:
    try:
        VOICE_MARKER.unlink()
    except FileNotFoundError:
        pass


def result_doc(sig: dict, binary_sha: str, *, cached: bool, built_at: int | None) -> dict:
    return {
        "status": "installed",
        "component": "MMDVM-Host",
        "variant": "upstream",
        "upstream_commit": sig["upstream_commit"],
        "binary_sha256": binary_sha,
        "built_at": built_at,
        "installed_at": int(time.time()),
        "cached": cached,
        "cache_key": cache_key(sig),
        "build_signature": sig,
        "capabilities": [],
        "extension_api": None,
        "patch_sha256": None,
    }


def load_cache() -> dict | None:
    if os.environ.get("YWD_RUNTIME_CACHE_BYPASS", "0") == "1":
        print("[CACHE BYPASS] MMDVM-Host upstream requested", flush=True)
        return None
    sig = signature()
    entry = cache_dir(sig)
    binary = entry / "MMDVM-Host"
    manifest = entry / "manifest.json"
    try:
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        if doc.get("signature") != sig:
            return None
        expected = str(doc.get("binary_sha256") or "")
        if not expected or sha256(binary) != expected:
            return None
        if not plausible_binary(binary, str(sig["architecture"])):
            return None
    except Exception:
        return None

    BINARY.parent.mkdir(parents=True, exist_ok=True)
    tmp = BINARY.with_name(".MMDVM-Host.ywd-upstream-cache-new")
    shutil.copy2(binary, tmp)
    os.chmod(tmp, 0o755)
    os.replace(tmp, BINARY)
    result = result_doc(sig, expected, cached=True, built_at=doc.get("built_at"))
    atomic_json(PROVENANCE, result)
    clean_voice_marker()
    print(f"[CACHE HIT] MMDVM-Host upstream {result['cache_key'][:12]}", flush=True)
    return result


def save_cache(sig: dict, built_at: int) -> dict:
    entry = cache_dir(sig)
    entry.mkdir(parents=True, exist_ok=True)
    binary = entry / "MMDVM-Host"
    tmp = entry / ".MMDVM-Host.tmp"
    shutil.copy2(BINARY, tmp)
    os.chmod(tmp, 0o755)
    os.replace(tmp, binary)
    digest = sha256(binary)
    atomic_json(entry / "manifest.json", {
        "signature": sig,
        "binary_sha256": digest,
        "built_at": built_at,
    })
    (entry / "SHA256").write_text(digest + "  MMDVM-Host\n", encoding="utf-8")
    print(f"[CACHE SAVE] MMDVM-Host upstream {cache_key(sig)[:12]}", flush=True)
    return {"binary_sha256": digest, "cache_key": cache_key(sig)}


def ensure_checkout(repo: str, commit: str) -> None:
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    good = False
    if (SOURCE / ".git").is_dir():
        p = probe(["git", "-C", SOURCE, "remote", "get-url", "origin"])
        good = p.returncode == 0 and (p.stdout or "").strip() == repo
    if not good:
        if SOURCE.exists():
            shutil.rmtree(SOURCE)
        run(["git", "clone", repo, SOURCE])
    have = probe(["git", "-C", SOURCE, "cat-file", "-e", f"{commit}^{{commit}}"])
    if have.returncode != 0:
        run(["git", "-C", SOURCE, "fetch", "origin", commit])
    run(["git", "-C", SOURCE, "reset", "--hard"])
    run(["git", "-C", SOURCE, "clean", "-fdx"])
    run(["git", "-C", SOURCE, "checkout", "--detach", commit])
    run(["git", "-C", SOURCE, "reset", "--hard", commit])
    run(["git", "-C", SOURCE, "clean", "-fdx"])


def install() -> dict:
    if os.geteuid() != 0:
        raise RuntimeError("canonical upstream MMDVM build must run as root")
    for command in ("git", "make", "g++"):
        if shutil.which(command) is None:
            raise RuntimeError(f"required build command is missing: {command}")

    cached = load_cache()
    if cached is not None:
        return cached

    pins = read_pins()
    sig = signature()
    print(f"[CACHE MISS] MMDVM-Host upstream {cache_key(sig)[:12]} - compiling exact pinned upstream", flush=True)
    ensure_checkout(pins["MMDVM_HOST_REPO"], pins["MMDVM_HOST_COMMIT"])
    run(["make", f"-j{build_jobs()}"], cwd=SOURCE)
    candidate = SOURCE / "MMDVM-Host"
    if not plausible_binary(candidate, str(sig["architecture"])):
        raise RuntimeError("upstream MMDVM-Host build did not produce a plausible target binary")

    BINARY.parent.mkdir(parents=True, exist_ok=True)
    tmp = BINARY.with_name(".MMDVM-Host.ywd-upstream-new")
    shutil.copy2(candidate, tmp)
    os.chmod(tmp, 0o755)
    os.replace(tmp, BINARY)
    built_at = int(time.time())
    cache = save_cache(sig, built_at)
    result = result_doc(sig, cache["binary_sha256"], cached=False, built_at=built_at)
    atomic_json(PROVENANCE, result)
    clean_voice_marker()
    return result


def status() -> dict:
    try:
        doc = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    except Exception:
        doc = {}
    sig = signature()
    digest = sha256(BINARY) if BINARY.is_file() else None
    installed = bool(
        digest
        and doc.get("status") == "installed"
        and doc.get("variant") == "upstream"
        and doc.get("upstream_commit") == sig["upstream_commit"]
        and doc.get("binary_sha256") == digest
        and doc.get("build_signature") == sig
    )
    return {
        "installed": installed,
        "variant": "upstream",
        "upstream_commit": sig["upstream_commit"],
        "binary_sha256": digest,
        "capabilities": [],
        "extension_api": None,
        "patch_sha256": None,
        "provenance": doc,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/verify exact pinned upstream MMDVM-Host")
    ap.add_argument("command", nargs="?", choices=("install", "canonical", "status"), default="install")
    args = ap.parse_args()
    try:
        if args.command == "status":
            print(json.dumps(status(), indent=2, sort_keys=True))
            return 0 if status()["installed"] else 1
        result = install()
        print(
            f"[OK] Canonical upstream MMDVM verified: upstream={result['upstream_commit'][:12]} "
            f"binary={result['binary_sha256'][:12]} cache={'hit' if result.get('cached') else 'miss'}",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(f"ERROR: upstream MMDVM build failed: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
