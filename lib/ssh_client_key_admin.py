#!/usr/bin/env python3
"""Fixed-user SSH client-key enrollment for YWD-Hotspot.

The appliance exposes exactly one managed remote-login account: ``ywd``.
Dashboard client-key enrollment therefore never accepts an arbitrary Linux
username, even if a crafted request tries to supply one.
"""
from __future__ import annotations

import json
import sys

import ssh_keys_admin

LOGIN_USER = "ywd"


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
    requested = str(payload.get("username") or LOGIN_USER).strip()
    if requested != LOGIN_USER:
        raise ValueError("SSH client login user is fixed to 'ywd'")

    out = ssh_keys_admin.create_client_key({"username": LOGIN_USER})
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:800]}, separators=(",", ":")))
        raise SystemExit(1)
