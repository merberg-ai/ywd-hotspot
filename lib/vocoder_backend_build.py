#!/usr/bin/env python3
"""Unprivileged staged builder for the approved YWD mbelib backend.

This module never installs or activates a live backend. It fetches the exact
approved mbelib commit into YWD-owned state, builds the YWD Protocol v1 adapter,
self-tests the resulting candidate, and publishes an immutable prepared-candidate
record for a later privileged activation transaction.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import select
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

import vocoder_manager

VAR = Path(os.environ.get("YWD_VAR", "/var/lib/ywd-hotspot"))
STATE_DIR = Path(os.environ.get("YWD_VOCODER_STATE_DIR", str(VAR / "vocoder")))
CACHE_ROOT = Path(os.environ.get("YWD_VOCODER_BUILD_CACHE", str(STATE_DIR / "build-cache")))
SOURCE_CACHE = CACHE_ROOT / "sources"
CANDIDATE_CACHE = CACHE_ROOT / "candidates"
PREPARED = Path(os.environ.get("YWD_VOCODER_PREPARED", str(STATE_DIR / "prepared.json")))
ADAPTER_SOURCE = Path(__file__).resolve().with_name("vocoder_mbelib_adapter.cpp")
BUILD_SCHEMA = 1
MAX_CANDIDATES = 2


class BuildError(RuntimeError):
    pass


class BuildCancelled(BuildError):
    pass


def _now() -> int:
    return int(time.time())


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(128 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_json(path: Path, doc: dict, mode: int = 0o640) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def _safe_env() -> dict[str, str]:
    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "HOME": str(STATE_DIR),
        "CMAKE_BUILD_PARALLEL_LEVEL": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _emit_lines(text: str, log: Callable[[str], None]) -> None:
    for raw in str(text or "").replace("\x00", "").splitlines():
        line = raw.strip()
        if line:
            log(line[:1200])


def run_logged(
    args: list[str],
    *,
    cwd: Path | None,
    timeout: int,
    log: Callable[[str], None],
    cancel: Callable[[], bool],
) -> subprocess.CompletedProcess:
    """Run one fixed argv command with bounded streaming output and cancellation."""
    if not args or any(not isinstance(x, str) or not x for x in args):
        raise BuildError("invalid build command")
    log("$ " + " ".join(args))
    proc = subprocess.Popen(
        args,
        cwd=str(cwd) if cwd else None,
        env=_safe_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        close_fds=True,
    )
    started = time.monotonic()
    captured: list[str] = []
    try:
        while True:
            if cancel():
                proc.terminate()
                try:
                    proc.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)
                raise BuildCancelled("vocoder preparation canceled")
            if time.monotonic() - started > timeout:
                proc.kill()
                proc.wait(timeout=3)
                raise BuildError(f"command timed out after {timeout}s: {args[0]}")

            if proc.stdout is not None:
                ready, _, _ = select.select([proc.stdout], [], [], 0.5)
                if ready:
                    line = proc.stdout.readline()
                    if line:
                        line = line.rstrip("\r\n")
                        captured.append(line)
                        log(line)
            rc = proc.poll()
            if rc is not None:
                if proc.stdout is not None:
                    rest = proc.stdout.read()
                    if rest:
                        _emit_lines(rest, log)
                        captured.extend(rest.splitlines())
                return subprocess.CompletedProcess(args, rc, "\n".join(captured), "")
    finally:
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass


def _compiler_identity() -> str:
    gxx = shutil.which("g++")
    if not gxx:
        raise BuildError("g++ is not installed")
    p = subprocess.run(
        [gxx, "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=5, check=False, env=_safe_env(),
    )
    line = (p.stdout or "").splitlines()[0].strip() if p.stdout else "unknown"
    return line[:240]


def _cache_identity() -> dict:
    if not ADAPTER_SOURCE.is_file():
        raise BuildError(f"YWD vocoder adapter source is missing: {ADAPTER_SOURCE}")
    return {
        "schema": BUILD_SCHEMA,
        "recipe": vocoder_manager.BACKEND_RECIPE,
        "recipe_version": vocoder_manager.BACKEND_RECIPE_VERSION,
        "protocol_version": vocoder_manager.PROTOCOL_VERSION,
        "mbelib_source": vocoder_manager.APPROVED_SOURCE,
        "mbelib_commit": vocoder_manager.APPROVED_MBELIB_COMMIT,
        "adapter_sha256": _sha256(ADAPTER_SOURCE),
        "architecture": platform.machine().strip().lower() or "unknown",
        "compiler": _compiler_identity(),
        "flags": "-O2 -DNDEBUG -std=c++17",
    }


def cache_key(identity: dict | None = None) -> str:
    doc = identity or _cache_identity()
    encoded = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_head(path: Path) -> str:
    try:
        p = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=5, check=False, env=_safe_env(),
        )
        return (p.stdout or "").strip() if p.returncode == 0 else ""
    except Exception:
        return ""


def ensure_source(*, job_id: str, log: Callable[[str], None], cancel: Callable[[], bool]) -> Path:
    SOURCE_CACHE.mkdir(parents=True, exist_ok=True)
    commit = vocoder_manager.APPROVED_MBELIB_COMMIT
    target = SOURCE_CACHE / f"mbelib-{commit[:12]}"
    if target.is_dir() and _source_head(target) == commit:
        log(f"Source cache hit: mbelib {commit[:12]}")
        return target
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)

    tmp = SOURCE_CACHE / f".mbelib-{job_id}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        commands = [
            (["git", "init", "-q", str(tmp)], None, 30),
            (["git", "-C", str(tmp), "remote", "add", "origin", vocoder_manager.APPROVED_SOURCE], None, 20),
            (["git", "-C", str(tmp), "fetch", "--depth", "1", "origin", commit], None, 180),
            (["git", "-C", str(tmp), "checkout", "-q", "--detach", "FETCH_HEAD"], None, 30),
        ]
        for args, cwd, timeout in commands:
            p = run_logged(args, cwd=cwd, timeout=timeout, log=log, cancel=cancel)
            if p.returncode != 0:
                raise BuildError(f"source command failed ({p.returncode}): {args[0]}")
        head = _source_head(tmp)
        if head != commit:
            raise BuildError(f"mbelib source verification failed: expected {commit}, got {head or 'unknown'}")
        os.replace(tmp, target)
        log(f"Pinned mbelib source verified: {commit}")
        return target
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def validate_candidate(binary: Path) -> dict:
    if not binary.is_file():
        raise BuildError("staged vocoder candidate is missing")
    p = subprocess.run(
        [str(binary), "--self-test"], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=20, check=False, env=_safe_env(),
    )
    raw = (p.stdout or "").strip()
    if p.returncode != 0:
        raise BuildError(f"candidate self-test failed ({p.returncode}): {raw[-500:]}")
    try:
        doc = json.loads(raw.splitlines()[-1])
    except Exception as exc:
        raise BuildError(f"candidate self-test did not return JSON: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("ok") is not True:
        raise BuildError("candidate self-test did not report success")
    if int(doc.get("protocol") or 0) != vocoder_manager.PROTOCOL_VERSION:
        raise BuildError("candidate Protocol version does not match YWD core")
    if int(doc.get("frames") or 0) != 10 or int(doc.get("pcm_bytes") or 0) != 3200:
        raise BuildError("candidate decode sanity output is invalid")
    return doc


def _candidate_cache_valid(path: Path, identity: dict, key: str) -> dict | None:
    binary = path / "ywd-vocoder-mbelib"
    provenance = path / "provenance.json"
    try:
        doc = json.loads(provenance.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(doc, dict) or doc.get("cache_key") != key or doc.get("identity") != identity:
        return None
    try:
        if doc.get("binary_sha256") != _sha256(binary):
            return None
        test = validate_candidate(binary)
    except Exception:
        return None
    return {"binary": binary, "provenance": doc, "self_test": test}


def _prune_candidates(keep_key: str) -> None:
    try:
        rows = [p for p in CANDIDATE_CACHE.iterdir() if p.is_dir() and p.name != keep_key]
    except Exception:
        return
    rows.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    for path in rows[max(0, MAX_CANDIDATES - 1):]:
        shutil.rmtree(path, ignore_errors=True)


def prepared_status() -> dict | None:
    try:
        doc = json.loads(PREPARED.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(doc, dict):
        return None
    binary = Path(str(doc.get("binary") or ""))
    if not binary.is_file():
        return None
    try:
        current = _cache_identity()
    except Exception:
        return None
    if doc.get("identity") != current or doc.get("cache_key") != cache_key(current):
        return None
    try:
        if doc.get("binary_sha256") != _sha256(binary):
            return None
    except Exception:
        return None
    return {
        "ready": True,
        "cache_key": str(doc.get("cache_key") or "")[:64],
        "binary_sha256": str(doc.get("binary_sha256") or "")[:64],
        "prepared_at": doc.get("prepared_at"),
        "cached": bool(doc.get("cached")),
        "mbelib_commit": str((doc.get("identity") or {}).get("mbelib_commit") or ""),
        "protocol_version": (doc.get("identity") or {}).get("protocol_version"),
        "architecture": str((doc.get("identity") or {}).get("architecture") or ""),
    }


def prepare_candidate(
    *,
    job_id: str,
    job_dir: Path,
    log: Callable[[str], None],
    progress: Callable[[str, int, str], None],
    cancel: Callable[[], bool],
) -> dict:
    identity = _cache_identity()
    key = cache_key(identity)
    CANDIDATE_CACHE.mkdir(parents=True, exist_ok=True)
    cache_dir = CANDIDATE_CACHE / key

    progress("downloading", 25, "Checking approved mbelib source and build cache")
    source = ensure_source(job_id=job_id, log=log, cancel=cancel)
    if cancel():
        raise BuildCancelled("vocoder preparation canceled")

    cached = _candidate_cache_valid(cache_dir, identity, key) if cache_dir.is_dir() else None
    if cached:
        log(f"Verified candidate cache hit: {key[:16]}")
        report = {
            "schema": BUILD_SCHEMA,
            "job_id": job_id,
            "cache_key": key,
            "cached": True,
            "binary": str(cached["binary"]),
            "binary_sha256": cached["provenance"]["binary_sha256"],
            "identity": identity,
            "self_test": cached["self_test"],
            "prepared_at": _now(),
        }
        _atomic_json(PREPARED, report)
        _atomic_json(job_dir / "prepare.json", report)
        _prune_candidates(key)
        return report

    work = job_dir / "work"
    build = work / "mbelib-build"
    staged = job_dir / "staged"
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(staged, ignore_errors=True)
    build.mkdir(parents=True, exist_ok=True)
    staged.mkdir(parents=True, exist_ok=True)

    progress("building", 42, "Configuring pinned mbelib Release build")
    p = run_logged(
        ["cmake", "-S", str(source), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release", "-DDISABLE_TEST=ON"],
        cwd=job_dir, timeout=180, log=log, cancel=cancel,
    )
    if p.returncode != 0:
        raise BuildError("cmake configuration failed")

    progress("building", 55, "Building mbelib static library with one build job")
    p = run_logged(
        ["cmake", "--build", str(build), "--target", "mbe-static", "--", "-j1"],
        cwd=job_dir, timeout=1200, log=log, cancel=cancel,
    )
    if p.returncode != 0:
        raise BuildError("mbelib build failed")
    library = build / "libmbe.a"
    if not library.is_file():
        raise BuildError("mbelib build completed without libmbe.a")

    progress("building", 74, "Building YWD Vocoder Protocol v1 native adapter")
    binary = staged / "ywd-vocoder-mbelib"
    p = run_logged(
        [
            "g++", "-O2", "-DNDEBUG", "-std=c++17", "-Wall", "-Wextra",
            "-I", str(source), str(ADAPTER_SOURCE), str(library), "-lm", "-o", str(binary),
        ],
        cwd=job_dir, timeout=240, log=log, cancel=cancel,
    )
    if p.returncode != 0:
        raise BuildError("YWD vocoder adapter build failed")
    os.chmod(binary, 0o750)

    progress("staging", 86, "Running staged Protocol/decode self-test")
    test = validate_candidate(binary)
    log("Candidate self-test PASS: Protocol v1 · 10 frames · 3200 PCM bytes")
    binary_sha = _sha256(binary)

    temp_cache = CANDIDATE_CACHE / ("." + key + ".tmp")
    shutil.rmtree(temp_cache, ignore_errors=True)
    temp_cache.mkdir(parents=True, exist_ok=True)
    cached_binary = temp_cache / "ywd-vocoder-mbelib"
    shutil.copy2(binary, cached_binary)
    os.chmod(cached_binary, 0o750)
    provenance = {
        "schema": BUILD_SCHEMA,
        "cache_key": key,
        "identity": identity,
        "binary_sha256": binary_sha,
        "built_at": _now(),
        "self_test": test,
    }
    _atomic_json(temp_cache / "provenance.json", provenance)
    shutil.rmtree(cache_dir, ignore_errors=True)
    os.replace(temp_cache, cache_dir)

    report = {
        "schema": BUILD_SCHEMA,
        "job_id": job_id,
        "cache_key": key,
        "cached": False,
        "binary": str(cache_dir / "ywd-vocoder-mbelib"),
        "binary_sha256": binary_sha,
        "identity": identity,
        "self_test": test,
        "prepared_at": _now(),
    }
    _atomic_json(PREPARED, report)
    _atomic_json(job_dir / "prepare.json", report)
    _prune_candidates(key)
    return report


if __name__ == "__main__":
    print(json.dumps({"prepared": prepared_status(), "cache_key": cache_key()}, indent=2, sort_keys=True))
