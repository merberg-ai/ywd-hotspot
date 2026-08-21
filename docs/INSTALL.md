# 🚀 Installing YWD-Hotspot

[← Docs index](README.md) · [Project README](../README.md) · [Building](BUILDING.md) · [Upgrading](UPGRADING.md) · [Security](../SECURITY.md)

---

> [!WARNING]
> YWD-Hotspot can control a radio transmitter. Attach a suitable antenna and verify the configured frequencies before enabling RF.

> [!IMPORTANT]
> The current stable release is **0.1.0** on `main`. Normal users should install from the promoted `main` line; use development or checkpoint refs only when intentionally testing or recovering.

## Supported development baseline

Primary performance/test target:

| Component | Current baseline |
|---|---|
| Raspberry Pi | Original **Pi Zero W Rev 1.1** |
| OS | Raspberry Pi OS Lite 32-bit / Raspbian 13 (trixie) |
| HAT | MMDVM_HS/JumboSpot-style **simplex or duplex** board |
| UART | `/dev/serial0` at 115200 |
| Pi Zero mapping | `/dev/serial0 -> /dev/ttyAMA0` |
| OLED | I2C bus 1, normally `0x3C` |
| Network | BrandMeister DMR |

Useful preflight:

```bash
cat /etc/os-release
uname -a
uname -m
ls -l /dev/serial0 2>/dev/null || true
readlink -f /dev/serial0 2>/dev/null || true
```

## Fresh install from GitHub

### Stable release line (`main`)

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

### Development line

For intentionally testing the accepted development baseline instead of the stable release:

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone --branch dev https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

The completed `dev-release-0.1.0` RC branch is retained only as release history/rollback context; it is not the normal installation path for 0.1.0.

A normal Git clone preserves executable bits. If source came through a ZIP/Windows copy and modes were lost, invoke the installer through Bash:

```bash
sudo bash ./INSTALL.sh
```

## What a fresh install builds

A genuinely fresh install does the following:

1. validates the YWD-Hotspot candidate/source tree;
2. verifies Raspberry Pi/UART prerequisites;
3. performs a read-only MMDVM version probe;
4. installs build/runtime dependencies;
5. creates the restricted `ywd-hotspot` service account;
6. clones the exact MMDVM-Host and DMRGateway repositories from `pins.env`;
7. checks out their pinned commits;
8. compiles the normal radio stack conservatively for the Pi;
9. deploys YWD-Hotspot under `/opt/ywd-hotspot/app`;
10. installs systemd units, CLI, split privileged admin bridge, and restricted sudo policy;
11. records non-secret Git/version provenance;
12. creates/adopts the managed `/opt/ywd-hotspot/repo` checkout when appropriate;
13. creates/migrates canonical configuration;
14. updates or due-checks the DMR ID database;
15. configures persistent journaling when enabled;
16. starts lightweight side services and the authoritative OLED owner when applicable;
17. asks for explicit RF-enable confirmation.

The original Pi Zero W is not a compile monster. The first radio-stack build can take a while. **Normal YWD application updates do not repeat it.**

For more detail, including manual validation and image builds, see **[BUILDING.md](BUILDING.md)**.

## Optional patched MMDVM for RX Monitor

Normal hotspot operation uses the pinned upstream MMDVM-Host baseline. The optional **RX Monitor / passive DMR voice** path needs a small YWD patch that mirrors accepted DMR voice frames to a loopback-only observation topic while MMDVM-Host remains the only modem/RF owner.

Current pin:

```text
MMDVM-Host commit dea6e9b2c35857fe6f904c5092bebadb86cbf079
```

Patch:

```text
lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch
```

The patched binary is prepared separately from normal RF startup and ordinary app updates:

```bash
sudo systemctl start ywd-mmdvm-voice-build.service
sudo journalctl -fu ywd-mmdvm-voice-build.service
```

