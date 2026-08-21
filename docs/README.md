# 📚 YWD-Hotspot Documentation

<p align="center"><strong>Pick the job you are trying to do and jump straight to the right guide.</strong></p>

[← Back to project README](../README.md)

---

> [!IMPORTANT]
> The current stable release is **0.1.0** on `main`. The `0.1.0-rc1` tree completed physical acceptance before promotion through `dev` to `main`.

## Documentation map

| I want to… | Guide |
|---|---|
| 🚀 Install a new hotspot | **[Installation](INSTALL.md)** |
| 🛠️ Build/validate source or compile the patched RX voice MMDVM | **[Building](BUILDING.md)** |
| 🔄 Check/apply updates or switch channels | **[Upgrading](UPGRADING.md)** |
| 🔐 Export/restore `.ywdsettings` | **[Backup / Restore](BACKUP-RESTORE.md)** |
| 📻 Manage BrandMeister static/dynamic talkgroups | **[Talkgroup Manager](TALKGROUPS.md)** |
| 📟 Configure live gauges and OLED | **[Display + Instrumentation](DISPLAY.md)** |
| 🧪 Calibrate RXOffset with BER measurements | **[Calibration](CALIBRATION.md)** |
| 🧩 Understand the plugin framework | **[Plugins](PLUGINS.md)** |
| 📦 Build/upload/sign/update `.ywdplugin` packages | **[Plugin Packages](PLUGIN-PACKAGES.md)** |
| 🖥️ Understand isolated browser plugin sections | **[Plugin UI](PLUGIN-UI.md)** |
| 🎧 Understand passive DMR voice / RX Monitor and its patched MMDVM | **[Passive DMR Voice](DMR-VOICE.md)** |
| 📡 Understand trusted MMDVM telemetry | **[MMDVM Telemetry](TELEMETRY.md)** |
| 📞 Understand normalized DMR sessions | **[MMDVM Sessions](MMDVM-SESSIONS.md)** |
| 🧱 Understand RF/runtime boundaries | **[Architecture](ARCHITECTURE.md)** |
| 🥧 Build a complete appliance image | **[OS Development](OS-DEVELOPMENT.md)** |
| 🌿 Understand branches/checkpoints/releases | **[Repository Policy](REPOSITORY.md)** |
| 🧰 Clone, validate, and develop safely | **[GitHub / Development](GITHUB-SETUP.md)** |
| 🗃️ Review Alpha21/22 implementation archaeology | **[Archived Alpha21–22 notes](history/ALPHA21-22-DEVELOPMENT-NOTES.md)** |
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
- uploaded executable service/UI plugins require trusted Ed25519 signatures.
- UI plugins execute in an isolated iframe and receive only declared capability methods.
- passive RX Monitor audio decoding runs in the browser, not on the Pi.
- the optional RX Monitor voice path uses a **patched copy of the pinned MMDVM-Host**, prepared outside normal startup/update; normal application updates do not recompile the radio stack.
- candidate update validation follows runtime capabilities present in the candidate, not only the branch name.
- Git branch/ref and persistent update channel are distinct provenance fields.

## Current branch model

| Branch | Purpose |
|---|---|
| `main` | promoted/conservative releases; current stable 0.1.0 line |
| `dev` | physically accepted integrated development baseline |
| `dev-builder` | isolated OS builder/image work |
| `dev-plugins` | plugin/framework development line |

The completed `dev-release-0.1.0` branch and named `checkpoint-release-*` refs are release-history/rollback references rather than persistent update channels. Normal stable appliances should follow `main`.

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

For the optional patched MMDVM voice tap:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py status
```

Never post protected backups, raw credential files, signing private keys, `.ywdsettings` passphrases, or unsanitized appliance state.
