# YWD-Hotspot OS Development

YWD-Hotspot OS development is isolated on the `dev-os` branch.

## Branch model

- `main` — stable YWD-Hotspot application releases.
- `dev` — normal next-version application development.
- `dev-os` — experimental OS/image-builder work.
- `dev-os-m1.1-known-good` — frozen known-good headless baseline.
- `dev-os-m2-known-good` — frozen M2 runtime checkpoint before M3 networking work.

Normal application changes may be merged from `dev` into `dev-os` as needed so images can consume the current application. Do not merge `dev-os` wholesale back into `dev`. If OS work produces a reusable application feature, move that feature back as a focused commit or pull request.

## Safety rules

1. Existing root-level install/update workflows must continue to work without any dependency on `os/`.
2. OS build scripts must never modify the builder host's installed YWD-Hotspot instance.
3. Generated images, work trees, caches, logs, release payloads, Wi-Fi credentials, and private keys stay out of Git history.
4. Raspberry Pi `pi-gen` is pinned by commit rather than vendored wholesale.
5. Each milestone is boot-tested on the target Pi Zero W before adding the next major layer.
6. Development images use key-only SSH; no shared/default SSH password is shipped.
7. RF services remain disabled until real station/radio configuration is explicitly applied and RF is deliberately enabled.

## Target

- Hardware: Raspberry Pi Zero W / Zero WH
- Architecture: `armhf`
- Base: Raspberry Pi OS Lite / Trixie
- Builder host: Raspberry Pi 5 or a faster compatible Linux builder with a 4K-page kernel for armhf pi-gen builds

## Milestone history

### M1 — builder pipeline

Complete. The Pi 5 produced a valid compressed Raspberry Pi OS Lite armhf image. The initial export-stage issue was fixed by explicitly limiting pi-gen to stages 0, 1, and 2.

### M1.1 — headless boot validation

Complete and frozen as `dev-os-m1.1-known-good`.

Validated on the reference Pi Zero W:

- Raspbian 13 Trixie boots as `armv6l`.
- Build-time Wi-Fi provisioning succeeds through NetworkManager.
- `ywd-hotspot.local` resolves over mDNS.
- Key-only SSH works with the builder-local ed25519 key.
- SSD1306 OLED is detected on I2C bus 1 at `0x3c`.
- The headless OLED service stays active.
- The one-shot Wi-Fi provisioner completes successfully.
- `systemctl --failed` reports zero failed units.

### M2 — hotspot runtime

Runtime injection/build and target boot were proven before M3 networking work began. The checkpoint is frozen as `dev-os-m2-known-good`.

M2 added:

- Current YWD-Hotspot app and WebUI under `/opt/ywd-hotspot/app`.
- Git-managed source checkout under `/opt/ywd-hotspot/repo`.
- Pinned MMDVM-Host and DMRGateway built inside the armhf image rootfs.
- Pi Zero W PL011 UART configuration.
- YWD user, permissions, sudoers helper, diagnostics and systemd units.
- Schema-3 placeholder config with BrandMeister disabled and `rf_autostart=false`.
- Activity collector, dashboard, persistent journal and build provenance.
- RF services disabled/inactive at first boot.

The M2 target boot exposed an important appliance problem: a headless hotspot with no usable IPv4 address leaves the user with no recovery path. M3 addresses that directly.

## M3 — network recovery + phone Wi-Fi setup

Current development milestone.

M3 adds a dedicated OS network manager for the Pi Zero W's single `wlan0` interface:

- Consumes optional builder-injected Wi-Fi credentials on first boot.
- Tries existing saved station profiles for a bounded period.
- If no Wi-Fi configuration exists, enters **Setup AP** mode.
- If saved Wi-Fi exists but cannot provide a usable IPv4 address, enters **Recovery AP** mode.
- If a previously healthy station connection disappears for 90 seconds, enters Recovery AP mode.
- Setup/recovery SSID is `YWD-Hotspot-xxxx`, where `xxxx` comes from the Wi-Fi MAC address.
- Setup/recovery AP is intentionally **open** for simple phone onboarding; no AP password is required or displayed.
- AP is pinned to 2.4 GHz channel 6 with Wi-Fi power saving disabled while hosting.
- AP address is fixed at `10.42.0.1/24` using NetworkManager shared mode.
- The network manager verifies that `wlan0` is actually in AP mode, the `YWD Setup AP` profile is active, and `10.42.0.1` is assigned before reporting the AP as ready.
- AP startup is retried automatically if activation or post-start verification fails; the OLED shows starting/failed/retrying states instead of falsely claiming the AP is available.
- Phone setup UI is served at `http://10.42.0.1/` only after the AP verifies successfully.
- The setup page shows visible networks captured before AP activation and also supports manual/hidden SSIDs.
- Submitting credentials tears down the AP and tries station mode.
- Successful credentials remain as a normal NetworkManager profile and the temporary builder credential file is removed.
- Failed credentials automatically restore Recovery AP mode.
- Once AP fallback is active it does not flap between AP/station modes on its own; it stays available until the user submits credentials or reboots.
- The OLED consumes `/run/ywd-hotspot-os/network.json` and displays online/waiting/setup/recovery/connecting/AP-failure state, AP SSID, open/channel status, and setup address.
- The normal YWD WebUI remains on port 8080; the recovery setup UI uses port 80.
- RF services and BrandMeister remain disabled throughout M3 networking operations.

Expected verified fallback display:

```text
YWD HOTSPOT OS
M3 NETWORK
WEB 8080 RF OFF
RECOVERY AP
YWD-Hotspot-xxxx
OPEN WIFI CH 6
10.42.0.1
OPEN 10.42.0.1
```

### Open setup-AP security note

The open AP is a deliberate usability choice for short-lived local provisioning. Because the setup page is plain HTTP on an open WLAN, the Wi-Fi password submitted to `10.42.0.1` is not protected by link-layer encryption. Use setup/recovery mode in a trusted physical environment and complete provisioning promptly. A later production-hardening milestone may replace this development behavior with a more secure pairing/onboarding mechanism without returning to an unreadable long OLED password.

## Current milestone sequence

1. **M1 — complete:** reproducible Raspberry Pi OS Lite image.
2. **M1.1 — complete:** headless OLED/Wi-Fi/mDNS/SSH validation.
3. **M2 — checkpoint:** bake in YWD-Hotspot + pinned RF runtime with RF disabled.
4. **M3 — current:** setup AP, recovery AP, phone Wi-Fi onboarding, network-state OLED.
5. Add persistent first-boot appliance state and transition from OS setup UI into the full YWD configuration wizard.
6. Add complete callsign/DMR/BrandMeister/radio first-boot wizard with explicit RF-enable gate.
7. Add release metadata, checksums/signing and eventual YWD-Hotspot Imager integration.
