# YWD-Hotspot OS Development

YWD-Hotspot OS development is isolated on the `dev-os` branch.

## Branch model

- `main` — stable YWD-Hotspot application releases.
- `dev` — normal next-version application development.
- `dev-os` — experimental OS/image-builder work.
- `dev-os-m1.1-known-good` — frozen headless baseline.
- `dev-os-m2-known-good` — frozen runtime checkpoint.
- `dev-os-m3-known-good` — physically proven Wi-Fi setup/recovery checkpoint.

Normal application changes may be merged from `dev` into `dev-os` as needed so images can consume the current application. OS-only behavior must be gated so existing root install/update workflows remain independent of `os/`.

## Safety rules

1. Existing root-level install/update workflows must continue without any dependency on `os/`.
2. OS build scripts never modify the builder host's installed YWD-Hotspot instance.
3. Generated images, work trees, logs, Wi-Fi credentials, keys, and secrets stay out of Git history.
4. Raspberry Pi `pi-gen` is pinned by commit.
5. Each milestone is target-tested on the original Pi Zero W before the next major layer.
6. Development images use key-only SSH.
7. RF services remain disabled until real station/radio configuration is validated and RF is deliberately enabled.
8. First-boot completion is represented by an explicit persistent state marker, never inferred only from placeholder callsign/DMR values.

## Target

- Hardware: Raspberry Pi Zero W / Zero WH
- Architecture: `armhf`
- Base: Raspberry Pi OS Lite / Trixie
- Builders: Pi 5 or compatible 4K-page Linux host; x86_64 builders use qemu-user for armhf chroot work.

## Milestone history

### M1 — builder pipeline

Complete. Reproducible Raspberry Pi OS Lite armhf image creation and export.

### M1.1 — headless boot validation

Complete and frozen as `dev-os-m1.1-known-good`. The reference Pi Zero W boots as armv6l with OLED/I2C, NetworkManager Wi-Fi, mDNS, key-only SSH, sudo and zero failed units.

### M2 — hotspot runtime

Complete checkpoint frozen as `dev-os-m2-known-good`. Added YWD-Hotspot, pinned MMDVM-Host/DMRGateway, PL011 UART setup, dashboard/activity services, persistent journal, placeholder schema-3 config and RF-off safety state.

### M3 — network recovery + phone Wi-Fi setup

Complete and physically proven on the reference Pi Zero W. Frozen as `dev-os-m3-known-good`.

Validated behavior:

- No usable station Wi-Fi falls back to an open `YWD-Hotspot-xxxx` 2.4 GHz setup/recovery AP.
- AP uses channel 6 and `10.42.0.1/24` with NetworkManager shared mode.
- AP readiness is verified from actual `wlan0` AP mode + active profile + address, not merely an `nmcli` return code.
- Phone UI at `http://10.42.0.1/` configures visible, manual or hidden Wi-Fi.
- Successful credentials tear down the AP and hand off cleanly to normal station Wi-Fi.
- Failed credentials restore recovery AP mode.
- After handoff, `ywd-hotspot.local` and the normal WebUI are reachable.
- `dnsmasq-base` and `iptables` are explicitly installed for NetworkManager sharing.
- RF remains disabled throughout network onboarding.

The open AP is intentionally a short-lived development onboarding network. Its HTTP Wi-Fi credential page should be used in a physically trusted environment.

## M4 — secure first-boot appliance wizard

Current development milestone.

M4 begins only after M3 has handed `wlan0` to a normal station network. The sequence is:

```text
boot
  -> M3 Wi-Fi setup/recovery if needed
  -> station IPv4 online
  -> M4 six-digit OLED ownership code
  -> HTTPS first-boot wizard on :8443
  -> canonical validation/apply
  -> persistent setup-state.json completion marker
  -> normal dashboard
```

Security/design details:

- `/var/lib/ywd-hotspot/setup-state.json` exists only after successful first-boot completion.
- Missing/corrupt normal configuration does not by itself reopen anonymous factory setup after completion.
- `ywd-setup.service` runs as unprivileged `ywd-hotspot`, not root.
- A random six-digit code is generated in `/run/ywd-hotspot/setup.json`, displayed on the OLED, expires after 30 minutes and changes after service/reboot regeneration.
- Unlock attempts are rate-limited to five failures per minute per client address.
- Setup authorization uses an in-memory session with `Secure`, `HttpOnly`, `SameSite=Strict` cookie attributes.
- First-boot configuration is served only over HTTPS on port 8443 using a per-device self-signed certificate generated locally with OpenSSL. A browser trust warning is expected for development images.
- The setup web process can sudo only the `setup-finish` action through a root-owned dispatcher.
- `setup-finish` validates the full canonical schema and secrets before changes, stops/disables RF first, applies generated MMDVM/DMRGateway configuration, creates the permanent scrypt dashboard password, optionally saves the BrandMeister API key, and writes the completion marker last.
- BrandMeister Hotspot Security password is required when BrandMeister networking is enabled.
- Final RF enable is an explicit unchecked-by-default choice. If not selected, MMDVM-Host and DMRGateway remain disabled/inactive.
- The normal port-8080 dashboard redirects to the wizard only on an M4 OS image while factory setup is incomplete; normal/manual YWD-Hotspot installs are not affected.

Wizard pages cover dashboard security, callsign/base DMR ID/ESSID, station description/URL/location/coordinates, frequency/color code/modem levels and advanced modem fields, BrandMeister settings/secrets, OLED/appliance settings, a redacted review page and the final RF gate.

Expected M4 OLED after Wi-Fi handoff:

```text
YWD HOTSPOT OS
M4 FIRST BOOT
SETUP REQUIRED
CODE 482731
<SSID>
<station IPv4>
HTTPS PORT 8443
RF OFF
```

### Shutdown OLED

The OS-level OLED handles SIGTERM/SIGINT and writes a shutdown screen before exiting:

```text
YWD HOTSPOT OS
SHUTTING DOWN
PLEASE WAIT

RF SERVICES STOPPING
SYSTEM HALTING
```

The OLED retains this state while Linux continues shutting down.

## Current milestone sequence

1. **M1 — complete:** reproducible Raspberry Pi OS Lite image.
2. **M1.1 — complete:** headless OLED/Wi-Fi/mDNS/SSH validation.
3. **M2 — complete checkpoint:** hotspot runtime baked in, RF safe by default.
4. **M3 — complete checkpoint:** phone Wi-Fi setup/recovery and successful station handoff.
5. **M4 — current:** secure first-boot ownership/configuration wizard + shutdown OLED.
6. Calibration/setup polish and controlled transition to the normal runtime OLED.
7. Production/release metadata, signing/checksums and eventual imager integration.
