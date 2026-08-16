#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

CFG = Path('/etc/ywd-hotspot/config.json')
BUILD = Path('/etc/ywd-hotspot/build-info.json')
SETUP = Path('/var/lib/ywd-hotspot/setup-state.json')
OS_VERSION = Path('/etc/ywd-hotspot/os-version')
OS_RELEASE = Path('/etc/ywd-hotspot/os-release')
PI_GEN = Path('/etc/ywd-hotspot/pi-gen-commit')
APP_VERSION = Path('/opt/ywd-hotspot/app/VERSION')
PINS = Path('/opt/ywd-hotspot/app/pins.env')
REPO = 'https://github.com/merberg-ai/ywd-hotspot'

UNITS = [
    ('Network Manager', 'ywd-network-manager.service'),
    ('Dashboard', 'ywd-dashboard.service'),
    ('Setup Wizard', 'ywd-setup.service'),
    ('OLED', 'ywd-headless-oled.service'),
    ('Activity', 'ywd-activity.service'),
    ('MMDVM-Host', 'ywd-mmdvmhost.service'),
    ('DMRGateway', 'ywd-dmrgateway.service'),
]


def run(args, timeout=2):
    try:
        p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=timeout, check=False)
        return p.stdout.strip()
    except Exception:
        return ''


def read_json(path, default):
    try:
        obj = json.loads(Path(path).read_text(encoding='utf-8'))
        return obj
    except Exception:
        return default


def read_text(path, default='unknown'):
    try:
        return Path(path).read_text(encoding='utf-8').strip() or default
    except Exception:
        return default


def parse_env(path):
    out = {}
    try:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            m = re.match(r'^([A-Z0-9_]+)=["\']?([^"\']*)["\']?$', line.strip())
            if m:
                out[m.group(1)] = m.group(2)
    except Exception:
        pass
    return out


def parse_kv(path):
    out = {}
    try:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            out[k] = v.strip().strip('"')
    except Exception:
        pass
    return out


def services():
    names = [u for _, u in UNITS]
    try:
        p = subprocess.run(['systemctl', 'is-active', *names], text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=3, check=False)
        rows = p.stdout.splitlines()
    except Exception:
        rows = []
    return {unit: (rows[i].strip() if i < len(rows) and rows[i].strip() else 'unknown')
            for i, unit in enumerate(names)}


def ipv4():
    out = run(['ip', '-4', '-o', 'addr', 'show', 'dev', 'wlan0', 'scope', 'global'])
    for line in out.splitlines():
        parts = line.split()
        if 'inet' in parts:
            try:
                return parts[parts.index('inet') + 1].split('/', 1)[0]
            except Exception:
                pass
    return ''


def wifi():
    ssid = run(['iwgetid', '-r']) or '-'
    link = run(['iw', 'dev', 'wlan0', 'link'])
    signal = ''
    m = re.search(r'signal:\s*(-?\d+)\s*dBm', link)
    if m:
        signal = f"{m.group(1)} dBm"
    return ssid, signal


