# YWD-Hotspot OS

[Project README](../README.md) · [Installation](../docs/INSTALL.md) · [SSH / SFTP](../docs/SSH.md) · [Building](../docs/BUILDING.md) · [OS Development](../docs/OS-DEVELOPMENT.md)

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

## Normal / personalized image

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

Normal images may intentionally use Wi-Fi preconfiguration, station settings, imported backups or builder-profile key-only SSH. Those are private/custom artifacts, not the GitHub release image.

## MMDVM runtime variants

### YWD Extended — default/recommended

Exact pinned upstream MMDVM-Host plus the verified YWD extension patch. Provides the current trusted passive DMR/RX Monitor capability set and the runtime surface used by compatible plugins.

### Stock Upstream

Exact pinned upstream MMDVM-Host without YWD extensions.

Select:

```bash
python3 os/builder/MMDVM-RUNTIME.py set ywd-extended
python3 os/builder/MMDVM-RUNTIME.py set upstream
```

The two variants have separate compile-cache identities. DMRGateway remains pinned upstream.

Current RC3 YWD Extended identity:

```text
MMDVM-Host upstream
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

YWD patch SHA256
  77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994

Extension API
  2

DMRGateway upstream
  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

## Persistent runtime compile cache

Status:

```bash
python3 os/builder/RUNTIME-CACHE.py status
```

The cache is reused only when strict build signatures match. For YWD Extended the signature includes upstream commit, patch API/hash, architecture, compiler and relevant flags. Stock uses its own namespace/signature.

## Public GitHub release image

The accepted `0.2.0-rc3` public artifact was built with:

```bash
bash os/builder/BUILD-PUBLIC-RELEASE.sh
```

The wrapper requires the intended release branch/version and a clean tracked checkout. It saves the developer's local builder profile/runtime preference, resets to release defaults, builds, verifies factory state, writes provenance assets, then restores the original local state.

Accepted RC3 source:

```text
release/0.2.0-rc3
3823140b9fd4d6e73fe9066af4b2280628f62f5e
```

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
Builder SSH client key   not embedded
Reusable SSH host keys   none
Update channel           main
MMDVM runtime            ywd-extended
```

`PUBLIC-RELEASE-CHECK.py` validates both the source profile and generated first-boot payload and refuses forbidden personalization.

The public image deliberately uses the product-default **YWD Extended** runtime. That is shipped software capability, not operator preconfiguration.

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
https://<LAN-IP>:8443/
  ↓
user configures identity/radio/BM/passwords
  ↓
Dashboard handoff
  ↓
RF only if explicitly enabled
SSH remains OFF
```

`ywd-hotspot.local` is an optional mDNS convenience when supported by the client/network, not the only setup URL.

## SSH behavior

### Public factory image

The OS includes `openssh-server`, but the first-boot image stage explicitly:

- disables `ssh.service`;
- removes `ssh_host_*` private/public server keys;
- embeds no builder client key.

After setup, the authenticated dashboard exposes **SYSTEM -> SSH ACCESS**. The recommended flow is:

```text
CREATE & EXPORT CLIENT KEY for ywd
  -> ENABLE SSH ACCESS
  -> connect on port 22 using the downloaded private key
```

The appliance then generates unique server host keys and enforces public-key-only authentication. SSH passwords and root SSH login remain disabled.

The generated client private key is not retained on the hotspot. On YWD-Hotspot OS, the `ywd` account has passwordless sudo, so the client key is an administrator credential.

See [`docs/SSH.md`](../docs/SSH.md).

### Normal custom images

A private builder profile may intentionally enable key-only SSH and stage a builder-local public key. If SSH is disabled, the image builder does not generate/embed an authorized builder key.

Custom/development images are never interchangeable with the factory public release artifact.

## 0.2.0-rc3 accepted artifact

```text
source
3823140b9fd4d6e73fe9066af4b2280628f62f5e

tag
v0.2.0-rc3

published image
ywd-hotspot-0.2.0-rc3.img.xz

SHA256
5c3151b2a39f5a800b703d8925c53cddcf7bf49d8fcb59eda6bed30afc4413cc
```

The exact compressed image passed the final fresh-flash acceptance on the reference Pi Zero W + MMDVM setup. The public filename was normalized after the build and re-hashed; byte identity remained unchanged and GitHub reports the same SHA-256 digest for the uploaded asset.

The published RC2 -> RC3 dashboard/application updater path was also exercised successfully without silently recompiling the radio runtime.

Immutable accepted refs:

```text
checkpoint-release-0.2.0-rc3-final-ui-wiring-proven-pre-image
release/0.2.0-rc3
v0.2.0-rc3
```

## Release artifacts

The published RC3 release includes:

```text
ywd-hotspot-0.2.0-rc3.img.xz
SHA256SUMS
BUILD-METADATA.json
README-FIRST.txt
```

Metadata records factory-clean state, source commit, target, MMDVM variant/pin/patch identity, DMRGateway pin, image filename/size and image SHA-256.

The compressed `.img.xz` is integrity-tested with `xz -t` before acceptance.

## Safety boundaries

- MMDVM-Host remains the sole modem/RF owner.
- RF is disabled until first-boot/operator policy explicitly permits it.
- SSH is disabled in the public factory state and is operator-controlled afterward.
- `ywd-headless-oled.service` is the authoritative OLED owner in YWD-Hotspot OS.
- normal app updates preserve the selected MMDVM runtime and do not recompile radio binaries.
- incomplete/failed onboarding falls back to the secure setup path rather than silently enabling RF.
- public image production fails closed on personalization.
- missing modem RSSI is not synthesized from BER.

## Physical validation

A release image is not known-good because it compiled. The **exact file to be uploaded** must pass setup AP, Wi-Fi handoff, OLED code, first-boot wizard, MMDVM provenance, BrandMeister, Parrot, RF, duplex TS1/TS2 where configured, telemetry/dashboard behavior, graceful optional-RSSI behavior, reboot persistence, explicit RF-autostart persistence, factory SSH policy, OLED ownership and zero-failed-units testing.

See [`docs/OS-DEVELOPMENT.md`](../docs/OS-DEVELOPMENT.md) and [`docs/history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md`](../docs/history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md).
