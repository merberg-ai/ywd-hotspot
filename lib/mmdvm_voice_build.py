#!/usr/bin/env python3
"""Build/install the YWD passive DMR voice-frame tap for pinned MMDVM-Host.

The experimental compile is intentionally independent of MMDVM-Host startup.
Normal hotspot services may stay running while this low-priority build proceeds.
Interrupted builds are resumed only when the existing source tree is provably the
same pinned commit with the exact YWD patch already applied.
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
FALLBACK = BINARY.with_name(".MMDVM-Host.ywd-voice-fallback")
PATCH_API = 2
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

    reverse = probe([
        "git", "-C", SOURCE, "apply", "--reverse", "--recount",
        "--exclude=Log.cpp", "--check", PATCH,
    ])
    if reverse.returncode != 0:
        return False

    try:
        log_text = (SOURCE / "Log.cpp").read_text(encoding="utf-8")
    except Exception:
        return False
    if LOG_ADDITION.strip() not in log_text:
        return False

    diff_check = probe(["git", "-C", SOURCE, "diff", "--check"])
    return diff_check.returncode == 0


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
    ensure_checkout(repo_url, commit)
    if patched_source_ready(commit):
        print("YWD voice build: exact patched source tree found; resuming existing object build.", flush=True)
        return True

    print("YWD voice build: preparing a clean pinned source tree.", flush=True)
    reset_to_pinned(commit)
    run(["git", "-C", SOURCE, "apply", "--recount", "--exclude=Log.cpp", "--check", PATCH])
    run(["git", "-C", SOURCE, "apply", "--recount", "--exclude=Log.cpp", PATCH])
    patch_log_cpp()
    if not patched_source_ready(commit):
        raise RuntimeError("patched source verification failed after preparation")
    return False


def build_strict() -> dict:
    if os.geteuid() != 0:
        raise RuntimeError("MMDVM voice tap build must run as root")
    for command in ("git", "make"):
        if shutil.which(command) is None:
            raise RuntimeError(f"required build command is missing: {command}")

    pins = read_pins()
    ident = identity()
    resumed = prepare_source(pins["MMDVM_HOST_REPO"], pins["MMDVM_HOST_COMMIT"])
    run(["make", "-j1"], cwd=SOURCE)

    candidate = SOURCE / "MMDVM-Host"
    if not candidate.is_file() or candidate.stat().st_size < 100_000:
        raise RuntimeError("patched MMDVM-Host build did not produce a plausible binary")

    staged = BINARY.with_name(".MMDVM-Host.ywd-voice-new")
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate, staged)
    os.chmod(staged, 0o755)
    os.replace(staged, BINARY)

    doc = {
        **ident,
        "status": "installed",
        "binary_sha256": sha256(BINARY),
        "built_at": int(time.time()),
        "resumed": resumed,
        "source": str(SOURCE),
        "topic": "ywd-mmdvm/voice",
    }
    write_marker(doc)
    return doc


def ensure() -> int:
    state = current_status()
    if state["installed"]:
        if state["active"]:
            print("YWD MMDVM DMR voice tap is installed and active.", flush=True)
        else:
            print("YWD MMDVM DMR voice tap is installed; run 'activate' for a guarded service restart.", flush=True)
        return 0

    if BINARY.is_file():
        shutil.copy2(BINARY, FALLBACK)
        os.chmod(FALLBACK, 0o755)

    print("YWD MMDVM DMR voice tap needs build; normal hotspot services may remain online.", flush=True)
    try:
        doc = build_strict()
        print(
            f"YWD MMDVM DMR voice tap built/installed: {doc['upstream_commit'][:12]} "
            f"patch={doc['patch_sha256'][:12]} resumed={doc['resumed']}",
            flush=True,
        )
        print("Activation is pending; use mmdvm_voice_build.py activate when ready.", flush=True)
        return 0
    except Exception as exc:
        print(f"WARNING: DMR voice tap build failed: {exc}", file=sys.stderr, flush=True)
        # Until the final compile succeeds, the live binary path is untouched.
        # If a previous attempt had already replaced it, restore the saved copy.
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


def activate() -> int:
    state = current_status()
    if not state["installed"]:
        print("Voice tap binary is not installed yet; run 'ensure' first.", file=sys.stderr)
        return 1
    if state["active"]:
        print("YWD MMDVM DMR voice tap is already active.")
        if FALLBACK.exists():
            FALLBACK.unlink()
        return 0

    mmdvm_was_active = service_active("ywd-mmdvmhost.service")
    gateway_was_active = service_active("ywd-dmrgateway.service")
    if not mmdvm_was_active:
        print("Patched binary is installed, but MMDVM-Host is intentionally stopped; activation will occur on its next start.")
        return 0

    print("Activating patched MMDVM-Host with guarded RF service restart...", flush=True)
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
            print("WARNING: DMRGateway did not return active after voice-tap activation.", file=sys.stderr)
            return 1

    marker = read_marker()
    marker.update({"status": "active", "activated_at": int(time.time()), "binary_sha256": sha256(BINARY)})
    write_marker(marker)
    if FALLBACK.exists():
        FALLBACK.unlink()
    print("YWD MMDVM DMR voice tap activation succeeded.", flush=True)
    return 0


def show_status() -> int:
    state = current_status()
    marker = state.pop("marker")
    print(json.dumps({
        **state,
        "marker_status": marker.get("status"),
        "topic": marker.get("topic"),
        "resumed": marker.get("resumed"),
    }, indent=2, sort_keys=True))
    return 0 if state["installed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/verify the YWD passive MMDVM DMR voice tap")
    parser.add_argument("command", nargs="?", choices=("ensure", "build", "activate", "status"), default="ensure")
    args = parser.parse_args()
    if args.command == "status":
        return show_status()
    if args.command == "activate":
        return activate()
    if args.command == "build":
        return ensure()
    return ensure()


if __name__ == "__main__":
    raise SystemExit(main())
