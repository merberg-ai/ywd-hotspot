#!/usr/bin/env python3
"""Static smoke checks for the experimental TGIF WebUI/privileged wiring."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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


def main() -> int:
    # Python syntax for every changed privileged/backend module.
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
        '"/api/tgif/configure": ("tgif-configure", 60)',
        '"/api/tgif/password": ("set-tgif-password", 60)',
        "require_control",
    )
    require(
        "lib/dashboard_tgif.py",
        "TGIF_RF_FIRST",
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
        "'/tgif-ui.js?v=dev-tgif3'",
        '"/tgif-ui.js": ("tgif-ui.js"',
    )
    require(
        "web/tgif-ui.js",
        "TGIF NETWORK — EXPERIMENTAL",
        "/api/tgif/password",
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
        "lib/update_admin.py",
        'cfg.get("brandmeister"',
        'cfg.get("tgif"',
        "dmr_network_enabled",
        'out["dmr_network_reconciled"]',
    )

    # The browser must never receive the stored TGIF secret.
    require(
        "lib/config_model.py",
        'out.setdefault("tgif", {})["password"] = None',
        'out["tgif"]["password_configured"]',
    )

    print("TGIF UI/admin smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
