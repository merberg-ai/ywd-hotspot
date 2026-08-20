#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "os" / "local"
EXPORTS = LOCAL / "exports"
# Keep the historical path used by BUILD.sh so an exported key is the exact
# key whose public half pi-gen installs for the ywd login account.
PRIVATE_KEY = LOCAL / "ywd-os-dev_ed25519"
PUBLIC_KEY = Path(str(PRIVATE_KEY) + ".pub")


def _mkdir_private(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def _run(args: list[str], *, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def ensure_key() -> None:
    if not shutil.which("ssh-keygen"):
        raise RuntimeError("ssh-keygen is unavailable; install openssh-client")
    _mkdir_private(LOCAL)

    if PRIVATE_KEY.exists() or PUBLIC_KEY.exists():
        if not PRIVATE_KEY.is_file() or PRIVATE_KEY.is_symlink():
            raise RuntimeError(f"SSH private key path is invalid: {PRIVATE_KEY}")
        if not PUBLIC_KEY.is_file() or PUBLIC_KEY.is_symlink():
            raise RuntimeError(f"SSH public key path is invalid: {PUBLIC_KEY}")
    else:
        proc = _run([
            "ssh-keygen", "-q", "-t", "ed25519", "-N", "",
            "-C", "ywd-hotspot-os-builder-login", "-f", str(PRIVATE_KEY),
        ])
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or "ssh-keygen failed").strip()[:500])

    os.chmod(PRIVATE_KEY, 0o600)
    os.chmod(PUBLIC_KEY, 0o644)

    public_line = PUBLIC_KEY.read_text(encoding="utf-8", errors="strict").strip()
    if not public_line.startswith("ssh-ed25519 "):
        raise RuntimeError("builder SSH public key is not a valid Ed25519 OpenSSH key")


def fingerprint() -> str:
    ensure_key()
    proc = _run(["ssh-keygen", "-lf", str(PUBLIC_KEY)], timeout=5)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "could not calculate SSH key fingerprint").strip()[:500])
    return (proc.stdout or "").strip()


def _image_name() -> str:
    try:
        import sys
        builder_dir = Path(__file__).resolve().parent
        if str(builder_dir) not in sys.path:
            sys.path.insert(0, str(builder_dir))
        from profile_model import compile_profile, load_profile
        return str(compile_profile(load_profile())["image"]["image_name"] or "ywd-hotspot-os")
    except Exception:
        return "ywd-hotspot-os"


def _tar_add_bytes(tf: tarfile.TarFile, name: str, data: bytes, mode: int, mtime: int) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    info.mode = mode
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = mtime
    tf.addfile(info, io.BytesIO(data))


def export_bundle() -> Path:
    ensure_key()
    _mkdir_private(EXPORTS)

    created = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = created.strftime("%Y%m%d-%H%M%S")
    image_name = _image_name()
    out = EXPORTS / f"{image_name}-ssh-client-login-{stamp}.tar.gz"
    fp = fingerprint()

    private = PRIVATE_KEY.read_bytes()
    public = PUBLIC_KEY.read_bytes()
    readme = (
        "YWD-Hotspot OS SSH CLIENT LOGIN KEY\n"
        f"Created: {created.isoformat().replace('+00:00', 'Z')}\n"
        f"Image profile: {image_name}\n"
        f"Fingerprint: {fp}\n\n"
        "THIS IS THE LOGIN KEY FOR THE ywd USER.\n"
        "The matching public key is baked into images built by this checkout.\n"
        "The private key lets you SSH/SFTP into the newly flashed hotspot.\n\n"
        "Linux / macOS / Windows OpenSSH:\n"
        "  chmod 600 ywd_hotspot_client_ed25519   # Unix-like systems\n"
        "  ssh -i ywd_hotspot_client_ed25519 ywd@ywd-hotspot.local\n\n"
        "PuTTY / PuTTYgen:\n"
        "  Import ywd_hotspot_client_ed25519 in PuTTYgen, then save it as a .ppk.\n"
        "  Configure PuTTY for user ywd and select that .ppk as the private key.\n\n"
        "IMPORTANT KEY DISTINCTION:\n"
        "  This is a CLIENT LOGIN key. It authenticates you to the hotspot.\n"
        "  SSH SERVER IDENTITY (ssh_host_*) keys only identify the server and do\n"
        "  not allow login. Server identity keys should remain unique per device;\n"
        "  export them from the YWD-Hotspot dashboard after first boot if you want\n"
        "  a recovery copy that preserves the server fingerprint.\n\n"
        "CONFIDENTIAL:\n"
        "  The private key is intentionally unencrypted for appliance/key-client\n"
        "  compatibility. Anyone who obtains it can authenticate as ywd while its\n"
        "  public key remains authorized. Store this archive like a password.\n"
    ).encode("utf-8")

    with tarfile.open(out, mode="w:gz") as tf:
        now = int(created.timestamp())
        _tar_add_bytes(tf, "README-SSH-CLIENT-LOGIN.txt", readme, 0o600, now)
        _tar_add_bytes(tf, "ywd_hotspot_client_ed25519", private, 0o600, now)
        _tar_add_bytes(tf, "ywd_hotspot_client_ed25519.pub", public, 0o644, now)

    os.chmod(out, 0o600)
    return out


def status() -> str:
    if not PRIVATE_KEY.exists() and not PUBLIC_KEY.exists():
        return "not generated"
    ensure_key()
    return f"configured | {fingerprint()} | private={PRIVATE_KEY}"


def main() -> int:
    ap = argparse.ArgumentParser(description="YWD-Hotspot OS builder SSH login key helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ensure")
    sub.add_parser("export")
    sub.add_parser("status")
    sub.add_parser("path")
    sub.add_parser("fingerprint")
    args = ap.parse_args()

    if args.cmd == "ensure":
        ensure_key()
        print(PRIVATE_KEY)
    elif args.cmd == "export":
        path = export_bundle()
        print("SSH LOGIN KEY BUNDLE EXPORTED")
        print(f"Archive:     {path}")
        print(f"Permissions: {oct(path.stat().st_mode & 0o777)[2:]}")
        print(f"Fingerprint: {fingerprint()}")
        print("The matching public key will be baked into the ywd account by BUILD.sh.")
        print("This is a client login key; server identity keys are exported after first boot.")
    elif args.cmd == "status":
        print(status())
    elif args.cmd == "path":
        ensure_key()
        print(PRIVATE_KEY)
    elif args.cmd == "fingerprint":
        print(fingerprint())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1)
