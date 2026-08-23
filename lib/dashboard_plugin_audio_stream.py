#!/usr/bin/env python3
"""Trusted Phase 3J streamed RX-audio bridge for sandboxed UI plugins.

The browser no longer polls DMR frames and POSTs each vocoder batch for live
audio.  One bounded HTTP stream performs trusted frame selection/recovery and
vocoder calls inside core, then emits only PCM/events to the parent WebUI.

The existing DMR frame polling API remains available for visual diagnostics.
"""
from __future__ import annotations

import base64
import json
import os
import select
import socket
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import dashboard_plugin_vocoder
import dashboard_plugins
import dmr_ambe49
import vocoder_client

FRAME_MS = 20
CHUNK_FRAMES = 10
CALL_GAP_MS = 500
AUTO_LOCK_GAP_MS = 450
MAX_BURST_BACKLOG = 16  # 16 DMR bursts ~= 960 ms / 48 AMBE frames
LIVE_SOCKET = Path(
    os.environ.get(
        "YWD_MMDVM_VOICE_LIVE_SOCKET",
        "/run/ywd-hotspot-voice/live-audio.sock",
    )
)
LIVE_PACKET_MAX = 4096
LIVE_RECV_BATCH = 64
LIVE_WAIT_MAX_S = 0.20
HEARTBEAT_S = 1.0
KEEPALIVE_S = 3.0
AUTH_RECHECK_S = 1.0
_STREAM_LOCK = threading.Lock()


def _route_key(frame):
    return (
        str(frame.get("source") or ""),
        int(frame.get("slot") or 0),
        int(frame.get("src_id") or 0),
        int(frame.get("dst_id") or 0),
        bool(frame.get("group")),
    )


def _route_doc(frame):
    return {
        "source": str(frame.get("source") or "")[:16],
        "slot": int(frame.get("slot") or 0),
        "src": int(frame.get("src_id") or 0),
        "dst": int(frame.get("dst_id") or 0),
        "group": bool(frame.get("group")),
    }


def _frame_time_ms(frame):
    try:
        value = float(frame.get("received_at") or 0.0)
        if value > 0:
            return value * 1000.0
    except Exception:
        pass
    return time.time() * 1000.0


def _parse_options(query):
    qs = parse_qs(query, keep_blank_values=False)
    source = str((qs.get("source") or ["network"])[0]).strip().lower()
    if source not in {"network", "rf", "all"}:
        raise ValueError("audio stream source must be network, rf, or all")
    slot_text = str((qs.get("slot") or ["auto"])[0]).strip().lower()
    if slot_text == "auto":
        slot = "auto"
    else:
        try:
            slot = int(slot_text)
        except Exception as exc:
            raise ValueError("audio stream slot must be auto, 1, or 2") from exc
        if slot not in {1, 2}:
            raise ValueError("audio stream slot must be auto, 1, or 2")
    return source, slot


def _open_live_receiver():
    """Own the single live-audio AF_UNIX datagram endpoint."""
    parent = LIVE_SOCKET.parent
    if not parent.is_dir():
        raise RuntimeError(f"DMR voice runtime directory is unavailable: {parent}")

    try:
        LIVE_SOCKET.unlink()
    except FileNotFoundError:
        pass

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        sock.setblocking(False)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        sock.bind(str(LIVE_SOCKET))
        os.chmod(LIVE_SOCKET, 0o600)
        return sock
    except Exception:
        try:
            sock.close()
        except Exception:
            pass
        try:
            LIVE_SOCKET.unlink()
        except FileNotFoundError:
            pass
        raise


def _close_live_receiver(sock):
    try:
        if sock is not None:
            sock.close()
    finally:
        try:
            LIVE_SOCKET.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass


def _recv_live_frames(sock, limit=LIVE_RECV_BATCH):
    """Drain currently queued burst datagrams without ever blocking."""
    frames = []
    invalid = 0
    for _ in range(max(1, min(int(limit), LIVE_RECV_BATCH))):
        try:
            raw = sock.recv(LIVE_PACKET_MAX)
        except BlockingIOError:
            break
        except InterruptedError:
            continue
        except OSError:
            break

        try:
            frame = json.loads(raw.decode("utf-8"))
        except Exception:
            invalid += 1
            continue

        if (
            not isinstance(frame, dict)
            or not isinstance(frame.get("seq"), int)
            or not isinstance(frame.get("frame_hex"), str)
        ):
            invalid += 1
            continue
        frames.append(frame)

    return frames, invalid


