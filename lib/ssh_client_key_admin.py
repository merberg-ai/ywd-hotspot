#!/usr/bin/env python3
"""Validated SSH client-key enrollment for YWD-Hotspot."""
from __future__ import annotations

import json
import sys

import ssh_keys_admin


def _payload() -> dict:
    raw = sys.stdin.buffer.read(4096)
    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("invalid JSON payload") from exc
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    return payload


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action != "ssh-client-key-create":
        raise SystemExit("usage: ssh_client_key_admin.py ssh-client-key-create")
    payload = _payload()
    requested = str(payload.get("username") or ssh_keys_admin.suggested_login_user()).strip()
    out = ssh_keys_admin.create_client_key({"username": requested})
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:800]}, separators=(",", ":")))
        raise SystemExit(1)
