# 📚 YWD-Hotspot Documentation

<p align="center"><strong>Pick the job you are trying to do and jump straight to the right guide.</strong></p>

[← Back to project README](../README.md)

---

## 🧭 Documentation map

| I want to… | Guide |
|---|---|
| 🚀 Install YWD-Hotspot from the promoted `main` branch | **[Installation](INSTALL.md)** |
| 🥧 Build a complete flashable YWD-Hotspot OS image | **[OS Image Build Guide](OS-IMAGE-BUILD.md)** |
| 🧱 Work on or validate the image-builder source | **[OS Development](OS-DEVELOPMENT.md)** |
| 🔁 Move an older archive install to GitHub | **[Installation](INSTALL.md#-existing-install--github-management)** |
| 🔄 Check/apply updates or switch `main` / `dev` | **[Upgrading](UPGRADING.md)** |
| 🛠️ Recover from an update/migration problem | **[Upgrading](UPGRADING.md#-recovery-and-rollback)** |
| 📻 Manage BrandMeister static/dynamic talkgroups | **[Talkgroup Manager](TALKGROUPS.md)** |
| 📟 Configure LIVE DMR gauges and OLED runtime display | **[Display + Instrumentation](DISPLAY.md)** |
| 🧪 Calibrate RXOffset with BER measurements | **[Calibration](CALIBRATION.md)** |
| 🧱 Understand the RF/runtime architecture | **[Architecture](ARCHITECTURE.md)** |
| 🌿 Understand branches, source layout, and dev checks | **[GitHub / Development](GITHUB-SETUP.md)** |
| 🔐 Review secrets/network exposure rules | **[Security](../SECURITY.md)** |
| 🤝 Contribute a change | **[Contributing](../CONTRIBUTING.md)** |
| 🗒️ See project checkpoints | **[Changelog](../CHANGELOG.md)** |

## 📌 Current promoted baseline

The promoted `main` line and plain `dev` line currently share the physically proven integrated application/OS baseline:

```text
0.1.0-alpha12.2-dev
41f1cf9fcf94b3880d5cf11fb35e2cccb6fd3afd
```

The unified OS-builder integration is preserved at `dev-alpha12.2-os-integrated-known-good`.

Experimental plugin/MMDVM work continues separately on `dev-plugins` and is **not** part of the `main` runtime documented here.

## 📡 Core operating rules

A few project rules show up everywhere because they are intentional design constraints:

- **RF never starts merely because an install/update happened.**
- `/etc/ywd-hotspot/config.json` is canonical; generated INI files are outputs.
- `/opt/ywd-hotspot/repo` is managed source; `/opt/ywd-hotspot/app` is deployed runtime.
- reusable credentials stay out of browser-readable data and public diagnostics.
- the dashboard/OLED/activity services stay outside the DMR-critical path.
- on YWD-Hotspot OS, one authoritative OLED daemon owns the SSD1306/I2C device.
- enhanced WebUI instrumentation is optional; Basic mode preserves the lightweight status UI.
- the original Raspberry Pi Zero W remains the performance budget.
- the OS builder packages the application from the same repository commit; normal app updates do not require rebuilding an image.

## 🥧 Image-builder behavior at a glance

Current `main` supports two documented image-build workflows:

- **factory image:** no Wi-Fi preseed; first boot creates the setup AP and then launches the secure setup wizard
- **Wi-Fi-preseeded image:** optional builder-local Wi-Fi credentials are embedded, but callsign/DMR/radio/BrandMeister/control configuration still goes through the secure first-boot wizard

The current builder does **not** provide a supported full radio/BrandMeister configuration preseed. See **[OS Image Build Guide](OS-IMAGE-BUILD.md)** for the exact supported workflow.

## 🌿 Branch model

| Branch | Purpose |
|---|---|
| `main` | promoted/conservative appliance line; currently Alpha12.2 integrated baseline |
| `dev` | normal application/OS development line; currently aligned with promoted Alpha12.2 |
| `dev-alpha12.2-os-integrated-known-good` | physically proven unified app + OS-builder checkpoint |
| `dev-plugins` | separate experimental plugin/MMDVM line; not included in `main` |
| temporary `dev-os-*` / feature branches | isolated integration work before deliberate promotion |

The historical long-lived `dev-os` branch is retained as reference; do not merge it wholesale into current development. Installed non-plugin appliances follow their selected `main`/`dev` application update channel.

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

Never post protected backups, raw credential files, builder-local private keys, or reusable BrandMeister/WebUI secrets.
