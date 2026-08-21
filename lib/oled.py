#!/usr/bin/env python3
"""Single-owner SSD1306 display renderer for YWD-Hotspot.

The same renderer supports generic app installs and YWD-Hotspot OS.  On the OS,
ywd-headless-oled.service remains the sole I2C owner and this process preserves
boot/network/first-boot/shutdown screens before transitioning to normal runtime
RX/TX/status display.  It only consumes local state; OLED failure cannot control
RF, networking, or BrandMeister.
"""
from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from pathlib import Path

try:
    import smbus
except ImportError:
    raise SystemExit("python3-smbus is required")

CFG = Path("/etc/ywd-hotspot/config.json")
ACTIVITY = Path("/run/ywd-hotspot/activity.json")
NETWORK_STATE = Path("/run/ywd-hotspot-os/network.json")
SETUP_RUNTIME = Path("/run/ywd-hotspot/setup.json")
SETUP_STATE = Path("/var/lib/ywd-hotspot/setup-state.json")
M4_GATE = Path("/etc/ywd-hotspot/m4-safety.txt")
UPDATE_STATE = Path("/var/lib/ywd-hotspot/update-status.json")
TG_CACHE = Path("/var/lib/ywd-hotspot/talkgroup-directory.json")
DMR_IDS = Path("/var/lib/ywd-hotspot/DMRIds.dat")
PROVISION = Path("/etc/ywd-headless/provision.env")
RUNTIME_VERSION = Path("/opt/ywd-hotspot/app/VERSION")
ACTIVE_OLED = None

FONT = {
    ' ':[0,0,0,0,0], '-':[8,8,8,8,8], '.':[0,96,96,0,0], '/':[32,16,8,4,2], ':':[0,54,54,0,0],
    '%':[35,19,8,100,98], '?':[2,1,81,9,6], '+':[8,8,62,8,8], '=':[20,20,20,20,20],
    '0':[62,81,73,69,62], '1':[0,66,127,64,0], '2':[66,97,81,73,70], '3':[33,65,69,75,49,],
    '4':[24,20,18,127,16], '5':[39,69,69,69,57], '6':[60,74,73,73,48], '7':[1,113,9,5,3],
    '8':[54,73,73,73,54], '9':[6,73,73,41,30],
    'A':[126,17,17,17,126], 'B':[127,73,73,73,54], 'C':[62,65,65,65,34], 'D':[127,65,65,34,28],
    'E':[127,73,73,73,65], 'F':[127,9,9,9,1], 'G':[62,65,73,73,122], 'H':[127,8,8,8,127],
    'I':[0,65,127,65,0], 'J':[32,64,65,63,1], 'K':[127,8,20,34,65], 'L':[127,64,64,64,64],
    'M':[127,2,12,2,127], 'N':[127,4,8,16,127], 'O':[62,65,65,65,62], 'P':[127,9,9,9,6],
    'Q':[62,65,81,33,94], 'R':[127,9,25,41,70], 'S':[70,73,73,73,49], 'T':[1,1,127,1,1],
    'U':[63,64,64,64,63], 'V':[31,32,64,32,31], 'W':[63,64,56,64,63], 'X':[99,20,8,20,99],
    'Y':[7,8,112,8,7], 'Z':[97,81,73,69,67], '_':[64,64,64,64,64],
}


def sh(args, timeout=2):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=timeout).strip()
    except Exception:
        return ""


def json_file(path):
    try:
        obj = json.loads(Path(path).read_text())
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def config():
    c = json_file(CFG)
    d = c.setdefault("display", {})
    d.setdefault("enabled", True); d.setdefault("i2c_bus", 1); d.setdefault("address", "0x3c")
    d.setdefault("brightness", 127); d.setdefault("idle_timeout_s", 0); d.setdefault("rotation", 0)
    d.setdefault("runtime_mode", "basic"); d.setdefault("large_callsign", True); d.setdefault("callsign_size", "auto")
    d.setdefault("show_talkgroup", True); d.setdefault("talkgroup_format", "number")
    d.setdefault("show_slot", True); d.setdefault("show_elapsed", True); d.setdefault("show_ber", True)
    d.setdefault("show_rssi", True); d.setdefault("show_loss", True); d.setdefault("post_call_hold_s", 3)
    d.setdefault("idle_cycle", False); d.setdefault("idle_cycle_s", 6)
    return c


