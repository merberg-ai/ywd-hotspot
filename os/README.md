# YWD-Hotspot OS

This directory contains the experimental image-building infrastructure for YWD-Hotspot OS.

## Safety boundary

The normal YWD-Hotspot install and update paths do not depend on anything under `os/`.

- `main` remains the stable application branch.
- `dev` remains normal application development.
- `dev-os` is the isolated OS/image-development branch.

OS work should consume the current application from this repository, but OS-only changes must not be merged back into `dev` wholesale. Reusable application changes should be moved back deliberately as focused commits or pull requests.

## Current target

The first target is Raspberry Pi Zero W / Zero WH (`armhf`) using a Raspberry Pi OS Lite base.

Milestone 1 proved that the Raspberry Pi 5 builder can create and compress a valid Lite image. Milestone 1.1 adds only the pieces needed to validate a headless Pi Zero boot:

- SSD1306 128x64 I2C OLED boot/network status at bus 1, address `0x3c`.
- Optional local Wi-Fi provisioning through NetworkManager.
- A builder-generated ed25519 key for key-only SSH to the fixed `ywd` test user.
- Hostname `ywd-hotspot` and mDNS support for `ywd-hotspot.local`.

The full MMDVMHost, DMRGateway, WebUI, RF stack, setup AP, and recovery AP are intentionally not part of M1.1 yet.

## Builder workflow

On the Pi 5:

```bash
git switch dev-os
git pull
bash os/builder/DOCTOR.sh
```

Optional Wi-Fi injection for a headless test image:

```bash
bash os/builder/CONFIGURE-WIFI.sh
```

Then build:

```bash
bash os/builder/BUILD.sh
```

The local Wi-Fi credentials and generated SSH private key live only under `os/local/`, which is ignored by Git. After successful Wi-Fi provisioning on the target, the temporary plaintext provisioning file is removed from the image; NetworkManager retains its normal root-only connection profile.

## Expected M1.1 OLED state

A successful userspace boot should produce a display similar to:

```text
YWD HOTSPOT OS
M1.1 HEADLESS

BOOT OK
WIFI ONLINE
<SSID>
<IPv4 address>
<temp> YWD-HOTSPOT.LOCAL
```

Without build-time Wi-Fi configuration, the OLED should show `WIFI NO CONFIG` and `NO IP`. That still proves the target booted far enough to start the M1.1 status service.

## Layout

- `builder/` — host-side build, doctor, and local Wi-Fi configuration helpers.
- `pi-gen/` — pinned upstream pi-gen metadata plus YWD custom substages.
- `local/` — generated builder-only credentials and keys; never committed.
- `overlay/` — reserved for broader target root-filesystem overlays in later milestones.
- `firstboot/` — first-boot service and provisioning logic in later milestones.
- `network/` — setup/recovery AP logic in later milestones.
- `provisioning/` — provisioning schema and helpers in later milestones.
- `docs/` — OS-specific design and build notes.

Generated images, build work directories, caches, deploy artifacts, and local secrets are intentionally excluded from Git.
