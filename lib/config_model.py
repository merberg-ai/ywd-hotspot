#!/usr/bin/env python3
"""YWD-Hotspot canonical configuration normalization, validation and redaction."""
from __future__ import annotations

import copy
import hashlib
import ipaddress
import json
import re
from pathlib import Path

SCHEMA = 6
CALL_RE = re.compile(r"^[A-Z0-9]{3,10}(?:-[A-Z0-9]{1,2})?$")
HOST_RE = re.compile(r"^[A-Za-z0-9.-]+$")


def defaults() -> dict:
    return {
        "schema": SCHEMA,
        "station": {
            "callsign": "NOCALL",
            "base_dmr_id": "",
            "essid": "01",
            "hotspot_id": 0,
            "location": "Hotspot",
            "description": "YWD Hotspot",
            "latitude": 0.0,
            "longitude": 0.0,
            "height": 0,
            "url": "",
        },
        "radio": {
            "mode": "simplex",
            "frequency_hz": 446525000,
            "rx_frequency_hz": 446525000,
            "tx_frequency_hz": 446525000,
            "color_code": 1,
            "rx_offset": 0,
            "tx_offset": 0,
            "tx_invert": 1,
            "rx_invert": 0,
            "rx_level": 50,
            "tx_level": 50,
            "rf_level": 100,
            "jitter_ms": 360,
            "call_hang_s": 3,
            "tx_hang_s": 4,
            "timeout_s": 180,
            "uart": "/dev/serial0",
            "uart_speed": 115200,
        },
        "brandmeister": {
            "enabled": True,
            "master": "3103.master.brandmeister.network",
            "port": 62031,
            "password": "",
        },
        "display": {
            "enabled": True,
            "i2c_bus": 1,
            "address": "0x3c",
            "brightness": 127,
            "idle_timeout_s": 0,
            "rotation": 0,
            "runtime_mode": "basic",
            "large_callsign": True,
            "callsign_size": "auto",
            "show_talkgroup": True,
            "talkgroup_format": "number",
            "show_slot": True,
            "show_elapsed": True,
            "show_ber": True,
            "show_rssi": True,
            "show_loss": True,
            "post_call_hold_s": 3,
            "idle_cycle": False,
            "idle_cycle_s": 6,
            "instrumentation": {
                "enabled": False,
                "preset": "basic",
                "signal_meter": True,
                "signal_style": "segmented",
                "signal_segments": 14,
                "rssi_min_dbm": -120,
                "rssi_max_dbm": -40,
                "peak_hold": True,
                "peak_hold_ms": 1500,
                "quality_meter": True,
                "ber_excellent": 1.0,
                "ber_good": 2.0,
                "ber_fair": 5.0,
                "tx_meter": True,
                "measurement_hold_s": 5,
                "history_rssi": True,
                "history_ber": True,
                "history_mode": "samples",
                "history_samples": 20,
                "history_max_age_s": 900,
                "history_seconds": 60,
                "render_fps": 10,
                "animation": "normal",
                "idle_animation": True,
                "live_status_strip": True,
                "show_numeric_values": True,
                "meter_labels": "full",
                "reduced_motion": "system",
            },
        },
        "web": {
            "bind": "0.0.0.0",
            "port": 8080,
        },
        "maintenance": {
            "rf_autostart": False,
            "persistent_journal": True,
            "journal_max_mb": 100,
            "dmrid_update_days": 7,
            "config_history_keep": 10,
        },
    }


def deep_merge(base: dict, incoming: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (incoming or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _int(v, name, lo, hi):
    try:
        n = int(v)
    except Exception:
        raise ValueError(f"{name} must be an integer")
    if not lo <= n <= hi:
        raise ValueError(f"{name} must be between {lo} and {hi}")
    return n


def _float(v, name, lo, hi):
    try:
        n = float(v)
    except Exception:
        raise ValueError(f"{name} must be a number")
    if not lo <= n <= hi:
        raise ValueError(f"{name} must be between {lo} and {hi}")
    return n


def _choice(v, name, allowed):
    s = str(v if v is not None else "").strip().lower()
    if s not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(allowed))}")
    return s


def _text(v, name, maxlen=160, allow_empty=True):
    s = str(v if v is not None else "").replace("\r", " ").replace("\n", " ").strip()
    if not allow_empty and not s:
        raise ValueError(f"{name} is required")
    if len(s) > maxlen:
        raise ValueError(f"{name} is too long")
    return s


