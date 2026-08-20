# YWD-Hotspot OS

This directory contains the Raspberry Pi image-building infrastructure for YWD-Hotspot OS.

## One repository, one source revision

The OS builder lives beside the normal application source. A build packages the application from the **same Git commit that runs the builder**; there is no separate stale application snapshot to maintain.

Normal YWD-Hotspot installs and updates do not depend on `os/`. The `os/` subtree is used only to produce fresh Raspberry Pi OS images.

> Build the image from the source revision you intend to ship. After first boot, normal application updates continue through the managed Git checkout and do not require rebuilding the image.

## Current target

- Raspberry Pi Zero W / Zero WH (`armhf`)
- Raspberry Pi OS Lite / trixie
- simplex or duplex MMDVM HAT on `/dev/serial0`
- SSD1306-style 128x64 OLED on I2C bus 1 / `0x3c`
- setup/recovery AP when station Wi-Fi is unavailable
- secure first-boot wizard for incomplete images
- optional factory preconfiguration for ready-to-run images
- pinned MMDVM-Host + DMRGateway builds

## Interactive builder

The preferred `dev-builder` entry point is deliberately terminal-simple and SSH-safe:

```bash
bash os/builder/YWD-BUILDER.sh
```

The interface uses plain Bash prompts, ASCII separators and optional ANSI colors. It does **not** use mouse reporting, alternate-screen mode or Unicode-heavy terminal widgets, so it remains usable through PuTTY, phone SSH clients and serial-style terminals.

The main menu exposes:

- image identity and Wi-Fi;
- station identity/location;
- simplex/duplex MMDVM and RF settings;
- BrandMeister master, Hotspot Security password and API key;
- dashboard control password;
- OLED presentation;
- instrumentation/meters;
- web and maintenance settings, including explicit RF autostart;
- redacted configuration review;
- profile validation;
- Builder Doctor;
- full image build.

The Bash frontend is intentionally thin. Profile normalization, validation, redaction and provisioning decisions live in the shared Python profile engine:

```text
os/builder/profile_model.py
os/builder/PROFILE-CLI.py
```

That same engine is intended to back the future local web builder and desktop controller so every frontend produces the same image configuration.

## Private builder state

The builder profile is stored only at:

```text
os/local/builder-profile.json
```

It may contain Wi-Fi and hotspot credentials and must never be committed or shared. Generated provisioning material remains under ignored `os/local/generated/` state.

For optional fields, the shell UI lets the operator keep defaults or clear values. Secret fields are never shown by the Review page; they are reported only as `configured` or `blank`.

## Partial/default vs fully preconfigured images

The builder deliberately supports both paths.

A **partial/default profile** writes canonical non-secret configuration hints into the image. Missing required identity/security values remain deferred. On boot:

1. configured Wi-Fi is tried automatically, or the normal YWD setup AP appears when Wi-Fi is blank/unavailable;
2. the secure OLED-code HTTPS first-boot wizard remains enabled;
3. the wizard starts from the builder-supplied canonical configuration baseline;
4. RF remains disabled until setup is completed.

A **fully preconfigured profile** requires a real callsign/base DMR ID, a dashboard password, and a BrandMeister Hotspot Security password when BrandMeister is enabled. The image carries a root-only one-shot provisioning payload. On first boot that payload is validated/applied through the same privileged `setup-finish` path used by the secure browser wizard. When it succeeds, the normal `setup-state.json` exists before the wizard can start, so the hotspot wizard is skipped.

Wi-Fi is independent from hotspot completion. A fully configured hotspot may leave Wi-Fi blank; the setup AP then performs Wi-Fi-only onboarding while the hotspot configuration wizard remains skipped after network handoff.

If factory preconfiguration fails, reusable payload secrets are removed and the normal secure first-boot wizard remains available as fallback.

RF autostart is always explicit and defaults off.

## Command-line engine

The lower-level builder paths remain available for regression and automation:

```bash
bash os/builder/DOCTOR.sh
python3 os/builder/PREPARE-PROFILE.py
bash os/builder/RUN-BUILD.sh
bash os/builder/BUILD.sh
```

`RUN-BUILD.sh` compiles the saved profile, creates short-lived ignored overlays for pi-gen, invokes `BUILD.sh`, and removes those overlays when the build exits.

The historical `CONFIGURE-WIFI.sh` remains temporarily available for the older Wi-Fi-only build path while `dev-builder` is under test.

## Safety boundaries

- MMDVM-Host remains the only modem/RF owner.
- RF services are disabled in the factory image unless a completed profile explicitly requests RF autostart.
- `ywd-headless-oled.service` remains the sole physical OLED/I2C owner.
- the OLED renderer is injected from current root `lib/oled.py`.
- console branding/helpers are injected from current root source.
- the runtime application is copied from the current repository revision.
- complete factory provisioning uses the existing trusted setup finalizer rather than a second configuration implementation.
- failed or partial factory provisioning falls back to the existing setup AP + secure wizard flow.
- normal GitHub application updates remain available after imaging.

## Ignored/local paths

```text
os/.pi-gen/
os/work/
os/deploy/
os/local/
os/build/
os/cache/
```

Temporary provisioning overlays inside the custom pi-gen stages are also ignored and deleted by `RUN-BUILD.sh` after the build.

`os/local/ywd-os-dev_ed25519` is a builder-local development SSH key. Never commit or distribute it as project source.

## Build output

Successful builds are placed under `os/deploy/` together with `SHA256SUMS-YWD-HOTSPOT-OS`. Compressed `.img.xz` output is integrity-tested with `xz -t` before the builder reports completion.

## Source layout

```text
os/
├── builder/
│   ├── YWD-BUILDER.sh       # SSH-safe interactive shell frontend
│   ├── PROFILE-CLI.py       # frontend/profile adapter + redacted review
│   ├── profile_model.py     # canonical builder profile compiler
│   ├── PREPARE-PROFILE.py   # profile -> build overlay preparation
│   ├── RUN-BUILD.sh         # profiled build wrapper
│   ├── BUILD.sh             # image-build engine
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

## Planned frontends

Once the shell/profile engine is physically proven, the next frontend is a **local web builder** hosted by the Linux build machine. It will use the same profile model and build engine while visually matching the YWD-Hotspot dashboard. A later Windows/Linux desktop controller can use the same backend contract rather than implementing image logic again.

## Physical validation

A candidate image is not a known-good checkpoint until it is physically tested on the target Pi Zero. `dev-builder` must validate both paths.

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
