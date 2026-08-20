#!/usr/bin/env python3
"""Generate upstream MMDVM-Host and DMRGateway INI files from canonical config."""
import json
import os
import re
import sys
from pathlib import Path

import config_model

CFG = Path(os.environ.get("YWD_CONFIG", "/etc/ywd-hotspot/config.json"))
OUT = Path(os.environ.get("YWD_CONFIG_DIR", "/etc/ywd-hotspot"))
DMRIDS = Path(os.environ.get("YWD_DMRID_FILE", "/var/lib/ywd-hotspot/DMRIds.dat"))
RSSI_MAP = Path(os.environ.get("YWD_RSSI_MAPPING_FILE", str(OUT / "mmdvm-hs-rssi.dat")))

RSSI_MAPPING_TEXT = """# YWD-Hotspot MMDVM_HS RSSI mapping
# MMDVM_HS ADF7021 firmware with SEND_RSSI_DATA reports the positive
# magnitude of received dBm. Map that value directly to negative dBm.
0 0
255 -255
"""


def clean(v):
    return str(v).replace("\n", " ").replace("\r", " ")


def write_secure(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.chmod(tmp, 0o640)
    try:
        import grp
        os.chown(tmp, 0, grp.getgrnam("ywd-hotspot").gr_gid)
    except Exception:
        pass
    os.replace(tmp, path)


def render(c):
    s, r, b = c["station"], c["radio"], c["brandmeister"]
    hid = int(s["hotspot_id"])
    callsign = clean(s["callsign"])
    simplex_freq = int(r["frequency_hz"])
    duplex = str(r.get("mode", "simplex")) == "duplex"
    rx_freq = int(r.get("rx_frequency_hz", simplex_freq)) if duplex else simplex_freq
    tx_freq = int(r.get("tx_frequency_hz", simplex_freq)) if duplex else simplex_freq
    duplex_flag = 1 if duplex else 0
    slot1 = 1 if duplex else 0
    slot2 = 1
    cc = int(r["color_code"])
    master = clean(b["master"])
    name = "BM_" + re.sub(r"[^A-Za-z0-9_-]+", "_", master.split(".")[0])
    pw = clean(b.get("password", ""))
    if '"' in pw:
        raise ValueError("Password contains unsupported double quote")
    lat = float(s.get("latitude", 0.0)); lon = float(s.get("longitude", 0.0))
    location_data = 0 if abs(lat) < 1e-9 and abs(lon) < 1e-9 else 1

    mmdvm = f"""[General]
Callsign={callsign}
Id={hid}
Timeout={int(r.get('timeout_s',180))}
Duplex={duplex_flag}
RFModeHang=10
NetModeHang=3
Daemon=0

[Log]
MQTTLevel=0
DisplayLevel=1

[MQTT]
Host=127.0.0.1
Port=18883
Auth=0
Username=ywd
Password=ywd
Keepalive=60
Name=ywd-mmdvm

[CW Id]
Enable=0
Time=10

[DMR Id Lookup]
File={DMRIDS}
Time=24

[Modem]
Protocol=uart
UARTPort={clean(r.get('uart','/dev/serial0'))}
UARTSpeed={int(r.get('uart_speed',115200))}
RXFrequency={rx_freq}
TXFrequency={tx_freq}
TXInvert={int(r.get('tx_invert',1))}
RXInvert={int(r.get('rx_invert',0))}
PTTInvert=0
TXDelay=100
RXOffset={int(r.get('rx_offset',0))}
TXOffset={int(r.get('tx_offset',0))}
DMRDelay=0
RXLevel={int(r.get('rx_level',50))}
TXLevel={int(r.get('tx_level',50))}
RXDCOffset=0
TXDCOffset=0
RFLevel={int(r.get('rf_level',100))}
DMRTXLevel={int(r.get('tx_level',50))}
RSSIMappingFile={RSSI_MAP}
UseCOSAsLockout=0
Trace=0
Debug=0

[D-Star]
Enable=0

[DMR]
Enable=1
Beacons=0
BeaconInterval=60
BeaconDuration=3
ColorCode={cc}
SelfOnly=0
EmbeddedLCOnly=0
DumpTAData=1
CallHang={int(r.get('call_hang_s',3))}
TXHang={int(r.get('tx_hang_s',4))}
Protect=0

[System Fusion]
Enable=0

[P25]
Enable=0

[NXDN]
Enable=0

[POCSAG]
Enable=0

[FM]
Enable=0

[D-Star Network]
Enable=0

[DMR Network]
Enable=1
LocalAddress=127.0.0.1
LocalPort=62032
GatewayAddress=127.0.0.1
GatewayPort=62031
Jitter={int(r.get('jitter_ms',360))}
Slot1={slot1}
Slot2={slot2}
Debug=0

[System Fusion Network]
Enable=0

[P25 Network]
Enable=0

[NXDN Network]
Enable=0

[POCSAG Network]
Enable=0

[FM Network]
Enable=0

[Lock File]
Enable=0

[Remote Control]
Enable=0
"""

    pass_tg = "PassAllTG=1\nPassAllTG=2" if duplex else "PassAllTG=2"
    pass_pc = "PassAllPC=1\nPassAllPC=2" if duplex else "PassAllPC=2"
    dmrgw = f"""[General]
Id={hid}
Timeout=10
RptAddress=127.0.0.1
RptPort=62032
LocalAddress=127.0.0.1
LocalPort=62031
RuleTrace=0
Daemon=0
TrunkingEnabled=0
Debug=0

[Log]
DisplayLevel=1
MQTTLevel=0

[Voice]
Enabled=0

[Info]
Callsign={callsign}
TXFrequency={tx_freq}
RXFrequency={rx_freq}
Power=1
ColorCode={cc}
Duplex={duplex_flag}
Slot1={slot1}
Slot2={slot2}
Latitude={lat}
Longitude={lon}
Height={int(s.get('height',0))}
Location={clean(s.get('location','Hotspot'))}
Description={clean(s.get('description','YWD Hotspot'))}
URL={clean(s.get('url',''))}

[XLX Network]
Enabled=0

[DMR Network 1]
Enabled={1 if b.get('enabled', True) else 0}
Name={name}
Id={hid}
Address={master}
Port={int(b.get('port',62031))}
{pass_tg}
{pass_pc}
Password="{pw}"
Location={location_data}
Debug=0

[DMR Network 2]
Enabled=0

[DMR Network 3]
Enabled=0

[DMR Network 4]
Enabled=0

[DMR Network 5]
Enabled=0

[GPSD]
Enable=0
Address=127.0.0.1
Port=2947

[APRS]
Enable=0
Description=YWD Hotspot
Suffix=3

[MQTT]
Address=127.0.0.1
Port=1883
Keepalive=60
Auth=0
Name=dmr-gateway

[Dynamic TG Control]
Enable=0

[Remote Commands]
Enable=0
"""
    return mmdvm, dmrgw, location_data


def main():
    if os.geteuid() != 0 and str(OUT).startswith("/etc/"):
        raise SystemExit("generate-config.py must run as root")
    raw = json.loads(CFG.read_text())
    c = config_model.normalize(raw)
    mmdvm, dmrgw, location_data = render(c)
    OUT.mkdir(parents=True, exist_ok=True)
    RSSI_MAP.parent.mkdir(parents=True, exist_ok=True)
    write_secure(RSSI_MAP, RSSI_MAPPING_TEXT)
    write_secure(OUT / "MMDVM-Host.ini", mmdvm)
    write_secure(OUT / "DMRGateway.ini", dmrgw)
    print("Generated:")
    print(f"  {OUT / 'MMDVM-Host.ini'}")
    print(f"  {OUT / 'DMRGateway.ini'}")
    print(f"  {RSSI_MAP}")
    if location_data == 0:
        print("  BrandMeister location data disabled because coordinates are 0,0.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"[FAIL] configuration: {e}", file=sys.stderr)
        raise SystemExit(2)
