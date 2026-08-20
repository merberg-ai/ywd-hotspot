# YWD-Hotspot OS

This directory contains the Raspberry Pi image-building infrastructure for YWD-Hotspot OS.

## One repository, one source revision

The OS builder now lives beside the normal application source. A build packages the application from the **same Git commit that runs the builder**; there is no separate stale application snapshot to maintain.

The normal YWD-Hotspot install/update paths do not depend on `os/`. The `os/` subtree is only used when producing a fresh Raspberry Pi OS image.

Key rule:

> Build the image from the source revision you intend to ship. After first boot, normal application updates continue through the managed Git checkout and do not require rebuilding the image.

## Current target

- Raspberry Pi Zero W / Zero WH (`armhf`)
- Raspberry Pi OS Lite / trixie
- MMDVM HAT on `/dev/serial0`
- SSD1306-style 128x64 OLED on I2C bus 1 / `0x3c`
- M3-style setup/recovery AP
- M4 secure first-boot wizard
- pinned MMDVM-Host + DMRGateway builds

## Safety boundaries

The image builder preserves the appliance rules proven during M4 testing:

- RF services are disabled in the factory image.
- First-boot setup must complete before RF can be explicitly enabled.
- `ywd-headless-oled.service` is the sole physical OLED/I2C owner.
- The OLED renderer is injected from the current root `lib/oled.py`.
- Console branding/helpers are injected from the current root `lib/branding/` and `lib/console/` sources.
- The runtime application is copied from the current repository root.
- The managed source checkout uses a full branch refspec rather than the old single-branch clone.
- Future application updates use `main` or `dev`; experimental integration branches do not become permanent appliance update channels.

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

### Optional build-time Wi-Fi

For headless development images you may preconfigure local Wi-Fi:

```bash
bash os/builder/CONFIGURE-WIFI.sh
```

Credentials are stored only under ignored `os/local/` state. Without build-time Wi-Fi, the normal setup AP handles onboarding.

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

`os/local/ywd-os-dev_ed25519` is the builder-local development SSH key. Never commit or distribute it as project source.

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

See `docs/OS-DEVELOPMENT.md` for the integration/checkpoint workflow.
