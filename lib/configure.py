#!/usr/bin/env python3
"""Interactive fallback configuration wizard for source installs."""
import getpass
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

import config_model
import web_auth

CFG = Path("/etc/ywd-hotspot/config.json")
APP = Path(__file__).resolve().parents[1]
try:
    VERSION = (APP / "VERSION").read_text(encoding="utf-8").strip() or "unknown"
except Exception:
    VERSION = "unknown"


def load():
    try: return config_model.normalize(json.loads(CFG.read_text()))
    except Exception: return config_model.defaults()


def ask(label, default=None, required=False):
    if default not in (None, ""):
        suffix = f" [{default}]"
    elif required:
        suffix = " [required]"
    else:
        suffix = ""
    while True:
        v=input(f"{label}{suffix}: ").strip()
        if not v and default is not None: v=str(default)
        if required and not v: print("  A value is required."); continue
        return v


def ask_int(label, default, lo=None, hi=None):
    while True:
        try:
            n=int(ask(label,default,True))
            if lo is not None and n<lo: raise ValueError
            if hi is not None and n>hi: raise ValueError
            return n
        except ValueError: print("  Enter a valid integer.")


def ask_float(label, default):
    while True:
        try: return float(ask(label,default,True))
        except ValueError: print("  Enter a valid number.")


def ask_bool(label, default=True):
    d="Y/n" if default else "y/N"
    while True:
        v=input(f"{label} [{d}]: ").strip().lower()
        if not v: return default
        if v in ("y","yes"): return True
        if v in ("n","no"): return False


def ask_frequency(default_hz):
    default=f"{Decimal(default_hz)/Decimal(1000000):.6f}".rstrip("0").rstrip(".")
    while True:
        raw=ask("Hotspot simplex frequency in MHz",default,True)
        try:
            mhz=Decimal(raw)
            if mhz<=0: raise ValueError
            return int(mhz*Decimal(1000000))
        except Exception: print("  Example: 433.550 or 446.525")


def write(c):
    CFG.parent.mkdir(parents=True,exist_ok=True)
    tmp=CFG.with_suffix(".json.tmp"); tmp.write_text(json.dumps(c,indent=2)+"\n"); os.chmod(tmp,0o640)
    try:
        import grp; os.chown(tmp,0,grp.getgrnam("ywd-hotspot").gr_gid)
    except Exception: pass
    os.replace(tmp,CFG)


def main():
    if os.geteuid()!=0: raise SystemExit("Run with sudo/root.")
    c=load(); st=c["station"]; rf=c["radio"]; bm=c["brandmeister"]; web=c["web"]; disp=c["display"]; m=c["maintenance"]
    print("\n============================================================")
    print(f" YWD-Hotspot {VERSION} configuration")
    print("============================================================")
    print("Enter each value below. Press Enter to keep a displayed [default].")
    print("Prompts marked [required] do not have a usable default.\n")
    while True:
        callsign=ask("Callsign",st.get("callsign"),True).upper()
        if re.fullmatch(r"[A-Z0-9]{3,10}(?:-[A-Z0-9]{1,2})?",callsign): break
        print("  Callsign format looks unusual.")
    while True:
        base=ask("Base DMR Radio ID",st.get("base_dmr_id"),True)
        if base.isdigit() and 5<=len(base)<=8: break
        print("  Enter the assigned numeric DMR ID.")
    essid=ask("Hotspot ESSID suffix 01-99 (blank for none)",st.get("essid","01"))
    freq=ask_frequency(rf.get("frequency_hz",446525000)); cc=ask_int("DMR Color Code",rf.get("color_code",1),0,15)
    master=ask("BrandMeister master",bm.get("master"),True); port=ask_int("BrandMeister UDP port",bm.get("port",62031),1,65535)
    oldpw=bm.get("password","")
    if oldpw:
        pw=getpass.getpass("Hotspot Security password [Enter keeps existing]: ") or oldpw
    else:
        while True:
            pw=getpass.getpass("BrandMeister Hotspot Security password: ")
            if pw: break
    location=ask("Location text",st.get("location","Hotspot")); description=ask("Description",st.get("description","YWD Hotspot"))
    lat=ask_float("Latitude",st.get("latitude",0)); lon=ask_float("Longitude",st.get("longitude",0)); height=ask_int("Antenna height meters",st.get("height",0),0,9999); url=ask("Station URL",st.get("url",f"https://www.qrz.com/db/{callsign}"))
    print("\nModem calibration / advanced values")
    rxoff=ask_int("RX offset Hz",rf.get("rx_offset",0),-10000,10000); txoff=ask_int("TX offset Hz",rf.get("tx_offset",0),-10000,10000)
    rxlvl=ask_int("RX level %",rf.get("rx_level",50),0,100); txlvl=ask_int("TX/DMR level %",rf.get("tx_level",50),0,100); rflvl=ask_int("RF level %",rf.get("rf_level",100),0,100)
    jitter=ask_int("DMR network jitter ms",rf.get("jitter_ms",360),60,3000)
    webport=ask_int("Dashboard TCP port",web.get("port",8080),1024,65535)
    brightness=ask_int("OLED brightness 1-255",disp.get("brightness",127),1,255); idle=ask_int("OLED idle timeout seconds (0=always on)",disp.get("idle_timeout_s",0),0,86400)
    autostart=ask_bool("RF services enabled at boot",m.get("rf_autostart",True)); persistent=ask_bool("Persistent crash journal",m.get("persistent_journal",True))
    candidate={
      "schema":3,
      "station":{**st,"callsign":callsign,"base_dmr_id":base,"essid":essid,"location":location,"description":description,"latitude":lat,"longitude":lon,"height":height,"url":url},
      "radio":{**rf,"frequency_hz":freq,"color_code":cc,"rx_offset":rxoff,"tx_offset":txoff,"rx_level":rxlvl,"tx_level":txlvl,"rf_level":rflvl,"jitter_ms":jitter},
      "brandmeister":{**bm,"master":master,"port":port,"password":pw},
      "display":{**disp,"brightness":brightness,"idle_timeout_s":idle},
      "web":{**web,"port":webport},
      "maintenance":{**m,"rf_autostart":autostart,"persistent_journal":persistent},
    }
    try: candidate=config_model.normalize(candidate)
    except ValueError as e: raise SystemExit(f"Configuration rejected: {e}")
    write(candidate)
    print("\nSaved canonical configuration.")
    rc=os.system("/usr/bin/python3 /opt/ywd-hotspot/app/lib/generate-config.py")
    if rc!=0: raise SystemExit("Config generation failed.")
    if not web_auth.configured():
        print("\n============================================================")
        print(" DASHBOARD CONTROL PASSWORD")
        print("============================================================")
        print("This is separate from the BrandMeister Hotspot Security password.")
        print("It unlocks WRITE/control actions in the YWD-Hotspot WebUI.")
        web_auth.set_password()
    else:
        print("Dashboard control password: existing credential preserved.")
    print("Use: sudo ywd-hotspotctl restart   # only restarts services already running")

if __name__=="__main__": main()