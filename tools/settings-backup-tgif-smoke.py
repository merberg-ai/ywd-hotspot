#!/usr/bin/env python3
"""Source-only encrypted backup regression for TGIF configuration.

No live YWD files or services are touched. A synthetic canonical config is
encrypted into .ywdsettings v1, authenticated/decrypted, normalized, and checked
for exact TGIF credential preservation plus a redacted human preview.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))

import config_model
import settings_backup

cfg = config_model.defaults()
cfg["station"].update({"callsign": "KJ6YWD", "base_dmr_id": "3196104", "essid": "02"})
cfg["brandmeister"].update({"enabled": True, "master": "3103.master.brandmeister.network", "password": "bm-smoke-secret"})
cfg["tgif"].update({"enabled": True, "master": "tgif.network", "port": 62031, "password": "tgif-smoke-secret"})
cfg = config_model.normalize(cfg)

payload = {
    "schema": 1,
    "created_at": "2026-08-30T00:00:00Z",
    "source": {"version": "0.2.0-rc3", "branch": "dev", "commit": "smoke", "hostname": "smoke"},
    "config": cfg,
    "secrets": {"bm_api_key": "", "web_auth": None},
    "calibration_baseline": None,
    "plugins": {
        "state": {"schema": 1, "enabled": False, "plugins": {}},
        "packages": {"schema": 1, "installed": {}},
        "configs": {},
        "trust_keys": {},
    },
    "wifi": None,
}

passphrase = "rc4-backup-smoke-passphrase"
blob = settings_backup.encrypt_payload(payload, passphrase)
assert b"tgif-smoke-secret" not in blob, "TGIF password leaked into encrypted envelope plaintext"
assert b"bm-smoke-secret" not in blob, "BrandMeister password leaked into encrypted envelope plaintext"

restored = settings_backup.decrypt_payload(blob, passphrase)
tgif = restored["config"]["tgif"]
brandmeister = restored["config"]["brandmeister"]

assert tgif["enabled"] is True
assert tgif["master"] == "tgif.network"
assert int(tgif["port"]) == 62031
assert tgif["password"] == "tgif-smoke-secret"
assert brandmeister["password"] == "bm-smoke-secret"

preview = settings_backup.preview(restored)
assert preview["tgif_enabled"] is True
assert preview["tgif_master"] == "tgif.network"
assert int(preview["tgif_port"]) == 62031
assert preview["tgif_password_configured"] is True
assert preview["hotspot_password_configured"] is True
preview_text = json.dumps(preview, sort_keys=True)
assert "tgif-smoke-secret" not in preview_text
assert "bm-smoke-secret" not in preview_text

try:
    settings_backup.decrypt_payload(blob, "wrong-passphrase-for-smoke")
except settings_backup.SettingsBackupError:
    pass
else:
    raise AssertionError("wrong backup passphrase must fail authentication")

print("[OK] encrypted .ywdsettings round trip preserves TGIF enabled/master/port/password")
print("[OK] BrandMeister credential survives the same canonical-config round trip")
print("[OK] redacted restore preview exposes TGIF intent without network passwords")
print("[OK] network credentials are not present as plaintext in the encrypted envelope")
print("[OK] wrong backup passphrase fails authentication before restore")
