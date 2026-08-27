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

These checks do not replace hardware acceptance. Candidate validation covers release-critical dynamic/static assets, including duplex controls, SSH UI, startup themes, software-channel UI, MODEM/MMDVM UI, plugin package/runtime integration and CSP-safe release wiring.

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

Exact pinned upstream MMDVM-Host plus the verified YWD extension patch. It advertises capabilities used by passive DMR/RX Monitor and compatible plugins.

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

Current RC3 runtime identity:

```text
MMDVM-Host
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

YWD extension API
  2

YWD patch SHA256
  77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994

Capabilities
  slot_affinity_queued_work
  dmr_pdu_route_metadata
  dmr_rx_audio_events

DMRGateway
  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

RC1/RC2 Extended remains a recognized legacy-compatible generation. See [UPGRADING.md](UPGRADING.md) for the explicit refresh path.

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

The wrapper is intentionally pinned to a specific release identity rather than acting as a generic "publish whatever branch is checked out" command. The published RC3 build required:

```text
VERSION   0.2.0-rc3
branch    release/0.2.0-rc3
source    3823140b9fd4d6e73fe9066af4b2280628f62f5e
```

Each future release must intentionally advance that release identity before building.

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

## Accepted RC3 build

```text
source / tag
  v0.2.0-rc3
  3823140b9fd4d6e73fe9066af4b2280628f62f5e

published image
  ywd-hotspot-0.2.0-rc3.img.xz

SHA256
  5c3151b2a39f5a800b703d8925c53cddcf7bf49d8fcb59eda6bed30afc4413cc
```

The public filename was normalized after the build. The renamed compressed artifact was re-hashed and retained the exact accepted SHA-256; it was not rebuilt or recompressed after physical acceptance. GitHub's uploaded asset reports the same digest.

The final fresh-flash acceptance covered the setup AP, Wi-Fi handoff, OLED code, first-run setup, dashboard auth/UI, RF-off and SSH-off factory policy, current runtime identity, BrandMeister/Parrot, reboot persistence and zero failed units.

The published RC2 -> RC3 application updater path also passed separately.

## Publication assets

The RC3 GitHub release publishes:

```text
ywd-hotspot-0.2.0-rc3.img.xz
SHA256SUMS
BUILD-METADATA.json
README-FIRST.txt
```

Builder-local `.bmap`/`.info` or staging filenames may exist locally without being required release assets. Artifact identity is established by exact source metadata and SHA-256.

## Release-image acceptance

A successful compile is not enough. For a future artifact intended for publication verify:

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

Only after the exact public artifact passes should the accepted source be checkpointed/promoted/tagged and the exact tested assets published.

See **[OS-DEVELOPMENT.md](OS-DEVELOPMENT.md)**, **[REPOSITORY.md](REPOSITORY.md)** and **[RC3 publication acceptance](history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md)**.
