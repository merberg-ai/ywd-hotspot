#!/usr/bin/env python3
"""Privileged, narrow control helper for the Alpha6 web dashboard.

This is installed root-owned as /usr/local/libexec/ywd-hotspot-admin and is the
only command the unprivileged dashboard may sudo. Every action is validated
here; no arbitrary shell command or arbitrary path is accepted.
"""
from __future__ import annotations

import grp
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = Path(os.environ.get("YWD_APP", "/opt/ywd-hotspot/app"))
APP_LIB = APP / "lib"
for p in (HERE, APP_LIB):
    if str(p) not in sys.path: sys.path.insert(0, str(p))

import config_model
import health
import web_auth

CFG = Path(os.environ.get("YWD_CONFIG", "/etc/ywd-hotspot/config.json"))
ETC = CFG.parent
VAR = Path(os.environ.get("YWD_VAR", "/var/lib/ywd-hotspot"))
PRIVATE = VAR / "private"
HISTORY = PRIVATE / "config-history"
HISTORY_META = VAR / "config-history.json"
AUDIT = VAR / "audit.json"
APPLIED = PRIVATE / "applied-config.json"
APPLIED_STATE = VAR / "applied-state.json"
DIAG = VAR / "diagnostics"
CAL_BASELINE = PRIVATE / "calibration-baseline.json"
CAL_BASELINE_META = VAR / "calibration-baseline.json"
BMKEY = Path(os.environ.get("YWD_BM_API_KEY", "/etc/ywd-hotspot/bm-api.key"))
JOURNAL_CONF = Path("/etc/systemd/journald.conf.d/10-ywd-hotspot-persistent.conf")
VERSION = "0.1.0-alpha6"


def run(args, timeout=20, check=False, env=None):
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout, check=False, env=env)
    if check and p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or f"command failed: {args[0]}").strip()[:1000])
    return p


def gid():
    try: return grp.getgrnam("ywd-hotspot").gr_gid
    except Exception: return 0


