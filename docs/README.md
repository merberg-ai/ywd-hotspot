# 📚 YWD-Hotspot Documentation

<p align="center"><strong>Pick the job you are trying to do and jump straight to the right guide.</strong></p>

[← Back to project README](../README.md)

---

## Documentation map

| I want to… | Guide |
|---|---|
| 🚀 Install a new hotspot | **[Installation](INSTALL.md)** |
| 🔄 Check/apply updates or switch channels | **[Upgrading](UPGRADING.md)** |
| 🔐 Export/restore `.ywdsettings` | **[Backup / Restore](BACKUP-RESTORE.md)** |
| 📻 Manage BrandMeister static/dynamic talkgroups | **[Talkgroup Manager](TALKGROUPS.md)** |
| 📟 Configure live gauges and OLED | **[Display + Instrumentation](DISPLAY.md)** |
| 🧪 Calibrate RXOffset with BER measurements | **[Calibration](CALIBRATION.md)** |
| 🧩 Understand the plugin framework | **[Plugins](PLUGINS.md)** |
| 📦 Build/upload/sign/update `.ywdplugin` packages | **[Plugin Packages](PLUGIN-PACKAGES.md)** |
| 🖥️ Understand isolated browser plugin sections | **[Plugin UI](PLUGIN-UI.md)** |
| 🎧 Understand passive DMR voice / RX Monitor core path | **[Passive DMR Voice](DMR-VOICE.md)** |
| 📡 Understand trusted MMDVM telemetry | **[MMDVM Telemetry](TELEMETRY.md)** |
| 📞 Understand normalized DMR sessions | **[MMDVM Sessions](MMDVM-SESSIONS.md)** |
| 🧱 Understand RF/runtime boundaries | **[Architecture](ARCHITECTURE.md)** |
| 🥧 Build a complete appliance image | **[OS Development](OS-DEVELOPMENT.md)** |
| 🌿 Understand branches/checkpoints/cleanup | **[Repository Policy](REPOSITORY.md)** |
| 🧰 Clone, validate, and develop safely | **[GitHub / Development](GITHUB-SETUP.md)** |
| 🔐 Review secrets/network exposure rules | **[Security](../SECURITY.md)** |
| 🤝 Contribute | **[Contributing](../CONTRIBUTING.md)** |
| 🗒️ Review project release history | **[Changelog](../CHANGELOG.md)** |

## Core operating rules

- **RF never starts merely because install/update/restore/plugin work happened.**
- `/etc/ywd-hotspot/config.json` is canonical; generated radio INIs are outputs.
- MMDVM-Host remains the only modem/RF owner.
- Simplex and duplex are explicit radio modes; duplex uses separate hotspot RX/TX frequencies and TS1/TS2.
- `/opt/ywd-hotspot/repo` is managed source; `/opt/ywd-hotspot/app` is deployed runtime.
- reusable credentials stay out of browser-readable state and public diagnostics.
- portable `.ywdsettings` backups are protected and must be handled as sensitive data.
- dashboard/OLED/activity/telemetry/plugin/voice-observer failures stay outside the DMR-critical path.
- YWD-Hotspot OS keeps one authoritative OLED owner.
- the original Raspberry Pi Zero W remains the performance budget.
- plugin support is globally disableable and no current plugin gets independent RF ownership or TX authority.
- uploading a `.ywdplugin` verifies/reviews it before install; installation and activation remain separate.
- same-plugin package updates are explicit transactional operations with rollback rather than manual uninstall/reinstall choreography.
- uploaded executable service/UI plugins require trusted Ed25519 signatures.
- UI plugins execute in an isolated iframe and receive only declared capability methods.
- passive RX Monitor audio decoding runs in the browser, not on the Pi.
- candidate update validation follows the runtime capabilities present in the candidate, not only the branch name.

## Branch model

Long-lived core branches:

| Branch | Purpose |
|---|---|
| `main` | promoted/conservative line |
| `dev` | physically accepted integrated development baseline |
| `dev-plugins` | next-development / experimental integration line |

Historical known-good milestones should ultimately live as immutable checkpoint/archive tags. Some legacy `checkpoint-*` branches remain from rapid Alpha development and are tracked as cleanup work rather than active lines.

## Useful first commands

```bash
ywd-hotspotctl status
ywd-hotspotctl source
ywd-hotspotctl health
```

For a sanitized support bundle:

```bash
sudo ywd-hotspotctl diagnostics
```

Never post protected backups, raw credential files, signing private keys, `.ywdsettings` passphrases, or unsanitized appliance state.
