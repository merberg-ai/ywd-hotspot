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
3. Generated images, work trees, caches, logs, and release payloads stay out of Git history.
4. Upstream build tooling such as Raspberry Pi `pi-gen` should be pinned by commit rather than vendored wholesale into this repository.
5. Each milestone must be boot-tested on the target hardware before the next major layer is added.

## Initial target

- Hardware: Raspberry Pi Zero W / Zero WH
- Architecture: `armhf`
- Base: Raspberry Pi OS Lite
- Builder host: Raspberry Pi 5 or another suitably fast Linux system

## Milestone sequence

1. Produce a reproducible vanilla Raspberry Pi OS Lite image.
2. Boot-test that image on the reference Pi Zero W.
3. Inject prebuilt YWD-Hotspot, MMDVMHost, and DMRGateway components.
4. Add first-boot provisioning state.
5. Add setup AP mode when Wi-Fi is not configured.
6. Add WebUI Wi-Fi onboarding.
7. Add recovery AP behavior when saved Wi-Fi cannot be reached.
8. Add the full YWD-Hotspot first-boot configuration wizard.
9. Add release metadata, checksums, and eventual imager integration.

The first milestone intentionally contains no hotspot-specific runtime changes. Its sole purpose is to prove the image-builder pipeline safely and repeatably.
