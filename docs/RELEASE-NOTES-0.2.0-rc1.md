# YWD-Hotspot 0.2.0-rc1 Release Notes

**Status:** physically accepted public release candidate; source is frozen/tagged as `v0.2.0-rc1` and the exact tested factory artifacts are the publication set.

`0.2.0-rc1` turns the proven YWD-Hotspot builder/appliance into a public-testable image workflow while making the YWD MMDVM extension a disclosed, optional runtime capability.

## Exact accepted release identity

```text
Source commit
  1575344d732994a7b54d5afc7f15a88040a274ec

Tag
  v0.2.0-rc1

Image
  image_2026-08-22-ywd-hotspot-0.2.0-rc1-pi-zero-lite.img.xz

Image SHA256
  f15232ec599cef550a23dd462ee0f30839cdde6cdf45b7e4b4b1fa929605190c

Physical checkpoint
  checkpoint-release-0.2.0-rc1-image-proven
```

The exact image was flashed and physically tested on the reference Raspberry Pi Zero W + duplex MMDVM appliance before source promotion/tagging. The accepted image is the artifact intended for publication; it is not rebuilt after acceptance under the same release identity.

## Proven starting point

The RC release branch originated from:

```text
checkpoint-builder-0.1.0-image-boot-proven
a5a6d9483a7cad519ee5288661447875f346b4e7
```

That earlier baseline had already physically passed Pi Zero W + duplex MMDVM first boot, OLED code setup, Wi-Fi, dashboard handoff, BrandMeister, Parrot, RF, reboot/settings persistence and explicitly enabled RF autostart.

## Public factory image

The accepted release image contains no operator/builder preconfiguration:

- no Wi-Fi credentials;
- no callsign/DMR ID;
- no BrandMeister credentials/API key;
- no dashboard password;
- no imported settings;
- no RF autostart;
- SSH disabled;
- no builder authorized client key;
- no reusable SSH server host identity.

First boot uses the temporary YWD setup AP, then the OLED-code protected hotspot wizard. RF and SSH remain off until explicitly enabled.

## SSH / SFTP access

The public image includes OpenSSH server software for optional maintenance, but there is no default SSH password and port 22 is closed at factory state.

After first-boot setup:

```text
unlock dashboard controls
  -> SYSTEM -> SSH ACCESS
  -> CREATE & EXPORT CLIENT KEY (normally user ywd)
  -> ENABLE SSH ACCESS
```

YWD enforces public-key-only authentication, disables password/root SSH login, generates unique server host keys on the appliance, and does not retain the generated client private key after delivering it.

On YWD-Hotspot OS, `ywd` has passwordless sudo, so its private login key is an administrator credential. See `docs/SSH.md`.

## MMDVM runtime variants

### YWD Extended — default/recommended

Pinned upstream MMDVM-Host plus the hash-verified YWD extension patch. Provides passive DMR voice/RX Monitor capabilities and the foundation for future compatible plugins.

### Stock Upstream

Exact pinned upstream MMDVM-Host without YWD extensions. Normal hotspot operation remains supported; extension-dependent plugins are refused cleanly.

The variant persists across ordinary app updates and each variant uses a separate compile-cache identity.

Current Extended identity:

```text
MMDVM-Host: dea6e9b2c35857fe6f904c5092bebadb86cbf079
Patch API:  2
Patch SHA:  f3542c80d6b854552f8affea933e6cd306908eb1ebc32c0cc55f6161e0ba362a
DMRGateway: 2a3306de313cf4c094c2031c9ced5a6858bbbfcc
```

## Plugin/runtime requirements

Trusted plugin dependency tokens include:

```text
mmdvm-ywd-extended
mmdvm-extension-api-2
mmdvm-cap-passive-dmr-voice
```

Core checks these during installation/enable/start and blocks incompatible plugins rather than allowing mysterious runtime failures.

## First-boot / duplex hardening

- Finish Setup displays visible apply/progress state.
- Backend validation errors appear beside the final action.
- Successful setup reports the configured dashboard URL/port and automatically hands off.
- Canonical schema/config is preserved rather than reconstructed from a legacy subset.
- Simplex/duplex is explicit.
- Duplex has separate hotspot RX/TX fields and TS1/TS2 support.
- Builder-provided defaults not edited by the wizard are preserved.

## LIVE DMR / telemetry hardening

The accepted RC includes the trusted loopback MMDVM telemetry path and enhanced browser instrumentation:

- dedicated local Mosquitto listener on `127.0.0.1:18883`;
- structured telemetry bridge and bounded passive voice bridge;
- BER/Last Heard/activity instrumentation;
- animated RX/TX presentation;
- RSSI displayed only when modem firmware supplies a usable value;
- RSSI-only UI hidden when unsupported rather than showing fake/stuck dBm;
- horizontal BER/quality layout when RSSI is unavailable.

Physical RC testing established that the reference duplex HAT firmware reports valid BER/voice traffic but no usable RSSI (`rssi=0`). YWD therefore does not synthesize dBm from BER. Real RSSI support may require compatible MMDVM_HS HAT firmware with firmware-side RSSI reporting enabled; YWD does not automatically flash modem firmware.

## Builder/release hardening

- persistent runtime compile cache with strict identities;
- public factory profile checker;
- isolated public release wrapper that saves/restores private developer builder settings;
- no SSH authorized key staged when SSH is disabled;
- no reusable server host keys in the public image;
- machine-readable `BUILD-METADATA.json`;
- `README-FIRST.txt` generated beside the release image;
- candidate validator covers coherent runtime/UI/static-route capabilities;
- release source and exact image checksum recorded independently.

## Physical acceptance completed

The exact public artifact passed the intended acceptance path, including:

- build/checksum integrity;
- setup AP from a completely unconfigured image;
- Wi-Fi handoff;
- OLED one-time-code setup;
- dashboard handoff;
- YWD Extended runtime identity;
- BrandMeister/Parrot/RF;
- duplex operation on target hardware;
- telemetry/dashboard behavior;
- settings and reboot persistence;
- explicitly enabled RF autostart behavior;
- SSH factory-off state;
- clean service/runtime checks.

After acceptance, the exact source was frozen as `checkpoint-release-0.2.0-rc1-image-proven`, fast-forwarded to `dev` and `main`, and tagged `v0.2.0-rc1`.

Post-release documentation corrections on moving branches do not rewrite the immutable tag/checkpoint or the image that was physically tested.
