#!/usr/bin/env python3
"""First-boot setup server for YWD-Hotspot OS M4.

Runs unprivileged as ywd-hotspot. A short-lived setup code is generated in /run
and shown on the OLED. The browser unlocks this setup-only HTTP service with
that code, then the server delegates exactly one privileged operation to the
narrow ywd-hotspot-admin setup-finish action.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
import subprocess
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import config_model

CFG = Path(os.environ.get("YWD_CONFIG", "/etc/ywd-hotspot/config.json"))
VAR = Path(os.environ.get("YWD_VAR", "/var/lib/ywd-hotspot"))
SETUP_STATE = VAR / "setup-state.json"
RUNTIME_DIR = Path(os.environ.get("YWD_SETUP_RUNTIME", "/run/ywd-hotspot"))
RUNTIME_STATE = RUNTIME_DIR / "setup.json"
ADMIN = os.environ.get("YWD_ADMIN", "/usr/local/libexec/ywd-hotspot-admin")

BIND = "0.0.0.0"
PORT = 8443
CODE_SECONDS = 30 * 60
SESSION_SECONDS = 30 * 60
MAX_BODY = 131072
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()
FAILS = {}
CODE_LOCK = threading.Lock()
SETUP_CODE = ""
CODE_EXPIRES = 0.0


def run(args, timeout=20):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, check=False)


def file_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def setup_complete():
    d = file_json(SETUP_STATE, {})
    return isinstance(d, dict) and d.get("state") == "complete"


def public_config():
    try:
        return config_model.public(config_model.normalize(json.loads(CFG.read_text())))
    except Exception:
        return config_model.public(config_model.normalize({
            "station": {"callsign": "NOCALL", "base_dmr_id": "00000"}
        }))


def dashboard_url():
    try:
        port = int(public_config().get("web", {}).get("port", 8080))
    except Exception:
        port = 8080
    return f"http://ywd-hotspot.local:{port}/"


def write_runtime_state():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    now = time.time()
    doc = {
        "mode": "first_boot",
        "code": SETUP_CODE,
        "expires_at": int(CODE_EXPIRES),
        "expires_in_s": max(0, int(CODE_EXPIRES - now)),
        "url": f"http://ywd-hotspot.local:{PORT}/",
        "port": PORT,
        "rf_forced_off": True,
    }
    tmp = RUNTIME_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n")
    os.chmod(tmp, 0o640)
    os.replace(tmp, RUNTIME_STATE)


def ensure_code():
    global SETUP_CODE, CODE_EXPIRES
    with CODE_LOCK:
        now = time.time()
        if not SETUP_CODE or now >= CODE_EXPIRES:
            SETUP_CODE = f"{secrets.randbelow(1_000_000):06d}"
            CODE_EXPIRES = now + CODE_SECONDS
        write_runtime_state()
        return SETUP_CODE


def code_matches(value):
    return hmac.compare_digest(str(value).strip(), ensure_code())


def clean_sessions():
    now = time.time()
    with SESSIONS_LOCK:
        for token in [k for k, expiry in SESSIONS.items() if expiry <= now]:
            SESSIONS.pop(token, None)


def new_session():
    clean_sessions()
    token = secrets.token_urlsafe(32)
    with SESSIONS_LOCK:
        SESSIONS[token] = time.time() + SESSION_SECONDS
    return token


def session_token(headers):
    try:
        c = SimpleCookie(); c.load(headers.get("Cookie", ""))
        return c["YWDSETUP"].value if "YWDSETUP" in c else None
    except Exception:
        return None


def authenticated(headers):
    token = session_token(headers)
    if not token:
        return False
    clean_sessions()
    with SESSIONS_LOCK:
        expiry = SESSIONS.get(token)
        if expiry and expiry > time.time():
            SESSIONS[token] = time.time() + SESSION_SECONDS
            return True
    return False


def admin_finish(payload):
    p = subprocess.run(
        ["sudo", "-n", ADMIN, "setup-finish"], input=json.dumps(payload), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90, check=False)
    raw = (p.stdout or "").strip()
    try:
        out = json.loads(raw) if raw else {}
    except Exception:
        out = {"ok": False, "error": raw or p.stderr.strip() or "invalid admin response"}
    if p.returncode != 0 or not out.get("ok"):
        raise RuntimeError(str(out.get("error") or p.stderr.strip() or "setup finish failed")[:800])
    return out


def delayed_shutdown(server, delay=2.0):
    time.sleep(delay)
    server.shutdown()


class Server(ThreadingHTTPServer):
    allow_reuse_address = True


class H(BaseHTTPRequestHandler):
    server_version = "YWD-Hotspot-Setup/0.7"

    def log_message(self, fmt, *args):
        return

    def common_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")

    def send_bytes(self, status, data, content_type, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.common_headers()
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj, status=200, headers=None):
        self.send_bytes(status, json.dumps(obj, separators=(",", ":")).encode(),
                        "application/json; charset=utf-8", headers)

    def page(self, body, status=200):
        self.send_bytes(status, body.encode(), "text/html; charset=utf-8")

    def body_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            raise ValueError("invalid Content-Length")
        if length < 0 or length > MAX_BODY:
            raise ValueError("request body too large")
        raw = self.rfile.read(length)
        try:
            obj = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            raise ValueError("invalid JSON")
        if not isinstance(obj, dict):
            raise ValueError("JSON body must be an object")
        return obj

    def same_origin(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            p = urlparse(origin)
            host = self.headers.get("Host", "").split(":")[0]
            return p.scheme == "http" and p.port == PORT and p.hostname in {"ywd-hotspot.local", host}
        except Exception:
            return False

    def do_GET(self):
        path = urlparse(self.path).path
        if setup_complete():
            dashboard = dashboard_url()
            if path == "/api/status":
                self.send_json({"complete": True, "dashboard": dashboard})
            else:
                self.page(COMPLETE_HTML.replace("__DASHBOARD_URL__", dashboard))
            return
        ensure_code()
        if path == "/api/status":
            self.send_json({
                "complete": False,
                "authenticated": authenticated(self.headers),
                "expires_in_s": max(0, int(CODE_EXPIRES - time.time())),
                "config": public_config() if authenticated(self.headers) else None,
                "dashboard": dashboard_url(),
            })
            return
        if path in ("/", "/index.html"):
            self.page(WIZARD_HTML)
            return
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if not self.same_origin():
            self.send_json({"error": "origin rejected"}, 403); return
        if setup_complete():
            self.send_json({"error": "appliance already provisioned"}, 403); return
        try:
            body = self.body_json()
        except ValueError as exc:
            self.send_json({"error": str(exc)}, 400); return

        if path == "/api/unlock":
            ip = self.client_address[0]; now = time.time()
            fails = [t for t in FAILS.get(ip, []) if now - t < 60]; FAILS[ip] = fails
            if len(fails) >= 5:
                self.send_json({"error": "Too many failed codes; wait one minute"}, 429); return
            if not code_matches(body.get("code", "")):
                FAILS[ip].append(now)
                self.send_json({"error": "Invalid or expired setup code"}, 401); return
            FAILS[ip] = []
            token = new_session()
            self.send_json({"ok": True, "config": public_config()}, 200, {
                "Set-Cookie": f"YWDSETUP={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_SECONDS}"
            })
            return

        if path == "/api/finish":
            if not authenticated(self.headers):
                self.send_json({"error": "setup authorization required"}, 401); return
            try:
                out = admin_finish(body)
            except Exception as exc:
                self.send_json({"error": str(exc)}, 502); return
            try:
                RUNTIME_STATE.unlink()
            except FileNotFoundError:
                pass
            self.send_json(out)
            threading.Thread(target=delayed_shutdown, args=(self.server,), daemon=True).start()
            return

        self.send_json({"error": "not found"}, 404)


COMPLETE_HTML = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>YWD-Hotspot Setup Complete</title><style>body{font-family:system-ui;background:#081019;color:#e9f8ff;display:grid;place-items:center;min-height:100vh;margin:0}main{max-width:560px;padding:28px;background:#101c27;border:1px solid #29465b;border-radius:18px}a{color:#4bdcff}</style><main><h1>Setup complete</h1><p>This YWD-Hotspot has already been provisioned.</p><p>The dashboard is available at <a href="__DASHBOARD_URL__">__DASHBOARD_URL__</a></p></main>"""

