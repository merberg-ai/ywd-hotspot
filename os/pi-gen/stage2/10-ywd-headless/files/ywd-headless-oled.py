#!/usr/bin/env python3
"""SSD1306 boot/network/setup display for YWD-Hotspot OS."""
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

import smbus

FONT = {
    ' ':[0,0,0,0,0], '-':[8,8,8,8,8], '.':[0,96,96,0,0], '/':[32,16,8,4,2], ':':[0,54,54,0,0],
    '0':[62,81,73,69,62], '1':[0,66,127,64,0], '2':[66,97,81,73,70], '3':[33,65,69,75,49],
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

PROVISION = Path('/etc/ywd-headless/provision.env')
RUNTIME_VERSION = Path('/opt/ywd-hotspot/app/VERSION')
NETWORK_STATE = Path('/run/ywd-hotspot-os/network.json')
SETUP_RUNTIME = Path('/run/ywd-hotspot/setup.json')
SETUP_STATE = Path('/var/lib/ywd-hotspot/setup-state.json')
ACTIVE_OLED = None


def sh(args, timeout=2):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=timeout).strip()
    except Exception:
        return ''


def ip_addr():
    out = sh(['hostname', '-I'])
    for item in out.split():
        if ':' not in item and not item.startswith('127.'):
            return item
    return ''


def ssid():
    return sh(['iwgetid', '-r'])


def wifi_profile_exists():
    out = sh(['nmcli', '-t', '-f', 'TYPE', 'connection', 'show'])
    return any(line.strip() in ('802-11-wireless', 'wifi') for line in out.splitlines())


def dashboard_active():
    return sh(['systemctl', 'is-active', 'ywd-dashboard.service']) == 'active'


def json_file(path):
    try:
        obj = json.loads(Path(path).read_text())
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def network_state():
    return json_file(NETWORK_STATE)


def setup_runtime():
    return json_file(SETUP_RUNTIME)


def setup_complete():
    return json_file(SETUP_STATE).get('state') == 'complete'