def _authorized(ident):
    # Both capabilities remain independently fail-closed and immediately
    # revocable through their existing cached-manifest authorization paths.
    dashboard_plugins._voice_plugin(ident)
    dashboard_plugin_vocoder._plugin(ident)


def _write_event(handler, event):
    try:
        raw = (json.dumps(event, separators=(",", ":")) + "\n").encode("utf-8")
        handler.wfile.write(raw)
        handler.wfile.flush()
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False


def _send_stream_headers(handler):
    handler.send_response(200)
    handler.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.close_connection = True


def stream_audio(handler, ident, source_filter, slot_filter):
    """Run one bounded audio stream until the browser disconnects."""
    if not _STREAM_LOCK.acquire(blocking=False):
        handler.send_json({"error": "another RX audio stream is already active"}, 409)
        return

    live_sock = None
    try:
        try:
            _authorized(ident)
            status = vocoder_client.status()
            if not status.get("available"):
                handler.send_json({"error": str(status.get("error") or "vocoder backend unavailable")[:500]}, 503)
                return
            reset_started = time.monotonic()
            vocoder_client.reset()
            initial_reset_ms = (time.monotonic() - reset_started) * 1000.0
            live_sock = _open_live_receiver()
        except ValueError as exc:
            handler.send_json({"error": str(exc)[:500]}, 409)
            return
        except vocoder_client.VocoderUnavailable as exc:
            handler.send_json({"error": str(exc)[:500]}, 503)
            return
        except vocoder_client.VocoderBackendError as exc:
            handler.send_json({"error": str(exc)[:500]}, 502)
            return
        except Exception as exc:
            handler.send_json({"error": str(exc)[:800]}, 502)
            return

        _send_stream_headers(handler)
        if not _write_event(handler, {
            "type": "hello",
            "schema": 1,
            "stream": "ywd-rx-audio",
            "voice_transport": "unix-dgram",
            "plugin": ident,
            "backend": str(status.get("backend") or "external")[:80],
            "protocol": int(status.get("protocol") or 1),
            "sample_rate": 8000,
            "samples_per_frame": 160,
            "channels": 1,
            "sample_format": "s16le",
            "chunk_frames": CHUNK_FRAMES,
            "chunk_ms": CHUNK_FRAMES * FRAME_MS,
            "source": source_filter,
            "slot": slot_filter,
            "initial_reset_ms": round(initial_reset_ms, 3),
        }):
            return

        # Binding the live datagram endpoint inherently starts at the live
        # edge: no historical diagnostic-ring frames are ever replayed.
        cursor = 0
        ipc_errors = 0
        ambe_queue = []
        previous_key = None
        last_source_ms = 0.0
        auto_key = None
        auto_slot = 0
        auto_last_ms = 0.0
        chunk_seq = 0
        dropped_bursts = 0
        dropped_ambe = 0
        recovered_frames = 0
        unrecoverable_frames = 0
        corrected_bits = 0
        decode_max_ms = 0.0
        reset_max_ms = initial_reset_ms
        last_route = None
        last_heartbeat = time.monotonic()
        last_vocoder_activity = time.monotonic()
        last_auth = time.monotonic()
        need_reset = False

        def send(event):
            event.setdefault("stream_seq", chunk_seq)
            return _write_event(handler, event)

        def do_reset(reason):
            nonlocal ambe_queue, need_reset, reset_max_ms, last_vocoder_activity
            ambe_queue = []
            started = time.monotonic()
            vocoder_client.reset()
            elapsed = (time.monotonic() - started) * 1000.0
            reset_max_ms = max(reset_max_ms, elapsed)
            last_vocoder_activity = time.monotonic()
            need_reset = False
            return send({"type": "reset", "reason": reason, "reset_ms": round(elapsed, 3)})

        while True:
            now = time.monotonic()

            if now - last_auth >= AUTH_RECHECK_S:
                try:
                    _authorized(ident)
                except Exception as exc:
                    send({"type": "error", "fatal": True, "error": str(exc)[:500]})
                    return
                last_auth = now

            # Successful RESET/DECODE traffic itself proves that the persistent
            # backend session is alive. Probe STATUS only after the vocoder has
            # actually been idle, keeping control traffic off the hot audio path.
            if now - last_vocoder_activity >= KEEPALIVE_S:
                keep = vocoder_client.status()
                last_vocoder_activity = time.monotonic()
                if not keep.get("available"):
                    send({"type": "error", "fatal": False, "error": str(keep.get("error") or "vocoder keepalive failed")[:500]})
                    need_reset = True

            # Sleep inside the stream thread until a burst arrives or one of
            # the periodic auth/idle-vocoder/heartbeat deadlines becomes due.
            # This replaces 25 ms filesystem polling/stat/JSON parsing.
            waits = [
                max(0.0, AUTH_RECHECK_S - (now - last_auth)),
                max(0.0, KEEPALIVE_S - (now - last_vocoder_activity)),
                max(0.0, HEARTBEAT_S - (now - last_heartbeat)),
            ]
            wait_s = min([LIVE_WAIT_MAX_S, *waits])
            try:
                readable, _, _ = select.select([live_sock], [], [], wait_s)
            except InterruptedError:
                readable = []

            frames = []
            if readable:
                frames, invalid = _recv_live_frames(live_sock)
                ipc_errors += invalid
                if frames:
                    cursor = int(frames[-1].get("seq") or cursor)

            # A slow decoder may allow multiple datagrams to accumulate. Keep
            # only a bounded live tail; dropping audio is always preferable to
            # applying backpressure to the bridge/MMDVM path.
            if len(frames) > MAX_BURST_BACKLOG:
                drop_count = len(frames) - MAX_BURST_BACKLOG
                dropped_bursts += drop_count
                frames = frames[-MAX_BURST_BACKLOG:]
                dropped_ambe += len(ambe_queue)
                ambe_queue = []
                need_reset = True
                if not send({
                    "type": "drop",
                    "reason": "live-ipc-backlog",
                    "dropped_bursts": dropped_bursts,
                    "dropped_ambe": dropped_ambe,
                }):
                    return

            for frame in frames:
                if not isinstance(frame, dict):
                    continue
                source = str(frame.get("source") or "")
                if source_filter != "all" and source != source_filter:
                    continue
                slot = int(frame.get("slot") or 0)
                if slot_filter != "auto" and slot != slot_filter:
                    continue

                key = _route_key(frame)
                source_ms = _frame_time_ms(frame)

                if slot_filter == "auto":
                    if auto_key is None:
                        auto_key, auto_slot, auto_last_ms = key, slot, source_ms
                    elif key == auto_key:
                        auto_last_ms = max(auto_last_ms, source_ms)
                    elif slot == auto_slot:
                        auto_key, auto_slot, auto_last_ms = key, slot, source_ms
                    elif auto_last_ms and source_ms - auto_last_ms >= AUTO_LOCK_GAP_MS:
                        auto_key, auto_slot, auto_last_ms = key, slot, source_ms
                    else:
                        continue

                route_changed = previous_key is not None and key != previous_key
                gap_detected = bool(last_source_ms and source_ms - last_source_ms > CALL_GAP_MS)
                if route_changed or gap_detected:
                    dropped_ambe += len(ambe_queue)
                    ambe_queue = []
                    need_reset = True

                if need_reset:
                    try:
                        if not do_reset("route-change" if route_changed else "gap/backlog"):
                            return
                    except Exception as exc:
                        send({"type": "error", "fatal": False, "error": f"vocoder reset failed: {exc}"[:500]})
                        need_reset = True
                        continue

                previous_key = key
                last_source_ms = source_ms
                last_route = _route_doc(frame)

                recovery_started = time.monotonic()
                try:
                    recovered = dmr_ambe49.recover_burst(frame.get("frame_hex"))
                except Exception:
                    unrecoverable_frames += 3
                    continue
                recovery_ms = (time.monotonic() - recovery_started) * 1000.0

                for item in recovered:
                    if not item.get("valid"):
                        unrecoverable_frames += 1
                        continue
                    recovered_frames += 1
                    corrected_bits += int(item.get("corrected") or 0)
                    ambe_queue.append(str(item["bits"]))

                # The route may have accumulated more than one decode batch
                # from one ring snapshot.  Work sequentially but keep only a
                # small bounded tail if decode cannot keep up.
                while len(ambe_queue) >= CHUNK_FRAMES:
                    batch = ambe_queue[:CHUNK_FRAMES]
                    del ambe_queue[:CHUNK_FRAMES]
                    decode_started = time.monotonic()
                    try:
                        decoded = vocoder_client.decode(batch)
                    except (vocoder_client.VocoderUnavailable, vocoder_client.VocoderBackendError) as exc:
                        last_vocoder_activity = time.monotonic()
                        dropped_ambe += len(batch) + len(ambe_queue)
                        ambe_queue = []
                        need_reset = True
                        if not send({"type": "error", "fatal": False, "error": str(exc)[:500]}):
                            return
                        break
                    decode_ms = (time.monotonic() - decode_started) * 1000.0
                    last_vocoder_activity = time.monotonic()
                    decode_max_ms = max(decode_max_ms, decode_ms)
                    pcm = decoded.pop("pcm_s16le")
                    chunk_seq += 1
                    if not send({
                        "type": "pcm",
                        "seq": chunk_seq,
                        "frame_count": int(decoded.get("frame_count") or CHUNK_FRAMES),
                        "sample_rate": int(decoded.get("sample_rate") or 8000),
                        "samples_per_frame": int(decoded.get("samples_per_frame") or 160),
                        "channels": int(decoded.get("channels") or 1),
                        "sample_format": str(decoded.get("sample_format") or "s16le"),
                        "pcm_s16le_b64": base64.b64encode(pcm).decode("ascii"),
                        "pcm_bytes": len(pcm),
                        "decode_ms": round(decode_ms, 3),
                        "decode_max_ms": round(decode_max_ms, 3),
                        "recovery_ms": round(recovery_ms, 3),
                        "route": last_route,
                        "dropped_bursts": dropped_bursts,
                        "dropped_ambe": dropped_ambe,
                        "recovered_frames": recovered_frames,
                        "unrecoverable_frames": unrecoverable_frames,
                        "corrected_bits": corrected_bits,
                    }):
                        return

            now = time.monotonic()
            if now - last_heartbeat >= HEARTBEAT_S:
                if not send({
                    "type": "heartbeat",
                    "voice_transport": "unix-dgram",
                    "ipc_errors": ipc_errors,
                    "cursor": cursor,
                    "queued_ambe": len(ambe_queue),
                    "route": last_route,
                    "dropped_bursts": dropped_bursts,
                    "dropped_ambe": dropped_ambe,
                    "recovered_frames": recovered_frames,
                    "unrecoverable_frames": unrecoverable_frames,
                    "corrected_bits": corrected_bits,
                    "decode_max_ms": round(decode_max_ms, 3),
                    "reset_max_ms": round(reset_max_ms, 3),
                }):
                    return
                last_heartbeat = now
    finally:
        _close_live_receiver(live_sock)
        _STREAM_LOCK.release()


def wrap_handler(base):
    class PluginAudioStreamHandler(base):
        def do_GET(self):
            parsed = urlparse(self.path)
            parts = parsed.path.strip("/").split("/")
            if not (len(parts) == 5 and parts[:3] == ["api", "plugins", "ui"] and parts[4] == "audio-stream"):
                super().do_GET()
                return
            ident = parts[3]
            if not self.require_control():
                return
            try:
                source, slot = _parse_options(parsed.query)
            except ValueError as exc:
                self.send_json({"error": str(exc)[:500]}, 400)
                return
            stream_audio(self, ident, source, slot)

    PluginAudioStreamHandler.__name__ = f"PluginAudioStream{base.__name__}"
    return PluginAudioStreamHandler