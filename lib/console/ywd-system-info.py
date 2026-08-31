#!/usr/bin/env python3
from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
from pathlib import Path

CFG = Path('/etc/ywd-hotspot/config.json')
BUILD = Path('/etc/ywd-hotspot/build-info.json')
SETUP = Path('/var/lib/ywd-hotspot/setup-state.json')
TGIF_SCANNER = Path('/run/ywd-hotspot/tgif-scanner.json')
M4_GATE = Path('/etc/ywd-hotspot/m4-safety.txt')
OS_VERSION = Path('/etc/ywd-hotspot/os-version')
APP_VERSION = Path('/opt/ywd-hotspot/app/VERSION')
PINS = Path('/opt/ywd-hotspot/app/pins.env')
REPO = 'https://github.com/merberg-ai/ywd-hotspot'

UNITS = [
    ('Network Manager', 'ywd-network-manager.service'),
    ('Dashboard', 'ywd-dashboard.service'),
    ('Setup Wizard', 'ywd-setup.service'),
    ('Headless OLED', 'ywd-headless-oled.service'),
    ('App OLED', 'ywd-oled.service'),
    ('Activity', 'ywd-activity.service'),
    ('MMDVM-Host', 'ywd-mmdvmhost.service'),
    ('DMRGateway', 'ywd-dmrgateway.service'),
    ('TGIF Scanner', 'ywd-tgif-scanner.service'),
]


def run(args, timeout=2):
    try:
        p = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=timeout, check=False)
        return p.stdout.strip()
    except Exception:
        return ''


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
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


def services():
    names = [unit for _, unit in UNITS]
    try:
        p = subprocess.run(['systemctl', 'is-active', *names], text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=3, check=False)
        rows = p.stdout.splitlines()
    except Exception:
        rows = []
    return {
        unit: (rows[i].strip() if i < len(rows) and rows[i].strip() else 'unknown')
        for i, unit in enumerate(names)
    }


def ipv4():
    out = run(['ip', '-4', '-o', 'addr', 'show', 'dev', 'wlan0', 'scope', 'global'])
    for line in out.splitlines():
        parts = line.split()
        if 'inet' in parts:
            try:
                return parts[parts.index('inet') + 1].split('/', 1)[0]
            except Exception:
                pass
    return run(['hostname', '-I']).split(' ')[0] if run(['hostname', '-I']) else ''


def wifi():
    ssid = run(['iwgetid', '-r']) or '-'
    link = run(['iw', 'dev', 'wlan0', 'link'])
    m = re.search(r'signal:\s*(-?\d+)\s*dBm', link)
    return ssid, (f'{m.group(1)} dBm' if m else '')


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
    return f'{days}d {hours:02d}:{mins:02d}' if days else f'{hours:02d}:{mins:02d}'


def setup_status():
    # First-boot ownership is an OS-appliance concept. Generic GitHub installs
    # have no M4 gate and must not be mislabeled as unconfigured.
    if not M4_GATE.is_file():
        return 'N/A', False
    d = read_json(SETUP, {})
    complete = isinstance(d, dict) and d.get('state') == 'complete'
    return ('COMPLETE' if complete else 'FIRST-BOOT REQUIRED'), not complete


def os_label():
    value = read_text(OS_VERSION, '')
    if value:
        return value
    data = {}
    try:
        for line in Path('/etc/os-release').read_text().splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                data[k] = v.strip().strip('"')
    except Exception:
        pass
    return data.get('PRETTY_NAME', 'Linux')


def configured_state(enabled, gateway_active):
    if not enabled:
        return 'DISABLED'
    return 'ACTIVE' if gateway_active else 'ENABLED'


def endpoint(network):
    if not isinstance(network, dict) or not network.get('enabled'):
        return '-'
    host = str(network.get('master') or '-').strip()
    try:
        port = int(network.get('port', 62031))
    except Exception:
        port = 62031
    return f'{host}:{port}'


