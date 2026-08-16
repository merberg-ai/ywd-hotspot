#!/usr/bin/env python3
"""Secure first-boot setup server for YWD-Hotspot OS M4.

Runs unprivileged as ywd-hotspot. A short-lived setup code is generated in /run
and shown on the OLED. The browser unlocks this HTTPS-only service with that
code, then the server delegates exactly one privileged operation to the narrow
ywd-hotspot-admin setup-finish action.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
import ssl
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
TLS_DIR = VAR / "setup-tls"
CERT = TLS_DIR / "cert.pem"
KEY = TLS_DIR / "key.pem"
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


def ensure_tls():
    TLS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(TLS_DIR, 0o700)
    if CERT.is_file() and KEY.is_file():
        return
    p = run([
        "/usr/bin/openssl", "req", "-x509", "-newkey", "rsa:2048", "-sha256",
        "-nodes", "-days", "3650", "-keyout", str(KEY), "-out", str(CERT),
        "-subj", "/CN=ywd-hotspot.local",
        "-addext", "subjectAltName=DNS:ywd-hotspot.local,IP:10.42.0.1",
    ], timeout=60)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "openssl certificate generation failed")[:800])
    os.chmod(KEY, 0o600)
    os.chmod(CERT, 0o644)


def write_runtime_state():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    now = time.time()
    doc = {
        "mode": "first_boot",
        "code": SETUP_CODE,
        "expires_at": int(CODE_EXPIRES),
        "expires_in_s": max(0, int(CODE_EXPIRES - now)),
        "url": f"https://ywd-hotspot.local:{PORT}/",
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


class Server(ThreadingHTTPServer):
    allow_reuse_address = True


class H(BaseHTTPRequestHandler):
    server_version = "YWD-Hotspot-Setup/0.4"

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
            return p.scheme == "https" and p.port == PORT and p.hostname in {"ywd-hotspot.local", host}
        except Exception:
            return False

    def do_GET(self):
        path = urlparse(self.path).path
        if setup_complete():
            if path == "/api/status":
                self.send_json({"complete": True, "dashboard": "http://ywd-hotspot.local:8080/"})
            else:
                self.page(COMPLETE_HTML)
            return
        ensure_code()
        if path == "/api/status":
            self.send_json({
                "complete": False,
                "authenticated": authenticated(self.headers),
                "expires_in_s": max(0, int(CODE_EXPIRES - time.time())),
                "config": public_config() if authenticated(self.headers) else None,
                "dashboard": "http://ywd-hotspot.local:8080/",
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
                "Set-Cookie": f"YWDSETUP={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age={SESSION_SECONDS}"
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
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        self.send_json({"error": "not found"}, 404)


COMPLETE_HTML = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>YWD-Hotspot Setup Complete</title><style>body{font-family:system-ui;background:#081019;color:#e9f8ff;display:grid;place-items:center;min-height:100vh;margin:0}main{max-width:560px;padding:28px;background:#101c27;border:1px solid #29465b;border-radius:18px}a{color:#4bdcff}</style><main><h1>Setup complete</h1><p>This YWD-Hotspot has already been provisioned.</p><p><a href="http://ywd-hotspot.local:8080/">Open the dashboard</a></p></main>"""

