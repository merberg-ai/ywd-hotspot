#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

PAYLOAD = Path('/var/lib/ywd-hotspot/private/factory-provision.json')
RESTORE = Path('/var/lib/ywd-hotspot/private/factory-restore.json')
STATUS = Path('/var/lib/ywd-hotspot/factory-provision-status.json')
ADMIN = '/usr/local/libexec/ywd-hotspot-admin'


def atomic_status(doc: dict) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS.with_suffix('.tmp')
    tmp.write_text(json.dumps(doc, indent=2) + '\n')
    os.chmod(tmp, 0o640)
    try:
        import grp
        os.chown(tmp, 0, grp.getgrnam('ywd-hotspot').gr_gid)
    except Exception:
        pass
    os.replace(tmp, STATUS)


def run_admin(action: str, request: dict) -> dict:
    p = subprocess.run(
        [ADMIN, action],
        input=json.dumps(request),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
        check=False,
    )
    try:
        result = json.loads((p.stdout or '').strip() or '{}')
    except Exception:
        result = {}
    if p.returncode != 0 or not result.get('ok'):
        raise RuntimeError(str(result.get('error') or p.stderr.strip() or p.stdout.strip() or f'{action} failed')[:800])
    return result


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit('factory provision helper must run as root')
    if not PAYLOAD.is_file() and not RESTORE.is_file():
        return 0

    try:
        if PAYLOAD.is_file() and RESTORE.is_file():
            raise ValueError('factory image contains conflicting provision and restore payloads')

        if RESTORE.is_file():
            request = json.loads(RESTORE.read_text())
            if not isinstance(request, dict):
                raise ValueError('factory restore request must be an object')
            result = run_admin('settings-import', request)
            mode = 'dashboard-backup-restore'
            atomic_status({
                'schema': 1,
                'state': 'complete',
                'mode': mode,
                'completed_at': int(time.time()),
                'rf_active': bool(result.get('rf_active')),
                'missing_plugins': result.get('missing_plugins') or [],
                'warnings': result.get('warnings') or [],
            })
            RESTORE.unlink(missing_ok=True)
            PAYLOAD.unlink(missing_ok=True)
            return 0

        request = json.loads(PAYLOAD.read_text())
        if not isinstance(request, dict):
            raise ValueError('factory provision payload must be an object')
        result = run_admin('setup-finish', request)
        atomic_status({
            'schema': 1,
            'state': 'complete',
            'mode': 'builder-profile',
            'completed_at': int(time.time()),
            'callsign': result.get('callsign'),
            'hotspot_id': result.get('hotspot_id'),
            'rf_started': bool(result.get('rf_started')),
        })
        PAYLOAD.unlink(missing_ok=True)
        RESTORE.unlink(missing_ok=True)
        return 0
    except Exception as exc:
        atomic_status({
            'schema': 1,
            'state': 'failed',
            'failed_at': int(time.time()),
            'error': str(exc)[:800],
            'fallback': 'secure-first-boot-wizard',
        })
        PAYLOAD.unlink(missing_ok=True)
        RESTORE.unlink(missing_ok=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
