#!/usr/bin/env python3
"""Migrate canonical config/runtime metadata without changing secrets or RF policy."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import config_model

APP = Path(__file__).resolve().parent.parent
CFG = Path(os.environ.get("YWD_CONFIG", "/etc/ywd-hotspot/config.json"))
RUNTIME_STATE = Path(os.environ.get("YWD_MMDVM_RUNTIME_STATE", "/etc/ywd-hotspot/mmdvm-runtime.json"))
MMDVM_PROVENANCE = Path(os.environ.get("YWD_MMDVM_BUILD_PROVENANCE", "/etc/ywd-hotspot/mmdvm-build.json"))
VOICE_MARKER = Path(os.environ.get("YWD_MMDVM_VOICE_MARKER", "/var/lib/ywd-hotspot/mmdvm-voice-tap.json"))
MMDVM_BINARY = Path(os.environ.get("YWD_MMDVM_BINARY", "/usr/local/bin/MMDVM-Host"))
PINS = APP / "pins.env"


def read_json(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_pins() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        lines = PINS.read_text(encoding="utf-8").splitlines()
    except Exception:
        return out
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def atomic_json(path: Path, doc: dict, mode=0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, mode)
    try:
        import grp
        os.chown(tmp, 0, grp.getgrnam("ywd-hotspot").gr_gid)
    except Exception:
        pass
    os.replace(tmp, path)


def migrate_config() -> None:
    raw = json.loads(CFG.read_text())
    new = config_model.normalize(raw)
    tmp = CFG.with_suffix(".migrate.tmp")
    tmp.write_text(json.dumps(new, indent=2) + "\n")
    os.chmod(tmp, 0o640)
    try:
        import grp
        os.chown(tmp, 0, grp.getgrnam("ywd-hotspot").gr_gid)
    except Exception:
        pass
    os.replace(tmp, CFG)
    print(f"Migrated {CFG} to schema {config_model.SCHEMA}")


def migrate_mmdvm_runtime() -> None:
    """Adopt legacy 0.1.x radio binaries without rebuilding or switching them."""
    existing = read_json(RUNTIME_STATE)
    if str(existing.get("variant") or "") in {"ywd-extended", "upstream"}:
        print(f"MMDVM runtime metadata already present: {existing['variant']}")
        return

    pins = read_pins()
    expected_patch = str(pins.get("MMDVM_YWD_PATCH_SHA256") or "").lower()
    try:
        expected_api = int(pins.get("MMDVM_YWD_PATCH_API") or 0)
    except Exception:
        expected_api = 0
    expected_upstream = str(pins.get("MMDVM_HOST_COMMIT") or "")
    binary_sha = sha256(MMDVM_BINARY)

    evidence = read_json(MMDVM_PROVENANCE)
    source = "mmdvm-build.json"
    if not evidence:
        evidence = read_json(VOICE_MARKER)
        source = "mmdvm-voice-tap.json"

    variant = "upstream"
    capabilities: list[str] = []
    extension_api = None
    patch_sha = None

    evidence_binary = str(evidence.get("binary_sha256") or "")
    evidence_patch = str(evidence.get("patch_sha256") or "").lower()
    try:
        evidence_api = int(evidence.get("api") or evidence.get("extension_api") or 0)
    except Exception:
        evidence_api = 0
    evidence_upstream = str(evidence.get("upstream_commit") or "")

    extended_proven = bool(
        binary_sha
        and evidence_binary == binary_sha
        and expected_patch
        and evidence_patch == expected_patch
        and expected_api > 0
        and evidence_api == expected_api
        and expected_upstream
        and evidence_upstream == expected_upstream
    )
    if extended_proven:
        variant = "ywd-extended"
        extension_api = expected_api
        patch_sha = expected_patch
        capabilities = ["passive-dmr-voice", "plugin-rx-monitor"]

    doc = {
        "schema": 1,
        "variant": variant,
        "selected_at": int(time.time()),
        "upstream_commit": evidence_upstream or expected_upstream or None,
        "binary_sha256": binary_sha,
        "extension_api": extension_api,
        "patch_sha256": patch_sha,
        "capabilities": capabilities,
        "adopted_from_legacy": True,
        "adoption_evidence": source if extended_proven else "no exact YWD extension proof; conservatively classified as upstream",
    }
    atomic_json(RUNTIME_STATE, doc, 0o640)
    print(f"Adopted existing MMDVM runtime without rebuild: {variant}")


def main():
    if os.geteuid() != 0:
        raise SystemExit("root required")
    migrate_config()
    migrate_mmdvm_runtime()


if __name__ == "__main__":
    main()
