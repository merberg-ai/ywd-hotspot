#!/usr/bin/env python3
"""Builder-side MMDVM runtime variant preference.

The preference is local-only under os/local and therefore never becomes a
secret or operator configuration in the image. YWD Extended is the default and
recommended variant; Stock Upstream is the explicit opt-out.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "os" / "local"
STATE = LOCAL / "mmdvm-runtime.json"
ENV = LOCAL / "generated" / "mmdvm-runtime.env"
ALLOWED = {"ywd-extended", "upstream"}


def load() -> dict:
    try:
        doc = json.loads(STATE.read_text(encoding="utf-8"))
        variant = str(doc.get("variant") or "").strip().lower()
    except Exception:
        variant = ""
    if variant not in ALLOWED:
        variant = "ywd-extended"
    return {"schema": 1, "variant": variant}


def save(variant: str) -> None:
    variant = variant.strip().lower()
    if variant not in ALLOWED:
        raise ValueError("variant must be ywd-extended or upstream")
    LOCAL.mkdir(parents=True, exist_ok=True)
    os.chmod(LOCAL, 0o700)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"schema": 1, "variant": variant}, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, STATE)


def review(variant: str) -> str:
    if variant == "ywd-extended":
        return "\n".join([
            "MMDVM RUNTIME",
            "-------------",
            "Variant:                YWD Extended [recommended/default]",
            "Upstream source:        exact pinned MMDVM-Host commit",
            "YWD extension patch:    enabled / hash-verified",
            "Plugin capabilities:    passive DMR voice, RX Monitor, future compatible extensions",
        ])
    return "\n".join([
        "MMDVM RUNTIME",
        "-------------",
        "Variant:                Stock Upstream",
        "Upstream source:        exact pinned MMDVM-Host commit",
        "YWD extension patch:    disabled",
        "Plugin capabilities:    YWD MMDVM-extension-dependent plugins unavailable",
    ])


def write_env(variant: str) -> Path:
    ENV.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(ENV.parent, 0o700)
    tmp = ENV.with_suffix(".tmp")
    tmp.write_text(f"YWD_MMDVM_VARIANT={shlex.quote(variant)}\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, ENV)
    return ENV


def main() -> int:
    ap = argparse.ArgumentParser(description="YWD-Hotspot builder MMDVM runtime variant")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("review")
    sub.add_parser("reset")
    sub.add_parser("write-env")
    s = sub.add_parser("set")
    s.add_argument("variant", choices=sorted(ALLOWED))
    args = ap.parse_args()

    if args.cmd == "set":
        save(args.variant)
        print(args.variant)
        return 0
    if args.cmd == "reset":
        save("ywd-extended")
        print("ywd-extended")
        return 0

    variant = load()["variant"]
    if args.cmd == "status":
        print(variant)
    elif args.cmd == "review":
        print(review(variant))
    elif args.cmd == "write-env":
        print(write_env(variant))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=__import__('sys').stderr)
        raise SystemExit(1)
