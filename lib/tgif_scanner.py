#!/usr/bin/env python3
"""Runtime TGIF watchlist scanner for YWD-Hotspot.

The scanner changes only the TGIF network session using TGIF's public
session-update endpoint. It never keys RF and never changes DMRGateway routing.
A radio must use Open RX / Promiscuous / Digital Monitor (or otherwise accept
all scanned destinations) to hear arbitrary watchlist traffic.
"""
from __future__ import annotations

import json
import os
import signal
import time
import urllib.error
import urllib.request
from pathlib import Path

CFG = Path(os.environ.get("YWD_CONFIG", "/etc/ywd-hotspot/config.json"))
PREFS = Path(os.environ.get("YWD_TGIF_CONTROL", "/var/lib/ywd-hotspot/tgif-control.json"))
ACTIVITY = Path(os.environ.get("YWD_ACTIVITY_STATE", "/run/ywd-hotspot/activity.json"))
RUNTIME = Path(os.environ.get("YWD_TGIF_SCANNER_STATE", "/run/ywd-hotspot/tgif-scanner.json"))
COMMAND = Path(os.environ.get("YWD_TGIF_SCANNER_COMMAND", "/run/ywd-hotspot/tgif-scanner-command.json"))
SESSION_API = os.environ.get(
    "YWD_TGIF_SESSION_API",
    "http://tgif.network:5040/api/sessions/update",
).rstrip("/")
RF_BASE = 5_000_000
RF_MAX_NETWORK_TG = 999_999
DISCONNECT_TG = 4000
DEFAULTS = {
    "schema": 1,
    "favorites": [],
    "watchlist": [],
    "dwell_s": 5,
    "hold_s": 3,
    "slot": 2,
}
STOP_REQUESTED = False


def _json(path: Path, default):
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj
    except Exception:
        return default


def _int(value, default=None):
    try:
        return int(value)
    except Exception:
        return default


def _clean_name(value) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())[:120]


def valid_tg(value, allow_disconnect=False):
    ident = _int(value)
    if ident is None or not 1 <= ident <= RF_MAX_NETWORK_TG:
        return None
    if ident == DISCONNECT_TG and not allow_disconnect:
        return None
    return ident


def normalize_preferences(raw, radio_mode="simplex") -> dict:
    raw = raw if isinstance(raw, dict) else {}
    out = dict(DEFAULTS)

    try:
        dwell = int(raw.get("dwell_s", out["dwell_s"]))
    except Exception:
        dwell = out["dwell_s"]
    out["dwell_s"] = max(2, min(60, dwell))

    try:
        hold = int(raw.get("hold_s", out["hold_s"]))
    except Exception:
        hold = out["hold_s"]
    out["hold_s"] = max(0, min(30, hold))

    mode = str(radio_mode or "simplex").strip().lower()
    if mode == "duplex":
        slot = _int(raw.get("slot"), 2)
        out["slot"] = slot if slot in {1, 2} else 2
    else:
        out["slot"] = 2

    favorites = []
    seen = set()
    for row in raw.get("favorites", []) if isinstance(raw.get("favorites"), list) else []:
        if not isinstance(row, dict):
            continue
        ident = valid_tg(row.get("id"))
        if ident is None or ident in seen:
            continue
        seen.add(ident)
        favorites.append({"id": ident, "name": _clean_name(row.get("name"))})
        if len(favorites) >= 100:
            break
    out["favorites"] = favorites

    watch = []
    seen.clear()
    for index, row in enumerate(raw.get("watchlist", []) if isinstance(raw.get("watchlist"), list) else []):
        if not isinstance(row, dict):
            continue
        ident = valid_tg(row.get("id"))
        if ident is None or ident in seen:
            continue
        seen.add(ident)
        try:
            priority = int(row.get("priority", index + 1))
        except Exception:
            priority = index + 1
        priority = max(1, min(10, priority))
        watch.append({
            "id": ident,
            "name": _clean_name(row.get("name")),
            "priority": priority,
            "enabled": bool(row.get("enabled", True)),
        })
        if len(watch) >= 10:
            break
    watch.sort(key=lambda row: (int(row["priority"]), int(row["id"])))
    out["watchlist"] = watch
    return out


def canonical_config() -> dict:
    return _json(CFG, {}) if CFG.is_file() else {}


