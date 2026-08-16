#!/usr/bin/env python3
"""YWD-Hotspot OS M3 network recovery and Wi-Fi setup service.

Runs as root because it controls NetworkManager. RF services are not touched.
The Raspberry Pi Zero W has one Wi-Fi interface, so this service explicitly
switches wlan0 between station mode and setup/recovery AP mode.
"""
from __future__ import annotations

import html
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

WLAN = "wlan0"
STATE_DIR = Path("/run/ywd-hotspot-os")
STATE_FILE = STATE_DIR / "network.json"
PROVISION = Path("/etc/ywd-headless/provision.env")

AP_PROFILE = "YWD Setup AP"
BUILDER_PROFILE = "YWD Builder WiFi"
USER_PROFILE = "YWD User WiFi"
AP_IP = "10.42.0.1"
AP_CIDR = f"{AP_IP}/24"
AP_CHANNEL = 6

NO_PROFILE_WAIT = 15
SAVED_PROFILE_WAIT = 75
LOST_NETWORK_WAIT = 90
CONNECT_WAIT = 45
AP_VERIFY_WAIT = 12
AP_RETRIES = 3

MANAGER = None


def run(args, timeout=30, check=False):
    try:
        return subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=check,
        )
    except Exception:
        return None


def output(args, timeout=10):
    p = run(args, timeout=timeout)
    return p.stdout.strip() if p and p.returncode == 0 else ""


def split_nmcli(line):
    fields, buf, esc = [], [], False
    for ch in line:
        if esc:
            buf.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            fields.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    fields.append("".join(buf))
    return fields


def current_ipv4(include_ap=False):
    out = output(["ip", "-4", "-o", "addr", "show", "dev", WLAN, "scope", "global"], 3)
    for line in out.splitlines():
        parts = line.split()
        if "inet" not in parts:
            continue
        try:
            addr = parts[parts.index("inet") + 1].split("/", 1)[0]
        except Exception:
            continue
        if addr.startswith("127."):
            continue
        if not include_ap and addr == AP_IP:
            continue
        return addr
    return ""


def current_ssid():
    return output(["iwgetid", "-r"], 3)


def wifi_saved_profiles():
    out = output(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], 5)
    result = []
    for line in out.splitlines():
        fields = split_nmcli(line)
        if len(fields) >= 2 and fields[-1] in ("802-11-wireless", "wifi"):
            name = ":".join(fields[:-1])
            if name != AP_PROFILE:
                result.append(name)
    return result


def scan_networks():
    run(["nmcli", "device", "wifi", "rescan", "ifname", WLAN], timeout=12)
    time.sleep(2)
    out = output(
        ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "ifname", WLAN],
        12,
    )
    best = {}
    for line in out.splitlines():
        fields = split_nmcli(line)
        if len(fields) < 3:
            continue
        ssid = fields[0].strip()
        if not ssid:
            continue
        try:
            signal = int(fields[1].strip())
        except Exception:
            signal = 0
        security = ":".join(fields[2:]).strip() or "OPEN"
        old = best.get(ssid)
        if old is None or signal > old["signal"]:
            best[ssid] = {"ssid": ssid, "signal": signal, "security": security}
    return sorted(best.values(), key=lambda item: (-item["signal"], item["ssid"].lower()))[:40]


def load_builder_credentials():
    if not PROVISION.is_file():
        return None
    p = run(
        [
            "/bin/bash",
            "-c",
            "set -a; source /etc/ywd-headless/provision.env; "
            "python3 - \"$WIFI_SSID\" \"$WIFI_PASSWORD\" <<'PY'\n"
            "import json,sys\n"
            "print(json.dumps({'ssid':sys.argv[1],'password':sys.argv[2]}))\n"
            "PY",
        ],
        timeout=5,
    )
    if not p or p.returncode != 0:
        return None
    try:
        obj = json.loads(p.stdout)
        return obj if obj.get("ssid") else None
    except Exception:
        return None


def ap_ssid():
    mac = "0000"
    try:
        mac = Path(f"/sys/class/net/{WLAN}/address").read_text().strip().replace(":", "")[-4:].upper()
    except Exception:
        pass
    return f"YWD-Hotspot-{mac}"


