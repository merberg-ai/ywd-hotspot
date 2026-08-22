# 📚 YWD-Hotspot Documentation

[← Back to project README](../README.md)

> [!IMPORTANT]
> `0.2.0-rc1` is the current public-testing release. Its factory-clean image was physically tested on the reference Pi Zero W + duplex MMDVM appliance before promotion/tagging.

## Documentation map

| I want to… | Guide |
|---|---|
| 🚀 Flash/install a new hotspot | **[Installation](INSTALL.md)** |
| 🔑 Enable SSH/SFTP and connect | **[SSH / SFTP Access](SSH.md)** |
| 🛠️ Validate/build source, MMDVM variants, or images | **[Building](BUILDING.md)** |
| 🥧 Understand the appliance/public-image workflow | **[OS Development](OS-DEVELOPMENT.md)** |
| 🔄 Check/apply updates | **[Upgrading](UPGRADING.md)** |
| 🔐 Export/restore `.ywdsettings` | **[Backup / Restore](BACKUP-RESTORE.md)** |
| 📻 Manage BrandMeister talkgroups | **[Talkgroup Manager](TALKGROUPS.md)** |
| 📟 Configure gauges/OLED | **[Display + Instrumentation](DISPLAY.md)** |
| 🧪 Calibrate RXOffset | **[Calibration](CALIBRATION.md)** |
| 🧩 Understand plugins/runtime requirements | **[Plugins](PLUGINS.md)** |
| 📦 Build/sign/update `.ywdplugin` packages | **[Plugin Packages](PLUGIN-PACKAGES.md)** |
| 🖥️ Understand isolated browser plugins | **[Plugin UI](PLUGIN-UI.md)** |
| 🎧 Understand YWD Extended/passive DMR voice | **[Passive DMR Voice](DMR-VOICE.md)** |
| 📡 Understand trusted MMDVM telemetry | **[Telemetry](TELEMETRY.md)** |
| 📞 Understand normalized sessions | **[MMDVM Sessions](MMDVM-SESSIONS.md)** |
| 🧱 Understand RF/runtime boundaries | **[Architecture](ARCHITECTURE.md)** |
| 🌿 Understand branches/checkpoints/releases | **[Repository Policy](REPOSITORY.md)** |
| 🧰 Develop safely | **[GitHub / Development](GITHUB-SETUP.md)** |
| 📋 Review the RC1 release record | **[0.2.0-rc1 Release Plan](RELEASE-PLAN-0.2.0-rc1.md)** |
| 🔐 Review security/exposure rules | **[Security](../SECURITY.md)** |
| 🗒️ Review release history | **[Changelog](../CHANGELOG.md)** |

## Core operating rules

- RF does not start merely because install/update/restore/plugin/SSH work happened.
- `/etc/ywd-hotspot/config.json` is canonical; generated MMDVM/DMRGateway INIs are outputs.
- MMDVM-Host remains the only modem/RF owner.
- Simplex/duplex are explicit; duplex has separate hotspot RX/TX and TS1/TS2.
- `ywd-extended` is the recommended/default MMDVM runtime; `upstream` is the supported stock opt-out.
- Runtime choice/provenance persists across ordinary app updates.
- Stock and Extended binaries use separate compile-cache identities.
- Plugins may declare trusted MMDVM runtime/API/capability requirements but cannot switch the runtime themselves.
- `/opt/ywd-hotspot/repo` is managed source; `/opt/ywd-hotspot/app` is deployed runtime.
- credentials stay out of browser-readable state and public diagnostics.
- executable service/UI plugins require trusted Ed25519 signatures.
- no current plugin gets independent modem ownership or RF TX authority.
- YWD-Hotspot OS keeps one authoritative OLED owner.
- RSSI is displayed only when modem firmware actually supplies a usable value; BER is never converted into fake dBm.
- factory SSH is OFF; when enabled from the authenticated dashboard it is public-key-only and root SSH/password auth stay disabled.
- the original Pi Zero W remains the performance budget.
- branch/ref and persistent update channel are distinct provenance fields.

## Public factory-image invariant

The release image contains **no operator preconfiguration**: no Wi-Fi, callsign/DMR ID, BM credentials/API key, dashboard password, imported settings, RF autostart, builder SSH authorized key, or reusable SSH server host identity. It boots into the setup AP/OLED-code onboarding flow.

## Current release refs

| Ref | Purpose |
|---|---|
| `v0.2.0-rc1` | immutable physically tested RC1 tag |
| `checkpoint-release-0.2.0-rc1-image-proven` | exact source checkpoint for the accepted RC1 factory image |
| `release/0.2.0-rc1` | frozen RC1 hardening/source branch |
| `dev` | accepted integrated baseline; may move with post-release docs/development |
| `main` | promoted public line; may move with post-release documentation fixes |
| `checkpoint-builder-0.1.0-image-boot-proven` | earlier immutable physically proven baseline |

## Useful commands

```bash
ywd-hotspotctl status
ywd-hotspotctl source
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py status
systemctl --failed --no-pager
```

Sanitized support bundle:

```bash
sudo ywd-hotspotctl diagnostics
```

Never post protected backups, raw credential files, SSH client/server private keys, signing private keys, `.ywdsettings` passphrases, or unsanitized appliance state.

Historical Alpha implementation notes remain under `docs/history/` for archaeology; they are intentionally not rewritten to describe the current release.