def scanner_label(svc):
    if svc.get('ywd-tgif-scanner.service') != 'active':
        return 'STOPPED'
    runtime = read_json(TGIF_SCANNER, {})
    state = str(runtime.get('state') or 'running').strip().upper()
    tg = runtime.get('current_tg')
    if tg:
        return f'{state}  TG {tg}'
    return state


def collect(public_only=False):
    cfg = {} if public_only else read_json(CFG, {})
    build = read_json(BUILD, {})
    svc = services()
    ssid, signal = wifi()
    station = cfg.get('station', {}) if isinstance(cfg, dict) else {}
    radio = cfg.get('radio', {}) if isinstance(cfg, dict) else {}
    bm = cfg.get('brandmeister', {}) if isinstance(cfg, dict) else {}
    tgif = cfg.get('tgif', {}) if isinstance(cfg, dict) else {}
    maintenance = cfg.get('maintenance', {}) if isinstance(cfg, dict) else {}
    setup_text, setup_required = setup_status()
    gateway_active = svc.get('ywd-dmrgateway.service') == 'active'
    rf_active = (svc.get('ywd-mmdvmhost.service') == 'active' or gateway_active)
    core_ok = svc.get('ywd-dashboard.service') == 'active'
    network_state = svc.get('ywd-network-manager.service')
    network_ok = network_state in ('active', 'inactive', 'unknown')
    if setup_required:
        mood = 'SETUP REQUIRED'
    elif rf_active:
        mood = 'RF ACTIVE'
    elif not core_ok or not network_ok:
        mood = 'ATTENTION'
    else:
        mood = 'READY'
    try:
        hz = int(radio.get('frequency_hz', 0))
        freq = f'{hz / 1_000_000:.4f} MHz' if hz else '-'
    except Exception:
        freq = '-'
    if public_only:
        callsign = 'protected'
        dmr_id = 'protected'
        freq = 'protected'
        bm_state = 'protected'
        bm_master = 'protected'
        tgif_state = 'protected'
        tgif_master = 'protected'
        tgif_scanner = 'protected'
    else:
        callsign = station.get('callsign') or 'NOCALL'
        dmr_id = station.get('base_dmr_id') or '-'
        bm_state = configured_state(bool(bm.get('enabled', True)), gateway_active)
        bm_master = endpoint(bm)
        tgif_enabled = bool(tgif.get('enabled', False))
        tgif_state = configured_state(tgif_enabled, gateway_active)
        tgif_master = endpoint(tgif)
        tgif_scanner = scanner_label(svc) if tgif_enabled else '-'
    return {
        'build': build if isinstance(build, dict) else {},
        'svc': svc,
        'mood': mood,
        'rf_active': rf_active,
        'ssid': ssid,
        'signal': signal,
        'ip': ipv4() or '-',
        'callsign': callsign,
        'dmr_id': dmr_id,
        'frequency': freq,
        'bm_state': bm_state,
        'bm_master': bm_master,
        'tgif_state': tgif_state,
        'tgif_master': tgif_master,
        'tgif_scanner': tgif_scanner,
        'rf_autostart': bool(maintenance.get('rf_autostart', False)),
        'setup_text': setup_text,
        'setup_required': setup_required,
        'os_version': os_label(),
        'app_version': read_text(APP_VERSION),
        'public_only': public_only,
    }


def banner():
    return [
        '$$   $$ $$   $$ $$$$$$       $$   $$  $$$$$  $$$$$$$  $$$$$$ $$$$$$   $$$$$  $$$$$$$',
        '\\$$ $$  $$   $$ $$   $$      $$   $$ $$   $$    $$   $$      $$   $$ $$   $$    $$',
        ' \\$$$   $$ $ $$ $$   $$      $$   $$ $$   $$    $$   $$      $$   $$ $$   $$    $$',
        '  $$    $$ $ $$ $$   $$ $$$$ $$$$$$$ $$   $$    $$    $$$$$  $$$$$$  $$   $$    $$',
        '  $$    $$$$$$$ $$   $$      $$   $$ $$   $$    $$        $$ $$      $$   $$    $$',
        '  $$    $$$ $$$ $$   $$      $$   $$ $$   $$    $$        $$ $$      $$   $$    $$',
        '  $$    $$   $$ $$$$$$       $$   $$  $$$$$     $$   $$$$$$  $$       $$$$$     $$',
        '',
        ' Raspberry Pi DMR Hotspot Appliance  //  BrandMeister + TGIF',
        ' ------------------------------------------------------------------------------------',
    ]


