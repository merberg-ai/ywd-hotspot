#!/usr/bin/env python3
"""Consume MMDVM-Host MQTT JSON into a sanitized local runtime snapshot."""
from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import mmdvm_session

STATE = Path(os.environ.get("YWD_MMDVM_TELEMETRY", "/run/ywd-hotspot-telemetry/telemetry.json"))
HOST = os.environ.get("YWD_MQTT_HOST", "127.0.0.1")
PORT = int(os.environ.get("YWD_MQTT_PORT", "18883"))
TOPIC = os.environ.get("YWD_MQTT_TOPIC", "ywd-mmdvm/json")
STOP = threading.Event()


def stop(_signum, _frame):
    STOP.set()


def atomic_write(doc):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".mmdvm-telemetry.", dir=str(STATE.parent), text=True)
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


def clean_text(value, limit=160):
    return str(value or "").replace("\n", " ").replace("\r", " ")[:limit]


def clean_scalar(value):
    return value if value is None or isinstance(value, (bool, int, float)) else clean_text(value)


def clean_map(raw, keys):
    if not isinstance(raw, dict):
        return {}
    return {key: clean_scalar(raw.get(key)) for key in keys if key in raw}


def initial_state():
    now = time.time()
    return {"schema":1,"bridge":{"status":"starting","heartbeat_at":now,"started_at":now,"messages":0,"parse_errors":0,"topic":TOPIC},"mmdvm":{},"rssi":{},"ber":{},"text":{},"dmr":{"active":None,"last":None},"sessions":mmdvm_session.initial_sessions(),"last_payload_at":None}


def handle_payload(doc, payload):
    try:
        envelope = json.loads(payload)
    except Exception:
        doc["bridge"]["parse_errors"] += 1
        return
    if not isinstance(envelope, dict) or len(envelope) != 1:
        doc["bridge"]["parse_errors"] += 1
        return
    now = time.time()
    kind, raw = next(iter(envelope.items()))
    if not isinstance(raw, dict):
        doc["bridge"]["parse_errors"] += 1
        return
    if kind == "MMDVM":
        item = clean_map(raw, ("timestamp","mode","message")); item["received_at"] = now; doc["mmdvm"] = item
    elif kind == "RSSI":
        item = clean_map(raw, ("timestamp","mode","slot","value")); item["received_at"] = now; doc["rssi"] = item
    elif kind == "BER":
        item = clean_map(raw, ("timestamp","mode","slot","value")); item["received_at"] = now; doc["ber"] = item
    elif kind == "Text":
        item = clean_map(raw, ("timestamp","mode","slot","value")); item["received_at"] = now; doc["text"] = item
    elif kind == "DMR":
        item = clean_map(raw, ("timestamp","src_id","src_info","dst_id","group","slot","source","action","csbk_desc","frames","duration","loss","ber"))
        if isinstance(raw.get("rssi"), dict): item["rssi"] = clean_map(raw["rssi"], ("min","max","ave"))
        item["received_at"] = now
        doc["dmr"]["last"] = item
        action = str(item.get("action") or "")
        if action in {"start","late_entry"}: doc["dmr"]["active"] = item
        elif action in {"end","lost","timeout","rejected","invalid"}:
            active = doc["dmr"].get("active")
            if not isinstance(active, dict) or active.get("slot") == item.get("slot"): doc["dmr"]["active"] = None
        doc["sessions"] = mmdvm_session.observe(doc.get("sessions"), item)
    else:
        return
    doc["bridge"]["messages"] += 1
    doc["last_payload_at"] = now


def spawn_subscriber():
    return subprocess.Popen(["/usr/bin/mosquitto_sub","-h",HOST,"-p",str(PORT),"-t",TOPIC,"-q","0"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1, close_fds=True)


def main():
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    doc = initial_state(); atomic_write(doc)
    child = None; selector = selectors.DefaultSelector(); last_write = 0.0; child_started = 0.0
    print(f"YWD MMDVM telemetry bridge starting: {HOST}:{PORT} topic={TOPIC}", flush=True)
    try:
        while not STOP.is_set():
            now = time.time()
            if child is None or child.poll() is not None:
                if child is not None:
                    try: selector.unregister(child.stdout)
                    except Exception: pass
                doc["bridge"]["status"] = "connecting"; doc["bridge"]["heartbeat_at"] = now; atomic_write(doc)
                if STOP.wait(1.0): break
                try:
                    child = spawn_subscriber(); child_started = time.time()
                    if child.stdout is not None: selector.register(child.stdout, selectors.EVENT_READ)
                except Exception as exc:
                    print(f"telemetry subscriber start failed: {exc}", flush=True); child = None
                    if STOP.wait(2.0): break
                    continue
            for key, _mask in selector.select(timeout=1.0):
                line = key.fileobj.readline()
                if line:
                    handle_payload(doc, line.strip()); doc["bridge"]["status"] = "online"; atomic_write(doc); last_write = time.time()
            now = time.time()
            if child is not None and child.poll() is None and now - child_started >= 2.0: doc["bridge"]["status"] = "online"
            doc["bridge"]["heartbeat_at"] = now
            if now - last_write >= 2.0: atomic_write(doc); last_write = now
    finally:
        if child is not None:
            try: child.terminate(); child.wait(timeout=2)
            except Exception:
                try: child.kill()
                except Exception: pass
        doc["bridge"]["status"] = "stopped"; doc["bridge"]["heartbeat_at"] = time.time()
        try: atomic_write(doc)
        except Exception: pass
        print("YWD MMDVM telemetry bridge stopped", flush=True)


if __name__ == "__main__": main()