def normalize(raw: dict, preserve_password: str | None = None) -> dict:
    """Migrate old schemas, fill defaults, validate, and return canonical schema 6."""
    if not isinstance(raw, dict):
        raise ValueError("configuration must be a JSON object")
    try:
        source_schema = int(raw.get("schema", 0) or 0)
    except Exception:
        source_schema = 0
    c = deep_merge(defaults(), raw)
    c["schema"] = SCHEMA

    st = c["station"]
    st["callsign"] = _text(st.get("callsign"), "callsign", 12, False).upper()
    if not CALL_RE.fullmatch(st["callsign"]):
        raise ValueError("callsign format is invalid")
    st["base_dmr_id"] = _text(st.get("base_dmr_id"), "base DMR ID", 8, False)
    if not st["base_dmr_id"].isdigit() or not 5 <= len(st["base_dmr_id"]) <= 8:
        raise ValueError("base DMR ID must be 5-8 digits")
    essid = _text(st.get("essid", "01"), "ESSID", 2, True)
    if essid:
        if not essid.isdigit() or not 1 <= int(essid) <= 99:
            raise ValueError("ESSID must be blank or 01-99")
        essid = f"{int(essid):02d}"
    st["essid"] = essid
    expected_hid = int(st["base_dmr_id"]) if not essid else int(f"{st['base_dmr_id']}{int(essid):02d}")
    st["hotspot_id"] = expected_hid
    st["location"] = _text(st.get("location"), "location", 20)
    st["description"] = _text(st.get("description"), "description", 20)
    st["latitude"] = _float(st.get("latitude", 0), "latitude", -90, 90)
    st["longitude"] = _float(st.get("longitude", 0), "longitude", -180, 180)
    st["height"] = _int(st.get("height", 0), "antenna height", 0, 9999)
    st["url"] = _text(st.get("url"), "station URL", 124)

    r = c["radio"]
    # Schema 6 introduces explicit simplex/duplex HAT mode and separate duplex
    # RX/TX frequencies. Existing appliances must remain simplex after update.
    if source_schema < 6:
        legacy_frequency = r.get("frequency_hz", 446525000)
        r["mode"] = "simplex"
        r["rx_frequency_hz"] = legacy_frequency
        r["tx_frequency_hz"] = legacy_frequency
    r["mode"] = _choice(r.get("mode", "simplex"), "HAT mode", {"simplex", "duplex"})
    r["frequency_hz"] = _int(r.get("frequency_hz"), "simplex frequency", 1000000, 1300000000)
    r["rx_frequency_hz"] = _int(r.get("rx_frequency_hz", r["frequency_hz"]), "duplex RX frequency", 1000000, 1300000000)
    r["tx_frequency_hz"] = _int(r.get("tx_frequency_hz", r["frequency_hz"]), "duplex TX frequency", 1000000, 1300000000)
    r["color_code"] = _int(r.get("color_code", 1), "color code", 0, 15)
    r["rx_offset"] = _int(r.get("rx_offset", 0), "RX offset", -10000, 10000)
    r["tx_offset"] = _int(r.get("tx_offset", 0), "TX offset", -10000, 10000)
    r["tx_invert"] = _int(r.get("tx_invert", 1), "TX invert", 0, 1)
    r["rx_invert"] = _int(r.get("rx_invert", 0), "RX invert", 0, 1)
    r["rx_level"] = _int(r.get("rx_level", 50), "RX level", 0, 100)
    r["tx_level"] = _int(r.get("tx_level", 50), "TX level", 0, 100)
    r["rf_level"] = _int(r.get("rf_level", 100), "RF level", 0, 100)
    r["jitter_ms"] = _int(r.get("jitter_ms", r.get("jitter", 360)), "DMR jitter", 60, 3000)
    r["call_hang_s"] = _int(r.get("call_hang_s", 3), "DMR call hang", 0, 30)
    r["tx_hang_s"] = _int(r.get("tx_hang_s", 4), "DMR TX hang", 0, 30)
    r["timeout_s"] = _int(r.get("timeout_s", 180), "RF timeout", 30, 900)
    r["uart"] = _text(r.get("uart", "/dev/serial0"), "UART path", 64, False)
    r["uart_speed"] = _int(r.get("uart_speed", 115200), "UART speed", 1200, 4000000)

    bm = c["brandmeister"]
    bm["enabled"] = bool(bm.get("enabled", True))
    bm["master"] = _text(bm.get("master"), "BrandMeister master", 128, False)
    if not HOST_RE.fullmatch(bm["master"]):
        raise ValueError("BrandMeister master hostname is invalid")
    bm["port"] = _int(bm.get("port", 62031), "BrandMeister port", 1, 65535)
    pw = bm.get("password", "")
    if (pw is None or pw == "") and preserve_password is not None:
        pw = preserve_password
    pw = str(pw)
    if any(ch in pw for ch in ('"', "\n", "\r")):
        raise ValueError("Hotspot Security password contains an unsupported character")
    if len(pw) > 20:
        raise ValueError("BrandMeister Hotspot Security password must be 20 characters or fewer")
    bm["password"] = pw

    d = c["display"]
    d["enabled"] = bool(d.get("enabled", True))
    d["i2c_bus"] = _int(d.get("i2c_bus", 1), "OLED I2C bus", 0, 32)
    d["address"] = _text(d.get("address", "0x3c"), "OLED address", 8, False).lower()
    try:
        addr = int(d["address"], 0)
    except Exception:
        raise ValueError("OLED address must look like 0x3c")
    if not 0x03 <= addr <= 0x77:
        raise ValueError("OLED address is outside the normal I2C range")
    d["address"] = hex(addr)
    d["brightness"] = _int(d.get("brightness", 127), "OLED brightness", 1, 255)
    d["idle_timeout_s"] = _int(d.get("idle_timeout_s", 0), "OLED idle timeout", 0, 86400)
    d["rotation"] = _int(d.get("rotation", 0), "OLED rotation", 0, 180)
    if d["rotation"] not in {0, 180}:
        raise ValueError("OLED rotation must be 0 or 180 degrees")
    d["runtime_mode"] = _choice(d.get("runtime_mode", "basic"), "OLED runtime mode", {"basic", "enhanced", "minimal"})
    d["large_callsign"] = bool(d.get("large_callsign", True))
    d["callsign_size"] = _choice(d.get("callsign_size", "auto"), "OLED callsign size", {"auto", "normal", "large", "huge"})
    d["show_talkgroup"] = bool(d.get("show_talkgroup", True))
    d["talkgroup_format"] = _choice(d.get("talkgroup_format", "number"), "OLED talkgroup format", {"number", "name", "name_number"})
    d["show_slot"] = bool(d.get("show_slot", True))
    d["show_elapsed"] = bool(d.get("show_elapsed", True))
    d["show_ber"] = bool(d.get("show_ber", True))
    d["show_rssi"] = bool(d.get("show_rssi", True))
    d["show_loss"] = bool(d.get("show_loss", True))
    d["post_call_hold_s"] = _int(d.get("post_call_hold_s", 3), "OLED post-call hold", 0, 30)
    d["idle_cycle"] = bool(d.get("idle_cycle", False))
    d["idle_cycle_s"] = _int(d.get("idle_cycle_s", 6), "OLED idle page interval", 2, 60)

    ins = d.get("instrumentation")
    if not isinstance(ins, dict):
        raise ValueError("display instrumentation must be an object")
    # Schema 4 used a short time-window history. Schema 5 switches to sample
    # history by default while preserving explicit values once schema 5 is saved.
    if source_schema < 5:
        ins.setdefault("measurement_hold_s", 5)
        ins.setdefault("history_mode", "samples")
        ins.setdefault("history_samples", 20)
        ins.setdefault("history_max_age_s", 900)
        if int(ins.get("history_seconds", 30) or 30) == 30:
            ins["history_seconds"] = 60
    ins["enabled"] = bool(ins.get("enabled", False))
    ins["preset"] = _choice(ins.get("preset", "basic"), "instrumentation preset", {"basic", "balanced", "instrument", "maximum", "custom"})
    ins["signal_meter"] = bool(ins.get("signal_meter", True))
    ins["signal_style"] = _choice(ins.get("signal_style", "segmented"), "signal meter style", {"segmented", "smooth"})
    ins["signal_segments"] = _int(ins.get("signal_segments", 14), "signal meter segments", 6, 24)
    ins["rssi_min_dbm"] = _int(ins.get("rssi_min_dbm", -120), "RSSI minimum", -160, -20)
    ins["rssi_max_dbm"] = _int(ins.get("rssi_max_dbm", -40), "RSSI maximum", -150, 0)
    if ins["rssi_min_dbm"] >= ins["rssi_max_dbm"]:
        raise ValueError("RSSI minimum must be lower than RSSI maximum")
    ins["peak_hold"] = bool(ins.get("peak_hold", True))
    ins["peak_hold_ms"] = _int(ins.get("peak_hold_ms", 1500), "signal peak hold", 0, 10000)
    ins["quality_meter"] = bool(ins.get("quality_meter", True))
    ins["ber_excellent"] = _float(ins.get("ber_excellent", 1.0), "BER excellent threshold", 0.0, 20.0)
    ins["ber_good"] = _float(ins.get("ber_good", 2.0), "BER good threshold", 0.0, 30.0)
    ins["ber_fair"] = _float(ins.get("ber_fair", 5.0), "BER fair threshold", 0.0, 50.0)
    if not ins["ber_excellent"] <= ins["ber_good"] <= ins["ber_fair"]:
        raise ValueError("BER thresholds must be ordered excellent <= good <= fair")
    ins["tx_meter"] = bool(ins.get("tx_meter", True))
    ins["measurement_hold_s"] = _int(ins.get("measurement_hold_s", 5), "instrument measurement hold", 0, 30)
    ins["history_rssi"] = bool(ins.get("history_rssi", True))
    ins["history_ber"] = bool(ins.get("history_ber", True))
    ins["history_mode"] = _choice(ins.get("history_mode", "samples"), "instrument history mode", {"samples", "time"})
    ins["history_samples"] = _int(ins.get("history_samples", 20), "instrument history samples", 5, 60)
    ins["history_max_age_s"] = _int(ins.get("history_max_age_s", 900), "instrument sample maximum age", 60, 3600)
    ins["history_seconds"] = _int(ins.get("history_seconds", 60), "instrument time history", 10, 600)
    ins["render_fps"] = _int(ins.get("render_fps", 10), "instrument render rate", 5, 20)
    if ins["render_fps"] not in {5, 10, 20}:
        raise ValueError("instrument render rate must be 5, 10, or 20 fps")
    ins["animation"] = _choice(ins.get("animation", "normal"), "instrument animation", {"off", "subtle", "normal", "high"})
    ins["idle_animation"] = bool(ins.get("idle_animation", True))
    ins["live_status_strip"] = bool(ins.get("live_status_strip", True))
    ins["show_numeric_values"] = bool(ins.get("show_numeric_values", True))
    ins["meter_labels"] = _choice(ins.get("meter_labels", "full"), "instrument meter labels", {"compact", "full"})
    ins["reduced_motion"] = _choice(ins.get("reduced_motion", "system"), "reduced motion mode", {"system", "reduce", "full"})

    w = c["web"]
    w["bind"] = _text(w.get("bind", "0.0.0.0"), "dashboard bind", 64, False)
    try:
        ipaddress.ip_address(w["bind"])
    except ValueError:
        raise ValueError("dashboard bind must be an IP address such as 0.0.0.0 or 127.0.0.1")
    w["port"] = _int(w.get("port", 8080), "dashboard port", 1024, 65535)

    m = c["maintenance"]
    m["rf_autostart"] = bool(m.get("rf_autostart", True))
    m["persistent_journal"] = bool(m.get("persistent_journal", True))
    m["journal_max_mb"] = _int(m.get("journal_max_mb", 100), "journal size", 16, 512)
    m["dmrid_update_days"] = _int(m.get("dmrid_update_days", 7), "DMR ID update interval", 1, 30)
    m["config_history_keep"] = _int(m.get("config_history_keep", 10), "config history retention", 3, 50)

    # Strict schema: drop unknown top-level and nested keys so browser input cannot
    # smuggle unvalidated data into the canonical appliance configuration.
    template = defaults()
    out = {"schema": SCHEMA}
    for sec in ("station", "radio", "brandmeister", "display", "web", "maintenance"):
        out[sec] = {}
        for key, default in template[sec].items():
            if isinstance(default, dict):
                out[sec][key] = {sub: c[sec][key][sub] for sub in default}
            else:
                out[sec][key] = c[sec][key]
    return out


