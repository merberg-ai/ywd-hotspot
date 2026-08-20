# 🛠️ Building YWD-Hotspot

[← Docs index](README.md) · [Installation](INSTALL.md) · [Development](GITHUB-SETUP.md) · [OS Development](OS-DEVELOPMENT.md)

This guide separates the four things people often mean by “build YWD-Hotspot.” Pick the one that matches what you are actually trying to do.

## 1. Build and install a hotspot from GitHub — recommended

For a normal Raspberry Pi hotspot install, you do **not** manually clone and build MMDVM-Host yourself. `INSTALL.sh` is the supported build/install entry point.

### Stable `main`

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

For intentionally testing the accepted development baseline instead of the stable release, clone `--branch dev`. The completed `dev-release-0.1.0` branch is release history rather than the normal 0.1.0 build path.

The fresh installer:

1. validates the YWD-Hotspot source tree;
2. checks Raspberry Pi/UART prerequisites;
3. installs build/runtime dependencies;
4. clones the exact upstream radio sources from `pins.env`;
5. checks out the exact pinned commits;
6. builds MMDVM-Host and DMRGateway conservatively for the Pi;
7. deploys YWD-Hotspot and systemd services;
8. establishes canonical configuration and GitHub provenance;
9. leaves RF start/enable as an explicit operator decision.

On the original Pi Zero W the first radio build can take a while. That is normal.

## 2. Validate source without installing it

For docs/WebUI/Python/shell work, run source validation before pushing or testing on a Pi:

```bash
cd ~/ywd-hotspot

python3 lib/candidate_validate.py .
python3 -m py_compile lib/*.py

bash -n \
  INSTALL.sh INSTALL-core.sh \
  UPDATE.sh UPDATE-core.sh \
  GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh \
  MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh \
  UNINSTALL.sh \
  bin/ywd-hotspotctl bin/ywd-hotspotctl-core bin/ywd-ui.sh \
  lab/mmdvm-diag.sh
```

If Node.js is available on the development machine:

```bash
for js in web/*.js; do
  node --check "$js"
done
```

These checks do not replace a real Pi test for runtime, systemd, sudoers, updater, RF, OLED, or plugin-lifecycle changes.

## 3. Build the patched MMDVM-Host used by RX Monitor

### Why there is a patch

YWD-Hotspot keeps **MMDVM-Host as the only owner of the modem serial/RF path**. RX Monitor therefore does not open `/dev/serial0` and does not run a second modem process.

Instead, the optional passive voice path applies a small patch to the pinned MMDVM-Host source. The patch mirrors already-accepted DMR voice bursts to a loopback-only observation topic while normal MMDVM processing continues unchanged.

Pinned upstream source:

```text
MMDVM-Host repo   https://github.com/g4klx/MMDVM-Host.git
MMDVM-Host commit dea6e9b2c35857fe6f904c5092bebadb86cbf079
```

Patch:

```text
lib/mmdvm_patches/0001-ywd-dmr-voice-mqtt.patch
```

The exact upstream pin is also recorded in `pins.env`.

### Guarded build

On an installed hotspot:

```bash
sudo systemctl start ywd-mmdvm-voice-build.service
```

Follow progress:

```bash
sudo journalctl -fu ywd-mmdvm-voice-build.service
```

Check status at any time:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py status
```

The service runs:

```text
/usr/bin/python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py ensure
```

and is intentionally configured as a low-priority one-shot build with a long timeout. On the original single-core Pi Zero W the patched MMDVM compile can be slow.

### Important behavior

- ordinary YWD-Hotspot application updates do **not** rebuild MMDVM-Host or DMRGateway;
- the passive voice build is outside normal RF startup;
- the helper verifies the exact pinned source and exact patch identity before reusing an interrupted source tree;
- activation is guarded and retains a fallback to the previously working binary;
- RX Monitor receives only a bounded capability-gated frame stream;
- RX Monitor does not receive arbitrary RF TX, serial, MQTT, sudo, or broad network authority.

If you do not use passive DMR voice/RX Monitor, there is no reason to manually trigger this optional build just to run a normal hotspot.

Full architecture: **[DMR-VOICE.md](DMR-VOICE.md)**.

## 4. Build a complete SD-card appliance image

The application repo also contains the YWD-Hotspot OS image builder. This is a separate workflow from installing the application onto an existing Raspberry Pi OS system.

On the Linux builder machine:

```bash
cd ~/ywd-hotspot
git status --short
git branch --show-current

bash os/builder/DOCTOR.sh
```

Fix anything reported by the doctor before starting a long image build.

Then:

```bash
bash os/builder/BUILD.sh
```

Optional build-time Wi-Fi configuration:

```bash
bash os/builder/CONFIGURE-WIFI.sh
```

Generated image artifacts are written under the ignored builder/deploy paths rather than committed to the application tree.

See **[OS-DEVELOPMENT.md](OS-DEVELOPMENT.md)** and `os/README.md` for the builder-specific workflow.

## Current pinned radio baseline

```text
MMDVM-Host
  repo   https://github.com/g4klx/MMDVM-Host.git
  commit dea6e9b2c35857fe6f904c5092bebadb86cbf079

DMRGateway
  repo   https://github.com/g4klx/DMRGateway.git
  commit 2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

Do not casually change these pins while doing unrelated UI/docs/plugin work. A radio pin move changes the calibration and RF stability baseline and needs an isolated physical regression pass.

## After a build/install

Useful checks:

```bash
ywd-hotspotctl status
ywd-hotspotctl source
```

Dashboard API:

```bash
curl -fsS http://127.0.0.1:8080/api/status | python3 -m json.tool | head -80
```

For the optional passive voice build:

```bash
sudo python3 /opt/ywd-hotspot/app/lib/mmdvm_voice_build.py status
```

For complete release acceptance, also exercise the real RF path: BrandMeister reconnect, Parrot, simplex/duplex behavior as configured, and both TS1/TS2 on duplex hardware.
