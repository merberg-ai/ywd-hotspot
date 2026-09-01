#!/usr/bin/env python3
"""Read-only validation/projection for the current staged vocoder candidate."""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import vocoder_manager

STATE_DIR = Path("/var/lib/ywd-hotspot/vocoder")
PREPARED = STATE_DIR / "prepared.json"
CANDIDATE_ROOT = STATE_DIR / "build-cache" / "candidates"


def _read() -> dict:
    try:
        doc = json.loads(PREPARED.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(128 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def status() -> dict:
    doc = _read()
    if not doc:
        return {"available": False, "valid": False, "reason": "No prepared candidate yet."}
    try:
        binary = Path(str(doc.get("binary") or "")).resolve(strict=True)
        binary.relative_to(CANDIDATE_ROOT.resolve())
        if not binary.is_file() or binary.is_symlink():
            raise ValueError("candidate is not a regular managed file")
        expected_sha = str(doc.get("binary_sha256") or "").lower()
        actual_sha = _sha256(binary)
        if len(expected_sha) != 64 or actual_sha != expected_sha:
            raise ValueError("candidate SHA-256 no longer matches")
        identity = doc.get("identity") if isinstance(doc.get("identity"), dict) else {}
        expected = {
            "recipe": vocoder_manager.BACKEND_RECIPE,
            "recipe_version": vocoder_manager.BACKEND_RECIPE_VERSION,
            "protocol_version": vocoder_manager.PROTOCOL_VERSION,
            "mbelib_commit": vocoder_manager.APPROVED_MBELIB_COMMIT,
            "architecture": platform.machine().strip().lower() or "unknown",
        }
        for key, value in expected.items():
            if identity.get(key) != value:
                raise ValueError(f"candidate identity mismatch: {key}")
        test = doc.get("self_test") if isinstance(doc.get("self_test"), dict) else {}
        if test.get("ok") is not True or int(test.get("protocol") or 0) != vocoder_manager.PROTOCOL_VERSION:
            raise ValueError("candidate self-test metadata is not current")
        return {
            "available": True,
            "valid": True,
            "reason": "Prepared candidate matches the current YWD recipe/pin and staged self-test.",
            "binary_sha256": actual_sha,
            "cache_key": str(doc.get("cache_key") or "")[:80],
            "prepared_at": doc.get("prepared_at"),
            "cached": bool(doc.get("cached")),
            "self_test": {
                "ok": True,
                "protocol": test.get("protocol"),
                "frames": test.get("frames"),
                "pcm_bytes": test.get("pcm_bytes"),
                "mbelib_version": test.get("mbelib_version"),
            },
        }
    except Exception as exc:
        return {
            "available": True,
            "valid": False,
            "reason": str(exc)[:300],
            "prepared_at": doc.get("prepared_at"),
            "cache_key": str(doc.get("cache_key") or "")[:80],
        }


if __name__ == "__main__":
    print(json.dumps(status(), indent=2, sort_keys=True))
