#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

PAYLOAD = Path('/var/lib/ywd-hotspot/private/factory-provision.json')
STATUS = Path('/var/lib/ywd-hotspot/factory-provision-status.json')
ADMIN = '/usr/local/libexec/ywd-hotspot-setup-admin'


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


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit('factory provision helper must run as root')
    if not PAYLOAD.is_file():
        return 0

    try:
        raw = PAYLOAD.read_text()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError('factory provision payload must be an object')
        p = subprocess.run(
            [ADMIN, 'setup-finish'],
            input=json.dumps(payload),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
        result = {}
        try:
            result = json.loads((p.stdout or '').strip() or '{}')
        except Exception:
            result = {}
        if p.returncode != 0 or not result.get('ok'):
            raise RuntimeError(str(result.get('error') or p.stderr.strip() or p.stdout.strip() or 'setup-finish failed')[:800])
        atomic_status({
            'schema': 1,
            'state': 'complete',
            'completed_at': int(time.time()),
            'callsign': result.get('callsign'),
            'hotspot_id': result.get('hotspot_id'),
            'rf_started': bool(result.get('rf_started')),
        })
        PAYLOAD.unlink(missing_ok=True)
        return 0
    except Exception as exc:
        atomic_status({
            'schema': 1,
            'state': 'failed',
            'failed_at': int(time.time()),
            'error': str(exc)[:800],
            'fallback': 'secure-first-boot-wizard',
        })
        try:
            PAYLOAD.unlink()
        except FileNotFoundError:
            pass
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
