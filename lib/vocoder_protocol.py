#!/usr/bin/env python3
"""YWD Vocoder Protocol v1 wire helpers.

The backend boundary is deliberately codec-neutral at the transport layer. v1
currently defines one codec payload, AMBE49, because DMR RX Monitor recovers
49-bit vocoder frames before crossing this boundary.

Wire framing:
    16-byte big-endian header:
      magic[4] = b"YVCP"
      version  = 1
      kind     = 0 request, 1 response
      opcode   = 1 STATUS, 2 RESET, 3 DECODE
      status   = 0 OK (requests must use 0)
      request_id u32
      payload_len u32

DECODE request payload:
      codec u8       (1 = AMBE49)
      frame_count u8 (1..10)
      frame_bytes u8 (7)
      reserved u8    (0)
      frame_count * 7 bytes

AMBE49 packing is MSB-first. Bits b0..b47 fill bytes 0..5; b48 occupies bit 7
of byte 6 and the remaining seven bits of byte 6 are zero.

DECODE response payload:
      sample_rate u16       (8000)
      samples_per_frame u16 (160)
      channels u8           (1)
      sample_format u8      (1 = signed 16-bit little-endian PCM)
      frame_count u16
      PCM bytes
"""
from __future__ import annotations

import json
import struct

MAGIC = b"YVCP"
VERSION = 1

KIND_REQUEST = 0
KIND_RESPONSE = 1

OP_STATUS = 1
OP_RESET = 2
OP_DECODE = 3

STATUS_OK = 0
STATUS_BAD_REQUEST = 1
STATUS_UNSUPPORTED = 2
STATUS_BACKEND_ERROR = 3

CODEC_AMBE49 = 1
SAMPLE_FORMAT_S16LE = 1
SAMPLE_RATE = 8000
SAMPLES_PER_FRAME = 160
CHANNELS = 1

MAX_PAYLOAD = 64 * 1024
MAX_FRAMES = 10
AMBE49_BYTES = 7

HEADER = struct.Struct("!4sBBBBII")
DECODE_REQUEST_HEADER = struct.Struct("!BBBB")
DECODE_RESPONSE_HEADER = struct.Struct("!HHBBH")


class ProtocolError(ValueError):
    pass


def packet(kind: int, opcode: int, status: int, request_id: int, payload: bytes = b"") -> bytes:
    payload = bytes(payload)
    if kind not in {KIND_REQUEST, KIND_RESPONSE}:
        raise ProtocolError("invalid packet kind")
    if opcode not in {OP_STATUS, OP_RESET, OP_DECODE}:
        raise ProtocolError("invalid opcode")
    if not 0 <= int(status) <= 255:
        raise ProtocolError("invalid status")
    if not 0 <= int(request_id) <= 0xFFFFFFFF:
        raise ProtocolError("invalid request id")
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError("payload is too large")
    return HEADER.pack(MAGIC, VERSION, kind, opcode, status, int(request_id), len(payload)) + payload


def parse_header(raw: bytes) -> dict:
    if len(raw) != HEADER.size:
        raise ProtocolError("invalid header length")
    magic, version, kind, opcode, status, request_id, payload_len = HEADER.unpack(raw)
    if magic != MAGIC:
        raise ProtocolError("invalid protocol magic")
    if version != VERSION:
        raise ProtocolError(f"unsupported protocol version: {version}")
    if kind not in {KIND_REQUEST, KIND_RESPONSE}:
        raise ProtocolError("invalid packet kind")
    if opcode not in {OP_STATUS, OP_RESET, OP_DECODE}:
        raise ProtocolError("invalid opcode")
    if payload_len > MAX_PAYLOAD:
        raise ProtocolError("payload is too large")
    return {
        "kind": kind,
        "opcode": opcode,
        "status": status,
        "request_id": request_id,
        "payload_len": payload_len,
    }


def recv_exact(sock, size: int) -> bytes:
    chunks = []
    remaining = int(size)
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ProtocolError("unexpected EOF")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_packet(sock) -> tuple[dict, bytes]:
    header = parse_header(recv_exact(sock, HEADER.size))
    payload = recv_exact(sock, header["payload_len"]) if header["payload_len"] else b""
    return header, payload


def json_payload(doc: dict) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")


def parse_json_payload(payload: bytes) -> dict:
    try:
        doc = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise ProtocolError("invalid JSON payload") from exc
    if not isinstance(doc, dict):
        raise ProtocolError("JSON payload must be an object")
    return doc


