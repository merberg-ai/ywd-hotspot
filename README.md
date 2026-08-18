<p align="center">
  <img src="assets/branding/ywd-hotspot-banner-webui.webp" alt="YWD-Hotspot" width="720">
</p>

<h1 align="center">YWD-Hotspot</h1>
<p align="center"><strong>Lightweight DMR hotspot software and appliance tooling for Raspberry Pi + MMDVM HAT hardware.</strong></p>
<p align="center">📡 DMR · 🎛️ BrandMeister · 🥧 Pi Zero W · 📟 OLED · 🧩 Plugins · 🧪 Calibration · 🔄 Safe updates</p>

<p align="center">
  <a href="#quick-start">Install</a> ·
  <a href="#branch-model">Branches</a> ·
  <a href="docs/README.md">Docs</a> ·
  <a href="docs/UPGRADING.md">Updates</a> ·
  <a href="SECURITY.md">Security</a>
</p>

---

> [!IMPORTANT]
> **Development status:** YWD-Hotspot is alpha software. The exact build is always defined by [`VERSION`](VERSION). `main` is the conservative line, `dev` is the unified app/OS baseline, and `dev-plugins` is the active experimental plugin/telemetry line.

> [!WARNING]
> The built-in WebUI is plain HTTP for a trusted LAN. Do **not** forward the dashboard port directly to the public Internet.

## What YWD-Hotspot is

YWD-Hotspot is a purpose-built DMR hotspot stack for small Raspberry Pi systems—especially the original **Raspberry Pi Zero W**. The RF path stays on pinned upstream **MMDVM-Host** and **DMRGateway**, while YWD-Hotspot provides a lightweight WebUI, CLI, BrandMeister controls, diagnostics, calibration, OLED presentation, telemetry, safe GitHub-managed updates, and an optional sandboxed plugin framework.

The design rule is simple: **the Pi does radio and small state collection; the browser does the fancy graphics.** Display, dashboard, telemetry, and plugin failures must not take down normal DMR operation.

| Area | YWD-Hotspot adds |
|---|---|
| RF | DMR-only simplex config, live RX/TX state, Last Heard, BER/RSSI context |
| BrandMeister | static/dynamic TG controls, Drop QSO, Talkgroup Manager |
| WebUI | responsive dark UI, authenticated write controls, RF-style instrumentation |
| OLED | one authoritative renderer with boot/runtime/update presentation |
| Telemetry | structured MMDVM sessions and local sanitized telemetry state |
| Plugins | optional declarative/sandboxed service packages with a global kill switch |
| Calibration | baseline save/restore and repeated BER-driven RXOffset workflow |
| Health | service, Wi-Fi, temperature, journal, diagnostics and support bundle tools |
| Updates | staged validation, protected backup, detached updater and rollback attempt |
| OS | reproducible Raspberry Pi OS image builder from the same source tree |

No Node.js runtime, React/Vue, SQL server, Redis, or Docker is required on the hotspot.

## Hardware target

Primary development budget:

- original Raspberry Pi Zero W / Zero WH
- Raspberry Pi OS Lite 32-bit / Raspbian 13 (trixie)
- simplex MMDVM_HS/JumboSpot-style HAT
- `/dev/serial0` at 115200 baud
- optional SSD1306-compatible 128×64 I2C OLED at `0x3C`
- DMR simplex through BrandMeister

Other Pi models may work, but the original Zero W remains the performance target.

## Quick start

### Promoted `main`

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

### Unified development `dev`

```bash
git clone --branch dev https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

### Experimental plugin/telemetry `dev-plugins`

```bash
git clone --branch dev-plugins https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

A fresh install builds the pinned radio components with `make -j1`; that can take a while on a Pi Zero. Normal YWD application updates do **not** rebuild them. The installer also does not start RF unless the operator explicitly enables it.

Full walkthrough: **[docs/INSTALL.md](docs/INSTALL.md)**

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

Update channels:

```bash
sudo ywd-hotspotctl update-channel main
sudo ywd-hotspotctl update-channel dev
sudo ywd-hotspotctl update-channel dev-plugins
```

