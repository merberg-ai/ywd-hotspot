#!/usr/bin/env python3
"""Trusted plugin update/rollback safety helper for YWD-Hotspot.

This helper captures plugin activation/runtime state, quiesces all YWD plugin
services before application replacement, restores only plugins that still
validate in the target runtime, and can cleanly deactivate plugin state when
switching to a non-plugin branch.
"""
from __future__ import annotations

import argparse
import grp
import json
import os
import re
import subprocess
import sys
from pathlib import Path

STATE = Path(os.environ.get('YWD_PLUGIN_STATE', '/etc/ywd-hotspot/plugin-state.json'))
UNIT_TEMPLATE = Path(os.environ.get('YWD_PLUGIN_UNIT_TEMPLATE', '/etc/systemd/system/ywd-plugin@.service'))
LOCAL_ROOT = Path(os.environ.get('YWD_LOCAL_PLUGIN_ROOT', '/var/lib/ywd-hotspot/plugin-packages'))
TELEMETRY_UNITS = ('ywd-mmdvm-telemetry.service', 'ywd-mqtt.service')
TELEMETRY_UNIT_PATHS = tuple(Path('/etc/systemd/system') / unit for unit in TELEMETRY_UNITS)
ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,39}$')
UNIT_RE = re.compile(r'^ywd-plugin@([a-z0-9][a-z0-9-]{0,39})\.service$')


def run(args, timeout=20, check=False):
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout, check=False)
    if check and p.returncode != 0:
        raise RuntimeError((p.stdout or f'command failed: {args!r}').strip()[-800:])
    return p


def ywd_gid():
    try:
        return grp.getgrnam('ywd-hotspot').gr_gid
    except Exception:
        return 0