WIZARD_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>YWD-Hotspot First Boot Setup</title>
<style>
:root{color-scheme:dark;--bg:#070d12;--panel:#0f1922;--line:#254258;--cyan:#45dcff;--text:#eaf8ff;--muted:#8da7b7;--bad:#ff6b7a;--good:#77efb0;--warn:#ffd166}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#102432 0,#070d12 55%);font:15px/1.45 system-ui,sans-serif;color:var(--text)}main{max-width:760px;margin:auto;padding:22px}.card{background:rgba(15,25,34,.97);border:1px solid var(--line);border-radius:18px;padding:22px;margin:0 0 18px;box-shadow:0 20px 60px #0008}.eyebrow{font:700 12px ui-monospace,monospace;color:var(--cyan);letter-spacing:.14em}h1{margin:.35rem 0}.muted,.hint{color:var(--muted)}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:620px){.grid{grid-template-columns:1fr}}label{display:block;margin:12px 0 5px;color:var(--muted);font-weight:650}input,select{width:100%;padding:12px;border-radius:10px;border:1px solid #31546d;background:#09131b;color:var(--text);font-size:16px}input[type=checkbox]{width:auto}.check{display:flex;gap:9px;align-items:center;color:var(--text)}button{padding:13px 16px;border:0;border-radius:11px;background:linear-gradient(90deg,var(--cyan),#8c8cff);color:#061118;font-weight:800;font-size:15px;cursor:pointer}button.secondary{background:#172a38;color:var(--text);border:1px solid var(--line)}button:disabled{cursor:wait;opacity:.65}.actions{display:flex;justify-content:space-between;gap:12px;margin-top:20px}.step{display:none}.step.active{display:block}.progress{display:flex;gap:5px;margin:14px 0 22px}.progress i{height:4px;flex:1;background:#1d3342;border-radius:999px}.progress i.on{background:var(--cyan)}.err{color:var(--bad);font-weight:700;white-space:pre-wrap}.finish-status{display:none;margin-top:16px;padding:12px 14px;border-radius:10px;border:1px solid var(--line);white-space:pre-wrap;font-weight:700}.finish-status.busy{display:block;color:var(--warn);border-color:#806b2f;background:#2a2414}.finish-status.bad{display:block;color:var(--bad);border-color:#7d3440;background:#291318}.finish-status.good{display:block;color:var(--good);border-color:#2f7553;background:#10271d}.summary{font-family:ui-monospace,monospace;background:#081119;border:1px solid var(--line);padding:14px;border-radius:12px;white-space:pre-wrap}.dashboard-link{color:var(--cyan);font-weight:800;overflow-wrap:anywhere}.radio-group[hidden],.network-fields[hidden]{display:none}code{color:var(--cyan)}details{margin-top:14px}
</style></head><body><main><div class="card"><div class="eyebrow">YWD-HOTSPOT OS · M4</div><h1>First-boot setup</h1><p class="muted">RF stays off until the final page. The setup code is shown on the hotspot OLED and expires automatically. This temporary provisioning portal uses HTTP so common browsers can open it without certificate warnings.</p><div class="progress" id="prog"></div><div id="err" class="err"></div>
<section class="step active" data-step="0"><h2>1 · Verify physical access</h2><p>Enter the six-digit code currently shown on the OLED.</p><label>One-time setup code</label><input id="code" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="000000"><div class="actions"><span></span><button onclick="unlock()">Unlock setup</button></div></section>
<section class="step" data-step="1"><h2>2 · Dashboard security</h2><p>Create the permanent password used for write/control access after setup.</p><label>Dashboard control password</label><input id="webpw" type="password" autocomplete="new-password" minlength="8"><label>Confirm password</label><input id="webpw2" type="password" autocomplete="new-password" minlength="8"><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="next()">Next</button></div></section>
<section class="step" data-step="2"><h2>3 · Station identity</h2><div class="grid"><div><label>Callsign</label><input id="callsign" maxlength="12" placeholder="KJ6YWD"></div><div><label>Base DMR ID</label><input id="dmrid" maxlength="8" inputmode="numeric"></div><div><label>ESSID</label><input id="essid" maxlength="2" value="01" inputmode="numeric"></div><div><label>Description</label><input id="description" maxlength="20" value="YWD Hotspot"></div><div><label>Station URL</label><input id="stationurl" maxlength="124" placeholder="https://www.qrz.com/db/CALL"></div></div><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="next()">Next</button></div></section>
<section class="step" data-step="3"><h2>4 · Location</h2><p class="hint">Approximate city-level coordinates are fine; an exact home address is not needed.</p><div class="grid"><div><label>Location</label><input id="location" maxlength="20" placeholder="Redding, CA"></div><div><label>Antenna height (m)</label><input id="height" type="number" min="0" max="9999" value="0"></div><div><label>Latitude</label><input id="lat" type="number" step="0.0000001" min="-90" max="90" value="0"></div><div><label>Longitude</label><input id="lon" type="number" step="0.0000001" min="-180" max="180" value="0"></div></div><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="next()">Next</button></div></section>
<section class="step" data-step="4"><h2>5 · MMDVM radio</h2><div class="grid"><div><label>HAT mode</label><select id="radiomode" onchange="radioModeChanged()"><option value="simplex">Simplex</option><option value="duplex">Duplex</option></select></div><div class="radio-group" id="simplexGroup"><label>Simplex frequency (MHz)</label><input id="freq" type="number" step="0.000001" value="446.525000"></div><div class="radio-group" id="duplexRxGroup"><label>Duplex hotspot RX (MHz)</label><input id="rxfreq" type="number" step="0.000001" value="446.525000"><p class="hint">Your radio transmits on this frequency.</p></div><div class="radio-group" id="duplexTxGroup"><label>Duplex hotspot TX (MHz)</label><input id="txfreq" type="number" step="0.000001" value="446.525000"><p class="hint">Your radio receives on this frequency.</p></div><div><label>Color code</label><input id="cc" type="number" min="0" max="15" value="1"></div><div><label>RX level</label><input id="rxlevel" type="number" min="0" max="100" value="50"></div><div><label>TX level</label><input id="txlevel" type="number" min="0" max="100" value="50"></div><div><label>RF level</label><input id="rflevel" type="number" min="0" max="100" value="100"></div></div><details><summary>Advanced modem settings</summary><div class="grid"><div><label>RX offset</label><input id="rxoff" type="number" min="-10000" max="10000" value="0"></div><div><label>TX offset</label><input id="txoff" type="number" min="-10000" max="10000" value="0"></div><div><label>TX invert</label><select id="txinv"><option value="1">1</option><option value="0">0</option></select></div><div><label>RX invert</label><select id="rxinv"><option value="0">0</option><option value="1">1</option></select></div><div><label>UART</label><input id="uart" value="/dev/serial0"></div><div><label>UART speed</label><input id="uartspeed" type="number" value="115200"></div><div><label>Jitter (ms)</label><input id="jitter" type="number" value="360"></div><div><label>Call hang (s)</label><input id="callhang" type="number" value="3"></div><div><label>TX hang (s)</label><input id="txhang" type="number" value="4"></div><div><label>RF timeout (s)</label><input id="timeout" type="number" value="180"></div></div></details><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="next()">Next</button></div></section>
<section class="step" data-step="5"><h2>6 · BrandMeister</h2><label class="check"><input id="bmenabled" type="checkbox" checked> Enable BrandMeister networking</label><div class="grid"><div><label>Master</label><input id="bmmaster" value="3103.master.brandmeister.network"></div><div><label>Port</label><input id="bmport" type="number" value="62031"></div></div><label>Hotspot Security password</label><input id="bmpw" type="password" autocomplete="new-password"><label>BrandMeister API key <span class="hint">(optional)</span></label><input id="bmkey" type="password" autocomplete="new-password"><p class="hint">Paste the full API key or leave this blank. Partial/short API keys are rejected.</p><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="next()">Next</button></div></section>
<section class="step" data-step="6"><h2>7 · TGIF</h2><label class="check"><input id="tgifenabled" type="checkbox" onchange="tgifChanged()"> Enable TGIF networking</label><div class="network-fields" id="tgifFields" hidden><div class="grid"><div><label>Master</label><input id="tgifmaster" value="tgif.network"></div><div><label>Port</label><input id="tgifport" type="number" value="62031"></div></div><label>TGIF security password</label><input id="tgifpw" type="password" autocomplete="new-password"><p class="hint">The password is stored in protected hotspot configuration and is never shown in the setup summary.</p></div><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="next()">Next</button></div></section>
<section class="step" data-step="7"><h2>8 · Display &amp; appliance</h2><label class="check"><input id="displayenabled" type="checkbox" checked> OLED enabled</label><div class="grid"><div><label>Brightness</label><input id="brightness" type="number" min="1" max="255" value="127"></div><div><label>Idle timeout (s; 0 = never)</label><input id="idletimeout" type="number" min="0" max="86400" value="0"></div></div><details><summary>Advanced appliance settings</summary><div class="grid"><div><label>Dashboard port</label><input id="webport" type="number" min="1024" max="65535" value="8080"></div><div><label>Journal size (MB)</label><input id="journal" type="number" min="16" max="512" value="100"></div><div><label>DMR ID update interval (days)</label><input id="dmrdays" type="number" min="1" max="30" value="7"></div><div><label>Config history entries</label><input id="history" type="number" min="3" max="50" value="10"></div></div></details><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="review()">Review</button></div></section>
<section class="step" data-step="8"><h2>9 · Review &amp; finish</h2><div id="summary" class="summary"></div><p>Secrets are never echoed here.</p><label class="check"><input id="enableRf" type="checkbox"> Enable RF services now and at boot</label><p class="hint">Leave this unchecked if you want to calibrate or inspect configuration before transmitting.</p><div id="finishStatus" class="finish-status" role="status" aria-live="polite"></div><div class="actions"><button class="secondary" onclick="prev()">Back</button><button id="finishBtn" onclick="finishSetup()">Finish setup</button></div></section>
<section class="step" data-step="9"><h2>Setup complete</h2><p id="doneText">Configuration has been applied.</p><p id="dashText">The dashboard is now available at:</p><p><a id="dashLink" class="dashboard-link" href="http://ywd-hotspot.local:8080/">http://ywd-hotspot.local:8080/</a></p><p id="redirectText" class="hint"></p></section>
</div></main><script>
let step=0,cfg=null;const $=id=>document.getElementById(id);function err(s=''){$('err').textContent=s}function finishStatus(s='',kind=''){let e=$('finishStatus');e.textContent=s;e.className='finish-status'+(kind?' '+kind:'')}function show(n){step=n;document.querySelectorAll('.step').forEach(x=>x.classList.toggle('active',+x.dataset.step===n));renderProg();scrollTo(0,0)}function renderProg(){let p=$('prog');p.innerHTML='';for(let i=0;i<9;i++){let e=document.createElement('i');if(i<=Math.min(step,8))e.className='on';p.appendChild(e)}}function prev(){if(step>1)show(step-1)}function next(){err();if(step===1&&($('webpw').value.length<8||$('webpw').value!==$('webpw2').value)){err('Dashboard passwords must match and be at least 8 characters.');return}show(step+1)}
async function api(path,body){let r=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,credentials:'same-origin'});let text=await r.text();let j={};try{j=text?JSON.parse(text):{}}catch(e){throw new Error(text||('Invalid server response (HTTP '+r.status+')'))}if(!r.ok)throw new Error(j.error||('HTTP '+r.status));return j}async function unlock(){err();let code=$('code').value.replace(/\D/g,'');if(code.length!==6){err('Enter the six-digit OLED code.');return}try{let j=await api('/api/unlock',{code});cfg=j.config;fill(cfg);show(1)}catch(e){err(e.message)}}
function radioModeChanged(){let duplex=$('radiomode').value==='duplex';$('simplexGroup').hidden=duplex;$('duplexRxGroup').hidden=!duplex;$('duplexTxGroup').hidden=!duplex}function tgifChanged(){$('tgifFields').hidden=!$('tgifenabled').checked}function fill(c){try{$('callsign').value=c.station.callsign==='NOCALL'?'':c.station.callsign;$('dmrid').value=c.station.base_dmr_id==='00000'?'':c.station.base_dmr_id;$('essid').value=c.station.essid||'01';$('description').value=c.station.description||'YWD Hotspot';$('stationurl').value=c.station.url||'';$('location').value=c.station.location==='Hotspot'?'':c.station.location;$('height').value=c.station.height??0;$('lat').value=c.station.latitude??0;$('lon').value=c.station.longitude??0;$('radiomode').value=c.radio.mode||'simplex';$('freq').value=(Number(c.radio.frequency_hz)/1e6).toFixed(6);$('rxfreq').value=(Number(c.radio.rx_frequency_hz??c.radio.frequency_hz)/1e6).toFixed(6);$('txfreq').value=(Number(c.radio.tx_frequency_hz??c.radio.frequency_hz)/1e6).toFixed(6);$('cc').value=c.radio.color_code;$('rxlevel').value=c.radio.rx_level;$('txlevel').value=c.radio.tx_level;$('rflevel').value=c.radio.rf_level;$('rxoff').value=c.radio.rx_offset;$('txoff').value=c.radio.tx_offset;$('txinv').value=String(c.radio.tx_invert);$('rxinv').value=String(c.radio.rx_invert);$('uart').value=c.radio.uart;$('uartspeed').value=c.radio.uart_speed;$('jitter').value=c.radio.jitter_ms;$('callhang').value=c.radio.call_hang_s;$('txhang').value=c.radio.tx_hang_s;$('timeout').value=c.radio.timeout_s;$('bmenabled').checked=!!c.brandmeister.enabled;$('bmmaster').value=c.brandmeister.master;$('bmport').value=c.brandmeister.port;$('tgifenabled').checked=!!c.tgif?.enabled;$('tgifmaster').value=c.tgif?.master||'tgif.network';$('tgifport').value=c.tgif?.port||62031;$('displayenabled').checked=!!c.display.enabled;$('brightness').value=c.display.brightness;$('idletimeout').value=c.display.idle_timeout_s;$('webport').value=c.web.port;$('journal').value=c.maintenance.journal_max_mb;$('dmrdays').value=c.maintenance.dmrid_update_days;$('history').value=c.maintenance.config_history_keep;radioModeChanged();tgifChanged()}catch(e){}}
function cloneConfig(){if(!cfg)throw new Error('Setup configuration has not been loaded. Unlock setup again.');return JSON.parse(JSON.stringify(cfg))}function mhzValue(id,label){let n=Number($(id).value);if(!Number.isFinite(n)||n<=0)throw new Error(label+' is invalid.');return Math.round(n*1e6)}function build(){let c=cloneConfig();c.station.callsign=$('callsign').value.trim().toUpperCase();c.station.base_dmr_id=$('dmrid').value.trim();c.station.essid=$('essid').value.trim();c.station.hotspot_id=0;c.station.location=$('location').value.trim()||'Hotspot';c.station.description=$('description').value.trim()||'YWD Hotspot';c.station.latitude=Number($('lat').value);c.station.longitude=Number($('lon').value);c.station.height=Number($('height').value);c.station.url=$('stationurl').value.trim();c.radio.mode=$('radiomode').value;c.radio.frequency_hz=mhzValue('freq','Simplex frequency');c.radio.rx_frequency_hz=mhzValue('rxfreq','Duplex hotspot RX frequency');c.radio.tx_frequency_hz=mhzValue('txfreq','Duplex hotspot TX frequency');c.radio.color_code=Number($('cc').value);c.radio.rx_offset=Number($('rxoff').value);c.radio.tx_offset=Number($('txoff').value);c.radio.tx_invert=Number($('txinv').value);c.radio.rx_invert=Number($('rxinv').value);c.radio.rx_level=Number($('rxlevel').value);c.radio.tx_level=Number($('txlevel').value);c.radio.rf_level=Number($('rflevel').value);c.radio.jitter_ms=Number($('jitter').value);c.radio.call_hang_s=Number($('callhang').value);c.radio.tx_hang_s=Number($('txhang').value);c.radio.timeout_s=Number($('timeout').value);c.radio.uart=$('uart').value.trim();c.radio.uart_speed=Number($('uartspeed').value);c.brandmeister.enabled=$('bmenabled').checked;c.brandmeister.master=$('bmmaster').value.trim();c.brandmeister.port=Number($('bmport').value);c.brandmeister.password='';delete c.brandmeister.password_configured;c.tgif=c.tgif||{};c.tgif.enabled=$('tgifenabled').checked;c.tgif.master=$('tgifmaster').value.trim()||'tgif.network';c.tgif.port=Number($('tgifport').value);c.tgif.password='';delete c.tgif.password_configured;c.display.enabled=$('displayenabled').checked;c.display.brightness=Number($('brightness').value);c.display.idle_timeout_s=Number($('idletimeout').value);c.web.bind='0.0.0.0';c.web.port=Number($('webport').value);c.maintenance.rf_autostart=$('enableRf').checked;c.maintenance.persistent_journal=true;c.maintenance.journal_max_mb=Number($('journal').value);c.maintenance.dmrid_update_days=Number($('dmrdays').value);c.maintenance.config_history_keep=Number($('history').value);return {config:c,web_password:$('webpw').value,hotspot_password:$('bmpw').value,tgif_password:$('tgifpw').value,bm_api_key:$('bmkey').value.trim(),enable_rf:$('enableRf').checked}}
function validateReview(p){if(!p.config.station.callsign||!p.config.station.base_dmr_id)throw new Error('Callsign and DMR ID are required.');if(p.config.brandmeister.enabled&&!p.hotspot_password)throw new Error('Hotspot Security password is required when BrandMeister is enabled.');if(p.config.tgif.enabled&&!p.tgif_password)throw new Error('TGIF security password is required when TGIF is enabled.');if(p.bm_api_key&&p.bm_api_key.length<12)throw new Error('BrandMeister API key looks incomplete. Paste the full API key or leave it blank.')}function review(){err();try{let p=build();validateReview(p);let c=p.config;let radio=c.radio.mode==='duplex'?`Radio mode: DUPLEX\nHotspot RX: ${(c.radio.rx_frequency_hz/1e6).toFixed(6)} MHz\nHotspot TX: ${(c.radio.tx_frequency_hz/1e6).toFixed(6)} MHz`:`Radio mode: SIMPLEX\nFrequency: ${(c.radio.frequency_hz/1e6).toFixed(6)} MHz`;$('summary').textContent=`Callsign: ${c.station.callsign}\nDMR ID: ${c.station.base_dmr_id}\nESSID: ${c.station.essid||'(none)'}\nLocation: ${c.station.location}\n${radio}\nColor Code: ${c.radio.color_code}\nRX/TX Level: ${c.radio.rx_level}/${c.radio.tx_level}\nBrandMeister: ${c.brandmeister.enabled?c.brandmeister.master:'disabled'}\nBM Hotspot Security: ${p.hotspot_password?'configured':'not configured'}\nBM API key: ${p.bm_api_key?'configured':'not configured'}\nTGIF: ${c.tgif.enabled?(c.tgif.master+':'+c.tgif.port):'disabled'}\nTGIF password: ${p.tgif_password?'configured':'not configured'}\nOLED: ${c.display.enabled?'enabled':'disabled'}\nDashboard port: ${c.web.port}\nRF after setup: ${p.enable_rf?'ENABLE':'remain OFF'}`;show(8)}catch(e){err(e.message)}}
async function finishSetup(){err();finishStatus();let btn=$('finishBtn');btn.disabled=true;btn.textContent='Applying setup...';try{let p=build();validateReview(p);finishStatus('Applying configuration and securing the dashboard. This can take a moment…','busy');let j=await api('/api/finish',p);let dashboard=j.dashboard||('http://ywd-hotspot.local:'+p.config.web.port+'/');$('doneText').textContent=j.rf_started===false&&j.rf_error?('Setup saved; RF could not start: '+j.rf_error):('Configuration applied successfully. RF '+(j.rf_started?'is enabled.':'remains off.'));$('dashLink').href=dashboard;$('dashLink').textContent=dashboard;show(9);let remaining=5;$('redirectText').textContent='Opening the dashboard automatically in '+remaining+' seconds…';let timer=setInterval(()=>{remaining--;if(remaining<=0){clearInterval(timer);window.location.href=dashboard;return}$('redirectText').textContent='Opening the dashboard automatically in '+remaining+' seconds…'},1000)}catch(e){finishStatus('Setup could not be completed:\n'+e.message,'bad');btn.disabled=false;btn.textContent='Finish setup';$('finishStatus').scrollIntoView({block:'center',behavior:'smooth'})}}renderProg();radioModeChanged();tgifChanged();
</script></body></html>"""


def main():
    if setup_complete():
        return
    ensure_code()
    server = Server((BIND, PORT), H)
    print(f"YWD first-boot setup HTTP listening on {BIND}:{PORT}", flush=True)
    try:
        server.serve_forever()
    finally:
        try:
            RUNTIME_STATE.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
