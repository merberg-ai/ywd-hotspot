#!/usr/bin/env python3
"""Source-only guard for source-installer I2C/OLED handling."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "INSTALL-core.sh"
text = INSTALL.read_text(encoding="utf-8")

required = (
    "/boot/firmware/config.txt",
    "/boot/config.txt",
    "dtparam=i2c_arm=on",
    "I2C_REBOOT_REQUIRED",
    "modprobe i2c-dev",
    'i2cdetect -y "$OLED_BUS"',
    "OLED_DETECTED_ADDR=\"3c\"",
    "OLED_DETECTED_ADDR=\"3d\"",
    "updated canonical display address",
    "OLED probing deferred until reboot",
)
for marker in required:
    assert marker in text, f"missing source OLED installer marker: {marker}"

# Do not regress to the old one-line policy that only accepted address 0x3c.
assert "grep -Eq '(^|[[:space:]])3c([[:space:]]|$)' <<<\"$OLED_SCAN\"; then systemctl enable --now ywd-oled.service" not in text

print("[OK] source installer enables Raspberry Pi I2C boot configuration when needed")
print("[OK] source installer defers OLED probing honestly when a reboot is required")
print("[OK] source installer accepts SSD1306 addresses 0x3c and 0x3d")
print("[OK] detected alternate OLED address is persisted to canonical config")