def atomic_json(path, data, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.chmod(tmp, mode)
    try:
        os.chown(tmp, 0, ywd_gid() if mode != 0o600 else 0)
    except Exception:
        pass
    os.replace(tmp, path)


def read_state_raw():
    try:
        data = json.loads(STATE.read_text(encoding='utf-8'))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    raw_plugins = data.get('plugins') if isinstance(data.get('plugins'), dict) else {}
    plugins = {}
    for ident, value in raw_plugins.items():
        ident = str(ident)
        if ID_RE.fullmatch(ident) and isinstance(value, dict):
            plugins[ident] = bool(value.get('enabled', False))
    return {'schema': 1, 'enabled': bool(data.get('enabled', False)), 'plugins': plugins}


def catalog_service_ids(lib_dir):
    ids = set()
    roots = [Path(lib_dir) / 'service_plugin_packages', LOCAL_ROOT]
    for root in roots:
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir() or child.is_symlink() or not ID_RE.fullmatch(child.name):
                continue
            manifest = child / 'plugin.json'
            if not manifest.is_file() or manifest.is_symlink() or manifest.stat().st_size > 65536:
                continue
            if root == LOCAL_ROOT:
                try:
                    raw = json.loads(manifest.read_text(encoding='utf-8'))
                except Exception:
                    continue
                if not isinstance(raw, dict) or raw.get('kind') != 'service' or raw.get('id') != child.name:
                    continue
            ids.add(child.name)
    return ids


def unit_ids_from_systemd():
    ids = set()
    for args in (
        ['systemctl', 'list-unit-files', '--type=service', '--no-legend', '--no-pager', 'ywd-plugin@*.service'],
        ['systemctl', 'list-units', '--type=service', '--all', '--no-legend', '--no-pager', 'ywd-plugin@*.service'],
    ):
        try:
            out = run(args, timeout=6).stdout or ''
        except Exception:
            out = ''
        for line in out.splitlines():
            token = line.strip().split(None, 1)[0] if line.strip() else ''
            match = UNIT_RE.fullmatch(token)
            if match:
                ids.add(match.group(1))
    return ids


def unit_state(ident):
    unit = f'ywd-plugin@{ident}.service'
    active = run(['systemctl', 'is-active', unit], timeout=4).stdout.strip()
    enabled = run(['systemctl', 'is-enabled', unit], timeout=4).stdout.strip()
    return {
        'unit': unit,
        'active': active == 'active',
        'enabled': enabled == 'enabled',
        'active_state': active or 'unknown',
        'enabled_state': enabled or 'disabled',
    }


def capture(snapshot_path, current_lib):
    state = read_state_raw()
    service_ids = catalog_service_ids(current_lib) | unit_ids_from_systemd()
    services = {ident: unit_state(ident) for ident in sorted(service_ids)}
    snapshot = {
        'schema': 1,
        'master_enabled': state['enabled'],
        'plugin_enabled': state['plugins'],
        'services': services,
    }
    atomic_json(snapshot_path, snapshot, 0o600)
    return snapshot


def load_snapshot(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema') != 1:
        raise RuntimeError('invalid plugin update snapshot')
    return data


def quiesce(snapshot_path, current_lib):
    snapshot = load_snapshot(snapshot_path)
    ids = set(snapshot.get('services', {})) | catalog_service_ids(current_lib) | unit_ids_from_systemd()
    errors = []
    for ident in sorted(i for i in ids if ID_RE.fullmatch(str(i))):
        unit = f'ywd-plugin@{ident}.service'
        state = unit_state(ident)
        if not state['active'] and not state['enabled']:
            continue
        p = run(['systemctl', 'disable', '--now', unit], timeout=25)
        if p.returncode != 0:
            errors.append((p.stdout or f'failed to stop {unit}').strip()[-400:])
    if errors:
        raise RuntimeError('could not quiesce plugin services: ' + '; '.join(errors)[:1000])
    return {'ok': True, 'quiesced': sorted(ids)}


def load_target_modules(lib_dir):
    lib = str(Path(lib_dir).resolve())
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import plugin_manager  # type: ignore
    import plugin_service_manager  # type: ignore
    try:
        import plugin_catalog_overlay  # type: ignore
        plugin_catalog_overlay.install()
    except ImportError:
        # Older/stable target runtimes do not have an uploaded-package overlay.
        pass
    return plugin_manager, plugin_service_manager


def write_plugin_state(master_enabled, plugin_flags):
    clean = {}
    for ident, enabled in plugin_flags.items():
        ident = str(ident)
        if ID_RE.fullmatch(ident):
            clean[ident] = {'enabled': bool(enabled) if master_enabled else False}
    atomic_json(STATE, {'schema': 1, 'enabled': bool(master_enabled), 'plugins': clean}, 0o640)


def restore(snapshot_path, target_lib):
    snapshot = load_snapshot(snapshot_path)
    plugin_manager, service_manager = load_target_modules(target_lib)

    valid_declarative = {
        e['manifest']['id'] for e in plugin_manager.discover()
        if e.get('valid') and e.get('manifest', {}).get('id')
    }
    valid_service = {
        e['manifest']['id'] for e in service_manager.discover()
        if e.get('valid') and e.get('manifest', {}).get('id')
    }
    valid_all = valid_declarative | valid_service

    master = bool(snapshot.get('master_enabled', False))
    prior_flags = snapshot.get('plugin_enabled') if isinstance(snapshot.get('plugin_enabled'), dict) else {}
    restored_flags = {}
    warnings = []
    for ident, enabled in prior_flags.items():
        if not ID_RE.fullmatch(str(ident)):
            continue
        desired = bool(enabled) and master
        if desired and ident not in valid_all:
            warnings.append(f'{ident}: no longer valid/installed; left disabled')
            desired = False
        restored_flags[ident] = desired

    # New packages introduced by the target update remain disabled until the user
    # explicitly enables them in the Plugin Manager.
    for ident in valid_all:
        restored_flags.setdefault(ident, False)
    write_plugin_state(master, restored_flags)

    # First make every known plugin unit inert. Then restore only validated
    # service plugins according to the captured boot/runtime state.
    ids = set(snapshot.get('services', {})) | unit_ids_from_systemd() | valid_service
    for ident in sorted(i for i in ids if ID_RE.fullmatch(str(i))):
        unit = f'ywd-plugin@{ident}.service'
        p = run(['systemctl', 'disable', '--now', unit], timeout=25)
        # A nonexistent inactive instance is harmless; any other lingering failure
        # is recorded and the plugin will not be reactivated below unless its own
        # requested restore operations succeed.
        if p.returncode != 0 and unit_state(ident)['active']:
            warnings.append(f'{ident}: could not force service inactive before restore')
            restored_flags[ident] = False

    if master:
        service_snapshot = snapshot.get('services') if isinstance(snapshot.get('services'), dict) else {}
        for ident in sorted(valid_service):
            if not restored_flags.get(ident, False):
                continue
            previous = service_snapshot.get(ident) if isinstance(service_snapshot.get(ident), dict) else {}
            unit = f'ywd-plugin@{ident}.service'

            if bool(previous.get('enabled', False)):
                p = run(['systemctl', 'enable', unit], timeout=20)
                if p.returncode != 0:
                    warnings.append(f'{ident}: could not restore boot enable state; plugin left disabled')
                    restored_flags[ident] = False
                    run(['systemctl', 'disable', '--now', unit], timeout=20)
                    continue

            if bool(previous.get('active', False)):
                p = run(['systemctl', 'start', unit], timeout=25)
                if p.returncode != 0:
                    warnings.append(f'{ident}: could not restore active runtime state; plugin left disabled')
                    restored_flags[ident] = False
                    run(['systemctl', 'disable', '--now', unit], timeout=20)

    write_plugin_state(master, restored_flags)
    return {'ok': True, 'warnings': warnings, 'master_enabled': master}


def stable_cleanup(snapshot_path, current_lib):
    # The service instances were already quiesced before the non-plugin target
    # updater ran. Repeat defensively and fail if anything somehow became active
    # again; never claim a plugin-free target while a plugin service is running.
    quiesce(snapshot_path, current_lib)
    state = read_state_raw()
    flags = {ident: False for ident in state.get('plugins', {})}
    snapshot = load_snapshot(snapshot_path)
    for ident in (snapshot.get('plugin_enabled') or {}):
        if ID_RE.fullmatch(str(ident)):
            flags[str(ident)] = False
    write_plugin_state(False, flags)

    # Alpha17's trusted telemetry transport is plugin infrastructure, not part of
    # the stable appliance. Stop and remove only YWD-owned units when handing off
    # to a plugin-free target. Mosquitto packages are intentionally retained so a
    # pre-existing/shared package installation is never removed behind the user.
    for unit in TELEMETRY_UNITS:
        run(['systemctl', 'disable', '--now', unit], timeout=25)
    for path in TELEMETRY_UNIT_PATHS:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    try:
        UNIT_TEMPLATE.unlink()
    except FileNotFoundError:
        pass
    run(['systemctl', 'daemon-reload'], timeout=20, check=True)
    run(['systemctl', 'reset-failed'], timeout=10)
    return {'ok': True, 'master_enabled': False}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('capture', 'quiesce'):
        p = sub.add_parser(name)
        p.add_argument('--snapshot', required=True)
        p.add_argument('--lib', required=True)
    p = sub.add_parser('restore')
    p.add_argument('--snapshot', required=True)
    p.add_argument('--lib', required=True)
    p = sub.add_parser('stable-cleanup')
    p.add_argument('--snapshot', required=True)
    p.add_argument('--lib', required=True)
    args = parser.parse_args()

    if os.geteuid() != 0:
        raise SystemExit('plugin update safety helper must run as root')
    if args.command == 'capture':
        out = capture(args.snapshot, args.lib)
    elif args.command == 'quiesce':
        out = quiesce(args.snapshot, args.lib)
    elif args.command == 'restore':
        out = restore(args.snapshot, args.lib)
    else:
        out = stable_cleanup(args.snapshot, args.lib)
    print(json.dumps(out, separators=(',', ':')))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)[:1200]}, separators=(',', ':')))
        raise SystemExit(1)
