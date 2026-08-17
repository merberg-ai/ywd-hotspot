<p align="center">
  <img src="assets/branding/ywd-hotspot-badge-256.webp" alt="YWD-Hotspot logo" width="220">
</p>

<h1 align="center">YWD-Hotspot</h1>
<p align="center"><strong>Lightweight DMR hotspot software for Raspberry Pi + MMDVM HAT hardware.</strong></p>
<p align="center">📡 DMR · 🎛️ BrandMeister · 🥧 Pi Zero W · 📟 OLED · 🧪 Calibration · 🔄 Safe GitHub updates</p>

<p align="center">
  <a href="#-quick-install">🚀 Install</a> ·
  <a href="#-build-a-complete-ywd-hotspot-os-image">🥧 Build OS image</a> ·
  <a href="#-updating">🔄 Update</a> ·
  <a href="#-live-dmr--display">📟 Display</a> ·
  <a href="#-talkgroup-manager">📻 Talkgroups</a> ·
  <a href="#-calibration">🧪 Calibration</a> ·
  <a href="docs/README.md">📚 Docs</a> ·
  <a href="SECURITY.md">🔐 Security</a>
</p>

---

> [!IMPORTANT]
> **Promoted runtime baseline:** `main` carries the physically proven unified application + OS-builder runtime from `0.1.0-alpha12.2-dev` (`41f1cf9fcf94b3880d5cf11fb35e2cccb6fd3afd`). Documentation-only commits may sit above that tested runtime commit on `main` without changing the installed application payload. Plain `dev` currently retains the same Alpha12.2 runtime baseline. The integrated checkpoint is preserved at `dev-alpha12.2-os-integrated-known-good`. Experimental plugin/MMDVM work remains separate on `dev-plugins` and is not part of the `main` runtime documented here.

> [!WARNING]
> The built-in WebUI is plain HTTP for a trusted LAN. Do **not** forward the dashboard port directly to the public Internet.

## ✨ What is YWD-Hotspot?

YWD-Hotspot is a purpose-built DMR hotspot stack for small Raspberry Pi systems—especially the original **Raspberry Pi Zero W**. The RF path stays on pinned upstream **MMDVM-Host** and **DMRGateway**, while YWD-Hotspot adds a lightweight local UI, CLI, BrandMeister controls, diagnostics, calibration tools, OLED support, safe GitHub-managed updates, and a reproducible appliance-image builder.

The design goal is simple: **make a DMR hotspot feel like a polished appliance without turning a Pi Zero into a tiny web-server science project.**

| Area | What YWD-Hotspot adds |
|---|---|
| 📡 RF | DMR-only simplex configuration, live RX/TX state, Last Heard, BER/RSSI context |
| 🎛️ BrandMeister | Static/dynamic TG controls, Drop QSO, Talkgroup Manager, directory search |
| 🌐 WebUI | Responsive dark UI, authenticated write controls, optional configurable RF-style instrumentation |
| 🧪 Calibration | Baseline save/restore, repeated BER samples, RXOffset recommendation, export |
| 🩺 Health | Service state, Wi-Fi/power/temperature checks, persistent journal, diagnostics |
| 📟 OLED | Unified lightweight runtime/boot display with configurable RX/TX presentation |
| 💻 CLI | Colorized control console, status/source/calibration helpers |
| 🔄 Updates | Managed Git checkout, staged validation, About-page updater, stage-driven progress, rollback attempt |
| 🥧 OS image | Unified Raspberry Pi OS image builder with setup AP, secure first boot, pinned RF binaries and reproducible provenance |

No Node.js runtime. No React/Vue. No SQL server. No Redis. No Docker.

## 🥧 Primary hardware target

Current development and test baseline:

- Raspberry Pi Zero W Rev 1.1 — original Zero W, not Zero 2 W
- Raspberry Pi OS Lite 32-bit / Raspbian 13 (trixie)
- Simplex MMDVM_HS_Hat / JumboSpot-style board
- STM32 + ADF7021 modem hardware
- `/dev/serial0` at 115200 baud
- expected Pi Zero mapping: `/dev/serial0 -> /dev/ttyAMA0`
- SSD1306-like 128×64 I2C OLED at `0x3C` when fitted
- DMR simplex through BrandMeister

Other Pi models may work, but the original Pi Zero W is the performance budget.

## 🚀 Quick install

### Promoted `main` line

