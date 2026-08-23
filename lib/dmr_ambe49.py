#!/usr/bin/env python3
"""Recover the three 49-bit AMBE payloads carried by one DMR voice burst.

This is first-party transport/FEC code only.  It performs the same DMR AMBE
interleave extraction, Golay(23,12) correction, and C1 de-scrambling already
physically proven in the RX Monitor browser implementation.  It does not
synthesize speech and contains no software vocoder.
"""
from __future__ import annotations

from itertools import combinations

DMR_A_TABLE = (0,4,8,12,16,20,24,28,32,36,40,44,48,52,56,60,64,68,1,5,9,13,17,21)
DMR_B_TABLE = (25,29,33,37,41,45,49,53,57,61,65,69,2,6,10,14,18,22,26,30,34,38,42)
DMR_C_TABLE = (46,50,54,58,62,66,70,3,7,11,15,19,23,27,31,35,39,43,47,51,55,59,63,67,71)
GOLAY_GENERATOR = (0x63a,0x31d,0x7b4,0x3da,0x1ed,0x6cc,0x366,0x1b3,0x6e3,0x54b,0x49f,0x475)


def _golay_codeword(data: int) -> int:
    parity = 0
    for i, generator in enumerate(GOLAY_GENERATOR):
        if data & (1 << (11 - i)):
            parity ^= generator
    return ((data << 11) | parity) & 0x7FFFFF


_CODEWORD_TO_DATA = {_golay_codeword(data): data for data in range(4096)}
_ERROR_MASKS = {
    weight: tuple(sum(1 << bit for bit in combo) for combo in combinations(range(23), weight))
    for weight in (1, 2, 3)
}


def _decode_golay2312(bits) -> tuple[bool, int, int]:
    word = 0
    for bit in bits:
        word = ((word << 1) | (1 if bit else 0)) & 0x7FFFFF

    data = _CODEWORD_TO_DATA.get(word)
    if data is not None:
        return True, data, 0

    # Most accepted network bursts are clean, so the exact lookup above is the
    # hot path.  Only corrected frames enumerate low-weight error masks.
    for weight in (1, 2, 3):
        for mask in _ERROR_MASKS[weight]:
            data = _CODEWORD_TO_DATA.get(word ^ mask)
            if data is not None:
                return True, data, weight
    return False, 0, 4


def _mapped_position(position: int, block: int) -> int:
    if block == 0:
        return position
    if block == 1:
        out = position + 72
        if out >= 108:
            out += 48
        return out
    return position + 192


def _bit_at(frame: bytes, position: int) -> int:
    return 1 if frame[position >> 3] & (0x80 >> (position & 7)) else 0


def _demodulate_b(bits, seed: int):
    pr = (16 * seed) & 0xFFFF
    out = list(bits)
    for i in range(23):
        pr = ((173 * pr) + 13849) & 0xFFFF
        out[i] ^= 1 if pr >= 32768 else 0
    return out


def _data_bits(value: int, count: int = 12):
    return [(value >> (count - 1 - i)) & 1 for i in range(count)]


def recover_burst(frame_hex: str) -> list[dict]:
    """Return up to three recovered AMBE49 payloads from a 33-byte DMR burst.

    Each result has ``valid``, ``index``, and correction metadata.  Valid
    results additionally contain a 49-character ``bits`` string and the same
    13-nibble padded hex representation used by the browser diagnostics.
    """
    text = str(frame_hex or "").strip().lower()
    if len(text) != 66:
        raise ValueError("DMR voice frame must contain exactly 33 bytes")
    try:
        frame = bytes.fromhex(text)
    except ValueError as exc:
        raise ValueError("DMR voice frame contains invalid hex") from exc
    if len(frame) != 33:
        raise ValueError("DMR voice frame must contain exactly 33 bytes")

    results = []
    for block in range(3):
        a = [_bit_at(frame, _mapped_position(pos, block)) for pos in DMR_A_TABLE]
        b = [_bit_at(frame, _mapped_position(pos, block)) for pos in DMR_B_TABLE]
        c = [_bit_at(frame, _mapped_position(pos, block)) for pos in DMR_C_TABLE]

        ok_a, data_a, corr_a = _decode_golay2312(a[:23])
        if not ok_a:
            results.append({"valid": False, "index": block, "stage": "C0", "corrected": corr_a})
            continue

        b_demod = _demodulate_b(b, data_a)
        ok_b, data_b, corr_b = _decode_golay2312(b_demod)
        if not ok_b:
            results.append({"valid": False, "index": block, "stage": "C1", "corrected": corr_a + corr_b})
            continue

        bits = _data_bits(data_a) + _data_bits(data_b) + c
        if len(bits) != 49:
            results.append({"valid": False, "index": block, "stage": "length", "corrected": corr_a + corr_b})
            continue

        bit_string = "".join("1" if bit else "0" for bit in bits)
        padded = bit_string + "000"
        hex_value = f"{int(padded, 2):013x}"
        results.append({
            "valid": True,
            "index": block,
            "bits": bit_string,
            "hex": hex_value,
            "corrected": corr_a + corr_b,
            "a_corrected": corr_a,
            "b_corrected": corr_b,
        })
    return results
