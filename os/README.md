# YWD-Hotspot OS

[Detailed image build guide](../docs/OS-IMAGE-BUILD.md) · [OS development notes](../docs/OS-DEVELOPMENT.md) · [Project README](../README.md)

This directory contains the Raspberry Pi image-building infrastructure for YWD-Hotspot OS.

## One repository, one source revision

The OS builder lives beside the normal application source. A build packages the application from the **same Git commit that runs the builder**; there is no separate stale application snapshot to maintain.

The normal YWD-Hotspot install/update paths do not depend on `os/`. The `os/` subtree is only used when producing a fresh Raspberry Pi OS image.

Key rule:

> Build the image from the source revision you intend to ship. After first boot, normal application updates continue through the managed Git checkout and do not require rebuilding the image.

## Current promoted baseline

The integrated app + OS-builder baseline currently promoted on `main` is:

```text
0.1.0-alpha12.2-dev
41f1cf9fcf94b3880d5cf11fb35e2cccb6fd3afd
```

It is preserved at `dev-alpha12.2-os-integrated-known-good`.

## Current target

- Raspberry Pi Zero W / Zero WH (`armhf`)
- Raspberry Pi OS Lite / trixie
- MMDVM HAT on `/dev/serial0`
- SSD1306-style 128×64 OLED on I2C bus 1 / `0x3c`
- setup/recovery AP
- secure first-boot wizard on HTTPS 8443
- pinned MMDVM-Host + DMRGateway builds

## Safety boundaries

The image builder preserves the appliance rules proven during physical testing:

- RF services are disabled in the factory image.
- First-boot setup must complete before RF can be explicitly enabled.
- `ywd-headless-oled.service` is the sole physical OLED/I2C owner.
- The OLED renderer is injected from the current root `lib/oled.py`.
- Console branding/helpers are injected from the current root `lib/branding/` and `lib/console/` sources.
- The runtime application is copied from the current repository root.
- The managed source checkout uses a full branch refspec rather than the old single-branch clone.
- Images built from `main` follow `main`; images built from `dev` follow `dev`; experimental build branches fall back to `dev` as the normal future application channel.

## Supported build modes

### Factory/unconfigured image

Do not provide build-time Wi-Fi credentials. On first boot the appliance creates a `YWD-Hotspot-XXXX` setup AP, serves Wi-Fi onboarding at `http://10.42.0.1/`, then starts the secure HTTPS setup wizard after station Wi-Fi is online.

### Wi-Fi-preseeded image

Run:

```bash
bash os/builder/CONFIGURE-WIFI.sh
```

before `BUILD.sh`. The credential is written only to ignored `os/local/provision.env` and is embedded as the initial station profile for that build.

If the preseeded network is unavailable, the setup AP remains the recovery path.

**Wi-Fi preseeding does not preconfigure the radio/hotspot.** The secure first-boot wizard still owns callsign, DMR ID, radio settings, BrandMeister credentials, dashboard password, optional BM API key, and the final RF-enable choice.

Current `main` does not expose a supported full configuration preseed interface.

## Builder workflow

From the repository root on the build machine:

```bash
git status --short
git branch --show-current
bash os/builder/DOCTOR.sh
bash os/builder/BUILD.sh
```

`BUILD.sh` refuses tracked uncommitted changes so the image provenance always points at reproducible source.

The historical `BUILD-M4.sh` command remains only as a compatibility alias and forwards to `BUILD.sh`.

For the complete host setup, build options, first-boot flow and validation checklist, read **[docs/OS-IMAGE-BUILD.md](../docs/OS-IMAGE-BUILD.md)**.

## Local/private builder state

These paths are ignored by Git:

```text
os/.pi-gen/
os/work/
os/deploy/
os/local/
os/build/
os/cache/
```

`os/local/ywd-os-dev_ed25519` is the builder-local development SSH private key. The builder embeds only its public key in the image. Never commit or casually distribute the private key.

## Build output

Successful builds are placed under `os/deploy/` together with `SHA256SUMS-YWD-HOTSPOT-OS`. Compressed `.img.xz` output is integrity-tested with `xz -t` before the builder reports completion.

The build banner records:

- application version
- source branch
- source commit
- selected application update channel
- YWD OS identity
- pinned pi-gen commit

## Source layout

```text
os/
├── builder/
│   ├── BUILD.sh
│   ├── BUILD-M4.sh        # compatibility alias
│   ├── DOCTOR.sh
│   └── CONFIGURE-WIFI.sh
└── pi-gen/
    ├── PI-GEN-COMMIT
    └── stage2/
        ├── 10-ywd-headless
        ├── 15-ywd-network
        ├── 20-ywd-runtime
        ├── 25-ywd-firstboot
        └── 27-ywd-polish
```

The pi-gen stages contain OS-specific boot/network/setup integration. Current application and presentation assets are injected by the builder from the repository root so those components do not drift independently.

## First-boot flow

Factory/no-Wi-Fi image:

```text
boot
  ↓
YWD-Hotspot-XXXX setup AP
  ↓
http://10.42.0.1/
  ↓
station Wi-Fi handoff
  ↓
OLED six-digit setup code
  ↓
https://ywd-hotspot.local:8443/
  ↓
secure hotspot configuration
  ↓
optional explicit RF enable
  ↓
normal dashboard
```

Wi-Fi-preseeded image skips directly to the station-Wi-Fi/setup-code phase if the saved network works.

## First-boot validation

A candidate image is not a known-good checkpoint until it is physically tested on the target Pi Zero:

1. image builds and XZ integrity passes
2. Pi boots and OLED reports setup/network state
3. setup AP appears when no station Wi-Fi exists
4. Wi-Fi handoff succeeds
5. secure HTTPS first-boot wizard accepts the OLED code
6. WebUI loads the current packaged application
7. BrandMeister and RF operate normally after explicit enable
8. Parrot/normal traffic succeeds
9. `ywd-headless-oled.service` is active and `ywd-oled.service` remains inactive
10. About-page / CLI GitHub application update succeeds without rebuilding the image
11. `systemctl --failed` is clean

See **[docs/OS-IMAGE-BUILD.md](../docs/OS-IMAGE-BUILD.md)** for the full checklist and troubleshooting notes.
