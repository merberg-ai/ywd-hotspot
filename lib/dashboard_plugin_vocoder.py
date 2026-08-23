#!/usr/bin/env python3
"""Trusted WebUI bridge for YWD Vocoder Protocol v1.

Sandboxed plugin frames never access the AF_UNIX socket directly.  This wrapper
checks the effective plugin capability, applies small request bounds, and then
uses the trusted core vocoder client.

The expensive signed UI-manifest validation is cached by manifest inode/mtime/
size. Mutable authorization gates remain live on every request, so disabling the
plugin subsystem, disabling the individual plugin, uninstalling the package, or
replacing its manifest revokes/revalidates access immediately without forcing a
full catalog discovery on every 100 ms live-audio decode batch.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import plugin_manager
import plugin_package_manager
import plugin_ui_manager
import vocoder_client

CAPABILITY = "use:vocoder"
MAX_FRAMES = 10
_PLUGIN_CACHE = {}


def _manifest_stamp(path: Path):
    st = path.stat()
    return (int(st.st_ino), int(st.st_mtime_ns), int(st.st_size))


def _live_authorized(ident: str) -> None:
    """Check only mutable gates that must remain immediately revocable."""
    state = plugin_manager.read_state()
    if not state.get("enabled"):
        raise ValueError("plugin subsystem is disabled")
    if not bool((state.get("plugins", {}).get(ident) or {}).get("enabled", False)):
        raise ValueError("UI plugin is disabled")
    if not plugin_package_manager.is_installed(ident):
        raise ValueError("UI plugin is not installed")


def _plugin(ident: str):
    ident = str(ident or "")
    if not plugin_manager.ID_RE.fullmatch(ident):
        raise ValueError("invalid plugin id")

    # These inexpensive state/package checks intentionally happen for every
    # request so permission removal takes effect without waiting for a cache TTL.
    _live_authorized(ident)

    cached = _PLUGIN_CACHE.get(ident)
    if cached:
        manifest_path = Path(cached["manifest_path"])
        try:
            if _manifest_stamp(manifest_path) == cached["stamp"]:
                plugin = cached["plugin"]
                if CAPABILITY not in set(plugin.get("capabilities") or []):
                    raise ValueError("plugin is not permitted to use the vocoder bridge")
                return plugin
        except (FileNotFoundError, OSError):
            pass
        _PLUGIN_CACHE.pop(ident, None)

    # Cache miss or package replacement: perform the full fail-closed signed UI
    # discovery/manifest validation once, then bind the cache to that exact file.
    plugin = plugin_ui_manager.get_effective_plugin(ident)
    if CAPABILITY not in set(plugin.get("capabilities") or []):
        raise ValueError("plugin is not permitted to use the vocoder bridge")
    manifest_path = Path(plugin["directory"]) / "plugin.json"
    _PLUGIN_CACHE[ident] = {
        "manifest_path": str(manifest_path),
        "stamp": _manifest_stamp(manifest_path),
        "plugin": plugin,
    }
    return plugin


def _parts(path: str):
    parts = str(path or "").strip("/").split("/")
    if len(parts) == 6 and parts[:3] == ["api", "plugins", "ui"] and parts[4] == "vocoder":
        return parts[3], parts[5]
    return None, None


def _frames(body) -> list[str]:
    frames = body.get("frames") if isinstance(body, dict) else None
    if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_FRAMES:
        raise ValueError(f"vocoder decode requires 1-{MAX_FRAMES} AMBE49 frames")
    clean = []
    for frame in frames:
        bits = str(frame or "")
        if len(bits) != 49 or any(ch not in "01" for ch in bits):
            raise ValueError("each vocoder frame must contain exactly 49 binary digits")
        clean.append(bits)
    return clean


def wrap_handler(base):
    class PluginVocoderHandler(base):
        def do_GET(self):
            ident, action = _parts(urlparse(self.path).path)
            if not ident or action != "status":
                super().do_GET()
                return
            if not self.require_control():
                return
            try:
                _plugin(ident)
                self.send_json({"ok": True, "id": ident, "vocoder": vocoder_client.status()})
            except ValueError as exc:
                self.send_json({"error": str(exc)[:500]}, 409)
            except Exception as exc:
                self.send_json({"error": str(exc)[:800]}, 502)

        def do_POST(self):
            ident, action = _parts(urlparse(self.path).path)
            if not ident or action not in {"reset", "decode"}:
                super().do_POST()
                return
            if not self.require_control():
                return
            try:
                _plugin(ident)
                body = self.body_json()
                if action == "reset":
                    out = vocoder_client.reset()
                else:
                    out = vocoder_client.public_decode(_frames(body))
                self.send_json({"ok": True, "id": ident, "vocoder": out})
            except ValueError as exc:
                self.send_json({"error": str(exc)[:500]}, 400)
            except vocoder_client.VocoderUnavailable as exc:
                self.send_json({"error": str(exc)[:500]}, 503)
            except vocoder_client.VocoderBackendError as exc:
                self.send_json({"error": str(exc)[:500]}, 502)
            except Exception as exc:
                self.send_json({"error": str(exc)[:800]}, 502)

    PluginVocoderHandler.__name__ = f"PluginVocoder{base.__name__}"
    return PluginVocoderHandler
