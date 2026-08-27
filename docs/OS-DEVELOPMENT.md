# YWD-Hotspot OS development

[Project README](../README.md) · [Building](BUILDING.md) · [SSH / SFTP](SSH.md) · [OS builder](../os/README.md) · [Repository policy](REPOSITORY.md)

YWD-Hotspot keeps the application and appliance-image source in one repository. Fresh images are built from the exact application commit that contains the builder; installed appliances then use the normal GitHub update mechanism rather than requiring another SD-card image for routine application updates.

## Accepted public release line

### 0.2.0-rc1

RC1 established the public factory-image/runtime baseline:

```text
source
  v0.2.0-rc1
  1575344d732994a7b54d5afc7f15a88040a274ec

checkpoint
  checkpoint-release-0.2.0-rc1-image-proven

image SHA256
  f15232ec599cef550a23dd462ee0f30839cdde6cdf45b7e4b4b1fa929605190c
```

### 0.2.0-rc2

RC2 retained RC1 RF/runtime behavior and proved both fresh-image and RC1 -> RC2 updater paths:

```text
source
  v0.2.0-rc2
  5f0d2967ce0ed728169f7819d2bc227687d6a9b2

checkpoint
  checkpoint-release-0.2.0-rc2-image-updater-proven

published image
  ywd-hotspot-0.2.0-rc2.img.xz

image SHA256
  60f74d4c6d25d6a7d9ec35aea24b97bae7a50d35f103a21dc50ee1cbe80f1649
```

### 0.2.0-rc3

RC3 is the current physically accepted public-testing release and adds the proven DMR RX Monitor / Phase 3J path, current YWD Extended capability generation, final first-run/UI integration work and expanded updater/runtime hardening.

```text
source
  v0.2.0-rc3
  3823140b9fd4d6e73fe9066af4b2280628f62f5e

release branch
  release/0.2.0-rc3

checkpoint
  checkpoint-release-0.2.0-rc3-final-ui-wiring-proven-pre-image

published image
  ywd-hotspot-0.2.0-rc3.img.xz

image SHA256
  5c3151b2a39f5a800b703d8925c53cddcf7bf49d8fcb59eda6bed30afc4413cc
```

The exact RC3 image passed fresh-flash acceptance. The published RC2 -> RC3 application updater path also passed. Release tags/checkpoints/branches remain immutable evidence of the tested artifacts even when `main`/`dev` later receive documentation or development commits.

## Builder entry points

```text
os/builder/DOCTOR.sh                  host/source preflight
os/builder/PROFILE-CLI.py             hotspot/image profile
os/builder/SYSTEM-CLI.py              OS/system profile
os/builder/MMDVM-RUNTIME.py           Extended vs Stock preference
os/builder/RUNTIME-CACHE.py           persistent compile cache
os/builder/RUN-BUILD.sh               normal/personalized image build
os/builder/BUILD-PUBLIC-RELEASE.sh    factory-clean release build
os/builder/PUBLIC-RELEASE-CHECK.py    fail-closed release gate
os/builder/RELEASE-ARTIFACTS.py       release metadata/readme generator
```

Historical milestone-specific builder aliases are not current entry points. Use the unified builder commands above.

## Normal image build

```bash
bash os/builder/DOCTOR.sh
python3 os/builder/PROFILE-CLI.py review
python3 os/builder/SYSTEM-CLI.py review
python3 os/builder/MMDVM-RUNTIME.py review
bash os/builder/RUN-BUILD.sh
```

Normal builds may intentionally contain local Wi-Fi, station identity, credentials, SSH policy, imported settings or a builder-local SSH public key according to the private builder profile. Those images are **not** public release artifacts.

## MMDVM runtime variants

### `ywd-extended` — default/recommended

- exact pinned MMDVM-Host upstream commit;
- exact hash-verified YWD extension patch;
- extension API 2;
- trusted passive DMR/RX Monitor capability set;
- local telemetry/voice path;
- foundation for plugins that declare matching requirements.

### `upstream`

- exact same pinned MMDVM-Host upstream commit;
- no YWD extension patch;
- extension-dependent plugins unavailable.

Current RC3 YWD Extended identity:

