# YWD-Hotspot OS Development

YWD-Hotspot OS development is isolated on the `dev-os` branch.

## Branch model

- `main` — stable YWD-Hotspot application releases.
- `dev` — normal next-version application development.
- `dev-os` — experimental OS/image-builder work.

Normal application changes may be merged from `dev` into `dev-os` as needed so images can consume the current application. Do not merge `dev-os` wholesale back into `dev`. If OS work produces a reusable application feature, move that feature back as a focused commit or pull request.

## Safety rules

1. Existing root-level install/update workflows must continue to work without any dependency on `os/`.
2. OS build scripts must never modify the builder host's installed YWD-Hotspot instance.
3. Generated images, work trees, caches, logs, release payloads, Wi-Fi credentials, and private keys stay out of Git history.
4. Upstream build tooling such as Raspberry Pi `pi-gen` is pinned by commit rather than vendored wholesale into this repository.
5. Each milestone must be boot-tested on the target hardware before the next major layer is added.
6. Development images use key-only SSH; no shared/default password is shipped.

## Initial target

- Hardware: Raspberry Pi Zero W / Zero WH
- Architecture: `armhf`
- Base: Raspberry Pi OS Lite / Trixie
- Builder host: Raspberry Pi 5 or another suitably fast Debian-based Linux system with a 4K-page kernel for armhf builds

## Current progress

### Milestone 1 — builder pipeline

Complete. The Pi 5 produced a valid compressed Raspberry Pi OS Lite armhf image. The initial run exposed and fixed an export-stage bug caused by skipped desktop stages registering `EXPORT_IMAGE`; the builder now explicitly limits pi-gen to stages 0, 1, and 2.

### Milestone 1.1 — headless boot validation

Current. This image remains intentionally smaller than a real YWD-Hotspot appliance and adds only:

- I2C enabled for the reference hardware.
- Minimal SSD1306 OLED boot/network status independent of the full application.
- Optional build-local Wi-Fi provisioning.
- Fixed `ywd` development user with builder-generated ed25519 public-key authentication only.
- SSH enabled with password authentication disabled.
- mDNS hostname `ywd-hotspot.local`.

Builder-local secrets live under ignored `os/local/`. The Wi-Fi helper writes `os/local/provision.env`; the M1.1 stage copies it into the image only for initial connection. After NetworkManager successfully creates the saved connection, the temporary plaintext provisioning file is removed.

## Planned milestone sequence

1. **M1 — complete:** produce a reproducible vanilla Raspberry Pi OS Lite image.
2. **M1.1 — current:** prove headless boot using OLED, optional Wi-Fi, and key-only SSH.
3. Inject prebuilt YWD-Hotspot, MMDVMHost, and DMRGateway components.
4. Add first-boot provisioning state.
5. Add setup AP mode when Wi-Fi is not configured.
6. Add WebUI Wi-Fi onboarding.
7. Add recovery AP behavior when saved Wi-Fi cannot be reached.
8. Add the full YWD-Hotspot first-boot configuration wizard.
9. Add release metadata, checksums, and eventual imager integration.

The M1.1 OLED is deliberately a small independent validation service. Once the full YWD runtime is injected, its boot/network states should be folded into the normal YWD status/OLED architecture instead of maintaining two competing display implementations.
