#!/usr/bin/env python3
"""Source-only regression for RC4 terminal branding and TGIF setup parity."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def require(rel: str, *markers: str) -> None:
    data = text(rel)
    for marker in markers:
        assert marker in data, f"{rel}: missing marker {marker!r}"


def main() -> int:
    issue = text("lib/branding/issue")
    motd = text("lib/branding/motd")
    ui = text("bin/ywd-ui.sh")
    wordmark = issue.splitlines()[:7]
    assert len(wordmark) == 7 and all(line.strip() for line in wordmark)
    for line in wordmark:
        assert line in motd, f"motd missing wordmark line: {line}"
        assert line in ui, f"terminal UI missing wordmark line: {line}"
        assert len(line) <= 88, f"wordmark line exceeds compact-terminal budget: {len(line)}"
    assert max(len(line) for line in issue.splitlines()) <= 88
    assert max(len(line) for line in motd.splitlines()) <= 88
    require(
        "lib/console/ywd-system-info.py",
        "'$$   $$ $$   $$ $$$$$$       $$   $$",
        "Raspberry Pi DMR Hotspot Appliance  //  BrandMeister + TGIF",
    )
    print("[OK] dollar-block YWD-HOTSPOT wordmark is shared by installer/update/static + dynamic login branding")

    require(
        "lib/configure.py",
        'tgif=c["tgif"]',
        'ask_bool("Enable TGIF Network"',
        'ask("TGIF master"',
        'ask_int("TGIF UDP port"',
        'getpass.getpass("TGIF Hotspot Security password',
        '"tgif":{**tgif,"enabled":tgif_enabled',
    )
    assert "print(tgif_pw" not in text("lib/configure.py")
    print("[OK] source/GitHub configuration wizard exposes optional TGIF settings without echoing secrets")

    require(
        "lib/console/ywd-system-info.py",
        "TGIF_SCANNER = Path('/run/ywd-hotspot/tgif-scanner.json')",
        "('TGIF Scanner', 'ywd-tgif-scanner.service')",
        "'tgif_state': tgif_state",
        "'tgif_master': tgif_master",
        "'tgif_scanner': tgif_scanner",
        "print(kv('TGIF', s['tgif_state']))",
        "print(kv('TGIF Master', s['tgif_master']))",
        "print(kv('TGIF Scanner', s['tgif_scanner']))",
        "http://ywd-hotspot.local:8443/",
    )
    assert "https://ywd-hotspot.local:8443/" not in text("lib/console/ywd-system-info.py")
    print("[OK] SSH/login appliance panel reports TGIF + scanner state and uses the HTTP setup URL")

    require("INSTALL.sh", 'ywd_banner "INSTALLER"')
    require("UPDATE.sh", 'ywd_banner "APPLIANCE UPDATE"')
    require("GITHUB-UPDATE.sh", 'ywd_banner "GITHUB UPDATE"', "Integrated networks: BrandMeister + TGIF")
    print("[OK] installer and both updater entry points use the shared terminal presentation")

    print("\nTerminal branding/TGIF source setup smoke: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] {exc}")
        raise SystemExit(1)