```text
MMDVM-Host upstream
  dea6e9b2c35857fe6f904c5092bebadb86cbf079

YWD patch SHA256
  77c712fae4a02c59ded8bfa777e796041cc081ba445817b2f0c07c3456a40994

Extension API
  2

Capabilities
  slot_affinity_queued_work
  dmr_pdu_route_metadata
  dmr_rx_audio_events

DMRGateway upstream
  2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

The two variants have separate compile-cache identities. RC1/RC2 Extended is recognized as legacy-compatible rather than silently rebuilt.

## Public factory image

Public artifacts are built only through:

```bash
bash os/builder/BUILD-PUBLIC-RELEASE.sh
```

The wrapper is release-identity-specific and fail-closed. It temporarily replaces local builder state with release defaults and restores the developer's original local settings afterward.

The public image is required to contain:

```text
Wi-Fi credentials       none
Callsign/DMR ID          none
BM credentials/API key  none
Dashboard password      none
Imported settings       none
RF autostart             OFF
SSH                      disabled
Builder authorized key  none
Reusable SSH host keys  none
Update channel           main
MMDVM runtime            ywd-extended
```

The release checker validates both the source profile and generated first-boot payload. `provision.env`, `factory-provision.json`, and `factory-restore.json` are forbidden in the public release path.

## First-boot factory path

```text
Flash image
  ↓
No saved Wi-Fi
  ↓
YWD-Hotspot-XXXX setup AP / 10.42.0.1
  ↓
User configures Wi-Fi
  ↓
OLED six-digit setup code
  ↓
HTTPS :8443 first-boot wizard
  ↓
user configures identity/radio/BM/passwords
  ↓
Dashboard handoff
  ↓
RF only if explicitly enabled
SSH still OFF until explicitly enabled later
```

The LAN IP shown by the appliance is the authoritative setup target. `ywd-hotspot.local` is an optional mDNS convenience rather than a requirement.

## Public SSH lifecycle

`openssh-server` is present in the appliance image so no package installation is required later, but first-boot staging disables SSH and ships no reusable server host identity.

After setup, authenticated dashboard **SYSTEM -> SSH ACCESS** can create/export a client key, enable/disable SSH, and manage the appliance's unique server identity. Password/root SSH login remains disabled. See **[SSH.md](SSH.md)**.

## Release artifacts

A successful public build places image/checksum artifacts under `os/deploy/` and generates:

```text
BUILD-METADATA.json
README-FIRST.txt
```

Metadata records source commit, target architecture, factory-clean state, MMDVM variant/upstream/patch identity, DMRGateway pin, image filename/size, and image SHA-256.

For RC3 the public release assets are:

```text
ywd-hotspot-0.2.0-rc3.img.xz
SHA256SUMS
BUILD-METADATA.json
README-FIRST.txt
```

The exact tested compressed image is the release artifact. A publication-time filename cleanup is acceptable only when the bytes remain identical and SHA-256 is reverified.

## Physical acceptance checklist

A successful compile is not enough. For an artifact intended for publication verify:

```text
[ ] checksum and xz integrity pass
[ ] setup AP appears with no preconfigured Wi-Fi
[ ] Wi-Fi handoff succeeds
[ ] OLED setup code works
[ ] setup wizard completes and dashboard handoff works
[ ] no operator defaults from the builder are present
[ ] MMDVM runtime/provenance matches intended release
[ ] BrandMeister connects after user configuration
[ ] Parrot succeeds
[ ] RF both directions
[ ] simplex/duplex behavior matches configured hardware
[ ] duplex TS1/TS2 when configured
[ ] telemetry/dashboard activity works
[ ] unsupported RSSI fails gracefully without fake dBm
[ ] reboot persists configuration
[ ] RF comes up on reboot only after explicit operator autostart enablement
[ ] SSH is factory OFF and optional enablement works when part of the release scope
[ ] authoritative OLED service owns the display
[ ] systemctl --failed reports zero failed units
```

For a release intended to exercise the updater, also test a supported prior public release -> candidate transition and reboot the upgraded appliance before calling the updater path proven.

## Release freeze / promotion policy

Release tags, release branches and proven checkpoints are immutable acceptance evidence. `main` is the public/update line and may receive intentional post-release documentation commits; `dev` is the active integrated development line. A docs-only commit after publication does not change the source/image represented by an existing release tag.

For a future release:

1. start from the intended `dev` baseline;
2. record exact release source/version;
3. build and hash the exact candidate artifact;
4. physically test the exact artifact to be published;
5. exercise updater transition when that is part of the release goal;
6. freeze a proven checkpoint;
7. promote `main` deliberately;
8. tag the accepted source;
9. upload the exact tested artifact set;
10. never rebuild a different image under the same release identity.

See **[REPOSITORY.md](REPOSITORY.md)** and **[RC3 publication acceptance](history/RC3-FACTORY-IMAGE-PUBLICATION-PASS.md)**.
