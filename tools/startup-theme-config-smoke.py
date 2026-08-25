#!/usr/bin/env python3
"""Smoke-test startup/loading animation configuration behavior."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("config_model", ROOT / "lib" / "config_model.py")
assert SPEC and SPEC.loader
config_model = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(config_model)

THEMES = {
    "rf_sweep",
    "radar_scan",
    "packet_burst",
    "digital_waterfall",
    "rf_orbit",
    "boot_telemetry",
    "signal_lock",
    "vfo_tuning",
    "dmr_frame",
}


def candidate(theme=None):
    cfg = config_model.defaults()
    cfg["station"]["callsign"] = "KJ6YWD"
    cfg["station"]["base_dmr_id"] = "3196104"
    cfg["station"]["essid"] = "01"
    if theme is not None:
        cfg["web"]["loading_animation"] = theme
    return cfg


def ok(name, cond):
    if not cond:
        raise AssertionError(name)
    print(f"[OK] {name}")


def main():
    default = config_model.normalize(candidate())
    ok("RF Sweep is the canonical default", default["web"]["loading_animation"] == "rf_sweep")

    for theme in sorted(THEMES):
        normalized = config_model.normalize(candidate(theme))
        ok(f"accepted theme {theme}", normalized["web"]["loading_animation"] == theme)
        public = config_model.public(normalized)
        ok(f"public config preserves {theme}", public["web"]["loading_animation"] == theme)

    try:
        config_model.normalize(candidate("not-a-real-theme"))
    except ValueError:
        print("[OK] invalid theme is rejected")
    else:
        raise AssertionError("invalid theme was accepted")

    cosmetic = config_model.classify_changes(["web.loading_animation"])
    ok("theme-only change does not require dashboard restart", cosmetic["dashboard"] is False)

    bind = config_model.classify_changes(["web.bind"])
    port = config_model.classify_changes(["web.port"])
    ok("dashboard bind change still requires restart", bind["dashboard"] is True)
    ok("dashboard port change still requires restart", port["dashboard"] is True)

    ok("theme-only change does not touch RF", cosmetic["rf"] is False)
    ok("theme-only change does not touch OLED", cosmetic["oled"] is False)

    print("\nStartup theme config smoke: PASS")


if __name__ == "__main__":
    main()