def temperature():
    try:
        c = int(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000.0
        return f'{c:.0f} C'
    except Exception:
        return '-'


def uptime():
    try:
        sec = int(float(Path('/proc/uptime').read_text().split()[0]))
    except Exception:
        return '-'
    days, sec = divmod(sec, 86400)
    hours, sec = divmod(sec, 3600)
    mins, _ = divmod(sec, 60)
    return (f'{days}d {hours:02d}:{mins:02d}' if days else f'{hours:02d}:{mins:02d}')


def setup_complete():
    d = read_json(SETUP, {})
    return isinstance(d, dict) and d.get('state') == 'complete'


def state():
    cfg = read_json(CFG, {})
    build = read_json(BUILD, {})
    svc = services()
    ssid, signal = wifi()
    ip = ipv4()
    station = cfg.get('station', {}) if isinstance(cfg, dict) else {}
    radio = cfg.get('radio', {}) if isinstance(cfg, dict) else {}
    bm = cfg.get('brandmeister', {}) if isinstance(cfg, dict) else {}
    maintenance = cfg.get('maintenance', {}) if isinstance(cfg, dict) else {}
    complete = setup_complete()
    rf_active = svc.get('ywd-mmdvmhost.service') == 'active' or svc.get('ywd-dmrgateway.service') == 'active'
    if not complete:
        mood = 'SETUP REQUIRED'
    elif rf_active:
        mood = 'RF ACTIVE'
    elif svc.get('ywd-dashboard.service') != 'active' or svc.get('ywd-network-manager.service') != 'active':
        mood = 'ATTENTION'
    else:
        mood = 'READY'
    try:
        freq = f"{int(radio.get('frequency_hz', 0)) / 1_000_000:.4f} MHz" if int(radio.get('frequency_hz', 0)) else '-'
    except Exception:
        freq = '-'
    bm_state = 'ACTIVE' if svc.get('ywd-dmrgateway.service') == 'active' else ('ENABLED' if bm.get('enabled') else 'DISABLED')
    return {
        'cfg': cfg,
        'build': build,
        'svc': svc,
        'complete': complete,
        'mood': mood,
        'rf_active': rf_active,
        'ssid': ssid,
        'signal': signal,
        'ip': ip or '-',
        'callsign': station.get('callsign') or 'NOCALL',
        'dmr_id': station.get('base_dmr_id') or '-',
        'frequency': freq,
        'bm_state': bm_state,
        'rf_autostart': bool(maintenance.get('rf_autostart', False)),
        'os_version': read_text(OS_VERSION),
        'app_version': read_text(APP_VERSION),
    }


def banner():
    return [
        '+----------------------------------------------------------------+',
        '|                        YWD-HOTSPOT OS                          |',
        '|             Raspberry Pi DMR Hotspot Appliance                |',
        '+----------------------------------------------------------------+',
    ]


def kv(label, value):
    return f' {label:<14} {value}'


def print_info(motd=False, all_sections=False):
    s = state()
    for line in banner():
        print(line)
    print()
    print(kv('State', s['mood']))
    print(kv('Hostname', platform.node()))
    print(kv('OS', s['os_version']))
    print(kv('App', s['app_version']))
    print(kv('Kernel', f'{platform.release()} / {platform.machine()}'))
    print(kv('Uptime', uptime()))
    print(kv('Temperature', temperature()))
    print(kv('WiFi', f"{s['ssid']}{'  (' + s['signal'] + ')' if s['signal'] else ''}"))
    print(kv('IP', s['ip']))
    print()
    print(' HOTSPOT')
    print(' ----------------------------------------------------------------')
    print(kv('Setup', 'COMPLETE' if s['complete'] else 'FIRST-BOOT REQUIRED'))
    print(kv('Callsign', s['callsign']))
    print(kv('DMR ID', s['dmr_id']))
    print(kv('Frequency', s['frequency']))
    print(kv('RF', 'ACTIVE' if s['rf_active'] else 'OFF'))
    print(kv('BrandMeister', s['bm_state']))
    print(kv('WebUI', 'http://ywd-hotspot.local:8080/'))
    if not s['complete']:
        print(kv('Setup URL', 'https://ywd-hotspot.local:8443/'))
    if all_sections:
        print()
        print_services(s)
        print()
        print_build(s)
    if motd:
        print()
        print(' Commands: ywd-info | ywd-services | ywd-build | ywd-logs')
        print(' GitHub:   github.com/merberg-ai/ywd-hotspot')


def print_services(s=None):
    s = s or state()
    print(' SERVICES')
    print(' ----------------------------------------------------------------')
    for label, unit in UNITS:
        st = s['svc'].get(unit, 'unknown')
        mark = '[+]' if st == 'active' else ('[-]' if st in ('inactive', 'failed') else '[?]')
        print(f' {mark} {label:<18} {st}')
    print()
    print(kv('RF safety', 'ACTIVE' if s['rf_active'] else 'OFF'))


def print_build(s=None):
    s = s or state()
    b = s['build'] if isinstance(s['build'], dict) else {}
    pins = parse_env(PINS)
    osr = parse_kv(OS_RELEASE)
    print(' BUILD')
    print(' ----------------------------------------------------------------')
    print(kv('OS', osr.get('PRETTY_NAME', s['os_version'])))
    print(kv('App', b.get('version') or s['app_version']))
    print(kv('Channel', b.get('update_channel') or '-'))
    print(kv('Branch', b.get('branch') or '-'))
    print(kv('Commit', b.get('commit_short') or '-'))
    print(kv('Built source', b.get('source') or '-'))
    print(kv('pi-gen', read_text(PI_GEN, '-')[:12]))
    print(kv('MMDVM', (pins.get('MMDVM_HOST_COMMIT') or '-')[:12]))
    print(kv('Gateway', (pins.get('DMR_GATEWAY_COMMIT') or '-')[:12]))
    print(kv('Repository', b.get('repository') or REPO))


def print_network():
    s = state()
    print(' NETWORK')
    print(' ----------------------------------------------------------------')
    print(kv('WiFi', s['ssid']))
    print(kv('Signal', s['signal'] or '-'))
    print(kv('IPv4', s['ip']))
    print(kv('mDNS', 'ywd-hotspot.local'))
    print(kv('WebUI', 'http://ywd-hotspot.local:8080/'))


def main():
    name = Path(sys.argv[0]).name
    args = set(sys.argv[1:])
    if name == 'ywd-services' or '--services' in args:
        print_services()
    elif name == 'ywd-build' or '--build' in args:
        print_build()
    elif '--network' in args:
        print_network()
    else:
        print_info(motd='--motd' in args, all_sections='--all' in args)


if __name__ == '__main__':
    main()
