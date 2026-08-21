<p align="center">
  <img src="assets/branding/ywd-hotspot-banner-webui.webp" alt="YWD-Hotspot" width="720">
</p>

<h1 align="center">YWD-Hotspot</h1>
<p align="center"><strong>Lightweight DMR hotspot software and appliance tooling for Raspberry Pi + MMDVM HAT hardware.</strong></p>
<p align="center">📡 DMR · 🎛️ BrandMeister · 🥧 Pi Zero W · 📟 OLED · 🧩 Plugins · 🎧 RX Monitor · 🔄 Safe updates</p>

<p align="center">
  <a href="#quick-start">Install</a> ·
  <a href="docs/BUILDING.md">Build</a> ·
  <a href="docs/README.md">Docs</a> ·
  <a href="docs/UPGRADING.md">Updates</a> ·
  <a href="SECURITY.md">Security</a>
</p>

---

> [!IMPORTANT]
> **Release status:** `0.1.0` is the first stable YWD-Hotspot release. The release candidate was physically acceptance-tested on the target Pi Zero W + duplex MMDVM hardware before promotion through `dev` to `main`. The exact installed build is always defined by [`VERSION`](VERSION) plus the Git branch/ref and commit shown by `ywd-hotspotctl source` and the About page.

> [!WARNING]
> The built-in WebUI is plain HTTP for a trusted LAN. Do **not** forward the dashboard port directly to the public Internet.

## What YWD-Hotspot is

YWD-Hotspot is a purpose-built DMR hotspot stack for small Raspberry Pi systems—especially the original **Raspberry Pi Zero W**. The RF path stays on pinned upstream **MMDVM-Host** and **DMRGateway**, while YWD-Hotspot adds a lightweight WebUI, CLI, BrandMeister controls, diagnostics, calibration, OLED presentation, passive telemetry/voice observation, safe GitHub-managed updates, RadioID maintenance, and a sandboxed plugin framework.

The design rule is simple: **the Pi does radio and small trusted state collection; the browser does the expensive presentation work.** Dashboard, OLED, telemetry, or plugin failures must not take down normal DMR operation.

| Area | YWD-Hotspot adds |
|---|---|
| RF | DMR simplex **or duplex**, TS1/TS2-aware config, live RX/TX state, Last Heard, BER/RSSI context |
| BrandMeister | static/dynamic TG controls, duplex-aware slot routing, Drop QSO, saved Talkgroup Manager sets |
| WebUI | responsive dark UI, authenticated write controls, themed confirmation/progress dialogs, RF-style instrumentation |
| OLED | one authoritative renderer with boot/runtime/update presentation |
| Telemetry | structured MMDVM sessions and local sanitized telemetry state |
| Plugins | signed sandboxed UI/service packages, explicit install/enable state, transactional in-place updates |
| RX Monitor | passive browser-side DMR receive decoding through a narrow core capability; no plugin RF ownership |
| Calibration | baseline save/restore and repeated BER-driven RXOffset workflow |
| Health | service, Wi-Fi, temperature, journal, diagnostics and support bundle tools |
| RadioID | local DMR ID database health, scheduled due-checks, and manual update controls |
| Updates | staged validation, protected backup, detached updater, plugin-state preservation and rollback attempt |
| OS | reproducible Raspberry Pi OS image builder from the same source tree |

No Node.js runtime, React/Vue, SQL server, Redis, or Docker is required on the hotspot.

## Hardware target

Primary development/test budget:

- original Raspberry Pi Zero W / Zero WH
- Raspberry Pi OS Lite 32-bit / Raspbian 13 (trixie)
- MMDVM_HS/JumboSpot-style HAT, including tested simplex and duplex configurations
- `/dev/serial0` at 115200 baud
- optional SSD1306-compatible 128×64 I2C OLED at `0x3C`
- BrandMeister DMR

Other Pi models may work, but the original Zero W remains the performance target.

## Quick start

The stable release line is `main`:

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

The installer performs a fresh pinned MMDVM-Host/DMRGateway build when needed, preserves explicit RF-start safety, and establishes GitHub-managed application updates. On a Pi Zero, the first radio-stack compile can take a while.

Full walkthrough: **[docs/INSTALL.md](docs/INSTALL.md)**  
Build/developer guide: **[docs/BUILDING.md](docs/BUILDING.md)**

## Building: the short version

For most users, **`INSTALL.sh` is the build system**. It checks out the exact upstream radio commits from `pins.env`, builds them with Pi-friendly settings, deploys the application, installs services, and leaves RF enablement as an explicit operator decision.