WIZARD_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>YWD-Hotspot First Boot Setup</title>
<style>
:root{color-scheme:dark;--bg:#070d12;--panel:#0f1922;--line:#254258;--cyan:#45dcff;--text:#eaf8ff;--muted:#8da7b7;--bad:#ff6b7a}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#102432 0,#070d12 55%);font:15px/1.45 system-ui,sans-serif;color:var(--text)}main{max-width:760px;margin:auto;padding:22px}.card{background:rgba(15,25,34,.97);border:1px solid var(--line);border-radius:18px;padding:22px;margin:0 0 18px;box-shadow:0 20px 60px #0008}.eyebrow{font:700 12px ui-monospace,monospace;color:var(--cyan);letter-spacing:.14em}h1{margin:.35rem 0}.muted,.hint{color:var(--muted)}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:620px){.grid{grid-template-columns:1fr}}label{display:block;margin:12px 0 5px;color:var(--muted);font-weight:650}input,select{width:100%;padding:12px;border-radius:10px;border:1px solid #31546d;background:#09131b;color:var(--text);font-size:16px}input[type=checkbox]{width:auto}.check{display:flex;gap:9px;align-items:center;color:var(--text)}button{padding:13px 16px;border:0;border-radius:11px;background:linear-gradient(90deg,var(--cyan),#8c8cff);color:#061118;font-weight:800;font-size:15px;cursor:pointer}button.secondary{background:#172a38;color:var(--text);border:1px solid var(--line)}.actions{display:flex;justify-content:space-between;gap:12px;margin-top:20px}.step{display:none}.step.active{display:block}.progress{display:flex;gap:5px;margin:14px 0 22px}.progress i{height:4px;flex:1;background:#1d3342;border-radius:999px}.progress i.on{background:var(--cyan)}.err{color:var(--bad);font-weight:700;white-space:pre-wrap}.summary{font-family:ui-monospace,monospace;background:#081119;border:1px solid var(--line);padding:14px;border-radius:12px;white-space:pre-wrap}code{color:var(--cyan)}details{margin-top:14px}
</style></head><body><main><div class="card"><div class="eyebrow">YWD-HOTSPOT OS · M4</div><h1>Secure first-boot setup</h1><p class="muted">RF stays off until the final page. The setup code is shown on the hotspot OLED and expires automatically.</p><div class="progress" id="prog"></div><div id="err" class="err"></div>
<section class="step active" data-step="0"><h2>1 · Verify physical access</h2><p>Enter the six-digit code currently shown on the OLED.</p><label>One-time setup code</label><input id="code" inputmode="numeric" maxlength="6" autocomplete="one-time-code" placeholder="000000"><div class="actions"><span></span><button onclick="unlock()">Unlock setup</button></div></section>
<section class="step" data-step="1"><h2>2 · Dashboard security</h2><p>Create the permanent password used for write/control access after setup.</p><label>Dashboard control password</label><input id="webpw" type="password" autocomplete="new-password" minlength="8"><label>Confirm password</label><input id="webpw2" type="password" autocomplete="new-password" minlength="8"><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="next()">Next</button></div></section>
<section class="step" data-step="2"><h2>3 · Station identity</h2><div class="grid"><div><label>Callsign</label><input id="callsign" maxlength="12" placeholder="KJ6YWD"></div><div><label>Base DMR ID</label><input id="dmrid" maxlength="8" inputmode="numeric"></div><div><label>ESSID</label><input id="essid" maxlength="2" value="01" inputmode="numeric"></div><div><label>Description</label><input id="description" maxlength="20" value="YWD Hotspot"></div><div><label>Station URL</label><input id="stationurl" maxlength="124" placeholder="https://www.qrz.com/db/CALL"></div></div><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="next()">Next</button></div></section>
<section class="step" data-step="3"><h2>4 · Location</h2><p class="hint">Approximate city-level coordinates are fine; an exact home address is not needed.</p><div class="grid"><div><label>Location</label><input id="location" maxlength="20" placeholder="Redding, CA"></div><div><label>Antenna height (m)</label><input id="height" type="number" min="0" max="9999" value="0"></div><div><label>Latitude</label><input id="lat" type="number" step="0.0000001" min="-90" max="90" value="0"></div><div><label>Longitude</label><input id="lon" type="number" step="0.0000001" min="-180" max="180" value="0"></div></div><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="next()">Next</button></div></section>
<section class="step" data-step="4"><h2>5 · MMDVM radio</h2><div class="grid"><div><label>Frequency (MHz)</label><input id="freq" type="number" step="0.000001" value="446.525000"></div><div><label>Color code</label><input id="cc" type="number" min="0" max="15" value="1"></div><div><label>RX level</label><input id="rxlevel" type="number" min="0" max="100" value="50"></div><div><label>TX level</label><input id="txlevel" type="number" min="0" max="100" value="50"></div><div><label>RF level</label><input id="rflevel" type="number" min="0" max="100" value="100"></div></div><details><summary>Advanced modem settings</summary><div class="grid"><div><label>RX offset</label><input id="rxoff" type="number" min="-10000" max="10000" value="0"></div><div><label>TX offset</label><input id="txoff" type="number" min="-10000" max="10000" value="0"></div><div><label>TX invert</label><select id="txinv"><option value="1">1</option><option value="0">0</option></select></div><div><label>RX invert</label><select id="rxinv"><option value="0">0</option><option value="1">1</option></select></div><div><label>UART</label><input id="uart" value="/dev/serial0"></div><div><label>UART speed</label><input id="uartspeed" type="number" value="115200"></div><div><label>Jitter (ms)</label><input id="jitter" type="number" value="360"></div><div><label>Call hang (s)</label><input id="callhang" type="number" value="3"></div><div><label>TX hang (s)</label><input id="txhang" type="number" value="4"></div><div><label>RF timeout (s)</label><input id="timeout" type="number" value="180"></div></div></details><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="next()">Next</button></div></section>
<section class="step" data-step="5"><h2>6 · BrandMeister</h2><label class="check"><input id="bmenabled" type="checkbox" checked> Enable BrandMeister networking</label><div class="grid"><div><label>Master</label><input id="bmmaster" value="3103.master.brandmeister.network"></div><div><label>Port</label><input id="bmport" type="number" value="62031"></div></div><label>Hotspot Security password</label><input id="bmpw" type="password" autocomplete="new-password"><label>BrandMeister API key <span class="hint">(optional)</span></label><input id="bmkey" type="password" autocomplete="new-password"><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="next()">Next</button></div></section>
<section class="step" data-step="6"><h2>7 · Display &amp; appliance</h2><label class="check"><input id="displayenabled" type="checkbox" checked> OLED enabled</label><div class="grid"><div><label>Brightness</label><input id="brightness" type="number" min="1" max="255" value="127"></div><div><label>Idle timeout (s; 0 = never)</label><input id="idletimeout" type="number" min="0" max="86400" value="0"></div></div><details><summary>Advanced appliance settings</summary><div class="grid"><div><label>Dashboard port</label><input id="webport" type="number" min="1024" max="65535" value="8080"></div><div><label>Journal size (MB)</label><input id="journal" type="number" min="16" max="512" value="100"></div><div><label>DMR ID update interval (days)</label><input id="dmrdays" type="number" min="1" max="30" value="7"></div><div><label>Config history entries</label><input id="history" type="number" min="3" max="50" value="10"></div></div></details><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="review()">Review</button></div></section>
<section class="step" data-step="7"><h2>8 · Review &amp; finish</h2><div id="summary" class="summary"></div><p>Secrets are never echoed here.</p><label class="check"><input id="enableRf" type="checkbox"> Enable RF services now and at boot</label><p class="hint">Leave this unchecked if you want to calibrate or inspect configuration before transmitting.</p><div class="actions"><button class="secondary" onclick="prev()">Back</button><button onclick="finishSetup()">Finish setup</button></div></section>
<section class="step" data-step="8"><h2>Setup complete</h2><p id="doneText">Configuration has been applied.</p><p><a href="http://ywd-hotspot.local:8080/" style="color:var(--cyan)">Open YWD-Hotspot dashboard</a></p></section>
</div></main><script>
let step=0,cfg=null;const $=id=>document.getElementById(id);function err(s=''){$('err').textContent=s}function show(n){step=n;document.querySelectorAll('.step').forEach(x=>x.classList.toggle('active',+x.dataset.step===n));renderProg();scrollTo(0,0)}function renderProg(){let p=$('prog');p.innerHTML='';for(let i=0;i<8;i++){let e=document.createElement('i');if(i<=Math.min(step,7))e.className='on';p.appendChild(e)}}function prev(){if(step>1)show(step-1)}function next(){err();if(step===1&&($('webpw').value.length<8||$('webpw').value!==$('webpw2').value)){err('Dashboard passwords must match and be at least 8 characters.');return}show(step+1)}
async function api(path,body){let r=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,credentials:'same-origin'});let j=await r.json();if(!r.ok)throw new Error(j.error||('HTTP '+r.status));return j}async function unlock(){err();let code=$('code').value.replace(/\D/g,'');if(code.length!==6){err('Enter the six-digit OLED code.');return}try{let j=await api('/api/unlock',{code});cfg=j.config;fill(cfg);show(1)}catch(e){err(e.message)}}
function fill(c){try{$('callsign').value=c.station.callsign==='NOCALL'?'':c.station.callsign;$('dmrid').value=c.station.base_dmr_id==='00000'?'':c.station.base_dmr_id;$('essid').value=c.station.essid||'01';$('description').value=c.station.description||'YWD Hotspot';$('stationurl').value=c.station.url||'';$('location').value=c.station.location==='Hotspot'?'':c.station.location;$('height').value=c.station.height??0;$('lat').value=c.station.latitude??0;$('lon').value=c.station.longitude??0;$('freq').value=(Number(c.radio.frequency_hz)/1e6).toFixed(6);$('cc').value=c.radio.color_code;$('rxlevel').value=c.radio.rx_level;$('txlevel').value=c.radio.tx_level;$('rflevel').value=c.radio.rf_level;$('rxoff').value=c.radio.rx_offset;$('txoff').value=c.radio.tx_offset;$('txinv').value=String(c.radio.tx_invert);$('rxinv').value=String(c.radio.rx_invert);$('uart').value=c.radio.uart;$('uartspeed').value=c.radio.uart_speed;$('jitter').value=c.radio.jitter_ms;$('callhang').value=c.radio.call_hang_s;$('txhang').value=c.radio.tx_hang_s;$('timeout').value=c.radio.timeout_s;$('bmenabled').checked=!!c.brandmeister.enabled;$('bmmaster').value=c.brandmeister.master;$('bmport').value=c.brandmeister.port;$('displayenabled').checked=!!c.display.enabled;$('brightness').value=c.display.brightness;$('idletimeout').value=c.display.idle_timeout_s;$('webport').value=c.web.port;$('journal').value=c.maintenance.journal_max_mb;$('dmrdays').value=c.maintenance.dmrid_update_days;$('history').value=c.maintenance.config_history_keep}catch(e){}}
function build(){let mhz=Number($('freq').value);if(!Number.isFinite(mhz))throw new Error('Frequency is invalid.');return {config:{schema:3,station:{callsign:$('callsign').value.trim().toUpperCase(),base_dmr_id:$('dmrid').value.trim(),essid:$('essid').value.trim(),hotspot_id:0,location:$('location').value.trim()||'Hotspot',description:$('description').value.trim()||'YWD Hotspot',latitude:Number($('lat').value),longitude:Number($('lon').value),height:Number($('height').value),url:$('stationurl').value.trim()},radio:{frequency_hz:Math.round(mhz*1e6),color_code:Number($('cc').value),rx_offset:Number($('rxoff').value),tx_offset:Number($('txoff').value),tx_invert:Number($('txinv').value),rx_invert:Number($('rxinv').value),rx_level:Number($('rxlevel').value),tx_level:Number($('txlevel').value),rf_level:Number($('rflevel').value),jitter_ms:Number($('jitter').value),call_hang_s:Number($('callhang').value),tx_hang_s:Number($('txhang').value),timeout_s:Number($('timeout').value),uart:$('uart').value.trim(),uart_speed:Number($('uartspeed').value)},brandmeister:{enabled:$('bmenabled').checked,master:$('bmmaster').value.trim(),port:Number($('bmport').value),password:''},display:{enabled:$('displayenabled').checked,i2c_bus:1,address:'0x3c',brightness:Number($('brightness').value),idle_timeout_s:Number($('idletimeout').value)},web:{bind:'0.0.0.0',port:Number($('webport').value)},maintenance:{rf_autostart:$('enableRf').checked,persistent_journal:true,journal_max_mb:Number($('journal').value),dmrid_update_days:Number($('dmrdays').value),config_history_keep:Number($('history').value)}},web_password:$('webpw').value,hotspot_password:$('bmpw').value,bm_api_key:$('bmkey').value.trim(),enable_rf:$('enableRf').checked}}
function review(){err();try{let p=build();if(!p.config.station.callsign||!p.config.station.base_dmr_id)throw new Error('Callsign and DMR ID are required.');if(p.config.brandmeister.enabled&&!p.hotspot_password)throw new Error('Hotspot Security password is required when BrandMeister is enabled.');let c=p.config;$('summary').textContent=`Callsign: ${c.station.callsign}\nDMR ID: ${c.station.base_dmr_id}\nESSID: ${c.station.essid||'(none)'}\nLocation: ${c.station.location}\nFrequency: ${(c.radio.frequency_hz/1e6).toFixed(6)} MHz\nColor Code: ${c.radio.color_code}\nRX/TX Level: ${c.radio.rx_level}/${c.radio.tx_level}\nBrandMeister: ${c.brandmeister.enabled?c.brandmeister.master:'disabled'}\nHotspot Security: ${p.hotspot_password?'configured':'not configured'}\nBM API key: ${p.bm_api_key?'configured':'not configured'}\nOLED: ${c.display.enabled?'enabled':'disabled'}\nDashboard port: ${c.web.port}\nRF after setup: ${p.enable_rf?'ENABLE':'remain OFF'}`;show(7)}catch(e){err(e.message)}}
async function finishSetup(){err();try{let p=build();let j=await api('/api/finish',p);$('doneText').textContent=j.rf_started===false&&j.rf_error?('Setup saved; RF could not start: '+j.rf_error):('Configuration applied. RF '+(j.rf_started?'is enabled.':'remains off.'));show(8)}catch(e){err(e.message)}}renderProg();
</script></body></html>"""


def main():
    if setup_complete():
        return
    ensure_tls(); ensure_code()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(CERT), str(KEY))
    server = Server((BIND, PORT), H)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print(f"YWD first-boot setup HTTPS listening on {BIND}:{PORT}", flush=True)
    try:
        server.serve_forever()
    finally:
        try:
            RUNTIME_STATE.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
