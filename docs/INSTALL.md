# 🚀 Installing YWD-Hotspot

[← Docs index](README.md) · [Project README](../README.md) · [SSH / SFTP](SSH.md) · [Building](BUILDING.md) · [Upgrading](UPGRADING.md) · [Security](../SECURITY.md)

---

> [!WARNING]
> YWD-Hotspot can control a radio transmitter. Attach a suitable antenna and verify the configured frequencies before enabling RF.

> [!IMPORTANT]
> `0.2.0-rc2` is the current public-testing release. Its exact factory image was physically tested on the reference Pi Zero W + duplex MMDVM appliance, and a published RC1 appliance successfully updated to RC2 through the normal dashboard updater before rebooting cleanly with zero failed systemd units.

## Recommended tester install: prebuilt factory image

The prerelease image is attached to:

**https://github.com/merberg-ai/ywd-hotspot/releases/tag/v0.2.0-rc2**

Current published image:

```text
ywd-hotspot-0.2.0-rc2.img.xz
SHA256 60f74d4c6d25d6a7d9ec35aea24b97bae7a50d35f103a21dc50ee1cbe80f1649
```

The release `.img.xz` is intentionally not personalized. It contains no:

- Wi-Fi credentials;
- operator callsign/DMR ID;
- BrandMeister Hotspot Security password;
- BrandMeister API key;
- dashboard password;
- imported YWD settings backup;
- builder SSH authorized key;
- reusable SSH server host identity;
- RF autostart state.

SSH and RF both ship disabled. Only application defaults and first-boot onboarding state are included. The public release builder refuses to create release metadata if forbidden personalization is detected.

### Flash

1. Download `ywd-hotspot-0.2.0-rc2.img.xz`, `SHA256SUMS`, and optionally `BUILD-METADATA.json` from the RC2 release.
2. Verify the SHA-256 checksum.
3. Write the `.img.xz` directly with Raspberry Pi Imager.
4. Do **not** apply Raspberry Pi Imager OS customization settings over the YWD appliance image.
5. Boot the Pi Zero W/Zero WH with the MMDVM HAT installed.

### First boot network setup

With no saved Wi-Fi profile, YWD-Hotspot creates a temporary open setup AP:

```text
SSID: YWD-Hotspot-XXXX
URL:  http://10.42.0.1/
RF:   OFF
SSH:  OFF
```

Join that AP, select/enter the hotspot's real Wi-Fi network, and save. The setup AP disappears while the Pi connects. If connection fails, the recovery AP returns automatically.

### First boot hotspot setup

After Wi-Fi connects:

1. reconnect your phone/computer to the normal LAN;
2. read the six-digit one-time setup code from the hotspot OLED;
3. browse to `https://<LAN-IP>:8443/`; `https://ywd-hotspot.local:8443/` is an optional mDNS convenience when supported;
4. enter the OLED code;
5. configure dashboard password, station identity, location, simplex/duplex RF settings, BrandMeister, OLED/appliance settings;
6. review and finish setup;
7. the wizard shows apply progress/errors inline and hands off to the configured dashboard on success.

If you choose **RESTORE FROM .YWDSETTINGS BACKUP** instead, the first-boot restore page now shows real upload progress for the encrypted backup, a busy spinner/status while the server decrypts and verifies it, and a second progress/status phase while the verified settings are uploaded and applied. The restore button remains disabled while the apply transaction is running so an impatient double-click cannot start a duplicate restore.

RF remains off unless explicitly enabled.

## SSH / SFTP after setup

The public YWD-Hotspot OS includes OpenSSH but intentionally leaves it disabled. There is **no default SSH password**.

Recommended sequence:

```text
Dashboard -> unlock controls
SYSTEM -> SSH ACCESS
CREATE & EXPORT CLIENT KEY   user: ywd
ENABLE SSH ACCESS
```

Then connect with the downloaded private key:

```bash
chmod 600 ywd_hotspot_client_ed25519
ssh -i ./ywd_hotspot_client_ed25519 ywd@HOTSPOT-IP
```

SFTP uses the same key/user/port 22. Password SSH and root SSH login remain disabled. The first time SSH is enabled, unique server host keys are generated on that appliance.

On the YWD-Hotspot OS image, `ywd` has passwordless sudo, so protect the client private key as an administrator credential.

Full Windows/Linux/macOS/SFTP/recovery instructions: **[SSH.md](SSH.md)**.

## Supported hardware baseline

| Component | Current baseline |
|---|---|
| Raspberry Pi | Original **Pi Zero W Rev 1.1** / Zero WH |
| OS | Raspberry Pi OS Lite 32-bit / Raspbian 13 (trixie) |
| HAT | MMDVM_HS/JumboSpot-style **simplex or duplex** board |
| UART | `/dev/serial0` at 115200 |
| Pi Zero mapping | `/dev/serial0 -> /dev/ttyAMA0` |
| OLED | I2C bus 1, normally `0x3C` |
| Network | BrandMeister DMR |

RSSI/dBm support depends on the MMDVM HAT firmware. Some otherwise compatible MMDVM_HS builds report BER but not RSSI. YWD-Hotspot does not synthesize dBm from BER and hides RSSI-only dashboard instrumentation when no usable RSSI is supplied.

## Fresh install from GitHub source

Source installation is still supported:

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

A normal Git clone preserves executable bits. If source came through a ZIP/Windows copy and modes were lost:

```bash
sudo bash ./INSTALL.sh
```

The source installer is interactive. Its configuration phase is deliberately kept attached directly to the controlling terminal rather than being piped through the installer's output colorizer. This keeps typed characters, `[default]` values and validation messages visible on SSH and local-console sessions. A required value with no usable default, such as a fresh Base DMR Radio ID, is shown as `[required]` rather than as a blank-looking prompt.

