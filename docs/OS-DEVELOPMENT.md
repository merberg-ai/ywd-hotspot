# YWD-Hotspot OS development

[Project README](../README.md) · [Building](BUILDING.md) · [SSH / SFTP](SSH.md) · [OS builder](../os/README.md) · [Repository policy](REPOSITORY.md)

YWD-Hotspot keeps the application and appliance-image source in one repository. Fresh images are built from the exact application commit that contains the builder; installed appliances then use the normal GitHub update mechanism rather than requiring another SD-card image for routine application updates.

## Accepted public release line

### 0.2.0-rc1

RC1 established the current factory-image/runtime baseline:

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

RC2 intentionally retained RC1 RF/runtime behavior and proved both the fresh-image and updater paths:

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

The exact RC2 image passed a fresh flash/test. A published RC1 appliance then updated to RC2 through the dashboard updater, rebooted cleanly, and reported zero failed systemd units.

The release tags/checkpoints remain immutable evidence of the tested artifacts.

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
- passive DMR voice/RX Monitor capability;
- trusted local telemetry/voice path;
- foundation for plugins that declare matching requirements.

### `upstream`

- exact same pinned MMDVM-Host upstream commit;
- no YWD extension patch;
- extension-dependent plugins unavailable.

The two variants have separate compile-cache identities. DMRGateway remains the same pinned upstream build.

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

`openssh-server` is present in the appliance image so no package installation is required later, but first-boot staging disables `ssh.service` and ships no reusable server host identity.

After setup, authenticated dashboard **SYSTEM -> SSH ACCESS** can:

- create/download an Ed25519 client key for the `ywd` login user;
- enable SSH and boot activation;
- generate unique server host keys locally on first enable;
- disable SSH while preserving authorized keys/server identity;
- export server identity keys for advanced recovery.

Password/root SSH login remains disabled. See **[SSH.md](SSH.md)**.

## Release artifacts

A successful public build places image/checksum artifacts under `os/deploy/` and generates:

```text
BUILD-METADATA.json
README-FIRST.txt
```

Metadata records source commit, target architecture, factory-clean state, MMDVM variant/upstream/patch identity, DMRGateway pin, image filename/size, and image SHA-256.

The exact tested compressed image is the release artifact. A publication-time filename cleanup is acceptable only when the copy remains byte-identical and SHA-256 is reverified.

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

While releases are frozen, `main` stays at the exact accepted public commit so normal appliances do not see unpublished development as an available update. Ongoing docs/repository/development work goes to `dev`.

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

See **[REPOSITORY.md](REPOSITORY.md)** for immutable release-history policy and **[history/RELEASE-PLAN-0.2.0-rc1.md](history/RELEASE-PLAN-0.2.0-rc1.md)** for the completed RC1 acceptance record.
