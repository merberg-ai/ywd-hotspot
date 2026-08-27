# 📚 YWD-Hotspot Documentation

[← Back to project README](../README.md)

> [!IMPORTANT]
> `0.2.0-rc3` is the current physically accepted public-testing release. The exact accepted source is tag `v0.2.0-rc3` at commit `3823140b9fd4d6e73fe9066af4b2280628f62f5e`. The exact published factory image passed fresh-flash acceptance, and the published RC2 -> RC3 application updater path also passed.

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
| 🧪 Review RC3 release details | **[0.2.0-rc3 Release Notes](RELEASE-NOTES-0.2.0-rc3.md)** |
| ✅ Review final RC3 image/publication evidence | **[RC3 Factory Image / Publication Pass](history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md)** |
| 🧪 Review accepted RC2 release notes | **[0.2.0-rc2 Release Notes](RELEASE-NOTES-0.2.0-rc2.md)** |
| 📦 Review RC1 release notes | **[0.2.0-rc1 Release Notes](RELEASE-NOTES-0.2.0-rc1.md)** |
| 🗄️ Browse completed plans / Alpha archaeology | **[Historical Documentation](history/README.md)** |
| 🔐 Review security/exposure rules | **[Security](../SECURITY.md)** |
| 🗒️ Review release history | **[Changelog](../CHANGELOG.md)** |

## Current accepted public release

```text
Version
  0.2.0-rc3

Tag / accepted source
  v0.2.0-rc3
  3823140b9fd4d6e73fe9066af4b2280628f62f5e

Published image
  ywd-hotspot-0.2.0-rc3.img.xz

Image SHA256
  5c3151b2a39f5a800b703d8925c53cddcf7bf49d8fcb59eda6bed30afc4413cc

Acceptance
  final fresh-image boot/test PASS
  published RC2 -> RC3 updater PASS
  duplex TS1/TS2 Parrot PASS
  first-run setup / dashboard PASS
  MODEM/MMDVM card + software-channel UI PASS
  reboot persistence PASS
  failed systemd units: 0
```

Release page:

https://github.com/merberg-ai/ywd-hotspot/releases/tag/v0.2.0-rc3

The published image is the exact tested compressed artifact. Renaming for the public GitHub-facing filename did not change its bytes; the SHA-256 was reverified before publication and matches GitHub's uploaded asset digest.

## Current RC3 runtime identity

```text
MMDVM-Host upstream
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

YWD Extended patch SHA256
  77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994

Extension API
  2

Current capabilities
  slot_affinity_queued_work
  dmr_pdu_route_metadata
  dmr_rx_audio_events

DMRGateway upstream
  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

RC1/RC2 YWD Extended remains recognized as a legacy-compatible runtime and is never silently rebuilt by an ordinary application update. See [Upgrading](UPGRADING.md).

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

## Current repository refs

| Ref | Purpose |
|---|---|
| `main` | public/update line carrying RC3 code plus post-release documentation |
| `dev` | active integrated development; aligned with `main` immediately after the RC3 documentation refresh |
| `dev-plugins` | isolated plugin/framework experiment line; may intentionally diverge |
| `v0.2.0-rc3` | immutable accepted RC3 tag at `3823140b9fd4d6e73fe9066af4b2280628f62f5e` |
| `release/0.2.0-rc3` | frozen exact RC3 source branch |
| `checkpoint-release-0.2.0-rc3-final-ui-wiring-proven-pre-image` | immutable final RC3 pre-image checkpoint |
| `v0.2.0-rc2` | immutable updater-proven RC2 tag |
| `release/0.2.0-rc2` | frozen RC2 source branch |
| `checkpoint-release-0.2.0-rc2-image-updater-proven` | exact source checkpoint for accepted RC2 image/updater test |
| `v0.2.0-rc1` | immutable physically tested RC1 tag |
| `release/0.2.0-rc1` | frozen RC1 source branch |
| `checkpoint-release-0.2.0-rc1-image-proven` | exact source checkpoint for accepted RC1 image |

Release tags/branches/checkpoints remain immutable historical evidence even when `main`/`dev` later receive documentation or new development commits.

See [Repository Policy](REPOSITORY.md) for the branch/ref rules.

## Useful commands

```bash
ywd-hotspotctl status
ywd-hotspotctl source
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py status
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_runtime_state.py status
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
