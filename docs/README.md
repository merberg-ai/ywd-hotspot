# 📚 YWD-Hotspot Documentation

[← Back to project README](../README.md)

> [!IMPORTANT]
> `0.2.0-rc2` is the current physically accepted public-testing release. It was validated both as a freshly flashed factory image and through an in-place `0.2.0-rc1 -> 0.2.0-rc2` dashboard update, followed by a clean reboot with zero failed systemd units. RC3 is in final pre-image acceptance and is not public until the exact factory artifact passes.

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
| 🌿 Understand branches/checkpoints/releases | **[Repository Policy](REPOSITORY.md)** |
| 🧰 Develop safely | **[GitHub / Development](GITHUB-SETUP.md)** |
| 🧪 Review the RC3 candidate/release notes | **[0.2.0-rc3 Release Notes](RELEASE-NOTES-0.2.0-rc3.md)** |
| 🧪 Review the accepted RC2 release | **[0.2.0-rc2 Release Notes](RELEASE-NOTES-0.2.0-rc2.md)** |
| 📦 Review RC1 release notes | **[0.2.0-rc1 Release Notes](RELEASE-NOTES-0.2.0-rc1.md)** |
| 🗄️ Browse completed plans / Alpha archaeology | **[Historical Documentation](history/README.md)** |
| 🔐 Review security/exposure rules | **[Security](../SECURITY.md)** |
| 🗒️ Review release history | **[Changelog](../CHANGELOG.md)** |

## Current accepted public release

```text
Version
  0.2.0-rc2

Tag / source
  v0.2.0-rc2
  5f0d2967ce0ed728169f7819d2bc227687d6a9b2

Image SHA256
  60f74d4c6d25d6a7d9ec35aea24b97bae7a50d35f103a21dc50ee1cbe80f1649

Acceptance
  fresh-image boot/test PASS
  RC1 -> RC2 dashboard updater PASS
  post-update reboot PASS
  failed systemd units: 0
```

The published image is the exact tested compressed artifact; its GitHub-facing filename is `ywd-hotspot-0.2.0-rc2.img.xz`.

## Core operating rules

- RF does not start merely because install/update/restore/plugin/SSH work happened.
- `/etc/ywd-hotspot/config.json` is canonical; generated MMDVM/DMRGateway INIs are outputs.
- MMDVM-Host remains the only modem/RF owner.
- Simplex/duplex are explicit; duplex has separate hotspot RX/TX and TS1/TS2.
- `ywd-extended` is the recommended/default MMDVM runtime; `upstream` is the supported stock opt-out.
- Runtime choice/provenance persists across ordinary application updates.
- Stock and Extended binaries use separate compile-cache identities.
- Plugins may declare trusted MMDVM runtime/API/capability requirements but cannot switch the runtime themselves.
- RX Monitor Phase 3J uses trusted core DMR recovery/batching plus a separately installed YWD Vocoder Protocol v1 backend; the sandbox receives PCM only.
- The external vocoder is not bundled into core or the `.ywdplugin`; current `dev` enforces the selected `Nice=0` / `CPUWeight=200` policy for the known external service.
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

## Current repository refs

| Ref | Purpose |
|---|---|
| `main` | frozen public/update line at accepted RC2 while releases are frozen |
| `dev` | active integrated development and RC3 preparation; includes the proven Phase 3J plugin/RX/vocoder work |
| `dev-plugins` | isolated plugin/framework experiment line; currently aligned with `dev` |
| `v0.2.0-rc2` | immutable updater-proven RC2 tag |
| `release/0.2.0-rc2` | frozen RC2 source branch |
| `checkpoint-release-0.2.0-rc2-image-updater-proven` | exact source checkpoint for accepted RC2 image/updater test |
| `v0.2.0-rc1` | immutable physically tested RC1 tag |
| `release/0.2.0-rc1` | frozen RC1 source branch |
| `checkpoint-release-0.2.0-rc1-image-proven` | exact source checkpoint for accepted RC1 image |
| `checkpoint-builder-0.1.0-image-boot-proven` | earlier immutable builder/appliance baseline |
| `checkpoint-dev-plugins-phase3j-stream-core-proven` | cleaned physically proven Phase 3J core baseline |

See [Repository Policy](REPOSITORY.md) for the branch/ref rules.

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
