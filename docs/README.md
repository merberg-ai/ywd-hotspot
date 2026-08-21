# 📚 YWD-Hotspot Documentation

[← Back to project README](../README.md)

> [!IMPORTANT]
> `0.2.0-rc1` is the current public-testing candidate. Its release image is a factory-clean appliance artifact and is published only after the exact image passes physical smoke testing.

## Documentation map

| I want to… | Guide |
|---|---|
| 🚀 Flash/install a new hotspot | **[Installation](INSTALL.md)** |
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
| 📋 Review the current RC plan | **[0.2.0-rc1 Release Plan](RELEASE-PLAN-0.2.0-rc1.md)** |
| 🔐 Review security/exposure rules | **[Security](../SECURITY.md)** |
| 🗒️ Review release history | **[Changelog](../CHANGELOG.md)** |

## Core operating rules

- RF does not start merely because install/update/restore/plugin work happened.
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
- the original Pi Zero W remains the performance budget.
- branch/ref and persistent update channel are distinct provenance fields.

## Public factory-image invariant

The release image contains **no operator preconfiguration**: no Wi-Fi, callsign/DMR ID, BM credentials/API key, dashboard password, imported settings, RF autostart, or builder SSH authorized key. It boots into the setup AP/OLED-code onboarding flow.

## Current release refs

| Ref | Purpose |
|---|---|
| `release/0.2.0-rc1` | current RC/factory-image preparation |
| `checkpoint-builder-0.1.0-image-boot-proven` | immutable physically proven baseline |
| `dev` | accepted integrated baseline; promotion target after image acceptance |
| `main` | promoted public line; promotion target after image acceptance |

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

Never post protected backups, raw credential files, signing private keys, `.ywdsettings` passphrases, or unsanitized appliance state.
