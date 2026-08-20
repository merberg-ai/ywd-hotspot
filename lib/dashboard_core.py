#!/usr/bin/env python3
"""YWD-Hotspot Alpha6 lightweight dashboard/control server."""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse

import brandmeister
import config_model
import health
import web_auth

VERSION = "0.1.0-alpha6"
CFG = Path(os.environ.get("YWD_CONFIG", "/etc/ywd-hotspot/config.json"))
ACTIVITY = Path(os.environ.get("YWD_ACTIVITY_STATE", "/run/ywd-hotspot/activity.json"))
VAR = Path(os.environ.get("YWD_VAR", "/var/lib/ywd-hotspot"))
WEB = Path(os.environ.get("YWD_WEB_ROOT", "/opt/ywd-hotspot/app/web"))
BRANDING = Path(os.environ.get("YWD_BRANDING_ROOT", "/opt/ywd-hotspot/app/assets/branding"))
BUILD_INFO = Path(os.environ.get("YWD_BUILD_INFO", "/etc/ywd-hotspot/build-info.json"))
HISTORY_META = VAR / "config-history.json"
AUDIT = VAR / "audit.json"
APPLIED_STATE = VAR / "applied-state.json"
CALIBRATION = VAR / "calibration.json"
CAL_BASELINE_META = VAR / "calibration-baseline.json"
GEOCODE_CACHE = VAR / "geocode-cache.json"
DIAG = VAR / "diagnostics"
ADMIN = os.environ.get("YWD_ADMIN", "/usr/local/libexec/ywd-hotspot-admin")
SESSION_SECONDS = 3600
SESSIONS = {}
SESSION_LOCK = threading.Lock()
LOGIN_FAILS = {}
GEOCODE_LOCK = threading.Lock()
GEOCODE_LAST = 0.0
CACHE_LOCK = threading.Lock()
CACHE = {"services_at": 0.0, "services": {}, "gw_at": 0.0, "gw": [], "bm_at": 0.0,
         "bm_profile": None, "bm_error": None, "health_at": 0.0, "health": None, "brief_at": 0.0, "brief": None}
UNITS = ["ywd-mmdvmhost.service", "ywd-dmrgateway.service", "ywd-dashboard.service", "ywd-activity.service"]
KNOWN_TG = {91:"Worldwide", 93:"North America", 3100:"USA Nationwide", 9990:"Parrot"}
OLED_UNIT = None


def run(args, timeout=3):
    try:
        p=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=timeout,check=False)
        return p.stdout.strip()
    except Exception: return ""


def unit_exists(unit):
    return bool(run(["systemctl", "cat", unit], 2))


def oled_unit():
    global OLED_UNIT
    if OLED_UNIT is None:
        OLED_UNIT = "ywd-headless-oled.service" if unit_exists("ywd-headless-oled.service") else "ywd-oled.service"
    return OLED_UNIT


def raw_cfg():
    try: return json.loads(CFG.read_text())
    except Exception: return {}


def canonical_cfg():
    try: return config_model.normalize(raw_cfg())
    except Exception: return raw_cfg()


def public_config():
    try: return config_model.public(config_model.normalize(raw_cfg()))
    except Exception: return {"schema": None}


def service_states(force=False):
    t=time.monotonic()
    with CACHE_LOCK:
        if not force and t-CACHE["services_at"]<5: return dict(CACHE["services"])
    units=UNITS+[oled_unit()]
    out=run(["systemctl","is-active",*units],2).splitlines(); states={}
    for i,u in enumerate(units): states[u]=out[i].strip() if i<len(out) and out[i].strip() else "unknown"
    with CACHE_LOCK: CACHE["services_at"]=t; CACHE["services"]=states
    return states


def journal(unit,n=100):
    txt=run(["journalctl","-u",unit,"-n",str(n),"--no-pager","-o","cat"],3)
    return txt.splitlines() if txt else []


def gateway_lines():
    t=time.monotonic()
    with CACHE_LOCK:
        if t-CACHE["gw_at"]<10: return list(CACHE["gw"])
    lines=journal("ywd-dmrgateway.service",80)
    with CACHE_LOCK: CACHE["gw_at"]=t; CACHE["gw"]=lines
    return lines


