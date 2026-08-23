#!/usr/bin/env python3
"""Consume passive MMDVM DMR voice MQTT into a bounded trusted runtime ring.

This process is first-party appliance infrastructure, not plugin code. It owns no
RF hardware and never talks to MMDVM serial. MMDVM-Host remains the sole modem
owner and publishes copies of accepted DMR voice frames to loopback MQTT.

Alpha22.5 keeps MQTT ingestion and snapshot serialization in separate processes.
The foreground reader only drains/parses MQTT and forwards compact events. A
nice'd writer process owns the bounded JSON ring, coalesces state-file updates,
and performs the heavier json.dump/atomic replace work. On a single-core Pi Zero
this prevents full-ring serialization from holding the ingestion interpreter/GIL
while voice bursts are waiting in the subscriber pipe.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import queue
import re
import selectors
import signal
import socket
import subprocess
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

STATE = Path(os.environ.get("YWD_MMDVM_VOICE_STATE", "/run/ywd-hotspot-voice/voice.json"))
HOST = os.environ.get("YWD_MQTT_HOST", "127.0.0.1")
PORT = int(os.environ.get("YWD_MQTT_PORT", "18883"))
TOPIC = os.environ.get("YWD_MQTT_VOICE_TOPIC", "ywd-mmdvm/voice")
MAX_FRAMES = max(32, min(512, int(os.environ.get("YWD_MMDVM_VOICE_RING", "32"))))
MAX_PIPE_BUFFER = 256 * 1024
LIVE_SOCKET = Path(
    os.environ.get(
        "YWD_MMDVM_VOICE_LIVE_SOCKET",
        "/run/ywd-hotspot-voice/live-audio.sock",
    )
)
LIVE_PACKET_MAX = 4096
LIVE_PROBE_INTERVAL_S = 0.25
WRITE_INTERVAL_S = 1.00
HEARTBEAT_INTERVAL_S = 1.0
STOP = threading.Event()
HEX_RE = re.compile(r"^[0-9a-fA-F]{66}$")


def stop(_signum, _frame):
    STOP.set()


def atomic_write(doc):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".mmdvm-voice.", dir=str(STATE.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(doc, handle, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
        os.chmod(name, 0o640)
        os.replace(name, STATE)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def as_int(value, minimum=None, maximum=None):
    try:
        out = int(value)
    except Exception:
        return None
    if minimum is not None and out < minimum:
        return None
    if maximum is not None and out > maximum:
        return None
    return out


def clean_frame(raw, seq):
    if not isinstance(raw, dict):
        return None
    frame_hex = str(raw.get("frame_hex") or "")
    if not HEX_RE.fullmatch(frame_hex):
        return None
    source = str(raw.get("source") or "")
    frame_kind = str(raw.get("frame_kind") or "")
    group = str(raw.get("group") or "")
    if source not in {"rf", "network"} or frame_kind not in {"voice", "voice_sync"} or group not in {"yes", "no"}:
        return None

    fields = {
        "slot": as_int(raw.get("slot"), 1, 2),
        "data_type": as_int(raw.get("data_type"), 0, 255),
        "src_id": as_int(raw.get("src_id"), 0, 16777215),
        "dst_id": as_int(raw.get("dst_id"), 0, 16777215),
        "seq_no": as_int(raw.get("seq_no"), 0, 255),
        "n": as_int(raw.get("n"), 0, 255),
        "ber": as_int(raw.get("ber"), 0, 255),
        "rssi": as_int(raw.get("rssi"), 0, 65535),
    }
    if any(value is None for value in fields.values()):
        return None

    return {
        "seq": seq,
        "received_at": time.time(),
        "timestamp": str(raw.get("timestamp") or "")[:64],
        "source": source,
        "slot": fields["slot"],
        "frame_kind": frame_kind,
        "data_type": fields["data_type"],
        "src_id": fields["src_id"],
        "dst_id": fields["dst_id"],
        "group": group == "yes",
        "seq_no": fields["seq_no"],
        "n": fields["n"],
        "ber": fields["ber"],
        "rssi": fields["rssi"],
        "frame_hex": frame_hex.lower(),
    }


def initial_doc():
    now = time.time()
    return {
        "schema": 1,
        "bridge": {
            "status": "starting",
            "heartbeat_at": now,
            "started_at": now,
            "messages": 0,
            "parse_errors": 0,
            "topic": TOPIC,
            "capacity": MAX_FRAMES,
            "writer": "process",
            "snapshot_write_ms": 0.0,
            "snapshot_write_max_ms": 0.0,
        },
        "next_seq": 1,
        "frames": [],
    }


def spawn_subscriber():
    return subprocess.Popen(
        ["/usr/bin/mosquitto_sub", "-h", HOST, "-p", str(PORT), "-t", TOPIC, "-q", "0"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=False,
        bufsize=0,
        close_fds=True,
    )


def parse_line(raw_line, seq):
    try:
        envelope = json.loads(raw_line.decode("utf-8"))
        raw = envelope.get("DMRVoice") if isinstance(envelope, dict) and len(envelope) == 1 else None
        return clean_frame(raw, seq)
    except Exception:
        return None


def drain_subscriber(fileobj, pipe_buffer):
    """Drain all bytes currently available and return complete MQTT lines."""
    fd = fileobj.fileno()
    while True:
        try:
            chunk = os.read(fd, 65536)
        except BlockingIOError:
            break
        except InterruptedError:
            continue
        if not chunk:
            break
        pipe_buffer.extend(chunk)
        if len(pipe_buffer) > MAX_PIPE_BUFFER:
            pipe_buffer.clear()
            return [], True

    lines = []
    while True:
        newline = pipe_buffer.find(b"\n")
        if newline < 0:
            break
        line = bytes(pipe_buffer[:newline]).rstrip(b"\r")
        del pipe_buffer[: newline + 1]
        if line:
            lines.append(line)
    return lines, False


def writer_main(events):
    """Own the public ring and coalesce whole-ring snapshots away from ingest."""
    try:
        os.nice(10)
    except Exception:
        pass

    doc = initial_doc()
    frames = deque(maxlen=MAX_FRAMES)
    dirty = True
    stopping = False
    last_write = 0.0

    while True:
        now = time.monotonic()
        if dirty:
            due_in = max(0.0, WRITE_INTERVAL_S - (now - last_write)) if last_write else 0.0
        else:
            due_in = max(0.0, HEARTBEAT_INTERVAL_S - (now - last_write)) if last_write else 0.0

        event = None
        try:
            event = events.get(timeout=min(0.10, due_in) if due_in > 0 else 0.0)
        except queue.Empty:
            pass
        except (EOFError, OSError):
            stopping = True

        if event is not None:
            batch = [event]
            while len(batch) < 512:
                try:
                    batch.append(events.get_nowait())
                except queue.Empty:
                    break
                except (EOFError, OSError):
                    stopping = True
                    break

            for kind, payload in batch:
                if kind == "frame":
                    if isinstance(payload, dict):
                        frames.append(payload)
                        doc["next_seq"] = int(payload.get("seq") or doc["next_seq"]) + 1
                        doc["bridge"]["messages"] += 1
                        doc["bridge"]["status"] = "online"
                        dirty = True
                elif kind == "parse_error":
                    doc["bridge"]["parse_errors"] += max(1, int(payload or 1))
                    dirty = True
                elif kind == "status":
                    value = str(payload or "unknown")[:32]
                    if doc["bridge"].get("status") != value:
                        doc["bridge"]["status"] = value
                        dirty = True
                elif kind == "stop":
                    doc["bridge"]["status"] = "stopped"
                    dirty = True
                    stopping = True

        now = time.monotonic()
        write_due = (dirty and (not last_write or now - last_write >= WRITE_INTERVAL_S)) or (
            last_write and now - last_write >= HEARTBEAT_INTERVAL_S
        )
        if write_due or (stopping and dirty):
            doc["bridge"]["heartbeat_at"] = time.time()
            doc["frames"] = list(frames)
            started = time.monotonic()
            try:
                atomic_write(doc)
            except Exception as exc:
                print(f"voice snapshot write failed: {exc}", flush=True)
            else:
                elapsed_ms = (time.monotonic() - started) * 1000.0
                doc["bridge"]["snapshot_write_ms"] = round(elapsed_ms, 3)
                doc["bridge"]["snapshot_write_max_ms"] = round(
                    max(float(doc["bridge"].get("snapshot_write_max_ms") or 0.0), elapsed_ms), 3
                )
                last_write = time.monotonic()
                dirty = False

        if stopping:
            if dirty:
                continue
            break


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    ctx = mp.get_context("fork")
    events = ctx.Queue(maxsize=0)
    writer = ctx.Process(target=writer_main, args=(events,), name="ywd-voice-writer", daemon=False)
    writer.start()

    child = None
    selector = selectors.DefaultSelector()
    child_started = 0.0
    pipe_buffer = bytearray()
    next_seq = 1
    current_status = None

    # Live RX audio is an optional, nonblocking side channel. The dashboard
    # creates the destination socket only while START AUDIO is active. Missing,
    # full, or disappearing consumers are audio-only loss and must never delay
    # MQTT ingest or MMDVM.
    live_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    live_socket.setblocking(False)
    live_ready = False
    next_live_probe = 0.0
    print(
        f"YWD DMR voice bridge starting: {HOST}:{PORT} topic={TOPIC} ring={MAX_FRAMES} writer_pid={writer.pid}",
        flush=True,
    )

    def emit(kind, payload=None):
        try:
            events.put_nowait((kind, payload))
            return True
        except Exception as exc:
            print(f"voice writer queue failed: {exc}", flush=True)
            return False

    def emit_status(value):
        nonlocal current_status
        if current_status == value:
            return
        current_status = value
        emit("status", value)

    def emit_live(item):
        """Best-effort one-burst live IPC; never block the ingest path."""
        nonlocal live_ready, next_live_probe
        now = time.monotonic()

        if not live_ready:
            if now < next_live_probe:
                return
            next_live_probe = now + LIVE_PROBE_INTERVAL_S
            try:
                live_ready = LIVE_SOCKET.exists()
            except Exception:
                live_ready = False
            if not live_ready:
                return

        try:
            raw = json.dumps(item, separators=(",", ":")).encode("utf-8")
            if len(raw) > LIVE_PACKET_MAX:
                return
            live_socket.sendto(raw, str(LIVE_SOCKET))
        except (BlockingIOError, FileNotFoundError, ConnectionRefusedError):
            live_ready = False
            next_live_probe = now + LIVE_PROBE_INTERVAL_S
        except OSError:
            # Any AF_UNIX delivery failure is audio-only. Retry discovery later.
            live_ready = False
            next_live_probe = now + LIVE_PROBE_INTERVAL_S

    try:
        while not STOP.is_set():
            now = time.time()
            if not writer.is_alive():
                raise RuntimeError("voice snapshot writer exited unexpectedly")

            if child is None or child.poll() is not None:
                if child is not None:
                    try:
                        selector.unregister(child.stdout)
                    except Exception:
                        pass
                emit_status("connecting")
                pipe_buffer.clear()
                if STOP.wait(1.0):
                    break
                try:
                    child = spawn_subscriber()
                    child_started = time.time()
                    if child.stdout is not None:
                        os.set_blocking(child.stdout.fileno(), False)
                        selector.register(child.stdout, selectors.EVENT_READ)
                except Exception as exc:
                    print(f"voice subscriber start failed: {exc}", flush=True)
                    child = None
                    if STOP.wait(2.0):
                        break
                    continue

            for key, _mask in selector.select(timeout=0.05):
                lines, overflow = drain_subscriber(key.fileobj, pipe_buffer)
                if overflow:
                    emit("parse_error", 1)
                    continue
                for raw_line in lines:
                    item = parse_line(raw_line, next_seq)
                    if item is None:
                        emit("parse_error", 1)
                    else:
                        # Real-time consumers receive the cleaned burst directly.
                        # Diagnostic persistence remains independently queued.
                        emit_live(item)
                        emit("frame", item)
                        next_seq += 1
                        emit_status("online")

            now = time.time()
            if child is not None and child.poll() is None and now - child_started >= 2.0:
                emit_status("online")
    finally:
        STOP.set()
        if child is not None:
            try:
                child.terminate()
                child.wait(timeout=2)
            except Exception:
                try:
                    child.kill()
                except Exception:
                    pass
        try:
            emit("stop", None)
            writer.join(timeout=3.0)
        except Exception:
            pass
        if writer.is_alive():
            try:
                writer.terminate()
                writer.join(timeout=1.0)
            except Exception:
                pass
        try:
            events.close()
            events.join_thread()
        except Exception:
            pass
        try:
            live_socket.close()
        except Exception:
            pass
        print("YWD DMR voice bridge stopped", flush=True)


if __name__ == "__main__":
    main()