def public(c: dict) -> dict:
    out = copy.deepcopy(c)
    out.setdefault("brandmeister", {})["password"] = None
    out["brandmeister"]["password_configured"] = bool(c.get("brandmeister", {}).get("password"))
    return out


def hash_config(c: dict, include_secrets=True) -> str:
    obj = copy.deepcopy(c)
    if not include_secrets:
        obj.setdefault("brandmeister", {})["password"] = "***"
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def read(path: Path) -> dict:
    return normalize(json.loads(path.read_text()))


def diff_paths(a, b, prefix=""):
    changes = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            p = f"{prefix}.{k}" if prefix else k
            if k not in a or k not in b:
                changes.append(p)
            else:
                changes.extend(diff_paths(a[k], b[k], p))
    elif a != b:
        changes.append(prefix)
    return changes


def classify_changes(paths):
    """Return service/apply hints for changed config paths."""
    p = set(paths)
    rf = any(x.startswith(("station.", "radio.", "brandmeister.")) for x in p)
    oled = any(x.startswith("display.") and not x.startswith("display.instrumentation.") for x in p)
    dashboard = any(x.startswith("web.") or x.startswith("display.instrumentation.") for x in p)
    journald = any(x in {"maintenance.persistent_journal", "maintenance.journal_max_mb"} for x in p)
    autostart = "maintenance.rf_autostart" in p
    return {
        "rf": rf,
        "oled": oled,
        "dashboard": dashboard,
        "journald": journald,
        "autostart": autostart,
        "changed": sorted(p),
    }
