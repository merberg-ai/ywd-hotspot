#!/usr/bin/env python3
"""Smoke checks for the experimental TGIF WebUI/privileged wiring."""
from __future__ import annotations

import ast
import copy
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "lib"


def text(rel: str) -> str:
    path = ROOT / rel
    assert path.is_file(), f"missing {rel}"
    return path.read_text(encoding="utf-8")


def require(rel: str, *markers: str) -> None:
    data = text(rel)
    for marker in markers:
        assert marker in data, f"{rel}: missing marker {marker!r}"


def forbid(rel: str, *markers: str) -> None:
    data = text(rel)
    for marker in markers:
        assert marker not in data, f"{rel}: forbidden marker still present {marker!r}"


def load_candidate_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def functional_config_save_check() -> None:
    """Prove redacted browser config cannot erase the stored TGIF credential."""
    sys.path.insert(0, str(LIB))
    # Preload the candidate modules under their production import names. This
    # prevents tgif_admin.py's /opt production path from making a /tmp smoke run
    # accidentally exercise the already-installed appliance copies instead.
    load_candidate_module("config_model", LIB / "config_model.py")
    load_candidate_module("admin", LIB / "admin.py")
    mod = load_candidate_module("tgif_admin_smoke", LIB / "tgif_admin.py")

    base = mod.config_model.defaults()
    base["station"].update({"callsign": "KJ6YWD", "base_dmr_id": "3196104", "essid": "02"})
    base["tgif"]["password"] = "smoke-secret"
    old = mod.config_model.normalize(base)
    candidate = copy.deepcopy(old)
    writes = []

    mod.core_admin.merge_browser_config = lambda data: (old, copy.deepcopy(candidate))
    mod.core_admin.backup_config = lambda reason, changed=None: "smoke-snapshot"
    mod.core_admin.write_config = lambda cfg: writes.append(copy.deepcopy(cfg))
    mod.core_admin.audit = lambda *args, **kwargs: None

    out = mod.config_save({
        "config": {
            "tgif": {
                "enabled": True,
                "master": "tgif.network",
                "port": 62031,
                "password": None,
                "password_configured": True,
            }
        }
    })
    assert out.get("ok") is True
    assert "tgif.enabled" in out.get("changed", [])
    assert writes, "TGIF-aware config-save did not write the candidate"
    saved = writes[-1]
    assert saved["tgif"]["enabled"] is True
    assert saved["tgif"]["password"] == "smoke-secret", "normal Settings save erased TGIF password"


def main() -> int:
    for rel in (
        "lib/tgif_admin.py",
        "lib/dashboard_tgif.py",
        "lib/dashboard_backup.py",
        "lib/dashboard_update.py",
        "lib/update_admin.py",
    ):
        ast.parse(text(rel), filename=rel)

    require(
        "lib/tgif_admin.py",
        'action == "config-save"',
        'action == "tgif-configure"',
        'action == "set-tgif-password"',
        'TGIF_BROWSER_KEYS = {"enabled", "master", "port"}',
        'TGIF_SECRET_KEYS = {"password", "password_configured"}',
        "core_admin.merge_browser_config(data)",
        'candidate.setdefault("tgif", {})[key] = value',
        'core_admin.backup_config("pre-save", changed)',
        '"tgif-security-password-change"',
        'cfg.get("brandmeister"',
        'cfg.get("tgif"',
    )
    require(
        "lib/admin_dispatch.sh",
        "config-save|tgif-configure|set-tgif-password",
        "tgif_admin.py",
    )
    require(
        "sudoers/ywd-hotspot",
        "ywd-hotspot-admin set-tgif-password",
        "ywd-hotspot-admin tgif-configure",
        "ywd-hotspot-admin config-save",
    )
    require(
        "lib/dashboard_backup.py",
        "import dashboard_tgif",
        "dashboard_tgif.install(core)",
        'path == "/api/tgif/talkgroups/search"',
        "search_tgif_talkgroups",
        "Unlock control mode before forcing a TGIF directory refresh",
        '"/api/tgif/configure": ("tgif-configure", 60, None)',
        '"/api/tgif/password": ("set-tgif-password", 60, None)',
        "require_control",
    )
    require(
        "lib/dashboard_tgif.py",
        "TGIF_RF_FIRST",
        "TGIF_DIRECTORY_URL",
        "https://api.tgif.network/dmr/talkgroups/json",
        "normalize_tgif_talkgroups",
        "search_tgif_talkgroups",
        "TGIF_KNOWN_TG",
        "_talkgroup_row",
        '"synthetic"',
        '"rf_talkgroup"',
        '"supported"',
        "_directory_names",
        "_network_state_from_lines",
        '"TGIF_Network"',
        'network="tgif"',
        'network="brandmeister"',
        '"rf_id"',
        "network_id=network_id",
        '"TGIF · TG {network_id}"',
        'base["tgif"]',
        "annotate_activity",
    )
    require(
        "lib/dashboard_update.py",
        "'/tgif-ui.js?v=dev-tgif4'",
        '"/tgif-ui.js": ("tgif-ui.js"',
        '"/control-theme.css": ("control-theme.css"',
        'control_css = _asset_bytes("control-theme.css")',
        "dashboard-wide interactive control theme",
    )
    require(
        "web/tgif-ui.js",
        "TGIF NETWORK — EXPERIMENTAL",
        "/api/tgif/password",
        "/api/tgif/talkgroups/search",
        "SEARCH TGIF DIRECTORY",
        "TGIF FAVORITES",
        "TGIF does not use BrandMeister-style static talkgroups",
        "COPY RF TG",
        "ywd.tgifFavorites.v1",
        "5031665",
        "password_configured",
        'data-cfg="tgif.master"',
        'data-cfg="tgif.port"',
        'data-cfg="tgif.enabled"',
        "function settingsDirty()",
        "function markSettingsDirty()",
        "setDirty(true)",
        "node.addEventListener('change', markSettingsDirty)",
        "normal Settings SAVE / SAVE &amp; APPLY controls",
        "function renderNetworkPresentation(data)",
        "TGIF ${safe(stateText",
        "destinationText(dst, true)",
        "RF ${dst.rf_id}",
        "heardRows",
    )
    forbid(
        "web/tgif-ui.js",
        "tgifSaveApply",
        "SAVE &amp; APPLY TGIF",
        "saveSettings()",
        "setFormDirty",
        "/api/tgif/configure",
    )
    require(
        "web/control-theme.css",
        "color-scheme:dark",
        ":focus-visible",
        "background-color:#06141b!important",
        "input:-webkit-autofill",
        "-webkit-text-fill-color:var(--text)!important",
        "select option",
        "file-selector-button",
    )
    require(
        "lib/update_admin.py",
        'cfg.get("brandmeister"',
        'cfg.get("tgif"',
        "dmr_network_enabled",
        'out["dmr_network_reconciled"]',
    )

    require(
        "lib/config_model.py",
        'out.setdefault("tgif", {})["password"] = None',
        'out["tgif"]["password_configured"]',
    )

    functional_config_save_check()
    print("TGIF UI/admin smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
