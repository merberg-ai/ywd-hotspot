# 📚 YWD-Hotspot Documentation

<p align="center"><strong>Pick the job you are trying to do and jump straight to the right guide.</strong></p>

[← Back to project README](../README.md)

---

## 🧭 Documentation map

| I want to… | Guide |
|---|---|
| 🚀 Install a new hotspot | **[Installation](INSTALL.md)** |
| 🧱 Build a complete YWD-Hotspot OS image | **[OS Development](OS-DEVELOPMENT.md)** |
| 🔐 Export/restore a fresh appliance from `.ywdsettings` | **[Backup / Restore](BACKUP-RESTORE.md)** |
| 🧩 Understand the experimental plugin framework | **[Plugins](PLUGINS.md)** |
| 🖥️ Build a signed plugin-owned dashboard section | **[Plugin UI v1](PLUGIN-UI.md)** |
| 📦 Build/upload/sign a `.ywdplugin` package | **[Plugin Packages](PLUGIN-PACKAGES.md)** |
| 📡 Understand the MMDVM live telemetry bus/plugin | **[MMDVM Telemetry](TELEMETRY.md)** |
| 📞 Understand normalized MMDVM DMR call sessions | **[MMDVM Sessions](MMDVM-SESSIONS.md)** |
| 🎧 Follow the experimental RX Monitor / passive voice-frame bridge | **[Passive DMR Voice](DMR-VOICE.md)** |
| 🔁 Move an older archive install to GitHub | **[Installation](INSTALL.md#-existing-install--github-management)** |
| 🔄 Check/apply updates or switch channels | **[Upgrading](UPGRADING.md)** |
| 🛠️ Recover from an update/migration problem | **[Upgrading](UPGRADING.md#-recovery-and-rollback)** |
| 📻 Manage BrandMeister static/dynamic talkgroups | **[Talkgroup Manager](TALKGROUPS.md)** |
| 📟 Configure LIVE DMR gauges and OLED runtime display | **[Display + Instrumentation](DISPLAY.md)** |
| 🧪 Calibrate RXOffset with BER measurements | **[Calibration](CALIBRATION.md)** |
| 🧱 Understand the RF/runtime architecture | **[Architecture](ARCHITECTURE.md)** |
| 🌿 Understand branches, tags and repository lifecycle | **[Repository Policy](REPOSITORY.md)** |
| 🧰 Clone, validate and develop safely | **[GitHub / Development](GITHUB-SETUP.md)** |
| 🔐 Review secrets/network exposure rules | **[Security](../SECURITY.md)** |
| 🤝 Contribute a change | **[Contributing](../CONTRIBUTING.md)** |
| 🗒️ See historical project checkpoints | **[Changelog](../CHANGELOG.md)** |

## 📡 Core operating rules

A few project rules show up everywhere because they are intentional design constraints:

- **RF never starts merely because an install/update/restore happened.**
- `/etc/ywd-hotspot/config.json` is canonical; generated INI files are outputs.
- `/opt/ywd-hotspot/repo` is managed source; `/opt/ywd-hotspot/app` is deployed runtime.
- reusable credentials stay out of browser-readable data and public diagnostics.
- portable `.ywdsettings` backups are encrypted/authenticated before leaving the appliance.
- restoring a backup always requires a fresh explicit choice before RF may be started/enabled.
- dashboard/OLED/activity/telemetry services stay outside the DMR-critical path.
- on YWD-Hotspot OS, one authoritative OLED daemon owns the SSD1306/I2C device.
- enhanced WebUI instrumentation is optional; Basic mode preserves the lightweight status UI.
- the original Raspberry Pi Zero W remains the performance budget.
- the OS builder packages the application from the same repository commit; normal app updates do not require rebuilding an image.
- the plugin subsystem is globally disableable and must leave core DMR operation intact when disabled.
- uploading a `.ywdplugin` never installs/enables/starts it.
- uploaded executable service plugins require a trusted Ed25519 signature and still run through the shared restrictive sandbox.
- uploaded browser UI plugins also require a trusted Ed25519 signature and execute only inside the isolated Plugin UI frame; they receive no Pi-side daemon.
- plugin telemetry and the Alpha20 passive voice tap remain observational; RF/modem ownership stays with trusted MMDVM-Host core.

## 🌿 Branch and checkpoint model

Long-lived branches are intentionally limited to:

| Branch | Purpose |
|---|---|
| `main` | promoted/conservative line |
| `dev` | stable tested development integration baseline |
| `dev-plugins` | experimental plugin/telemetry/integration line |

Known-good historical builds should be preserved as immutable `checkpoint/*` tags. Superseded long-lived development lines may be retained as `archive/*` tags. Feature/audit branches are temporary and should be removed after their tested result is published.

See **[Repository Policy](REPOSITORY.md)** for naming and cleanup rules.

## 🆘 Useful first commands

```bash
ywd-hotspotctl status
ywd-hotspotctl source
ywd-hotspotctl health
```

For a sanitized support bundle:

```bash
sudo ywd-hotspotctl diagnostics
```

Never post protected backups, raw credential files, signing private keys, `.ywdsettings` passphrases, or reusable BrandMeister/WebUI secrets.