A normal Git clone follows the promoted `main` branch and preserves executable bits:

```bash
sudo apt update
sudo apt install -y git

cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

Equivalent explicit branch form:

```bash
cd ~
git clone --branch main https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

### Active `dev` line

For normal core/application development testing:

```bash
sudo apt update
sudo apt install -y git

cd ~
git clone --branch dev https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

> [!NOTE]
> If you are working from a ZIP/Windows copy that lost executable bits, run the entry point through Bash instead: `sudo bash ./INSTALL.sh`.

A genuinely fresh repository installation builds the pinned MMDVM-Host and DMRGateway commits with `make -j1`. On an original Pi Zero W, that can take a while. Normal YWD application updates do **not** repeat that compile.

The installer never starts RF unless you explicitly type:

```text
ENABLE-RF
```

Full walkthrough: **[docs/INSTALL.md](docs/INSTALL.md)**

## 🥧 Build a complete YWD-Hotspot OS image

The promoted `main` branch also contains the unified Raspberry Pi OS image builder.

A build packages the **same Git commit that runs the builder**, compiles the pinned RF stack inside the armhf image, configures the Pi Zero UART, installs the headless OLED/network/setup layers, and leaves RF disabled until secure first-boot setup explicitly enables it.

Short build flow on a suitable Linux builder:

```bash
cd ~/ywd-hotspot
git switch main
git pull --ff-only
bash os/builder/DOCTOR.sh
bash os/builder/BUILD.sh
```

Current supported image modes:

- **Factory/unconfigured:** no Wi-Fi embedded; first boot creates `YWD-Hotspot-XXXX`, with onboarding at `http://10.42.0.1/`.
- **Wi-Fi preseeded:** run `bash os/builder/CONFIGURE-WIFI.sh` before building; the Pi tries that Wi-Fi first and falls back to the setup AP if needed.

In both modes, real station/radio/BrandMeister/control configuration still goes through the secure first-boot wizard at:

```text
https://ywd-hotspot.local:8443/
```

after the OLED displays its six-digit setup code.

Current `main` does **not** expose a supported full radio/BrandMeister build-time preseed. The image deliberately starts with `NOCALL` / `00000`, cleared control/API credentials, and RF disabled.

Detailed host prerequisites, builder variables, outputs, flashing, setup flow and acceptance checklist: **[docs/OS-IMAGE-BUILD.md](docs/OS-IMAGE-BUILD.md)**

## 🔁 Existing install → GitHub management

If an older archive-installed YWD-Hotspot is already working, do **not** rebuild the radio stack just to switch update methods.

```bash
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./MIGRATE-TO-GITHUB.sh
```

Migration preserves canonical config, BrandMeister credentials, local WebUI control password, calibration/history/runtime data, and current RF running/enabled policy. It does **not** rebuild MMDVM-Host or DMRGateway.

After migration, cross onto `dev` only if you want the active normal development line:

```bash
sudo ywd-hotspotctl update --branch dev
```

A successful `--branch dev` update remembers `dev` as the future update channel.

## ✅ After installation

Check the appliance:

```bash
ywd-hotspotctl status
ywd-hotspotctl source
systemctl --failed --no-pager
```

For a normal repository install, configure the local write-control password:

```bash
sudo ywd-hotspotctl web-password
```

Configure a separate BrandMeister API v2 key for TG/Drop-QSO controls:

```bash
sudo ywd-hotspotctl bm-api-key
```

YWD-Hotspot OS handles those credentials through its secure first-boot wizard.

Then open:

```text
http://PI-IP:8080/
```

The dashboard port is configurable.

## 🔄 Updating

YWD-Hotspot separates managed source from the live runtime:

```text
/opt/ywd-hotspot/repo    root-owned managed Git checkout
/opt/ywd-hotspot/app     deployed runtime copy; no .git directory
```

Normal CLI update flow:

```bash
sudo ywd-hotspotctl update --check
sudo ywd-hotspotctl update --dry-run
sudo ywd-hotspotctl update
```

Update channels:

```bash
sudo ywd-hotspotctl update-channel main
sudo ywd-hotspotctl update-channel dev
```

GitHub-managed installs also expose **ABOUT → SOFTWARE UPDATE** when WebUI controls are unlocked. The WebUI updater validates the saved channel, starts a detached one-shot update job, and shows real stage-driven progress while the dashboard restarts/reconnects. The final install button gives immediate busy/spinner feedback while the detached service is being launched so there is no silent gap before the progress modal appears.

