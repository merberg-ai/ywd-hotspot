# 🛠️ Building YWD-Hotspot

[← Docs index](README.md) · [Installation](INSTALL.md) · [Development](GITHUB-SETUP.md) · [OS Development](OS-DEVELOPMENT.md)

`0.2.0-rc1` separates four build paths: source validation, source installation, MMDVM runtime selection, and complete appliance images.

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
  os/pi-gen/stage2/20-ywd-runtime/01-run.sh
```

If Node.js is available:

```bash
for js in web/*.js; do node --check "$js"; done
```

These checks do not replace hardware acceptance.

## 2. Build/install from GitHub source

```bash
sudo apt update
sudo apt install -y git
cd ~
git clone https://github.com/merberg-ai/ywd-hotspot.git
cd ywd-hotspot
sudo ./INSTALL.sh
```

The full installer asks which MMDVM runtime to build:

### YWD Extended — default/recommended

Exact pinned upstream MMDVM-Host plus the verified YWD extension patch. It advertises capabilities used by RX Monitor and future compatible plugins.

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

Pinned identities:

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
python3 os/builder/MMDVM-RUNTIME.py set ywd-extended   # default
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

## 5. Public factory release image

Public release images use a separate wrapper:

```bash
bash os/builder/BUILD-PUBLIC-RELEASE.sh
```

The wrapper:

1. requires the exact release branch/version and clean tracked source;
2. saves the developer's private local builder profile/runtime preference;
3. resets hotspot configuration to canonical defaults;
4. removes Wi-Fi/operator/credential/imported-backup preconfiguration;
5. sets RF first boot OFF;
6. sets update channel `main`;
7. disables SSH and embeds no builder authorized key;
8. selects default/recommended `ywd-extended`;
9. runs `PUBLIC-RELEASE-CHECK.py` before and after profile generation;
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

## Release-image acceptance

A successful compile is not enough. For the exact artifact intended for GitHub, verify:

```text
[ ] SHA256 verification passes
[ ] xz integrity passes
[ ] no preconfigured Wi-Fi -> YWD setup AP appears
[ ] Wi-Fi handoff works
[ ] OLED one-time code appears
[ ] secure first-boot wizard completes
[ ] shipped runtime reports ywd-extended + exact patch API/hash
[ ] RF remains OFF until explicit enable
[ ] BrandMeister connects after configuration
[ ] Parrot works
[ ] simplex/duplex settings operate as configured
[ ] duplex TS1/TS2 work on duplex hardware
[ ] reboot preserves settings
[ ] RF autostart works only when operator enabled it
[ ] zero failed systemd units
```

Only after the exact public artifact passes should `dev`/`main` promotion and GitHub prerelease publication happen.

See **[OS-DEVELOPMENT.md](OS-DEVELOPMENT.md)** and the release plan for the full promotion sequence.
