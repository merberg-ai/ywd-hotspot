# YWD-Hotspot OS

This directory contains the Raspberry Pi appliance-image builder for YWD-Hotspot.

The builder packages the application from the **same Git commit that runs the build**. Installed appliances then use normal GitHub-managed application updates; they do not need another SD-card image for routine upgrades.

## Target

- Raspberry Pi Zero W / Zero WH (`armhf`)
- Raspberry Pi OS Lite / trixie
- simplex or duplex MMDVM HAT on `/dev/serial0`
- SSD1306-compatible 128×64 OLED on I2C bus 1 / `0x3c`
- YWD setup/recovery AP when station Wi-Fi is unavailable
- OLED-code protected first-boot setup
- pinned MMDVM-Host + DMRGateway runtime

## Builder interfaces

```text
os/builder/YWD-BUILDER.sh              interactive SSH-safe builder UI
os/builder/PROFILE-CLI.py              hotspot/image profile
os/builder/SYSTEM-CLI.py               OS/system profile
os/builder/MMDVM-RUNTIME.py            MMDVM runtime selection
os/builder/RUNTIME-CACHE.py            compile-cache management
os/builder/DOCTOR.sh                   host/source preflight
os/builder/RUN-BUILD.sh                normal profile-driven build
os/builder/BUILD-PUBLIC-RELEASE.sh     public factory release build
os/builder/PUBLIC-RELEASE-CHECK.py     fail-closed factory checker
os/builder/RELEASE-ARTIFACTS.py        release metadata/readme generator
```

## Private builder state

Private/local builder state lives below ignored `os/local/` paths. `builder-profile.json` may contain Wi-Fi, station identity and credentials. `mmdvm-runtime.json` stores the local builder's runtime preference. Runtime compile caches also live below `os/local`.

These files are not public release content.

## Normal/personalized image

Review settings:

```bash
python3 os/builder/PROFILE-CLI.py review
python3 os/builder/SYSTEM-CLI.py review
python3 os/builder/MMDVM-RUNTIME.py review
```

Validate/build:

```bash
bash os/builder/DOCTOR.sh
python3 os/builder/PROFILE-CLI.py validate
bash os/builder/RUN-BUILD.sh
```

Normal images may intentionally use Wi-Fi preconfiguration, station settings, imported backups, SSH key-only access, or fully preconfigured hotspot setup. Those are private/custom artifacts, not the GitHub release image.

## MMDVM runtime variants

### YWD Extended — default/recommended

Exact pinned upstream MMDVM-Host plus the verified YWD extension patch. Provides passive DMR voice/RX Monitor capability and a platform for future plugins that explicitly declare extension requirements.

### Stock Upstream

Exact pinned upstream MMDVM-Host without YWD extensions.

Select:

```bash
python3 os/builder/MMDVM-RUNTIME.py set ywd-extended
python3 os/builder/MMDVM-RUNTIME.py set upstream
```

The two variants have separate compile-cache identities. DMRGateway remains pinned upstream.

## Persistent runtime compile cache

Status:

```bash
python3 os/builder/RUNTIME-CACHE.py status
```

The cache is reused only when strict build signatures match. For YWD Extended the signature includes upstream commit, patch API/hash, architecture, compiler and relevant flags. Stock uses its own namespace/signature.

A one-time clean rebuild can be requested through the runtime-cache helper without deleting all cached history.

## Public GitHub release image

For `0.2.0-rc1`, use only:

```bash
bash os/builder/BUILD-PUBLIC-RELEASE.sh
```

The wrapper requires the release branch/version and a clean tracked checkout. It saves the developer's local builder profile/runtime preference, resets to release defaults, builds, then restores the original local state.

### Factory-image invariant

The public image contains no operator/builder preconfiguration:

```text
Wi-Fi credentials       none
Callsign/DMR ID          none
BM credentials/API key  none
Dashboard password      none
Imported settings       none
RF autostart             OFF
SSH                      disabled
Builder SSH key          not embedded
Update channel           main
MMDVM runtime            ywd-extended
```

`PUBLIC-RELEASE-CHECK.py` validates both the source profile and generated first-boot payload. It refuses release creation if Wi-Fi provisioning, a completed hotspot provisioning payload, imported restore payload, credentials, identity, RF autostart, non-default hotspot config, or SSH enablement is present.

The public image deliberately uses the product-default **YWD Extended** MMDVM runtime. That is a shipped software capability, not operator preconfiguration.

## Public first-boot path

```text
Boot with no saved Wi-Fi
  ↓
YWD-Hotspot-XXXX open setup AP
  ↓
http://10.42.0.1/
  ↓
user configures Wi-Fi
  ↓
OLED six-digit one-time setup code
  ↓
https://ywd-hotspot.local:8443/
  ↓
user configures identity/radio/BM/passwords
  ↓
Dashboard handoff
  ↓
RF only if explicitly enabled
```

## SSH behavior

Normal custom images may enable key-only SSH and use a builder-local public key. If SSH is disabled, the image builder does **not** generate or embed an authorized builder key. Public release images ship SSH disabled.

## Release artifacts

Successful public builds place image/checksum files under `os/deploy/`, then generate:

```text
BUILD-METADATA.json
README-FIRST.txt
```

The metadata records factory-clean state, source commit, target, MMDVM variant/pin/patch identity, DMRGateway pin, image filename/size and image SHA-256.

The compressed `.img.xz` is integrity-tested with `xz -t` before acceptance.

## Safety boundaries

- MMDVM-Host remains the sole modem/RF owner.
- RF is disabled until first-boot setup/factory policy explicitly permits it.
- `ywd-headless-oled.service` is the authoritative OLED owner in YWD-Hotspot OS.
- normal app updates preserve the selected MMDVM runtime and do not recompile radio binaries.
- incomplete/failed onboarding falls back to the secure setup path rather than silently enabling RF.
- public image production fails closed on personalization.

## Physical validation

A release image is not known-good because it compiled. The **exact file to be uploaded** must pass setup AP, Wi-Fi handoff, OLED code, first-boot wizard, MMDVM provenance, BrandMeister, Parrot, RF, duplex TS1/TS2 where configured, reboot persistence, explicit RF-autostart persistence, OLED ownership and zero-failed-units testing.

See [`docs/OS-DEVELOPMENT.md`](../docs/OS-DEVELOPMENT.md) and [`docs/RELEASE-PLAN-0.2.0-rc1.md`](../docs/RELEASE-PLAN-0.2.0-rc1.md).
