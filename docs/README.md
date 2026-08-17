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
| 📦 Build/upload/sign a `.ywdplugin` package | **[Plugin Packages](PLUGIN-PACKAGES.md)** |
| 📡 Understand the MMDVM live telemetry bus/plugin | **[MMDVM Telemetry](TELEMETRY.md)** |
| 📞 Understand normalized MMDVM DMR call sessions | **[MMDVM Sessions](MMDVM-SESSIONS.md)** |
| 🔁 Move an older archive install to GitHub | **[Installation](INSTALL.md#-existing-install--github-management)** |
| 🔄 Check/apply updates or switch `main` / `dev` / `dev-plugins` | **[Upgrading](UPGRADING.md)** |
| 🛠️ Recover from an update/migration problem | **[Upgrading](UPGRADING.md#-recovery-and-rollback)** |
| 📻 Manage BrandMeister static/dynamic talkgroups | **[Talkgroup Manager](TALKGROUPS.md)** |
| 📟 Configure LIVE DMR gauges and OLED runtime display | **[Display + Instrumentation](DISPLAY.md)** |
| 🧪 Calibrate RXOffset with BER measurements | **[Calibration](CALIBRATION.md)** |
| 🧱 Understand the RF/runtime architecture | **[Architecture](ARCHITECTURE.md)** |
| 🌿 Understand branches, source layout, and dev checks | **[GitHub / Development](GITHUB-SETUP.md)** |
| 🔐 Review secrets/network exposure rules | **[Security](../SECURITY.md)** |
| 🤝 Contribute a change | **[Contributing](../CONTRIBUTING.md)** |
| 🗒️ See project checkpoints | **[Changelog](../CHANGELOG.md)** |

## 📡 Core operating rules

A few project rules show up everywhere because they are intentional design constraints:

- **RF never starts merely because an install/update/restore happened.**
- `/etc/ywd-hotspot/config.json` is canonical; generated INI files are outputs.
- `/opt/ywd-hotspot/repo` is managed source; `/opt/ywd-hotspot/app` is deployed runtime.
- reusable credentials stay out of browser-readable data and public diagnostics.
- portable `.ywdsettings` backups are encrypted/authenticated before leaving the appliance.
- restoring a backup always requires a fresh explicit choice before RF may be started/enabled.
- the dashboard/OLED/activity services stay outside the DMR-critical path.
- on YWD-Hotspot OS, one authoritative OLED daemon owns the SSD1306/I2C device.
- enhanced WebUI instrumentation is optional; Basic mode preserves the lightweight status UI.
- the original Raspberry Pi Zero W remains the performance budget.
- the OS builder packages the application from the same repository commit; normal app updates do not require rebuilding an image.
- the experimental plugin subsystem is globally disableable and must leave core DMR operation intact when disabled.
- uploading a `.ywdplugin` never installs/enables/starts it.
- uploaded executable service plugins require a trusted Ed25519 signature and still run through the shared restrictive sandbox.
- plugin telemetry remains observational; RF/modem ownership requires a separate explicit arbitration design.

## 🌿 Branch model

| Branch | Purpose |
|---|---|
| `main` | promoted/conservative project line |
| `dev` | current unified non-plugin application + OS-builder baseline |
| `dev-alpha12.2-os-integrated-known-good` | physically tested unified app/OS checkpoint |
| `dev-plugins` | experimental Plugin API / Plugin Manager development line |
| `dev-plugins-alpha18.1-known-good` | current physically proven telemetry/session/plugin rollback anchor before Alpha18.2 |
| temporary feature / audit branches | isolated work merged/published only after validation |

The historical long-lived `dev-os` branch is retained as reference; do not merge it wholesale into current `dev`. The installed appliance can remember `main`, `dev`, or `dev-plugins` as its update channel. See **[Upgrading](UPGRADING.md)**, **[OS Development](OS-DEVELOPMENT.md)**, and **[Plugins](PLUGINS.md)**.

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