def temp():
    try:
        value = int(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000
        return f'{value:.0f}C'
    except Exception:
        return '--C'


def compact_error(state):
    diag = state.get('ap_diagnostic') if isinstance(state.get('ap_diagnostic'), dict) else {}
    text = str(diag.get('error') or state.get('reason') or '')
    for prefix in ('Error: ', 'error: '):
        if text.startswith(prefix):
            text = text[len(prefix):]
    for old, new in (
        ('Connection activation failed', 'ACTIVATION FAILED'),
        ('Failed to activate connection', 'ACTIVATION FAILED'),
        ('dnsmasq', 'DNSMASQ'), ('supplicant', 'SUPPLICANT')):
        text = text.replace(old, new)
    return text[:21]


class OLED:
    def __init__(self, bus=1, addr=0x3C):
        self.bus = smbus.SMBus(bus)
        self.addr = addr
        self.last = [None] * 8
        self.cmds([
            0xAE, 0x20, 0x00, 0xB0, 0xC8, 0x00, 0x10, 0x40,
            0x81, 0x7F, 0xA1, 0xA6, 0xA8, 0x3F, 0xA4, 0xD3,
            0x00, 0xD5, 0x80, 0xD9, 0xF1, 0xDA, 0x12, 0xDB, 0x40,
            0x8D, 0x14, 0xAF,
        ])
        self.clear()

    def cmd(self, value):
        self.bus.write_byte_data(self.addr, 0x00, value)

    def cmds(self, values):
        for value in values:
            self.cmd(value)

    def _write(self, page, text):
        text = str(text).upper()[:21]
        data = []
        for ch in text:
            data += FONT.get(ch, FONT[' ']) + [0]
        data = (data + [0] * 128)[:128]
        self.cmd(0xB0 + page); self.cmd(0x00); self.cmd(0x10)
        for pos in range(0, 128, 16):
            self.bus.write_i2c_block_data(self.addr, 0x40, data[pos:pos + 16])

    def line(self, page, text):
        text = str(text).upper()[:21]
        if self.last[page] != text:
            self._write(page, text); self.last[page] = text

    def lines(self, rows):
        for page, text in enumerate(rows[:8]):
            self.line(page, text)

    def clear(self):
        for page in range(8):
            self._write(page, ''); self.last[page] = ''


def open_oled_forever():
    while True:
        try:
            return OLED()
        except Exception:
            time.sleep(2)


def shutdown_handler(signum, frame):
    oled = ACTIVE_OLED
    if oled is not None:
        try:
            oled.lines([
                'YWD HOTSPOT OS',
                'SHUTTING DOWN',
                'PLEASE WAIT',
                '',
                'RF SERVICES STOPPING',
                'SYSTEM HALTING',
                '',
                temp(),
            ])
            time.sleep(0.4)
        except Exception:
            pass
    raise SystemExit(0)


def legacy_lines(runtime):
    current_ip = ip_addr(); current_ssid = ssid()
    if current_ip: state = 'WIFI ONLINE'
    elif PROVISION.exists(): state = 'WIFI SETUP'
    elif wifi_profile_exists(): state = 'WIFI WAITING'
    else: state = 'WIFI NO CONFIG'
    return [
        'YWD HOTSPOT OS', 'M2 RUNTIME' if runtime else 'M1.1 HEADLESS',
        'WEB 8080 RF OFF' if runtime and dashboard_active() else ('WEB STARTING RF OFF' if runtime else ''),
        'BOOT OK', state, current_ssid or '', current_ip or 'NO IP', f'{temp()} YWD-HOTSPOT.LOCAL']


def first_boot_lines(state):
    setup = setup_runtime()
    code = str(setup.get('code') or '')
    net_ssid = str(state.get('ssid') or '')
    ip = str(state.get('ip') or '')
    return [
        'YWD HOTSPOT OS',
        'M4 FIRST BOOT',
        'SETUP REQUIRED',
        f'CODE {code}' if code else 'SETUP STARTING',
        net_ssid,
        ip or 'NO IP',
        'HTTPS PORT 8443',
        'RF OFF',
    ]


def m3_lines(runtime, state):
    mode = str(state.get('mode') or 'boot')
    net_ssid = str(state.get('ssid') or '')
    ip = str(state.get('ip') or '')
    web = 'WEB 8080 RF OFF' if runtime and dashboard_active() else ('WEB STARTING RF OFF' if runtime else '')

    if runtime and mode == 'online' and not setup_complete():
        return first_boot_lines(state)
    if mode in ('setup_ap', 'recovery_ap'):
        verified = bool(state.get('ap_verified'))
        return ['YWD HOTSPOT OS','M3 NETWORK',web,
                ('RECOVERY AP' if mode == 'recovery_ap' else 'SETUP AP') if verified else 'AP VERIFYING',
                str(state.get('ap_ssid') or 'YWD-HOTSPOT'),'OPEN WIFI CH 6','10.42.0.1','OPEN 10.42.0.1']
    if mode == 'ap_starting':
        return ['YWD HOTSPOT OS','M3 NETWORK',web,'AP STARTING',str(state.get('ap_ssid') or 'YWD-HOTSPOT'),'OPEN WIFI CH 6','PLEASE WAIT',temp()]
    if mode == 'ap_failed':
        return ['YWD HOTSPOT OS','M3 NETWORK',web,'AP START FAILED',str(state.get('ap_ssid') or 'YWD-HOTSPOT'),'RETRY IN 30S',compact_error(state),temp()]
    if mode == 'online':
        return ['YWD HOTSPOT OS','M3 NETWORK',web,'WIFI ONLINE',net_ssid,ip or 'NO IP','YWD-HOTSPOT.LOCAL',temp()]
    if mode == 'connecting':
        return ['YWD HOTSPOT OS','M3 NETWORK',web,'WIFI CONNECTING',net_ssid,'','PLEASE WAIT',temp()]
    return ['YWD HOTSPOT OS','M3 NETWORK',web,'WIFI WAITING',net_ssid,ip or 'NO IP',str(state.get('reason') or '')[:21],temp()]


def main():
    global ACTIVE_OLED
    ACTIVE_OLED = open_oled_forever()
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    while True:
        try:
            runtime = RUNTIME_VERSION.exists(); state = network_state()
            ACTIVE_OLED.lines(m3_lines(runtime, state) if state else legacy_lines(runtime))
        except OSError:
            pass
        except Exception:
            pass
        time.sleep(2)


if __name__ == '__main__':
    main()
