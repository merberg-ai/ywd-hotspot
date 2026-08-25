#!/usr/bin/env python3
"""Privacy/runtime policy wrapper for the YWD-Hotspot diagnostics v2 collector.

Keep the large collector focused on collection mechanics while this thin layer
hardens free-form string scrubbing and adds safe live runtime snapshots that did
not exist when the original diagnostic bundle was designed.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import diagnostics_admin as base

_ORIGINAL_MARKERS = base.marker_state
_ORIGINAL_READ_JSON = base.read_json
_ORIGINAL_SANITIZE = base.sanitize_text
_ORIGINAL_SUMMARY = base.support_summary
CLI_SECRET_RE = re.compile(
    r"(?i)(--?(?:password|passwd|passphrase|api[-_]?key|token|secret|credential|psk)\s+)(\S+)"
)
PSK_ASSIGN_RE = re.compile(r"(?i)\b(psk)(\s*[:=]\s*)([^\s,;]+)")
URL_CREDENTIAL_RE = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)([^/\s:@]+):([^@\s/]+)@")
LOCAL_SECRET_KEY_RE = re.compile(r"(?:psk|pre[_ -]?shared[_ -]?key)", re.I)
MODEM_ID_RE = re.compile(
    r"(?i)(?:MMDVM|modem).*(?:protocol|firmware|version|description|revision|serial|opened|opening)"
)


def sanitize_text(text: str) -> str:
    """Scrub structured values plus common command-line/URL credential forms."""
    value = _ORIGINAL_SANITIZE(text)
    value = CLI_SECRET_RE.sub(lambda m: f"{m.group(1)}***REDACTED***", value)
    value = PSK_ASSIGN_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}***REDACTED***", value)
    value = URL_CREDENTIAL_RE.sub(lambda m: f"{m.group(1)}***:***@", value)
    return value


def redact_json(value, key=""):
    """Apply structural redaction plus text-pattern scrubbing to every string."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            name = str(k)
            is_secret = (
                base.SECRET_KEY_RE.search(name)
                or LOCAL_SECRET_KEY_RE.search(name)
            )
            if is_secret and not base.SAFE_SECRET_META_RE.search(name):
                out[name] = "***REDACTED***" if v not in (None, "", False) else v
            else:
                out[name] = redact_json(v, name)
        return out
    if isinstance(value, list):
        return [redact_json(item, key) for item in value]
    if isinstance(value, str):
        return sanitize_text(value).rstrip("\n")
    return value


def read_json(path: Path, default=None):
    """Inject the separately persisted first-party update channel into build info."""
    doc = _ORIGINAL_READ_JSON(path, default)
    try:
        same_build = Path(path).resolve() == (base.ETC / "build-info.json").resolve()
    except Exception:
        same_build = False
    if same_build and isinstance(doc, dict):
        doc = dict(doc)
        try:
            channel = (base.ETC / "update-channel").read_text(encoding="utf-8").strip()
            if channel:
                doc["update_channel"] = channel
        except Exception:
            pass
    return doc


def _safe_runtime_json(root: Path, rel: str, path: Path, state: dict) -> None:
    if not path.is_file() or path.is_symlink():
        state[rel] = {"present": False, "readable": False, "path": str(path)}
        return
    doc = read_json(path, None)
    if not isinstance(doc, dict):
        state[rel] = {"present": True, "readable": False, "path": str(path)}
        return
    base.write_json(root, f"runtime-state/{rel}", redact_json(doc), redact=False)
    state[rel] = {"present": True, "readable": True, "path": str(path)}


def _copy_boot_metadata(root: Path) -> None:
    """Capture passive Pi UART/boot configuration without touching the live modem."""
    candidates = {
        "hardware/boot-config.txt": [Path("/boot/firmware/config.txt"), Path("/boot/config.txt")],
        "hardware/boot-cmdline.txt": [Path("/boot/firmware/cmdline.txt"), Path("/boot/cmdline.txt")],
    }
    for rel, paths in candidates.items():
        for path in paths:
            if not path.is_file() or path.is_symlink():
                continue
            try:
                base.write_text(
                    root,
                    rel,
                    f"SOURCE: {path}\n\n" + path.read_text(encoding="utf-8", errors="replace"),
                    sanitize=True,
                )
            except Exception as exc:
                base.write_text(root, rel, f"could not read {path}: {sanitize_text(str(exc))}\n")
            break
    try:
        cmdline = Path("/proc/cmdline").read_text(encoding="utf-8", errors="replace")
        base.write_text(root, "hardware/proc-cmdline.txt", cmdline, sanitize=True)
    except Exception:
        pass

    serial_lines = []
    for path in (Path("/dev/serial0"), Path("/dev/ttyAMA0"), Path("/dev/ttyS0")):
        try:
            serial_lines.append(f"{path} -> {path.resolve(strict=False)}")
        except Exception as exc:
            serial_lines.append(f"{path} -> error: {sanitize_text(str(exc))}")
    base.write_text(root, "hardware/serial-resolution.txt", "\n".join(serial_lines) + "\n")

    for unit in ("serial-getty@serial0.service", "serial-getty@ttyAMA0.service", "serial-getty@ttyS0.service"):
        safe = unit.replace("@", "_")
        base.command(
            root,
            f"hardware/{safe}.txt",
            ["systemctl", "show", unit, "--property=LoadState,ActiveState,SubState,UnitFileState,FragmentPath"],
            timeout=4,
        )

    if shutil.which("raspi-config"):
        base.command(root, "hardware/raspi-config-serial.txt", ["raspi-config", "nonint", "get_serial"], timeout=5)


