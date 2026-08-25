#!/usr/bin/env python3
"""Comprehensive, credential-aware diagnostic bundle collector for YWD-Hotspot.

The dashboard diagnostic action is intentionally privileged because useful
support data spans root-owned configuration/provenance files and systemd logs.
The collector favors metadata, public/sanitized configuration, fingerprints,
hashes, and bounded journals. It never intentionally exports passwords, API
keys, WebUI credentials, Wi-Fi connection profiles/PSKs, or SSH key material.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = Path(os.environ.get("YWD_APP", "/opt/ywd-hotspot/app"))
ETC = Path(os.environ.get("YWD_CONFIG_DIR", "/etc/ywd-hotspot"))
CFG = Path(os.environ.get("YWD_CONFIG", str(ETC / "config.json")))
VAR = Path(os.environ.get("YWD_VAR", "/var/lib/ywd-hotspot"))
DIAG = VAR / "diagnostics"
REPO = Path(os.environ.get("YWD_REPO", "/opt/ywd-hotspot/repo"))

for p in (HERE, APP / "lib"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import admin
import config_model
import health

SECRET_KEY_RE = re.compile(
    r"(?:password|passwd|passphrase|api[_ -]?key|secret|bearer|token|private[_ -]?key|credential)",
    re.I,
)
SAFE_SECRET_META_RE = re.compile(
    r"(?:configured|present|count|retained|fingerprint|sha256|policy|authentication|available)",
    re.I,
)
ASSIGN_SECRET_RE = re.compile(
    r"(?i)\b(password|passwd|passphrase|api[_ -]?key|secret|token|credential)\b(\s*[:=]\s*)([^\s,;]+)"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----.*?-----END (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----",
    re.S,
)
UNIT_RE = re.compile(r"^ywd-[A-Za-z0-9@_.:-]+\.(?:service|timer|socket|path)$")
MAX_COMMAND_TEXT = 2 * 1024 * 1024


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(args, timeout=8, cwd=None):
    try:
        return subprocess.run(
            [str(x) for x in args],
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            args,
            124,
            stdout=(exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
            stderr=f"timed out after {timeout}s",
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(args, 127, stdout="", stderr=str(exc))
    except Exception as exc:
        return subprocess.CompletedProcess(args, 125, stdout="", stderr=str(exc))


def read_json(path: Path, default=None):
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj
    except Exception:
        return default


def redact_json(value, key=""):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            name = str(k)
            if SECRET_KEY_RE.search(name) and not SAFE_SECRET_META_RE.search(name):
                out[name] = "***REDACTED***" if v not in (None, "", False) else v
            else:
                out[name] = redact_json(v, name)
        return out
    if isinstance(value, list):
        return [redact_json(x, key) for x in value]
    return value


def sanitize_text(text: str) -> str:
    text = str(text or "")
    text = PRIVATE_KEY_RE.sub("***SSH PRIVATE KEY REDACTED***", text)
    text = BEARER_RE.sub("Bearer ***REDACTED***", text)
    text = ASSIGN_SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}***REDACTED***", text)
    lines = []
    for raw in text.splitlines():
        line = raw
        # Generated INI files commonly use Password=...; preserve the key name
        # while removing the value even when quoting/spacing is unusual.
        if re.match(r"^\s*(?:Password|Passphrase|APIKey|ApiKey|Token|Secret)\s*=", line, re.I):
            key = line.split("=", 1)[0].rstrip()
            line = f"{key}=***REDACTED***"
        lines.append(line)
    return "\n".join(lines) + ("\n" if text.endswith("\n") or lines else "")


def write_text(root: Path, rel: str, text: str, sanitize=False) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    value = sanitize_text(text) if sanitize else str(text or "")
    if len(value.encode("utf-8", errors="replace")) > MAX_COMMAND_TEXT:
        raw = value.encode("utf-8", errors="replace")[-MAX_COMMAND_TEXT:]
        value = "[output truncated to final 2 MiB]\n" + raw.decode("utf-8", errors="replace")
    path.write_text(value, encoding="utf-8", errors="replace")


def write_json(root: Path, rel: str, obj, redact=True) -> None:
    value = redact_json(obj) if redact else obj
    write_text(root, rel, json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")


def command(root: Path, rel: str, args, timeout=8, cwd=None, sanitize=True) -> str:
    p = run(args, timeout=timeout, cwd=cwd)
    cmd = " ".join(str(x) for x in args)
    text = f"COMMAND: {cmd}\nRETURN CODE: {p.returncode}\n\nSTDOUT:\n{p.stdout or ''}"
    if p.stderr:
        text += f"\n\nSTDERR:\n{p.stderr}"
    text += "\n"
    write_text(root, rel, text, sanitize=sanitize)
    return (p.stdout or "").strip()


def file_meta(path: Path) -> dict:
    try:
        st = path.lstat()
        return {
            "path": str(path),
            "exists": True,
            "type": "symlink" if stat.S_ISLNK(st.st_mode) else "directory" if stat.S_ISDIR(st.st_mode) else "file" if stat.S_ISREG(st.st_mode) else "other",
            "mode": oct(stat.S_IMODE(st.st_mode)),
            "uid": st.st_uid,
            "gid": st.st_gid,
            "size": st.st_size,
            "mtime": st.st_mtime,
        }
    except Exception as exc:
        return {"path": str(path), "exists": False, "error": str(exc)[:300]}


def inventory_dir(path: Path, depth=1) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    base_parts = len(path.parts)
    try:
        for item in sorted(path.rglob("*"), key=lambda p: str(p)):
            if len(item.parts) - base_parts > depth:
                continue
            rows.append(file_meta(item))
            if len(rows) >= 800:
                rows.append({"truncated": True, "reason": "inventory row limit"})
                break
    except Exception as exc:
        rows.append({"error": str(exc)[:500]})
    return rows


def sha256(path: Path) -> str | None:
    if not path.is_file() or path.is_symlink():
        return None
    h = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def safe_remote_url(url: str) -> str:
    url = str(url or "").strip()
    # Strip possible https://user:token@host credentials while preserving host/path.
    return re.sub(r"^(https?://)[^/@\s]+@", r"\1***@", url)


def discover_units() -> list[str]:
    found = set()
    for args in (
        ["systemctl", "list-unit-files", "--no-legend", "--no-pager", "ywd-*"],
        ["systemctl", "list-units", "--all", "--no-legend", "--no-pager", "ywd-*"],
    ):
        p = run(args, timeout=6)
        for line in (p.stdout or "").splitlines():
            unit = line.split()[0] if line.split() else ""
            if UNIT_RE.fullmatch(unit):
                found.add(unit)
    # Image-only units and dependencies are worth recording even if they are
    # currently inactive or absent from repository templates.
    for unit in (
        "ywd-headless-oled.service",
        "ywd-update.service",
        "ywd-dmrid-update.service",
        "ywd-dmrid-update.timer",
        "ssh.service",
        "mosquitto.service",
    ):
        p = run(["systemctl", "show", unit, "-p", "LoadState", "--value"], timeout=3)
        if (p.stdout or "").strip() not in {"", "not-found"}:
            found.add(unit)
    return sorted(found)


def binary_inventory() -> list[dict]:
    candidates = [
        Path("/usr/local/bin/MMDVMHost"),
        Path("/usr/local/bin/DMRGateway"),
        Path("/usr/bin/mosquitto"),
        Path("/usr/sbin/sshd"),
    ]
    for name in ("MMDVMHost", "DMRGateway", "mosquitto", "sshd"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    out = []
    seen = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if str(resolved) in seen or not path.exists():
            continue
        seen.add(str(resolved))
        row = file_meta(path)
        row["resolved"] = str(resolved)
        row["sha256"] = sha256(resolved)
        p = run(["file", "-b", str(resolved)], timeout=4) if shutil.which("file") else None
        row["file"] = (p.stdout or "").strip() if p else None
        out.append(row)
    return out


def marker_state(root: Path) -> dict:
    json_paths = {
        "build-info.json": ETC / "build-info.json",
        "mmdvm-runtime.json": ETC / "mmdvm-runtime.json",
        "dmrgateway-build.json": ETC / "dmrgateway-build.json",
        "runtime-generation.json": ETC / "runtime-generation.json",
        "update-status.json": VAR / "update-status.json",
        "calibration.json": VAR / "calibration.json",
        "calibration-baseline.json": VAR / "calibration-baseline.json",
        "config-history.json": VAR / "config-history.json",
        "audit.json": VAR / "audit.json",
        "setup-state.json": VAR / "setup-state.json",
        "plugin-state.json": ETC / "plugin-state.json",
        "plugin-packages.json": ETC / "plugin-packages.json",
    }
    state = {}
    for name, path in json_paths.items():
        doc = read_json(path, None)
        if doc is None:
            state[name] = {"present": path.exists(), "readable": False}
            continue
        safe = redact_json(doc)
        write_json(root, f"state/{name}", safe, redact=False)
        state[name] = {"present": True, "readable": True}

    text_paths = {
        "update-channel.txt": ETC / "update-channel",
        "mmdvm-active-marker.txt": ETC / "mmdvm-active-marker",
        "m4-safety.txt": ETC / "m4-safety.txt",
        "VERSION.txt": APP / "VERSION",
        "pins.env.txt": APP / "pins.env",
        "MANIFEST.txt": APP / "MANIFEST.txt",
    }
    for name, path in text_paths.items():
        if path.is_file():
            try:
                write_text(root, f"state/{name}", path.read_text(encoding="utf-8", errors="replace"), sanitize=True)
                state[name] = {"present": True, "readable": True}
            except Exception as exc:
                state[name] = {"present": True, "readable": False, "error": str(exc)[:300]}
        else:
            state[name] = {"present": False, "readable": False}
    return state


def plugin_snapshot(system_summary: dict) -> dict:
    try:
        import plugin_manager
        import plugin_service_manager
        import plugin_ui_manager

        base = plugin_manager.snapshot(system_summary)
        declarative = list(base.get("plugins", []))
        services = plugin_service_manager.snapshot()
        ui = plugin_ui_manager.snapshot()
        plugins = declarative + list(services or []) + list(ui or [])
        return redact_json({
            "api": base.get("api", 1),
            "system": {
                **dict(base.get("system", {})),
                "available_all_kinds": len(plugins),
                "installed_all_kinds": sum(1 for p in plugins if p.get("installed")),
                "enabled_all_kinds": sum(1 for p in plugins if p.get("enabled")),
                "active_all_kinds": sum(1 for p in plugins if p.get("health") == "active"),
            },
            "plugins": plugins,
        })
    except Exception as exc:
        return {"error": str(exc)[:800]}


def dmrid_snapshot() -> dict:
    try:
        import dmrid_admin
        return redact_json(dmrid_admin.status(include_units=True))
    except Exception as exc:
        return {"error": str(exc)[:800]}


def ssh_snapshot() -> dict:
    try:
        import ssh_runtime_admin
        return redact_json(ssh_runtime_admin.status())
    except Exception as exc:
        return {"error": str(exc)[:800]}


def vocoder_snapshot() -> dict:
    try:
        import vocoder_client
        return redact_json(vocoder_client.status(timeout=1.5))
    except Exception as exc:
        return {"available": False, "error": str(exc)[:800]}


def ssh_fingerprints(root: Path) -> None:
    if not shutil.which("ssh-keygen"):
        write_text(root, "security/ssh-key-fingerprints.txt", "ssh-keygen unavailable\n")
        return
    lines = ["SSH key material is NOT included. Fingerprints/comments only.\n"]
    for pub in sorted(Path("/etc/ssh").glob("ssh_host_*_key.pub")):
        p = run(["ssh-keygen", "-lf", str(pub)], timeout=4)
        if p.returncode == 0 and p.stdout.strip():
            lines.append(f"server {pub.name}: {p.stdout.strip()}")
    auth = Path("/home/ywd/.ssh/authorized_keys")
    if auth.is_file() and not auth.is_symlink():
        p = run(["ssh-keygen", "-lf", str(auth)], timeout=4)
        if p.returncode == 0 and p.stdout.strip():
            for row in p.stdout.splitlines():
                lines.append(f"authorized ywd: {row}")
        else:
            lines.append("authorized ywd: fingerprint extraction unavailable")
    else:
        lines.append("authorized ywd: no authorized_keys file")
    write_text(root, "security/ssh-key-fingerprints.txt", "\n".join(lines) + "\n", sanitize=True)


def generated_config(root: Path, config_public: dict) -> None:
    write_json(root, "config/config-redacted.json", config_public, redact=True)
    for name in ("MMDVM-Host.ini", "DMRGateway.ini"):
        path = ETC / name
        if not path.is_file():
            continue
        try:
            write_text(root, f"config/{name}.redacted", path.read_text(encoding="utf-8", errors="replace"), sanitize=True)
        except Exception as exc:
            write_text(root, f"config/{name}.redacted", f"could not read: {exc}\n")


def git_provenance(root: Path) -> dict:
    out = {"managed_checkout": str(REPO), "present": (REPO / ".git").is_dir()}
    if not out["present"]:
        write_json(root, "update/git-provenance.json", out)
        return out
    commands = {
        "head": ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        "branch": ["git", "-C", str(REPO), "branch", "--show-current"],
        "upstream": ["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "@{upstream}"],
        "upstream_commit": ["git", "-C", str(REPO), "rev-parse", "@{upstream}^{commit}"],
        "status": ["git", "-C", str(REPO), "status", "--short", "--branch"],
        "commit": ["git", "-C", str(REPO), "log", "-1", "--format=%H%n%cI%n%s"],
        "origin": ["git", "-C", str(REPO), "remote", "get-url", "origin"],
    }
    for key, args in commands.items():
        p = run(args, timeout=5)
        value = (p.stdout or "").strip()
        if key == "origin":
            value = safe_remote_url(value)
        out[key] = value if p.returncode == 0 else None
        if p.returncode != 0:
            out[f"{key}_error"] = (p.stderr or "").strip()[:500]
    write_json(root, "update/git-provenance.json", out)
    return out


def support_summary(build: dict, cfg: dict, h: dict, units: list[str], plugins: dict,
                    dmrid: dict, ssh: dict, vocoder: dict, git: dict) -> str:
    radio = cfg.get("radio", {}) if isinstance(cfg, dict) else {}
    bm = cfg.get("brandmeister", {}) if isinstance(cfg, dict) else {}
    display = cfg.get("display", {}) if isinstance(cfg, dict) else {}
    maintenance = cfg.get("maintenance", {}) if isinstance(cfg, dict) else {}
    wifi = h.get("wifi", {}) if isinstance(h, dict) else {}
    throttle = h.get("throttled", {}) if isinstance(h, dict) else {}
    mode = str(radio.get("mode") or "simplex").lower()
    if mode == "duplex":
        rf = (
            f"duplex | RX {float(radio.get('rx_frequency_hz') or 0)/1e6:.6f} MHz | "
            f"TX {float(radio.get('tx_frequency_hz') or 0)/1e6:.6f} MHz"
        )
    else:
        rf = f"simplex | {float(radio.get('frequency_hz') or 0)/1e6:.6f} MHz"
    service_states = []
    for unit in units:
        if not unit.endswith(".service"):
            continue
        p = run(["systemctl", "is-active", unit], timeout=2)
        service_states.append(f"{unit}={(p.stdout or '').strip() or 'unknown'}")
    db = dmrid.get("database", {}) if isinstance(dmrid, dict) else {}
    ps = plugins.get("system", {}) if isinstance(plugins, dict) else {}
    lines = [
        f"YWD-Hotspot support summary · {now_iso()}",
        f"Version/build: {build.get('version', 'unknown')} | {build.get('branch', 'unknown')} @ {build.get('commit', 'unknown')} | channel {build.get('update_channel', build.get('branch', 'unknown'))}",
        f"Source: {build.get('source', 'unknown')} / {build.get('source_state', 'unknown')} | checkout {git.get('branch') or 'unknown'} @ {git.get('head') or 'unknown'}",
        f"Host: {h.get('hostname', socket.gethostname())} | uptime {int(float(h.get('uptime_s') or 0))}s | boot {h.get('boot_id', 'unknown')}",
        f"RF: {rf} | CC{radio.get('color_code', '?')} | RX/TX offset {radio.get('rx_offset', '?')}/{radio.get('tx_offset', '?')} Hz | levels {radio.get('rx_level', '?')}/{radio.get('tx_level', '?')}%",
        f"Modem: port {radio.get('port', 'unknown')} | TX/RX invert {radio.get('tx_invert', '?')}/{radio.get('rx_invert', '?')} | RF level {radio.get('rf_level', '?')}%",
        f"BrandMeister config: enabled={bm.get('enabled', False)} | master {bm.get('master', 'unknown')}:{bm.get('port', 'unknown')} | password configured={bm.get('password_configured', False)}",
        f"Display: enabled={display.get('enabled', False)} | address {display.get('address', 'unknown')} | brightness {display.get('brightness', 'unknown')}",
        f"System: {h.get('temperature_c', '—')} C | throttle {throttle.get('raw', throttle.get('value', 'unknown'))} | load {' / '.join(str(x) for x in h.get('load', []))}",
        f"Wi-Fi: {wifi.get('interface', 'wlan0')} | {wifi.get('ssid') or 'unknown'} | {wifi.get('ip') or 'no IPv4'} | {wifi.get('signal_dbm', '—')} dBm | gateway {wifi.get('gateway') or 'unknown'} | errors RX {wifi.get('rx_errors', '—')} TX {wifi.get('tx_errors', '—')}",
        f"DMR ID DB: {db.get('state', 'unknown')} | records {db.get('records', 'unknown')} | interval {db.get('interval_days', 'unknown')}d | due={db.get('due', 'unknown')}",
        f"Plugins: subsystem {ps.get('health', 'unknown')} | installed {ps.get('installed_all_kinds', ps.get('installed', 'unknown'))} | active {ps.get('active_all_kinds', ps.get('active_plugins', 'unknown'))}",
        f"SSH: active={ssh.get('active', 'unknown')} | boot={ssh.get('enabled_at_boot', 'unknown')} | policy={ssh.get('authentication', 'unknown')} | user={ssh.get('login_user', 'ywd')} | authorized keys={ssh.get('authorized_key_count', 'unknown')}",
        f"Vocoder: available={vocoder.get('available', False)} | protocol={vocoder.get('protocol', 'unknown')} | error={vocoder.get('error', 'none') if not vocoder.get('available') else 'none'}",
        f"Policy: RF autostart={maintenance.get('rf_autostart', 'unknown')} | persistent journal={maintenance.get('persistent_journal', 'unknown')} | journal max={maintenance.get('journal_max_mb', 'unknown')} MB",
        "Services: " + (" | ".join(service_states) if service_states else "none discovered"),
        "Secrets: BrandMeister password/API key, WebUI credentials, Wi-Fi PSKs, and SSH key material intentionally excluded.",
    ]
    return "\n".join(lines) + "\n"


def prune_old(keep=8) -> None:
    try:
        rows = sorted(DIAG.glob("ywd-hotspot-diagnostics-*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in rows[keep:]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception:
        pass


def diagnostics() -> dict:
    if os.geteuid() != 0:
        raise PermissionError("root required")

    DIAG.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"ywd-hotspot-diagnostics-{stamp}.tar.gz"
    final = DIAG / name

    with tempfile.TemporaryDirectory(prefix="ywd-diag-") as td:
        root = Path(td) / "ywd-hotspot-diagnostics"
        root.mkdir()

        try:
            raw_cfg = json.loads(CFG.read_text(encoding="utf-8"))
            canonical = config_model.normalize(raw_cfg)
            public_cfg = config_model.public(canonical)
        except Exception as exc:
            canonical = {}
            public_cfg = {"error": f"configuration could not be normalized: {exc}"}
        generated_config(root, public_cfg)

        try:
            health_doc = health.collect()
        except Exception as exc:
            health_doc = {"error": str(exc)[:800]}
        write_json(root, "system/health.json", health_doc)

        marker_index = marker_state(root)
        write_json(root, "state/index.json", marker_index)
        build = read_json(ETC / "build-info.json", {}) or {}

        units = discover_units()
        write_json(root, "system/discovered-units.json", units, redact=False)
        if units:
            command(root, "system/systemd-status.txt", ["systemctl", "--no-pager", "--full", "status", *units], timeout=12)
            command(
                root,
                "system/systemd-properties.txt",
                ["systemctl", "show", *units,
                 "--property=Id,LoadState,ActiveState,SubState,UnitFileState,NRestarts,Result,ExecMainStatus,ExecMainPID,FragmentPath,DropInPaths,ExecStart"],
                timeout=12,
            )
            command(root, "system/systemd-unit-files.txt", ["systemctl", "list-unit-files", "--no-pager", "ywd-*"], timeout=8)
            command(root, "system/systemd-units.txt", ["systemctl", "list-units", "--all", "--no-pager", "ywd-*"], timeout=8)
            command(root, "system/systemd-timers.txt", ["systemctl", "list-timers", "--all", "--no-pager", "ywd-*"], timeout=8)
        command(root, "system/systemd-failed.txt", ["systemctl", "--failed", "--no-pager", "--full"], timeout=6)

        # Bounded per-unit journals make plugin/new-service failures visible while
        # keeping bundle size and creation latency under control on a Pi Zero.
        for unit in units:
            if not unit.endswith(".service"):
                continue
            count = "500" if unit == "ywd-mmdvmhost.service" else "320" if unit == "ywd-dmrgateway.service" else "180"
            safe_name = re.sub(r"[^A-Za-z0-9_.@-]+", "_", unit)
            command(
                root,
                f"journals/{safe_name}.txt",
                ["journalctl", "-u", unit, "-n", count, "--no-pager", "-o", "short-precise"],
                timeout=6,
            )

        command(root, "journals/kernel-current.txt", ["journalctl", "-k", "-b", "0", "-n", "600", "--no-pager", "-o", "short-precise"], timeout=8)
        command(root, "journals/kernel-previous.txt", ["journalctl", "-k", "-b", "-1", "-n", "400", "--no-pager", "-o", "short-precise"], timeout=8)
        command(root, "journals/warnings-current-boot.txt", ["journalctl", "-b", "0", "-p", "warning..alert", "-n", "400", "--no-pager", "-o", "short-precise"], timeout=8)
        command(root, "journals/previous-boot-tail.txt", ["journalctl", "-b", "-1", "-n", "250", "--no-pager", "-o", "short-precise"], timeout=8)
        command(root, "journals/boot-list.txt", ["journalctl", "--list-boots", "--no-pager"], timeout=5)
        command(root, "journals/disk-usage.txt", ["journalctl", "--disk-usage"], timeout=5)

        # OS / Raspberry Pi / dependency inventory.
        if Path("/etc/os-release").is_file():
            write_text(root, "system/os-release.txt", Path("/etc/os-release").read_text(encoding="utf-8", errors="replace"), sanitize=True)
        model = Path("/proc/device-tree/model")
        if model.is_file():
            try:
                write_text(root, "system/device-model.txt", model.read_bytes().replace(b"\x00", b"").decode("utf-8", "replace") + "\n")
            except Exception:
                pass
        for rel, args, timeout in (
            ("system/uname.txt", ["uname", "-a"], 4),
            ("system/hostnamectl.txt", ["hostnamectl"], 5),
            ("system/timedatectl.txt", ["timedatectl", "status"], 5),
            ("system/architecture.txt", ["dpkg", "--print-architecture"], 4),
            ("system/lscpu.txt", ["lscpu"], 5),
            ("system/memory.txt", ["free", "-h"], 4),
            ("system/disk.txt", ["df", "-hT"], 5),
            ("system/mounts.txt", ["findmnt"], 5),
            ("hardware/usb.txt", ["lsusb"], 5),
            ("hardware/serial-devices.txt", ["ls", "-l", "/dev/serial0", "/dev/ttyAMA0", "/dev/ttyS0", "/dev/serial/by-id"], 4),
            ("hardware/i2c-devices.txt", ["ls", "-l", "/dev/i2c-0", "/dev/i2c-1"], 4),
            ("hardware/throttle.txt", ["vcgencmd", "get_throttled"], 3),
            ("hardware/temperature.txt", ["vcgencmd", "measure_temp"], 3),
        ):
            command(root, rel, args, timeout=timeout)

        # Network troubleshooting without collecting Wi-Fi connection profiles or PSKs.
        for rel, args, timeout in (
            ("network/ip-addresses.txt", ["ip", "-brief", "address"], 5),
            ("network/ip-links.txt", ["ip", "-s", "link"], 5),
            ("network/routes-ipv4.txt", ["ip", "route", "show"], 5),
            ("network/routes-ipv6.txt", ["ip", "-6", "route", "show"], 5),
            ("network/listeners.txt", ["ss", "-lntup"], 5),
            ("network/wifi-link.txt", ["iw", "dev", "wlan0", "link"], 5),
            ("network/rfkill.txt", ["rfkill", "list"], 5),
        ):
            command(root, rel, args, timeout=timeout)
        if Path("/etc/resolv.conf").is_file():
            write_text(root, "network/resolv.conf.txt", Path("/etc/resolv.conf").read_text(encoding="utf-8", errors="replace"), sanitize=True)
        master = str((public_cfg.get("brandmeister") or {}).get("master") or "").strip()
        if master and re.fullmatch(r"[A-Za-z0-9.-]{1,253}", master):
            command(root, "network/brandmeister-dns.txt", ["getent", "ahosts", master], timeout=5)
        command(root, "network/github-dns.txt", ["getent", "ahosts", "github.com"], timeout=5)

        # Exact binary/runtime provenance is critical when RF/plugin behavior differs.
        write_json(root, "runtime/binaries.json", binary_inventory(), redact=False)
        git_doc = git_provenance(root)

        # Public/safe subsystem snapshots added after the original diagnostics code.
        system_summary = {
            "hostname": health_doc.get("hostname"),
            "uptime_s": health_doc.get("uptime_s"),
            "temperature_c": health_doc.get("temperature_c"),
            "load": health_doc.get("load"),
        }
        plugins = plugin_snapshot(system_summary)
        dmrid = dmrid_snapshot()
        ssh = ssh_snapshot()
        vocoder = vocoder_snapshot()
        write_json(root, "plugins/plugin-snapshot.json", plugins)
        write_json(root, "dmrid/dmrid-status.json", dmrid)
        write_json(root, "security/ssh-status.json", ssh)
        write_json(root, "vocoder/vocoder-status.json", vocoder)
        ssh_fingerprints(root)

        # File inventories provide presence/ownership/size clues without copying
        # private config history, plugin data payloads, credentials, or key files.
        write_json(root, "inventory/etc-ywd-hotspot.json", inventory_dir(ETC, depth=2), redact=False)
        write_json(root, "inventory/var-lib-ywd-hotspot.json", inventory_dir(VAR, depth=2), redact=False)
        write_json(root, "inventory/plugin-config-files.json", inventory_dir(ETC / "plugins", depth=1), redact=False)
        write_json(root, "inventory/plugin-data-files.json", inventory_dir(VAR / "plugins", depth=2), redact=False)
        write_json(root, "inventory/pre-update-backups.json", inventory_dir(Path("/var/backups/ywd-hotspot"), depth=2), redact=False)

        summary = support_summary(build, public_cfg, health_doc, units, plugins, dmrid, ssh, vocoder, git_doc)
        write_text(root, "support-summary.txt", summary, sanitize=True)

        readme = (
            "YWD-Hotspot diagnostic bundle\n"
            f"Created: {now_iso()}\n\n"
            "This archive is intended for troubleshooting YWD-Hotspot appliance, RF, network, update, plugin, display, SSH, and vocoder issues.\n\n"
            "INTENTIONALLY EXCLUDED / REDACTED:\n"
            "  - BrandMeister Hotspot Security password\n"
            "  - BrandMeister API key\n"
            "  - WebUI control credential/hash\n"
            "  - Wi-Fi connection profiles and PSKs\n"
            "  - SSH private/public key material (fingerprints only)\n"
            "  - plugin fields declared secret\n\n"
            "The bundle DOES contain station/system metadata, LAN addressing, SSID name, configured RF frequencies, callsign/location data from the public config, recent radio/service logs, and plugin/service inventory. Treat it as support data rather than a public document.\n\n"
            "Known credential patterns are scrubbed from collected text. Third-party/plugin logs can contain arbitrary text, so review a bundle before posting it publicly.\n\n"
            "Start with support-summary.txt, then state/, runtime/, system/, journals/, plugins/, network/, security/, dmrid/, and vocoder/ as needed.\n"
        )
        write_text(root, "README.txt", readme)

        files = []
        for path in sorted(root.rglob("*")):
            if path.is_file():
                files.append({
                    "path": str(path.relative_to(root)),
                    "size": path.stat().st_size,
                    "sha256": sha256(path),
                })
        manifest = {
            "schema": 2,
            "kind": "ywd-hotspot-diagnostics",
            "created_at": now_iso(),
            "hostname": socket.gethostname(),
            "version": build.get("version", "unknown"),
            "branch": build.get("branch", "unknown"),
            "commit": build.get("commit", "unknown"),
            "update_channel": build.get("update_channel", build.get("branch", "unknown")),
            "credential_policy": "known secrets excluded/redacted; review third-party logs before public sharing",
            "files": files,
        }
        write_json(root, "bundle-manifest.json", manifest, redact=False)

        tmp_archive = Path(td) / name
        with tarfile.open(tmp_archive, "w:gz") as tf:
            tf.add(root, arcname=root.name)
        shutil.copyfile(tmp_archive, final)

    os.chmod(final, 0o640)
    try:
        os.chown(final, 0, admin.gid())
    except Exception:
        pass
    admin.audit("diagnostics-created-v2", {"file": name, "size": final.stat().st_size})
    prune_old(keep=8)
    return {"ok": True, "filename": name, "size": final.stat().st_size, "schema": 2}


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("diagnostics helper must run as root")
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action != "diagnostics":
        raise SystemExit("usage: diagnostics_admin.py diagnostics")
    print(json.dumps(diagnostics(), separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)[:1000]}, separators=(",", ":")))
        raise SystemExit(1)