Status:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py status
```

On a Pi Zero this optional compile can take a long time. The service is intentionally low-priority and outside the RF-critical path. You do **not** need to manually trigger it just to run a normal DMR hotspot without RX Monitor/passive voice.

See **[BUILDING.md](BUILDING.md)** and **[DMR-VOICE.md](DMR-VOICE.md)**.

## Existing install → GitHub management

If `/etc/ywd-hotspot/config.json` and `/opt/ywd-hotspot/app` already exist, the migration path can adopt the existing appliance rather than recompiling the RF stack.

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./MIGRATE-TO-GITHUB.sh
```

Migration preserves canonical configuration, BrandMeister credentials, local WebUI control password, calibration/history/runtime data, plugin state/data, and current RF active/enabled policy. It does **not** rebuild MMDVM-Host or DMRGateway.

Migration adopts the promoted `main` line first. Opt into another development/ref only deliberately.

## UART / modem preflight

If `/dev/serial0` is missing or mapped incorrectly:

```bash
cd ~/ywd-hotspot
sudo ./lab/mmdvm-diag.sh
```

On the original Pi Zero W, the recommended UART configuration enables the PL011 UART, disables Bluetooth ownership of it, removes serial-console tokens, and requires a reboot. Wi-Fi is unaffected.

Expected after reboot:

```text
/dev/serial0 -> /dev/ttyAMA0
```

## Canonical radio configuration

Source of truth:

```text
/etc/ywd-hotspot/config.json
```

Generated outputs:

```text
/etc/ywd-hotspot/MMDVM-Host.ini
/etc/ywd-hotspot/DMRGateway.ini
```

Do **not** hand-maintain generated INI files.

Current radio configuration supports:

```text
simplex
  one RF frequency
  TS2 hotspot operation

duplex
  separate hotspot RX/TX frequencies
  TS1 + TS2 operation
```

Older configs migrate conservatively rather than silently switching radio mode.

## RF enable confirmation

Fresh install ends with an explicit RF-enable choice. Source installation, migration, update, restore, dashboard restart, or plugin installation is **never** permission to unexpectedly key the transmitter.

## WebUI write control

Configure the local control password:

```bash
sudo ywd-hotspotctl web-password
```

This is separate from BrandMeister credentials.

## BrandMeister API control

Static TG, saved-set, Drop Dynamic, and Drop QSO controls use a separate BrandMeister API v2 key:

```bash
sudo ywd-hotspotctl bm-api-key
```

The key remains server-side.

## Plugin publisher trust

Uploaded executable service/browser-UI plugins require a trusted Ed25519 publisher public key under:

```text
/etc/ywd-hotspot/plugin-trust.d/<key-id>.pem
```

Private signing keys belong on the development machine only and must never be copied to the hotspot.

See **[PLUGIN-PACKAGES.md](PLUGIN-PACKAGES.md)**.

## Verify installation

```bash
ywd-hotspotctl status
ywd-hotspotctl source
```

Core managed services include the RF stack plus dashboard/activity/update/RadioID services. Plugin, telemetry, passive voice, and OLED services are present/active according to installed feature set and operator configuration.

Useful local API sanity check:

```bash
curl -fsS http://127.0.0.1:8080/api/status | python3 -m json.tool | head -80
```

## Open the dashboard

```bash
hostname -I
```

Browse to the configured WebUI port on the hotspot's trusted LAN. Do not expose the plain-HTTP dashboard directly to the public Internet.

## Next steps

- **[Building](BUILDING.md)** — source validation, pinned RF builds, patched RX voice MMDVM, image builder
- **[Upgrading](UPGRADING.md)** — update channels, validation, rollback
- **[Talkgroups](TALKGROUPS.md)** — simplex/duplex BrandMeister controls
- **[Plugins](PLUGINS.md)** — plugin lifecycle/security model
- **[Passive DMR Voice](DMR-VOICE.md)** — optional RX observation path
- **[Calibration](CALIBRATION.md)** — BER-driven RXOffset workflow