### SSH note for source-installed systems

The source installer does not turn a general-purpose Raspberry Pi into the exact YWD appliance user/SSH layout. It creates the restricted `ywd-hotspot` service account, but it does not create the appliance login user `ywd` or install OpenSSH solely for remote shell access.

The dashboard SSH helper can enroll a client key for an **existing** normal local Linux user (UID 1000+, interactive shell, home directly under `/home`). Enter that account name in the SSH client-key field. OpenSSH server must already be installed.

## MMDVM runtime choice

A fresh/full installation makes the MMDVM runtime explicit before compiling.

### 1. YWD Extended — recommended/default

- exact pinned upstream MMDVM-Host source;
- verified YWD extension patch;
- extension API and patch SHA recorded in provenance;
- passive DMR voice/RX Monitor capability;
- foundation for plugins that explicitly require YWD MMDVM capabilities.

### 2. Stock Upstream

- exact same pinned upstream MMDVM-Host source;
- no YWD MMDVM extension patch;
- extension-dependent plugins are unavailable;
- normal DMR hotspot operation remains supported.

Fresh installs default to **YWD Extended**. Recovery installs preserve the already-installed runtime choice by default. `YWD_MMDVM_VARIANT=ywd-extended` or `YWD_MMDVM_VARIANT=upstream` can be supplied for noninteractive/full installation workflows.

The selected state is recorded in:

```text
/etc/ywd-hotspot/mmdvm-runtime.json
/etc/ywd-hotspot/mmdvm-build.json
```

Stock and Extended MMDVM binaries have separate runtime cache identities; a stock build cannot consume a patched cache entry and vice versa.

Current YWD Extended identity:

```text
MMDVM-Host commit
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

Patch
  lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch

Extension API
  2

Patch SHA256
  f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a
```

See **[DMR-VOICE.md](DMR-VOICE.md)**.

## What a fresh source install does

1. validates the YWD-Hotspot candidate tree;
2. verifies Raspberry Pi/UART prerequisites;
3. performs a read-only MMDVM version probe;
4. installs application/radio dependencies;
5. creates the restricted service account;
6. asks/selects the MMDVM runtime variant;
7. builds/verifies the selected pinned MMDVM-Host runtime and pinned DMRGateway;
8. records runtime provenance/capabilities;
9. deploys `/opt/ywd-hotspot/app`;
10. installs systemd units, CLI and restricted privileged bridge;
11. records Git/version provenance;
12. creates/adopts the managed `/opt/ywd-hotspot/repo` checkout;
13. creates/migrates canonical configuration;
14. updates the DMR ID database when possible;
15. configures journaling;
16. starts non-RF side services;
17. asks for explicit RF-enable confirmation.

The original Pi Zero W is slow at compiling the radio stack. Normal application updates do **not** repeat the compile and do not change the selected MMDVM runtime.

## Existing install -> GitHub management

To adopt an existing appliance without rebuilding the RF stack:

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./MIGRATE-TO-GITHUB.sh
```

Migration preserves configuration, BrandMeister credentials, WebUI credential, calibration/history data, plugin state/data, RF active/enabled policy, and the installed MMDVM runtime. It does not recompile MMDVM-Host or DMRGateway.

## UART / modem preflight

```bash
cat /etc/os-release
uname -a
uname -m
ls -l /dev/serial0 2>/dev/null || true
readlink -f /dev/serial0 2>/dev/null || true
```

If `/dev/serial0` is missing or mapped incorrectly:

```bash
cd ~/ywd-hotspot
sudo ./lab/mmdvm-diag.sh
```

On the original Pi Zero W, expected mapping after the recommended UART setup/reboot is:

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

Supported radio modes:

```text
simplex
  one RF frequency

duplex
  separate hotspot RX/TX frequencies
  TS1 + TS2 operation
```

Older configuration migrates conservatively rather than silently changing mode.

## RF safety

Source installation, migration, update, restore, dashboard restart, plugin installation, SSH enable/disable, or MMDVM runtime selection is never permission to unexpectedly key the transmitter. RF start/enable remains explicit.

## WebUI / BrandMeister credentials

Set local dashboard write access:

```bash
sudo ywd-hotspotctl web-password
```

Set the separate BrandMeister API v2 key for TG controls:

```bash
sudo ywd-hotspotctl bm-api-key
```

These are separate from the BrandMeister Hotspot Security password.

## Verify installation

```bash
ywd-hotspotctl status
ywd-hotspotctl source
sudo python3 /opt/ywd-hotspot/app/lib/runtime_build.py status
systemctl --failed --no-pager
```

The runtime status reports the installed MMDVM variant/provenance plus DMRGateway identity.

## Open the dashboard

```bash
hostname -I
```

Browse to the configured WebUI port on the trusted LAN. Do not expose the plain-HTTP dashboard directly to the public Internet.

## Next steps

- **[SSH / SFTP](SSH.md)** — enable key-only remote administration and connect
- **[Building](BUILDING.md)** — source validation, runtime variants, personalized/public images
- **[OS Development](OS-DEVELOPMENT.md)** — appliance builder and factory release workflow
- **[Upgrading](UPGRADING.md)** — update channels, validation, rollback
- **[Backup / Restore](BACKUP-RESTORE.md)** — encrypted settings migration
- **[Talkgroups](TALKGROUPS.md)** — simplex/duplex BrandMeister controls
- **[Plugins](PLUGINS.md)** — plugin lifecycle/capability model
- **[Passive DMR Voice](DMR-VOICE.md)** — YWD Extended observation path
- **[Calibration](CALIBRATION.md)** — BER-driven RXOffset workflow