def preferences(cfg=None) -> dict:
    cfg = cfg if isinstance(cfg, dict) else canonical_config()
    mode = str((cfg.get("radio") or {}).get("mode") or "simplex")
    return normalize_preferences(_json(PREFS, {}), mode)


def _atomic_runtime(doc: dict) -> None:
    RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    tmp = RUNTIME.with_name(RUNTIME.name + ".tmp")
    tmp.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o640)
    os.replace(tmp, RUNTIME)


def runtime_state(**updates) -> dict:
    doc = _json(RUNTIME, {})
    if not isinstance(doc, dict):
        doc = {}
    doc.setdefault("schema", 1)
    doc.update(updates)
    doc["updated_at"] = time.time()
    _atomic_runtime(doc)
    return doc


def network_identity(cfg: dict) -> int:
    station = cfg.get("station") if isinstance(cfg.get("station"), dict) else {}
    ident = _int(station.get("hotspot_id"))
    if ident is None or not 1 <= ident <= 999_999_999:
        raise RuntimeError("TGIF scanner cannot determine a valid hotspot DMR ID")
    return ident


def api_slot(slot: int) -> int:
    slot = int(slot)
    if slot not in {1, 2}:
        raise ValueError("TGIF scanner timeslot must be 1 or 2")
    return slot - 1


