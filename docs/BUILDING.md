# 🛠️ Building YWD-Hotspot

[← Docs index](README.md) · [Installation](INSTALL.md) · [Development](GITHUB-SETUP.md) · [OS Development](OS-DEVELOPMENT.md)

YWD-Hotspot separates four build paths: source validation, source installation, MMDVM runtime selection, and complete appliance images.

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

These checks do not replace hardware acceptance. Candidate validation also covers release-critical dynamic/static assets such as the duplex dashboard controls, SSH UI route and LIVE DMR layout route.

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

Exact pinned upstream MMDVM-Host plus the verified YWD extension patch. It advertises capabilities used by passive DMR voice/RX Monitor and future compatible plugins.

### Stock Upstream

Exact pinned upstream MMDVM-Host with no YWD MMDVM extensions. Normal DMR hotspot operation remains supported; plugins declaring extension requirements are refused cleanly.

Noninteractive selection:

```bash
sudo YWD_MMDVM_VARIANT=ywd-extended ./INSTALL.sh
sudo YWD_MMDVM_VARIANT=upstream ./INSTALL.sh
```

Recovery installs preserve the existing runtime variant by default. Ordinary app updates do not rebuild or switch it.

## 3. Runtime builders and cache identity

Dispatcher:

```bash
sudo python3 lib/runtime_build.py install --mmdvm-variant ywd-extended
sudo python3 lib/runtime_build.py install --mmdvm-variant upstream
sudo python3 lib/runtime_build.py status
```

YWD Extended uses `lib/mmdvm_voice_build.py`. Stock uses `lib/mmdvm_upstream_build.py`.

The variants have separate cache namespaces/signatures. Extended cache identity includes the extension API/hash, so an unpatched binary cannot satisfy a patched cache lookup.

Pinned RC1 identities:

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

Review/select the MMDVM runtime:

```bash
python3 os/builder/MMDVM-RUNTIME.py review
python3 os/builder/MMDVM-RUNTIME.py set ywd-extended
# or
python3 os/builder/MMDVM-RUNTIME.py set upstream
```

Review the builder profile, then build:

```bash
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

Public release images use the fail-closed wrapper:

```bash
bash os/builder/BUILD-PUBLIC-RELEASE.sh
```

For `0.2.0-rc1` the wrapper requires the exact release branch/version and clean source. It:

1. saves the developer's private local builder profile/runtime preference;
2. resets hotspot configuration to canonical defaults;
3. removes Wi-Fi/operator/credential/imported-backup preconfiguration;
4. sets RF first boot OFF;
5. sets update channel `main`;
6. disables SSH and embeds no builder authorized key;
7. ensures no reusable SSH server host identity is shipped;
8. selects default/recommended `ywd-extended`;
9. runs the factory-release checker before and after profile generation;
10. runs the normal image build/cache path;
11. validates factory state again;
12. writes `BUILD-METADATA.json` and `README-FIRST.txt` beside the image;
13. restores the developer's original local profile.

The release gate refuses personalized images rather than trying to sanitize them after the fact.

Expected release assets:

```text
*.img.xz
*.bmap
*.info
SHA256SUMS-YWD-HOTSPOT-OS
BUILD-METADATA.json
README-FIRST.txt
```

## 0.2.0-rc1 accepted build

The physically accepted RC1 source/image pair is:

```text
source commit
1575344d732994a7b54d5afc7f15a88040a274ec

image
image_2026-08-22-ywd-hotspot-0.2.0-rc1-pi-zero-lite.img.xz

SHA256
f15232ec599cef550a23dd462ee0f30839cdde6cdf45b7e4b4b1fa929605190c
```

Do not rebuild a different image and call it the same RC1 artifact. Use the tag `v0.2.0-rc1` to inspect/reproduce the exact source that generated the accepted image.

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

See **[OS-DEVELOPMENT.md](OS-DEVELOPMENT.md)** and **[RELEASE-PLAN-0.2.0-rc1.md](RELEASE-PLAN-0.2.0-rc1.md)**.