def pack_ambe49_bits(bits) -> bytes:
    if isinstance(bits, str):
        text = bits.strip()
        if len(text) != 49 or any(ch not in "01" for ch in text):
            raise ProtocolError("AMBE49 frame must contain exactly 49 binary digits")
        values = [1 if ch == "1" else 0 for ch in text]
    else:
        values = list(bits)
        if len(values) != 49 or any(int(x) not in (0, 1) for x in values):
            raise ProtocolError("AMBE49 frame must contain exactly 49 bits")
        values = [int(x) for x in values]

    out = bytearray(AMBE49_BYTES)
    for index, bit in enumerate(values):
        if bit:
            out[index // 8] |= 1 << (7 - (index % 8))
    return bytes(out)


def unpack_ambe49_bits(frame: bytes) -> str:
    frame = bytes(frame)
    validate_packed_ambe49(frame)
    bits = []
    for index in range(49):
        bits.append("1" if frame[index // 8] & (1 << (7 - (index % 8))) else "0")
    return "".join(bits)


def validate_packed_ambe49(frame: bytes) -> None:
    frame = bytes(frame)
    if len(frame) != AMBE49_BYTES:
        raise ProtocolError("packed AMBE49 frame must be 7 bytes")
    if frame[6] & 0x7F:
        raise ProtocolError("packed AMBE49 frame has non-zero padding bits")


def encode_decode_request(frames) -> bytes:
    packed = [bytes(frame) for frame in frames]
    if not 1 <= len(packed) <= MAX_FRAMES:
        raise ProtocolError(f"decode requires 1-{MAX_FRAMES} frames")
    for frame in packed:
        validate_packed_ambe49(frame)
    return DECODE_REQUEST_HEADER.pack(CODEC_AMBE49, len(packed), AMBE49_BYTES, 0) + b"".join(packed)


def parse_decode_request(payload: bytes) -> list[bytes]:
    if len(payload) < DECODE_REQUEST_HEADER.size:
        raise ProtocolError("decode request is truncated")
    codec, frame_count, frame_bytes, reserved = DECODE_REQUEST_HEADER.unpack_from(payload)
    if codec != CODEC_AMBE49:
        raise ProtocolError("unsupported codec")
    if not 1 <= frame_count <= MAX_FRAMES:
        raise ProtocolError("invalid frame count")
    if frame_bytes != AMBE49_BYTES or reserved != 0:
        raise ProtocolError("invalid AMBE49 decode header")
    expected = DECODE_REQUEST_HEADER.size + frame_count * AMBE49_BYTES
    if len(payload) != expected:
        raise ProtocolError("decode payload length mismatch")
    frames = []
    offset = DECODE_REQUEST_HEADER.size
    for _ in range(frame_count):
        frame = payload[offset:offset + AMBE49_BYTES]
        validate_packed_ambe49(frame)
        frames.append(frame)
        offset += AMBE49_BYTES
    return frames


def encode_decode_response(frame_count: int, pcm_s16le: bytes) -> bytes:
    frame_count = int(frame_count)
    expected = frame_count * SAMPLES_PER_FRAME * CHANNELS * 2
    pcm_s16le = bytes(pcm_s16le)
    if not 1 <= frame_count <= MAX_FRAMES:
        raise ProtocolError("invalid response frame count")
    if len(pcm_s16le) != expected:
        raise ProtocolError("PCM byte length does not match frame count")
    return DECODE_RESPONSE_HEADER.pack(
        SAMPLE_RATE, SAMPLES_PER_FRAME, CHANNELS, SAMPLE_FORMAT_S16LE, frame_count
    ) + pcm_s16le


def parse_decode_response(payload: bytes) -> dict:
    if len(payload) < DECODE_RESPONSE_HEADER.size:
        raise ProtocolError("decode response is truncated")
    sample_rate, samples_per_frame, channels, sample_format, frame_count = DECODE_RESPONSE_HEADER.unpack_from(payload)
    if sample_rate != SAMPLE_RATE or samples_per_frame != SAMPLES_PER_FRAME:
        raise ProtocolError("unsupported PCM timing")
    if channels != CHANNELS or sample_format != SAMPLE_FORMAT_S16LE:
        raise ProtocolError("unsupported PCM format")
    if not 1 <= frame_count <= MAX_FRAMES:
        raise ProtocolError("invalid response frame count")
    pcm = payload[DECODE_RESPONSE_HEADER.size:]
    expected = frame_count * samples_per_frame * channels * 2
    if len(pcm) != expected:
        raise ProtocolError("PCM response length mismatch")
    return {
        "sample_rate": sample_rate,
        "samples_per_frame": samples_per_frame,
        "channels": channels,
        "sample_format": "s16le",
        "frame_count": frame_count,
        "pcm_s16le": pcm,
    }
