#!/usr/bin/env python3
"""Validate a staged YWD-Hotspot candidate as a coherent runtime tree.

This check is intentionally based on capabilities present in the candidate,
not on the Git branch name used to fetch it. That lets the same safety gate
cover development, promoted dev/main, release candidates, and explicit
checkpoint/tag updates.

It performs only source-tree validation. It never reads or changes live RF,
configuration, plugin state, services, or hardware.
"""
from __future__ import annotations

import argparse
from pathlib import Path


CORE_REQUIRED = (
    "VERSION",
    "MANIFEST.txt",
    "pins.env",
    "INSTALL.sh",
    "INSTALL-core.sh",
    "UPDATE.sh",
    "UPDATE-core.sh",
    "UNINSTALL.sh",
    "GITHUB-UPDATE.sh",
    "GITHUB-UPDATE-core.sh",
    "MIGRATE-TO-GITHUB.sh",
    "MIGRATE-TO-GITHUB-core.sh",
    "bin/ywd-hotspotctl",
    "bin/ywd-hotspotctl-core",
    "bin/ywd-ui.sh",
    "lab/mmdvm-diag.sh",
    "lib/admin.py",
    "lib/dashboard.py",
    "lib/dashboard_backup.py",
    "lib/dashboard_core.py",
    "lib/dashboard_update.py",
    "lib/build_info.py",
    "lib/candidate_validate.py",
    "lib/config_model.py",
    "lib/dmrid_admin.py",
    "lib/generate-config.py",
    "lib/id-update.py",
    "lib/migrate.py",
    "lib/mmdvm_upstream_build.py",
    "lib/runtime_build.py",
    "lib/oled.py",
    "lib/oled_owner.sh",
    "lib/setup_server.py",
    "lib/system_admin.py",
    "lib/update_admin.py",
    "lib/update_runner.py",
    "sudoers/ywd-hotspot",
    "systemd/ywd-mmdvmhost.service",
    "systemd/ywd-dmrgateway.service",
    "systemd/ywd-dashboard.service",
    "systemd/ywd-activity.service",
    "systemd/ywd-setup.service",
    "systemd/ywd-oled.service",
    "systemd/ywd-update.service",
    "systemd/ywd-dmrid-update.service",
    "systemd/ywd-dmrid-update.timer",
    "web/index.html",
    "web/app.js",
    "web/app-core.js",
    "web/style.css",
    "web/talkgroups.js",
    "web/ui-polish.js",
    "web/ui-polish.css",
    "web/update.js",
    "web/update.css",
    "web/update-progress.js",
    "web/system-ui.js",
    "web/system-ui.css",
    "web/backup-restore.js",
    "web/backup-restore.css",
    "web/ssh-key-export.js",
    "web/instrumentation.js",
    "web/instrumentation-bootstrap.js",
    "web/instrumentation.css",
)

PLUGIN_MARKERS = (
    "lib/plugin_ui_manager.py",
    "lib/plugin_package_update.py",
    "web/plugin-ui-host.js",
    "systemd/ywd-plugin@.service",
)

PLUGIN_REQUIRED = (
    "lib/admin_dispatch.sh",
    "lib/dashboard_backup.py",
    "lib/dashboard_plugin_upload.py",
    "lib/dashboard_plugin_wasm.py",
    "lib/dashboard_plugins.py",
    "lib/plugin_admin.py",
    "lib/plugin_admin_common.py",
    "lib/plugin_admin_packages.py",
    "lib/plugin_admin_state.py",
    "lib/plugin_admin_upload.py",
    "lib/plugin_catalog_overlay.py",
    "lib/plugin_manager.py",
    "lib/plugin_manifest.py",
    "lib/plugin_package_archive.py",
    "lib/plugin_package_manager.py",
    "lib/plugin_package_update.py",
    "lib/plugin_service_manager.py",
    "lib/plugin_service_runner.py",
    "lib/plugin_ui_manager.py",
    "lib/plugin_update_safety.py",
    "lib/settings_admin.py",
    "lib/settings_backup.py",
    "lib/setup_entry.sh",
    "lib/setup_restore_server.py",
    "systemd/ywd-plugin@.service",
    "web/backup-restore.css",
    "web/backup-restore.js",
    "web/plugin-config-actions.js",
    "web/plugin-manager-render.js",
    "web/plugin-manager.css",
    "web/plugin-manager.js",
    "web/plugin-package-actions.js",
    "web/plugin-package-update.js",
    "web/plugin-package-upload.js",
    "web/plugin-ui-host.js",
    "web/plugin-ui-runtime.js",
    "web/plugin-ui.css",
)

