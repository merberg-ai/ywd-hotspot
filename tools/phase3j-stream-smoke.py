#!/usr/bin/env python3
"""Non-mutating Phase 3J core smoke test."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import dmr_ambe49
import dashboard_plugin_audio_stream  # noqa: F401 - import is itself a smoke gate


def set_bit(buf, position, value):
    mask = 0x80 >> (position & 7)
    index = position >> 3
    if value:
        buf[index] |= mask
    else:
        buf[index] &= (~mask) & 0xFF


def mapped(position, block):
    if block == 0:
        return position
    if block == 1:
        out = position + 72
        if out >= 108:
            out += 48
        return out
    return position + 192


def pr_mask(seed):
    pr = (16 * seed) & 0xFFFF
    bits = []
    for _ in range(23):
        pr = ((173 * pr) + 13849) & 0xFFFF
        bits.append(1 if pr >= 32768 else 0)
    return bits


def build_zero_payload_burst():
    frame = bytearray(33)
    # AMBE payload all-zero => Golay C0/C1 data and parity are zero.  C1 is
    # transmitted through the AMBE pseudo-random demodulation mask for seed 0.
    transmitted_b = pr_mask(0)
    for block in range(3):
        for pos in dmr_ambe49.DMR_A_TABLE:
            set_bit(frame, mapped(pos, block), 0)
        for i, pos in enumerate(dmr_ambe49.DMR_B_TABLE):
            set_bit(frame, mapped(pos, block), transmitted_b[i])
        for pos in dmr_ambe49.DMR_C_TABLE:
            set_bit(frame, mapped(pos, block), 0)
    return frame.hex()


def main():
    recovered = dmr_ambe49.recover_burst(build_zero_payload_burst())
    assert len(recovered) == 3, recovered
    for index, item in enumerate(recovered):
        assert item.get("valid"), (index, item)
        assert item.get("bits") == "0" * 49, (index, item)
        assert item.get("hex") == "0" * 13, (index, item)
        assert item.get("corrected") == 0, (index, item)
    print("[OK] Phase 3J core imports")
    print("[OK] DMR burst -> 3 x AMBE49 zero-payload recovery")
    print("[OK] streamed audio handler import")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
