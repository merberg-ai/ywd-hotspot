#!/usr/bin/env python3
"""Trusted YWD Vocoder Protocol v1 client.

This module is the core-side broker boundary. It never loads a vocoder library
or executes plugin code. It talks only to a local AF_UNIX backend selected and
installed separately by the operator.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import socket
from pathlib import Path

import vocoder_protocol as proto

SOCKET_PATH = Path(os.environ.get("YWD_VOCODER_SOCKET", "/run/ywd-vocoder.sock"))
DEFAULT_TIMEOUT = 0.30
STATUS_TIMEOUT = 3.0
MAX_TIMEOUT = 5.0


class VocoderUnavailable(RuntimeError):
    pass


class VocoderBackendError(RuntimeError):
    pass


def _request(opcode: int, payload: bytes = b"", timeout: float = DEFAULT_TIMEOUT) -> bytes:
    request_id = random.SystemRandom().randrange(1, 0xFFFFFFFF)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    # DECODE callers keep the 300 ms default.  STATUS may use a longer timeout
    # because a cold socket activation on a Pi Zero must start the Python backend
    # before it can answer; that startup latency is not part of the live audio
    # backpressure budget.
    sock.settimeout(max(0.05, min(float(timeout), MAX_TIMEOUT)))
    try:
        sock.connect(str(SOCKET_PATH))
        sock.sendall(proto.packet(proto.KIND_REQUEST, opcode, 0, request_id, payload))
        header, response = proto.recv_packet(sock)
    except (FileNotFoundError, ConnectionRefusedError) as exc:
        raise VocoderUnavailable(f"vocoder backend socket unavailable: {SOCKET_PATH}") from exc
    except socket.timeout as exc:
        raise VocoderUnavailable("vocoder backend timed out") from exc
    except OSError as exc:
        raise VocoderUnavailable(f"vocoder backend connection failed: {exc}") from exc
    finally:
        sock.close()

    if header["kind"] != proto.KIND_RESPONSE:
        raise VocoderBackendError("vocoder backend returned a non-response packet")
    if header["request_id"] != request_id or header["opcode"] != opcode:
        raise VocoderBackendError("vocoder backend response did not match the request")
    if header["status"] != proto.STATUS_OK:
        detail = ""
        try:
            detail = proto.parse_json_payload(response).get("error", "")
        except Exception:
            detail = response.decode("utf-8", "replace")[:240]
        raise VocoderBackendError(detail or f"vocoder backend error status {header['status']}")
    return response


def status(timeout: float = STATUS_TIMEOUT) -> dict:
    """Probe the backend, allowing extra time for a cold socket activation."""
    try:
        doc = proto.parse_json_payload(_request(proto.OP_STATUS, timeout=timeout))
        return {"available": True, "socket": str(SOCKET_PATH), **doc}
    except VocoderUnavailable as exc:
        return {
            "available": False,
            "socket": str(SOCKET_PATH),
            "protocol": proto.VERSION,
            "error": str(exc),
        }


def reset(timeout: float = DEFAULT_TIMEOUT) -> dict:
    _request(proto.OP_RESET, timeout=timeout)
    return {"ok": True, "protocol": proto.VERSION, "socket": str(SOCKET_PATH)}


def decode(frames, timeout: float = DEFAULT_TIMEOUT) -> dict:
    packed = []
    for frame in frames:
        if isinstance(frame, str):
            packed.append(proto.pack_ambe49_bits(frame))
        else:
            packed.append(bytes(frame))
    payload = proto.encode_decode_request(packed)
    result = proto.parse_decode_response(_request(proto.OP_DECODE, payload, timeout=timeout))
    pcm = result.pop("pcm_s16le")
    return {
        "protocol": proto.VERSION,
        "codec": "ambe49",
        **result,
        "pcm_s16le": pcm,
    }


def public_decode(frames) -> dict:
    result = decode(frames)
    pcm = result.pop("pcm_s16le")
    return {
        **result,
        "pcm_bytes": len(pcm),
        "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
        "pcm_s16le_b64": base64.b64encode(pcm).decode("ascii"),
    }


def _decode_test(count: int) -> dict:
    count = max(1, min(int(count), proto.MAX_FRAMES))
    zero = "0" * 49
    result = public_decode([zero] * count)
    result.pop("pcm_s16le_b64", None)
    result["requested_frames"] = count
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="YWD Vocoder Protocol v1 core client")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("reset")
    test = sub.add_parser("decode-test")
    test.add_argument("--frames", type=int, default=5)
    args = ap.parse_args()

    try:
        if args.command == "status":
            out = status()
            print(json.dumps(out, indent=2, sort_keys=True))
            return 0 if out.get("available") else 3
        if args.command == "reset":
            print(json.dumps(reset(), indent=2, sort_keys=True))
            return 0
        if args.command == "decode-test":
            print(json.dumps(_decode_test(args.frames), indent=2, sort_keys=True))
            return 0
    except (VocoderUnavailable, VocoderBackendError, proto.ProtocolError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
