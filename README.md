<p align="center">
  <img src="assets/branding/ywd-hotspot-banner-webui.webp" alt="YWD-Hotspot" width="720">
</p>

<h1 align="center">YWD-Hotspot</h1>
<p align="center"><strong>Lightweight DMR hotspot software and appliance tooling for Raspberry Pi + MMDVM HAT hardware.</strong></p>
<p align="center">📡 DMR · 🎛️ BrandMeister · 🥧 Pi Zero W · 📟 OLED · 🧩 Plugins · 🎧 RX Monitor · 🔄 Safe updates</p>

<p align="center">
  <a href="#recommended-for-testers-prebuilt-image">Download / Flash</a> ·
  <a href="docs/INSTALL.md">Install</a> ·
  <a href="docs/SSH.md">SSH</a> ·
  <a href="docs/BUILDING.md">Build</a> ·
  <a href="docs/README.md">Docs</a> ·
  <a href="docs/UPGRADING.md">Updates</a>
</p>

---

> [!IMPORTANT]
> **Current public-testing release:** `0.2.0-rc1`. The exact public factory image was built from commit `1575344d732994a7b54d5afc7f15a88040a274ec`, flashed to the reference Pi Zero W + duplex MMDVM appliance, and physically accepted before promotion/tagging.

> [!WARNING]
> The normal YWD-Hotspot dashboard is plain HTTP for a trusted LAN. Do **not** forward the dashboard port directly to the public Internet.

## Recommended for testers: prebuilt image

The easiest way to test YWD-Hotspot is the prebuilt Raspberry Pi image attached to the `v0.2.0-rc1` GitHub prerelease:

**[YWD-Hotspot 0.2.0-rc1 release](https://github.com/merberg-ai/ywd-hotspot/releases/tag/v0.2.0-rc1)**

The downloadable release image is deliberately a **factory image**. It contains:

- no Wi-Fi SSID or password;
- no callsign, DMR ID, or hotspot ID belonging to the builder;
- no BrandMeister Hotspot Security password;
- no BrandMeister API key;
- no dashboard/control password;
- no imported settings backup;
- no builder SSH authorized key or reusable SSH server identity;
- SSH disabled on first boot;
- RF disabled on first boot;
- only YWD-Hotspot application defaults and first-boot onboarding state.

The public release builder fails closed if forbidden personalization is present.

### First boot

1. Flash the `.img.xz` directly with Raspberry Pi Imager.
2. Do **not** apply Raspberry Pi Imager OS customization settings over the appliance image.
3. Boot the Pi Zero W/Zero WH with the MMDVM HAT installed.
4. Join the temporary `YWD-Hotspot-XXXX` Wi-Fi network.
5. Browse to `http://10.42.0.1/` and configure Wi-Fi.
6. Reconnect your phone/computer to the normal LAN.
7. Read the six-digit one-time setup code from the hotspot OLED.
8. Browse to `https://<LAN-IP>:8443/` and complete hotspot setup. `https://ywd-hotspot.local:8443/` is an optional mDNS convenience when supported by the client network.
9. The wizard hands off to the configured dashboard when setup succeeds.
10. RF stays off unless you explicitly enable it.

Release assets include SHA-256 checksums, `BUILD-METADATA.json`, and `README-FIRST.txt` so the exact source/runtime identity of the image can be audited.

## Optional SSH / SFTP access

The public image includes OpenSSH but ships with **SSH disabled and port 22 closed**. There is no default SSH password.

Recommended setup after first-boot configuration:

```text
unlock dashboard controls
  -> SYSTEM
  -> SSH ACCESS
  -> CREATE & EXPORT CLIENT KEY (user ywd)
  -> ENABLE SSH ACCESS
  -> ssh -i <private-key> ywd@<hotspot-ip>
```

YWD enforces public-key-only authentication, disables SSH passwords/root login, and generates unique server host keys on the appliance the first time SSH is enabled. The downloaded client private key is not retained by the hotspot.

On YWD-Hotspot OS, `ywd` has passwordless sudo, so its SSH client key is effectively an administrator credential. Keep it private and prefer LAN/VPN access rather than directly forwarding port 22 to the Internet.

Full instructions: **[docs/SSH.md](docs/SSH.md)**.

## What YWD-Hotspot is

YWD-Hotspot is a purpose-built DMR hotspot stack for small Raspberry Pi systems—especially the original **Raspberry Pi Zero W**. MMDVM-Host remains the sole modem/RF owner while YWD-Hotspot adds a lightweight WebUI, CLI, BrandMeister controls, diagnostics, calibration, OLED presentation, passive telemetry/voice observation, safe GitHub-managed updates, RadioID maintenance, an appliance-image builder, and a sandboxed plugin framework.

The design rule is simple: **the Pi does radio and small trusted state collection; the browser does the expensive presentation work.** Dashboard, OLED, telemetry, or plugin failures must not take down normal DMR operation.

| Area | YWD-Hotspot adds |
|---|---|
| RF | simplex or duplex, TS1/TS2-aware config, live RX/TX state, Last Heard, BER and optional modem-reported RSSI context |
| BrandMeister | static/dynamic TG controls, duplex-aware slot routing, Drop QSO, saved TG sets |
| WebUI | responsive dark UI, authenticated write controls, live DMR instrumentation, themed confirmation/progress dialogs |
| OLED | one authoritative renderer with boot/network/setup/runtime presentation |
| Plugins | signed sandboxed UI/service packages with explicit capabilities and transactional updates |
| RX Monitor | passive browser-side DMR receive decoding through a narrow core capability |
| Calibration | baseline save/restore and BER-driven RXOffset workflow |
| Health | service, Wi-Fi, temperature, journal, diagnostics and support tools |
| Updates | staged validation, protected backup, plugin-state preservation and rollback attempt |
| OS | reproducible Raspberry Pi OS image builder from the same source tree |

No Node.js runtime, React/Vue, SQL server, Redis, or Docker is required on the hotspot.

## Hardware target

Primary development/test budget:

- original Raspberry Pi Zero W / Zero WH;
- Raspberry Pi OS Lite 32-bit / Raspbian 13 (trixie);
- MMDVM_HS/JumboSpot-style HAT, including tested simplex and duplex configurations;
- `/dev/serial0` at 115200 baud;
- optional SSD1306-compatible 128×64 I2C OLED at `0x3C`;
- BrandMeister DMR.

Other Pi models may work, but the original Zero W remains the performance target.

> [!NOTE]
> RSSI/dBm reporting is optional at the MMDVM HAT firmware layer. YWD displays RSSI only when the modem supplies a usable value; it does not estimate dBm from BER. The reference duplex HAT used for RC1 testing reported valid BER but no usable RSSI, so the WebUI automatically hides RSSI-only instrumentation on that hardware.

## MMDVM runtime variants

`0.2.0-rc1` makes the YWD MMDVM extension an explicit supported runtime choice instead of an invisible build detail.

| Variant | Default | Description |
|---|---:|---|
| **YWD Extended** (`ywd-extended`) | ✅ | exact pinned upstream MMDVM-Host plus the hash-verified YWD extension patch; enables passive DMR voice/RX Monitor and capabilities future compatible plugins may require |
| **Stock Upstream** (`upstream`) |  | exact pinned upstream MMDVM-Host with no YWD MMDVM extensions; extension-dependent plugins remain unavailable |

Fresh/full GitHub installs display this choice before compiling. **YWD Extended is recommended and selected by default.** Recovery installs preserve the already-installed variant unless the operator explicitly changes it. Normal application updates do not silently switch variants.

Runtime state/provenance is stored on the appliance and includes the upstream commit, binary identity, variant, extension API/hash when applicable, and advertised capabilities. Stock and Extended builds use separate compile-cache identities.

Pinned YWD Extended patch identity:

```text
MMDVM-Host upstream
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

YWD extension patch
  lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch

Extension API
  2

Patch SHA256
  f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a
```

MMDVM-Host remains the sole modem serial/RF owner in both variants. Plugins never receive RF TX authority.

Details: **[docs/DMR-VOICE.md](docs/DMR-VOICE.md)** and **[docs/PLUGINS.md](docs/PLUGINS.md)**.

## Fresh install from GitHub

Source installation remains supported:

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

The installer validates hardware/source, asks which MMDVM runtime variant to build, installs the exact pinned radio components, deploys YWD-Hotspot, and leaves RF startup behind an explicit confirmation.

Full walkthrough: **[docs/INSTALL.md](docs/INSTALL.md)**.

## Building images

Normal personalized/development image build:

```bash
bash os/builder/DOCTOR.sh
bash os/builder/RUN-BUILD.sh
```

Choose the builder MMDVM runtime:

```bash
python3 os/builder/MMDVM-RUNTIME.py review
python3 os/builder/MMDVM-RUNTIME.py set ywd-extended
python3 os/builder/MMDVM-RUNTIME.py set upstream
```

Public release image builds use a separate fail-closed wrapper:

```bash
bash os/builder/BUILD-PUBLIC-RELEASE.sh
```

That wrapper temporarily replaces the private local builder profile with factory defaults, disables SSH, selects the default YWD Extended runtime, verifies no personalization is staged, builds the image, verifies the generated profile again, creates release provenance files, then restores the developer's original local builder settings.

See **[docs/BUILDING.md](docs/BUILDING.md)** and **[docs/OS-DEVELOPMENT.md](docs/OS-DEVELOPMENT.md)**.

## Updating

Managed installs separate source from the deployed runtime:

```text
/opt/ywd-hotspot/repo    root-owned managed Git checkout
/opt/ywd-hotspot/app     deployed runtime copy; no .git directory
```

CLI:

```bash
sudo ywd-hotspotctl update --check
sudo ywd-hotspotctl update --dry-run
sudo ywd-hotspotctl update
```

The updater stages and validates the complete candidate before touching the live stack, preserves RF/service policy, creates protected backups, keeps the privileged admin bridge coherent, quiesces/restores plugin intent, and advances managed source only after successful deployment.

Normal application updates do **not** rebuild MMDVM-Host or DMRGateway and do not change the selected MMDVM runtime variant.

See **[docs/UPGRADING.md](docs/UPGRADING.md)**.

## Branch / release model

| Ref | Purpose |
|---|---|
| `main` | current promoted public line; may receive documentation-only follow-up commits after a tagged release |
| `dev` | accepted integrated development baseline |
| `v0.2.0-rc1` | immutable tag for the physically tested RC1 source |
| `release/0.2.0-rc1` | frozen RC1 source/hardening branch |
| `checkpoint-release-0.2.0-rc1-image-proven` | exact source checkpoint for the physically tested public RC1 image |
| `checkpoint-builder-0.1.0-image-boot-proven` | earlier immutable known-good builder/appliance baseline |

Historical `checkpoint-*` refs and release tags are evidence of what was actually tested and are not rewritten.

See **[docs/REPOSITORY.md](docs/REPOSITORY.md)** and **[docs/GITHUB-SETUP.md](docs/GITHUB-SETUP.md)**.

## Plugin safety model

The plugin subsystem is optional. Master OFF must return the appliance to normal YWD-Hotspot behavior.

Rules include:

- upload verifies/reviews a package before installation;
- install and enable are separate operator decisions;
- executable service/browser-UI plugins require trusted Ed25519 signatures;
- service plugins use a restrictive shared systemd sandbox;
- UI plugins use an isolated iframe with a narrow trusted bridge;
- plugins get no arbitrary sudo, RF serial ownership, broad device access, RF TX authority, or independent MMDVM instance;
- plugin state/config/data remains separate from canonical hotspot configuration;
- plugins may declare required MMDVM extension API/capabilities;
- a plugin requiring YWD Extended capabilities is blocked cleanly on Stock Upstream rather than failing mysteriously.

Guides: **[Plugins](docs/PLUGINS.md)** · **[Plugin Packages](docs/PLUGIN-PACKAGES.md)** · **[Plugin UI](docs/PLUGIN-UI.md)**

## Security

YWD-Hotspot deliberately separates BrandMeister credentials, the local WebUI control password, plugin publisher trust, and system access. Secrets stay server-side and out of browser-readable state and sanitized diagnostics.

The public factory image contains no operator credentials and ships SSH disabled with no builder authorized key or reusable server host key embedded. SSH can later be enabled from the authenticated **SYSTEM -> SSH ACCESS** card and remains public-key-only.

Read **[SECURITY.md](SECURITY.md)** and **[docs/SSH.md](docs/SSH.md)** before exposing or sharing anything from a real appliance.

## Pinned RF components

```text
MMDVM-Host
  repo   https://github.com/g4klx/MMDVM-Host.git
  commit dea6e9b2c35857fe6f904c5092bebadb86cbf079

DMRGateway
  repo   https://github.com/g4klx/DMRGateway.git
  commit 2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

A radio pin or extension-patch identity change alters the tested RF/runtime baseline and requires its own physical regression pass.

## Documentation

| Guide | Purpose |
|---|---|
| [Documentation index](docs/README.md) | find the right guide |
| [Installation](docs/INSTALL.md) | prebuilt image, source install, migration |
| [SSH / SFTP](docs/SSH.md) | dashboard enablement, client keys, connection and recovery |
| [Building](docs/BUILDING.md) | source validation, runtime variants, appliance/public image builds |
| [Upgrading](docs/UPGRADING.md) | channels, validation, rollback/recovery |
| [Architecture](docs/ARCHITECTURE.md) | RF/runtime boundaries and side services |
| [Display](docs/DISPLAY.md) | WebUI instrumentation and OLED |
| [Plugins](docs/PLUGINS.md) | plugin architecture, capabilities and safety boundaries |
| [Passive DMR Voice](docs/DMR-VOICE.md) | YWD Extended voice tap and RX bridge |
| [Telemetry](docs/TELEMETRY.md) | local MMDVM telemetry path |
| [Talkgroups](docs/TALKGROUPS.md) | BrandMeister Talkgroup Manager |
| [Calibration](docs/CALIBRATION.md) | BER-driven RX workflow |
| [Backup / Restore](docs/BACKUP-RESTORE.md) | encrypted settings migration |
| [Repository Policy](docs/REPOSITORY.md) | branch/checkpoint/release policy |
| [Development](docs/GITHUB-SETUP.md) | clone, validation and source workflow |
| [OS Development](docs/OS-DEVELOPMENT.md) | image builder and public factory releases |
| [Security](SECURITY.md) | credentials and exposure rules |

## Project

Written by **KJ6YWD**. Project home: **https://kj6ywd.net**  
Canonical repository: **https://github.com/merberg-ai/ywd-hotspot**

## License

YWD-Hotspot is released under the **[Unlicense](LICENSE)** / public-domain dedication included in this repository.