The updater refuses ambiguous or unsafe state, preserves RF policy, stages candidate validation outside the live app, and keeps protected pre-update backups. See **[docs/UPGRADING.md](docs/UPGRADING.md)**.

## Branch model

Long-lived development branches are intentionally few:

| Branch | Purpose |
|---|---|
| `main` | promoted/conservative line |
| `dev` | unified application + OS-builder baseline |
| `dev-plugins` | experimental plugin, telemetry, and current integration work |

Known-good historical points belong in immutable **`checkpoint/*` tags**, not permanent work branches. Superseded development lines belong in **`archive/*` tags** when they are worth retaining. Temporary feature/audit branches should be deleted after their tested result is published.

See **[docs/REPOSITORY.md](docs/REPOSITORY.md)** and **[docs/GITHUB-SETUP.md](docs/GITHUB-SETUP.md)** for the policy and validation workflow.

## Plugin safety model

The plugin subsystem is optional. Master OFF must return the appliance to normal YWD-Hotspot behavior.

Current rules include:

- new packages do not auto-enable or auto-start
- uploaded executable service plugins require a trusted Ed25519 signature
- shared service plugins run through a restrictive systemd sandbox
- no plugin gets arbitrary sudo, RF serial ownership, or broad device access
- plugin state/config is separate from canonical hotspot configuration
- updates quiesce plugin services and restore only previously valid state
- MMDVM telemetry remains observational and does not own RF

The old `system-info` and `service-heartbeat` proof packages are retired from the operator catalog. Their source manifests may remain temporarily as compatibility fixtures so upgrades can safely unregister old installations.

Guides: **[Plugins](docs/PLUGINS.md)** · **[Plugin Packages](docs/PLUGIN-PACKAGES.md)** · **[Telemetry](docs/TELEMETRY.md)**

## OLED and live display

YWD-Hotspot OS uses `ywd-headless-oled.service` as the sole physical SSD1306 owner. The canonical renderer lives in `lib/oled.py` and supports boot/network/setup frames plus Basic/Enhanced runtime RX/TX presentation. OLED failure is intentionally outside the RF-critical path.

The browser instrumentation similarly consumes existing status/telemetry state and does not invent missing RSSI/BER measurements.

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
MMDVM-Host ── local telemetry/session normalization
  │
  ▼
DMRGateway
  │
  ▼
BrandMeister

Side services:
  ├─ dashboard / API
  ├─ activity + telemetry collectors
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

Secrets stay server-side and out of browser-readable state and sanitized diagnostics. Protected `.ywdsettings` backups can contain reusable credentials and must remain private.

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

Do not casually move these pins during unrelated UI/plugin/cleanup work.

## Documentation

| Guide | Purpose |
|---|---|
| [Documentation index](docs/README.md) | find the right guide |
| [Installation](docs/INSTALL.md) | fresh install and migration |
| [Upgrading](docs/UPGRADING.md) | channels, WebUI update, rollback/recovery |
| [OS Development](docs/OS-DEVELOPMENT.md) | reproducible image builder |
| [Display](docs/DISPLAY.md) | WebUI instrumentation and OLED |
| [Plugins](docs/PLUGINS.md) | plugin architecture and safety boundaries |
| [Plugin Packages](docs/PLUGIN-PACKAGES.md) | `.ywdplugin` packaging/signing |
| [Telemetry](docs/TELEMETRY.md) | local MMDVM telemetry path |
| [MMDVM Sessions](docs/MMDVM-SESSIONS.md) | normalized call/session semantics |
| [Talkgroups](docs/TALKGROUPS.md) | BrandMeister Talkgroup Manager |
| [Calibration](docs/CALIBRATION.md) | BER-driven RX workflow |
| [Repository Policy](docs/REPOSITORY.md) | branch/tag/checkpoint policy |
| [Development](docs/GITHUB-SETUP.md) | clone, validation and source workflow |
| [Security](SECURITY.md) | credentials and exposure rules |

## Project

Written by **KJ6YWD**. Project home: **https://kj6ywd.net**  
Canonical repository: **https://github.com/merberg-ai/ywd-hotspot**

## License

YWD-Hotspot is released under the **[Unlicense](LICENSE)** / public-domain dedication included in this repository.
