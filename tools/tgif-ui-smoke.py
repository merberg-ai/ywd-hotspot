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


def main() -> int:
    # Python syntax for every changed privileged/backend module.
    for rel in (
        "lib/tgif_admin.py",
        "lib/dashboard_backup.py",
        "lib/dashboard_update.py",
        "lib/update_admin.py",
    ):
        ast.parse(text(rel), filename=rel)

    require(
        "lib/tgif_admin.py",
        'action == "tgif-configure"',
        'action == "set-tgif-password"',
        '"tgif-security-password-change"',
        'cfg.get("brandmeister"',
        'cfg.get("tgif"',
        'core_admin.backup_config("pre-tgif-config"',
        'core_admin.backup_config("pre-tgif-password"',
    )
    require(
        "lib/admin_dispatch.sh",
        "tgif-configure|set-tgif-password",
        "tgif_admin.py",
    )
    require(
        "sudoers/ywd-hotspot",
        "ywd-hotspot-admin set-tgif-password",
        "ywd-hotspot-admin tgif-configure",
    )
    require(
        "lib/dashboard_backup.py",
        '"/api/tgif/configure": ("tgif-configure", 60)',
        '"/api/tgif/password": ("set-tgif-password", 60)',
        "require_control",
    )
    require(
        "lib/dashboard_update.py",
        "'/tgif-ui.js?v=dev-tgif2'",
        '"/tgif-ui.js": ("tgif-ui.js"',
    )
    require(
        "web/tgif-ui.js",
        "TGIF NETWORK — EXPERIMENTAL",
        "/api/tgif/configure",
        "/api/tgif/password",
        "5031665",
        "password_configured",
        "let formDirty = false",
        "function setFormDirty(value)",
        "if (!formDirty)",
        "setFormDirty(false)",
        "node.addEventListener('change', () => setFormDirty(true))",
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