def activity():
    return json_file(ACTIVITY)


def setup_complete():
    return json_file(SETUP_STATE).get("state") == "complete"


def ip_addr():
    out = sh(["hostname", "-I"])
    for item in out.split():
        if ":" not in item and not item.startswith("127."):
            return item
    return ""


def ssid():
    return sh(["iwgetid", "-r"])


def temp():
    try:
        return f"{int(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000:.0f}C"
    except Exception:
        return "--C"


def service_states():
    out = sh(["systemctl", "is-active", "ywd-mmdvmhost.service", "ywd-dmrgateway.service", "ywd-dashboard.service"], 3).splitlines()
    return tuple((out + ["unknown", "unknown", "unknown"])[:3])


def compact_error(state):
    diag = state.get("ap_diagnostic") if isinstance(state.get("ap_diagnostic"), dict) else {}
    text = str(diag.get("error") or state.get("reason") or "")
    for prefix in ("Error: ", "error: "):
        if text.startswith(prefix):
            text = text[len(prefix):]
    for old, new in (("Connection activation failed", "ACTIVATION FAILED"),
                     ("Failed to activate connection", "ACTIVATION FAILED"),
                     ("dnsmasq", "DNSMASQ"), ("supplicant", "SUPPLICANT")):
        text = text.replace(old, new)
    return text[:21]