def ap_radio_state():
    iw_info = output(["iw", "dev", WLAN, "info"], 5)
    is_ap = any(line.strip() == "type AP" for line in iw_info.splitlines())
    active = output(["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", WLAN], 5)
    ip = current_ipv4(include_ap=True)
    return {
        "verified": bool(is_ap and active == AP_PROFILE and ip == AP_IP),
        "iw_type_ap": is_ap,
        "connection": active,
        "ip": ip,
        "iw_info": " | ".join(line.strip() for line in iw_info.splitlines() if line.strip())[:500],
    }


class SetupServer(ThreadingHTTPServer):
    allow_reuse_address = True


class SetupHandler(BaseHTTPRequestHandler):
    server_version = "YWD-Hotspot-Setup/0.2"

    def log_message(self, fmt, *args):
        return

    def _send(self, body, status=200, content_type="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/status"):
            self._send(json.dumps(MANAGER.public_state()), content_type="application/json")
            return
        self._send(MANAGER.setup_page())

    def do_POST(self):
        if self.path != "/connect":
            self._send("Not found", 404, "text/plain; charset=utf-8")
            return
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 8192)
        except Exception:
            length = 0
        form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        ssid = (form.get("ssid", [""])[0] or "").strip()
        manual = (form.get("manual_ssid", [""])[0] or "").strip()
        if manual:
            ssid = manual
        password = form.get("password", [""])[0]
        hidden = form.get("hidden", [""])[0] == "1"
        if not (1 <= len(ssid.encode("utf-8")) <= 32):
            self._send(MANAGER.message_page("Invalid SSID", "SSID must be 1-32 bytes."), 400)
            return
        if len(password) > 63:
            self._send(MANAGER.message_page("Invalid password", "Wi-Fi password is too long."), 400)
            return
        if not MANAGER.begin_connect(ssid, password, hidden):
            self._send(MANAGER.message_page("Busy", "A Wi-Fi connection attempt is already running."), 409)
            return
        self._send(
            MANAGER.message_page(
                "Trying Wi-Fi",
                f"Trying {html.escape(ssid)}. This setup network will disappear briefly. "
                "If the connection succeeds, reconnect your phone to normal Wi-Fi and open "
                "http://ywd-hotspot.local:8080/. If it fails, the YWD setup AP will return.",
            ),
            202,
        )


class NetworkManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.mode = "boot"
        self.reason = "starting"
        self.networks = []
        self.ap_ssid = ap_ssid()
        self.httpd = None
        self.http_thread = None
        self.connecting = False
        self.last_good = time.monotonic()
        self.last_ap_diag = {}
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(STATE_DIR, 0o755)
        self.write_state(mode="boot", reason="Starting NetworkManager")

    def write_state(self, **extra):
        ap_mode = self.mode in ("ap_starting", "setup_ap", "recovery_ap", "ap_failed")
        state = {
            "mode": self.mode,
            "reason": self.reason,
            "ssid": current_ssid(),
            "ip": current_ipv4(include_ap=True),
            "ap_ssid": self.ap_ssid,
            "ap_open": True,
            "ap_channel": AP_CHANNEL,
            "ap_verified": bool(self.last_ap_diag.get("verified")) if ap_mode else False,
            "setup_url": f"http://{AP_IP}/" if self.mode in ("setup_ap", "recovery_ap") else "",
            "updated": int(time.time()),
        }
        if ap_mode and self.last_ap_diag:
            state["ap_diagnostic"] = self.last_ap_diag
        state.update(extra)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, STATE_FILE)

    def public_state(self):
        try:
            data = json.loads(STATE_FILE.read_text())
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def stop_ap(self):
        run(["nmcli", "connection", "down", AP_PROFILE], timeout=15)
        run(["nmcli", "connection", "delete", AP_PROFILE], timeout=15)

    def stop_http(self):
        srv = self.httpd
        self.httpd = None
        if srv:
            try:
                srv.shutdown()
                srv.server_close()
            except Exception:
                pass

    def start_http(self):
        self.stop_http()
        try:
            self.httpd = SetupServer(("0.0.0.0", 80), SetupHandler)
        except OSError as exc:
            self.reason = f"Setup web failed: {exc}"
            self.write_state()
            return False
        self.http_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.http_thread.start()
        return True

    def wait_for_ip(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            ip = current_ipv4()
            if ip:
                return ip
            time.sleep(2)
        return ""

    def try_wifi(self, ssid, password="", hidden=False, profile=USER_PROFILE):
        self.mode = "connecting"
        self.reason = f"Trying {ssid}"
        self.write_state(ssid=ssid, ip="")
        self.stop_http()
        self.stop_ap()
        run(["nmcli", "radio", "wifi", "on"], timeout=10)
        run(["nmcli", "connection", "delete", profile], timeout=10)
        run(["nmcli", "device", "wifi", "rescan", "ifname", WLAN, "ssid", ssid], timeout=12)
        args = ["nmcli", "--wait", str(CONNECT_WAIT), "device", "wifi", "connect", ssid]
        if password:
            args += ["password", password]
        args += ["ifname", WLAN, "name", profile]
        if hidden:
            args += ["hidden", "yes"]
        p = run(args, timeout=CONNECT_WAIT + 10)
        if not p or p.returncode != 0:
            return ""
        return self.wait_for_ip(20)

    def try_saved_profiles(self):
        profiles = wifi_saved_profiles()
        if current_ipv4():
            return current_ipv4()
        for name in profiles:
            self.mode = "waiting"
            self.reason = f"Trying saved Wi-Fi: {name}"
            self.write_state()
            p = run(["nmcli", "--wait", "25", "connection", "up", "id", name, "ifname", WLAN], timeout=32)
            if p and p.returncode == 0:
                ip = self.wait_for_ip(15)
                if ip:
                    return ip
        return ""

    def configure_open_ap_profile(self):
        add = run(
            [
                "nmcli", "connection", "add", "type", "wifi", "ifname", WLAN,
                "con-name", AP_PROFILE, "autoconnect", "no", "ssid", self.ap_ssid,
            ],
            timeout=15,
        )
        if not add or add.returncode != 0:
            return False, (add.stderr.strip() if add else "nmcli add failed")
        mod = run(
            [
                "nmcli", "connection", "modify", AP_PROFILE,
                "802-11-wireless.mode", "ap",
                "802-11-wireless.band", "bg",
                "802-11-wireless.channel", str(AP_CHANNEL),
                "802-11-wireless.hidden", "no",
                "802-11-wireless.powersave", "2",
                "ipv4.method", "shared",
                "ipv4.addresses", AP_CIDR,
                "ipv4.never-default", "yes",
                "ipv6.method", "disabled",
            ],
            timeout=15,
        )
        if not mod or mod.returncode != 0:
            return False, (mod.stderr.strip() if mod else "nmcli modify failed")
        return True, ""

    def verify_ap(self):
        end = time.monotonic() + AP_VERIFY_WAIT
        while time.monotonic() < end:
            diag = ap_radio_state()
            self.last_ap_diag = diag
            if diag["verified"]:
                return True
            time.sleep(1)
        return False

    def start_ap(self, recovery, reason):
        with self.lock:
            self.connecting = False
        target_mode = "recovery_ap" if recovery else "setup_ap"
        self.mode = "ap_starting"
        self.reason = reason
        self.last_ap_diag = {}
        self.networks = scan_networks()
        self.write_state()
        self.stop_http()

        for attempt in range(1, AP_RETRIES + 1):
            self.stop_ap()
            run(["nmcli", "device", "disconnect", WLAN], timeout=10)
            run(["nmcli", "radio", "wifi", "on"], timeout=10)
            time.sleep(1)
            ok, error = self.configure_open_ap_profile()
            if not ok:
                self.reason = f"AP profile failed ({attempt}/{AP_RETRIES})"
                self.last_ap_diag = {"verified": False, "error": error[:500]}
                self.write_state()
                time.sleep(2)
                continue
            up = run(["nmcli", "--wait", "30", "connection", "up", AP_PROFILE, "ifname", WLAN], timeout=38)
            if not up or up.returncode != 0:
                error = up.stderr.strip() if up else "nmcli connection up failed"
                self.reason = f"AP start failed ({attempt}/{AP_RETRIES})"
                self.last_ap_diag = {"verified": False, "error": error[:500]}
                self.write_state()
                time.sleep(2)
                continue
            if self.verify_ap():
                self.mode = target_mode
                self.reason = reason
                self.write_state(ip=AP_IP, ap_verified=True)
                self.start_http()
                return True
            self.reason = f"AP not broadcasting ({attempt}/{AP_RETRIES})"
            self.write_state()
            time.sleep(2)

        self.mode = "ap_failed"
        self.reason = "Setup AP failed to broadcast; retrying"
        self.write_state()
        return False

    def begin_connect(self, ssid, password, hidden):
        with self.lock:
            if self.connecting:
                return False
            self.connecting = True
        threading.Thread(target=self._connect_worker, args=(ssid, password, hidden), daemon=True).start()
        return True

    def _connect_worker(self, ssid, password, hidden):
        time.sleep(2)
        ip = self.try_wifi(ssid, password, hidden, USER_PROFILE)
        if ip:
            try:
                PROVISION.unlink()
            except FileNotFoundError:
                pass
            self.mode = "online"
            self.reason = "Wi-Fi connected"
            self.last_good = time.monotonic()
            self.last_ap_diag = {}
            self.write_state(ssid=ssid, ip=ip)
            with self.lock:
                self.connecting = False
            return
        self.start_ap(True, f"Could not connect to {ssid}")

    def message_page(self, title, text):
        return self._page(title, f"<div class='card'><h2>{html.escape(title)}</h2><p>{text}</p></div>")

    def setup_page(self):
        options = ["<option value=''>Select a visible network…</option>"]
        for item in self.networks:
            label = f"{item['ssid']} — {item['signal']}% — {item['security']}"
            options.append(f"<option value='{html.escape(item['ssid'], quote=True)}'>{html.escape(label)}</option>")
        mode = "Recovery AP" if self.mode == "recovery_ap" else "Setup AP"
        body = f"""
<div class="card hero">
  <div class="eyebrow">YWD-HOTSPOT OS · M3</div>
  <h1>Wi-Fi {mode}</h1>
  <p>{html.escape(self.reason)}</p>
  <div class="facts">
    <span>AP <b>{html.escape(self.ap_ssid)}</b></span>
    <span>Security <b>OPEN</b></span>
    <span>Channel <b>{AP_CHANNEL}</b></span>
    <span>Setup <b>{AP_IP}</b></span>
    <span>RF <b>OFF</b></span>
  </div>
</div>
<div class="card">
  <h2>Connect YWD-Hotspot to Wi-Fi</h2>
  <p class="small">This temporary setup access point is open. Configure Wi-Fi, then leave setup mode promptly.</p>
  <form method="post" action="/connect">
    <label>Visible networks</label>
    <select name="ssid" id="ssid">{''.join(options)}</select>
    <label>Or enter SSID manually</label>
    <input name="manual_ssid" maxlength="32" autocomplete="off" placeholder="Hidden or unlisted network">
    <label>Wi-Fi password</label>
    <input name="password" maxlength="63" type="password" autocomplete="new-password" placeholder="Leave blank for open Wi-Fi">
    <label class="check"><input type="checkbox" name="hidden" value="1"> Hidden network</label>
    <button type="submit">Save &amp; Connect</button>
  </form>
  <p class="small">The AP disappears while YWD-Hotspot tries the new network. If it fails, recovery AP returns automatically.</p>
</div>
"""
        return self._page("YWD-Hotspot Wi-Fi Setup", body)

    def _page(self, title, body):
        return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{color-scheme:dark;--bg:#080d12;--panel:#101922;--line:#243849;--cyan:#42d9ff;--text:#e8f4fa;--muted:#8aa2b2}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top,#10212c 0,#080d12 48%);font:16px/1.45 system-ui,sans-serif;color:var(--text)}}
main{{max-width:680px;margin:auto;padding:24px}}.card{{background:rgba(16,25,34,.96);border:1px solid var(--line);border-radius:18px;padding:22px;margin:0 0 18px;box-shadow:0 18px 50px #0008}}
.eyebrow{{font:700 12px/1.2 ui-monospace,monospace;letter-spacing:.14em;color:var(--cyan)}}h1{{margin:.35rem 0 .6rem;font-size:30px}}h2{{margin-top:0}}
.facts{{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}}.facts span{{border:1px solid var(--line);border-radius:999px;padding:7px 10px;color:var(--muted)}}.facts b{{color:var(--text)}}
label{{display:block;margin:15px 0 6px;color:var(--muted);font-weight:650}}select,input{{width:100%;padding:13px 14px;border-radius:11px;border:1px solid #315064;background:#091118;color:var(--text);font-size:16px}}
.check{{display:flex;align-items:center;gap:9px}}.check input{{width:auto}}button{{width:100%;margin-top:18px;padding:14px;border:0;border-radius:12px;background:linear-gradient(90deg,var(--cyan),#7f8cff);color:#051017;font-weight:800;font-size:16px}}
.small{{color:var(--muted);font-size:13px;margin-bottom:0}}a{{color:var(--cyan)}}
</style></head><body><main>{body}</main></body></html>"""

    def boot(self):
        for _ in range(30):
            if output(["systemctl", "is-active", "NetworkManager.service"], 2) == "active":
                break
            time.sleep(1)
        run(["nmcli", "radio", "wifi", "on"], timeout=10)

        creds = load_builder_credentials()
        if creds:
            self.mode = "waiting"
            self.reason = "Trying image Wi-Fi"
            self.write_state()
            ip = self.try_wifi(creds["ssid"], creds.get("password", ""), False, BUILDER_PROFILE)
            if ip:
                try:
                    PROVISION.unlink()
                except FileNotFoundError:
                    pass
                self.mode = "online"
                self.reason = "Wi-Fi connected"
                self.last_good = time.monotonic()
                self.write_state(ip=ip)
                return

        profiles = wifi_saved_profiles()
        timeout = SAVED_PROFILE_WAIT if profiles else NO_PROFILE_WAIT
        self.mode = "waiting"
        self.reason = "Waiting for saved Wi-Fi" if profiles else "No saved Wi-Fi"
        self.write_state()
        ip = self.wait_for_ip(timeout)
        if not ip and profiles:
            ip = self.try_saved_profiles()
        if ip:
            self.mode = "online"
            self.reason = "Wi-Fi connected"
            self.last_good = time.monotonic()
            self.write_state(ip=ip)
            return

        self.start_ap(bool(profiles or creds), "Saved Wi-Fi unavailable" if (profiles or creds) else "Wi-Fi setup required")

    def loop(self):
        self.boot()
        lost_since = None
        ap_retry_at = 0.0
        while True:
            if self.mode == "online":
                ip = current_ipv4()
                if ip:
                    lost_since = None
                    self.last_good = time.monotonic()
                    self.write_state(ip=ip)
                else:
                    if lost_since is None:
                        lost_since = time.monotonic()
                    elapsed = int(time.monotonic() - lost_since)
                    self.mode = "waiting"
                    self.reason = f"Wi-Fi lost; recovery in {max(0, LOST_NETWORK_WAIT-elapsed)}s"
                    self.write_state(ip="")
            elif self.mode == "waiting" and lost_since is not None:
                ip = current_ipv4()
                if ip:
                    self.mode = "online"
                    self.reason = "Wi-Fi restored"
                    lost_since = None
                    self.write_state(ip=ip)
                elif time.monotonic() - lost_since >= LOST_NETWORK_WAIT:
                    lost_since = None
                    self.start_ap(True, "Wi-Fi connection lost")
            elif self.mode == "ap_failed" and time.monotonic() >= ap_retry_at:
                ap_retry_at = time.monotonic() + 30
                self.start_ap(True, "Retrying recovery AP")
            time.sleep(5)


def main():
    global MANAGER
    MANAGER = NetworkManager()
    MANAGER.loop()


if __name__ == "__main__":
    main()
