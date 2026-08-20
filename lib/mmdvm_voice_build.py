#!/usr/bin/env python3
"""Build/install/verify the canonical YWD-patched MMDVM-Host.

The YWD patch publishes passive DMR voice bursts to the dedicated loopback MQTT
voice topic while MMDVM-Host remains the sole modem owner.  This module keeps
its original guarded activation/fallback behavior for live systems, and also
provides a strict ``canonical`` command for OS images and fresh/full installs:
that command succeeds only when the installed binary is positively identified
as the exact pinned upstream commit plus the exact pinned YWD patch.

Expensive builds can be cached in YWD_RUNTIME_BUILD_CACHE.  Cache identity is
conservative: upstream commit, patch API/hash, target architecture, compiler
identity, relevant build flag environment, and cache schema all participate in
the cache key.
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
MARKER = Path(os.environ.get("YWD_MMDVM_VOICE_MARKER", "/var/lib/ywd-hotspot/mmdvm-voice-tap.json"))
PROVENANCE = Path(os.environ.get("YWD_MMDVM_BUILD_PROVENANCE", "/etc/ywd-hotspot/mmdvm-build.json"))
FALLBACK = BINARY.with_name(".MMDVM-Host.ywd-voice-fallback")
CACHE_ROOT = Path(os.environ.get("YWD_RUNTIME_BUILD_CACHE", "/var/cache/ywd-hotspot/runtime-build"))
CACHE_SCHEMA = 1
EXPECTED_TRACKED = {"DMRSlot.cpp", "DMRSlot.h", "Log.cpp", "Log.h"}

LOG_NEEDLE = '''void WriteJSON(const std::string& topLevel, nlohmann::json& json)\n{\n\tif (m_mqtt != nullptr) {\n\t\tnlohmann::json top;\n\n\t\ttop[topLevel] = json;\n\n\t\tm_mqtt->publish("json", top.dump());\n\t}\n}\n'''
LOG_ADDITION = '''\nvoid WriteJSONToTopic(const std::string& topic, const std::string& topLevel, nlohmann::json& json)\n{\n\tif (m_mqtt != nullptr) {\n\t\tnlohmann::json top;\n\n\t\ttop[topLevel] = json;\n\n\t\tm_mqtt->publish(topic.c_str(), top.dump());\n\t}\n}\n'''


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


def probe(argv, *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(x) for x in argv],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )


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
    patch_rel = out.get("MMDVM_YWD_PATCH", "lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch")
    patch_sha = out.get("MMDVM_YWD_PATCH_SHA256", "")
    patch_api = out.get("MMDVM_YWD_PATCH_API", "")
    if not repo or len(commit) != 40:
        raise RuntimeError("pins.env does not contain a valid MMDVM-Host repository/commit")
    if not patch_sha or len(patch_sha) != 64:
        raise RuntimeError("pins.env does not contain the canonical YWD MMDVM patch SHA-256")
    if not patch_api.isdigit():
        raise RuntimeError("pins.env does not contain the canonical YWD MMDVM patch API")
    out["MMDVM_YWD_PATCH"] = patch_rel
    return out


def patch_path() -> Path:
    pins = read_pins()
    p = APP / pins["MMDVM_YWD_PATCH"]
    if not p.is_file():
        raise RuntimeError(f"YWD MMDVM patch is missing: {p}")
    actual = sha256(p)
    expected = pins["MMDVM_YWD_PATCH_SHA256"].lower()
    if actual != expected:
        raise RuntimeError(f"YWD MMDVM patch hash mismatch: expected {expected}, got {actual}")
    return p


def read_marker() -> dict:
    try:
        value = json.loads(MARKER.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _atomic_json(path: Path, doc: dict, mode: int = 0o644) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except OSError:
        if path == MARKER:
            raise


def write_marker(doc: dict) -> None:
    _atomic_json(MARKER, doc)
    # Keep a stable appliance-level provenance record in addition to the
    # historical voice-tap marker consumed by the RX path.
    try:
        _atomic_json(PROVENANCE, doc)
    except OSError:
        pass


def identity() -> dict[str, str | int]:
    pins = read_pins()
    patch = patch_path()
    return {
        "api": int(pins["MMDVM_YWD_PATCH_API"]),
        "upstream_commit": pins["MMDVM_HOST_COMMIT"],
        "patch_name": patch.name,
        "patch_sha256": sha256(patch),
    }


def target_architecture() -> str:
    p = probe(["dpkg", "--print-architecture"])
    value = (p.stdout or "").strip() if p.returncode == 0 else ""
    return value or platform.machine() or "unknown"


def compiler_identity() -> str:
    p = probe(["g++", "--version"])
    if p.returncode != 0:
        raise RuntimeError("g++ is required to build/identify canonical MMDVM-Host")
    return ((p.stdout or "").splitlines() or ["unknown"])[0].strip()


def build_flags_identity() -> dict[str, str]:
    return {name: os.environ.get(name, "") for name in ("CPPFLAGS", "CXXFLAGS", "LDFLAGS")}


def build_jobs() -> int:
    raw = os.environ.get("YWD_BUILD_JOBS", "1").strip()
    try:
        value = int(raw)
    except Exception:
        value = 1
    return max(1, min(value, 4))


def cache_signature() -> dict:
    ident = identity()
    return {
        "cache_schema": CACHE_SCHEMA,
        "component": "mmdvm-host-ywd",
        "upstream_commit": ident["upstream_commit"],
        "patch_api": ident["api"],
        "patch_sha256": ident["patch_sha256"],
        "architecture": target_architecture(),
        "compiler": compiler_identity(),
        "flags": build_flags_identity(),
    }


def cache_key(signature: dict | None = None) -> str:
    signature = signature or cache_signature()
    packed = json.dumps(signature, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()


def cache_dir(signature: dict | None = None) -> Path:
    signature = signature or cache_signature()
    return CACHE_ROOT / "mmdvm-host" / cache_key(signature)


def plausible_binary(path: Path, architecture: str) -> bool:
    if not path.is_file() or path.stat().st_size < 100_000:
        return False
    file_cmd = shutil.which("file")
    if file_cmd:
        p = probe([file_cmd, "-b", path])
        desc = (p.stdout or "")
        if architecture == "armhf" and "ARM" not in desc:
            return False
    return True


def load_cache() -> dict | None:
    if os.environ.get("YWD_RUNTIME_CACHE_BYPASS", "0") == "1":
        print("[CACHE BYPASS] MMDVM-Host requested", flush=True)
        return None
    signature = cache_signature()
    entry = cache_dir(signature)
    binary = entry / "MMDVM-Host"
    manifest = entry / "manifest.json"
    try:
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        if doc.get("signature") != signature:
            return None
        expected_sha = str(doc.get("binary_sha256") or "")
        if not expected_sha or sha256(binary) != expected_sha:
            return None
        if not plausible_binary(binary, str(signature["architecture"])):
            return None
    except Exception:
        return None

    BINARY.parent.mkdir(parents=True, exist_ok=True)
    staged = BINARY.with_name(".MMDVM-Host.ywd-cache-new")
    shutil.copy2(binary, staged)
    os.chmod(staged, 0o755)
    os.replace(staged, BINARY)
    result = {
        **identity(),
        "status": "installed",
        "binary_sha256": expected_sha,
        "built_at": doc.get("built_at"),
        "installed_at": int(time.time()),
        "cached": True,
        "cache_key": cache_key(signature),
        "build_signature": signature,
        "topic": "ywd-mmdvm/voice",
    }
    write_marker(result)
    print(f"[CACHE HIT] MMDVM-Host {result['cache_key'][:12]}", flush=True)
    return result


def save_cache(binary: Path, built_at: int) -> dict:
    signature = cache_signature()
    entry = cache_dir(signature)
    entry.mkdir(parents=True, exist_ok=True)
    cached_binary = entry / "MMDVM-Host"
    tmp_binary = entry / ".MMDVM-Host.tmp"
    shutil.copy2(binary, tmp_binary)
    os.chmod(tmp_binary, 0o755)
    os.replace(tmp_binary, cached_binary)
    digest = sha256(cached_binary)
    doc = {
        "signature": signature,
        "binary_sha256": digest,
        "built_at": built_at,
    }
    _atomic_json(entry / "manifest.json", doc)
    (entry / "SHA256").write_text(digest + "  MMDVM-Host\n", encoding="utf-8")
    os.chmod(entry / "SHA256", 0o644)
    print(f"[CACHE SAVE] MMDVM-Host {cache_key(signature)[:12]}", flush=True)
    return {"cache_key": cache_key(signature), "build_signature": signature, "binary_sha256": digest}


def service_active(name: str) -> bool:
    return probe(["systemctl", "is-active", "--quiet", name]).returncode == 0


def running_binary_sha() -> str | None:
    p = probe(["systemctl", "show", "-p", "MainPID", "--value", "ywd-mmdvmhost.service"])
    try:
        pid = int((p.stdout or "0").strip())
    except Exception:
        pid = 0
    if pid <= 0:
        return None
    try:
        return sha256(Path(f"/proc/{pid}/exe"))
    except Exception:
        return None


def current_status() -> dict:
    ident = identity()
    marker = read_marker()
    binary_sha = sha256(BINARY) if BINARY.is_file() else None
    running_sha = running_binary_sha()
    marker_ok = bool(
        binary_sha
        and marker.get("api") == ident["api"]
        and marker.get("upstream_commit") == ident["upstream_commit"]
        and marker.get("patch_sha256") == ident["patch_sha256"]
        and marker.get("binary_sha256") == binary_sha
        and marker.get("status") in {"installed", "active"}
    )
    active = bool(marker_ok and running_sha and running_sha == binary_sha)
    return {
        **ident,
        "installed": marker_ok,
        "active": active,
        "binary_sha256": binary_sha,
        "running_binary_sha256": running_sha,
        "marker": marker,
    }


def patched_source_ready(commit: str) -> bool:
    patch = patch_path()
    if not (SOURCE / ".git").is_dir():
        return False
    head = probe(["git", "-C", SOURCE, "rev-parse", "HEAD"])
    if head.returncode != 0 or (head.stdout or "").strip() != commit:
        return False
    changed = probe(["git", "-C", SOURCE, "diff", "--name-only"])
    if changed.returncode != 0:
        return False
    names = {line.strip() for line in (changed.stdout or "").splitlines() if line.strip()}
    if names != EXPECTED_TRACKED:
        return False
    reverse = probe(["git", "-C", SOURCE, "apply", "--reverse", "--recount", "--exclude=Log.cpp", "--check", patch])
    if reverse.returncode != 0:
        return False
    try:
        log_text = (SOURCE / "Log.cpp").read_text(encoding="utf-8")
    except Exception:
        return False
    if LOG_ADDITION.strip() not in log_text:
        return False
    return probe(["git", "-C", SOURCE, "diff", "--check"]).returncode == 0


def ensure_checkout(repo_url: str, commit: str) -> None:
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    if not (SOURCE / ".git").is_dir():
        if SOURCE.exists():
            shutil.rmtree(SOURCE)
        run(["git", "clone", repo_url, SOURCE])
    have = probe(["git", "-C", SOURCE, "cat-file", "-e", f"{commit}^{{commit}}"])
    if have.returncode != 0:
        run(["git", "-C", SOURCE, "fetch", "origin", commit])


def reset_to_pinned(commit: str) -> None:
    run(["git", "-C", SOURCE, "reset", "--hard"], check=False)
    run(["git", "-C", SOURCE, "clean", "-fdx"], check=False)
    run(["git", "-C", SOURCE, "checkout", "--detach", commit])
    run(["git", "-C", SOURCE, "reset", "--hard", commit])
    run(["git", "-C", SOURCE, "clean", "-fdx"])


def patch_log_cpp() -> None:
    path = SOURCE / "Log.cpp"
    text = path.read_text(encoding="utf-8")
    if text.count(LOG_NEEDLE) != 1:
        raise RuntimeError("pinned Log.cpp WriteJSON anchor did not match exactly once")
    if "void WriteJSONToTopic(" in text:
        raise RuntimeError("pinned Log.cpp unexpectedly already contains WriteJSONToTopic")
    path.write_text(text.replace(LOG_NEEDLE, LOG_NEEDLE + LOG_ADDITION, 1), encoding="utf-8")


def prepare_source(repo_url: str, commit: str) -> bool:
    patch = patch_path()
    ensure_checkout(repo_url, commit)
    if patched_source_ready(commit):
        print("YWD MMDVM build: exact patched source tree found; resuming existing object build.", flush=True)
        return True
    print("YWD MMDVM build: preparing clean pinned source plus canonical YWD patch.", flush=True)
    reset_to_pinned(commit)
    run(["git", "-C", SOURCE, "apply", "--recount", "--exclude=Log.cpp", "--check", patch])
    run(["git", "-C", SOURCE, "apply", "--recount", "--exclude=Log.cpp", patch])
    patch_log_cpp()
    if not patched_source_ready(commit):
        raise RuntimeError("patched MMDVM source verification failed after preparation")
    return False


def build_strict() -> dict:
    if os.geteuid() != 0:
        raise RuntimeError("canonical MMDVM build must run as root")
    for command in ("git", "make", "g++"):
        if shutil.which(command) is None:
            raise RuntimeError(f"required build command is missing: {command}")

    cached = load_cache()
    if cached is not None:
        return cached

    pins = read_pins()
    ident = identity()
    signature = cache_signature()
    print(f"[CACHE MISS] MMDVM-Host {cache_key(signature)[:12]} - compiling YWD-patched binary", flush=True)
    resumed = prepare_source(pins["MMDVM_HOST_REPO"], pins["MMDVM_HOST_COMMIT"])
    run(["make", f"-j{build_jobs()}"], cwd=SOURCE)
    candidate = SOURCE / "MMDVM-Host"
    if not plausible_binary(candidate, str(signature["architecture"])):
        raise RuntimeError("patched MMDVM-Host build did not produce a plausible target binary")

    staged = BINARY.with_name(".MMDVM-Host.ywd-voice-new")
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate, staged)
    os.chmod(staged, 0o755)
    os.replace(staged, BINARY)
    built_at = int(time.time())
    cache_doc = save_cache(BINARY, built_at)
    doc = {
        **ident,
        "status": "installed",
        "binary_sha256": sha256(BINARY),
        "built_at": built_at,
        "resumed": resumed,
        "source": str(SOURCE),
        "topic": "ywd-mmdvm/voice",
        "cached": False,
        **cache_doc,
    }
    write_marker(doc)
    return doc


def ensure() -> int:
    state = current_status()
    if state["installed"]:
        if state["active"]:
            print("YWD-patched MMDVM-Host is installed and active.", flush=True)
        else:
            print("YWD-patched MMDVM-Host is installed; activation occurs on its next service start or via 'activate'.", flush=True)
        return 0

    if BINARY.is_file():
        shutil.copy2(BINARY, FALLBACK)
        os.chmod(FALLBACK, 0o755)

    print("Canonical YWD-patched MMDVM-Host needs installation; live services may remain online during compilation.", flush=True)
    try:
        doc = build_strict()
        print(
            f"YWD-patched MMDVM-Host installed: {doc['upstream_commit'][:12]} "
            f"patch={doc['patch_sha256'][:12]} cache={'hit' if doc.get('cached') else 'miss'}",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(f"WARNING: canonical YWD MMDVM build failed: {exc}", file=sys.stderr, flush=True)
        if FALLBACK.exists():
            try:
                if not BINARY.exists() or read_marker().get("status") in {"installed", "active"}:
                    os.replace(FALLBACK, BINARY)
                write_marker({
                    **identity(),
                    "status": "failed-fallback",
                    "binary_sha256": sha256(BINARY) if BINARY.exists() else None,
                    "failed_at": int(time.time()),
                    "error": str(exc)[:500],
                })
                print("Known-good MMDVM-Host binary retained/restored.", file=sys.stderr, flush=True)
                return 0
            except Exception as restore_exc:
                print(f"ERROR: could not preserve fallback MMDVM-Host binary: {restore_exc}", file=sys.stderr, flush=True)
        return 1


def canonical() -> int:
    rc = ensure()
    state = current_status()
    if rc != 0 or not state["installed"]:
        print("ERROR: canonical install requires the exact YWD-patched MMDVM-Host; fallback/stock binary is not acceptable.", file=sys.stderr)
        return 1
    marker = state["marker"]
    print(
        f"[OK] Canonical MMDVM verified: upstream={state['upstream_commit'][:12]} "
        f"patch={state['patch_sha256'][:12]} binary={str(state['binary_sha256'])[:12]}",
        flush=True,
    )
    return 0


def activate() -> int:
    state = current_status()
    if not state["installed"]:
        print("YWD-patched MMDVM-Host is not installed yet; run 'ensure' first.", file=sys.stderr)
        return 1
    if state["active"]:
        print("YWD-patched MMDVM-Host is already active.")
        if FALLBACK.exists():
            FALLBACK.unlink()
        return 0

    mmdvm_was_active = service_active("ywd-mmdvmhost.service")
    gateway_was_active = service_active("ywd-dmrgateway.service")
    if not mmdvm_was_active:
        print("Patched binary is installed, but MMDVM-Host is intentionally stopped; activation will occur on its next start.")
        return 0

    print("Activating YWD-patched MMDVM-Host with guarded RF service restart...", flush=True)
    if gateway_was_active:
        run(["systemctl", "stop", "ywd-dmrgateway.service"], check=False)
    run(["systemctl", "restart", "ywd-mmdvmhost.service"], check=False)
    time.sleep(3)

    if not service_active("ywd-mmdvmhost.service") or not current_status()["active"]:
        print("Patched MMDVM-Host did not come up cleanly; restoring fallback.", file=sys.stderr, flush=True)
        if FALLBACK.exists():
            os.replace(FALLBACK, BINARY)
            run(["systemctl", "restart", "ywd-mmdvmhost.service"], check=False)
            time.sleep(3)
        if gateway_was_active:
            run(["systemctl", "start", "ywd-dmrgateway.service"], check=False)
        write_marker({
            **identity(),
            "status": "failed-activation",
            "binary_sha256": sha256(BINARY) if BINARY.exists() else None,
            "failed_at": int(time.time()),
        })
        return 1

    if gateway_was_active:
        run(["systemctl", "start", "ywd-dmrgateway.service"], check=False)
        time.sleep(2)
        if not service_active("ywd-dmrgateway.service"):
            print("WARNING: DMRGateway did not return active after MMDVM activation.", file=sys.stderr)
            return 1

    marker = read_marker()
    marker.update({"status": "active", "activated_at": int(time.time()), "binary_sha256": sha256(BINARY)})
    write_marker(marker)
    if FALLBACK.exists():
        FALLBACK.unlink()
    print("YWD-patched MMDVM-Host activation succeeded.", flush=True)
    return 0


def show_status() -> int:
    state = current_status()
    marker = state.pop("marker")
    print(json.dumps({
        **state,
        "marker_status": marker.get("status"),
        "topic": marker.get("topic"),
        "cached": marker.get("cached"),
        "cache_key": marker.get("cache_key"),
        "build_signature": marker.get("build_signature"),
    }, indent=2, sort_keys=True))
    return 0 if state["installed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/verify the canonical YWD-patched MMDVM-Host")
    parser.add_argument("command", nargs="?", choices=("ensure", "build", "canonical", "activate", "status"), default="ensure")
    args = parser.parse_args()
    if args.command == "status":
        return show_status()
    if args.command == "activate":
        return activate()
    if args.command == "canonical":
        return canonical()
    return ensure()


if __name__ == "__main__":
    raise SystemExit(main())
