# YWD-Hotspot 0.2.0-rc1 Release Plan / Acceptance Record

The `0.2.0-rc1` release plan is complete through physical image acceptance, source checkpoint/promotion and tag creation. This document now records the exact accepted state rather than describing those steps as future work.

## Exact accepted identity

```text
RC source commit
  1575344d732994a7b54d5afc7f15a88040a274ec

Tag
  v0.2.0-rc1

Image
  image_2026-08-22-ywd-hotspot-0.2.0-rc1-pi-zero-lite.img.xz

Image SHA256
  f15232ec599cef550a23dd462ee0f30839cdde6cdf45b7e4b4b1fa929605190c

Accepted checkpoint
  checkpoint-release-0.2.0-rc1-image-proven
```

The release branch was originally based on the physically proven builder checkpoint:

```text
checkpoint-builder-0.1.0-image-boot-proven
a5a6d9483a7cad519ee5288661447875f346b4e7
```

## Public prebuilt image policy

The GitHub release image is a true factory image and contains no operator/builder-specific configuration.

Accepted public-image state:

- no saved Wi-Fi SSID or password;
- no callsign;
- no DMR ID or hotspot ID;
- no BrandMeister Hotspot Security password;
- no BrandMeister API key;
- no dashboard/control password;
- no imported settings backup;
- RF disabled on first boot;
- SSH disabled on first boot;
- no builder SSH authorized client key;
- no reusable SSH server host identity;
- only application defaults and first-boot onboarding state.

With no usable Wi-Fi profile, the image starts the temporary YWD-Hotspot setup AP. The user configures Wi-Fi, reconnects to the LAN, then completes the OLED-code protected first-boot hotspot wizard.

The public release build fails closed if forbidden preconfiguration is detected.

## 0.2.0-rc1 delivered scope

### 1. MMDVM runtime variants

- `ywd-extended` is the recommended/default variant.
- `upstream` is supported as an explicit stock opt-out.
- YWD Extended uses the pinned MMDVM-Host upstream commit plus the verified YWD extension patch.
- Stock Upstream uses the exact pinned upstream source without YWD extensions.
- Cache identities are distinct between variants.
- Installed runtime variant/provenance persists across normal updates.
- Plugin capability checks can require YWD extension API/capabilities.

### 2. First-boot / duplex hardening

- visible inline finish errors and apply/progress state;
- success reports the configured dashboard URL/port and automatically hands off;
- canonical schema-preserving setup submission;
- explicit simplex/duplex controls;
- separate duplex hotspot RX/TX frequencies;
- TS1/TS2 operation on duplex hardware.

### 3. Telemetry / dashboard hardening

- local-only MMDVM MQTT broker on `127.0.0.1:18883`;
- trusted structured telemetry/session bridge;
- bounded passive DMR voice bridge for YWD Extended;
- BER/activity/Last Heard instrumentation;
- data-aware RSSI handling;
- RSSI UI hidden when the modem firmware reports no usable RSSI;
- no BER-to-dBm estimation;
- release-critical static UI routes covered by candidate validation.

### 4. SSH hardening

- OpenSSH server installed in YWD-Hotspot OS but factory OFF;
- no default/reusable SSH password;
- no builder client key in public image;
- no reusable server host identity in public image;
- unique host keys generated locally on first SSH enable;
- dashboard `SYSTEM -> SSH ACCESS` controls;
- generated Ed25519 client key with one-time private-key delivery;
- public-key-only policy;
- password and root SSH login disabled;
- disable/re-enable preserves authorized clients and server identity;
- separate recovery-only server identity export.

### 5. Public image distribution

Release build produces:

```text
*.img.xz
*.bmap
*.info
SHA256SUMS-YWD-HOTSPOT-OS
BUILD-METADATA.json
README-FIRST.txt
```

The exact image accepted on hardware is the image used for publication; it is not regenerated after acceptance under the same release identity.

## Physical acceptance result

The exact factory artifact was built, flashed and tested on the reference Raspberry Pi Zero W + duplex MMDVM setup with no release-blocking issues.

Acceptance covered the intended matrix, including:

```text
[PASS] image/checksum integrity
[PASS] clean first boot / setup AP
[PASS] Wi-Fi handoff
[PASS] OLED one-time setup code
[PASS] secure first-boot wizard
[PASS] dashboard handoff
[PASS] YWD Extended runtime identity
[PASS] BrandMeister / Parrot / RF
[PASS] duplex operation on target hardware
[PASS] telemetry / BER / LIVE DMR presentation
[PASS] graceful no-RSSI behavior on reference HAT firmware
[PASS] settings/reboot persistence
[PASS] explicit RF-autostart persistence
[PASS] factory SSH OFF / optional dashboard enablement
[PASS] service/runtime smoke checks
```

## Completed promotion sequence

```text
checkpoint-builder-0.1.0-image-boot-proven
        ↓
release/0.2.0-rc1
        ↓ source/static/factory validation
exact public factory image
        ↓ physical acceptance
checkpoint-release-0.2.0-rc1-image-proven
        ↓
dev (fast-forwarded to accepted source)
        ↓
main (fast-forwarded to accepted source)
        ↓
v0.2.0-rc1 tag
        ↓
GitHub prerelease publication uses the exact tested artifact set
```

Historical checkpoint/release/tag refs remain immutable. Post-release documentation fixes on `main`/`dev` do not change the source/image represented by `v0.2.0-rc1`.
