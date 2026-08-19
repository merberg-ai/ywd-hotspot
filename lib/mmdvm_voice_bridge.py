#!/usr/bin/env python3
"""Consume passive MMDVM DMR voice MQTT into a bounded trusted runtime ring.

This process is first-party appliance infrastructure, not plugin code. It owns no
RF hardware and never talks to MMDVM serial. MMDVM-Host remains the sole modem
owner and publishes copies of accepted DMR voice frames to loopback MQTT.
"""
from __future__ import annotations

import json
import os
import re
import selectors
import signal
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
MAX_FRAMES = max(32, min(512, int(os.environ.get("YWD_MMDVM_VOICE_RING", "160"))))
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
        text=True,
        bufsize=1,
        close_fds=True,
    )


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    doc = initial_doc()
    frames = deque(maxlen=MAX_FRAMES)
    atomic_write(doc)
    child = None
    selector = selectors.DefaultSelector()
    child_started = 0.0
    dirty = False
    last_write = 0.0
    print(f"YWD DMR voice bridge starting: {HOST}:{PORT} topic={TOPIC} ring={MAX_FRAMES}", flush=True)
    try:
        while not STOP.is_set():
            now = time.time()
            if child is None or child.poll() is not None:
                if child is not None:
                    try:
                        selector.unregister(child.stdout)
                    except Exception:
                        pass
                doc["bridge"]["status"] = "connecting"
                doc["bridge"]["heartbeat_at"] = now
                doc["frames"] = list(frames)
                atomic_write(doc)
                dirty = False
                last_write = now
                if STOP.wait(1.0):
                    break
                try:
                    child = spawn_subscriber()
                    child_started = time.time()
                    if child.stdout is not None:
                        selector.register(child.stdout, selectors.EVENT_READ)
                except Exception as exc:
                    print(f"voice subscriber start failed: {exc}", flush=True)
                    child = None
                    if STOP.wait(2.0):
                        break
                    continue

            for key, _mask in selector.select(timeout=0.10):
                line = key.fileobj.readline()
                if not line:
                    continue
                try:
                    envelope = json.loads(line)
                    raw = envelope.get("DMRVoice") if isinstance(envelope, dict) and len(envelope) == 1 else None
                    item = clean_frame(raw, int(doc["next_seq"]))
                except Exception:
                    item = None
                if item is None:
                    doc["bridge"]["parse_errors"] += 1
                else:
                    frames.append(item)
                    doc["next_seq"] = item["seq"] + 1
                    doc["bridge"]["messages"] += 1
                    doc["bridge"]["status"] = "online"
                dirty = True

            now = time.time()
            if child is not None and child.poll() is None and now - child_started >= 2.0:
                doc["bridge"]["status"] = "online"
            doc["bridge"]["heartbeat_at"] = now
            if dirty and now - last_write >= 0.10 or now - last_write >= 1.0:
                doc["frames"] = list(frames)
                atomic_write(doc)
                dirty = False
                last_write = now
    finally:
        if child is not None:
            try:
                child.terminate()
                child.wait(timeout=2)
            except Exception:
                try:
                    child.kill()
                except Exception:
                    pass
        doc["bridge"]["status"] = "stopped"
        doc["bridge"]["heartbeat_at"] = time.time()
        doc["frames"] = list(frames)
        try:
            atomic_write(doc)
        except Exception:
            pass
        print("YWD DMR voice bridge stopped", flush=True)


if __name__ == "__main__":
    main()