def _mmdvm_identification(root: Path) -> None:
    """Extract startup modem identity lines from the journal; never open the UART."""
    proc = base.run(
        ["journalctl", "-u", "ywd-mmdvmhost.service", "-b", "0", "--no-pager", "-o", "cat"],
        timeout=8,
    )
    rows = []
    for line in (proc.stdout or "").splitlines():
        if MODEM_ID_RE.search(line):
            clean = sanitize_text(line).strip()
            if clean and clean not in rows:
                rows.append(clean)
        if len(rows) >= 120:
            break
    if not rows:
        rows = ["No modem identification/version lines matched in the current-boot MMDVMHost journal."]
        if proc.returncode != 0 and proc.stderr:
            rows.append(f"journal error: {sanitize_text(proc.stderr).strip()}")
    base.write_text(root, "hardware/mmdvm-identification-current-boot.txt", "\n".join(rows) + "\n")


def _support_tooling(root: Path) -> None:
    """Collect small dependency/firewall facts that commonly explain LAN issues."""
    packages = ["python3", "git", "openssh-server", "mosquitto", "network-manager", "iw", "rfkill"]
    if shutil.which("dpkg-query"):
        base.command(
            root,
            "system/support-package-versions.txt",
            ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Architecture}\n", *packages],
            timeout=6,
        )
    if shutil.which("nft"):
        base.command(root, "network/firewall-nft.txt", ["nft", "list", "ruleset"], timeout=6)
    elif shutil.which("iptables"):
        base.command(root, "network/firewall-iptables.txt", ["iptables", "-S"], timeout=6)
    if shutil.which("nmcli"):
        base.command(
            root,
            "network/networkmanager-device-status.txt",
            ["nmcli", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"],
            timeout=5,
        )


def marker_state(root: Path) -> dict:
    state = _ORIGINAL_MARKERS(root)

    # Current dashboard activity includes recent DMR traffic/session quality and
    # is often the fastest way to reconcile "radio did X / dashboard showed Y".
    _safe_runtime_json(root, "activity.json", Path("/run/ywd-hotspot/activity.json"), state)

    # Raw bridge JSON is already local/trusted, but export only the public
    # projections for telemetry/voice where possible so frame payloads are not
    # needlessly copied into support archives.
    try:
        import mmdvm_telemetry
        base.write_json(
            root,
            "runtime-state/mmdvm-telemetry-public.json",
            redact_json(mmdvm_telemetry.public_snapshot()),
            redact=False,
        )
        state["mmdvm-telemetry-public.json"] = {
            "present": True,
            "readable": True,
            "path": str(mmdvm_telemetry.SNAPSHOT),
        }
    except Exception as exc:
        state["mmdvm-telemetry-public.json"] = {
            "present": False,
            "readable": False,
            "error": sanitize_text(str(exc))[:400],
        }

    try:
        import mmdvm_voice
        raw = mmdvm_voice.read_state()
        frames = raw.get("frames") if isinstance(raw.get("frames"), list) else []
        # Do not export AMBE frame payloads. Keep only bridge/session counters and
        # a tiny metadata-only description of the newest frames.
        recent = []
        for frame in frames[-8:]:
            if not isinstance(frame, dict):
                continue
            recent.append({
                key: value for key, value in frame.items()
                if key not in {"ambe", "ambe49", "bits", "payload", "data", "frame"}
            })
        voice = {
            "schema": raw.get("schema"),
            "bridge": raw.get("bridge") if isinstance(raw.get("bridge"), dict) else {},
            "next_seq": raw.get("next_seq"),
            "buffered_frame_count": len(frames),
            "recent_frame_metadata": recent,
        }
        base.write_json(root, "runtime-state/mmdvm-voice-public.json", redact_json(voice), redact=False)
        state["mmdvm-voice-public.json"] = {
            "present": True,
            "readable": True,
            "path": str(mmdvm_voice.STATE),
        }
    except Exception as exc:
        state["mmdvm-voice-public.json"] = {
            "present": False,
            "readable": False,
            "error": sanitize_text(str(exc))[:400],
        }

    # Presence/ownership/size clues for transient runtime files without dumping
    # arbitrary sockets or private payloads.
    base.write_json(
        root,
        "inventory/run-ywd-hotspot.json",
        base.inventory_dir(Path("/run/ywd-hotspot"), depth=2),
        redact=False,
    )
    base.write_json(
        root,
        "inventory/run-ywd-telemetry.json",
        base.inventory_dir(Path("/run/ywd-hotspot-telemetry"), depth=1),
        redact=False,
    )
    base.write_json(
        root,
        "inventory/run-ywd-voice.json",
        base.inventory_dir(Path("/run/ywd-hotspot-voice"), depth=1),
        redact=False,
    )

    _copy_boot_metadata(root)
    _mmdvm_identification(root)
    _support_tooling(root)
    return state


def support_summary(build, cfg, h, units, plugins, dmrid, ssh, vocoder, git):
    build = dict(build or {})
    try:
        channel = (base.ETC / "update-channel").read_text(encoding="utf-8").strip()
        if channel:
            build["update_channel"] = channel
    except Exception:
        pass
    return sanitize_text(
        _ORIGINAL_SUMMARY(build, cfg, h, units, plugins, dmrid, ssh, vocoder, git)
    )


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("diagnostics helper must run as root")
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action != "diagnostics":
        raise SystemExit("usage: diagnostics_policy.py diagnostics")

    # Monkey-patch only the policy seams intentionally exposed by the collector.
    base.sanitize_text = sanitize_text
    base.redact_json = redact_json
    base.read_json = read_json
    base.marker_state = marker_state
    base.support_summary = support_summary
    print(json.dumps(base.diagnostics(), separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": sanitize_text(str(exc))[:1000]}, separators=(",", ":")))
        raise SystemExit(1)
