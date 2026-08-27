# 📚 YWD-Hotspot Documentation

[← Back to project README](../README.md)

> [!IMPORTANT]
> `0.2.0-rc3` is the current physically accepted public-testing release. Its exact factory image passed fresh-flash acceptance on the reference Pi Zero W + MMDVM appliance, and the published RC2 -> RC3 application update path also passed. The immutable release source remains `3823140b9fd4d6e73fe9066af4b2280628f62f5e`; moving channel branches may contain later documentation-only cleanup.

## Documentation map

| I want to… | Guide |
|---|---|
| 🚀 Flash/install a new hotspot | **[Installation](INSTALL.md)** |
| 🔑 Enable SSH/SFTP and connect | **[SSH / SFTP Access](SSH.md)** |
| 🛠️ Validate/build source, MMDVM variants, or images | **[Building](BUILDING.md)** |
| 🥧 Understand the appliance/public-image workflow | **[OS Development](OS-DEVELOPMENT.md)** |
| 🔄 Check/apply updates | **[Upgrading](UPGRADING.md)** |
| 🌿 Change/check the main/dev/dev-plugins software channel | **[Software Channels](SOFTWARE-CHANNELS.md)** |
| 🔐 Export/restore `.ywdsettings` | **[Backup / Restore](BACKUP-RESTORE.md)** |
| 📻 Manage BrandMeister talkgroups | **[Talkgroup Manager](TALKGROUPS.md)** |
| 📟 Configure gauges/OLED | **[Display + Instrumentation](DISPLAY.md)** |
| 🧪 Calibrate RXOffset | **[Calibration](CALIBRATION.md)** |
| 🧩 Understand plugins/runtime requirements | **[Plugins](PLUGINS.md)** |
| 📦 Build/sign/update `.ywdplugin` packages | **[Plugin Packages](PLUGIN-PACKAGES.md)** |
| 🖥️ Understand isolated browser plugins | **[Plugin UI](PLUGIN-UI.md)** |
| 🎧 Understand YWD Extended/passive DMR voice | **[Passive DMR Voice](DMR-VOICE.md)** |
| 📡 Inspect MMDVM HAT/runtime identity in System | **[MODEM / MMDVM System Card](MODEM-SYSTEM-CARD.md)** |
| 🎙️ Install/verify the external RX vocoder backend | **[External Vocoder](VOCODER.md)** |
| 📡 Understand trusted MMDVM telemetry | **[Telemetry](TELEMETRY.md)** |
| 📞 Understand normalized sessions | **[MMDVM Sessions](MMDVM-SESSIONS.md)** |
| 🧱 Understand RF/runtime boundaries | **[Architecture](ARCHITECTURE.md)** |
| 🌿 Understand branches/releases/ref cleanup | **[Repository Policy](REPOSITORY.md)** |
| 🧰 Develop safely | **[GitHub / Development](GITHUB-SETUP.md)** |
| 🧪 Review the accepted RC3 release | **[0.2.0-rc3 Release Notes](RELEASE-NOTES-0.2.0-rc3.md)** |
| 🧪 Review the accepted RC2 release | **[0.2.0-rc2 Release Notes](RELEASE-NOTES-0.2.0-rc2.md)** |
| 📦 Review RC1 release notes | **[0.2.0-rc1 Release Notes](RELEASE-NOTES-0.2.0-rc1.md)** |
| 🗄️ Browse completed plans / Alpha archaeology | **[Historical Documentation](history/README.md)** |
| 🔐 Review security/exposure rules | **[Security](../SECURITY.md)** |
| 🗒️ Review release history | **[Changelog](../CHANGELOG.md)** |

## Current accepted public release

```text
Version
  0.2.0-rc3

Tag / exact release source
  v0.2.0-rc3
  3823140b9fd4d6e73fe9066af4b2280628f62f5e

Published image
  ywd-hotspot-0.2.0-rc3.img.xz

Image SHA256
  5c3151b2a39f5a800b703d8925c53cddcf7bf49d8fcb59eda6bed30afc4413cc

Acceptance
  fresh-image boot/test PASS
  RC2 -> RC3 application updater PASS
  reboot/persistence PASS
  failed systemd units: 0
```

Release page: **[YWD-Hotspot 0.2.0-rc3](https://github.com/merberg-ai/ywd-hotspot/releases/tag/v0.2.0-rc3)**.

## Current repository shape

Normal software channels are `main`, `dev`, and `dev-plugins`. Published release source is retained by immutable `v...` tags plus frozen `release/<version>` branches. Intermediate checkpoint/test refs are temporary engineering evidence and should be pruned once a later published release supersedes them and their commits remain reachable from retained history.

See [Repository Policy](REPOSITORY.md) for the cleanup/retention rules.

## Core operating rules

- RF does not start merely because install/update/restore/plugin/SSH work happened.
- `/etc/ywd-hotspot/config.json` is canonical; generated MMDVM/DMRGateway INIs are outputs.
- MMDVM-Host remains the only modem/RF owner.
- Simplex/duplex are explicit; duplex has separate hotspot RX/TX and TS1/TS2.
- `ywd-extended` is the recommended/default MMDVM runtime; `upstream` is the supported stock opt-out.
- Runtime choice/provenance persists across ordinary application updates.
- Stock and Extended binaries use separate compile-cache identities.
- Plugins may declare trusted MMDVM runtime/API/capability requirements but cannot switch the runtime themselves.
- RX Monitor uses trusted core DMR recovery/batching plus a separately installed YWD Vocoder Protocol v1 backend; the sandbox receives PCM only.
- The external vocoder is not bundled into core or the `.ywdplugin`.
- `/opt/ywd-hotspot/repo` is managed source; `/opt/ywd-hotspot/app` is deployed runtime.
- Credentials stay out of browser-readable state and public diagnostics.
- Executable service/UI plugins require trusted Ed25519 signatures.
- No current plugin gets independent modem ownership or RF TX authority.
- YWD-Hotspot OS keeps one authoritative OLED owner.
- RSSI is displayed only when modem firmware actually supplies a usable value; BER is never converted into fake dBm.
- Factory SSH is OFF; when enabled from the authenticated dashboard it is public-key-only and root/password SSH remain disabled.
- The original Pi Zero W remains the performance budget.
- Branch/ref identity and persistent update channel are distinct provenance fields.

## Public factory-image invariant

Public images contain **no operator preconfiguration**: no Wi-Fi, callsign/DMR ID, BM credentials/API key, dashboard password, imported settings, RF autostart, builder SSH authorized key, or reusable SSH server host identity. They boot into the setup AP/OLED-code onboarding flow.

## Useful commands

```bash
ywd-hotspotctl status
ywd-hotspotctl source
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py status
systemctl --failed --no-pager
```

Vocoder status when the external backend is installed:

```bash
sudo -u ywd-hotspot python3 /opt/ywd-hotspot/app/lib/vocoder_client.py status
systemctl show ywd-vocoder-mbelib.service -p Nice -p CPUWeight
```

Sanitized support bundle:

```bash
sudo ywd-hotspotctl diagnostics
```

Never post protected backups, raw credential files, SSH client/server private keys, signing private keys, `.ywdsettings` passphrases, or unsanitized appliance state.

Historical implementation notes and completed release plans live under `docs/history/` and are intentionally separated from current operating documentation.
