#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "lib"
sys.path.insert(0, str(LIB))
import config_model

spec = importlib.util.spec_from_file_location("generate_config", LIB / "generate-config.py")
generate_config = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(generate_config)


def fixture():
    c = config_model.defaults()
    c["station"].update({"callsign": "KJ6YWD", "base_dmr_id": "3196104", "essid": "02"})
    c["brandmeister"]["password"] = "bm-secret"
    return config_model.normalize(c)


def section(text, name):
    marker = f"[{name}]\n"
    start = text.index(marker) + len(marker)
    end = text.find("\n[", start)
    return text[start:] if end < 0 else text[start:end]


# Schema 6 configs acquire an inert TGIF section with no behavioral change.
legacy = fixture()
legacy["schema"] = 6
legacy.pop("tgif", None)
migrated = config_model.normalize(legacy)
assert migrated["schema"] == 7
assert migrated["tgif"] == {
    "enabled": False,
    "master": "tgif.network",
    "port": 62031,
    "password": "",
}

# Secrets never escape the public configuration view or secret-insensitive hash.
secret = fixture()
secret["tgif"].update({"enabled": True, "password": "tgif-long-security-secret"})
secret = config_model.normalize(secret)
public = config_model.public(secret)
assert public["brandmeister"]["password"] is None
assert public["tgif"]["password"] is None
assert public["tgif"]["password_configured"] is True
changed_secret = config_model.normalize({**secret, "tgif": {**secret["tgif"], "password": "another-tgif-secret"}})
assert config_model.hash_config(secret, include_secrets=False) == config_model.hash_config(changed_secret, include_secrets=False)

# Enabling TGIF without an explicit credential fails closed.
bad = fixture()
bad["tgif"]["enabled"] = True
try:
    config_model.normalize(bad)
except ValueError as exc:
    assert "TGIF security password is required" in str(exc)
else:
    raise AssertionError("TGIF enabled without password was accepted")

# Existing BrandMeister-only generation remains unchanged in routing behavior.
base = fixture()
_, dmrgw_base, _ = generate_config.render(base)
bm = section(dmrgw_base, "DMR Network 1")
tgif = section(dmrgw_base, "DMR Network 2")
assert "Enabled=1" in bm
assert "PassAllTG=2" in bm
assert "PassAllPC=2" in bm
assert "Enabled=0" in tgif
assert "TGRewrite=2,5000001,2,1,999999" in tgif
assert "PassAllTG" not in tgif
assert "PassAllPC" not in tgif
assert "TrunkingEnabled=0" in dmrgw_base

# Simultaneous mode reserves the 5xxxxxx namespace away from BrandMeister and routes it only to TGIF.
dual = fixture()
dual["tgif"].update({"enabled": True, "password": "tgif-long-security-secret"})
dual = config_model.normalize(dual)
_, dmrgw_dual, _ = generate_config.render(dual)
bm = section(dmrgw_dual, "DMR Network 1")
tgif = section(dmrgw_dual, "DMR Network 2")
assert "Enabled=1" in bm
assert "PassAllTG" not in bm
assert "TGRewrite0=2,1,2,1,4999999" in bm
assert "TGRewrite1=2,6000000,2,6000000,10777216" in bm
assert "PassAllPC=2" in bm
assert "Enabled=1" in tgif
assert "Address=tgif.network" in tgif
assert "Port=62031" in tgif
assert "TGRewrite=2,5000001,2,1,999999" in tgif
assert 'Password="tgif-long-security-secret"' in tgif
assert "PassAllTG" not in tgif and "PassAllPC" not in tgif

# Duplex keeps the same namespace independently on both slots.
duplex = dual.copy()
duplex["radio"] = dict(dual["radio"])
duplex["radio"]["mode"] = "duplex"
duplex = config_model.normalize(duplex)
_, dmrgw_duplex, _ = generate_config.render(duplex)
tgif = section(dmrgw_duplex, "DMR Network 2")
bm = section(dmrgw_duplex, "DMR Network 1")
assert "PassAllTG" not in bm
assert "TGRewrite0=1,1,1,1,4999999" in bm
assert "TGRewrite1=1,6000000,1,6000000,10777216" in bm
assert "TGRewrite2=2,1,2,1,4999999" in bm
assert "TGRewrite3=2,6000000,2,6000000,10777216" in bm
assert "TGRewrite0=1,5000001,1,1,999999" in tgif
assert "TGRewrite1=2,5000001,2,1,999999" in tgif

# A TGIF configuration change is RF-affecting and must use the normal controlled apply path.
hints = config_model.classify_changes(["tgif.enabled"])
assert hints["rf"] is True

print("TGIF routing smoke: PASS")