The updater preserves RF active/enabled policy and keeps a protected pre-update backup. Browser code cannot supply arbitrary root shell commands or update URLs/branches.

Full details and recovery notes: **[docs/UPGRADING.md](docs/UPGRADING.md)**

## 📟 LIVE DMR + Display

The promoted Alpha12.x line provides an optional RF-instrument style Status panel while preserving the established Basic UI.

### WebUI LIVE DMR modes

**Basic** keeps the lightweight RX/TX activity card and is the default.

Enhanced instrumentation can add:

- segmented or smooth RSSI meter
- BER quality meter with configurable thresholds
- configured TX/RF drive meters
- peak hold and completed-measurement hold
- sample-based or time-window RSSI/BER history traces
- animated RF-energy visualization
- live top-strip RX/TX information
- 5/10/20 fps performance targets
- reduced-motion controls
- Basic, Balanced, Instrument, Maximum Shiny, and Custom presets

RX and TX intentionally use different instruments. During active **RF receive**, RSSI/BER reads `SAMPLING…` / `MEASURING…` until the normal MMDVM-Host completed-call journal summary supplies measured values. During **network → RF TX**, the UI prioritizes configured TX/RF drive and shows network quality as pending until packet-loss/BER results are available.

The promoted `main` line deliberately does not add a local MQTT dependency merely to animate gauges. The lightweight journal/activity collector remains the default stability-oriented path.

The gauges consume the dashboard's existing status payload; enhanced mode does not create another server polling loop. Missing measurements stay missing rather than being fabricated. The animated RF-energy display is presentation, not an audio VU meter.

All dynamic meter/progress levels are represented through same-origin CSS state rather than inline style mutations, preserving the dashboard's strict `style-src 'self'` CSP.

### Unified OLED

On YWD-Hotspot OS, `ywd-headless-oled.service` remains the **sole SSD1306/I2C owner**. It uses the unified renderer for boot/network/setup screens and, after setup, configurable runtime RX/TX pages. The duplicate `ywd-oled.service` remains disabled on the appliance OS.

Runtime OLED options include:

- Basic / Enhanced / Minimal modes
- large auto-fit callsign
- group/private destination and cached TG names
- local DMR-ID callsign resolution
- slot, elapsed, BER, RSSI, and packet-loss toggles
- post-call hold
- optional idle page cycling
- brightness/timeout
- hardware 0° / 180° rotation
- software-update progress display

Display services remain passive consumers outside the RF-critical path. OLED failure must not stop DMR.

Full guide: **[docs/DISPLAY.md](docs/DISPLAY.md)**

## 📻 Talkgroup Manager

The **TALKGROUPS** page gives BrandMeister static TG management a safer workflow:

1. search the public BrandMeister TG directory by ID or name
2. build a desired static-TG plan locally
3. preview exact `ADD` / `REMOVE` changes
4. press **APPLY PLAN**
5. confirm the plan in the themed YWD dialog

Browsing, favorites, saved sets, and plan editing do **not** change BrandMeister by themselves.

The directory is normalized and cached locally for 24 hours to stay cheap on a Pi Zero W.

Guide: **[docs/TALKGROUPS.md](docs/TALKGROUPS.md)**

## 🧪 Calibration

The RX workflow is intentionally measurement-driven:

- save a baseline
- change one variable at a time
- record repeated RF calls at each RXOffset
- compare average BER, not one lucky packet
- require at least 3 samples at an offset before recommending it
- require operator confirmation before applying the recommendation

TX calibration remains separate because the hotspot cannot directly measure the handheld receiver's BER.

Guide: **[docs/CALIBRATION.md](docs/CALIBRATION.md)**

## 🧱 Architecture

```text
DMR HT
  │
  ▼
MMDVM HAT
  │
  ▼
MMDVM-Host
  │
  ▼
DMRGateway
  │
  ▼
BrandMeister

Side services:
  ├─ activity collector
  ├─ dashboard / API
  ├─ authoritative OLED renderer
  ├─ detached software updater
  └─ RadioID updater
```

The dashboard/OLED/activity presentation stay outside the RF-critical path. If the WebUI or OLED dies, DMR should keep working.

Architecture notes: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

## 🔐 Security model

YWD-Hotspot keeps three credentials deliberately separate:

