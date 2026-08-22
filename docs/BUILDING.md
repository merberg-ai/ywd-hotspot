# 🛠️ Building YWD-Hotspot

[← Docs index](README.md) · [Installation](INSTALL.md) · [Development](GITHUB-SETUP.md) · [OS Development](OS-DEVELOPMENT.md)

YWD-Hotspot separates source validation, source installation, MMDVM runtime selection, normal appliance images, and public factory-release images.

## 1. Source validation

Before installation/image work:

```bash
python3 lib/candidate_validate.py .
python3 -m py_compile lib/*.py os/builder/*.py

bash -n \
  INSTALL.sh INSTALL-core.sh \
  UPDATE.sh UPDATE-core.sh \
  GITHUB-UPDATE.sh GITHUB-UPDATE-core.sh \
  MIGRATE-TO-GITHUB.sh MIGRATE-TO-GITHUB-core.sh \
  os/builder/BUILD.sh os/builder/RUN-BUILD.sh \
  os/builder/BUILD-PUBLIC-RELEASE.sh \
  os/pi-gen/stage2/20-ywd-runtime/01-run.sh \
  os/pi-gen/stage2/25-ywd-firstboot/01-run.sh
```

If Node.js is available:

```bash
for js in web/*.js; do node --check "$js"; done
```

These checks do not replace hardware acceptance. Candidate validation also covers release-critical dynamic/static assets such as duplex dashboard controls, SSH UI assets, and LIVE DMR layout routes.

## 2. Build/install from GitHub source

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

The full installer asks which MMDVM runtime to build.

### YWD Extended — default/recommended

Exact pinned upstream MMDVM-Host plus the verified YWD extension patch. It advertises capabilities used by passive DMR voice/RX Monitor and compatible plugins.

### Stock Upstream

Exact pinned upstream MMDVM-Host with no YWD MMDVM extensions. Normal DMR hotspot operation remains supported; extension-dependent plugins are refused cleanly.

Noninteractive selection:

```bash
sudo YWD_MMDVM_VARIANT=ywd-extended ./INSTALL.sh
sudo YWD_MMDVM_VARIANT=upstream ./INSTALL.sh
```

Recovery installs preserve the existing runtime variant by default. Ordinary application updates do not rebuild or switch it.

## 3. Runtime builders and cache identity

```bash
sudo python3 lib/runtime_build.py install --mmdvm-variant ywd-extended
sudo python3 lib/runtime_build.py install --mmdvm-variant upstream
sudo python3 lib/runtime_build.py status
```

YWD Extended uses `lib/mmdvm_voice_build.py`. Stock uses `lib/mmdvm_upstream_build.py`.

The variants have separate cache namespaces/signatures. Extended cache identity includes the extension API/hash, so an unpatched binary cannot satisfy a patched cache lookup.

Accepted RC1/RC2 radio identities remain:

```text
MMDVM-Host
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

YWD extension API
  2

YWD patch SHA256
  f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a

DMRGateway
  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

## 4. Personalized/development appliance image

Run builder doctor first:

```bash
bash os/builder/DOCTOR.sh
```

Review/select the MMDVM runtime and builder profile:

```bash
python3 os/builder/MMDVM-RUNTIME.py review
python3 os/builder/MMDVM-RUNTIME.py set ywd-extended
# or: python3 os/builder/MMDVM-RUNTIME.py set upstream

python3 os/builder/PROFILE-CLI.py review
python3 os/builder/PROFILE-CLI.py validate
bash os/builder/RUN-BUILD.sh
```

Local runtime cache status:

```bash
python3 os/builder/RUNTIME-CACHE.py status
```

Normal/development images can intentionally include private Wi-Fi, station settings and key-only SSH according to the ignored local builder profile. They are not public release artifacts.

## 5. Public factory release image

Public releases use the fail-closed wrapper:

```bash
bash os/builder/BUILD-PUBLIC-RELEASE.sh
```

The wrapper is intentionally pinned to a specific release identity rather than acting as a generic "publish whatever branch is checked out" command. For the accepted RC2 source it requires:

```text
VERSION   0.2.0-rc2
branch    release/0.2.0-rc2
```

A future release must intentionally update that release identity before building.

The public wrapper:

1. requires clean tracked source;
2. saves the developer's private builder profile/runtime preference;
3. resets hotspot configuration to canonical defaults;
4. removes Wi-Fi/operator/credential/imported-backup preconfiguration;
5. sets RF first boot OFF;
6. sets update channel `main`;
7. disables SSH and embeds no builder authorized key;
8. ensures no reusable SSH server host identity ships;
9. selects default/recommended `ywd-extended`;
10. runs the factory-release checker before and after generated profile creation;
11. runs the normal image build/cache path;
12. validates factory state again;
13. writes `BUILD-METADATA.json` and `README-FIRST.txt`;
14. restores the developer's original local builder settings.

The release gate refuses personalized images rather than trying to sanitize them after the fact.

## Accepted RC2 build

```text
source / tag
  v0.2.0-rc2
  5f0d2967ce0ed728169f7819d2bc227687d6a9b2

published image
  ywd-hotspot-0.2.0-rc2.img.xz

SHA256
  60f74d4c6d25d6a7d9ec35aea24b97bae7a50d35f103a21dc50ee1cbe80f1649
```

The GitHub-facing image was a byte-for-byte copy of the physically tested compressed artifact. The SHA matched before publication; no rebuild/recompression was performed after acceptance.

RC2 was also exercised as an in-place dashboard update from the published RC1 image and passed a subsequent reboot with zero failed systemd units.

## Publication assets

For RC2 the published GitHub assets are:

```text
ywd-hotspot-0.2.0-rc2.img.xz
ywd-hotspot-0.2.0-rc2.bmap
ywd-hotspot-0.2.0-rc2.info
SHA256SUMS
BUILD-METADATA.json
README-FIRST.txt
```

Local builder/deploy filenames may reflect implementation-specific staging names. Artifact identity is established by exact source metadata and SHA-256, not by preserving an awkward local filename.

## Release-image acceptance

A successful compile is not enough. For a future exact artifact intended for publication verify:

```text
[ ] SHA256 verification passes
[ ] xz integrity passes
[ ] no preconfigured Wi-Fi -> YWD setup AP appears
[ ] Wi-Fi handoff works
[ ] OLED one-time code appears
[ ] secure first-boot wizard completes
[ ] shipped runtime identity matches release intent
[ ] RF remains OFF until explicit enable
[ ] SSH remains OFF until explicit enable
[ ] optional SSH client-key/enable flow works when in scope
[ ] BrandMeister connects after configuration
[ ] Parrot works
[ ] simplex/duplex settings operate as configured
[ ] duplex TS1/TS2 work on duplex hardware
[ ] telemetry/BER activity works
[ ] missing RSSI is handled without fake dBm
[ ] reboot preserves settings
[ ] RF autostart works only when operator enabled it
[ ] zero failed systemd units
```

Only after the exact public artifact passes should source be checkpointed/promoted/tagged and the exact tested assets published.

See **[OS-DEVELOPMENT.md](OS-DEVELOPMENT.md)**, **[REPOSITORY.md](REPOSITORY.md)** and the completed **[RC1 acceptance record](history/RELEASE-PLAN-0.2.0-rc1.md)**.
