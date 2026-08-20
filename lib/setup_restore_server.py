#!/usr/bin/env python3
"""Alpha18.2 wrapper adding encrypted backup restore to first-boot setup."""
from __future__ import annotations

import json
import ssl
import subprocess
import threading
from urllib.parse import urlparse

import setup_server as base


def admin(action, payload, timeout=150):
    p = subprocess.run(["sudo", "-n", base.ADMIN, action], input=json.dumps(payload), text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    raw = (p.stdout or "").strip()
    try:
        out = json.loads(raw) if raw else {}
    except Exception:
        out = {"ok": False, "error": raw or p.stderr.strip() or "invalid admin response"}
    if p.returncode != 0 or not out.get("ok"):
        raise RuntimeError(str(out.get("error") or p.stderr.strip() or "restore admin failed")[:1200])
    return out


def injected_wizard():
    marker = '<div class="progress" id="prog"></div>'
    extra = '<div class="restore-choice"><p><strong>Already have a YWD-Hotspot backup?</strong></p><p><a href="/restore" style="color:var(--cyan);font-weight:800">RESTORE FROM .YWDSETTINGS BACKUP</a></p><p class="hint">Restore uses the same OLED physical-access code and keeps RF off until you explicitly approve it.</p></div>'
    return base.WIZARD_HTML.replace(marker, extra + marker, 1)


RESTORE_HTML = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Restore YWD-Hotspot</title><style>:root{color-scheme:dark;--bg:#070d12;--panel:#0f1922;--line:#254258;--cyan:#45dcff;--text:#eaf8ff;--muted:#8da7b7;--bad:#ff6b7a}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#102432 0,#070d12 55%);font:15px/1.45 system-ui,sans-serif;color:var(--text)}main{max-width:720px;margin:auto;padding:22px}.card{background:rgba(15,25,34,.97);border:1px solid var(--line);border-radius:18px;padding:22px;margin:0 0 18px}.eyebrow{font:700 12px ui-monospace,monospace;color:var(--cyan);letter-spacing:.14em}.muted,.hint{color:var(--muted)}label{display:block;margin:12px 0 5px;color:var(--muted);font-weight:650}input{width:100%;padding:12px;border-radius:10px;border:1px solid #31546d;background:#09131b;color:var(--text);font-size:16px}input[type=checkbox]{width:auto}.check{display:flex;gap:9px;align-items:center;color:var(--text)}button,.button{display:inline-block;padding:13px 16px;border:0;border-radius:11px;background:linear-gradient(90deg,var(--cyan),#8c8cff);color:#061118;font-weight:800;font-size:15px;cursor:pointer;text-decoration:none}.secondary{background:#172a38;color:var(--text);border:1px solid var(--line)}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}.err{color:var(--bad);font-weight:700;white-space:pre-wrap}.summary{font-family:ui-monospace,monospace;background:#081119;border:1px solid var(--line);padding:14px;border-radius:12px;white-space:pre-wrap;margin-top:14px}.hidden{display:none}</style></head><body><main><div class="card"><div class="eyebrow">YWD-HOTSPOT OS · RESTORE</div><h1>Restore from encrypted backup</h1><p class="muted">Use a .ywdsettings file exported from your previous hotspot. RF remains off while the backup is verified and restored.</p><div id="err" class="err"></div><section id="unlock"><label>Six-digit OLED setup code</label><input id="code" inputmode="numeric" maxlength="6" autocomplete="one-time-code"><div class="actions"><button id="unlockBtn">UNLOCK RESTORE</button><a class="button secondary" href="/">SET UP AS NEW</a></div></section><section id="restore" class="hidden"><label>Backup file</label><input id="file" type="file" accept=".ywdsettings,application/octet-stream"><label>Backup passphrase</label><input id="pass" type="password" autocomplete="current-password" minlength="10"><div class="actions"><button id="verifyBtn">DECRYPT &amp; VERIFY</button></div><pre id="summary" class="summary hidden"></pre><div id="options" class="hidden"><label class="check"><input id="startRf" type="checkbox"> Start RF after successful restore and enable RF at boot</label><label class="check"><input id="restoreWifi" type="checkbox"> Recreate included Wi-Fi as a saved profile without switching this live connection</label><label class="check"><input id="confirmRestore" type="checkbox"> I have reviewed this backup and want to replace the factory settings shown above</label><div class="actions"><button id="restoreBtn">RESTORE HOTSPOT</button><a class="button secondary" href="/">CANCEL / SET UP AS NEW</a></div></div></section></div></main><script>const $=id=>document.getElementById(id);let b64=null,preview=null;function error(s=''){$('err').textContent=s}function bytesToB64(bytes){let out='';for(let i=0;i<bytes.length;i+=32768)out+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(out)}async function api(path,body){let r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),credentials:'same-origin'});let j=await r.json();if(!r.ok)throw new Error(j.error||('HTTP '+r.status));return j}function text(p){let s=p.source||{};return [`Created: ${p.created_at||'unknown'}`,`Source: ${s.version||'unknown'} · ${s.branch||'unknown'} @ ${String(s.commit||'unknown').slice(0,12)}`,`Station: ${p.callsign||'?'} · DMR ${p.dmr_id||'?'}`,`Radio: ${p.frequency_mhz??'?'} MHz · CC${p.color_code??'?'}`,`BrandMeister: ${p.brandmeister_master||'unknown'}`,`Credentials: hotspot ${p.hotspot_password_configured?'yes':'no'} · API ${p.bm_api_key_configured?'yes':'no'} · Web ${p.web_password_configured?'yes':'no'}`,`Plugins: ${p.plugins_installed||0} installed · ${p.plugins_enabled||0} enabled · ${p.plugin_configs||0} configs`,`Wi-Fi: ${p.wifi_included?('included · '+(p.wifi_ssid||'unknown')):'not included'}`].join('\n')}$('unlockBtn').onclick=async()=>{error();let code=$('code').value.replace(/\D/g,'');if(code.length!==6)return error('Enter the six-digit OLED code.');try{await api('/api/unlock',{code});$('unlock').className='hidden';$('restore').className='';}catch(e){error(e.message)}};$('verifyBtn').onclick=async()=>{error();let f=$('file').files?.[0],pass=$('pass').value;if(!f)return error('Choose a .ywdsettings backup.');if(f.size<=0||f.size>1572864)return error('Backup is empty or too large.');if(pass.length<10)return error('Enter the backup passphrase.');try{b64=bytesToB64(new Uint8Array(await f.arrayBuffer()));let d=await api('/api/restore-preview',{backup_b64:b64,passphrase:pass});preview=d.preview;$('summary').textContent=text(preview);$('summary').className='summary';$('options').className='';$('startRf').checked=false;$('restoreWifi').checked=!!preview.wifi_included;$('confirmRestore').checked=false;}catch(e){error(e.message)}};$('restoreBtn').onclick=async()=>{error();if(!b64||!preview)return error('Verify the backup first.');if(!$('confirmRestore').checked)return error('Check the restore confirmation box before continuing.');let button=$('restoreBtn');button.disabled=true;button.textContent='RESTORING…';try{let d=await api('/api/restore-apply',{backup_b64:b64,passphrase:$('pass').value,start_rf:!!$('startRf').checked,restore_wifi:!!$('restoreWifi').checked});$('restore').innerHTML='<h2>Restore complete</h2><pre id="doneSummary" class="summary"></pre><p><a id="doneLink" class="button">OPEN DASHBOARD</a></p>';$('doneSummary').textContent=text(preview)+'\n\nMissing plugin packages: '+(d.missing_plugins||[]).join(', ')+'\nWarnings: '+(d.warnings||[]).join(' | ');$('doneLink').href=d.dashboard||'http://ywd-hotspot.local:8080/';}catch(e){error(e.message);button.disabled=false;button.textContent='RESTORE HOTSPOT';}};</script></body></html>"""


class H(base.H):
    def _large_json(self, limit=2050000):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except Exception:
            raise ValueError("invalid Content-Length")
        if length < 0 or length > limit:
            raise ValueError("restore request is too large")
        raw = self.rfile.read(length)
        try:
            obj = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            raise ValueError("invalid JSON body")
        if not isinstance(obj, dict):
            raise ValueError("JSON body must be an object")
        return obj

    def do_GET(self):
        path = urlparse(self.path).path
        if not base.setup_complete() and path in ("/", "/index.html"):
            base.ensure_code()
            self.page(injected_wizard())
            return
        if not base.setup_complete() and path == "/restore":
            base.ensure_code()
            self.page(RESTORE_HTML)
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in {"/api/restore-preview", "/api/restore-apply"}:
            super().do_POST()
            return
        if not self.same_origin():
            self.send_json({"error": "origin rejected"}, 403); return
        if base.setup_complete():
            self.send_json({"error": "appliance already provisioned"}, 403); return
        if not base.authenticated(self.headers):
            self.send_json({"error": "setup authorization required"}, 401); return
        try:
            body = self._large_json()
            if path == "/api/restore-preview":
                out = admin("settings-preview", body)
            else:
                body["first_boot"] = True
                out = admin("settings-import", body)
            self.send_json(out)
            if path == "/api/restore-apply":
                try:
                    base.RUNTIME_STATE.unlink()
                except FileNotFoundError:
                    pass
                threading.Thread(target=self.server.shutdown, daemon=True).start()
        except ValueError as exc:
            self.send_json({"error": str(exc)[:800]}, 400)
        except Exception as exc:
            self.send_json({"error": str(exc)[:1200]}, 502)


def main():
    if base.setup_complete():
        return
    base.ensure_tls(); base.ensure_code()
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(base.CERT), str(base.KEY))
    server = base.Server((base.BIND, base.PORT), H)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print(f"YWD first-boot setup + restore HTTPS listening on {base.BIND}:{base.PORT}", flush=True)
    try:
        server.serve_forever()
    finally:
        try:
            base.RUNTIME_STATE.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