def session_update(hotspot_id: int, slot: int, talkgroup: int, timeout=8) -> dict:
    hotspot_id = int(hotspot_id)
    talkgroup = valid_tg(talkgroup, allow_disconnect=True)
    if talkgroup is None:
        raise ValueError("invalid TGIF talkgroup")
    endpoint = f"{SESSION_API}/{hotspot_id}/{api_slot(slot)}/{talkgroup}"
    req = urllib.request.Request(endpoint, headers={"User-Agent": "YWD-Hotspot/TGIF-Scanner"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            body = response.read(512).decode("utf-8", "replace").strip()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"TGIF session update failed: {exc}") from exc
    if status != 200:
        raise RuntimeError(f"TGIF session update returned HTTP {status}")
    return {"ok": True, "status": status, "response": body[:120], "talkgroup": talkgroup, "slot": slot}


def _event_matches(event, talkgroup: int, slot: int, tuned_at: float) -> bool:
    if not isinstance(event, dict):
        return False
    if str(event.get("path") or "").upper() != "NETWORK":
        return False
    if _int(event.get("slot")) != int(slot):
        return False
    destination = event.get("destination") if isinstance(event.get("destination"), dict) else {}
    if not destination.get("group"):
        return False
    if _int(destination.get("id")) != RF_BASE + int(talkgroup):
        return False
    started = float(event.get("started_at") or 0)
    return started >= max(0.0, float(tuned_at) - 1.0)


def traffic_hold(talkgroup: int, slot: int, tuned_at: float, hold_s: int, now=None):
    """Return (holding, reason, until) for locally observed TGIF network traffic."""
    now = float(time.time() if now is None else now)
    doc = _json(ACTIVITY, {})
    current = doc.get("current") if isinstance(doc, dict) else None
    if _event_matches(current, talkgroup, slot, tuned_at):
        if current.get("active"):
            return True, "traffic", None
        ended = float(current.get("ended_at") or 0)
        if ended and now < ended + hold_s:
            return True, "post-call", ended + hold_s

    rows = doc.get("lastheard") if isinstance(doc, dict) and isinstance(doc.get("lastheard"), list) else []
    for event in rows[:6]:
        if not _event_matches(event, talkgroup, slot, tuned_at):
            continue
        if event.get("active"):
            return True, "traffic", None
        ended = float(event.get("ended_at") or 0)
        if ended and now < ended + hold_s:
            return True, "post-call", ended + hold_s
    return False, None, None


def enabled_watchlist(prefs: dict):
    return [row for row in prefs.get("watchlist", []) if row.get("enabled")]


def read_command():
    try:
        doc = json.loads(COMMAND.read_text(encoding="utf-8"))
    except Exception:
        return None
    try:
        COMMAND.unlink()
    except Exception:
        pass
    return doc if isinstance(doc, dict) else None


def _signal_stop(_signum, _frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True


def main() -> int:
    signal.signal(signal.SIGTERM, _signal_stop)
    signal.signal(signal.SIGINT, _signal_stop)

    cfg = canonical_config()
    tg_cfg = cfg.get("tgif") if isinstance(cfg.get("tgif"), dict) else {}
    if not tg_cfg.get("enabled"):
        runtime_state(state="disabled", active=False, error="TGIF network is disabled")
        return 0

    prefs = preferences(cfg)
    watch = enabled_watchlist(prefs)
    if not watch:
        runtime_state(state="idle", active=False, error="TGIF watchlist is empty")
        return 0

    hotspot_id = network_identity(cfg)
    current_tg = None
    current_name = ""
    current_index = -1
    tuned_at = 0.0
    dwell_until = 0.0
    manual_hold = False
    last_error = None

    runtime_state(
        state="starting",
        active=True,
        hotspot_id=hotspot_id,
        slot=prefs["slot"],
        current_tg=None,
        current_rf_tg=None,
        manual_hold=False,
        error=None,
    )

    while not STOP_REQUESTED:
        cfg = canonical_config()
        tg_cfg = cfg.get("tgif") if isinstance(cfg.get("tgif"), dict) else {}
        if not tg_cfg.get("enabled"):
            last_error = "TGIF network was disabled while scanning"
            break

        prefs = preferences(cfg)
        watch = enabled_watchlist(prefs)
        if not watch:
            last_error = "TGIF watchlist is empty"
            break

        force_next = False
        command = read_command()
        if command:
            op = str(command.get("operation") or "").strip().lower()
            if op == "hold":
                manual_hold = True
            elif op == "resume":
                manual_hold = False
                dwell_until = time.time() + prefs["dwell_s"]
            elif op == "next":
                manual_hold = False
                force_next = True

        ids = [int(row["id"]) for row in watch]
        if current_tg not in ids:
            current_index = -1
            current_tg = None
        else:
            # Re-anchor to the live watchlist order so editing/reordering the list
            # while scanning cannot leave the next-step index pointing elsewhere.
            current_index = ids.index(current_tg)

        now = time.time()
        holding = False
        hold_reason = None
        hold_until = None
        if current_tg is not None:
            holding, hold_reason, hold_until = traffic_hold(
                current_tg, prefs["slot"], tuned_at, prefs["hold_s"], now=now
            )

        # Traffic wins the dwell race. A call that appears at the exact end of a
        # dwell must be heard/held instead of being discarded by a timer advance.
        if manual_hold:
            state = "holding"
            reason = "manual"
        elif holding and not force_next:
            state = "holding"
            reason = hold_reason
            if hold_until is not None:
                dwell_until = max(dwell_until, float(hold_until))
        else:
            if current_tg is None or force_next or now >= dwell_until:
                current_index = (current_index + 1) % len(watch)
                row = watch[current_index]
                current_tg = int(row["id"])
                current_name = str(row.get("name") or "")
                try:
                    session_update(hotspot_id, prefs["slot"], current_tg)
                    tuned_at = time.time()
                    dwell_until = tuned_at + prefs["dwell_s"]
                    last_error = None
                except Exception as exc:
                    last_error = str(exc)[:500]
                    runtime_state(
                        state="error",
                        active=True,
                        current_tg=current_tg,
                        current_name=current_name,
                        current_rf_tg=RF_BASE + current_tg,
                        slot=prefs["slot"],
                        manual_hold=manual_hold,
                        error=last_error,
                    )
                    time.sleep(2.0)
                    dwell_until = 0.0
                    continue
            state = "scanning"
            reason = None

        runtime_state(
            state=state,
            active=True,
            current_tg=current_tg,
            current_name=current_name,
            current_rf_tg=RF_BASE + current_tg,
            slot=prefs["slot"],
            manual_hold=manual_hold,
            hold_reason=reason,
            tuned_at=tuned_at,
            dwell_until=dwell_until,
            dwell_remaining_s=max(0.0, dwell_until - time.time()) if not manual_hold else None,
            watch_count=len(watch),
            error=last_error,
        )
        time.sleep(0.35)

    runtime_state(
        state="stopped",
        active=False,
        current_tg=current_tg,
        current_name=current_name,
        current_rf_tg=(RF_BASE + current_tg) if current_tg else None,
        manual_hold=manual_hold,
        error=last_error,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
