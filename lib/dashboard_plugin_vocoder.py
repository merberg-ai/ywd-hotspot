#!/usr/bin/env python3
"""Trusted WebUI bridge for YWD Vocoder Protocol v1.

Sandboxed plugin frames never access the AF_UNIX socket directly.  This wrapper
checks the effective plugin capability, applies small request bounds, and then
uses the trusted core vocoder client.
"""
from __future__ import annotations

from urllib.parse import urlparse

import plugin_ui_manager
import vocoder_client

CAPABILITY = "use:vocoder"
MAX_FRAMES = 10


def _plugin(ident: str):
    plugin = plugin_ui_manager.get_effective_plugin(ident)
    if CAPABILITY not in set(plugin.get("capabilities") or []):
        raise ValueError("plugin is not permitted to use the vocoder bridge")
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
