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
  <a href="docs/VOCODER.md">RX Vocoder</a> ·
  <a href="docs/UPGRADING.md">Updates</a>
</p>

---

> [!IMPORTANT]
> **Current public-testing release:** `0.2.0-rc2`. The exact RC2 source is `5f0d2967ce0ed728169f7819d2bc227687d6a9b2`. Its factory image passed a fresh flash/test, and a published RC1 appliance successfully updated to RC2 through the normal dashboard updater and rebooted with zero failed systemd units.

> [!WARNING]
> The normal YWD-Hotspot dashboard is plain HTTP for a trusted LAN. Do **not** forward the dashboard port directly to the public Internet.

## Recommended for testers: prebuilt image

The easiest way to test YWD-Hotspot is the prebuilt Raspberry Pi image attached to the `v0.2.0-rc2` GitHub prerelease:

**[YWD-Hotspot 0.2.0-rc2 release](https://github.com/merberg-ai/ywd-hotspot/releases/tag/v0.2.0-rc2)**

Published image:

```text
ywd-hotspot-0.2.0-rc2.img.xz
SHA256 60f74d4c6d25d6a7d9ec35aea24b97bae7a50d35f103a21dc50ee1cbe80f1649
```

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

Release assets include SHA-256 checksums, `BUILD-METADATA.json`, and `README-FIRST.txt` so the exact source/runtime identity can be audited.

## What YWD-Hotspot is

YWD-Hotspot is a purpose-built DMR hotspot stack for small Raspberry Pi systems—especially the original **Raspberry Pi Zero W**. MMDVM-Host remains the sole modem/RF owner while YWD-Hotspot adds a lightweight WebUI, CLI, BrandMeister controls, diagnostics, calibration, OLED presentation, passive telemetry/voice observation, safe GitHub-managed updates, RadioID maintenance, appliance-image tooling, and a sandboxed plugin framework.

The design rule is simple: **the Pi owns radio plus bounded trusted processing; optional expensive work must be isolated, demand-driven, and unable to take down RF.** Browser presentation stays client-side, while Phase 3J RX speech synthesis is delegated through a narrow local protocol to a separately installed external vocoder backend. Dashboard, OLED, telemetry, plugin, or decoder failures must not take down normal DMR operation.

| Area | YWD-Hotspot adds |
|---|---|
| RF | simplex or duplex, TS1/TS2-aware config, live RX/TX state, Last Heard, BER and optional modem-reported RSSI context |
| BrandMeister | static/dynamic TG controls, duplex-aware slot routing, Drop QSO, saved TG sets |
| WebUI | responsive dark UI, authenticated write controls, live DMR instrumentation, themed confirmation/progress dialogs |
| OLED | one authoritative renderer with boot/network/setup/runtime presentation |
| Plugins | signed sandboxed UI/service packages with explicit capabilities and transactional updates |
| RX Monitor | passive DMR diagnostics plus trusted streamed PCM audio through a separately installed local vocoder backend; the sandbox receives PCM only |
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
> RSSI/dBm reporting is optional at the MMDVM HAT firmware layer. YWD displays RSSI only when the modem supplies a usable value; it does not estimate dBm from BER. The reference duplex HAT used for RC1/RC2 testing reported valid BER but no usable RSSI, so the WebUI automatically hides RSSI-only instrumentation on that hardware.

## MMDVM runtime variants

The accepted RC1/RC2 line supports an explicit MMDVM runtime choice:

| Variant | Default | Description |
|---|---:|---|
| **YWD Extended** (`ywd-extended`) | ✅ | exact pinned upstream MMDVM-Host plus the hash-verified YWD extension patch; enables passive DMR voice/RX Monitor and compatible plugin capabilities |
| **Stock Upstream** (`upstream`) |  | exact pinned stock upstream with no YWD MMDVM extensions; extension-dependent plugins remain unavailable |

Fresh/full GitHub installs display this choice before compiling. **YWD Extended is recommended and selected by default.** Recovery installs preserve the already-installed variant unless the operator explicitly changes it. Normal application updates do not silently switch variants.

Pinned YWD Extended identity:

```text
MMDVM-Host upstream
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

YWD extension patch
  lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch

Extension API
  2

Patch SHA256
  f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a

DMRGateway
  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

MMDVM-Host remains the sole modem serial/RF owner in both variants. Plugins never receive RF TX authority.

Details: **[Passive DMR Voice](docs/DMR-VOICE.md)** · **[External Vocoder](docs/VOCODER.md)** · **[Plugins](docs/PLUGINS.md)**

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

> [!NOTE]
> RX Monitor live speech on the active `dev-plugins` line additionally requires a separately installed YWD Vocoder Protocol v1 backend. Core/plugin packages do not bundle mbelib. See **[docs/VOCODER.md](docs/VOCODER.md)** for the quick setup and verification flow.

## Building images

Normal personalized/development image build:

```bash
bash os/builder/DOCTOR.sh
bash os/builder/RUN-BUILD.sh
```

Public release image builds use the separate fail-closed wrapper:

```bash
bash os/builder/BUILD-PUBLIC-RELEASE.sh
```

See **[docs/BUILDING.md](docs/BUILDING.md)** and **[docs/OS-DEVELOPMENT.md](docs/OS-DEVELOPMENT.md)**.

## Updating

Managed installs separate source from deployed runtime:

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

`0.2.0-rc2` was successfully installed over a published RC1 appliance using the normal dashboard updater path.

See **[docs/UPGRADING.md](docs/UPGRADING.md)**.

## Branch / release model

| Ref | Purpose |
|---|---|
| `main` | frozen public/update line at accepted RC2 while releases are frozen |
| `dev` | active integrated development and repository housekeeping |
| `dev-plugins` | specialized plugin/framework development and current Phase 3J RX Monitor integration |
| `v0.2.0-rc2` | immutable updater-proven RC2 tag |
| `release/0.2.0-rc2` | frozen RC2 source branch |
| `checkpoint-release-0.2.0-rc2-image-updater-proven` | exact source checkpoint for RC2 image/update acceptance |
| `v0.2.0-rc1` | immutable physically tested RC1 tag |
| `release/0.2.0-rc1` | frozen RC1 source branch |
| `checkpoint-release-0.2.0-rc1-image-proven` | exact source checkpoint for RC1 image acceptance |
| `checkpoint-builder-0.1.0-image-boot-proven` | earlier immutable builder/appliance baseline |
| `checkpoint-dev-plugins-phase3j-stream-core-proven` | cleaned physically proven Phase 3J core baseline |

Historical release evidence is not rewritten. While releases are frozen, ordinary cleanup/development stays on `dev` so `main`-channel appliances do not see unpublished work as an available update.

See **[docs/REPOSITORY.md](docs/REPOSITORY.md)**.

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
- a plugin requiring YWD Extended capabilities is blocked cleanly on Stock Upstream rather than failing mysteriously;
- RX Monitor live audio uses trusted core recovery/batching and a separately installed local vocoder; the sandbox never receives decoder ownership.

Guides: **[Plugins](docs/PLUGINS.md)** · **[Plugin Packages](docs/PLUGIN-PACKAGES.md)** · **[Plugin UI](docs/PLUGIN-UI.md)** · **[External Vocoder](docs/VOCODER.md)**

## Documentation

Start with **[docs/README.md](docs/README.md)**.

Current operating/development guides stay directly under `docs/`. Completed release plans and Alpha implementation archaeology are kept under **[docs/history/](docs/history/README.md)** so historical state is preserved without being mistaken for current instructions.
