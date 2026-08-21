# YWD-Hotspot 0.2.0-rc1 Release Notes

**Status:** release candidate in factory-image acceptance. Publish/promote only after the exact public image passes physical smoke testing.

`0.2.0-rc1` turns the proven YWD-Hotspot builder/appliance into a public-testable image workflow while making the YWD MMDVM extension a disclosed, optional runtime capability.

## Proven starting point

The release branch was created from:

```text
checkpoint-builder-0.1.0-image-boot-proven
a5a6d9483a7cad519ee5288661447875f346b4e7
```

That exact baseline physically passed Pi Zero W + duplex MMDVM first boot, OLED code setup, Wi-Fi, dashboard handoff, BrandMeister, Parrot, RF, reboot persistence, settings persistence and RF autostart when explicitly enabled.

## Public factory image

The release image is generated with no operator/builder preconfiguration:

- no Wi-Fi credentials;
- no callsign/DMR ID;
- no BrandMeister credentials/API key;
- no dashboard password;
- no imported settings;
- no RF autostart;
- SSH disabled with no builder authorized key.

First boot uses the temporary YWD setup AP, then the OLED-code protected hotspot wizard.

## MMDVM runtime variants

### YWD Extended — default/recommended

Pinned upstream MMDVM-Host plus the hash-verified YWD extension patch. Provides passive DMR voice/RX Monitor capabilities and the foundation for future compatible plugins.

### Stock Upstream

Exact pinned upstream MMDVM-Host without YWD extensions. Normal hotspot operation remains supported; extension-dependent plugins are refused cleanly.

The variant is persistent across ordinary app updates and each variant uses a separate compile-cache identity.

Current Extended identity:

```text
MMDVM-Host: dea6e9b2c35857fe6f904c5092bebadb86cbf079
Patch API:  2
Patch SHA:  f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a
DMRGateway: 2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

## Plugin runtime requirements

Trusted plugin dependency tokens now include:

```text
mmdvm-ywd-extended
mmdvm-extension-api-2
mmdvm-cap-passive-dmr-voice
```

Core checks these during installation/enable/start and blocks incompatible plugins rather than allowing mysterious runtime failures.

## First-boot wizard hardening

- Finish Setup displays visible apply/progress state.
- Backend validation errors appear beside the final action.
- successful setup reports the configured dashboard URL/port and automatically hands off;
- canonical schema/config is preserved rather than reconstructed from a legacy subset;
- simplex/duplex is explicit;
- duplex has separate hotspot RX/TX fields;
- builder-provided defaults not edited by the wizard are preserved.

## Builder/release hardening

- persistent runtime compile cache with strict identities;
- public factory profile checker;
- isolated public release wrapper that saves/restores private developer builder settings;
- no SSH authorized key staged when SSH is disabled;
- machine-readable `BUILD-METADATA.json`;
- `README-FIRST.txt` generated beside the release image;
- candidate validator requires complete MMDVM variant runtime support.

## Publication gate

Before this prerelease is published/promoted, the exact public image must pass:

- SHA256/XZ verification;
- setup AP from a completely unconfigured image;
- Wi-Fi handoff;
- OLED one-time-code setup;
- dashboard handoff;
- YWD Extended runtime identity verification;
- BrandMeister/Parrot/RF;
- duplex TS1/TS2 on the target hardware;
- reboot/settings/RF-autostart persistence;
- zero failed units.

After that acceptance, the exact source tree will be checkpointed, fast-forwarded to `dev` and `main`, then published as the `v0.2.0-rc1` GitHub prerelease with the exact tested artifacts.
