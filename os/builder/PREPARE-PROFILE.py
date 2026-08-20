#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from profile_model import PROFILE_PATH, compile_profile, load_profile, write_generated


def main() -> int:
    ap = argparse.ArgumentParser(description="Compile YWD-Hotspot OS builder profile")
    ap.add_argument("--profile", type=Path, default=PROFILE_PATH)
    ap.add_argument("--json", action="store_true", help="print sanitized summary as JSON")
    args = ap.parse_args()
    try:
        profile = load_profile(args.profile)
        compiled = compile_profile(profile)
        paths = write_generated(compiled)
        summary = json.loads(paths["summary"].read_text())
    except Exception as exc:
        print(f"[FAIL] Builder profile: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        state = "FULLY PRECONFIGURED" if summary["complete"] else "FIRST-BOOT WIZARD REQUIRED"
        print(f"[OK] Builder profile prepared: {state}")
        print(f"     callsign: {summary['callsign']}  hotspot ID: {summary['hotspot_id']}")
        print(f"     radio: {summary['radio_mode']}  Wi-Fi: {'preconfigured' if summary['wifi_preconfigured'] else 'setup AP on first boot'}")
        if summary["missing"]:
            print("     deferred: " + ", ".join(summary["missing"]))
        print(f"     generated: {paths['summary'].parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
