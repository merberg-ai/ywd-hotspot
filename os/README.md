# YWD-Hotspot OS

This directory contains the Raspberry Pi image-building infrastructure for YWD-Hotspot OS.

## One repository, one source revision

The OS builder lives beside the normal application source. A build packages the application from the **same Git commit that runs the builder**; there is no separate stale application snapshot to maintain.

The normal YWD-Hotspot install/update paths do not depend on `os/`. The `os/` subtree is only used when producing a fresh Raspberry Pi OS image.

Key rule:

> Build the image from the source revision you intend to ship. After first boot, normal application updates continue through the managed Git checkout and do not require rebuilding the image.

## Current target

- Raspberry Pi Zero W / Zero WH (`armhf`)
- Raspberry Pi OS Lite / trixie
- MMDVM HAT on `/dev/serial0`
- simplex or duplex DMR configuration
- SSD1306-style 128x64 OLED on I2C bus 1 / `0x3c`
- setup/recovery AP when station Wi-Fi is unavailable
- secure first-boot wizard for incomplete images
- optional factory preconfiguration for ready-to-run images
- pinned MMDVM-Host + DMRGateway builds

## Interactive builder

The preferred development entry point on `dev-builder` is the Textual builder:

```bash
bash os/builder/YWD-BUILDER.sh
```

The launcher creates a builder-only Python virtual environment under ignored `os/local/` state and pins the tested Textual version. The interface uses the same dark/cyan/blue visual language as the dashboard and exposes configuration pages for:

- image identity and Wi-Fi;
- station identity/location;
- simplex/duplex MMDVM and RF settings;
- BrandMeister master, Hotspot Security password and API key;
- dashboard control password;
- OLED presentation;
- instrumentation/meters;
- web and maintenance settings, including explicit RF autostart;
- profile validation, Builder Doctor and image build output.

The builder profile is stored only at:

```text
os/local/builder-profile.json
```

It may contain Wi-Fi and hotspot credentials and must never be committed or shared. Generated provisioning material also remains under ignored `os/local/generated/` state.

### Blank/default values and first boot

The builder deliberately supports both partial and complete images.

A **partial/default profile** writes canonical non-secret configuration hints into the image. Blank required identity/security values remain deferred. On boot:

1. configured Wi-Fi is tried automatically, or the normal YWD setup AP appears when Wi-Fi is blank/unavailable;
2. the secure OLED-code HTTPS first-boot wizard remains enabled;
3. the wizard starts with the builder-supplied canonical settings already available as its configuration baseline;
4. RF remains disabled until setup is completed.

A **fully preconfigured profile** requires a real callsign/base DMR ID, a dashboard password, and a BrandMeister Hotspot Security password when BrandMeister is enabled. The image carries a root-only one-shot provisioning payload. On first boot that payload is validated/applied through the same privileged `setup-finish` path used by the secure browser wizard. When it succeeds, the normal `setup-state.json` is created before the wizard starts, so the hotspot wizard is skipped.

Wi-Fi is independent from hotspot completion: a fully configured hotspot may still leave Wi-Fi blank. In that case the setup AP handles Wi-Fi onboarding, but the hotspot configuration wizard remains skipped after network handoff.

If factory preconfiguration fails for any reason, reusable payload secrets are removed and the normal secure first-boot wizard remains available as the fallback.

RF autostart is always an explicit builder option and defaults off.

## Command-line builder paths

The original engine remains available for regression and low-level work:

```bash
bash os/builder/DOCTOR.sh
bash os/builder/BUILD.sh
```

A saved Textual profile can be compiled and built without opening the UI:

```bash
python3 os/builder/PREPARE-PROFILE.py
bash os/builder/RUN-BUILD.sh
```

`RUN-BUILD.sh` creates short-lived ignored overlays for pi-gen, invokes the existing `BUILD.sh` engine, and removes those overlays when the build exits. This keeps credentials out of tracked source while leaving the proven build engine largely untouched.

The historical `CONFIGURE-WIFI.sh` remains usable for the old Wi-Fi-only build path while `dev-builder` is under test.

## Safety boundaries

The image builder preserves the appliance rules proven during earlier OS testing:

- MMDVM-Host remains the only modem/RF owner.
- RF services are disabled in the factory image unless a completed profile explicitly requests RF autostart.
- `ywd-headless-oled.service` is the sole physical OLED/I2C owner.
- the OLED renderer is injected from the current root `lib/oled.py`.
- console branding/helpers are injected from current root source.
- the runtime application is copied from the current repository revision.
- complete factory provisioning uses the existing trusted setup finalizer instead of maintaining a second configuration implementation.
- failed or partial factory provisioning falls back to the existing setup AP + secure wizard flow.
- normal GitHub application updates remain available after imaging.

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

Temporary provisioning overlays inside the custom pi-gen stages are explicitly ignored as well and are deleted by `RUN-BUILD.sh` after the build.

`os/local/ywd-os-dev_ed25519` is the builder-local development SSH key. Never commit or distribute it as project source.

## Build output

Successful builds are placed under `os/deploy/` together with `SHA256SUMS-YWD-HOTSPOT-OS`. Compressed `.img.xz` output is integrity-tested with `xz -t` before the builder reports completion.

## Source layout

```text
os/
├── builder/
│   ├── YWD-BUILDER.sh       # Textual launcher
│   ├── ywd_builder.py       # interactive UI
│   ├── profile_model.py     # canonical profile compiler
│   ├── PREPARE-PROFILE.py   # CLI profile preparation
│   ├── RUN-BUILD.sh         # profiled build wrapper
│   ├── BUILD.sh             # existing image-build engine
│   ├── DOCTOR.sh
│   └── CONFIGURE-WIFI.sh    # legacy Wi-Fi-only helper
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

## Physical validation

A candidate image is not a known-good checkpoint until it is physically tested on the target Pi Zero. For `dev-builder` we test both paths:

### Partial/default image

1. image builds and XZ integrity passes;
2. Pi boots and OLED reports setup/network state;
3. setup AP appears when Wi-Fi is blank;
4. configured Wi-Fi handoff works when supplied;
5. HTTPS first-boot wizard still requires the OLED code;
6. builder-supplied settings appear as the setup baseline;
7. completing setup generates working MMDVM/DMRGateway configuration;
8. RF remains off until explicitly enabled.

### Fully preconfigured image

1. factory preconfiguration finalizer succeeds;
2. `setup-state.json` is complete before the secure wizard starts;
3. dashboard password and optional BrandMeister API key are installed;
4. secure hotspot wizard does not run;
5. Wi-Fi preconfiguration works, or setup AP performs Wi-Fi-only onboarding when Wi-Fi was left blank;
6. RF remains off by default, or starts only when RF autostart was explicitly selected;
7. BrandMeister, Parrot and normal duplex/simplex RF paths are physically verified.

See `docs/OS-DEVELOPMENT.md` for branch/checkpoint workflow.