For source validation without installing anything:

```bash
python3 lib/candidate_validate.py .
python3 -m py_compile lib/*.py
bash -n INSTALL.sh INSTALL-core.sh UPDATE.sh UPDATE-core.sh GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh
```

For complete appliance-image builds:

```bash
bash os/builder/DOCTOR.sh
bash os/builder/BUILD.sh
```

See **[docs/BUILDING.md](docs/BUILDING.md)** for the easy step-by-step build paths.

## Patched MMDVM-Host for RX Monitor

Normal DMR operation uses the pinned MMDVM-Host baseline. The optional **RX Monitor / passive DMR voice** path needs a small YWD patch that mirrors accepted DMR voice frames to a **loopback-only observation topic** while MMDVM-Host remains the sole modem/RF owner.

Pinned upstream MMDVM-Host:

```text
repo    https://github.com/g4klx/MMDVM-Host.git
commit  dea6e9b2c35857fe6f904c5092bebadb86cbf079
```

YWD voice-tap patch:

```text
lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch
```

The patched binary is prepared through the guarded background build path:

```bash
sudo systemctl start ywd-mmdvm-voice-build.service
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py status
sudo journalctl -u ywd-mmdvm-voice-build.service -f
```

On the original Pi Zero this compile can be slow, so it is intentionally de-prioritized and kept outside normal RF startup and ordinary application updates. **Normal YWD-Hotspot updates do not recompile MMDVM-Host or DMRGateway.** The RX Monitor plugin never opens the modem serial port and never gets RF TX authority.

Details: **[docs/DMR-VOICE.md](docs/DMR-VOICE.md)** and **[docs/BUILDING.md](docs/BUILDING.md)**.

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

An unlocked WebUI also provides **ABOUT → SOFTWARE UPDATE** with detached progress that survives dashboard restart.

Git branch/ref provenance is intentionally separate from the persistent update channel. Normal stable appliances should follow `main`; explicit checkpoint or temporary-branch tests do not need to redefine the long-term update channel.

```bash
sudo ywd-hotspotctl update-channel main
sudo ywd-hotspotctl update-channel dev
sudo ywd-hotspotctl update-channel dev-plugins
```

The updater verifies canonical origin, refuses dirty managed source, stages and validates the candidate before touching the live stack, preserves RF/service policy, creates protected backups, keeps the split privileged admin bridge coherent, quiesces/restores plugin state where appropriate, and advances managed source only after a successful deployment.

See **[docs/UPGRADING.md](docs/UPGRADING.md)**.

## Branch model

| Branch | Purpose |
|---|---|
| `main` | conservative/promoted releases; `0.1.0` stable line |
| `dev` | physically accepted integrated development baseline |
| `dev-builder` | isolated OS image/builder work |
| `dev-plugins` | plugin/framework development line |

Temporary release/feature branches are not additional release channels. The completed `dev-release-0.1.0` RC branch and its `checkpoint-release-*` refs remain useful historical/rollback references, while new accepted release work continues to flow deliberately through `dev` and then `main`.

See **[docs/REPOSITORY.md](docs/REPOSITORY.md)** and **[docs/GITHUB-SETUP.md](docs/GITHUB-SETUP.md)**.

## Plugin safety model

The plugin subsystem is optional. Master OFF must return the appliance to normal YWD-Hotspot behavior.

Current rules include:

- upload verifies/reviews a package before installation;
- install and enable are separate operator decisions;
- same-ID package updates are explicit transactional operations with rollback on failure;
- uploaded executable service and browser-UI plugins require a trusted Ed25519 signature;
- signer/kind/capability changes are checked during replacement;
- service plugins run through a restrictive shared systemd sandbox;
- UI plugins run in an isolated iframe with a narrow trusted MessageChannel bridge;
- no plugin gets arbitrary sudo, RF serial ownership, broad device access, RF TX authority, or an independent MMDVM instance;
- plugin state/config/data is separate from canonical hotspot configuration;
- core application updates quiesce and restore only previously valid plugin intent.

Guides: **[Plugins](docs/PLUGINS.md)** · **[Plugin Packages](docs/PLUGIN-PACKAGES.md)** · **[Plugin UI](docs/PLUGIN-UI.md)**

## Passive DMR voice / RX Monitor

MMDVM-Host remains the only modem/RF owner. The optional YWD voice tap mirrors accepted DMR voice frames to a loopback-only trusted path. Core turns that into a bounded capability-gated frame stream; RX Monitor performs FEC/AMBE recovery and audio playback in the browser.

