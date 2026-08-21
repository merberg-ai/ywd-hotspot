# YWD-Hotspot OS development

[Project README](../README.md) · [Building](BUILDING.md) · [OS builder](../os/README.md) · [Release plan](RELEASE-PLAN-0.2.0-rc1.md)

YWD-Hotspot keeps the application and appliance-image source in one repository. Fresh images are built from the exact application commit that contains the builder; installed appliances then use the normal GitHub update mechanism.

## Current release flow

```text
checkpoint-builder-0.1.0-image-boot-proven
        │ physically proven baseline
        ▼
release/0.2.0-rc1
        │ release hardening + public factory image
        ▼ exact factory-image physical acceptance
       dev
        ▼ promotion sanity
       main
        ▼
 v0.2.0-rc1 GitHub prerelease
```

The checkpoint is immutable evidence of the tested pre-release baseline. `main` and `dev` are not moved until the exact public factory artifact is accepted.

## Builder entry points

```text
os/builder/DOCTOR.sh                  host/source preflight
os/builder/PROFILE-CLI.py             hotspot/image profile
os/builder/SYSTEM-CLI.py              OS/system profile
os/builder/MMDVM-RUNTIME.py           Extended vs Stock preference
os/builder/RUNTIME-CACHE.py           persistent compile cache
os/builder/RUN-BUILD.sh                normal/personalized image build
os/builder/BUILD-PUBLIC-RELEASE.sh     factory-clean release build
os/builder/PUBLIC-RELEASE-CHECK.py     fail-closed release gate
os/builder/RELEASE-ARTIFACTS.py        release metadata/readme generator
```

## Normal image build

```bash
bash os/builder/DOCTOR.sh
python3 os/builder/PROFILE-CLI.py review
python3 os/builder/SYSTEM-CLI.py review
python3 os/builder/MMDVM-RUNTIME.py review
bash os/builder/RUN-BUILD.sh
```

Normal builds may intentionally contain local Wi-Fi, station identity, credentials, SSH policy, or imported settings according to the private builder profile. Those images are **not** public release artifacts.

## MMDVM runtime variants

### `ywd-extended` — default/recommended

- exact pinned MMDVM-Host upstream commit;
- exact hash-verified YWD extension patch;
- extension API 2;
- passive DMR voice/RX Monitor capability;
- foundation for future plugins that declare matching requirements.

### `upstream`

- exact same pinned MMDVM-Host upstream commit;
- no YWD extension patch;
- extension-dependent plugins unavailable.

The two variants have separate compile-cache identities. DMRGateway remains the same pinned upstream build.

## Public factory image

Run only from the release branch:

```bash
bash os/builder/BUILD-PUBLIC-RELEASE.sh
```

The wrapper temporarily replaces the local builder state with release defaults and restores the developer's original local settings afterward.

The public image is required to contain:

```text
Wi-Fi credentials       none
Callsign/DMR ID          none
BM credentials/API key  none
Dashboard password      none
Imported settings       none
RF autostart             OFF
SSH                      disabled; no builder authorized key
Update channel           main
MMDVM runtime            ywd-extended (default/recommended)
```

The release checker validates both the source profile and generated first-boot payload. `provision.env`, `factory-provision.json`, and `factory-restore.json` are forbidden in the public artifact path.

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
```

## Release artifacts

After a successful public build, `RELEASE-ARTIFACTS.py` writes:

```text
BUILD-METADATA.json
README-FIRST.txt
```

Metadata records source commit, target architecture, factory-clean state, MMDVM variant/upstream/patch identity, DMRGateway pin, image filename/size, and image SHA-256.

## Physical acceptance checklist

For the exact artifact to be uploaded:

```text
[ ] checksum and xz integrity pass
[ ] setup AP appears with no preconfigured Wi-Fi
[ ] Wi-Fi handoff succeeds
[ ] OLED setup code works
[ ] setup wizard completes and dashboard handoff works
[ ] no operator defaults from the builder are present
[ ] MMDVM runtime = ywd-extended
[ ] extension API/hash match pins.env
[ ] BrandMeister connects after user configuration
[ ] Parrot succeeds
[ ] RF both directions
[ ] duplex TS1/TS2 when configured on duplex hardware
[ ] reboot persists configuration
[ ] RF comes up on reboot only after user enables autostart
[ ] authoritative ywd-headless-oled service owns display
[ ] systemctl --failed reports zero failed units
```

## Promotion

After acceptance:

1. record the exact release commit and image SHA-256;
2. freeze an immutable `checkpoint-release-0.2.0-rc1-image-proven` ref;
3. update release wording from candidate to physically accepted;
4. fast-forward `dev` to the accepted release commit;
5. perform promotion sanity validation;
6. fast-forward `main` to the same accepted tree;
7. create/publish `v0.2.0-rc1` as a GitHub prerelease with the exact tested assets.

Never rebuild a different binary after acceptance and upload it under the same release identity.