def atomic_json(path: Path, obj, mode=0o640, group=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    os.chmod(tmp, mode)
    if group:
        try: os.chown(tmp, 0, gid())
        except Exception: pass
    os.replace(tmp, path)


def read_json(path, default):
    try: return json.loads(Path(path).read_text())
    except Exception: return default


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def audit(action, detail=None):
    rows = read_json(AUDIT, [])
    if not isinstance(rows, list): rows = []
    rows.insert(0, {"time": now_iso(), "action": action, "detail": detail or {}})
    atomic_json(AUDIT, rows[:150])


def current():
    raw = json.loads(CFG.read_text())
    return config_model.normalize(raw)


def history_meta():
    rows = read_json(HISTORY_META, [])
    return rows if isinstance(rows, list) else []


def backup_config(reason, changed=None):
    c = current()
    HISTORY.mkdir(parents=True, exist_ok=True)
    os.chmod(PRIVATE, 0o700); os.chmod(HISTORY, 0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"{stamp}-{re.sub(r'[^a-z0-9-]+','-',reason.lower()).strip('-') or 'snapshot'}"
    ident = base; n = 1
    while (HISTORY / f"{ident}.json").exists():
        n += 1; ident = f"{base}-{n}"
    atomic_json(HISTORY / f"{ident}.json", c, mode=0o600, group=False)
    rows = history_meta()
    rows.insert(0, {"id": ident, "time": now_iso(), "reason": reason, "changed": sorted(changed or [])})
    keep = int(c.get("maintenance", {}).get("config_history_keep", 10))
    for old in rows[keep:]:
        oid = old.get("id", "")
        if re.fullmatch(r"[A-Za-z0-9._-]+", oid):
            try: (HISTORY / f"{oid}.json").unlink()
            except FileNotFoundError: pass
    rows = rows[:keep]
    atomic_json(HISTORY_META, rows)
    return ident


def write_config(c):
    atomic_json(CFG, c, mode=0o640, group=True)


def load_applied():
    try: return config_model.normalize(json.loads(APPLIED.read_text()))
    except Exception: return None


def save_applied(c):
    PRIVATE.mkdir(parents=True, exist_ok=True); os.chmod(PRIVATE, 0o700)
    atomic_json(APPLIED, c, mode=0o600, group=False)
    atomic_json(APPLIED_STATE, {"time": now_iso(), "hash": config_model.hash_config(c, include_secrets=False)})


def admin_payload():
    raw = sys.stdin.buffer.read(131072)
    if not raw: return {}
    try: obj = json.loads(raw.decode("utf-8"))
    except Exception: raise ValueError("invalid JSON payload")
    if not isinstance(obj, dict): raise ValueError("payload must be an object")
    return obj


def merge_browser_config(payload):
    old = current()
    incoming = payload.get("config", payload)
    if not isinstance(incoming, dict): raise ValueError("config must be an object")
    # Only these browser-editable sections can be merged here. Secrets are separate actions.
    candidate = json.loads(json.dumps(old))
    for sec in ("station", "radio", "brandmeister", "display", "web", "maintenance"):
        if sec in incoming:
            if not isinstance(incoming[sec], dict): raise ValueError(f"{sec} must be an object")
            for k, v in incoming[sec].items():
                if sec == "brandmeister" and k in {"password", "password_configured"}:
                    continue
                candidate.setdefault(sec, {})[k] = v
    candidate = config_model.normalize(candidate, preserve_password=old["brandmeister"].get("password", ""))
    return old, candidate


def config_save(payload):
    old, new = merge_browser_config(payload)
    changed = config_model.diff_paths(old, new)
    if not changed:
        return {"ok": True, "changed": [], "hints": config_model.classify_changes([]), "message": "No changes"}
    snap = backup_config("pre-save", changed)
    write_config(new)
    audit("config-save", {"changed": changed, "snapshot": snap})
    return {"ok": True, "changed": changed, "hints": config_model.classify_changes(changed), "snapshot": snap}


def _install_generated(tmpdir):
    for name in ("MMDVM-Host.ini", "DMRGateway.ini"):
        src = Path(tmpdir) / name
        if not src.is_file() or src.stat().st_size < 100:
            raise RuntimeError(f"generated {name} is missing or invalid")
        dst = ETC / name
        tmp = dst.with_name(dst.name + ".alpha4-tmp")
        shutil.copyfile(src, tmp); os.chmod(tmp, 0o640)
        try: os.chown(tmp, 0, gid())
        except Exception: pass
        os.replace(tmp, dst)


def apply_journal(c):
    m = c["maintenance"]
    JOURNAL_CONF.parent.mkdir(parents=True, exist_ok=True)
    if m.get("persistent_journal", True):
        Path("/var/log/journal").mkdir(parents=True, exist_ok=True)
        text = f"[Journal]\nStorage=persistent\nSystemMaxUse={int(m['journal_max_mb'])}M\nRuntimeMaxUse=50M\n"
        tmp = JOURNAL_CONF.with_suffix(".tmp"); tmp.write_text(text); os.chmod(tmp, 0o644); os.replace(tmp, JOURNAL_CONF)
    else:
        JOURNAL_CONF.parent.mkdir(parents=True, exist_ok=True)
        tmp = JOURNAL_CONF.with_suffix(".tmp")
        tmp.write_text("[Journal]\nStorage=volatile\nRuntimeMaxUse=50M\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, JOURNAL_CONF)
    run(["systemctl", "restart", "systemd-journald.service"], timeout=15, check=False)


def active(unit):
    return run(["systemctl", "is-active", "--quiet", unit], 3).returncode == 0


def unit_exists(unit):
    return run(["systemctl", "cat", unit], 3).returncode == 0


def oled_unit():
    # YWD-Hotspot OS owns the physical SSD1306 with the headless unit. Generic
    # installs have no such unit and continue using the application OLED unit.
    return "ywd-headless-oled.service" if unit_exists("ywd-headless-oled.service") else "ywd-oled.service"


def apply_oled_policy(enabled):
    unit = oled_unit()
    if unit == "ywd-headless-oled.service":
        helper = APP / "lib" / "oled_owner.sh"
        if not helper.is_file():
            raise RuntimeError("authoritative OLED owner helper is missing")
        # The helper installs the unified renderer drop-in, disables the legacy
        # app unit, and mirrors canonical display.enabled into boot/runtime state.
        run(["bash", str(helper), "install", str(APP)], 20, check=True)
    elif enabled:
        run(["systemctl", "enable", unit], 10, check=True)
        if active(unit):
            run(["systemctl", "restart", unit], 10, check=True)
        else:
            run(["systemctl", "start", unit], 10, check=True)
    else:
        run(["systemctl", "disable", "--now", unit], 10, check=True)
    return unit


def schedule_dashboard_restart(delay=2):
    # systemd-run lets the HTTP request finish before its own process is restarted.
    unit = f"ywd-dashboard-restart-{int(time.time())}"
    run(["systemd-run", "--unit", unit, f"--on-active={int(delay)}s", "/bin/systemctl", "try-restart", "ywd-dashboard.service"], 5)


def apply_runtime(old, new, hints):
    result = {"restarted": [], "dashboard_restart_pending": False}
    if hints["journald"]:
        apply_journal(new); result["restarted"].append("systemd-journald")

    # Autostart changes only enable/disable boot behavior. They do not unexpectedly key RF now.
    if hints["autostart"]:
        if new["maintenance"].get("rf_autostart", True):
            run(["systemctl", "enable", "ywd-mmdvmhost.service", "ywd-dmrgateway.service"], 10)
        else:
            run(["systemctl", "disable", "ywd-dmrgateway.service", "ywd-mmdvmhost.service"], 10)

    if hints["rf"]:
        ma = active("ywd-mmdvmhost.service"); ga = active("ywd-dmrgateway.service")
        if ga: run(["systemctl", "stop", "ywd-dmrgateway.service"], 12)
        if ma:
            run(["systemctl", "restart", "ywd-mmdvmhost.service"], 15, check=True)
            result["restarted"].append("MMDVM-Host")
        if ga:
            time.sleep(1)
            run(["systemctl", "start", "ywd-dmrgateway.service"], 15, check=True)
            result["restarted"].append("DMRGateway")

    if hints["oled"]:
        enabled = bool(new["display"].get("enabled", True))
        unit = apply_oled_policy(enabled)
        result["restarted"].append("OLED" if enabled else "OLED stopped")
        result["oled_unit"] = unit

    if hints["dashboard"]:
        schedule_dashboard_restart(2)
        result["dashboard_restart_pending"] = True
    return result


def config_apply(payload):
    c = current(); old = load_applied() or c
    changed = config_model.diff_paths(old, c); hints = config_model.classify_changes(changed)
    with tempfile.TemporaryDirectory(prefix="ywd-config-") as td:
        env = dict(os.environ); env["YWD_CONFIG"] = str(CFG); env["YWD_CONFIG_DIR"] = td
        gen = run([sys.executable, str(APP / "lib" / "generate-config.py")], 20, check=True, env=env)
        _install_generated(td)
    runtime = apply_runtime(old, c, hints)
    save_applied(c)
    audit("config-apply", {"changed": changed, "restarted": runtime["restarted"]})
    return {"ok": True, "changed": changed, "hints": hints, **runtime,
            "new_port": c["web"]["port"], "new_bind": c["web"]["bind"]}


def config_revert(payload):
    ident = str(payload.get("id", ""))
    if not re.fullmatch(r"[A-Za-z0-9._-]+", ident): raise ValueError("invalid history id")
    src = HISTORY / f"{ident}.json"
    if not src.is_file(): raise ValueError("configuration snapshot not found")
    target = config_model.normalize(json.loads(src.read_text()))
    old = current(); changed = config_model.diff_paths(old, target)
    snap = backup_config("pre-revert", changed)
    write_config(target)
    audit("config-revert", {"from": ident, "changed": changed, "snapshot": snap})
    out = {"ok": True, "changed": changed, "restored": ident, "snapshot": snap}
    if payload.get("apply", False): out["apply"] = config_apply({})
    return out


def set_hotspot_password(payload):
    pw = str(payload.get("password", ""))
    if not pw: raise ValueError("password cannot be empty")
    old = current(); candidate = json.loads(json.dumps(old)); candidate["brandmeister"]["password"] = pw
    new = config_model.normalize(candidate)
    changed = ["brandmeister.password"]
    snap = backup_config("pre-hotspot-password", changed); write_config(new)
    audit("hotspot-security-password-change", {"snapshot": snap})
    out = {"ok": True, "saved": True}
    if payload.get("apply", True): out["apply"] = config_apply({})
    return out


def set_bm_key(payload):
    key = str(payload.get("key", "")).strip()
    if len(key) < 12 or len(key) > 4096 or "\n" in key or "\r" in key:
        raise ValueError("API key format is invalid")
    BMKEY.parent.mkdir(parents=True, exist_ok=True)
    tmp = BMKEY.with_suffix(".tmp"); tmp.write_text(key + "\n"); os.chmod(tmp, 0o640)
    try: os.chown(tmp, 0, gid())
    except Exception: pass
    os.replace(tmp, BMKEY); audit("bm-api-key-change")
    return {"ok": True}


def set_web_password(payload):
    pw = str(payload.get("password", ""))
    if len(pw) < 8: raise ValueError("web password must be at least 8 characters")
    web_auth.set_password_value(pw)
    audit("web-control-password-change")
    return {"ok": True}


def rf_action(action):
    if action == "rf-start":
        run(["systemctl", "start", "ywd-mmdvmhost.service"], 15, check=True); time.sleep(1)
        run(["systemctl", "start", "ywd-dmrgateway.service"], 15, check=True)
    elif action == "rf-stop":
        run(["systemctl", "stop", "ywd-dmrgateway.service", "ywd-mmdvmhost.service"], 15, check=False)
    elif action == "rf-restart":
        ga = active("ywd-dmrgateway.service")
        if ga: run(["systemctl", "stop", "ywd-dmrgateway.service"], 12)
        run(["systemctl", "restart", "ywd-mmdvmhost.service"], 15, check=True); time.sleep(1)
        if ga: run(["systemctl", "start", "ywd-dmrgateway.service"], 15, check=True)
    else: raise ValueError("unknown RF action")
    audit(action)
    return {"ok": True}


def service_action(payload):
    name = str(payload.get("service", ""))
    if name == "oled":
        if not current()["display"].get("enabled", True):
            raise ValueError("OLED is disabled in Settings")
        unit = apply_oled_policy(True)
    elif name == "activity":
        unit = "ywd-activity.service"
        run(["systemctl", "restart", unit], 12, check=True)
    else:
        raise ValueError("unsupported service")
    audit("service-restart", {"service": name, "unit": unit})
    return {"ok": True, "unit": unit}


def reboot():
    audit("reboot-request")
    unit = f"ywd-reboot-{int(time.time())}"
    run(["systemd-run", "--unit", unit, "--on-active=3s", "/bin/systemctl", "reboot"], 5, check=True)
    return {"ok": True, "scheduled_in_s": 3}



def calibration_baseline_save():
    """Save the current radio/modem settings as a dedicated calibration baseline."""
    c = current()
    applied = load_applied()
    if applied and config_model.diff_paths(applied, c):
        raise ValueError("Configuration has pending changes; apply or revert them before saving a calibration baseline")
    doc = {"time": now_iso(), "version": VERSION, "radio": c.get("radio", {})}
    PRIVATE.mkdir(parents=True, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    atomic_json(CAL_BASELINE, doc, mode=0o600, group=False)
    # Safe metadata is group-readable so the unprivileged dashboard can display it.
    atomic_json(CAL_BASELINE_META, doc, mode=0o640, group=True)
    audit("calibration-baseline-save", {"rx_offset": c["radio"].get("rx_offset"), "tx_offset": c["radio"].get("tx_offset")})
    return {"ok": True, "baseline": doc}


def calibration_baseline_restore():
    """Restore only radio/modem settings from the saved calibration baseline, then apply."""
    doc = read_json(CAL_BASELINE, {})
    radio = doc.get("radio") if isinstance(doc, dict) else None
    if not isinstance(radio, dict):
        raise ValueError("No calibration baseline has been saved")
    old = current()
    applied_now = load_applied()
    if applied_now:
        pending = config_model.diff_paths(applied_now, old)
        non_radio = [x for x in pending if not x.startswith("radio.")]
        if non_radio:
            raise ValueError("Non-radio configuration changes are pending; apply or revert them before restoring the calibration baseline")
    candidate = json.loads(json.dumps(old))
    candidate.setdefault("radio", {}).update(radio)
    new = config_model.normalize(candidate, preserve_password=old["brandmeister"].get("password", ""))
    changed = config_model.diff_paths(old, new)
    if changed:
        snap = backup_config("pre-calibration-baseline-restore", changed)
        write_config(new)
    else:
        snap = None
    applied = config_apply({})
    audit("calibration-baseline-restore", {"changed": changed, "snapshot": snap})
    return {"ok": True, "changed": changed, "snapshot": snap, "baseline": doc, "apply": applied}

def sanitize_ini(text):
    out=[]
    for ln in text.splitlines():
        if re.match(r"\s*Password\s*=", ln, re.I): out.append('Password="***REDACTED***"')
        else: out.append(ln)
    return "\n".join(out)+"\n"


def diagnostics():
    DIAG.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"ywd-hotspot-diagnostics-{stamp}.tar.gz"
    final = DIAG / name
    with tempfile.TemporaryDirectory(prefix="ywd-diag-") as td:
        root = Path(td) / "ywd-hotspot-diagnostics"; root.mkdir()
        c = current(); atomic_json(root/"config-redacted.json", config_model.public(c), mode=0o600, group=False)
        for ini in ("MMDVM-Host.ini", "DMRGateway.ini"):
            p=ETC/ini
            if p.exists(): (root/(ini+".redacted")).write_text(sanitize_ini(p.read_text(errors="replace")))
        (root/"health.json").write_text(json.dumps(health.collect(), indent=2)+"\n")
        cmds = {
            "system-status.txt": ["systemctl", "--no-pager", "--full", "status", "ywd-mmdvmhost.service", "ywd-dmrgateway.service", "ywd-dashboard.service", "ywd-headless-oled.service", "ywd-oled.service", "ywd-activity.service"],
            "mmdvm-journal.txt": ["journalctl", "-u", "ywd-mmdvmhost.service", "-n", "400", "--no-pager", "-o", "short-precise"],
            "gateway-journal.txt": ["journalctl", "-u", "ywd-dmrgateway.service", "-n", "300", "--no-pager", "-o", "short-precise"],
            "kernel-current.txt": ["journalctl", "-k", "-b", "0", "-n", "400", "--no-pager", "-o", "short-precise"],
            "kernel-previous.txt": ["journalctl", "-k", "-b", "-1", "-n", "400", "--no-pager", "-o", "short-precise"],
        }
        for fn, cmd in cmds.items():
            p=run(cmd, 10); (root/fn).write_text((p.stdout or "") + (("\nSTDERR:\n"+p.stderr) if p.stderr else ""))
        (root/"README.txt").write_text("YWD-Hotspot diagnostic bundle. BrandMeister Hotspot Security password and API key are intentionally excluded/redacted.\n")
        with tarfile.open(final, "w:gz") as tf: tf.add(root, arcname=root.name)
    os.chmod(final, 0o640)
    try: os.chown(final, 0, gid())
    except Exception: pass
    audit("diagnostics-created", {"file": name})
    return {"ok": True, "filename": name, "size": final.stat().st_size}


def init_applied():
    c = current(); save_applied(c); return {"ok": True}


def main():
    if os.geteuid() != 0: raise SystemExit("ywd-hotspot-admin must run as root")
    if len(sys.argv) != 2: raise SystemExit("usage: ywd-hotspot-admin ACTION")
    action = sys.argv[1]
    payload_actions = {
        "config-save", "config-apply", "config-revert",
        "set-hotspot-password", "set-bm-api-key", "set-web-password",
        "service-restart",
    }
    payload = admin_payload() if action in payload_actions else {}
    if action == "config-save": out = config_save(payload)
    elif action == "config-apply": out = config_apply(payload)
    elif action == "config-revert": out = config_revert(payload)
    elif action == "set-hotspot-password": out = set_hotspot_password(payload)
    elif action == "set-bm-api-key": out = set_bm_key(payload)
    elif action == "set-web-password": out = set_web_password(payload)
    elif action in {"rf-start", "rf-stop", "rf-restart"}: out = rf_action(action)
    elif action == "service-restart": out = service_action(payload)
    elif action == "reboot": out = reboot()
    elif action == "diagnostics": out = diagnostics()
    elif action == "calibration-baseline-save": out = calibration_baseline_save()
    elif action == "calibration-baseline-restore": out = calibration_baseline_restore()
    elif action == "init-applied": out = init_applied()
    else: raise ValueError("unsupported admin action")
    print(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)[:800]}))
        raise SystemExit(1)