def bm_login_state(states):
    if states.get("ywd-dmrgateway.service")!="active": return "offline","DMRGateway is not active"
    state,detail="connecting",""
    for ln in gateway_lines():
        low=ln.lower()
        if "logged into the master successfully" in low or "login successful" in low: state,detail="connected",ln[-180:]
        elif "could not lookup the address of the master" in low: state,detail="dns-failed",ln[-180:]
        elif "failed login" in low or "wrong-password" in low or ("authorisation" in low and ("fail" in low or "nak" in low)) or ("authentication" in low and "fail" in low): state,detail="auth-failed",ln[-180:]
        elif "not replying" in low or "timeout" in low or "timed out" in low: state,detail="master-unreachable",ln[-180:]
        elif "closing dmr network" in low or "socket has failed" in low: state,detail="disconnected",ln[-180:]
    return state,detail


def bm_profile(force=False):
    t=time.monotonic()
    with CACHE_LOCK:
        if not force and t-CACHE["bm_at"]<15: return CACHE["bm_profile"],CACHE["bm_error"]
    try: p=brandmeister.profile(); err=None
    except Exception as e: p=None; err=str(e)
    with CACHE_LOCK: CACHE["bm_at"]=t; CACHE["bm_profile"]=p; CACHE["bm_error"]=err
    return p,err


def invalidate_bm():
    with CACHE_LOCK: CACHE["bm_at"]=0.0


def subscriptions(profile):
    stat,dyn=[],[]
    if not isinstance(profile,dict): return stat,dyn
    for key,target in (("staticSubscriptions",stat),("dynamicSubscriptions",dyn)):
        vals=profile.get(key,[])
        if not isinstance(vals,list): continue
        for v in vals:
            if not isinstance(v,dict): continue
            try: tg=int(v.get("talkgroup",v.get("group"))); slot=int(v.get("slot",0))
            except Exception: continue
            target.append({"talkgroup":tg,"slot":slot,"name":KNOWN_TG.get(tg)})
    return stat,dyn


def activity_state():
    try:
        d=json.loads(ACTIVITY.read_text()); return d if isinstance(d,dict) else {}
    except Exception: return {"current":{"active":False,"direction":"idle"},"lastheard":[],"modem":{},"counters":{}}


def file_json(path,default):
    try: return json.loads(Path(path).read_text())
    except Exception: return default


