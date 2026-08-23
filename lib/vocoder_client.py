#!/usr/bin/env python3
"""Trusted YWD Vocoder Protocol v1 client.

This module is the core-side broker boundary. It never loads a vocoder library
or executes plugin code. It talks only to a local AF_UNIX backend selected and
installed separately by the operator.

Phase 3H keeps one protocol-v1 AF_UNIX session warm inside the dashboard
process. STATUS, RESET, and DECODE requests are serialized through that session,
removing one connect/close cycle per live audio batch while preserving the same
wire framing and fail-closed request validation.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import socket
import threading
from pathlib import Path

import vocoder_protocol as proto

SOCKET_PATH = Path(os.environ.get("YWD_VOCODER_SOCKET", "/run/ywd-vocoder.sock"))
DECODE_TIMEOUT = 0.30
CONTROL_TIMEOUT = 15.0
MAX_TIMEOUT = 15.0


class VocoderUnavailable(RuntimeError):
    pass


class VocoderBackendError(RuntimeError):
    pass


class PersistentVocoderSession:
    """Serialize protocol v1 requests over one reusable AF_UNIX connection.

    The dashboard HTTP server is threaded, so the socket is protected by one
    lock. Requests are deliberately not replayed after a transport failure:
    DECODE is stateful and silently sending the same batch twice would be worse
    than dropping it and letting the caller perform its normal RESET/recovery.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._sock = None
        self._connects = 0
        self._requests = 0
        self._reused_requests = 0

    def _close_locked(self):
        sock = self._sock
        self._sock = None
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

    def close(self):
        with self._lock:
            self._close_locked()

    def _connect_locked(self, timeout: float):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(str(SOCKET_PATH))
        except Exception:
            sock.close()
            raise
        self._sock = sock
        self._connects += 1
        return sock

    def snapshot(self):
        with self._lock:
            return {
                "transport": "persistent-af-unix",
                "connected": self._sock is not None,
                "connects": self._connects,
                "requests": self._requests,
                "reused_requests": self._reused_requests,
            }

    def request(self, opcode: int, payload: bytes = b"", timeout: float = DECODE_TIMEOUT) -> bytes:
        timeout = max(0.05, min(float(timeout), MAX_TIMEOUT))
        request_id = random.SystemRandom().randrange(1, 0xFFFFFFFF)

        with self._lock:
            reused = self._sock is not None
            try:
                sock = self._sock or self._connect_locked(timeout)
                sock.settimeout(timeout)
                sock.sendall(proto.packet(proto.KIND_REQUEST, opcode, 0, request_id, payload))
                header, response = proto.recv_packet(sock)
            except (FileNotFoundError, ConnectionRefusedError) as exc:
                self._close_locked()
                raise VocoderUnavailable(f"vocoder backend socket unavailable: {SOCKET_PATH}") from exc
            except socket.timeout as exc:
                self._close_locked()
                raise VocoderUnavailable("vocoder backend timed out") from exc
            except OSError as exc:
                self._close_locked()
                raise VocoderUnavailable(f"vocoder backend connection failed: {exc}") from exc
            except proto.ProtocolError as exc:
                self._close_locked()
                raise VocoderBackendError(f"vocoder protocol transport failed: {exc}") from exc

            if header["kind"] != proto.KIND_RESPONSE:
                self._close_locked()
                raise VocoderBackendError("vocoder backend returned a non-response packet")
            if header["request_id"] != request_id or header["opcode"] != opcode:
                self._close_locked()
                raise VocoderBackendError("vocoder backend response did not match the request")

            self._requests += 1
            if reused:
                self._reused_requests += 1

            if header["status"] != proto.STATUS_OK:
                detail = ""
                try:
                    detail = proto.parse_json_payload(response).get("error", "")
                except Exception:
                    detail = response.decode("utf-8", "replace")[:240]
                raise VocoderBackendError(detail or f"vocoder backend error status {header['status']}")
            return response


_SESSION = PersistentVocoderSession()


def transport_status() -> dict:
    return _SESSION.snapshot()


def _request(opcode: int, payload: bytes = b"", timeout: float = DECODE_TIMEOUT) -> bytes:
    return _SESSION.request(opcode, payload, timeout)


def status(timeout: float = CONTROL_TIMEOUT) -> dict:
    """Probe the backend, allowing extra time for a cold socket activation."""
    try:
        doc = proto.parse_json_payload(_request(proto.OP_STATUS, timeout=timeout))
        return {
            "available": True,
            "socket": str(SOCKET_PATH),
            **doc,
            "client_transport": transport_status(),
        }
    except VocoderUnavailable as exc:
        return {
            "available": False,
            "socket": str(SOCKET_PATH),
            "protocol": proto.VERSION,
            "error": str(exc),
            "client_transport": transport_status(),
        }


def reset(timeout: float = CONTROL_TIMEOUT) -> dict:
    """Reset backend stream state; like STATUS this may wake a cold backend."""
    _request(proto.OP_RESET, timeout=timeout)
    return {
        "ok": True,
        "protocol": proto.VERSION,
        "socket": str(SOCKET_PATH),
        "client_transport": transport_status(),
    }


def decode(frames, timeout: float = DECODE_TIMEOUT) -> dict:
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
        "client_transport": transport_status(),
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
