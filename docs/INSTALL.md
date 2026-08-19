# 🚀 Installing YWD-Hotspot

[← Docs index](README.md) · [Project README](../README.md) · [Upgrading](UPGRADING.md) · [Security](../SECURITY.md)

---

> [!WARNING]
> YWD-Hotspot can control a radio transmitter. Attach a suitable antenna and verify the configured frequencies before enabling RF.

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

## Fresh install

### Promoted `main`

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

### Tested development `dev`

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone --branch dev https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

### Next-development `dev-plugins`

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone --branch dev-plugins https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

A normal Git clone preserves executable bits. If source came through a ZIP/Windows copy and modes were lost, invoking the script through Bash is sufficient:

```bash
sudo bash ./INSTALL.sh
```

## Existing install → GitHub management

If `/etc/ywd-hotspot/config.json` and `/opt/ywd-hotspot/app` already exist, the installer can adopt the existing appliance rather than recompiling the RF stack.

Direct migration:

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./MIGRATE-TO-GITHUB.sh
```

Migration preserves canonical configuration, BrandMeister credentials, local WebUI control password, calibration/history/runtime data, plugin state/data, and current RF active/enabled policy. It does **not** rebuild MMDVM-Host or DMRGateway.

Migration adopts the promoted `main` line first. Opt into `dev` afterward only if desired:

```bash
sudo ywd-hotspotctl update --branch dev
```

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

## Source validation before install

Current source runs the same capability-coherence checks used by the updater. If the tree contains the plugin UI/package runtime, passive voice runtime, or MMDVM telemetry runtime, the matching companion files must also be present. Python/shell source is syntax-checked before the installer proceeds to hardware/build/service work.

This protects fresh installs from an incomplete promoted branch just as the managed updater protects existing appliances.

## What a genuinely fresh install does

1. verifies Raspberry Pi/UART prerequisites;
2. performs a read-only MMDVM version probe;
3. installs build/runtime dependencies;
4. creates the restricted `ywd-hotspot` service account;
5. clones the pinned MMDVM-Host and DMRGateway sources;
6. checks out the exact commits from `pins.env`;
7. compiles both with `make -j1`;
8. deploys YWD-Hotspot under `/opt/ywd-hotspot/app`;
9. installs systemd units, CLI, admin helper, and restricted sudo rules;
10. writes non-secret build provenance;
11. creates/adopts the managed `/opt/ywd-hotspot/repo` checkout when appropriate;
12. creates/migrates canonical configuration;
13. updates the DMR ID database when possible;
14. configures persistent journaling when enabled;
15. starts lightweight side services;
16. starts OLED only when configured/detected;
17. asks for explicit RF-enable confirmation.

The original Pi Zero W is not a compile monster. The first upstream build can take a while. Normal application updates do not repeat it.

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

The WebUI/CLI configuration layer generates matching MMDVM-Host and DMRGateway settings. Existing older configs migrate conservatively rather than silently switching radio mode.

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

Core managed services include the RF stack plus dashboard/activity/update/RadioID services. Plugin, telemetry, passive voice, and OLED services are present/active according to the installed feature set and operator configuration.

## Open the dashboard

```bash
hostname -I
```

Browse to the configured WebUI port on the hotspot's trusted LAN. Do not expose the plain-HTTP dashboard directly to the public Internet.

## Next steps

- **[Upgrading](UPGRADING.md)** — update channels, validation, rollback
- **[Talkgroups](TALKGROUPS.md)** — simplex/duplex BrandMeister controls
- **[Plugins](PLUGINS.md)** — plugin lifecycle/security model
- **[Passive DMR Voice](DMR-VOICE.md)** — optional RX observation path
- **[Calibration](CALIBRATION.md)** — BER-driven RXOffset workflow