def write_var_json(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    os.chmod(tmp, 0o640)
    os.replace(tmp, path)


def geocode_search(query):
    """User-triggered approximate location lookup with a small local cache."""
    global GEOCODE_LAST
    q = " ".join(str(query or "").replace("\r", " ").replace("\n", " ").split())
    if not 2 <= len(q) <= 100:
        raise ValueError("Enter a city/state or ZIP/postal code (2-100 characters)")
    key = q.casefold()
    cache = file_json(GEOCODE_CACHE, {"entries": {}})
    entries = cache.get("entries", {}) if isinstance(cache, dict) else {}
    hit = entries.get(key) if isinstance(entries, dict) else None
    if isinstance(hit, dict) and time.time() - float(hit.get("time", 0)) < 30 * 86400:
        return {"ok": True, "query": q, "cached": True, "results": hit.get("results", []),
                "attribution": "© OpenStreetMap contributors"}

    # The public service asks clients to stay at or below one request/second.
    with GEOCODE_LOCK:
        wait = 1.1 - (time.monotonic() - GEOCODE_LAST)
        if wait > 0: time.sleep(wait)
        params = urlencode({"q": q, "format": "jsonv2", "addressdetails": 1, "limit": 5})
        c = canonical_cfg(); station_url = str(c.get("station", {}).get("url", ""))
        ua = f"YWD-Hotspot/{VERSION}" + (f" ({station_url})" if station_url.startswith(("http://", "https://")) else "")
        req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + params,
                                     headers={"User-Agent": ua, "Accept": "application/json", "Accept-Language": "en"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                raw = r.read(262144)
        except (urllib.error.URLError, TimeoutError) as e:
            raise RuntimeError(f"Location lookup failed: {e}")
        finally:
            GEOCODE_LAST = time.monotonic()
    try: data = json.loads(raw.decode("utf-8", "replace"))
    except Exception: raise RuntimeError("Location service returned invalid data")
    results = []
    if isinstance(data, list):
        for item in data[:5]:
            if not isinstance(item, dict): continue
            try:
                lat = float(item.get("lat")); lon = float(item.get("lon"))
            except Exception: continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180): continue
            addr = item.get("address") if isinstance(item.get("address"), dict) else {}
            short = next((str(addr.get(k)).strip() for k in ("city", "town", "village", "hamlet", "municipality", "postcode", "county") if addr.get(k)), None)
            display = str(item.get("display_name") or short or q)[:300]
            results.append({"display_name": display, "short_name": (short or display.split(",",1)[0])[:40],
                            "latitude": round(lat, 7), "longitude": round(lon, 7),
                            "type": str(item.get("type") or item.get("category") or "place")[:40]})
    if not isinstance(entries, dict): entries = {}
    entries[key] = {"time": time.time(), "results": results}
    # Keep a tiny cache; most appliances will only ever have a handful of searches.
    newest = sorted(entries.items(), key=lambda kv: float((kv[1] or {}).get("time", 0)), reverse=True)[:40]
    try: write_var_json(GEOCODE_CACHE, {"entries": dict(newest)})
    except Exception: pass
    return {"ok": True, "query": q, "cached": False, "results": results,
            "attribution": "© OpenStreetMap contributors"}


def pending_state(c):
    cur=config_model.hash_config(c,include_secrets=False)
    ap=file_json(APPLIED_STATE,{})
    return {"pending": ap.get("hash")!=cur, "applied_at":ap.get("time"), "current_hash":cur[:12]}


def get_health(force=False):
    t=time.monotonic()
    with CACHE_LOCK:
        if not force and CACHE["health"] is not None and t-CACHE["health_at"]<15: return CACHE["health"]
    h=health.collect()
    with CACHE_LOCK: CACHE["health_at"]=t; CACHE["health"]=h
    return h


def brief_health(force=False):
    t=time.monotonic()
    with CACHE_LOCK:
        if not force and CACHE.get("brief") is not None and t-CACHE.get("brief_at",0)<10: return CACHE["brief"]
    try: uptime=float(Path("/proc/uptime").read_text().split()[0])
    except Exception: uptime=0
    try: load=[float(x) for x in Path("/proc/loadavg").read_text().split()[:3]]
    except Exception: load=[0,0,0]
    h={"hostname":os.uname().nodename,"uptime_s":uptime,"temperature_c":health.temp_c(),"load":load,
       "memory":health.memory(),"disk":health.disk("/"),"wifi":health.wifi(),"throttled":health.throttled()}
    with CACHE_LOCK: CACHE["brief_at"]=t; CACHE["brief"]=h
    return h

def clean_sessions():
    n=time.time()
    with SESSION_LOCK:
        for token in [k for k,v in SESSIONS.items() if v<n]: SESSIONS.pop(token,None)


def new_session():
    clean_sessions(); token=secrets.token_urlsafe(32)
    with SESSION_LOCK: SESSIONS[token]=time.time()+SESSION_SECONDS
    return token


def session_token(headers):
    raw=headers.get("Cookie","")
    try:
        c=SimpleCookie(); c.load(raw); return c["YWDSESS"].value if "YWDSESS" in c else None
    except Exception: return None


def authenticated(headers):
    token=session_token(headers)
    if not token: return False
    clean_sessions()
    with SESSION_LOCK:
        exp=SESSIONS.get(token)
        if exp and exp>time.time(): SESSIONS[token]=time.time()+SESSION_SECONDS; return True
    return False


def snapshot(headers=None):
    states=service_states(); ou=oled_unit(); bstate,detail=bm_login_state(states)
    prof,perr=(bm_profile() if states.get("ywd-dmrgateway.service")=="active" else (None,"DMRGateway is offline"))
    static,dynamic=subscriptions(prof); c=canonical_cfg(); h=brief_health()
    return {
        "version":VERSION,
        "build":file_json(BUILD_INFO,{"version":VERSION,"repository":"https://github.com/merberg-ai/ywd-hotspot","branch":"unknown","commit":"unknown","commit_short":"unknown","commit_date":"unknown","source":"unknown","source_state":"unknown"}),
        "services":{"mmdvmhost":states.get("ywd-mmdvmhost.service","unknown"),"dmrgateway":states.get("ywd-dmrgateway.service","unknown"),
                    "dashboard":states.get("ywd-dashboard.service","unknown"),"oled":states.get(ou,"unknown"),"oled_unit":ou,
                    "activity":states.get("ywd-activity.service","unknown")},
        "brandmeister":{"state":bstate,"detail":detail,"profile_error":perr,"static":static,"dynamic":dynamic,"api_key_configured":brandmeister.key_configured()},
        "controls":{"auth_configured":web_auth.configured(),"authenticated":authenticated(headers) if headers else False},
        "config":config_model.public(c), "pending":pending_state(c), "activity":activity_state(),
        "system":{"hostname":h.get("hostname"),"uptime_s":h.get("uptime_s"),"temp_c":h.get("temperature_c"),"load":h.get("load"),
                  "memory":h.get("memory"),"disk":h.get("disk"),"wifi":h.get("wifi"),"throttled":h.get("throttled")},
        "calibration":calibration_state(),
    }


def admin_call(action,payload=None,timeout=35):
    p=subprocess.run(["sudo","-n",ADMIN,action],input=json.dumps(payload or {}),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
    raw=(p.stdout or "").strip()
    try: out=json.loads(raw) if raw else {}
    except Exception: out={"ok":False,"error":raw or p.stderr.strip() or "admin helper returned invalid data"}
    if p.returncode!=0 or not out.get("ok",False): raise RuntimeError(str(out.get("error") or p.stderr.strip() or f"admin helper failed ({p.returncode})")[:800])
    with CACHE_LOCK: CACHE["services_at"]=0; CACHE["health_at"]=0; CACHE["brief_at"]=0
    return out


def calibration_state():
    doc = file_json(CALIBRATION, {"tests": []})
    if not isinstance(doc, dict): doc = {"tests": []}
    doc = dict(doc)
    doc["baseline"] = file_json(CAL_BASELINE_META, None)
    return doc


def calibration_reset():
    doc = {"tests": [], "best": None, "session_started_at": time.time()}
    write_var_json(CALIBRATION, doc)
    return doc


def calibration_record():
    c=canonical_cfg(); rows=file_json(CALIBRATION,{"tests":[]})
    tests=rows.get("tests",[]) if isinstance(rows,dict) else []
    lh=activity_state().get("lastheard",[])
    rf=next((x for x in lh if x.get("path")=="RF RX" or x.get("direction")=="rx"),None)
    if not rf: raise ValueError("No completed RF reception is available to record")
    ber=rf.get("ber_pct")
    if ber is None: raise ValueError("The last RF reception has no BER measurement")
    call_started=rf.get("started_at")
    rx_offset=int(c["radio"]["rx_offset"])
    if tests and call_started is not None and tests[0].get("call_started_at")==call_started and int(tests[0].get("rx_offset",0))==rx_offset:
        raise ValueError("That RF call is already recorded at this RX offset")
    rec={"time":time.time(),"call_started_at":call_started,"rx_offset":rx_offset,"ber_pct":float(ber),"rssi_dbm":rf.get("rssi_dbm"),
         "source":(rf.get("source") or {}).get("display"),"destination":(rf.get("destination") or {}).get("display"),"duration_s":rf.get("duration_s")}
    tests.insert(0,rec); tests=tests[:60]
    best=min(tests,key=lambda x:x.get("ber_pct",999)) if tests else None
    doc={"tests":tests,"best":best,"session_started_at":rows.get("session_started_at") if isinstance(rows,dict) else None}
    write_var_json(CALIBRATION, doc)
    return doc


class H(BaseHTTPRequestHandler):
    server_version="YWDHotspot/0.1"
    def log_message(self,fmt,*args): pass
    def security_headers(self):
        self.send_header("X-Content-Type-Options","nosniff"); self.send_header("X-Frame-Options","DENY"); self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Content-Security-Policy","default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
    def send_bytes(self,status,data,ctype="application/json",extra_headers=None,cache="no-store"):
        self.send_response(status); self.send_header("Content-Type",ctype); self.send_header("Cache-Control",cache); self.security_headers()
        if extra_headers:
            for k,v in extra_headers.items(): self.send_header(k,v)
        self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def send_json(self,obj,status=200,extra_headers=None): self.send_bytes(status,json.dumps(obj).encode(),"application/json",extra_headers)
    def body_json(self):
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n<0 or n>131072: raise ValueError
            return json.loads(self.rfile.read(n).decode()) if n else {}
        except Exception: raise ValueError("invalid JSON body")
    def same_origin(self):
        origin=self.headers.get("Origin")
        if not origin: return True
        host=self.headers.get("Host","")
        return origin in (f"http://{host}",f"https://{host}")
    def require_control(self):
        if not self.same_origin(): self.send_json({"error":"origin rejected"},403); return False
        if not web_auth.configured(): self.send_json({"error":"Dashboard control password is not configured"},403); return False
        if not authenticated(self.headers): self.send_json({"error":"Control login required"},401); return False
        return True
    def require_bm(self):
        if not self.require_control(): return False
        if not brandmeister.key_configured(): self.send_json({"error":"BrandMeister API key is not configured"},409); return False
        return True
    def serve_static(self,name,ctype):
        p=WEB/name
        if not p.is_file(): self.send_json({"error":"not found"},404); return
        self.send_bytes(200,p.read_bytes(),ctype,cache="no-cache")
    def serve_asset(self,path,ctype):
        if not path.is_file(): self.send_json({"error":"not found"},404); return
        self.send_bytes(200,path.read_bytes(),ctype,cache="public, max-age=86400")
    def do_GET(self):
        p=urlparse(self.path).path
        if p=="/api/status": self.send_json(snapshot(self.headers)); return
        if p=="/api/health": self.send_json(get_health()); return
        if p=="/api/config":
            c=canonical_cfg(); self.send_json({"config":config_model.public(c),"pending":pending_state(c),"history":file_json(HISTORY_META,[])[:20],"audit":file_json(AUDIT,[])[:40]}); return
        if p=="/api/logs": self.send_json({"mmdvm":journal("ywd-mmdvmhost.service",120),"dmrgateway":journal("ywd-dmrgateway.service",120),"dashboard":journal("ywd-dashboard.service",80)}); return
        if p.startswith("/api/diagnostics/"):
            if not self.require_control(): return
            name=p.split("/")[-1]
            if not re.fullmatch(r"ywd-hotspot-diagnostics-[0-9-]+\.tar\.gz",name): self.send_json({"error":"invalid filename"},400); return
            f=DIAG/name
            if not f.is_file(): self.send_json({"error":"not found"},404); return
            self.send_bytes(200,f.read_bytes(),"application/gzip",{"Content-Disposition":f'attachment; filename="{name}"'}); return
        if p in ("/","/index.html"): self.serve_static("index.html","text/html; charset=utf-8"); return
        if p=="/app.js": self.serve_static("app.js","application/javascript; charset=utf-8"); return
        if p=="/style.css": self.serve_static("style.css","text/css; charset=utf-8"); return
        if p=="/ywd-hotspot-badge.webp": self.serve_asset(BRANDING/"ywd-hotspot-badge-256.webp","image/webp"); return
        self.send_json({"error":"not found"},404)
    def do_POST(self):
        p=urlparse(self.path).path
        if p=="/api/login":
            if not self.same_origin(): self.send_json({"error":"origin rejected"},403); return
            if not web_auth.configured(): self.send_json({"error":"Control password is not configured"},403); return
            ip=self.client_address[0]; t=time.time(); fails=[x for x in LOGIN_FAILS.get(ip,[]) if t-x<60]; LOGIN_FAILS[ip]=fails
            if len(fails)>=5: self.send_json({"error":"Too many failed logins; wait a minute"},429); return
            try: body=self.body_json()
            except ValueError as e: self.send_json({"error":str(e)},400); return
            if not web_auth.verify(str(body.get("password",""))): LOGIN_FAILS[ip].append(t); self.send_json({"error":"Invalid control password"},401); return
            LOGIN_FAILS[ip]=[]; token=new_session(); self.send_json({"ok":True},200,{"Set-Cookie":f"YWDSESS={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_SECONDS}"}); return
        if p=="/api/logout":
            token=session_token(self.headers)
            if token:
                with SESSION_LOCK: SESSIONS.pop(token,None)
            self.send_json({"ok":True},200,{"Set-Cookie":"YWDSESS=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"}); return
        if p.startswith("/api/bm/"):
            if not self.require_bm(): return
            try: body=self.body_json()
            except ValueError as e: self.send_json({"error":str(e)},400); return
            try:
                if p=="/api/bm/drop-qso": out=brandmeister.drop_qso(0)
                elif p=="/api/bm/drop-dynamic": out=brandmeister.drop_dynamic(0)
                elif p=="/api/bm/static/add":
                    tg=int(body.get("talkgroup",0));
                    if not 1<=tg<=16777215: raise ValueError("invalid talkgroup")
                    out=brandmeister.add_static(tg,0)
                elif p=="/api/bm/static/remove":
                    tg=int(body.get("talkgroup",0));
                    if not 1<=tg<=16777215: raise ValueError("invalid talkgroup")
                    out=brandmeister.remove_static(tg,0)
                else: self.send_json({"error":"not found"},404); return
                invalidate_bm(); self.send_json({"ok":True,"result":out})
            except Exception as e: self.send_json({"error":str(e)[:500]},502)
            return
        if not self.require_control(): return
        try: body=self.body_json()
        except ValueError as e: self.send_json({"error":str(e)},400); return
        try:
            if p=="/api/location/search": out=geocode_search(body.get("query", ""))
            elif p=="/api/config/save": out=admin_call("config-save",body)
            elif p=="/api/config/apply": out=admin_call("config-apply",body,50)
            elif p=="/api/config/revert": out=admin_call("config-revert",body,55)
            elif p=="/api/secrets/hotspot-password": out=admin_call("set-hotspot-password",body,55)
            elif p=="/api/secrets/bm-api-key": out=admin_call("set-bm-api-key",body)
            elif p=="/api/secrets/web-password": out=admin_call("set-web-password",body)
            elif p=="/api/runtime/rf-start": out=admin_call("rf-start",body,40)
            elif p=="/api/runtime/rf-stop": out=admin_call("rf-stop",body,30)
            elif p=="/api/runtime/rf-restart": out=admin_call("rf-restart",body,45)
            elif p=="/api/runtime/restart-service": out=admin_call("service-restart",body,30)
            elif p=="/api/runtime/reboot": out=admin_call("reboot",body)
            elif p=="/api/diagnostics/create": out=admin_call("diagnostics",body,60)
            elif p=="/api/calibration/record": out={"ok":True,"calibration":calibration_record()}
            elif p=="/api/calibration/reset": out={"ok":True,"calibration":calibration_reset()}
            elif p=="/api/calibration/baseline/save": out=admin_call("calibration-baseline-save",body)
            elif p=="/api/calibration/baseline/restore": out=admin_call("calibration-baseline-restore",body,55)
            elif p=="/api/calibration/adjust":
                which=str(body.get("which","rx")); delta=int(body.get("delta",0))
                if which not in {"rx","tx"} or delta not in {-500,-250,-100,100,250,500}: raise ValueError("invalid calibration adjustment")
                c=canonical_cfg(); key=f"{which}_offset"; val=max(-10000,min(10000,int(c["radio"].get(key,0))+delta))
                admin_call("config-save",{"config":{"radio":{key:val}}}); out=admin_call("config-apply",{},50); out["new_offset"]=val
            else: self.send_json({"error":"not found"},404); return
            self.send_json(out)
        except Exception as e: self.send_json({"error":str(e)[:800]},502)


def main():
    c=canonical_cfg(); w=c.get("web",{}); bind=w.get("bind","0.0.0.0"); port=int(w.get("port",8080))
    print(f"YWD dashboard {VERSION} listening on {bind}:{port}",flush=True)
    ThreadingHTTPServer((bind,port),H).serve_forever()

if __name__=="__main__": main()