VOICE_MARKERS = (
    "lib/mmdvm_voice.py",
    "lib/mmdvm_voice_bridge.py",
    "lib/mmdvm_voice_build.py",
    "lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch",
    "systemd/ywd-mmdvm-voice.service",
)

VOICE_REQUIRED = (
    "lib/mmdvm_voice.py",
    "lib/mmdvm_voice_bridge.py",
    "lib/mmdvm_voice_build.py",
    "lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch",
    "systemd/ywd-mmdvm-voice.service",
    "systemd/ywd-mmdvm-voice-build.service",
)

TELEMETRY_MARKERS = (
    "lib/mmdvm_telemetry.py",
    "lib/mmdvm_telemetry_bridge.py",
    "systemd/ywd-mmdvm-telemetry.service",
    "systemd/ywd-mqtt.service",
)

TELEMETRY_REQUIRED = (
    "lib/mmdvm_session.py",
    "lib/mmdvm_telemetry.py",
    "lib/mmdvm_telemetry_bridge.py",
    "lib/telemetry_runtime.py",
    "lib/ywd-mosquitto.conf",
    "systemd/ywd-mmdvm-telemetry.service",
    "systemd/ywd-mqtt.service",
)


def _present(root: Path, rel: str) -> bool:
    return (root / rel).exists()


def _require(root: Path, label: str, paths: tuple[str, ...], errors: list[str]) -> None:
    missing = [path for path in paths if not _present(root, path)]
    if missing:
        errors.append(f"{label} is incomplete; missing: {', '.join(missing)}")


def _require_text_markers(
    root: Path,
    label: str,
    rel: str,
    markers: tuple[str, ...],
    errors: list[str],
) -> None:
    path = root / rel
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        errors.append(f"{label} cannot read {rel}: {exc}")
        return
    missing = [marker for marker in markers if marker not in text]
    if missing:
        errors.append(f"{label} is incomplete in {rel}; missing markers: {', '.join(missing)}")


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    _require(root, "core runtime", CORE_REQUIRED, errors)

    # These are release-critical UI capabilities. The dashboard duplex controls
    # are installed dynamically, so a missing loader/static route can otherwise
    # make a duplex-capable runtime look simplex-only in the browser.
    _require_text_markers(
        root,
        "first-boot duplex setup",
        "lib/setup_server.py",
        ('id="radiomode"', 'id="rxfreq"', 'id="txfreq"', "radioModeChanged"),
        errors,
    )
    _require_text_markers(
        root,
        "dashboard duplex UI",
        "web/app.js",
        ("installDuplexSettings", 'id="hatMode"', "duplexRxMhz", "duplexTxMhz"),
        errors,
    )
    _require_text_markers(
        root,
        "SSH dashboard static route",
        "lib/dashboard_backup.py",
        ('path == "/ssh-key-export.js"', 'self.serve_static("ssh-key-export.js"'),
        errors,
    )
    _require_text_markers(
        root,
        "dashboard instrumentation loader",
        "web/app.js",
        ("/instrumentation.js", "/instrumentation-bootstrap.js", "/instrumentation.css"),
        errors,
    )
    for rel in ("systemd/ywd-setup.service", "systemd/ywd-activity.service"):
        _require_text_markers(
            root,
            "shared runtime state preservation",
            rel,
            ("RuntimeDirectory=ywd-hotspot", "RuntimeDirectoryPreserve=yes"),
            errors,
        )

    plugin_runtime = any(_present(root, path) for path in PLUGIN_MARKERS)
    voice_runtime = any(_present(root, path) for path in VOICE_MARKERS)
    telemetry_runtime = any(_present(root, path) for path in TELEMETRY_MARKERS)

    if plugin_runtime:
        _require(root, "plugin runtime", PLUGIN_REQUIRED, errors)
    if voice_runtime:
        _require(root, "passive DMR voice runtime", VOICE_REQUIRED, errors)
        if not plugin_runtime:
            errors.append("passive DMR voice runtime requires the plugin/UI capability runtime")
    if telemetry_runtime:
        _require(root, "MMDVM telemetry runtime", TELEMETRY_REQUIRED, errors)
        _require_text_markers(
            root,
            "MQTT telemetry listener",
            "lib/ywd-mosquitto.conf",
            ("listener 18883 127.0.0.1",),
            errors,
        )
        _require_text_markers(
            root,
            "MQTT telemetry readiness probe",
            "systemd/ywd-mqtt.service",
            ("/dev/tcp/127.0.0.1/18883",),
            errors,
        )

    if plugin_runtime and voice_runtime and not _present(root, "lib/dashboard_plugin_wasm.py"):
        errors.append("plugin + voice runtime is missing lib/dashboard_plugin_wasm.py")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"[FAIL] Candidate validation: {error}")
        return 1
    print("Candidate capability validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