class Frame:
    def __init__(self):
        self.buf = bytearray(1024)

    def pixel(self, x, y, on=True):
        if 0 <= x < 128 and 0 <= y < 64 and on:
            self.buf[(y // 8) * 128 + x] |= 1 << (y & 7)

    def text(self, x, y, text, scale=1, max_width=None):
        text = str(text).upper()
        width = max_width if max_width is not None else 128 - x
        char_w = 6 * scale
        if char_w > 0:
            text = text[:max(0, width // char_w)]
        for ch in text:
            glyph = FONT.get(ch, FONT[' '])
            for gx, column in enumerate(glyph):
                for gy in range(7):
                    if column & (1 << gy):
                        for sx in range(scale):
                            for sy in range(scale):
                                self.pixel(x + gx * scale + sx, y + gy * scale + sy)
            x += char_w
        return x

    def center(self, y, text, scale=1):
        text = str(text).upper()
        width = len(text) * 6 * scale
        self.text(max(0, (128 - width) // 2), y, text, scale)

    def line(self, y, text):
        self.text(1, y, str(text)[:21], 1)

    def hline(self, y):
        for x in range(128):
            self.pixel(x, y)


class OLED:
    def __init__(self, bus=1, addr=0x3c, brightness=127, rotation=0):
        self.bus = smbus.SMBus(bus)
        self.addr = addr
        self.on = True
        self.last = None
        self.rotation = 180 if int(rotation) == 180 else 0
        seg = 0xA0 if self.rotation == 180 else 0xA1
        com = 0xC0 if self.rotation == 180 else 0xC8
        brightness = max(1, min(255, int(brightness)))
        self.cmds([0xAE,0x20,0x00,0xB0,com,0x00,0x10,0x40,0x81,brightness,seg,0xA6,
                   0xA8,0x3F,0xA4,0xD3,0x00,0xD5,0x80,0xD9,0xF1,0xDA,0x12,0xDB,0x40,
                   0x8D,0x14,0xAF])
        self.show(Frame(), force=True)

    def cmd(self, value):
        self.bus.write_byte_data(self.addr, 0x00, value)

    def cmds(self, values):
        for value in values:
            self.cmd(value)

    def power(self, on):
        on = bool(on)
        if self.on != on:
            self.cmd(0xAF if on else 0xAE)
            self.on = on

    def show(self, frame, force=False):
        data = bytes(frame.buf)
        if not force and self.last == data:
            return
        for page in range(8):
            self.cmd(0xB0 + page); self.cmd(0x00); self.cmd(0x10)
            row = data[page * 128:(page + 1) * 128]
            for pos in range(0, 128, 16):
                self.bus.write_i2c_block_data(self.addr, 0x40, list(row[pos:pos + 16]))
        self.last = data


def lines_frame(rows):
    f = Frame()
    for i, row in enumerate(rows[:8]):
        f.line(i * 8, row)
    return f


def first_boot_frame(state):
    setup = json_file(SETUP_RUNTIME)
    code = str(setup.get("code") or "")
    ip = str(state.get("ip") or ip_addr() or "")
    f = Frame()
    f.center(0, "SETUP CODE")
    if code:
        # Six digits at scale 3 are about 108 px wide: intentionally dominant
        # and readable without needing to put your face on the OLED.
        f.center(11, code, 3)
    else:
        f.center(14, "STARTING", 2)
    f.center(38, ip or "WAITING FOR IP")
    f.center(48, "HTTPS :8443")
    f.center(56, "RF OFF")
    return f


def network_frame(state, runtime=True):
    mode = str(state.get("mode") or "boot")
    net_ssid = str(state.get("ssid") or "")
    ip = str(state.get("ip") or "")
    dashboard = service_states()[2]
    web = "WEB 8080 RF OFF" if runtime and dashboard == "active" else ("WEB STARTING RF OFF" if runtime else "")
    if runtime and mode == "online" and M4_GATE.exists() and not setup_complete():
        return first_boot_frame(state)
    if mode in ("setup_ap", "recovery_ap"):
        verified = bool(state.get("ap_verified"))
        return lines_frame(["YWD HOTSPOT OS", "M3 NETWORK", web,
            (("RECOVERY AP" if mode == "recovery_ap" else "SETUP AP") if verified else "AP VERIFYING"),
            str(state.get("ap_ssid") or "YWD-HOTSPOT"), "OPEN WIFI CH 6", "10.42.0.1", "OPEN 10.42.0.1"])
    if mode == "ap_starting":
        return lines_frame(["YWD HOTSPOT OS", "M3 NETWORK", web, "AP STARTING",
                            str(state.get("ap_ssid") or "YWD-HOTSPOT"), "OPEN WIFI CH 6", "PLEASE WAIT", temp()])
    if mode == "ap_failed":
        return lines_frame(["YWD HOTSPOT OS", "M3 NETWORK", web, "AP START FAILED",
                            str(state.get("ap_ssid") or "YWD-HOTSPOT"), "RETRY IN 30S", compact_error(state), temp()])
    if mode == "connecting":
        return lines_frame(["YWD HOTSPOT OS", "M3 NETWORK", web, "WIFI CONNECTING", net_ssid, "", "PLEASE WAIT", temp()])
    if mode == "online":
        return lines_frame(["YWD HOTSPOT OS", "M3 NETWORK", web, "WIFI ONLINE", net_ssid,
                            ip or "NO IP", "YWD-HOTSPOT.LOCAL", temp()])
    return lines_frame(["YWD HOTSPOT OS", "M3 NETWORK", web, "WIFI WAITING", net_ssid,
                        ip or "NO IP", str(state.get("reason") or "")[:21], temp()])


def legacy_boot_frame(runtime=True):
    current_ip = ip_addr(); current_ssid = ssid()
    if current_ip: state = "WIFI ONLINE"
    elif PROVISION.exists(): state = "WIFI SETUP"
    else: state = "WIFI WAITING"
    dashboard = service_states()[2]
    return lines_frame(["YWD HOTSPOT OS", "RUNTIME STARTING" if runtime else "HEADLESS BOOT",
                        "WEB 8080" if runtime and dashboard == "active" else "WEB STARTING",
                        "BOOT OK", state, current_ssid, current_ip or "NO IP", temp()])


_DMR_CACHE = {}
_TG_NAMES = {}
_TG_MTIME = None


def dmr_callsign(value):
    try:
        rid = int(value)
    except Exception:
        return ""
    if rid in _DMR_CACHE:
        return _DMR_CACHE[rid]
    result = ""
    try:
        prefix = f"{rid}\t"
        with DMR_IDS.open(errors="replace") as fh:
            for line in fh:
                if line.startswith(prefix):
                    result = line.split("\t", 1)[1].strip().upper()[:12]
                    break
    except Exception:
        pass
    if len(_DMR_CACHE) >= 64:
        _DMR_CACHE.pop(next(iter(_DMR_CACHE)))
    _DMR_CACHE[rid] = result
    return result


def talkgroup_name(value):
    global _TG_MTIME
    try:
        tid = int(value)
    except Exception:
        return ""
    try:
        mt = TG_CACHE.stat().st_mtime_ns
        if mt != _TG_MTIME:
            _TG_NAMES.clear(); _TG_MTIME = mt
    except Exception:
        return ""
    if tid in _TG_NAMES:
        return _TG_NAMES[tid]
    name = ""
    try:
        doc = json.loads(TG_CACHE.read_text())
        rows = doc.get("rows", []) if isinstance(doc, dict) else []
        for row in rows:
            if isinstance(row, dict) and int(row.get("id", -1)) == tid:
                name = str(row.get("name") or "").upper()[:21]
                break
    except Exception:
        pass
    if len(_TG_NAMES) >= 64:
        _TG_NAMES.pop(next(iter(_TG_NAMES)))
    _TG_NAMES[tid] = name
    return name


def party_label(p):
    p = p or {}
    call = str(p.get("callsign") or "").upper()
    if call:
        return call[:12]
    did = p.get("dmr_id")
    resolved = dmr_callsign(did) if did else ""
    return resolved or str(p.get("display") or did or "UNKNOWN")[:12].upper()


def tg_label(dst, display):
    dst = dst or {}
    raw = str(dst.get("display") or dst.get("id") or "?")
    if not dst.get("group"):
        return f"PC {raw}"[:21]
    fmt = str(display.get("talkgroup_format", "number"))
    name = talkgroup_name(dst.get("id") or raw) if fmt != "number" else ""
    if fmt == "name" and name:
        return name[:21]
    if fmt == "name_number" and name:
        short_name = name[:max(1, 17 - len(raw))]
        return f"{short_name} {raw}"[:21]
    return f"TG {raw}"[:21]


def callsign_scale(call, display):
    pref = str(display.get("callsign_size", "auto"))
    if not display.get("large_callsign", True) or pref == "normal":
        return 1
    if pref == "huge":
        return 3 if len(call) <= 7 else 2 if len(call) <= 10 else 1
    if pref == "large":
        return 2 if len(call) <= 10 else 1
    return 3 if len(call) <= 7 else 2 if len(call) <= 10 else 1


def update_frame(doc):
    f = Frame()
    pct = max(0, min(100, int(doc.get("progress") or 0)))
    f.center(0, "SOFTWARE UPDATE")
    f.center(12, str(doc.get("phase") or "UPDATING").replace("-", " ")[:20])
    f.center(24, f"{pct}%", 2)
    blocks = int(round(pct / 100 * 20))
    f.text(4, 46, "=" * blocks + "-" * (20 - blocks))
    f.center(56, "DO NOT POWER OFF")
    return f


def event_for_display(a, hold_s):
    cur = a.get("current") or {}
    if cur.get("active"):
        return cur
    ended = cur.get("ended_at")
    if ended and hold_s > 0:
        try:
            if time.time() - float(ended) <= hold_s:
                return cur
        except Exception:
            pass
    return None


def runtime_event_frame(c, event):
    d = c.get("display", {})
    mode = str(d.get("runtime_mode", "basic"))
    rx = event.get("direction") == "rx"
    src = party_label(event.get("source"))
    dst = event.get("destination") or {}
    elapsed = event.get("duration_s")
    if event.get("active"):
        try: elapsed = max(0, int(time.time() - float(event.get("started_at", time.time()))))
        except Exception: elapsed = 0
    if mode == "basic":
        rows = [f"YWD HOTSPOT {c.get('station',{}).get('callsign','NOCALL')}", "",
                "RX FROM RADIO" if rx else "TX TO RADIO", src,
                tg_label(dst, d) if d.get("show_talkgroup", True) else "",
                f"SLOT {event.get('slot','?')}  {int(elapsed or 0)}S", "", f"{ip_addr()} {temp()}"]
        return lines_frame(rows)

    f = Frame()
    f.text(1, 0, "RX" if rx else "TX", 1)
    if d.get("show_talkgroup", True):
        label = tg_label(dst, d)
        f.text(max(42, 127 - len(label) * 6), 0, label)
    f.hline(8)
    scale = callsign_scale(src, d)
    call_y = 13 if scale == 3 else 15 if scale == 2 else 18
    f.center(call_y, src, scale)
    if mode == "minimal":
        if d.get("show_talkgroup", True): f.center(54, tg_label(dst, d))
        return f

    metric_y = 42
    if d.get("show_slot", True):
        f.text(1, metric_y, f"S{event.get('slot','?')}")
    if d.get("show_elapsed", True):
        text = f"{int(elapsed or 0)}S"
        f.text(127 - len(text) * 6, metric_y, text)
    quality = []
    if d.get("show_ber", True) and event.get("ber_pct") is not None:
        quality.append(f"BER {float(event['ber_pct']):.1f}%")
    if d.get("show_rssi", True) and event.get("rssi_dbm") is not None:
        quality.append(f"{int(event['rssi_dbm'])}DBM")
    if d.get("show_loss", True) and event.get("packet_loss_pct") is not None:
        quality.append(f"LOSS {int(event['packet_loss_pct'])}%")
    f.center(54, " ".join(quality)[:21] or ("RF ACTIVE" if rx else "NETWORK TO RF"))
    return f


def idle_frames(c, states, a):
    d = c.get("display", {})
    station = c.get("station", {}); radio = c.get("radio", {})
    call = str(station.get("callsign") or "NOCALL").upper()
    mmdvm, gateway, _ = states
    mode = str(d.get("runtime_mode", "basic"))
    if mode == "basic":
        mhz = float(radio.get("frequency_hz", 0)) / 1e6
        return [lines_frame([f"YWD HOTSPOT {call}", "", f"DMR {mhz:.4f} CC{radio.get('color_code',1)}", "",
                             "MMDVM UP" if mmdvm == "active" else "MMDVM DOWN",
                             "BM LINK UP" if gateway == "active" else "BM LINK DOWN", "", f"{ip_addr()} {temp()}"])]

    f = Frame(); f.center(0, "YWD-HOTSPOT"); f.hline(8)
    scale = 2 if len(call) <= 10 else 1
    f.center(14, call, scale)
    mhz = float(radio.get("frequency_hz", 0)) / 1e6
    f.center(34, f"{mhz:.4f} CC{radio.get('color_code',1)}")
    f.text(1, 46, "RF READY" if mmdvm == "active" else "RF DOWN")
    f.text(77, 46, "BM UP" if gateway == "active" else "BM DOWN")
    f.center(56, f"{ip_addr()} {temp()}"[:21])
    pages = [f]
    if d.get("idle_cycle", False):
        w = Frame(); w.center(0, "NETWORK"); w.center(17, ssid()[:20]); w.center(31, ip_addr() or "NO IP", 1); w.center(47, "YWD-HOTSPOT.LOCAL")
        pages.append(w)
        heard = (a.get("lastheard") or [None])[0]
        if isinstance(heard, dict):
            h = Frame(); h.center(0, "LAST HEARD"); h.center(14, party_label(heard.get("source")), 2 if len(party_label(heard.get("source"))) <= 10 else 1)
            h.center(36, tg_label(heard.get("destination") or {}, d))
            q = []
            if heard.get("ber_pct") is not None: q.append(f"BER {heard['ber_pct']}%")
            if heard.get("rssi_dbm") is not None: q.append(f"{heard['rssi_dbm']}DBM")
            h.center(52, " ".join(q)[:21])
            pages.append(h)
    return pages


def critical_os_frame(cached_network, states):
    if not M4_GATE.exists() and not NETWORK_STATE.exists():
        return None
    state = cached_network or json_file(NETWORK_STATE)
    mode = str(state.get("mode") or "boot")
    if mode in {"setup_ap", "recovery_ap", "ap_starting", "ap_failed", "connecting"}:
        return network_frame(state, RUNTIME_VERSION.exists())
    if M4_GATE.exists() and not setup_complete():
        return network_frame(state, RUNTIME_VERSION.exists()) if state else first_boot_frame({})
    # During a normal boot preserve the proven network/boot information until
    # both station networking and the dashboard are established.
    if states[2] != "active" or (state and mode != "online"):
        return network_frame(state, RUNTIME_VERSION.exists()) if state else legacy_boot_frame(RUNTIME_VERSION.exists())
    return None


def shutdown_handler(signum, frame):
    if ACTIVE_OLED is not None:
        try:
            ACTIVE_OLED.power(True)
            ACTIVE_OLED.show(lines_frame(["YWD HOTSPOT OS", "SHUTTING DOWN", "PLEASE WAIT", "",
                                          "RF SERVICES STOPPING", "SYSTEM HALTING", "", temp()]), force=True)
            time.sleep(0.35)
        except Exception:
            pass
    raise SystemExit(0)


def open_oled_forever(c):
    d = c.get("display", {})
    while True:
        try:
            return OLED(int(d.get("i2c_bus", 1)), int(str(d.get("address", "0x3c")), 0),
                        int(d.get("brightness", 127)), int(d.get("rotation", 0)))
        except Exception:
            time.sleep(2)


def main():
    global ACTIVE_OLED
    c = config()
    if not c.get("display", {}).get("enabled", True):
        return
    ACTIVE_OLED = open_oled_forever(c)
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    last_cfg_mtime = CFG.stat().st_mtime_ns if CFG.exists() else 0
    last_activity_at = time.monotonic()
    states = ("unknown", "unknown", "unknown")
    cached_ip = ""; cached_network = {}; next_services = next_ip = next_network = 0.0
    idle_page = 0; next_idle_page = 0.0

    while True:
        active_now = False
        try:
            n = time.monotonic()
            try:
                mt = CFG.stat().st_mtime_ns
                if mt != last_cfg_mtime:
                    # Display hardware settings require service restart; content
                    # settings can be re-read live while the current owner stays up.
                    c = config(); last_cfg_mtime = mt
            except Exception:
                pass
            if n >= next_services:
                states = service_states(); next_services = n + 12
            if n >= next_ip:
                cached_ip = ip_addr(); next_ip = n + 30
            if n >= next_network:
                cached_network = json_file(NETWORK_STATE); next_network = n + 4

            d = c.get("display", {})
            if not d.get("enabled", True):
                ACTIVE_OLED.power(False); time.sleep(2); continue

            critical = critical_os_frame(cached_network, states)
            if critical is not None:
                ACTIVE_OLED.power(True); ACTIVE_OLED.show(critical); time.sleep(1.5); continue

            upd = json_file(UPDATE_STATE)
            if upd.get("state") == "running":
                ACTIVE_OLED.power(True); ACTIVE_OLED.show(update_frame(upd)); time.sleep(1); continue

            a = activity()
            event = event_for_display(a, int(d.get("post_call_hold_s", 3)))
            if event:
                active_now = bool(event.get("active"))
                last_activity_at = n
                ACTIVE_OLED.power(True); ACTIVE_OLED.show(runtime_event_frame(c, event))
                time.sleep(0.75 if active_now else 1.0); continue

            idle_timeout = max(0, int(d.get("idle_timeout_s", 0)))
            if idle_timeout and n - last_activity_at >= idle_timeout:
                ACTIVE_OLED.power(False); time.sleep(2); continue
            ACTIVE_OLED.power(True)
            pages = idle_frames(c, states, a)
            if not pages:
                pages = [Frame()]
            cycle = bool(d.get("idle_cycle", False)) and len(pages) > 1
            if cycle and (next_idle_page == 0.0 or n >= next_idle_page):
                idle_page = (idle_page + 1) % len(pages) if next_idle_page else 0
                next_idle_page = n + max(2, int(d.get("idle_cycle_s", 6)))
            elif not cycle:
                idle_page = 0; next_idle_page = 0.0
            ACTIVE_OLED.show(pages[idle_page % len(pages)])
        except OSError:
            pass
        except Exception:
            pass
        time.sleep(0.8 if active_now else 2.0)


if __name__ == "__main__":
    main()