1. BrandMeister Hotspot Security password
2. BrandMeister API v2 key
3. local YWD-Hotspot WebUI control password

The API key stays server-side and is never returned to browser JavaScript. Sanitized diagnostics are preferred for support; protected backups can contain reusable credentials and must remain private.

The image builder also creates builder-local SSH key material under ignored `os/local/`; keep the private key private.

Read **[SECURITY.md](SECURITY.md)** before exposing or sharing anything from a real appliance.

## 🧭 Build provenance

Install/update/image builds write non-secret provenance to:

```text
/etc/ywd-hotspot/build-info.json
```

The CLI and About page show the installed version, source branch, update channel, commit, commit date, source type and source state. For a promoted `main` install/image, the normal branch/channel should be `main`; `dev` builds report `dev`.

## 💻 CLI quick reference

<details>
<summary><strong>Show common commands</strong></summary>

```bash
# Read-only/status
ywd-hotspotctl status
ywd-hotspotctl source
ywd-hotspotctl health
ywd-hotspotctl lastheard
ywd-hotspotctl logs
ywd-hotspotctl calibration

# Update management
sudo ywd-hotspotctl update --check
sudo ywd-hotspotctl update --dry-run
sudo ywd-hotspotctl update
sudo ywd-hotspotctl update-channel main
sudo ywd-hotspotctl update-channel dev

# Config/support
sudo ywd-hotspotctl configure
sudo ywd-hotspotctl apply
sudo ywd-hotspotctl diagnostics
sudo ywd-hotspotctl backup
sudo ywd-hotspotctl lab

# RF/runtime
sudo ywd-hotspotctl restart
sudo ywd-hotspotctl start
sudo ywd-hotspotctl stop

# BrandMeister
sudo ywd-hotspotctl bm profile
sudo ywd-hotspotctl bm addtg 3100
sudo ywd-hotspotctl bm deltg 3100
sudo ywd-hotspotctl bm dropqso
sudo ywd-hotspotctl bm dropdyn
```

Running `sudo ywd-hotspotctl` with no subcommand opens the themed interactive control console.

</details>

Terminal colors are automatically disabled when output is redirected. Set `NO_COLOR=1` to force plain output.

## 📌 Pinned RF components

```text
MMDVM-Host
  repo   https://github.com/g4klx/MMDVM-Host.git
  commit dea6e9b2c35857fe6f904c5092bebadb86cbf079

DMRGateway
  repo   https://github.com/g4klx/DMRGateway.git
  commit 2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

Do not casually move these pins during calibration/stability work.

## 📚 Documentation

| Guide | Use it for |
|---|---|
| **[Documentation index](docs/README.md)** | Find the right guide quickly |
| **[Installation](docs/INSTALL.md)** | Main/dev install, migration, UART/modem preflight, OS-image first boot |
| **[OS Image Build](docs/OS-IMAGE-BUILD.md)** | Full image-builder prerequisites, factory/Wi-Fi-preseed modes, output, flashing, setup and acceptance tests |
| **[OS Development](docs/OS-DEVELOPMENT.md)** | Builder architecture, branch/integration workflow, promotion rules |
| **[Upgrading](docs/UPGRADING.md)** | Channels, staged/WebUI updates, rollback/recovery |
| **[Display + Instrumentation](docs/DISPLAY.md)** | LIVE DMR meters, Basic/Enhanced modes, unified OLED settings |
| **[Talkgroups](docs/TALKGROUPS.md)** | BrandMeister Talkgroup Manager |
| **[Calibration](docs/CALIBRATION.md)** | Controlled RX BER workflow |
| **[Architecture](docs/ARCHITECTURE.md)** | RF path, privilege boundaries, runtime layout |
| **[Repository / development](docs/GITHUB-SETUP.md)** | Branch model, validation, source workflow |
| **[Security](SECURITY.md)** | Credentials, exposure, diagnostics, builder-local secrets |
| **[Contributing](CONTRIBUTING.md)** | Project constraints and PR expectations |
| **[Changelog](CHANGELOG.md)** | Development checkpoints |

## 👤 Project

Written by **KJ6YWD**. Project home: **https://kj6ywd.net**  
Canonical repository: **https://github.com/merberg-ai/ywd-hotspot**

## 📄 License

YWD-Hotspot is released under the **[Unlicense](LICENSE)** / public-domain dedication included in this repository.
