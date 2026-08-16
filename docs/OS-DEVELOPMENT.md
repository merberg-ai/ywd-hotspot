# YWD-Hotspot OS Development

YWD-Hotspot OS development is isolated on the `dev-os` branch.

## Branch model

- `main` — stable YWD-Hotspot application releases.
- `dev` — normal next-version application development.
- `dev-os` — experimental OS/image-builder work.
- `dev-os-m1.1-known-good` — frozen known-good M1.1 headless baseline.

Normal application changes may be merged from `dev` into `dev-os` as needed so images can consume the current application. Do not merge `dev-os` wholesale back into `dev`. If OS work produces a reusable application feature, move that feature back as a focused commit or pull request.

## Safety rules

1. Existing root-level install/update workflows must continue to work without any dependency on `os/`.
2. OS build scripts must never modify the builder host's installed YWD-Hotspot instance.
3. Generated images, work trees, caches, logs, release payloads, Wi-Fi credentials, and private keys stay out of Git history.
4. Upstream build tooling such as Raspberry Pi `pi-gen` is pinned by commit rather than vendored wholesale into this repository.
5. Each milestone must be boot-tested on the target hardware before the next major layer is added.
6. Development images use key-only SSH; no shared/default SSH password is shipped.
7. RF services remain disabled until real station/radio configuration is explicitly applied and RF is deliberately enabled.

## Initial target

- Hardware: Raspberry Pi Zero W / Zero WH
- Architecture: `armhf`
- Base: Raspberry Pi OS Lite / Trixie
- Builder host: Raspberry Pi 5 or another suitably fast Debian-based Linux system with a 4K-page kernel for armhf builds

## Current progress

### Milestone 1 — builder pipeline

Complete. The Pi 5 produced a valid compressed Raspberry Pi OS Lite armhf image. The initial run exposed and fixed an export-stage bug caused by skipped desktop stages registering `EXPORT_IMAGE`; the builder now explicitly limits pi-gen to stages 0, 1, and 2.

### Milestone 1.1 — headless boot validation

Complete and frozen as `dev-os-m1.1-known-good`.

Validated on the reference Raspberry Pi Zero W:

- Raspberry Pi OS Lite / Raspbian 13 Trixie boots as `armv6l`.
- Wi-Fi provisioning succeeds through NetworkManager.
- `ywd-hotspot.local` resolves over mDNS.
- Key-only SSH works with the builder-local ed25519 key.
- SSD1306 OLED is detected on I2C bus 1 at `0x3c`.
- The independent headless OLED service runs continuously.
- The temporary Wi-Fi provisioner exits successfully after creating the saved NetworkManager connection.
- `systemctl --failed` reports zero failed units on the known-good test image.

Builder-local secrets live under ignored `os/local/`. The Wi-Fi helper writes `os/local/provision.env`; the image removes its temporary plaintext provisioning copy after NetworkManager successfully creates the saved connection.

### Milestone 2 — hotspot runtime

Current development milestone.

M2 layers the actual hotspot runtime onto the proven M1.1 base while deliberately preserving a safe RF-off first boot:

- Current YWD-Hotspot application and WebUI under `/opt/ywd-hotspot/app`.
- Git-managed source checkout under `/opt/ywd-hotspot/repo` for the existing updater workflow.
- Pinned MMDVM-Host and DMRGateway built inside the armhf image rootfs.
- Pi Zero W PL011 UART configuration: `enable_uart=1`, Bluetooth disabled, serial-console tokens removed.
- YWD application user, permissions, sudoers helper, diagnostics and systemd units.
- Canonical schema-3 placeholder config with `NOCALL`, placeholder DMR ID, BrandMeister disabled and `rf_autostart=false`.
- Generated MMDVM-Host and DMRGateway INI files present for inspection, but both RF services disabled.
- YWD activity collector and dashboard enabled.
- Persistent journal enabled with a bounded 100 MB limit.
- Full YWD OLED runtime shipped but left disabled until real hotspot configuration is applied.
- The independent OS OLED remains active and displays `M2 RUNTIME`, WebUI state, RF-off state, Wi-Fi and IP information.
- Build provenance records the exact source branch/commit embedded into the image.

Expected M2 first-boot state:

```text
ywd-headless-oled.service   active
ywd-activity.service        active
ywd-dashboard.service       active
ywd-mmdvmhost.service       disabled/inactive
ywd-dmrgateway.service      disabled/inactive
ywd-oled.service            disabled/inactive
```

WebUI should be reachable at `http://ywd-hotspot.local:8080/`. Configuration write controls remain locked until a local web-control password is explicitly set.

## Planned milestone sequence

1. **M1 — complete:** reproducible vanilla Raspberry Pi OS Lite image.
2. **M1.1 — complete:** headless boot validation with OLED, Wi-Fi, mDNS and key-only SSH.
3. **M2 — current:** bake in YWD-Hotspot, MMDVM-Host, DMRGateway, WebUI and hardware setup with RF disabled.
4. Add first-boot provisioning state and transition from the OS OLED to the normal YWD OLED after setup.
5. Add setup AP mode when Wi-Fi is not configured.
6. Add WebUI Wi-Fi onboarding.
7. Add recovery AP behavior when saved Wi-Fi cannot be reached.
8. Add the full YWD-Hotspot first-boot configuration wizard.
9. Add release metadata, checksums, signing and eventual imager integration.
