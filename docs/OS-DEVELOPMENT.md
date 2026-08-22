# YWD-Hotspot OS development

[Project README](../README.md) · [Building](BUILDING.md) · [SSH / SFTP](SSH.md) · [OS builder](../os/README.md) · [RC1 acceptance record](RELEASE-PLAN-0.2.0-rc1.md)

YWD-Hotspot keeps the application and appliance-image source in one repository. Fresh images are built from the exact application commit that contains the builder; installed appliances then use the normal GitHub update mechanism rather than requiring another SD-card image for routine application updates.

## 0.2.0-rc1 completed release flow

```text
checkpoint-builder-0.1.0-image-boot-proven
        │ physically proven baseline
        ▼
release/0.2.0-rc1
        │ release hardening + public factory image
        ▼ exact factory-image physical acceptance
checkpoint-release-0.2.0-rc1-image-proven
        ▼
       dev
        ▼
       main
        ▼
   v0.2.0-rc1
```

Accepted source/image identity:

```text
source commit
1575344d732994a7b54d5afc7f15a88040a274ec

image SHA256
f15232ec599cef550a23dd462ee0f30839cdde6cdf45b7e4b4b1fa929605190c
```

The release tag/checkpoint remain immutable evidence of the tested artifact. Later documentation-only commits on moving branches do not change that accepted source/image identity.

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

For RC1, the public artifact was built only through:

```bash
bash os/builder/BUILD-PUBLIC-RELEASE.sh
```

The wrapper temporarily replaces local builder state with release defaults and restores the developer's original local settings afterward.

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

`openssh-server` is present in the image so no package installation is required later, but first-boot staging explicitly disables `ssh.service` and deletes factory `ssh_host_*` keys.

After setup, authenticated dashboard **SYSTEM -> SSH ACCESS** can:

- create/download an Ed25519 client key for the `ywd` login user;
- enable SSH and boot activation;
- generate unique server host keys locally on first enable;
- disable SSH while preserving authorized keys/server identity;
- export server identity keys for advanced recovery.

Password/root SSH login remains disabled. See **[SSH.md](SSH.md)**.

## Release artifacts

A successful public build places the image/checksum artifacts under `os/deploy/` and generates:

```text
BUILD-METADATA.json
README-FIRST.txt
```

Metadata records source commit, target architecture, factory-clean state, MMDVM variant/upstream/patch identity, DMRGateway pin, image filename/size, and image SHA-256.

The accepted RC1 artifact set includes the exact tested `.img.xz`, `.bmap`, `.info`, checksum file, metadata and first-readme files.

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
[ ] authoritative ywd-headless-oled service owns display
[ ] systemctl --failed reports zero failed units
```

RC1 passed the release-blocking physical checks on the exact published/tested image candidate.

## Promotion policy

For future releases:

1. record exact release commit and artifact SHA-256;
2. physically test the exact artifact to be published;
3. freeze an image-proven checkpoint;
4. promote moving integration/public branches only after acceptance;
5. tag the accepted source;
6. upload the exact tested artifacts;
7. never rebuild a different binary under the same release identity.

See **[REPOSITORY.md](REPOSITORY.md)** for immutable release-history policy.