def kv(label, value):
    return f' {label:<14} {value}'


def print_services(s=None):
    s = s or collect()
    print(' SERVICES')
    print(' ------------------------------------------------------------------------------------')
    for label, unit in UNITS:
        st = s['svc'].get(unit, 'unknown')
        mark = '[+]' if st == 'active' else ('[-]' if st in ('inactive', 'failed') else '[?]')
        print(f' {mark} {label:<18} {st}')
    print()
    print(kv('RF safety', 'ACTIVE' if s['rf_active'] else 'OFF'))


def print_build(s=None):
    s = s or collect()
    b = s['build']
    pins = parse_env(PINS)
    commit = b.get('commit_short') or str(b.get('commit') or '-')[:10]
    print(' BUILD')
    print(' ------------------------------------------------------------------------------------')
    print(kv('OS', s['os_version']))
    print(kv('App', b.get('version') or s['app_version']))
    print(kv('Channel', b.get('update_channel') or '-'))
    print(kv('Branch', b.get('branch') or '-'))
    print(kv('Commit', commit))
    print(kv('Source', b.get('source') or '-'))
    print(kv('MMDVM', (pins.get('MMDVM_HOST_COMMIT') or '-')[:12]))
    print(kv('Gateway', (pins.get('DMR_GATEWAY_COMMIT') or '-')[:12]))
    print(kv('Repository', b.get('repository') or REPO))


def print_network(s=None):
    s = s or collect(public_only=True)
    print(' NETWORK')
    print(' ------------------------------------------------------------------------------------')
    print(kv('WiFi', s['ssid']))
    print(kv('Signal', s['signal'] or '-'))
    print(kv('IPv4', s['ip']))
    print(kv('mDNS', 'ywd-hotspot.local'))
    print(kv('WebUI', 'http://ywd-hotspot.local:8080/'))


def print_info(s, motd=False, all_sections=False):
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
    print(' ------------------------------------------------------------------------------------')
    print(kv('Setup', s['setup_text']))
    print(kv('Callsign', s['callsign']))
    print(kv('DMR ID', s['dmr_id']))
    print(kv('Frequency', s['frequency']))
    print(kv('RF', 'ACTIVE' if s['rf_active'] else 'OFF'))
    print(kv('BrandMeister', s['bm_state']))
    print(kv('BM Master', s['bm_master']))
    print(kv('TGIF', s['tgif_state']))
    print(kv('TGIF Master', s['tgif_master']))
    print(kv('TGIF Scanner', s['tgif_scanner']))
    print(kv('WebUI', 'http://ywd-hotspot.local:8080/'))
    if s['setup_required']:
        print(kv('Setup URL', 'http://ywd-hotspot.local:8443/'))
    if s['public_only']:
        print(kv('Protected', 'run sudo ywd-info for full station details'))
    if all_sections:
        print()
        print_services(s)
        print()
        print_build(s)
    if motd:
        print()
        print(' Commands: ywd-info | ywd-services | ywd-build | ywd-logs')
        print(' GitHub:   github.com/merberg-ai/ywd-hotspot')


def main():
    name = Path(sys.argv[0]).name
    args = set(sys.argv[1:])
    public_only = '--public-fallback' in args
    s = collect(public_only=public_only)
    if name == 'ywd-services' or '--services' in args:
        print_services(s)
    elif name == 'ywd-build' or '--build' in args:
        print_build(s)
    elif '--network' in args:
        print_network(s)
    else:
        print_info(s, motd='--motd' in args, all_sections='--all' in args)


if __name__ == '__main__':
    main()