This architecture intentionally keeps AMBE-to-PCM work off the Pi Zero and gives plugins no direct serial, MQTT, network, or TX authority.

Guide: **[docs/DMR-VOICE.md](docs/DMR-VOICE.md)**

## OLED and live display

YWD-Hotspot OS uses `ywd-headless-oled.service` as the sole physical SSD1306 owner. The canonical renderer lives in `lib/oled.py` and supports boot/network/setup frames plus Basic/Enhanced runtime RX/TX presentation. OLED failure is intentionally outside the RF-critical path.

Guide: **[docs/DISPLAY.md](docs/DISPLAY.md)**

## Calibration

The RX calibration workflow is measurement-driven: save a baseline, change one variable at a time, record repeated RF calls, and compare average BER rather than one lucky packet. TX remains separate because the hotspot cannot directly measure the handheld receiver's BER.

Guide: **[docs/CALIBRATION.md](docs/CALIBRATION.md)**

## Architecture

```text
DMR HT
  │
  ▼
MMDVM HAT
  │
  ▼
MMDVM-Host ── passive telemetry/voice copies ──► trusted YWD side services
  │
  ▼
DMRGateway
  │
  ▼
BrandMeister

Side services:
  ├─ dashboard / authenticated admin API
  ├─ activity + telemetry collectors
  ├─ passive voice bridge
  ├─ authoritative OLED renderer
  ├─ optional sandboxed plugins
  ├─ detached updater
  └─ RadioID updater
```

Architecture notes: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

## Security

YWD-Hotspot deliberately separates:

1. BrandMeister Hotspot Security password
2. BrandMeister API v2 key
3. local WebUI control password
4. plugin publisher **public** trust keys

Secrets stay server-side and out of browser-readable state and sanitized diagnostics. Protected `.ywdsettings` backups can contain reusable credentials and must remain private. Plugin signing **private** keys belong only on the development machine and never on the hotspot.

Read **[SECURITY.md](SECURITY.md)** before exposing or sharing anything from a real appliance.

## Pinned RF components

```text
MMDVM-Host
  repo   https://github.com/g4klx/MMDVM-Host.git
  commit dea6e9b2c35857fe6f904c5092bebadb86cbf079

DMRGateway
  repo   https://github.com/g4klx/DMRGateway.git
  commit 2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

Do not casually move these pins during unrelated UI/plugin/docs/cleanup work. A pin move changes the tested RF/calibration baseline and requires its own physical regression pass.

## Documentation

| Guide | Purpose |
|---|---|
| [Documentation index](docs/README.md) | find the right guide |
| [Installation](docs/INSTALL.md) | fresh install and migration |
| [Building](docs/BUILDING.md) | source validation, fresh radio build, patched RX voice build, OS image build |
| [Upgrading](docs/UPGRADING.md) | channels, WebUI update, rollback/recovery |
| [Architecture](docs/ARCHITECTURE.md) | RF/runtime boundaries and side services |
| [Display](docs/DISPLAY.md) | WebUI instrumentation and OLED |
| [Plugins](docs/PLUGINS.md) | plugin architecture and safety boundaries |
| [Plugin Packages](docs/PLUGIN-PACKAGES.md) | `.ywdplugin` packaging/signing/update model |
| [Plugin UI](docs/PLUGIN-UI.md) | browser plugin isolation/bridge |
| [Passive DMR Voice](docs/DMR-VOICE.md) | patched MMDVM voice tap, RX frame bridge and browser decode path |
| [Telemetry](docs/TELEMETRY.md) | local MMDVM telemetry path |
| [Talkgroups](docs/TALKGROUPS.md) | BrandMeister Talkgroup Manager |
| [Calibration](docs/CALIBRATION.md) | BER-driven RX workflow |
| [Repository Policy](docs/REPOSITORY.md) | branch/checkpoint/release policy |
| [Development](docs/GITHUB-SETUP.md) | clone, validation and source workflow |
| [OS Development](docs/OS-DEVELOPMENT.md) | full image builder workflow |
| [Security](SECURITY.md) | credentials and exposure rules |

## Project

Written by **KJ6YWD**. Project home: **https://kj6ywd.net**  
Canonical repository: **https://github.com/merberg-ai/ywd-hotspot**

## License

YWD-Hotspot is released under the **[Unlicense](LICENSE)** / public-domain dedication included in this repository.
