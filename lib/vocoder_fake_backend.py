#!/usr/bin/env python3
"""Development-only fake backend for YWD Vocoder Protocol v1.

It decodes nothing. DECODE requests return either silence or a deterministic
440 Hz test tone so the transport/socket/audio plumbing can be proven without
shipping or loading an AMBE/AMBE+2 software vocoder.

Phase 3H keeps protocol v1 framing unchanged but permits multiple request/
response packets on one accepted AF_UNIX connection. An idle persistent client
is closed after the configured idle interval so socket-activated backend demand
still disappears when RX audio stops.
"""
from __future__ import annotations

import argparse
import math
import os
import select
import socket
import struct
import sys
import time

import vocoder_protocol as proto

BACKEND_NAME = "ywd-fake-vocoder"
TONE_HZ = 440.0
TONE_AMPLITUDE = 6000


class FakeBackend:
    def __init__(self, mode: str):
        self.mode = mode if mode in {"silence", "tone"} else "tone"
        self.sample_index = 0

    def status_doc(self) -> dict:
        return {
            "protocol": proto.VERSION,
            "backend": BACKEND_NAME,
            "fake": True,
            "mode": self.mode,
            "codecs": ["ambe49"],
            "sample_rate": proto.SAMPLE_RATE,
            "samples_per_frame": proto.SAMPLES_PER_FRAME,
            "channels": proto.CHANNELS,
            "sample_format": "s16le",
            "preferred_batch_frames": 10,
            "max_batch_frames": proto.MAX_FRAMES,
            "persistent_sessions": True,
        }

    def reset(self) -> None:
        self.sample_index = 0

    def pcm(self, frame_count: int) -> bytes:
        samples = frame_count * proto.SAMPLES_PER_FRAME
        if self.mode == "silence":
            self.sample_index += samples
            return b"\0\0" * samples

        out = bytearray()
        for _ in range(samples):
            phase = 2.0 * math.pi * TONE_HZ * (self.sample_index / proto.SAMPLE_RATE)
            sample = int(round(TONE_AMPLITUDE * math.sin(phase)))
            out.extend(struct.pack("<h", sample))
            self.sample_index += 1
        return bytes(out)


def _error_packet(opcode: int, request_id: int, status: int, message: str) -> bytes:
    payload = proto.json_payload({"error": str(message)[:400]})
    return proto.packet(proto.KIND_RESPONSE, opcode, status, request_id, payload)


def _serve_request(conn: socket.socket, backend: FakeBackend, header: dict, payload: bytes) -> None:
    opcode = header["opcode"]
    request_id = header["request_id"]
    if header["kind"] != proto.KIND_REQUEST or header["status"] != 0:
        conn.sendall(_error_packet(opcode, request_id, proto.STATUS_BAD_REQUEST, "invalid request packet"))
        return

    try:
        if opcode == proto.OP_STATUS:
            if payload:
                raise proto.ProtocolError("STATUS request payload must be empty")
            response = proto.json_payload(backend.status_doc())
        elif opcode == proto.OP_RESET:
            if payload:
                raise proto.ProtocolError("RESET request payload must be empty")
            backend.reset()
            response = b""
        elif opcode == proto.OP_DECODE:
            frames = proto.parse_decode_request(payload)
            response = proto.encode_decode_response(len(frames), backend.pcm(len(frames)))
        else:
            conn.sendall(_error_packet(opcode, request_id, proto.STATUS_UNSUPPORTED, "unsupported opcode"))
            return
        conn.sendall(proto.packet(proto.KIND_RESPONSE, opcode, proto.STATUS_OK, request_id, response))
    except proto.ProtocolError as exc:
        conn.sendall(_error_packet(opcode, request_id, proto.STATUS_BAD_REQUEST, str(exc)))
    except Exception as exc:
        conn.sendall(_error_packet(opcode, request_id, proto.STATUS_BACKEND_ERROR, str(exc)))


def handle_connection(conn: socket.socket, backend: FakeBackend, idle_seconds: float) -> bool:
    """Serve repeated v1 packets. Return True when the session itself idled out."""
    idle_seconds = max(1.0, min(float(idle_seconds), 60.0))
    conn.settimeout(idle_seconds)
    while True:
        try:
            header, payload = proto.recv_packet(conn)
        except socket.timeout:
            return True
        except proto.ProtocolError as exc:
            # A clean peer close appears as the framing helper's unexpected EOF.
            if str(exc) == "unexpected EOF":
                return False
            return False
        except (ConnectionResetError, BrokenPipeError, OSError):
            return False

        try:
            _serve_request(conn, backend, header, payload)
        except (ConnectionResetError, BrokenPipeError, OSError):
            return False


def systemd_listener() -> socket.socket:
    try:
        listen_pid = int(os.environ.get("LISTEN_PID", "0"))
        listen_fds = int(os.environ.get("LISTEN_FDS", "0"))
    except Exception:
        listen_pid = listen_fds = 0
    if listen_pid != os.getpid() or listen_fds < 1:
        raise RuntimeError("fake vocoder backend was not socket-activated")
    listener = socket.socket(fileno=3)
    listener.setblocking(False)
    return listener


def serve(listener: socket.socket, backend: FakeBackend, idle_seconds: float) -> None:
    last_activity = time.monotonic()
    idle_seconds = max(1.0, min(float(idle_seconds), 60.0))
    while True:
        remaining = idle_seconds - (time.monotonic() - last_activity)
        if remaining <= 0:
            return
        readable, _, _ = select.select([listener], [], [], remaining)
        if not readable:
            return
        try:
            conn, _ = listener.accept()
        except BlockingIOError:
            continue
        last_activity = time.monotonic()
        with conn:
            session_idled = handle_connection(conn, backend, idle_seconds)
        last_activity = time.monotonic()
        if session_idled:
            # The warm dashboard session itself went quiet. Exit immediately;
            # systemd socket activation will start us again on the next demand.
            return


def main() -> int:
    ap = argparse.ArgumentParser(description="Development-only fake YWD vocoder backend")
    ap.add_argument("--systemd", action="store_true")
    ap.add_argument("--idle-seconds", type=float, default=5.0)
    ap.add_argument("--mode", choices=("silence", "tone"), default=os.environ.get("YWD_FAKE_VOCODER_MODE", "tone"))
    args = ap.parse_args()
    if not args.systemd:
        raise RuntimeError("standalone listening is intentionally unsupported; use systemd socket activation")
    listener = systemd_listener()
    backend = FakeBackend(args.mode)
    serve(listener, backend, args.idle_seconds)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] fake vocoder backend: {exc}", file=sys.stderr)
        raise SystemExit(1)
