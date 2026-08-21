#!/usr/bin/env python3
"""Generate auditable metadata/readme files for a public YWD-Hotspot image."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OS_DIR = ROOT / "os"
LOCAL = OS_DIR / "local"
DEPLOY = OS_DIR / "deploy"
GENERATED = LOCAL / "generated"
PINS = ROOT / "pins.env"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], text=True, stdout=subprocess.PIPE, check=True)
    return p.stdout.strip()


def pins() -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in PINS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def load_json(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def main() -> int:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    summary = load_json(GENERATED / "summary.json")
    runtime = load_json(LOCAL / "mmdvm-runtime.json")
    variant = str(runtime.get("variant") or "ywd-extended")
    p = pins()

    # The artifact generator is intentionally release-only and refuses any
    # personalized first-boot payload even if called independently.
    forbidden = []
    if summary.get("complete"):
        forbidden.append("complete hotspot setup")
    if summary.get("wifi_preconfigured"):
        forbidden.append("Wi-Fi")
    if summary.get("dashboard_password_preconfigured"):
        forbidden.append("dashboard credential")
    if summary.get("bm_api_key_preconfigured"):
        forbidden.append("BrandMeister API key")
    if summary.get("dashboard_backup_imported"):
        forbidden.append("imported settings")
    if summary.get("rf_autostart"):
        forbidden.append("RF autostart")
    if summary.get("callsign") not in {None, "", "NOCALL"}:
        forbidden.append("operator callsign")
    if forbidden:
        raise RuntimeError("refusing public release metadata for preconfigured image: " + ", ".join(forbidden))
    for name in ("provision.env", "factory-provision.json", "factory-restore.json"):
        if (GENERATED / name).exists():
            raise RuntimeError(f"refusing public release metadata; forbidden generated payload exists: {name}")

    image_name = str((summary.get("image") or {}).get("image_name") or "")
    candidates = sorted(DEPLOY.glob(f"*{image_name}*.img.xz"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError(f"no public image found in {DEPLOY} for image name {image_name!r}")
    image = candidates[0]
    digest = sha256(image)

    meta = {
        "schema": 1,
        "version": version,
        "release_kind": "prerelease",
        "factory_image": True,
        "preconfigured": False,
        "source": {
            "repository": "merberg-ai/ywd-hotspot",
            "branch": git("branch", "--show-current"),
            "commit": git("rev-parse", "HEAD"),
            "commit_date": git("show", "-s", "--format=%cI", "HEAD"),
        },
        "target": {
            "hardware": "Raspberry Pi Zero W / Zero WH",
            "architecture": "armhf",
            "base": "Raspberry Pi OS Lite / trixie",
        },
        "first_boot": {
            "wifi_preconfigured": False,
            "operator_identity_preconfigured": False,
            "dashboard_credential_preconfigured": False,
            "brandmeister_credentials_preconfigured": False,
            "settings_backup_imported": False,
            "rf_autostart": False,
            "ssh_enabled": False,
            "ssh_server_installed": True,
            "ssh_host_identity_preconfigured": False,
            "ssh_enablement": "authenticated dashboard / Settings / SSH Access",
            "setup_ap": "YWD-Hotspot-XXXX",
            "setup_ap_url": "http://10.42.0.1/",
            "hotspot_setup_url": "https://<LAN-IP>:8443/",
            "mdns_setup_url_optional": "https://ywd-hotspot.local:8443/",
        },
        "mmdvm": {
            "variant": variant,
            "upstream_commit": p.get("MMDVM_HOST_COMMIT"),
            "extension_api": int(p.get("MMDVM_YWD_PATCH_API", "0")) if variant == "ywd-extended" else None,
            "patch_sha256": p.get("MMDVM_YWD_PATCH_SHA256") if variant == "ywd-extended" else None,
            "capabilities": ["passive-dmr-voice", "plugin-rx-monitor"] if variant == "ywd-extended" else [],
        },
        "dmrgateway": {
            "upstream_commit": p.get("DMR_GATEWAY_COMMIT"),
        },
        "artifact": {
            "filename": image.name,
            "size_bytes": image.stat().st_size,
            "sha256": digest,
        },
        "generated_at_epoch": int(time.time()),
    }

    metadata_path = DEPLOY / "BUILD-METADATA.json"
    metadata_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    readme = f"""YWD-Hotspot {version} - Public Factory Image
============================================================

THIS IMAGE HAS NO OPERATOR PRECONFIGURATION.

It contains no Wi-Fi credentials, callsign, DMR ID, BrandMeister credentials,
API key, dashboard password, imported settings backup, or RF autostart state.
SSH is disabled, no builder authorized key is embedded, and no reusable SSH
server host identity is shipped in the image.

MMDVM runtime shipped in this image:
  {variant}

Image:
  {image.name}

SHA256:
  {digest}

First boot:
  1. Flash the .img.xz directly with Raspberry Pi Imager.
  2. Boot the Raspberry Pi Zero W/Zero WH with the MMDVM HAT installed.
  3. Join the temporary YWD-Hotspot-XXXX Wi-Fi network.
  4. Browse to http://10.42.0.1/ and configure your Wi-Fi.
  5. Reconnect your phone/computer to your normal network.
  6. The OLED shows the assigned LAN IP and a large six-digit setup code.
  7. Browse to https://<LAN-IP>:8443/ and complete setup.
     ywd-hotspot.local is only an optional mDNS convenience when supported.
  8. RF remains off unless you explicitly enable it during/after setup.

SSH after setup:
  - Factory state: disabled / port 22 closed.
  - Unlock dashboard controls and open Settings -> SSH Access.
  - Create/export a client login key for user ywd.
  - Enable SSH Access. YWD generates unique server host keys on that appliance.
  - SSH remains public-key-only; password authentication and root SSH are disabled.

Do not apply Raspberry Pi Imager OS customization settings over this appliance
image. YWD-Hotspot provides its own first-boot network and hotspot setup flow.
"""
    (DEPLOY / "README-FIRST.txt").write_text(readme, encoding="utf-8")

    print(f"BUILD-METADATA: {metadata_path}")
    print(f"README-FIRST:   {DEPLOY / 'README-FIRST.txt'}")
    print(f"Image SHA256:   {digest}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
