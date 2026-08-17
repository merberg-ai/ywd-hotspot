# 🚀 Installing YWD-Hotspot

[← Docs index](README.md) · [Project README](../README.md) · [OS Image Build](OS-IMAGE-BUILD.md) · [Upgrading](UPGRADING.md) · [Security](../SECURITY.md)

---

> [!WARNING]
> YWD-Hotspot can control a radio transmitter. Attach a suitable antenna and verify the configured frequency before enabling RF.

## ✅ Supported test baseline

The primary development target is:

| Component | Current baseline |
|---|---|
| Raspberry Pi | Original **Pi Zero W Rev 1.1** |
| OS | Raspberry Pi OS Lite 32-bit / Raspbian 13 (trixie) |
| HAT | Simplex MMDVM_HS_Hat / JumboSpot-style |
| UART | `/dev/serial0` at 115200 |
| Pi Zero mapping | `/dev/serial0 -> /dev/ttyAMA0` |
| OLED | I2C bus 1, normally `0x3C` |
| Network | BrandMeister DMR simplex |

Current promoted `main` application baseline:

```text
0.1.0-alpha12.2-dev
41f1cf9fcf94b3880d5cf11fb35e2cccb6fd3afd
```

Useful preflight:

```bash
cat /etc/os-release
uname -a
uname -m
ls -l /dev/serial0 2>/dev/null || true
readlink -f /dev/serial0 2>/dev/null || true
```

## 🧭 Choose an installation path

There are two supported ways to start:

### A. Install onto an existing Raspberry Pi OS system

Use the normal Git clone + installer path below. This is appropriate when the Pi is already running Raspberry Pi OS and you want YWD-Hotspot to install/build the radio stack in place.

### B. Build/flash a complete YWD-Hotspot OS image

Use the integrated image builder when you want a ready-to-flash appliance image containing the current YWD-Hotspot application, pinned radio binaries, network onboarding, OLED boot/setup screens and secure first-boot wizard.

See **[Building a YWD-Hotspot OS image](OS-IMAGE-BUILD.md)**.

## 🚀 Fresh install from promoted `main`

A normal Git clone of the repository's default branch installs the promoted `main` line:

```bash
sudo apt update
sudo apt install -y git

cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

If you prefer to make the branch explicit:

```bash
cd ~
git clone --branch main https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

A normal Git clone preserves executable bits. No manual chmod pass is required.

If your source came from a ZIP/Windows copy and executable bits were lost:

```bash
sudo bash ./INSTALL.sh
```

## 🧪 Fresh install from `dev`

To install the normal development line directly:

```bash
sudo apt update
sudo apt install -y git

cd ~
git clone --branch dev https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

`dev` is for active core/application testing. The promoted `main` line is intentionally more conservative.

Experimental plugin/MMDVM work is maintained separately and is not part of the normal `main` installation documented here.

## 🥧 Install using a YWD-Hotspot OS image

The unified OS builder packages the exact application commit used to build the image.

A factory image boots with:

- RF disabled
- factory `NOCALL` / `00000` identity
- BrandMeister disabled
- no WebUI control password
- no BrandMeister API key
- `ywd-headless-oled.service` as the sole OLED owner

Without embedded Wi-Fi, the appliance creates a setup AP similar to:

```text
YWD-Hotspot-ABCD
```

Connect to it and browse to:

```text
http://10.42.0.1/
```

After station Wi-Fi is established, the OLED displays a six-digit setup code and the secure setup wizard becomes available at:

```text
https://ywd-hotspot.local:8443/
```

The browser may warn about the locally generated self-signed certificate. Verify you are talking to the local hotspot before continuing.

The first-boot wizard finalizes the canonical station/radio/BrandMeister configuration, dashboard password, optional BrandMeister API key and final RF-enable choice.

RF remains disabled unless the operator explicitly enables it during setup.

The image builder can optionally preseed **Wi-Fi only**. Current `main` does not provide a supported full radio/BrandMeister configuration preseed. See **[OS-IMAGE-BUILD.md](OS-IMAGE-BUILD.md)** for exact build modes and the physical acceptance checklist.

## 🔁 Existing install → GitHub management

If `/etc/ywd-hotspot/config.json` and `/opt/ywd-hotspot/app` already exist, the installer detects the appliance before it does any radio-stack compilation.

`INSTALL.sh` offers:

```text
1) Adopt existing installation and switch to GitHub updates
2) Full/recovery installation
3) Cancel
```

For a working existing hotspot, choose **1**.

The direct migration path is even simpler:

```bash
sudo apt update
sudo apt install -y git

cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./MIGRATE-TO-GITHUB.sh
```

Migration preserves:

- `/etc/ywd-hotspot/config.json`
- BrandMeister credentials
- local WebUI control password
- calibration/history/runtime data
- current RF active/enabled policy
- existing MMDVM-Host and DMRGateway binaries

It **does not** recompile MMDVM-Host or DMRGateway.

The migration intentionally adopts the promoted `main` line first. After it completes, opt into `dev` only if desired:

```bash
sudo ywd-hotspotctl update --branch dev
```

That successful branch update becomes the saved update channel.

## 🔌 UART / modem preflight

For a fresh Pi, run the hardware lab before installation if `/dev/serial0` is missing or mapped incorrectly:

```bash
cd ~/ywd-hotspot
sudo ./lab/mmdvm-diag.sh
```

Useful choices:

- **1** — full read-only diagnostic set
- **2** — MMDVM firmware probe only
- **5** — apply the recommended Pi Zero W PL011 configuration

On the original Pi Zero W, option 5:

- backs up boot configuration
- sets `enable_uart=1`
- adds `dtoverlay=disable-bt`
- removes UART serial-console tokens
- disables `hciuart`
- requires a reboot

Bluetooth is disabled by this configuration; Wi-Fi is not.

After reboot:

```bash
cd ~/ywd-hotspot
readlink -f /dev/serial0
sudo ./lab/mmdvm-diag.sh
```

Expected:

```text
/dev/ttyAMA0
```

## 🧱 What a fresh repository install does

A genuinely fresh clone/install on an existing Raspberry Pi OS system:

1. verifies Raspberry Pi hardware and UART mapping
2. performs a read-only MMDVM `GET_VERSION` probe
3. installs build/runtime dependencies
4. creates the restricted `ywd-hotspot` service account
5. clones the pinned MMDVM-Host and DMRGateway sources
6. checks out the exact commits from `pins.env`
7. compiles both with `make -j1`
8. deploys YWD-Hotspot under `/opt/ywd-hotspot/app`
9. installs systemd units, CLI, admin helper, and restricted sudo rules
10. writes non-secret build provenance
11. creates the managed `/opt/ywd-hotspot/repo` checkout when appropriate
12. runs/updates canonical configuration
13. updates the DMR ID database when possible
14. configures persistent journaling
15. starts lightweight side services
16. starts OLED only when configured/detected
17. asks for explicit RF-enable confirmation

> [!NOTE]
> The original Pi Zero W is not exactly a compile monster. The first upstream build can take a while. Normal YWD application updates do not repeat it.

The OS-image path differs: MMDVM-Host and DMRGateway are compiled inside the image build, and the deployed Pi uses the secure first-boot appliance wizard instead of the command-line fresh-install flow.

## ⚙️ Canonical configuration

Source of truth:

```text
/etc/ywd-hotspot/config.json
```

Generated outputs:

```text
/etc/ywd-hotspot/MMDVM-Host.ini
/etc/ywd-hotspot/DMRGateway.ini
```

Do **not** hand-maintain generated INI files. Change configuration through YWD-Hotspot and let it regenerate them.

Current canonical configuration schema is **5**.

The configuration system covers station identity, DMR ID/ESSID, simplex frequency, Color Code, BrandMeister master/security password, location, offsets/levels, WebUI port, OLED behavior, LIVE DMR instrumentation behavior, RF boot policy, and journal policy.

## 📡 RF enable confirmation — repository install

At the end of a fresh repository install:

```text
Type ENABLE-RF to start AND enable RF at boot now:
```

Only the exact text `ENABLE-RF` starts/enables the RF path. Any other response leaves MMDVM-Host and DMRGateway stopped/disabled.

On YWD-Hotspot OS, the equivalent safety decision is made on the final secure first-boot wizard step.

That invariant also applies to migration and normal application updates: **source management is never permission to key a transmitter.**

## 🔐 Configure WebUI write control

For a repository install, the dashboard is readable without a write-control session. Configure the local control password with:

```bash
sudo ywd-hotspotctl web-password
```

YWD-Hotspot OS creates this password during the secure first-boot wizard.

This password is separate from BrandMeister credentials.

## 🎛️ Configure the BrandMeister API key

Static-TG and Drop-QSO controls use a separate BrandMeister API v2 key:

```bash
sudo ywd-hotspotctl bm-api-key
```

YWD-Hotspot OS can accept the optional key during first-boot setup.

The API key stays on the Pi and is never returned to browser JavaScript.

## ✅ Verify the installation

```bash
ywd-hotspotctl status
ywd-hotspotctl source
systemctl --failed --no-pager
```

Core services include:

```text
ywd-mmdvmhost.service
ywd-dmrgateway.service
ywd-dashboard.service
ywd-activity.service
ywd-dmrid-update.timer
```

OLED ownership depends on installation type:

```text
Generic/repository install: ywd-oled.service
YWD-Hotspot OS:             ywd-headless-oled.service
```

On YWD-Hotspot OS, `ywd-oled.service` should remain inactive so there is only one physical SSD1306 owner.

RF service state depends on the operator's explicit choice.

## 🌐 Open the dashboard

Find the Pi address:

```bash
hostname -I
```

Then browse to:

```text
http://PI-IP:8080/
```

Use the configured port if it differs from `8080`.

> [!CAUTION]
> The built-in dashboard is plain HTTP for a trusted LAN. Do not expose its TCP port directly to the public Internet.

## 🔄 First update check

Once GitHub management is active:

```bash
sudo ywd-hotspotctl update --check
sudo ywd-hotspotctl update --dry-run
```

`--check` only reports. `--dry-run` also stages and validates the candidate without replacing the live app or changing RF service policy.

Before applying updates, read **[UPGRADING.md](UPGRADING.md)**.

## 📟 OLED notes

Generic installer paths scan I2C bus 1. The primary test HAT uses an SSD1306-like display at `0x3C`:

```bash
i2cdetect -y 1
```

YWD-Hotspot OS enables the headless OLED owner for boot/network/setup/runtime presentation.

OLED failure/absence must not interrupt DMR operation.

## 🪵 Known harmless DMRGateway MQTT message

Upstream DMRGateway may attempt a localhost MQTT connection and log connection-refused even though the promoted `main` line does not require a local MQTT broker.

Do **not** install Mosquitto solely to silence that message.

## 🧰 Troubleshooting

### UART / HAT

```bash
sudo ./lab/mmdvm-diag.sh
```

### BrandMeister / RF stack

```bash
ywd-hotspotctl status
ywd-hotspotctl logs
```

### Dashboard

```bash
systemctl status ywd-dashboard.service --no-pager
journalctl -u ywd-dashboard.service -n 100 --no-pager
```

### GitHub management

```bash
ywd-hotspotctl source
git -C /opt/ywd-hotspot/repo status --short
git -C /opt/ywd-hotspot/repo remote -v
```

### OS image / first boot

See **[OS-IMAGE-BUILD.md](OS-IMAGE-BUILD.md)** for setup-AP, Wi-Fi handoff, HTTPS wizard, builder doctor and image-output troubleshooting.

Never paste reusable credentials, protected backups or builder-local private SSH keys into public issues.

## 🗑️ Uninstall

From a repository checkout or installed source copy:

```bash
sudo ./UNINSTALL.sh
```

The uninstaller preserves configuration/runtime data by default so credentials/history are not casually destroyed.

---

**Next:** [🥧 Build an OS image](OS-IMAGE-BUILD.md) · [🔄 Upgrading](UPGRADING.md) · [📚 Docs index](README.md)
